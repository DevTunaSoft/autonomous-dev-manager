"""Opt-in Windows logon launcher. No installation occurs without user action.

Task Scheduler starts a dedicated supervisor at user logon. This is NOT
Windows-service, sandbox, or reboot-recovery acceptance evidence.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
import sys

TASK_NAME = 'AutonomousDevelopmentManager'


def startup_command(state: str, *, python_executable: str | None = None) -> list[str]:
    """Return a safe argv vector for the Python daemon (no shell)."""
    target = Path(state).expanduser().resolve()
    interpreter = Path(python_executable or sys.executable).resolve()
    if not interpreter.is_file():
        raise FileNotFoundError(f'Python executable not found: {interpreter}')
    if getattr(sys, 'frozen', False) and python_executable is None:
        return [str(interpreter), '--adm-supervisor', '--state', str(target)]
    return [str(interpreter), '-m', 'adm.daemon', '--state', str(target)]


def windows_task_command(state: str, *, python_executable: str | None = None) -> list[str]:
    """Create a user-logon task; caller must approve and invoke explicitly.

    Uses schtasks.exe with argv, not shell=True. Quoted executable/state paths
    are required because schtasks /TR accepts a single Windows command string.
    """
    argv = startup_command(state, python_executable=python_executable)
    def quote(part):
        if '"' in part:
            raise ValueError('Double quote in Windows command path')
        return '"' + part + '"'
    cmdline = ' '.join(quote(x) for x in argv)
    if len(cmdline) > 261:
        raise ValueError(f'Startup command is {len(cmdline)} characters; schtasks /TR allows at most 261. '
                         'Install ADM in a shorter folder path.')
    return ['schtasks.exe', '/Create', '/F', '/SC', 'ONLOGON', '/TN', TASK_NAME,
            '/TR', cmdline, '/RL', 'LIMITED']


def install(state: str, *, approve: bool = False) -> subprocess.CompletedProcess:
    from .engine import SafetyError
    if os.name != 'nt':
        raise SafetyError('Startup registration is only available on Windows')
    if not approve:
        raise PermissionError('Explicit approval required for startup registration')
    return subprocess.run(windows_task_command(state), check=True, capture_output=True, text=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description='ADM opt-in Windows startup task')
    parser.add_argument('--state', required=True)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args(argv)
    if args.install:
        install(args.state, approve=True)
        print('Windows startup task registered')
    else:
        print('Proposed command (not executed):', windows_task_command(args.state))

if __name__ == '__main__':
    main()
