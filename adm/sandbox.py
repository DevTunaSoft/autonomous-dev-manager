"""Windows sandbox for generated code (fallback tier: dedicated low-privilege account).

What it enforces (verified on a real Windows runner by tools/sandbox_live_check.py):
  * code runs as a separate local account, so it cannot read or write the owner's files;
  * the account has a per-user outbound firewall block, so no internet;
  * the account may write only to the one project copy it is given;
  * a Job Object caps memory and kills the whole process tree on timeout.
It does NOT work without administrator rights (account and firewall creation).
Never reports success from a run it could not confine: setup errors raise SandboxError.
"""
from __future__ import annotations
import os, secrets, subprocess, sys, tempfile, time
from pathlib import Path

USER = 'admsandbox'
RULE = 'ADM-sandbox-block-outbound'


from .engine import SafetyError


class SandboxError(SafetyError):
    pass


def available() -> bool:
    return os.name == 'nt'


def is_admin() -> bool:
    """True if this process can create local accounts and firewall rules."""
    if os.name != 'nt':
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


NEED_ADMIN = ("Building needs administrator access once, to create the locked-down sandbox account "
              "that runs generated code safely. Close ADM, right-click it and choose "
              "'Run as administrator', then try again.")


def new_password() -> str:
    """Windows accepts <=14 chars without a legacy-compat prompt; 12 random chars cover complexity."""
    alphabet = 'abcdefghijkmnpqrstuvwxyz'
    return 'Aa1!' + ''.join(secrets.choice(alphabet) for _ in range(8))


def setup_commands(password: str, user: str = USER) -> list[list[str]]:
    """Commands (need administrator) that create/reset the account. Pure; testable anywhere."""
    return [['net', 'user', user, password, '/add', '/expires:never'],
            ['net', 'user', user, password]]


def acl_grant_command(folder: str, user: str = USER) -> list[str]:
    return ['icacls', folder, '/grant', f'{user}:(OI)(CI)M']


_CMDLINE_BAD = '"%\x00\r\n&|<>^'


def cmdline_for(argv: list[str], stdout_path: str) -> str:
    """Single command line that redirects output to a file the sandbox account can write.

    Our argv is always a fixed interpreter plus flags, so we can afford to be strict: reject empty
    args, shell metacharacters and a trailing backslash (which would escape the closing quote).
    """
    if not argv or any(not isinstance(a, str) or a == '' or a.endswith('\\')
                       or any(c in a for c in _CMDLINE_BAD) for a in argv):
        raise SandboxError('Command arguments must be non-empty, single-line, and free of shell metacharacters')
    quoted = ' '.join(f'"{a}"' for a in argv)
    return f'cmd.exe /c "{quoted} > "{stdout_path}" 2>&1"'


def _run(cmd, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if check and r.returncode != 0:
        raise SandboxError(f'{cmd[0]} failed: {(r.stdout + r.stderr).strip()[:300]}')
    return r


# Shared locations an ordinary Windows account can usually write to. The account is explicitly
# denied write access to each. This is a deny-list, so it REDUCES exposure; it cannot enumerate
# every folder on every PC (Windows has no "deny everything except" rule). See docs in the handoff.
HARDEN_DIRS = (r'C:\Users\Public', r'C:\ProgramData', r'C:\Windows\Temp', r'C:\Windows\Tasks',
               r'C:\Windows\tracing', r'C:\Windows\System32\spool\drivers\color')


def harden_commands(user: str = USER, dirs=HARDEN_DIRS) -> list[list[str]]:
    cmds = [['icacls', d, '/deny', f'{user}:(OI)(CI)(W,DC)'] for d in dirs]
    return cmds


def refuse_hardened_location(project: str | Path, dirs=HARDEN_DIRS) -> None:
    import ntpath
    p = ntpath.normcase(ntpath.normpath(str(project))).rstrip('\\')
    for d in dirs:
        if p == d.lower() or p.startswith(d.lower() + '\\'):
            raise SandboxError(f'Projects cannot live under {d}; the sandbox account is denied writes there')
    if len(p) <= 3:
        raise SandboxError('A project cannot be a drive root')


def provision(user: str = USER) -> str:
    """Create the account and its outbound firewall block; return a fresh password."""
    if not available():
        raise SandboxError('The Windows account sandbox only runs on Windows')
    if not is_admin():
        raise SandboxError(NEED_ADMIN)
    password = new_password()
    create, reset = setup_commands(password, user)
    if _run(create, check=False).returncode != 0:
        _run(reset)  # account already exists: rotate its password
    sid = subprocess.run(['powershell', '-NoProfile', '-Command',
        f"(New-Object System.Security.Principal.NTAccount('{user}')).Translate("
        f"[System.Security.Principal.SecurityIdentifier]).Value"],
        capture_output=True, text=True, timeout=60).stdout.strip()
    if not sid.startswith('S-1-5-'):
        raise SandboxError('Could not resolve the sandbox account SID (are you an administrator?)')
    for cmd in harden_commands(user):
        _run(cmd, check=False)      # a directory missing on this PC is fine; denial applies where it exists
    ps = (f"Get-NetFirewallRule -DisplayName '{RULE}' -ErrorAction SilentlyContinue | Remove-NetFirewallRule; "
          f"New-NetFirewallRule -DisplayName '{RULE}' -Direction Outbound -Action Block "
          f"-LocalUser 'D:(A;;CC;;;{sid})' | Out-Null; 'RULE_OK'")
    out = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True, timeout=120)
    if 'RULE_OK' not in out.stdout:
        raise SandboxError('Firewall rule was not created: ' + (out.stdout + out.stderr).strip()[:300])
    return password


def run_confined(argv: list[str], project: str | Path, password: str, *, timeout: int = 120,
                 memory_mb: int = 1024, user: str = USER) -> dict:
    """Run argv as the sandbox account with write access to `project` only. Returns exit code and output."""
    if not available():
        raise SandboxError('The Windows account sandbox only runs on Windows')
    import ctypes, ctypes.wintypes as w
    import win32job
    project = Path(project).resolve()
    refuse_hardened_location(project)
    if not project.is_dir():
        raise SandboxError('Project folder does not exist')
    _run(acl_grant_command(str(project), user))
    out_dir = Path(tempfile.mkdtemp(prefix='admsb-out-'))
    _run(['icacls', str(out_dir), '/grant', f'{user}:(OI)(CI)M'])
    stdout_path = out_dir / 'out.txt'
    adv = ctypes.WinDLL('advapi32', use_last_error=True)
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)

    class SI(ctypes.Structure):
        _fields_ = [("cb", w.DWORD), ("r", w.LPWSTR), ("d", w.LPWSTR), ("t", w.LPWSTR)] + \
                   [(n, w.DWORD) for n in ("x", "y", "xs", "ys", "xc", "yc", "fa", "fl")] + \
                   [("sw", w.WORD), ("cb2", w.WORD), ("r2", ctypes.c_void_p),
                    ("i", w.HANDLE), ("o", w.HANDLE), ("e", w.HANDLE)]

    class PI(ctypes.Structure):
        _fields_ = [("hp", w.HANDLE), ("ht", w.HANDLE), ("pid", w.DWORD), ("tid", w.DWORD)]

    adv.CreateProcessWithLogonW.argtypes = [w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, w.DWORD, w.LPCWSTR, w.LPWSTR,
                                            w.DWORD, ctypes.c_void_p, w.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p]
    k32.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    k32.ResumeThread.argtypes = [w.HANDLE]
    k32.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    si = SI(); si.cb = ctypes.sizeof(si); pi = PI()
    cmd = ctypes.create_unicode_buffer(cmdline_for(argv, str(stdout_path)))
    CREATE_SUSPENDED, CREATE_NO_WINDOW = 0x4, 0x08000000
    if not adv.CreateProcessWithLogonW(user, '.', password, 0, None, cmd, CREATE_SUSPENDED | CREATE_NO_WINDOW,
                                       None, str(project), ctypes.byref(si), ctypes.byref(pi)):
        raise SandboxError(f'Could not start the sandboxed process (winerror {ctypes.get_last_error()})')
    job = win32job.CreateJobObject(None, '')
    info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
    info['BasicLimitInformation']['LimitFlags'] |= (win32job.JOB_OBJECT_LIMIT_JOB_MEMORY |
                                                    win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
    info['JobMemoryLimit'] = memory_mb * 1024 * 1024
    win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
    win32job.AssignProcessToJobObject(job, int(pi.hp))   # assigned while suspended: nothing escapes
    k32.ResumeThread(pi.ht)
    started = time.time()
    waited = k32.WaitForSingleObject(pi.hp, int(timeout * 1000))
    timed_out = waited != 0
    if timed_out:
        win32job.TerminateJobObject(job, 1)
        k32.WaitForSingleObject(pi.hp, 5000)
    code = w.DWORD(); k32.GetExitCodeProcess(pi.hp, ctypes.byref(code))
    try:
        output = stdout_path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        output = ''
    return {'exit_code': None if timed_out else int(code.value), 'timed_out': timed_out,
            'output': output[-30000:], 'seconds': round(time.time() - started, 2), 'sandbox': 'account+firewall+job'}


def make_runner(password: str, *, memory_mb: int = 1024):
    """A drop-in for engine.run_checked that executes inside the sandbox.

    Same arguments and result shape, plus 'sandbox'. The working directory must be the project
    root itself: the account is granted write access to that one folder and nothing else.
    """
    from .engine import SafetyError, inside

    def runner(argv, cwd, root, timeout=90, output_limit=30000):
        cwd, root = Path(cwd).resolve(), Path(root).resolve()
        if cwd != root or not inside(cwd, root):
            raise SafetyError('Sandboxed runs must use the project folder itself as the working directory')
        if timeout <= 0 or timeout > 600:
            raise SafetyError('Timeout outside allowed range')
        r = run_confined(list(argv), root, password, timeout=int(timeout), memory_mb=memory_mb)
        output = r['output']
        if r['timed_out']:
            output = f"Timed out after {timeout}s; sandbox process tree terminated.\n" + output
        return {'argv': list(argv), 'exit_code': 124 if r['timed_out'] else r['exit_code'],
                'output': output[-output_limit:], 'elapsed_seconds': r['seconds'], 'sandbox': r['sandbox']}
    runner.adm_isolation = 'sandbox'
    return runner
