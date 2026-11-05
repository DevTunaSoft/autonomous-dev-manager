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

    r = sandbox.run_confined(py("open('b.txt','w').write('ok');print('WROTE_INSIDE')"), project, pw)
    emit('write_inside_project', 'WROTE_INSIDE' in r['output'] and (project / 'b.txt').exists(), r)

    r = sandbox.run_confined(py(f"open(r'{outside}\\\\x.txt','w').write('no');print('WROTE_OUTSIDE')"), project, pw)
    emit('write_outside_refused', 'WROTE_OUTSIDE' not in r['output'] and not (outside / 'x.txt').exists(), r['output'])

    r = sandbox.run_confined(py(f"print(open(r'{secret}').read())"), project, pw)
    emit('owner_file_unreadable', 'owner private data' not in r['output'], r['output'])

    net = "import socket\ntry:\n socket.create_connection(('1.1.1.1',443),timeout=5);print('NET_OPEN')\nexcept Exception as e: print('NET_BLOCKED',type(e).__name__)"
    r = sandbox.run_confined(py(net), project, pw)
    emit('network_blocked', 'NET_BLOCKED' in r['output'], r['output'])

    r = sandbox.run_confined(py("import time;time.sleep(60)"), project, pw, timeout=3)
    emit('timeout_kills', r['timed_out'] is True, r)

    r = sandbox.run_confined(py("x=bytearray(900*1024*1024);print('BIG')"), project, pw, memory_mb=300)
    emit('memory_cap', 'BIG' not in r['output'] and r['exit_code'] != 0, r)

    r = sandbox.run_confined([sys.executable, '-m', 'unittest', 'discover', '-s', '.'], project, pw)
    emit('child_process_with_pipes', r['exit_code'] is not None and r['exit_code'] != 0xC0000142, r)

if __name__ == '__main__':
    if os.name != 'nt':
        print('Windows only'); raise SystemExit(2)
    try:
        main()
    except Exception as exc:
        emit('crashed', False, f'{type(exc).__name__}: {exc}')
