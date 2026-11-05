"""First-run local-AI setup: find out what is missing, ask, then install with progress.

Logic only (no Tk) so it can be tested. Nothing is installed or downloaded unless the
caller passes approved=True after showing the user ``prompt_text()``.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Callable

from .setup import MODELS, build_plan, execute_step, find_executable

# Approximate download sizes (GB) of Ollama's default 4-bit builds. Informational only.
MODEL_SIZE_GB = {'qwen2.5-coder:1.5b': 1.0, 'qwen2.5-coder:3b': 2.0, 'qwen2.5-coder:7b': 4.7}
OLLAMA_DOWNLOAD_URL = 'https://ollama.com/download'


def models_dir(env: dict | None = None, home: Path | None = None) -> Path:
    """Where Ollama keeps downloaded models (OLLAMA_MODELS overrides the default)."""
    env = os.environ if env is None else env
    if env.get('OLLAMA_MODELS'):
        return Path(env['OLLAMA_MODELS'])
    return (home or Path.home()) / '.ollama' / 'models'


def recommend_model(ram_gib: float) -> str:
    """Same RAM tiers as model_selection: <8 GiB small, <20 GiB 3b, otherwise 7b."""
    if ram_gib < 8:
        return MODELS['constrained']
    if ram_gib < 20:
        return MODELS['balanced']
    return MODELS['performance']


def _free_gb(path: Path) -> float | None:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        return round(shutil.disk_usage(probe).free / 1024 ** 3, 1)
    except OSError:
        return None


def assess(*, ram_gib: float | None = None, find_exe: Callable = find_executable,
           inspect: Callable | None = None, python_finder: Callable | None = None,
           env: dict | None = None, home: Path | None = None, winget: bool | None = None) -> dict:
    """Read-only look at what this PC already has. Never changes anything."""
    from .ollama_health import inspect_ollama
    from .pyruntime import project_python, PythonNotFound
    from .queued_ai import physical_ram_gib
    from .model_selection import select_installed_model
    from .engine import SafetyError
    inspect = inspect or inspect_ollama
    python_finder = python_finder or project_python
    if ram_gib is None:
        try:
            ram_gib = physical_ram_gib()
        except SafetyError:
            ram_gib = 8.0                      # unknown: assume modest, recommend a small model
    try:
        ollama_exe = find_exe('ollama')
    except Exception:
        ollama_exe = None                      # a broken discovery helper must not abort the assessment
    reachable, installed = False, []
    try:
        info = inspect(timeout=3)
        reachable, installed = True, list(info['installed_models'])
    except Exception:
        pass
    try:
        python = {'found': True, 'path': python_finder()}
    except PythonNotFound as exc:
        python = {'found': False, 'path': None, 'message': str(exc)}
    except Exception as exc:                        # a broken finder must not abort the assessment
        python = {'found': False, 'path': None, 'message': f'Python check failed: {type(exc).__name__}'}
    usable = None
    if installed:
        try:
            usable = select_installed_model(installed, ram_gib=ram_gib)['model']
        except SafetyError:
            usable = None
    target = recommend_model(ram_gib)
    store = models_dir(env, home)
    needs = []
    if not ollama_exe and not reachable:
        needs.append('ollama')
    elif not reachable:
        needs.append('start_ollama')
    if usable is None:
        needs.append('model')
    if not python['found']:
        needs.append('python')
    return {'ram_gib': round(ram_gib, 1), 'python': python,
            'ollama': {'installed': bool(ollama_exe or reachable), 'exe': ollama_exe, 'reachable': reachable},
            'installed_models': installed, 'usable_model': usable,
            'recommended_model': target, 'recommended_size_gb': MODEL_SIZE_GB.get(target),
            'models_dir': str(store), 'models_dir_free_gb': _free_gb(store),
            'winget': (shutil.which('winget') is not None) if winget is None else winget,
            'needs': needs, 'ready': not needs}


def prompt_text(a: dict) -> tuple[str, str]:
    """(title, message) shown to the user BEFORE anything is downloaded."""
    if a['ready']:
        return 'Local AI ready', f"Everything ADM needs is installed. Using {a['usable_model']}."
    lines = ['ADM runs its AI on your own PC, so a few one-time downloads are needed:', '']
    if 'ollama' in a['needs']:
        how = ('ADM can install it for you with Windows Package Manager.' if a['winget']
               else f"Download and run the installer from {OLLAMA_DOWNLOAD_URL} first.")
        lines += ['1. Ollama (the program that runs AI models on your PC, free).', f'   {how}']
    if 'start_ollama' in a['needs']:
        lines += ['1. Ollama is installed but not running. ADM will start it.']
    if 'model' in a['needs']:
        size = a['recommended_size_gb']
        lines += [f"2. AI model: {a['recommended_model']}" + (f" (about {size} GB download)." if size else '.'),
                  f"   Chosen for your PC's {a['ram_gib']} GB of memory.",
                  f"   It will be saved in: {a['models_dir']}"]
        if a['models_dir_free_gb'] is not None:
            lines.append(f"   Free space on that drive: {a['models_dir_free_gb']} GB.")
    if 'python' in a['needs']:
        lines += ['3. Python 3.10 or newer is also needed to test the software ADM builds.',
                  '   Install it from python.org and tick "Add python.exe to PATH". ADM cannot install this yet.']
    lines += ['', 'An internet connection is needed only for these downloads.']
    can_act = bool({'ollama', 'start_ollama', 'model'} & set(a['needs']))
    if can_act:
        lines += ['', 'Download and set up now?']
    return 'Set up local AI', '\n'.join(lines)


def pull_with_progress(exe: str, model: str, on_line: Callable[[str], None], *, timeout: float = 7200) -> dict:
    """`ollama pull` with live progress. Only allow-listed models."""
    if model not in MODELS.values():
        raise ValueError('Unapproved model download')
    started = time.monotonic()
    proc = subprocess.Popen([exe, 'pull', model], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))
    tail = []
    buf = b''
    try:
        while True:
            chunk = proc.stdout.read(256)
            if not chunk:
                break
            buf += chunk
            parts = buf.replace(b'\r', b'\n').split(b'\n')
            buf = parts.pop()
            for raw in parts:
                text = raw.decode('utf-8', 'replace').strip()
                if text:
                    tail = (tail + [text])[-20:]
                    try:
                        on_line(text)
                    except Exception:
                        pass                        # a progress-callback error must not abort the download
            if time.monotonic() - started > timeout:
                proc.kill()
                return {'key': 'pull_model', 'status': 'failed', 'reason': 'Download timed out'}
        code = proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.stdout.close()
    return {'key': 'pull_model', 'status': 'completed' if code == 0 else 'failed', 'exit_code': code,
            'output_tail': '\n'.join(tail)}


def _start_ollama(exe: str, wait: float = 25.0, inspect: Callable | None = None) -> bool:
    from .ollama_health import inspect_ollama
    inspect = inspect or inspect_ollama
    def up():
        try:
            inspect(timeout=2); return True
        except Exception:
            return False
    if up():
        return True
    flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW) if os.name == 'nt' else 0
    subprocess.Popen([exe, 'serve'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=flags, **({} if os.name == 'nt' else {'start_new_session': True}))
    end = time.monotonic() + wait
    while time.monotonic() < end:
        if up():
            return True
        time.sleep(1)
    return False


def run_setup(a: dict, *, approved: bool, on_status: Callable[[str], None],
              executor: Callable = execute_step, puller: Callable = pull_with_progress,
              starter: Callable = _start_ollama, finder: Callable = find_executable) -> dict:
    """Do what ``assess`` found missing. Requires approved=True (the user said yes)."""
    if not approved:
        raise PermissionError('The user has not approved setup')
    results = []
    exe = a['ollama'].get('exe')
    if 'ollama' in a['needs']:
        if not a['winget']:
            return {'status': 'manual', 'results': results,
                    'message': f'Install Ollama from {OLLAMA_DOWNLOAD_URL}, then reopen ADM.'}
        on_status('Installing Ollama (this can take a few minutes)...')
        plan = build_plan(system='Windows', binaries={'winget': 'winget', 'ollama': None, 'opencode': None},
                          hardware={'ram_available_bytes': 16 * 1024 ** 3, 'disk_free_bytes': 100 * 1024 ** 3, 'cpu_count': 4},
                          model=a['recommended_model'])
        step = next(s for s in plan['steps'] if s['key'] == 'install_ollama')
        res = executor(step, approved=True, system='Windows')
        results.append(res)
        if res.get('status') != 'completed':
            return {'status': 'failed', 'results': results, 'message': 'Ollama installation did not finish: ' + str(res.get('reason') or res.get('output_tail', ''))[-300:]}
        exe = finder('ollama')
        if not exe:
            return {'status': 'manual', 'results': results, 'message': 'Ollama installed. Please reopen ADM so it can find it.'}
    if exe is None:
        exe = finder('ollama')
    if exe is None:
        return {'status': 'failed', 'results': results, 'message': 'Ollama was not found.'}
    on_status('Starting Ollama...')
    if not starter(exe):
        return {'status': 'failed', 'results': results, 'message': 'Ollama did not start. Open it from the Start menu and try again.'}
    if 'model' in a['needs']:
        model = a['recommended_model']
        size = a['recommended_size_gb']
        on_status(f'Downloading {model}' + (f' (about {size} GB)' if size else '') + '...')
        res = puller(exe, model, lambda line: on_status(f'{model}: {line}'))
        results.append(res)
        if res.get('status') != 'completed':
            return {'status': 'failed', 'results': results, 'message': 'Model download did not finish: ' + str(res.get('output_tail') or res.get('reason', ''))[-300:]}
    return {'status': 'completed', 'results': results, 'message': 'Local AI is ready.'}
