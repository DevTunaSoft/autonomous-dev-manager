"""ADM-007: auditable, explicit-consent local dependency provisioning.

No installation, download, or process execution happens on import or in plan().
The installer is deliberately limited to an approved Windows Ollama winget package,
and an Ollama model pull after a local Ollama executable is available.
OpenCode provisioning remains blocked until a verified installation route is added.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .core import resources, mode

OLLAMA_PACKAGE = 'Ollama.Ollama'
MODELS = {'constrained': 'qwen2.5-coder:1.5b', 'balanced': 'qwen2.5-coder:3b',
          'performance': 'qwen2.5-coder:7b'}


@dataclass(frozen=True)
class Step:
    key: str
    argv: tuple[str, ...]
    description: str
    requires_approval: bool = True


def choose_model(info: dict) -> str:
    """Conservative candidate only; selection is not a capability benchmark."""
    return MODELS[mode(info)]


def build_plan(*, system: str | None = None, binaries: dict | None = None,
               hardware: dict | None = None, model: str | None = None) -> dict:
    system = system or platform.system()
    binaries = binaries if binaries is not None else {x: shutil.which(x) for x in ('winget', 'ollama', 'opencode')}
    hardware = hardware if hardware is not None else resources()
    selected = model or choose_model(hardware)
    if selected not in MODELS.values():
        raise ValueError('Model must be an explicitly allowlisted local model')
    steps: list[Step] = []
    blockers: list[str] = []
    if system != 'Windows':
        blockers.append('Automatic tool installation is supported only on Windows in this milestone')
    elif not binaries.get('ollama'):
        if binaries.get('winget'):
            steps.append(Step('install_ollama', ('winget', 'install', '--exact', '--id', OLLAMA_PACKAGE,
                                                '--source', 'winget', '--accept-package-agreements',
                                                '--accept-source-agreements'),
                              'Install the official Ollama package through Windows Package Manager'))
        else:
            blockers.append('winget is unavailable; cannot safely install Ollama automatically')
    if system == 'Windows' and (binaries.get('ollama') or binaries.get('winget')):
        steps.append(Step('pull_model', ('ollama', 'pull', selected),
                          'Download a local model; may use several GB of disk space'))
    if not binaries.get('opencode'):
        blockers.append('OpenCode automatic installation is not yet implemented or verified')
    return {'platform': system, 'resource_mode': mode(hardware), 'model_candidate': selected,
            'model_benchmarked': False, 'steps': [asdict(s) for s in steps],
            'blockers': blockers, 'automatic_setup_complete': False}


def execute_step(step: dict, *, approved: bool = False,
                 runner: Callable | None = None, system: str | None = None) -> dict:
    """Execute only exact allowlisted commands with explicit approval.

    A test runner can be injected; it does not loosen command validation.
    """
    if not approved:
        raise PermissionError('Installation or model download requires explicit approval')
    if (system or platform.system()) != 'Windows':
        raise RuntimeError('Provisioning execution is Windows-only')
    key, argv = step.get('key'), step.get('argv')
    if not isinstance(argv, (list, tuple)) or not all(isinstance(v, str) for v in argv):
        raise ValueError('Invalid setup command')
    argv = tuple(argv)
    if key == 'install_ollama':
        expected = ('winget', 'install', '--exact', '--id', OLLAMA_PACKAGE, '--source', 'winget',
                    '--accept-package-agreements', '--accept-source-agreements')
        if argv != expected:
            raise ValueError('Installer command differs from approved package')
    elif key == 'pull_model':
        if len(argv) != 3 or argv[:2] != ('ollama', 'pull') or argv[2] not in MODELS.values():
            raise ValueError('Unapproved model download')
    else:
        raise ValueError('Unknown setup action')
    if runner is None:
        runner = subprocess.run
    executable = shutil.which(argv[0])
    if executable is None:
        return {'key': key, 'status': 'blocked', 'reason': f'{argv[0]} is not available in PATH'}
    try:
        result = runner([executable, *argv[1:]], capture_output=True, text=True,
                        timeout=1800, check=False)
        return {'key': key, 'status': 'completed' if result.returncode == 0 else 'failed',
                'exit_code': result.returncode,
                'output_tail': ((result.stdout or '') + '\n' + (result.stderr or ''))[-3000:]}
    except subprocess.TimeoutExpired:
        return {'key': key, 'status': 'failed', 'reason': 'Setup timed out'}
    except OSError as exc:
        return {'key': key, 'status': 'failed', 'reason': type(exc).__name__}


def save_plan(plan: dict, destination: str | Path) -> None:
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(plan, indent=2), encoding='utf-8')
