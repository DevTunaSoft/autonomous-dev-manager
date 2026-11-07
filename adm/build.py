"""Approved plan -> frozen tests -> scaffold -> sandboxed repair loop -> honest report.

The chain of custody this module guarantees (tests in tests/test_build_052.py):
  * it runs only on an APPROVED plan (intake.require_approved is the gate);
  * the AI first turns the approved plain-language checks into real tests, which are
    then FROZEN: the code-writing loop cannot touch test files or requirements.json;
  * the tests must be non-trivial -- they must contain real assertions AND must FAIL
    before any code exists. Tests that pass against an empty stub are rejected, because
    they would let the builder 'succeed' without doing anything;
  * the code is written by the local model and accepted only when the frozen tests pass
    twice; the test runner is the only gate (never the model's opinion);
  * generated code is executed through the caller's runner. In production that is the
    Windows sandbox; this module never runs code unsandboxed on its own initiative.

What it does NOT promise, and the report says so: that the generated tests capture exactly
what the person meant. They are the AI's reading of checks the person approved in plain words.
"""
from __future__ import annotations
import ast, json, os, time
from pathlib import Path
from . import intake
from .engine import SafetyError
from .skills import select_guidance

STUB = '"""ADM will write this file to make the approved tests pass. It starts empty on purpose."""\n'
CONFLICTS = ('app.py', 'test_app.py', 'requirements.json')
MAX_TEST_CHARS = 60_000


def requirements_doc(plan: dict) -> dict:
    c = plan['content']
    return {'title': c['title'], 'summary': c['summary'],
            'source_file': 'app.py',
            'requirements': [{'id': f'FEAT-{i:03d}', 'description': f} for i, f in enumerate(c['features'], 1)],
            'checks_in_plain_words': c['tests'],
            'approved_request': plan['request'],
            'note': 'The AI wrote test_app.py from checks_in_plain_words. app.py must satisfy those tests.'}


def test_prompt(plan: dict) -> str:
    c = plan['content']
    checks = '\n'.join(f'{i}. {t}' for i, t in enumerate(c['tests'], 1))
    return (
        "Write automated tests for a small Python program, from the plain-language checks below. "
        "Reply with JSON only: {\"files\": [{\"path\": \"test_app.py\", \"content\": \"...\"}]} and nothing else.\n"
        "Rules:\n"
        "- Put every test in one file named test_app.py.\n"
        "- The program under test is a module named app (import it with 'from app import ...' or 'import app').\n"
        "- Use only Python's standard library and the built-in unittest framework.\n"
        "- Write one test method per check, each with a real assertion (self.assertEqual and friends). "
        "Never write a test that is always true, and never weaken a check.\n"
        "- Choose clear function names in app for the behaviour each check describes; the program itself "
        "will be written afterwards to match these tests.\n"
        "- Do not write app.py here, only the tests.\n\n"
        f"WORKFLOW GUIDANCE:\n{select_guidance('testing', c['summary'] + ' ' + checks, max_chars=800)}\n"
        f"TITLE: {c['title']}\nWHAT IT SHOULD DO:\n{c['summary']}\n\nCHECKS TO TURN INTO TESTS:\n{checks}\n")


def validate_tests(answer) -> str:
    """Accept a model answer only if it is one real, non-trivial test file that targets `app`."""
    if not isinstance(answer, dict) or set(answer) != {'files'} or not isinstance(answer['files'], list):
        raise SafetyError('The AI did not return tests in the expected form')
    files = answer['files']
    if len(files) != 1:
        raise SafetyError('Exactly one test file (test_app.py) is expected')
    item = files[0]
    if not isinstance(item, dict) or set(item) != {'path', 'content'}:
        raise SafetyError('The test file entry is malformed')
    if item['path'] != 'test_app.py':
        raise SafetyError('The test file must be named test_app.py')
    content = item['content']
    if not isinstance(content, str) or not 20 <= len(content) <= MAX_TEST_CHARS:
        raise SafetyError('The test file is empty or too large')
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError, RecursionError) as exc:   # ValueError: null bytes; RecursionError: deep nesting
        raise SafetyError(f'The generated tests are not valid Python: {exc}') from exc
    imports_app = any(
        (isinstance(n, ast.Import) and any(a.name == 'app' for a in n.names)) or
        (isinstance(n, ast.ImportFrom) and n.module == 'app')
        for n in ast.walk(tree))
    if not imports_app:
        raise SafetyError('The tests do not import the program (app); they would not test it')
    test_funcs = [n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name.startswith('test')]
    if not test_funcs:
        raise SafetyError('The tests contain no test methods')
    asserts = sum(isinstance(n, ast.Assert) or
                  (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr.startswith('assert'))
                  for n in ast.walk(tree))
    if asserts < 1:
        raise SafetyError('The tests contain no assertions, so they check nothing')
    return content


def _write(path: Path, text: str) -> None:
    with open(path, 'w', encoding='utf-8', newline='') as stream:
        stream.write(text)


def is_adm_project(folder) -> bool:
    """True only for a folder ADM itself built (so amending it is safe)."""
    folder = Path(folder)
    if not ((folder / 'requirements.json').is_file() and (folder / 'app.py').is_file()
            and (folder / 'test_app.py').is_file()):
        return False
    try:
        data = json.loads((folder / 'requirements.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get('source_file') == 'app.py' and 'checks_in_plain_words' in data


def _test_method_names(content: str) -> set:
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError, RecursionError):
        return set()
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith('test')}


def amend_test_prompt(plan: dict, old_tests: str) -> str:
    c = plan['content']
    checks = '\n'.join(f'{i}. {t}' for i, t in enumerate(c['tests'], 1))
    return (
        "You are adding to an existing Python program's tests. Reply with JSON only: "
        "{\"files\": [{\"path\": \"test_app.py\", \"content\": \"...\"}]} and nothing else.\n"
        "Rules:\n"
        "- Return the COMPLETE new test_app.py.\n"
        "- KEEP every existing test method exactly as it is — same names, same assertions. Do not rename, "
        "remove, weaken or skip any of them.\n"
        "- ADD one new test method per new check below, each with a real assertion.\n"
        "- The program is the module app (import with 'from app import ...' or 'import app'). Standard library only.\n\n"
        f"EXISTING test_app.py (keep all of these tests):\n{old_tests[:20000]}\n\n"
        f"NEW CHECKS TO ADD:\n{checks}\n")


def amend_project(root: Path, plan: dict, new_tests: str) -> None:
    """Overwrite only test_app.py and extend requirements.json; the app source is left for the repair loop."""
    root = Path(root)
    req = json.loads((root / 'requirements.json').read_text(encoding='utf-8'))
    req.setdefault('checks_in_plain_words', [])
    req['checks_in_plain_words'] = list(req['checks_in_plain_words']) + list(plan['content']['tests'])
    existing = req.setdefault('requirements', [])
    base = len(existing)
    existing += [{'id': f'FEAT-{base + i:03d}', 'description': f} for i, f in enumerate(plan['content']['features'], 1)]
    _write(root / 'requirements.json', json.dumps(req, indent=2, ensure_ascii=False))
    _write(root / 'test_app.py', new_tests)


def scaffold(root: Path, plan: dict, test_content: str) -> None:
    """Write requirements.json, the frozen tests and an empty app.py stub. Never overwrite user files."""
    root = Path(root)
    if not root.is_dir():
        raise SafetyError('The approved project folder does not exist')
    present = [name for name in CONFLICTS if (root / name).exists()]
    if present:
        raise SafetyError('This folder already has ' + ', '.join(present) +
                          '. Building into an existing project is not supported yet; use a new project.')
    _write(root / 'requirements.json', json.dumps(requirements_doc(plan), indent=2, ensure_ascii=False))
    _write(root / 'test_app.py', test_content)
    _write(root / 'app.py', STUB)


def _say(on_event, stage, **detail):
    if on_event is None:
        return
    try:
        on_event(stage, detail)
    except Exception:
        pass


def build_from_plan(plan_path, evidence, *, test_generator, code_generator, model,
                    runner=None, timeout=120, max_repairs=3, inference_timeout=600,
                    require_sandbox=True, on_event=None):
    """Full build. `test_generator`/`code_generator` are (model, prompt, timeout) callables.

    `runner` runs the tests; in production pass a sandbox runner. With require_sandbox=True
    (the default) a non-sandbox runner is refused, so generated code is never run unprotected.
    """
    from .ollama_direct import _direct_repair_unlocked
    from .project_lock import exclusive_project
    plan = intake.require_approved(plan_path)                      # gate: approved plans only
    root = Path(plan['folder'])
    if runner is not None and require_sandbox and getattr(runner, 'adm_isolation', None) != 'sandbox':
        raise SafetyError('Refusing to run generated code without the sandbox')
    if runner is None and require_sandbox:
        raise SafetyError('No sandbox runner was provided; generated code will not be run')

    report = {'plan_id': plan['id'], 'folder': str(root), 'model': model, 'created': time.time(),
              'stage': 'generating_tests', 'status': 'in_progress', 'mode': 'new',
              'honest_scope': ('Tests were written by the AI from the plain-language checks you approved. '
                               'A pass means the generated code satisfies those tests, which approximate '
                               'your intent; ADM does not prove the tests capture exactly what you meant.')}

    # Decide how to treat the target folder: a fresh scaffold, resume of this plan's own new build,
    # or an amend of an ADM project. "Empty" ignores ADM's own lock file, so ADM never writes alongside
    # a person's own work. The whole operation holds the project lock so two builds cannot race on the
    # same folder — a second concurrent build is refused cleanly instead of corrupting the scaffold.
    if not root.is_dir():
        raise SafetyError('The approved project folder does not exist')
    with exclusive_project(root):
        _recover_interrupted(root, Path(evidence))            # clean up any crashed prior build, under the lock
        contents = [p for p in root.iterdir() if p.name not in ('.adm-repair.lock', '__pycache__')]
        empty = not contents
        # A non-empty 'new' folder with our scaffold is an interrupted prior build of THIS plan
        # (approve created the folder empty), so reset and build fresh rather than treat it as an amend.
        resumed_new = (not empty and plan.get('mode') == 'new' and is_adm_project(root))
        if empty or resumed_new:
            if resumed_new:
                _reset_scaffold(root)
            _say(on_event, 'writing_tests')
            answer = test_generator(model, test_prompt(plan), timeout=inference_timeout)
            test_content = validate_tests(answer)
            report['stage'] = 'scaffolding'
            _say(on_event, 'scaffolding')
            scaffold(root, plan, test_content)
            amend = False
        elif is_adm_project(root):
            report['mode'] = 'amend'
            _say(on_event, 'writing_tests', amend=True)
            old_tests = (root / 'test_app.py').read_text(encoding='utf-8')
            old_names = _test_method_names(old_tests)
            answer = test_generator(model, amend_test_prompt(plan, old_tests), timeout=inference_timeout)
            test_content = validate_tests(answer)
            if not old_names <= _test_method_names(test_content):
                raise SafetyError('The updated tests dropped or renamed existing checks; refusing to weaken your project.')
            report['stage'] = 'amending'
            amend_project(root, plan, test_content)
            amend = True
        else:
            raise SafetyError('This folder has files that ADM did not create. ADM can build into an empty folder '
                              'or add to a project it made; it will not change your own files. Choose another folder.')

        report['stage'] = 'writing_and_testing_code'
        _say(on_event, 'writing_code')
        repair = _direct_repair_unlocked(root, Path(evidence), model=model, generator=code_generator,
                                         runner=runner, timeout=timeout, max_repairs=max_repairs,
                                         inference_timeout=inference_timeout, on_event=on_event)
    report['repair'] = repair
    report['isolation'] = repair.get('isolation', 'none')

    if repair['status'] == 'baseline_passed' and amend:
        # Amending and everything already passes: the requested change needed no code change.
        report['status'] = 'already_passing'
        report['message'] = 'All checks, new and existing, already pass — no code change was needed.'
    elif repair['status'] == 'baseline_passed':
        # New project whose tests passed before any code was written: they test nothing.
        report['status'] = 'rejected_trivial_tests'
        report['message'] = ('The generated tests passed before any program was written, so they are not '
                             'really testing anything. Nothing was built. Try rephrasing your request.')
    elif repair['status'] == 'verified_direct_repair':
        report['status'] = 'built'
        report['message'] = f'Built and all {len(plan["content"]["tests"])} checks pass (verified twice in the sandbox).'
    else:
        report['status'] = 'could_not_build'
        report['message'] = ('ADM could not make all the checks pass within the attempt limit. The code and '
                             'the test output were kept so you can see how far it got.')
    report['stage'] = 'done'
    return report


def builds_root(state) -> Path:
    return Path(state) / 'builds'


def evidence_root(state) -> Path:
    return Path(state) / 'evidence'


def _safe_evidence(state, plan) -> Path:
    """A STABLE per-plan evidence directory, guaranteed to be outside the project folder.

    Stable (not timestamped) so a retry after a crash finds the previous attempt's recovery journal.
    """
    root = Path(plan['folder']).resolve()
    ev = (evidence_root(state) / plan['id']).resolve()
    if ev == root or root in ev.parents or ev in root.parents:
        raise SafetyError('Evidence directory must be outside the project folder')
    return ev


def _recover_interrupted(root: Path, ev: Path) -> None:
    """Roll back a half-applied patch from a crashed build, then clear stale evidence for a clean retry."""
    import shutil
    if not ev.exists():
        return
    try:
        if (ev / 'repair-journal.json').exists():
            from .repair_recovery import recover_journal
            recover_journal(root, ev)
    except SafetyError:
        pass
    shutil.rmtree(ev, ignore_errors=True)


def _reset_scaffold(root: Path) -> None:
    """Remove this plan's own scaffold so an interrupted new build starts fresh (never touches user files)."""
    import shutil
    for name in CONFLICTS:
        p = root / name
        if p.is_file():
            p.unlink()
    for d in root.glob('__pycache__'):
        shutil.rmtree(d, ignore_errors=True)


def save_report(state, report: dict) -> Path:
    folder = builds_root(state)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{report['plan_id']}.json"
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    os.replace(tmp, path)
    return path


def run_build(state, plan_path, *, test_generator, code_generator, model, runner,
              timeout=120, max_repairs=3, require_sandbox=True, on_event=None) -> dict:
    """The path the dashboard uses: safe evidence location + a persisted report for the stats tiles."""
    plan = intake.require_approved(plan_path)
    try:
        from . import runtime_install
        runtime_install.ensure_runtime()   # install the bundled Python (frozen app only); no-op in source
    except SafetyError:
        pass                               # project_python() will report clearly if no Python is available
    ev = _safe_evidence(state, plan)                   # recovery now happens inside build_from_plan, under the lock
    report = build_from_plan(plan_path, ev, test_generator=test_generator,
                             code_generator=code_generator, model=model, runner=runner,
                             timeout=timeout, max_repairs=max_repairs, require_sandbox=require_sandbox,
                             on_event=on_event)
    report['checks'] = plan['content']['tests']
    report['evidence'] = str(ev)
    save_report(state, report)
    return report
