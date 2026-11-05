"""Windows sandbox feasibility probes. Run on a throwaway CI runner ONLY.

Each probe prints one JSON line: {"probe", "ok", "detail"}. Probes never claim
success without observing the behavior (a blocked connection, a refused write).
"""
import ctypes, json, os, subprocess, sys, tempfile, textwrap

def emit(probe, ok, detail):
    print(json.dumps({'probe': probe, 'ok': bool(ok), 'detail': str(detail)[:600]}), flush=True)

CHILD_NET = ("import socket,sys\n"
             "try:\n s=socket.create_connection(('1.1.1.1',443),timeout=5); print('NET_OPEN')\n"
             "except Exception as e: print('NET_BLOCKED',type(e).__name__)\n")

def run_py(code, **kw):
    return subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=60, **kw)

def probe_baseline_network():
    r = run_py(CHILD_NET)
    emit('baseline_network_visible', 'NET_OPEN' in r.stdout, r.stdout.strip() or r.stderr.strip())

def probe_job_object_limits():
    import win32job, win32process, win32con
    job = win32job.CreateJobObject(None, '')
    info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
    info['BasicLimitInformation']['LimitFlags'] |= (win32job.JOB_OBJECT_LIMIT_JOB_MEMORY |
                                                    win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
    info['JobMemoryLimit'] = 200 * 1024 * 1024
    win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
    p = subprocess.Popen([sys.executable, '-c', "x=bytearray(800*1024*1024); print('ALLOCATED')"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         creationflags=win32con.CREATE_SUSPENDED if False else 0)
    win32job.AssignProcessToJobObject(job, int(p._handle))
    out, err = p.communicate(timeout=60)
    emit('job_object_memory_limit', 'ALLOCATED' not in out and p.returncode != 0,
         f'rc={p.returncode} out={out.strip()!r} err={err.strip()[-200:]!r} (child may have allocated before assignment)')

def probe_job_object_blocks_network():
    # Expected to FAIL: documents that a Job Object alone does not block the network.
    emit('job_object_blocks_network', False, 'Not testable as a block: Job Objects have no network control (expected).')

def probe_restricted_token_pipes():
    import win32api, win32con, win32pipe, win32file, win32process, win32security, win32event, pywintypes
    tok = win32security.OpenProcessToken(win32api.GetCurrentProcess(),
            win32con.TOKEN_DUPLICATE | win32con.TOKEN_QUERY | win32con.TOKEN_ASSIGN_PRIMARY | win32con.TOKEN_ADJUST_DEFAULT)
    restricted = win32security.CreateRestrictedToken(tok, 0x8, [], [], [])  # WRITE_RESTRICTED
    sa = pywintypes.SECURITY_ATTRIBUTES(); sa.bInheritHandle = True
    rd, wr = win32pipe.CreatePipe(sa, 0)
    win32api.SetHandleInformation(rd, win32con.HANDLE_FLAG_INHERIT, 0)
    si = win32process.STARTUPINFO(); si.dwFlags = win32con.STARTF_USESTDHANDLES
    si.hStdOutput = wr; si.hStdError = wr; si.hStdInput = win32file.INVALID_HANDLE_VALUE if False else wr
    code = "import subprocess,sys;r=subprocess.run([sys.executable,'-c','print(7)'],capture_output=True,text=True);print('CHILD',r.returncode,r.stdout.strip())"
    cmd = f'"{sys.executable}" -c "{code}"'
    h, ht, pid, tid = win32process.CreateProcessAsUser(restricted, None, cmd, None, None, True, 0, None, None, si)
    win32event.WaitForSingleObject(h, 30000); wr.Close()
    out = win32file.ReadFile(rd, 4096)[1].decode(errors='replace')
    emit('restricted_token_child_with_pipes', 'CHILD 0 7' in out, out.strip())

def probe_dedicated_user_and_firewall():
    user, pw = 'admsandbox', 'Ab1!' + os.urandom(4).hex()
    def ps(cmd):
        return subprocess.run(['powershell', '-NoProfile', '-Command', cmd], capture_output=True, text=True, timeout=120)
    r = subprocess.run(['net', 'user', user, pw, '/add'], capture_output=True, text=True)
    if r.returncode != 0:
        emit('dedicated_user_created', False, r.stdout + r.stderr); return
    emit('dedicated_user_created', True, user)
    try:
        work = tempfile.mkdtemp(prefix='admsb_')
        py = sys.executable
        # Block outbound for this python.exe path when run by the sandbox user.
        sid = ps(f"(New-Object System.Security.Principal.NTAccount('{user}')).Translate([System.Security.Principal.SecurityIdentifier]).Value").stdout.strip()
        rule = ps(f"New-NetFirewallRule -DisplayName 'ADM-sandbox-block' -Direction Outbound -Action Block "
                  f"-LocalUser 'D:(A;;CC;;;{sid})' | Out-Null; 'RULE_OK'")
        emit('firewall_rule_for_user', 'RULE_OK' in rule.stdout, rule.stdout + rule.stderr)
        script = os.path.join(work, 'net.py'); open(script, 'w').write(CHILD_NET)
        subprocess.run(['icacls', work, '/grant', f'{user}:(OI)(CI)F'], capture_output=True)
        import win32process, win32event, win32con
        si = win32process.STARTUPINFO()
        cmd = f'cmd.exe /c ""{py}" "{script}" > "{work}\\out.txt" 2>&1"'
        h, ht, pid, tid = win32process.CreateProcessWithLogonW(user, '.', pw, 0, None, cmd,
                                                              win32con.CREATE_NO_WINDOW, None, work, si)
        win32event.WaitForSingleObject(h, 60000)
        out = ''
        try: out = open(os.path.join(work, 'out.txt')).read()
        except OSError: pass
        emit('sandbox_user_network_blocked', 'NET_BLOCKED' in out, out or 'no output captured')
    finally:
        ps("Remove-NetFirewallRule -DisplayName 'ADM-sandbox-block' -ErrorAction SilentlyContinue")
        subprocess.run(['net', 'user', user, '/delete'], capture_output=True)

if __name__ == '__main__':
    if os.name != 'nt':
        print('Windows only'); raise SystemExit(2)
    for fn in (probe_baseline_network, probe_job_object_limits, probe_job_object_blocks_network,
               probe_restricted_token_pipes, probe_dedicated_user_and_firewall):
        try:
            fn()
        except Exception as exc:
            emit(fn.__name__, False, f'probe crashed: {type(exc).__name__}: {exc}')
