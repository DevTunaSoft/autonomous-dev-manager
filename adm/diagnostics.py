"""Diagnostics: a persistent app log and a one-click export bundle the person can send for debugging.

The log captures unhandled errors (so a crash or a frozen callback leaves a trace), and the bundle
gathers version/OS, local-AI and runtime status, recent build reports and their test output, and the
log tail — into one zip. It never includes the person's generated source code, only test output and
status, so it is safe to share.
"""
from __future__ import annotations
import json
import os
import platform
import sys
import time
from pathlib import Path

VERSION = '0.5.2-dev'


def log_dir(state) -> Path:
    return Path(state) / 'logs'


def log_path(state) -> Path:
    return log_dir(state) / 'adm.log'


MAX_LOG_BYTES = 512 * 1024


def _rotate_if_big(path: Path) -> None:
    try:
        if path.is_file() and path.stat().st_size > MAX_LOG_BYTES:
            backup = path.with_name(path.name + '.1')
            if backup.exists():
                backup.unlink()
            path.rename(backup)
    except OSError:
        pass


def log_line(state, message: str, *, level: str = 'info', component: str = 'app') -> None:
    """Append one line to adm.log. Opens and closes the file each time so nothing holds a handle
    (a persistent handle would lock the file on Windows). Never raises."""
    try:
        log_dir(state).mkdir(parents=True, exist_ok=True)
        path = log_path(state)
        _rotate_if_big(path)
        stamp = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(path, 'a', encoding='utf-8') as stream:
            stream.write(f'{stamp} {level.upper()} [{component}] {message}\n')
    except Exception:
        pass                                   # logging must never crash the app


def install_excepthook(state, component: str = 'app') -> None:
    """Log any uncaught exception before the default handler runs."""
    import traceback
    previous = sys.excepthook

    def hook(exc_type, exc, tb):
        try:
            text = ''.join(traceback.format_exception(exc_type, exc, tb))
            log_line(state, 'UNCAUGHT:\n' + text, level='error', component=component)
        finally:
            previous(exc_type, exc, tb)
    sys.excepthook = hook


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as exc:
        return f'unavailable: {type(exc).__name__}: {exc}'


def self_check(state) -> list:
    """Run ADM's own health checks and return a list of {name, ok, detail}. Never raises."""
    checks = []

    def add(name, ok, detail):
        checks.append({'name': name, 'ok': bool(ok), 'detail': str(detail)[:300]})

    try:
        from .pyruntime import project_python
        add('Python for your projects', True, project_python())
    except Exception as exc:
        add('Python for your projects', False, f'{type(exc).__name__}: {exc}')
    try:
        from .ollama_health import inspect_ollama
        models = inspect_ollama(timeout=3).get('installed_models', [])
        add('Local AI (Ollama)', bool(models),
            'Models: ' + (', '.join(models[:5]) if models else 'reachable, but no model installed'))
    except Exception as exc:
        add('Local AI (Ollama)', False, f'Not reachable ({type(exc).__name__}). Use "Set up…".')
    try:
        from .runtime_install import shared_python_dir
        p = shared_python_dir() / 'python.exe'
        add('Bundled Python runtime', p.is_file(),
            str(p) if p.is_file() else 'Not installed yet (installs on first build)')
    except Exception as exc:
        add('Bundled Python runtime', False, str(exc))
    try:
        from . import sandbox
        if not sandbox.available():
            add('Sandbox for generated code', False, 'Only available on Windows')
        else:
            admin = sandbox.is_admin()
            add('Sandbox for generated code', admin,
                'Administrator: yes' if admin else 'Needs administrator once (run ADM as administrator to build)')
    except Exception as exc:
        add('Sandbox for generated code', False, str(exc))
    try:
        import shutil
        free = shutil.disk_usage(Path(state)).free / 1024 ** 3
        add('Disk space', free > 2, f'{free:.1f} GB free')
    except Exception as exc:
        add('Disk space', False, str(exc))
    try:
        Path(state).mkdir(parents=True, exist_ok=True)
        probe = Path(state) / '.adm-write-test'
        probe.write_text('x', encoding='utf-8')
        probe.unlink()
        add('Write access to ADM folder', True, str(state))
    except Exception as exc:
        add('Write access to ADM folder', False, str(exc))
    try:
        import tkinter  # noqa: F401
        add('Window toolkit', True, 'Available')
    except Exception as exc:
        add('Window toolkit', False, str(exc))
    return checks


def collect(state) -> dict:
    state = Path(state)
    info = {
        'adm_version': VERSION,
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'platform': _safe(platform.platform),
        'python': sys.version.split()[0],
        'frozen': bool(getattr(sys, 'frozen', False)),
    }
    info['resources'] = _safe(lambda: __import__('adm.core', fromlist=['resources']).resources())
    info['local_ai'] = _safe(lambda: _ai_status())
    info['bundled_python_installed'] = _safe(lambda: _bundled_python_present())
    info['plans_by_status'] = _safe(lambda: _plan_counts(state), {})
    info['recent_builds'] = _safe(lambda: _recent_builds(state), [])
    info['worker'] = _safe(lambda: __import__('adm.desktop', fromlist=['status_summary']).status_summary(state))
    info['self_check'] = _safe(lambda: self_check(state), [])
    info['log_tail'] = _safe(lambda: _log_tail(state), '')
    return info


def _ai_status():
    from .ollama_health import inspect_ollama
    r = inspect_ollama(timeout=3)
    return {'reachable': True, 'installed_models': r.get('installed_models', [])}


def _bundled_python_present():
    from .runtime_install import shared_python_dir
    return (shared_python_dir() / 'python.exe').is_file()


def _plan_counts(state):
    counts = {}
    plans = Path(state) / 'plans'
    if plans.is_dir():
        for pj in plans.glob('*/plan.json'):
            try:
                status = json.loads(pj.read_text(encoding='utf-8')).get('status', '?')
            except (OSError, ValueError, RecursionError):
                status = 'unreadable'
            counts[status] = counts.get(status, 0) + 1
    return counts


def _recent_builds(state):
    out = []
    builds = Path(state) / 'builds'
    if builds.is_dir():
        for b in sorted(builds.glob('*.json'), reverse=True)[:10]:
            try:
                data = json.loads(b.read_text(encoding='utf-8'))
            except (OSError, ValueError, RecursionError):
                continue
            out.append({k: data.get(k) for k in ('plan_id', 'status', 'mode', 'isolation', 'message', 'model')})
    return out


def _log_tail(state, lines: int = 400):
    p = log_path(state)
    if not p.is_file():
        return ''
    text = p.read_text(encoding='utf-8', errors='replace').splitlines()
    return '\n'.join(text[-lines:])


def export_bundle(state, dest_path) -> Path:
    """Write a single zip with diagnostics.json, the log, build reports and their test output."""
    import zipfile
    state = Path(state)
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('diagnostics.json', json.dumps(collect(state), indent=2, ensure_ascii=False, default=str))
        if log_path(state).is_file():
            z.write(log_path(state), 'adm.log')
        builds = state / 'builds'
        if builds.is_dir():
            for b in sorted(builds.glob('*.json'))[-10:]:
                z.write(b, f'builds/{b.name}')
        # test output only (never the generated source files)
        evidence = state / 'evidence'
        if evidence.is_dir():
            for log in sorted(evidence.glob('*/*.log'))[-30:]:
                z.write(log, f'evidence/{log.parent.name}/{log.name}')
            for rep in sorted(evidence.glob('*/ollama-direct-report.json'))[-10:]:
                z.write(rep, f'evidence/{rep.parent.name}/{rep.name}')
    return dest
