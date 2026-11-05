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


def get_logger(state, component: str = 'app'):
    import logging
    import logging.handlers
    log_dir(state).mkdir(parents=True, exist_ok=True)   # raises on a bad path BEFORE we touch handlers
    target = str(log_path(state))
    logger = logging.getLogger('adm')
    if getattr(logger, '_adm_path', None) != target:    # (re)bind if the state path changed
        for old in list(logger.handlers):
            logger.removeHandler(old)
            try:
                old.close()
            except Exception:
                pass
        handler = logging.handlers.RotatingFileHandler(
            target, maxBytes=512 * 1024, backupCount=2, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger._adm_path = target                        # type: ignore[attr-defined]
    return logger


def log_line(state, message: str, *, level: str = 'info', component: str = 'app') -> None:
    try:
        logger = get_logger(state, component)
        getattr(logger, level, logger.info)(f'[{component}] {message}')
    except Exception:
        pass                                   # logging must never crash the app


def install_excepthook(state, component: str = 'app') -> None:
    """Log any uncaught exception before the default handler runs."""
    logger = get_logger(state, component)
    previous = sys.excepthook

    def hook(exc_type, exc, tb):
        try:
            logger.error('UNCAUGHT in %s', component, exc_info=(exc_type, exc, tb))
        finally:
            previous(exc_type, exc, tb)
    sys.excepthook = hook


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as exc:
        return f'unavailable: {type(exc).__name__}: {exc}'


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
            except (OSError, ValueError):
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
            except (OSError, ValueError):
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
