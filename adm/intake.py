"""Plain-language request -> plan in plain words -> explicit approval. Nothing here writes code.

Rules this module enforces (tests/test_intake_052.py):
  * a plan is only ever produced by a LOCAL model (no prompt leaves this PC);
  * a plan is saved as 'awaiting_approval' and tied to its content by a SHA-256;
  * `require_approved` refuses anything not approved, or edited after approval;
  * a plan with open questions cannot be approved: the request must be clarified first;
  * a project folder is created only AFTER approval, never for a rejected plan;
  * an existing folder is accepted, but system folders, drive roots, symlinks and the
    sandbox-denied shared locations are refused.
"""
from __future__ import annotations
import hashlib, json, os, re, secrets, time
from pathlib import Path
from .engine import SafetyError

MAX_REQUEST = 4000
MIN_REQUEST = 10
LIMITS = {'features': (15, 200), 'tests': (20, 300), 'questions': (5, 300)}
_WINDOWS_SYSTEM = ('c:\\windows', 'c:\\program files', 'c:\\program files (x86)', 'c:\\programdata')


def projects_root(home: Path | None = None) -> Path:
    home = Path(home) if home else Path.home()
    return (home / 'Documents' / 'ADM Projects') if os.name == 'nt' else (home / 'ADM Projects')


def validate_request(text) -> str:
    if not isinstance(text, str):
        raise SafetyError('The request must be text')
    text = text.strip()
    if '\x00' in text:
        raise SafetyError('The request contains an invalid character')
    if len(text) < MIN_REQUEST:
        raise SafetyError('Please describe what you want in at least a sentence')
    if len(text) > MAX_REQUEST:
        raise SafetyError(f'Please keep the request under {MAX_REQUEST} characters')
    return text


def slugify(text: str) -> str:
    words = re.findall(r'[a-z0-9]+', text.lower())[:5]
    return '-'.join(words)[:40] or 'project'


def check_existing_folder(folder) -> Path:
    import ntpath
    raw = str(folder)
    low = ntpath.normcase(ntpath.normpath(raw))
    for prefix in ('\\\\?\\', '\\\\.\\'):           # extended-length prefixes must not bypass the guards
        if low.startswith(prefix):
            low = low[len(prefix):]
            if low.startswith('unc\\'):
                low = '\\\\' + low[4:]
    if re.fullmatch(r'[a-z]:\\?', low) or low in ('/', ''):
        raise SafetyError('A whole drive cannot be a project folder')
    for bad in _WINDOWS_SYSTEM:
        if low == bad or low.startswith(bad + '\\'):
            raise SafetyError('System folders cannot be project folders')
    from .sandbox import refuse_hardened_location
    refuse_hardened_location(raw)
    path = Path(raw)
    try:
        if path.is_symlink():
            raise SafetyError('Linked folders are not supported')
        if not path.is_dir():
            raise SafetyError('That folder does not exist')
        return path.resolve()
    except OSError as exc:                       # e.g. a path far too long for the filesystem
        raise SafetyError('That folder path cannot be used') from exc


def describe_existing(folder: Path) -> dict:
    """What ADM can see without reading any file contents."""
    py = sorted(p.name for p in folder.glob('*.py') if not p.name.startswith('test_'))[:50]
    tests = sorted(p.name for p in folder.glob('test_*.py'))[:50]
    return {'python_files': py, 'test_files': tests, 'has_requirements': (folder / 'requirements.json').is_file(),
            'is_empty': not any(folder.iterdir())}


def plan_prompt(request: str, existing: dict | None) -> str:
    base = (
        "You plan small software projects for a person who does not code. Reply with JSON only, with exactly "
        "these keys: title (short name), summary (2-3 plain sentences saying what will be built), "
        "features (list of plain-language things the finished app does), tests (list of plain checks, each "
        "written as 'When <something happens>, <this result is expected>'), needs_internet (true or false), "
        "questions (list; only questions you truly cannot guess, otherwise an empty list). "
        "Keep it small and buildable as a single Windows program in Python. No jargon.\n")
    if existing is not None:
        base += ("The person already has a project folder. It contains these Python files: "
                 f"{existing['python_files']} and these test files: {existing['test_files']}. "
                 "Plan changes to fit it; do not plan a rewrite.\n")
    return base + "REQUEST:\n" + request


def _text_list(value, name, required):
    max_items, max_len = LIMITS[name]
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise SafetyError(f'The plan\'s {name} were not a list of sentences')
    items = [' '.join(x.split())[:max_len] for x in value if x.strip()][:max_items]
    if required and not items:
        raise SafetyError(f'The plan had no {name}')
    return items


def parse_plan(answer) -> dict:
    if not isinstance(answer, dict):
        raise SafetyError('The model did not return a plan')
    title = answer.get('title'); summary = answer.get('summary')
    if not isinstance(title, str) or not title.strip() or not isinstance(summary, str) or not summary.strip():
        raise SafetyError('The plan is missing its title or summary')
    questions = _text_list(answer.get('questions', []), 'questions', False)
    return {'title': ' '.join(title.split())[:80], 'summary': ' '.join(summary.split())[:600],
            'features': _text_list(answer.get('features'), 'features', not questions),
            'tests': _text_list(answer.get('tests'), 'tests', not questions),
            'needs_internet': bool(answer.get('needs_internet', False)),
            'questions': questions}


def _digest(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def _body(plan: dict) -> dict:
    keys = ('request', 'mode', 'folder', 'model', 'content')
    return {k: plan[k] for k in keys}


def _save(plan_dir: Path, plan: dict) -> None:
    # Unique temp name so two concurrent saves can't rename the same file out from under each other.
    tmp = plan_dir / f'plan.json.{os.getpid()}.{secrets.token_hex(4)}.tmp'
    tmp.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding='utf-8')
    final = plan_dir / 'plan.json'
    for attempt in range(20):
        try:
            os.replace(tmp, final)
            return
        except PermissionError:
            # Windows can deny an atomic rename-over briefly while another writer holds the target.
            if attempt == 19:
                raise
            time.sleep(0.05)


def create_plan(state, request_text: str, *, mode: str, folder, generator, model: str,
                timeout: int = 300, home: Path | None = None) -> dict:
    """Ask the local model for a plan and save it, unapproved. `mode` is 'new' or 'existing'."""
    request = validate_request(request_text)
    if mode not in ('new', 'existing'):
        raise SafetyError("Choose 'new project' or 'existing project'")
    if not callable(generator):
        raise SafetyError('No local model is available to make a plan')
    if mode == 'existing':
        target = check_existing_folder(folder)
        existing = describe_existing(target)
        target_text = str(target)
    else:
        existing, target_text = None, ''
    answer = generator(model, plan_prompt(request, existing), timeout)
    content = parse_plan(answer)
    if mode == 'new':
        target_text = str(projects_root(home) / slugify(content['title']))
    plan_id = time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3)
    plan = {'id': plan_id, 'status': 'awaiting_approval' if not content['questions'] else 'needs_answers',
            'request': request, 'mode': mode, 'folder': target_text, 'model': model,
            'created': time.time(), 'content': content}
    plan['sha256'] = _digest(_body(plan))
    plan_dir = Path(state) / 'plans' / plan_id
    plan_dir.mkdir(parents=True, exist_ok=False)
    _save(plan_dir, plan)
    plan['path'] = str(plan_dir / 'plan.json')
    return plan


def load_plan(path) -> dict:
    path = Path(path)
    try:
        plan = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, RecursionError) as exc:
        raise SafetyError('The plan file cannot be read') from exc
    if not isinstance(plan, dict):
        raise SafetyError('The plan file is not a valid plan')
    plan['path'] = str(path)
    return plan


def _verify(plan: dict) -> None:
    try:
        ok = plan.get('sha256') == _digest(_body(plan))
    except KeyError:
        ok = False
    if not ok:
        raise SafetyError('The plan was changed after it was shown to you; make a new plan')


def approve(path) -> dict:
    plan = load_plan(path)
    _verify(plan)
    if plan['status'] != 'awaiting_approval':
        raise SafetyError('This plan cannot be approved' + (' until its questions are answered'
                          if plan['status'] == 'needs_answers' else f" (it is {plan['status']})"))
    if plan['mode'] == 'new':
        base = Path(plan['folder'])
        folder, n = base, 1
        while True:                                 # atomic create; retry on a race or an existing name
            try:
                folder.mkdir(parents=True, exist_ok=False)
                break
            except FileExistsError:
                n += 1
                folder = base.with_name(f'{base.name}-{n}')
                if n > 10000:
                    raise SafetyError('Could not create a new project folder')
        plan['folder'] = str(folder)
    else:
        plan['folder'] = str(check_existing_folder(plan['folder']))
    plan['status'] = 'approved'
    plan['approved_at'] = time.time()
    plan['sha256'] = _digest(_body(plan))
    _save(Path(path).parent, plan)
    return plan


def reject(path) -> dict:
    plan = load_plan(path)
    _verify(plan)
    if plan['status'] in ('approved',):
        raise SafetyError('An approved plan cannot be rejected; make a new request')
    plan['status'] = 'rejected'
    _save(Path(path).parent, plan)
    return plan


def require_approved(path) -> dict:
    """The gate every later stage must pass through before it touches a project."""
    plan = load_plan(path)
    _verify(plan)
    if plan.get('status') != 'approved':
        raise SafetyError('This plan has not been approved')
    return plan


def plan_text(plan: dict) -> str:
    c = plan['content']
    lines = [c['title'], '', c['summary'], '']
    if c['features']:
        lines += ['What it will do:'] + [f'  - {x}' for x in c['features']] + ['']
    if c['tests']:
        lines += ['How ADM will check it works (these become the tests):'] + [f'  {i}. {x}' for i, x in enumerate(c['tests'], 1)] + ['']
    if c['needs_internet']:
        lines += ['Note: this idea seems to need the internet. ADM runs generated code with NO internet, so '
                  'those parts cannot be tested here.', '']
    if c['questions']:
        lines += ['ADM needs answers before it can plan this. Add them to your request and press Make plan again:'] + \
                 [f'  ? {x}' for x in c['questions']] + ['']
    if plan['status'] == 'approved':
        where = 'Approved. Project folder:' if plan['mode'] == 'new' else 'Approved. Your existing folder:'
    else:
        where = 'A new folder will be created at' if plan['mode'] == 'new' else 'Your existing folder:'
    lines.append(f"{where} {plan['folder']}")
    return '\n'.join(lines)


def test_model(model=None, *, generator=None, timeout=120) -> dict:
    """One quick real inference so the person can confirm the local AI works before a long build.

    Returns {model, seconds, ok, answer}. Raises SafetyError with a plain message if the model is
    missing or unreachable. `generator` injection is for tests only.
    """
    use_model = model or choose_model()
    gen = generator
    if gen is None:
        from .backends import make_json_generator
        gen = make_json_generator(use_model)
    start = time.time()
    answer = gen(use_model, 'Reply with only this JSON and nothing else: {"ok": true}', timeout)
    return {'model': use_model, 'seconds': round(time.time() - start, 2),
            'ok': isinstance(answer, dict), 'answer': answer}


def choose_model(*, installed=None, ram_gib=None) -> str:
    """Pick an installed local model, or explain in plain words what is missing."""
    from .model_selection import select_installed_model
    if installed is None:
        from .ollama_health import inspect_ollama
        try:
            installed = inspect_ollama(timeout=3)['installed_models']
        except SafetyError as exc:
            raise SafetyError("The local AI is not running. Press 'Set up local AI...' first.") from exc
    if not installed:
        raise SafetyError("No local AI model is installed yet. Press 'Set up local AI...' first.")
    if ram_gib is None:
        from .core import resources
        total = resources().get('ram_total_bytes')
        ram_gib = round(total / 1024 ** 3, 1) if total else 16
    try:
        return select_installed_model(installed, ram_gib=max(4, ram_gib))['model']
    except SafetyError as exc:
        raise SafetyError("None of the installed AI models fit this PC's memory. Press 'Set up local AI...' "
                          "to get one that does.") from exc
