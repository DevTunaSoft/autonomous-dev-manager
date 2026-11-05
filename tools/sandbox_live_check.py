"""Live check of adm.sandbox on a throwaway Windows runner (administrator). Prints one JSON line per check."""
import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm import sandbox

def emit(name, ok, detail):
    print(json.dumps({'check': name, 'ok': bool(ok), 'detail': str(detail)[:500]}), flush=True)

def py(code):
    return [sys.executable, '-c', code]

def main():
    pw = sandbox.provision()
    emit('provision', True, 'account + firewall rule created')
    base = Path(tempfile.mkdtemp(prefix='admlive_'))
    project = base / 'project'; project.mkdir()
    outside = base / 'outside'; outside.mkdir()
    secret = Path.home() / 'adm_secret.txt'; secret.write_text('owner private data')
    (project / 'a.txt').write_text('hi')

    # Every check prints RAN first: a "blocked" result only counts if the program really started.
    r = sandbox.run_confined(py("print('RAN');open('b.txt','w').write('ok');print('WROTE_INSIDE')"), project, pw)
    emit('write_inside_project', 'WROTE_INSIDE' in r['output'] and (project / 'b.txt').exists(), r)

    target = str(outside / 'x.txt').replace('\\', '/')
    r = sandbox.run_confined(py(f"print('RAN');open('{target}','w').write('no');print('WROTE_OUTSIDE')"), project, pw)
    emit('write_outside_refused', 'RAN' in r['output'] and 'WROTE_OUTSIDE' not in r['output']
         and not (outside / 'x.txt').exists(), r['output'])

    sec = str(secret).replace('\\', '/')
    r = sandbox.run_confined(py(f"print('RAN');print(open('{sec}').read())"), project, pw)
    emit('owner_file_unreadable', 'RAN' in r['output'] and 'owner private data' not in r['output'], r['output'])

    (project / 'net.py').write_text("print('RAN')\nimport socket\ntry:\n socket.create_connection(('1.1.1.1',443),timeout=5);print('NET_OPEN')\nexcept Exception as e: print('NET_BLOCKED',type(e).__name__)\n")
    r = sandbox.run_confined([sys.executable, 'net.py'], project, pw)
    emit('network_blocked', 'RAN' in r['output'] and 'NET_BLOCKED' in r['output'], r['output'])

    r = sandbox.run_confined(py("print(1);import time;time.sleep(60)"), project, pw, timeout=3)
    emit('timeout_kills', r['timed_out'] is True and r['seconds'] < 20, r)

    r = sandbox.run_confined(py("print('RAN');x=bytearray(900*1024*1024);print('BIG')"), project, pw, memory_mb=300)
    emit('memory_cap', 'RAN' in r['output'] and 'BIG' not in r['output'] and r['exit_code'] != 0, r)

    (project / 'child.py').write_text("import subprocess,sys\nr=subprocess.run([sys.executable,'-c','print(7)'],capture_output=True,text=True)\nprint('CHILD',r.returncode,r.stdout.strip())\n")
    r = sandbox.run_confined([sys.executable, 'child.py'], project, pw)
    emit('child_process_with_pipes', 'CHILD 0 7' in r['output'], r)

if __name__ == '__main__':
    if os.name != 'nt':
        print('Windows only'); raise SystemExit(2)
    try:
        main()
    except Exception as exc:
        emit('crashed', False, f'{type(exc).__name__}: {exc}')
