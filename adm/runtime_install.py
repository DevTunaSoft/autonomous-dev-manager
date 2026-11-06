"""Install a bundled Python runtime so people don't have to install Python themselves.

The low-privilege sandbox account cannot read the main user's profile, so the runtime is
placed in a world-readable shared folder (%ProgramData%\\ADM\\python) that the sandbox account
can read and execute. Writing there needs administrator once -- the same elevation the sandbox
already requires. In source checkouts nothing is bundled and the current Python is used.
"""
from __future__ import annotations
import os
import shutil
import sys
from pathlib import Path
from .engine import SafetyError


def shared_python_dir(programdata=None) -> Path:
    base = programdata or os.environ.get('ProgramData') or r'C:\ProgramData'
    return Path(base) / 'ADM' / 'python'


def fixup_pth(py_dir) -> Path | None:
    """Make an embeddable Python import from the current directory and enable site.

    Embeddable distributions ship a ``pythonXY._pth`` that omits '.' and comments out site,
    so a project's test_app.py / app.py in the working directory would not import. Fix both.
    """
    py_dir = Path(py_dir)
    for pth in sorted(py_dir.glob('python*._pth')):
        out, have_dot, have_site = [], False, False
        # A corrupt embeddable distribution could ship a non-UTF8 ._pth; decode
        # tolerantly rather than crash the runtime install (we rewrite it anyway).
        for line in pth.read_text(encoding='utf-8', errors='replace').splitlines():
            s = line.strip()
            if s == '.':
                have_dot = True
            if s == 'import site':
                have_site = True
            if s in ('#import site', '# import site'):
                out.append('import site')
                have_site = True
                continue
            out.append(line)
        if not have_dot:
            out.append('.')
        if not have_site:
            out.append('import site')
        pth.write_text('\n'.join(out) + '\n', encoding='utf-8')
        return pth
    return None


def _grant_read_exec(path, user) -> None:
    """Give the low-privilege sandbox account read+execute on the shared runtime. Best effort."""
    import subprocess
    try:
        subprocess.run(['icacls', str(path), '/grant', f'{user}:(OI)(CI)RX', '/T', '/C', '/Q'],
                       capture_output=True, timeout=180)
    except (OSError, subprocess.SubprocessError):
        pass


def ensure_shared_python(source_dir, *, programdata=None, grant_user=None) -> Path:
    """Copy an embeddable Python into the shared folder if it is not there yet; return python.exe.

    On install, grant the sandbox account read+execute so it can run the interpreter (the shared
    folder's inherited permissions are not enough for a cross-account launch).
    """
    source_dir = Path(source_dir)
    if not (source_dir / 'python.exe').is_file():
        raise SafetyError('No bundled Python runtime was found to install')
    dest = shared_python_dir(programdata)
    dest_exe = dest / 'python.exe'
    if dest_exe.is_file():
        return dest_exe
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + '.tmp')
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(source_dir, tmp)
    fixup_pth(tmp)
    os.replace(tmp, dest)       # move the finished runtime into place in one step
    if grant_user is None:
        try:
            from .sandbox import USER
            grant_user = USER
        except Exception:
            grant_user = None
    if grant_user and os.name == 'nt':
        _grant_read_exec(dest, grant_user)
    return dest_exe


def bundled_source() -> Path | None:
    """The embeddable runtime inside the frozen app, if it was bundled."""
    base = getattr(sys, '_MEIPASS', None)
    if not base:
        return None
    src = Path(base) / 'pyembed'
    return src if (src / 'python.exe').is_file() else None


def ensure_runtime():
    """Install the bundled runtime to the shared folder when frozen. Returns python.exe or None."""
    src = bundled_source()
    if src is None:
        return None
    return ensure_shared_python(src)
