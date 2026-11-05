"""Live check of adm.sandbox on a throwaway Windows runner (administrator). Prints one JSON line per check."""
import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm import sandbox

def emit(name, ok, detail):
    print(json.dumps({'check': name, 'ok': bool(ok), 'detail': str(detail)[:500]}), flush=True)

def py(code):
    return [sys.executable, '-c', code]

def e2e_repair():
    from adm.engine import make_broken_demo
    from adm.ollama_direct import direct_repair
    pw = sandbox.provision()
    base = Path(tempfile.mkdtemp(prefix='admrepair_'))
    root = make_broken_demo(base / 'project')
    def fake(model, prompt, timeout):
        return {'files': [{'path': 'calculator.py', 'content': 'def add(a,b):\n    return a+b\n'}]}
    report = direct_repair(root, base / 'evidence', generator=fake, runner=sandbox.make_runner(pw))
    emit('repair_loop_through_sandbox',
         report['status'] == 'verified_direct_repair' and report['isolation'] == 'sandbox'
         and report['baseline']['exit_code'] != 0 and report['baseline'].get('sandbox') == 'account+firewall+job',
         {k: report[k] for k in ('status', 'isolation')} | {'baseline_exit': report['baseline']['exit_code'],
                                                         'baseline_tail': report['baseline']['output'][-200:]})

def shared_folder_check(pw):
    # C:\\Users\\Public is writable by ordinary users. This is informational: it tells us
    # whether the account can escape the project folder through shared locations.
    shared = Path(r'C:\Users\Public') / 'adm_shared_probe'
    shared.mkdir(exist_ok=True)
    proj = Path(tempfile.mkdtemp(prefix='admproj_'))
    t = str(shared / 'leak.txt').replace('\\', '/')
    r = sandbox.run_confined(py(f"print('RAN');open('{t}','w').write('x');print('LEAKED')"), proj, pw)
    emit('shared_public_folder_write_refused', 'RAN' in r['output'] and 'LEAKED' not in r['output'], r['output'])

def scan(pw, label):
    import shutil
    proj = Path(tempfile.mkdtemp(prefix='admscan_'))
    shutil.copy(Path(__file__).with_name('sandbox_scan.py'), proj / 'scan.py')
    dirs = [r'C:\\Users\\Public', r'C:\\ProgramData', r'C:\\Windows\\Temp', r'C:\\Windows\\Tasks']
    r = sandbox.run_confined([sys.executable, 'scan.py'] + dirs, proj, pw, timeout=60)
    lines = [l for l in r['output'].splitlines() if l.startswith(('WRITABLE', 'refused'))]
    emit('scan_' + label, 'RAN' in r['output'] and not any(l.startswith('WRITABLE') for l in lines), lines)

def build_through_sandbox(pw):
    """Full chain on real Windows: approved plan -> frozen tests -> scaffold -> sandboxed build."""
    from adm import intake, build
    base = Path(tempfile.mkdtemp(prefix='admbuild_'))
    state, home = base / 'state', base / 'home'; home.mkdir()
    plan_answer = {'title': 'Tip calculator', 'summary': 'Adds a tip and splits a bill.',
                   'features': ['Add a tip', 'Split a total'],
                   'tests': ['When the bill is 100 and the tip is 20 percent, the total is 120',
                             'When 120 is split between 4 people, each pays 30'],
                   'needs_internet': False, 'questions': []}
    def plan_gen(model, prompt, timeout): return plan_answer
    plan = intake.approve(intake.create_plan(state, 'a tip calculator that splits the bill',
                          mode='new', folder='', generator=plan_gen, model='ollama/fake', home=home)['path'])
    tests = ('import unittest\nfrom app import tip_total, per_person\n\n'
             'class T(unittest.TestCase):\n'
             '    def test_total(self):\n        self.assertEqual(tip_total(100, 20), 120)\n'
             '    def test_split(self):\n        self.assertEqual(per_person(120, 4), 30)\n')
    code = 'def tip_total(b, t):\n    return b + b * t / 100\ndef per_person(total, people):\n    return total / people\n'
    def tgen(model, prompt, timeout=300): return {'files': [{'path': 'test_app.py', 'content': tests}]}
    def cgen(model, prompt, timeout=300): return {'files': [{'path': 'app.py', 'content': code}]}
    report = build.run_build(state, plan['path'], test_generator=tgen, code_generator=cgen,
                             model='ollama/fake', runner=sandbox.make_runner(pw), require_sandbox=True)
    saved = build.builds_root(state) / (report['plan_id'] + '.json')
    ev_outside = not str(Path(report['evidence']).resolve()).startswith(str(Path(plan['folder']).resolve()))
    emit('build_through_sandbox', report['status'] == 'built' and report['isolation'] == 'sandbox'
         and saved.is_file() and ev_outside,
         {'status': report['status'], 'isolation': report['isolation'], 'report_saved': saved.is_file(),
          'evidence_outside_project': ev_outside, 'app_written': (Path(plan['folder']) / 'app.py').read_text()[:60]})

def shared_python_in_sandbox(pw):
    from adm import runtime_install
    src = Path('pyembed')
    if not (src / 'python.exe').is_file():
        emit('shared_python_in_sandbox', False, 'pyembed was not prepared'); return
    exe = runtime_install.ensure_shared_python(src)        # installs to C:\\ProgramData\\ADM\\python (admin)
    proj = Path(tempfile.mkdtemp(prefix='embedsb_'))
    (proj / 'app.py').write_text('def add(a, b):\n    return a + b\n')
    (proj / 'test_app.py').write_text('import unittest\nfrom app import add\n'
                                      'class T(unittest.TestCase):\n    def test(self):\n        self.assertEqual(add(2, 3), 5)\n')
    r = sandbox.run_confined([str(exe), '-m', 'unittest', 'discover', '-s', '.', '-p', 'test_*.py'], proj, pw, timeout=90)
    emit('shared_python_in_sandbox', r['exit_code'] == 0,
         {'exit_code': r['exit_code'], 'timed_out': r['timed_out'], 'out': r['output'][-200:]})

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
    shared_folder_check(pw)
    scan(pw, 'hardened_shared_locations')
    e2e_repair()
    build_through_sandbox(sandbox.provision())
    shared_python_in_sandbox(sandbox.provision())

if __name__ == '__main__':
    if os.name != 'nt':
        print('Windows only'); raise SystemExit(2)
    try:
        main()
    except Exception as exc:
        emit('crashed', False, f'{type(exc).__name__}: {exc}')
