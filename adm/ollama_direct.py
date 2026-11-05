"""Direct local Ollama repair trial, with deterministic evidence and guarded file edits.

Only for trusted disposable Python projects. This is NOT an OS sandbox.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
import urllib.request
import urllib.error
from urllib.parse import urlsplit
from .agent import (safe_local_model, validate_project, protected_hashes,
                    source_hashes, test_command, atomic_json, make_prompt)
from .engine import SafetyError, run_checked
from .repair_recovery import prepare_journal, recover_journal, finish_journal
from .project_lock import exclusive_project
from .context import (excerpt_failure, AttemptLedger, check_patch, build_repair_prompt)
from .repomap import select_context
from .backends import safe_model

DEFAULT_ENDPOINT = 'http://127.0.0.1:11434'
# Ollama truncates prompts that exceed the context window WITHOUT telling the caller,
# so the window is requested explicitly and oversized prompts are refused up front.
NUM_CTX = 8192
CHARS_PER_TOKEN = 3          # conservative for source code
MAX_SOURCE_FILE_CHARS = 20000
DEFAULT_INFERENCE_TIMEOUT = 300


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Never follow an Ollama redirect: prompts and source may be confidential."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SafetyError('Local Ollama attempted HTTP redirect; request blocked')


_LOCAL_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}), _RejectRedirects())



def request_patch(model: str, prompt: str, *, endpoint: str = DEFAULT_ENDPOINT,
                  timeout: int = 90) -> dict:
    safe_local_model(model)
    parsed = urlsplit(endpoint)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.username
            or parsed.password or parsed.path or parsed.query or parsed.fragment
            or not parsed.port):
        raise SafetyError('Only a local loopback Ollama endpoint is permitted')
    if not 1 <= timeout <= 600:
        raise SafetyError('Invalid inference timeout')
    payload = json.dumps({'model': model.removeprefix('ollama/'), 'stream': False,
                          'format': 'json', 'prompt': prompt,
                          'options': {'num_ctx': NUM_CTX, 'temperature': 0}}).encode('utf-8')
    request = urllib.request.Request(endpoint + '/api/generate', data=payload,
                                     headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with _LOCAL_OPENER.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise SafetyError('Local model returned HTTP error')
            raw = response.read(1_000_001)
    except (OSError, TimeoutError, urllib.error.HTTPError) as exc:
        raise SafetyError(f'Local Ollama request failed: {exc}') from exc
    if len(raw) > 1_000_000:
        raise SafetyError('Model response too large')
    try:
        answer = json.loads(json.loads(raw)['response'])
    except (ValueError, KeyError, TypeError) as exc:
        raise SafetyError('Model did not return valid patch JSON') from exc
    if not isinstance(answer, dict) or set(answer) != {'files'} or not isinstance(answer['files'], list):
        raise SafetyError('Invalid patch envelope')
    return answer


request_patch.adm_live_generator = True      # talks to a real model server


def apply_patch(root: Path, patch: dict) -> list[str]:
    """Validate *all* changes before writing any; only replace existing app .py files."""
    files = patch['files']
    if not 1 <= len(files) <= 12:
        raise SafetyError('Expected 1 to 12 file replacements')
    updates = []
    seen = set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {'path', 'content'}:
            raise SafetyError('Invalid file replacement')
        name, content = item['path'], item['content']
        if not isinstance(name, str) or not isinstance(content, str) or len(content) > 250_000:
            raise SafetyError('Invalid file replacement data')
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts or len(rel.parts) != 1 or not name.endswith('.py') or name.startswith('test_'):
            raise SafetyError('Only existing top-level application Python files can be edited')
        path = root / name
        if name in seen or not path.is_file() or path.is_symlink():
            raise SafetyError('Duplicate, missing, or symlink target')
        seen.add(name)
        try:
            compile(content, name, 'exec')
        except SyntaxError as exc:
            raise SafetyError(f'Generated code is not valid Python: {exc}') from exc
        updates.append((path, content))
    # Atomic replacement per file. A failed partial replacement is recovered from the
    # original bytes in finally below, and no edits are committed unless all succeed.
    originals = [(path, path.read_bytes()) for path, _ in updates]
    try:
        for path, content in updates:
            fd, tmp = tempfile.mkstemp(prefix='.adm-patch-', dir=root)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8', newline='') as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(tmp, path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
    except Exception:
        for path, old in originals:
            path.write_bytes(old)
        raise
    return [p.name for p, _ in updates]


def _save_text(path: Path, text: str) -> None:
    path.write_text(text, encoding='utf-8', errors='replace', newline='')


def _direct_repair_unlocked(root, evidence, *, model='ollama/qwen2.5-coder:3b',
                  max_repairs=2, timeout=90, generator=request_patch,
                  inference_timeout=DEFAULT_INFERENCE_TIMEOUT,
                  escalation_model=None, escalation_generator=None, escalate_after=2):
    """Evidence-backed repair. Generator injection permits fake-server tests, not live claims.

    The test runner is the only gate. The model sees a bounded excerpt of each failure
    and the files that matter, but full output is saved and every failing test is named.
    """
    if safe_model(model)[0] == 'remote':
        raise SafetyError('The primary model must run on this PC')
    if not 1 <= max_repairs <= 5:
        raise SafetyError('Invalid repair count')
    if escalation_generator is not None and not escalation_model:
        raise SafetyError('An escalation generator needs an escalation model name')
    if escalation_model:
        safe_model(escalation_model, allow_remote=True)   # remote needs consent inside its generator
    root, evidence = Path(root).resolve(), Path(evidence).resolve()
    validate_project(root, evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    report_path = evidence / 'ollama-direct-report.json'
    if report_path.exists():
        if (evidence / 'repair-journal.json').exists():
            recover_journal(root, evidence)
            raise SafetyError('Interrupted repair restored; submit a fresh job with new evidence')
        raise SafetyError('Evidence directory already contains a trial; choose a new directory')
    protected = protected_hashes(root)
    initial = source_hashes(root)
    baseline = run_checked(test_command(), root, root, timeout=timeout)
    report = {'status': 'baseline_passed' if baseline['exit_code'] == 0 else 'baseline_failed',
              'model': model, 'baseline': baseline, 'attempts': [], 'live_model_verified': False, 'network_generator': False,
              'gate': 'tests_only',
              'escalation': {'configured': escalation_generator is not None,
                             'model': escalation_model, 'used': False},
              'warning': 'Trusted disposable projects only; no OS sandbox'}
    atomic_json(report_path, report)
    if baseline['exit_code'] == 0:
        return report
    requirements = (root / 'requirements.json').read_text(encoding='utf-8')
    failure = baseline['output']
    _save_text(evidence / 'baseline-output.log', failure)
    failure_file = 'baseline-output.log'
    ledger = AttemptLedger()
    budget = int(NUM_CTX * CHARS_PER_TOKEN * 0.8)
    for index in range(1, max_repairs + 1):
        # Save originals for rollback if the model touches tests or a test fails.
        originals = {p.name: p.read_bytes() for p in root.glob('*.py') if not p.name.startswith('test_')}
        report['status'] = 'inference_in_progress'
        atomic_json(report_path, report)
        view = ctx = patch = None
        escalated = (escalation_generator is not None
                     and (index > escalate_after or ledger.stuck()))
        use_generator = escalation_generator if escalated else generator
        use_model = escalation_model if escalated else model
        try:
            view = excerpt_failure(failure, saved_to=failure_file)
            notes = ledger.notes()
            fixed = len(requirements[:12000]) + len(view['text']) + len(notes) + 1400
            ctx = select_context(root, failure, budget - fixed)
            prompt = build_repair_prompt(requirements, view['text'], index, ctx['text'], notes)
            if len(prompt) > budget:
                raise SafetyError('Prompt would exceed the model context window; refusing silent truncation')
            patch = use_generator(use_model, prompt, timeout=inference_timeout)
            repeated = ledger.seen_patch(patch)
            if repeated is not None:
                raise SafetyError(f'Model repeated the patch from attempt {repeated}; not applied again')
            check_patch(root, patch, set(ctx['full']))
            prepare_journal(root, evidence, patch)
            changed = apply_patch(root, patch)
            report['status'] = 'testing_patch'
            atomic_json(report_path, report)
            result = run_checked(test_command(), root, root, timeout=timeout)
            safe = protected_hashes(root) == protected
            # A second independent invocation guards against a one-off/flaky green test.
            # Never mark success based on only one passing process.
            verification = None
            if result['exit_code'] == 0 and safe and source_hashes(root) != initial:
                verification = run_checked(test_command(), root, root, timeout=timeout)
            safe = safe and protected_hashes(root) == protected
            successful = (verification is not None and verification['exit_code'] == 0
                          and safe and source_hashes(root) != initial)
            report['attempts'].append({'number': index, 'files': changed, 'test': result,
                                       'independent_retest': verification,
                                       'protected_unchanged': safe, 'passed': successful,
                                       'generator': 'escalation' if escalated else 'primary',
                                       'model': use_model,
                                       'failure_view': {k: view[k] for k in (
                                           'total_chars', 'shown_chars', 'omitted_chars',
                                           'failing_tests', 'all_failures_named')},
                                       'context': {'full': ctx['full'], 'map_only': ctx['map_only']}})
            if escalated:
                report['escalation']['used'] = True
            if successful:
                # Commit the recovery journal BEFORE publishing success. A crash
                # between those operations must never leave a "verified" report
                # beside a journal that the next invocation would roll back.
                report['status'] = 'verification_passed_commit_pending'
                atomic_json(report_path, report)
                finish_journal(evidence)
                report['status'] = 'verified_direct_repair'
                # A network generator proves only that a server answered, not that the server is a real model
                # (tests use fake servers). Only live_acceptance may promote this to live_model_verified.
                report['network_generator'] = bool(getattr(use_generator, 'adm_live_generator', False))
                atomic_json(report_path, report)
                return report
            failure = result['output']
            failure_file = f'attempt-{index}-output.log'
            _save_text(evidence / failure_file, failure)
            ledger.record(index, patch, failure, changed)
        except (SafetyError, ValueError, OSError) as exc:
            report['attempts'].append({'number': index, 'error': str(exc), 'passed': False,
                                       'generator': 'escalation' if escalated else 'primary',
                                       'model': use_model,
                                       'failure_view': ({k: view[k] for k in (
                                           'total_chars', 'shown_chars', 'omitted_chars',
                                           'failing_tests', 'all_failures_named')} if view else None)})
            if escalated:
                report['escalation']['used'] = True
            # Keep the real test output for the next try; just tell the model what was refused.
            ledger.add_note(f'Attempt {index} was rejected before testing: {str(exc)[:200]}.')
        finally:
            if report['status'] != 'verified_direct_repair':
                if (evidence / 'repair-journal.json').exists():
                    recover_journal(root, evidence)
                else:
                    for name, data in originals.items():
                        (root / name).write_bytes(data)
            else:
                finish_journal(evidence)
        report['status'] = 'repair_failed'
        atomic_json(report_path, report)
        if protected_hashes(root) != protected:
            report['status'] = 'blocked_protected_file_change'
            atomic_json(report_path, report)
            break
    return report


def direct_repair(root, evidence, *, model='ollama/qwen2.5-coder:3b',
                  max_repairs=2, timeout=90, generator=request_patch,
                  inference_timeout=DEFAULT_INFERENCE_TIMEOUT,
                  escalation_model=None, escalation_generator=None, escalate_after=2):
    """Hold exclusive project ownership across baseline, inference, edits and tests."""
    with exclusive_project(root):
        return _direct_repair_unlocked(root, evidence, model=model,
                                       max_repairs=max_repairs, timeout=timeout,
                                       generator=generator, inference_timeout=inference_timeout,
                                       escalation_model=escalation_model,
                                       escalation_generator=escalation_generator,
                                       escalate_after=escalate_after)
