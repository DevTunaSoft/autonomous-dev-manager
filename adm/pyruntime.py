"""Which interpreter runs what, in source and in the packaged (frozen) app.

* ADM's own jobs (repair CLI, agent CLI) are re-invoked through ADM itself when
  frozen: ``ADM-Desktop.exe --adm-module adm.ollama_cli ...``. A frozen
  ``sys.executable`` is the GUI EXE, so passing it ``-m``/``-c`` fails.
* The user's generated project needs a real Python with the full standard
  library to run its unit tests. When frozen we discover one; we never run the
  bundled runtime for project code.

Discovery never installs anything and never executes the Microsoft Store stub.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys

MIN_PYTHON = (3, 10)
# Modules the frozen entrypoint may dispatch to (allowlist; no arbitrary imports).
ENTRY_MODULES = ('adm.ollama_cli', 'adm.agent_cli')


class PythonNotFound(Exception):
    """No suitable Python interpreter for running the user's project."""


def is_frozen() -> bool:
    return bool(getattr(sys, 'frozen', False))


def self_command(module: str, args: list[str], *, frozen: bool | None = None,
                 executable: str | None = None, package_root: str | None = None) -> list[str]:
    """argv that runs an ADM module the same way in source and frozen builds."""
    if module not in ENTRY_MODULES:
        raise ValueError('Module is not an approved ADM entry point')
    frozen = is_frozen() if frozen is None else frozen
    exe = str(executable or sys.executable)
    if frozen:
        return [exe, '--adm-module', module, *args]
    root = package_root or str(Path(__file__).resolve().parent.parent)
    launcher = (f'import sys; sys.path.insert(0, {root!r}); '
                f'from {module} import main; main()')
    return [exe, '-B', '-c', launcher, *args]


def _candidates() -> list[str]:
    found: list[str] = []
    if os.name == 'nt':
        shared = os.environ.get('ProgramData')
        if shared:
            # Shared ADM runtime, readable by the sandbox account (see runtime_install).
            found.append(str(Path(shared) / 'ADM' / 'python' / 'python.exe'))
        local = os.environ.get('LOCALAPPDATA')
        if local:
            found.append(str(Path(local) / 'ADM' / 'python' / 'python.exe'))   # ADM-managed runtime
            for minor in (13, 12, 11, 10):                                     # per-user python.org installs
                found.append(str(Path(local) / 'Programs' / 'Python' / f'Python3{minor}' / 'python.exe'))
        for base in (os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)')):
            if base:
                for minor in (13, 12, 11, 10):
                    found.append(str(Path(base) / f'Python3{minor}' / 'python.exe'))
    for name in ('python3', 'python'):
        which = shutil.which(name)
        if which:
            found.append(which)
    return found


def _usable(path: str) -> bool:
    p = Path(path)
    if not p.is_file() or 'windowsapps' in str(p).lower():   # Store stub / app-execution aliases
        return False
    try:
        out = subprocess.run([str(p), '-c', 'import sys,unittest;print(sys.version_info[0],sys.version_info[1])'],
                             capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
        major, minor = (int(x) for x in out.stdout.split()[:2])
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    return out.returncode == 0 and (major, minor) >= MIN_PYTHON


def project_python(*, frozen: bool | None = None, candidates: list[str] | None = None) -> str:
    """Interpreter for the user's project. Source runs use the current Python."""
    frozen = is_frozen() if frozen is None else frozen
    if not frozen:
        return sys.executable
    for path in (candidates if candidates is not None else _candidates()):
        if _usable(path):
            return str(Path(path))
    raise PythonNotFound('Python 3.10 or newer was not found. ADM needs it to run your '
                         'project\'s tests. Install Python from python.org (tick "Add python.exe to '
                         'PATH"), then try again.')
