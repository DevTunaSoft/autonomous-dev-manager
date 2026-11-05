"""ADM-008: resumable, dependency-aware local provisioning coordinator.

This is not an unattended installer. Every install/download requires explicit approval.
The journal is durable but is not a security boundary or proof of a working model.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Callable

from .setup import build_plan, execute_step


def _write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.adm-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def execute_plan(plan: dict, journal_path: str | Path, *, approved: bool = False,
                 executor: Callable = execute_step, verify: Callable | None = None) -> dict:
    """Run a validated setup plan with journaled progress and dependency gates.

    `verify(key)` checks an already completed step before skipping it on resume.
    Failed verification makes the step run again, never silently accepted.
    """
    if not approved:
        raise PermissionError('Explicit installation/download approval is required')
    if not isinstance(plan, dict):
        raise ValueError('Invalid plan')
    if plan.get('platform') != 'Windows':
        raise ValueError('This installer only supports Windows')
    steps = plan.get('steps')
    if not isinstance(steps, list) or any(not isinstance(s, dict) for s in steps):
        raise ValueError('Invalid plan')
    keys = [s.get('key') for s in steps]
    if len(keys) != len(set(keys)) or any(k not in {'install_ollama', 'pull_model'} for k in keys):
        raise ValueError('Invalid or repeated provisioning steps')
    path = Path(journal_path)
    # A journal is bound to the precise commands, preventing stale resume after a changed plan.
    fingerprint = json.dumps(steps, sort_keys=True)
    if path.exists():
        try:
            state = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError, RecursionError) as exc:
            raise ValueError('Existing setup journal is unreadable') from exc
        if not isinstance(state, dict) or not isinstance(state.get('results'), dict):
            raise ValueError('Existing setup journal is malformed')
        if state.get('fingerprint') != fingerprint:
            raise ValueError('Existing setup journal belongs to a different plan')
    else:
        state = {'fingerprint': fingerprint, 'results': {}, 'status': 'pending'}
        _write_atomic(path, state)
    results = state['results']
    for step in steps:
        key = step['key']
        if key == 'pull_model' and 'install_ollama' in keys and results.get('install_ollama', {}).get('status') != 'completed':
            state['status'] = 'blocked'
            _write_atomic(path, state)
            break
        previous = results.get(key, {})
        if previous.get('status') == 'completed' and verify is not None and verify(key):
            continue
        # With no verifier, rerun the step; journal success alone cannot prove installation.
        result = executor(step, approved=True, system='Windows')
        results[key] = result
        state['status'] = 'running'
        _write_atomic(path, state)
        if result.get('status') != 'completed':
            state['status'] = 'blocked'
            _write_atomic(path, state)
            break
    else:
        state['status'] = 'steps_completed' if not plan.get('blockers') else 'blocked'
        _write_atomic(path, state)
    return state
