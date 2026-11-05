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
    code = textwrap.dedent('''
        import ctypes, ctypes.wintypes as w, subprocess, sys
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        class BASIC(ctypes.Structure):
            _fields_=[("a",ctypes.c_int64),("b",ctypes.c_int64),("LimitFlags",w.DWORD),("min",ctypes.c_size_t),("max",ctypes.c_size_t),("c",w.DWORD),("d",ctypes.c_size_t),("e",w.DWORD),("f",w.DWORD)]
        class IOC(ctypes.Structure):
            _fields_=[(n,ctypes.c_uint64) for n in ("r","w","o","ro","wo","oo")]
        class EXT(ctypes.Structure):
            _fields_=[("Basic",BASIC),("Io",IOC),("ProcessMemoryLimit",ctypes.c_size_t),("JobMemoryLimit",ctypes.c_size_t),("Peak1",ctypes.c_size_t),("Peak2",ctypes.c_size_t)]
        job = k.CreateJobObjectW(None, None)
        e = EXT(); e.Basic.LimitFlags = 0x2000 | 0x100  # KILL_ON_JOB_CLOSE | JOB_MEMORY
        e.JobMemoryLimit = 200*1024*1024
        ok = k.SetInformationJobObject(job, 9, ctypes.byref(e), ctypes.sizeof(e))
        p = subprocess.Popen([sys.executable,"-c","x=bytearray(800*1024*1024); print('ALLOCATED')"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        k.AssignProcessToJobObject(job, int(p._handle))
        out, err = p.communicate(timeout=60)
        print("SET=%s ALLOCATED=%s rc=%s" % (bool(ok), "ALLOCATED" in out, p.returncode))
    ''')
    r = run_py(code)
    emit('job_object_memory_limit', 'ALLOCATED=False' in r.stdout, r.stdout.strip() or r.stderr.strip())

def probe_job_object_blocks_network():
    # Expected to FAIL: documents that a Job Object alone does not block the network.
    emit('job_object_blocks_network', False, 'Not testable as a block: Job Objects have no network control (expected).')

def probe_restricted_token_pipes():
    code = textwrap.dedent('''
        import ctypes, ctypes.wintypes as w, subprocess, sys
        adv = ctypes.WinDLL("advapi32", use_last_error=True); k = ctypes.WinDLL("kernel32", use_last_error=True)
        tok = w.HANDLE();
        if not adv.OpenProcessToken(k.GetCurrentProcess(), 0x2|0x8|0x80|0x20, ctypes.byref(tok)): raise SystemExit("open token fail")
        new = w.HANDLE()
        # WRITE_RESTRICTED (0x8) with no restricting SIDs and no deleted privileges.
        ok = adv.CreateRestrictedToken(tok, 0x8, 0, None, 0, None, 0, None, ctypes.byref(new))
        print("CREATE=%s err=%s" % (bool(ok), ctypes.get_last_error()))
        if not ok: raise SystemExit
        class SI(ctypes.Structure):
            _fields_=[("cb",w.DWORD),("r",w.LPWSTR),("d",w.LPWSTR),("t",w.LPWSTR),("x",w.DWORD),("y",w.DWORD),("xs",w.DWORD),("ys",w.DWORD),("xc",w.DWORD),("yc",w.DWORD),("fa",w.DWORD),("fl",w.DWORD),("sw",w.WORD),("cb2",w.WORD),("r2",ctypes.c_void_p),("in",w.HANDLE),("out",w.HANDLE),("err",w.HANDLE)]
        class PI(ctypes.Structure):
            _fields_=[("hp",w.HANDLE),("ht",w.HANDLE),("pid",w.DWORD),("tid",w.DWORD)]
        # Pipe for stdout
        sa = ctypes.create_string_buffer(24); ctypes.memmove(sa, (w.DWORD*1)(24), 4); ctypes.memmove(ctypes.byref(sa, 16), (w.DWORD*1)(1), 4)
        rd, wr = w.HANDLE(), w.HANDLE()
        k.CreatePipe(ctypes.byref(rd), ctypes.byref(wr), sa, 0)
        si = SI(); si.cb = ctypes.sizeof(si); si.fl = 0x100; si.out = wr; si.err = wr
        pi = PI()
        cmd = ctypes.create_unicode_buffer('"%s" -c "import subprocess,sys;r=subprocess.run([sys.executable,\\'-c\\',\\'print(7)\\'],capture_output=True,text=True);print(\\'CHILD\\',r.returncode,r.stdout.strip())"' % sys.executable)
        ok = adv.CreateProcessAsUserW(new, None, cmd, None, None, True, 0, None, None, ctypes.byref(si), ctypes.byref(pi))
        print("SPAWN=%s err=%s" % (bool(ok), ctypes.get_last_error()))
        if ok:
            k.WaitForSingleObject(pi.hp, 30000); k.CloseHandle(wr)
            buf = ctypes.create_string_buffer(4096); n = w.DWORD()
            k.ReadFile(rd, buf, 4095, ctypes.byref(n), None)
            print(buf.value.decode(errors="replace"))
    ''')
    r = run_py(code)
    out = (r.stdout + r.stderr).strip()
    emit('restricted_token_child_with_pipes', 'CHILD 0 7' in out, out)

def probe_dedicated_user_and_firewall():
    user, pw = 'admsandbox', 'Adm!' + os.urandom(6).hex() + 'Zz9'
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
        run = ps(f"$s=ConvertTo-SecureString '{pw}' -AsPlainText -Force; $c=New-Object PSCredential('{user}',$s); "
                 f"$p=Start-Process -FilePath '{py}' -ArgumentList '{script}' -Credential $c -WorkingDirectory '{work}' "
                 f"-RedirectStandardOutput '{work}\\out.txt' -Wait -PassThru -NoNewWindow; $p.ExitCode")
        out = ''
        try: out = open(os.path.join(work, 'out.txt')).read()
        except OSError: pass
        emit('sandbox_user_network_blocked', 'NET_BLOCKED' in out, (out or run.stdout + run.stderr))
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
