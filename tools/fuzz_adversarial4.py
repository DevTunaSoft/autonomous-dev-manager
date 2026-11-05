"""Adversarial harness, round 4: the job queue, worker concurrency, daemon status,
the project lock, recovery journals, and a REAL concurrent-build race. Exit 0 = clean."""
import json
import sys
import threading
import time
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError, make_broken_demo, run_checked
from adm import core, worker, project_lock, repair_recovery, daemon, build, intake, desktop

BUGS = []
OK = [0]
GRACEFUL = (SafetyError, ValueError)


def graceful(label, fn):
    try:
        fn(); OK[0] += 1
    except GRACEFUL:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {str(exc)[:160]}')


def reject(label, fn):
    try:
        fn(); BUGS.append(f'[{label}] accepted bad input (expected reject)')
    except GRACEFUL:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {str(exc)[:160]}')


def pass_core_queue(base):
    sup = core.Supervisor(base / 'core')
    root = make_broken_demo(base / 'cjob')
    for argv in [[], 'notlist', [''], [1], ['ok', 2], None, ['a'] * 100000]:
        reject('core.add', lambda argv=argv: sup.add('n', argv, str(root)))
    reject('core.add_badcwd', lambda: sup.add('n', ['echo', 'x'], str(base / 'missing')))
    sup.add('ok', [sys.executable, '-c', 'print(1)'], str(root))
    graceful('core.run_next', lambda: sup.run_next(timeout=20))
    sup.close()


def pass_worker_queue(base):
    w = worker.WorkerSupervisor(base / 'wk')
    root = make_broken_demo(base / 'wjob')
    for argv in [[], 'x', [''], [1], None]:
        reject('worker.add', lambda argv=argv: w.add('n', argv, str(root)))
    # inject malformed DB rows directly, then run them -- must not crash the worker loop
    for raw in ['not json', '"astring"', '123', '{"a":1}', '[]', 'null']:
        w.db.execute("INSERT INTO jobs(label,argv,cwd,max_attempts,updated,state) VALUES(?,?,?,?,?, 'pending')",
                     ('bad', raw, str(root), 2, time.time()))
        w.db.commit()
        graceful(f'worker.run_once_badrow[{raw[:6]}]', lambda: w.run_once(timeout=10))
    w.close()


def pass_worker_concurrency(base):
    d = base / 'wkc'
    a = worker.WorkerSupervisor(d)
    b = worker.WorkerSupervisor(d)
    root = make_broken_demo(base / 'cjob2')
    a.add('job', [sys.executable, '-c', 'print(1)'], str(root))
    r1, r2 = a.claim(), b.claim()
    claimed = [x for x in (r1, r2) if x]
    if len(claimed) != 1:
        BUGS.append(f'[worker.claim] {len(claimed)} supervisors claimed the same single job')
    else:
        OK[0] += 1
    a.close(); b.close()


def pass_lock(base):
    from adm.project_lock import exclusive_project
    root = base / 'lockdir'; root.mkdir(); (root / '.adm-repair.lock').mkdir()   # lock path is a directory
    graceful('lock_is_directory', lambda: exclusive_project(root).__enter__())
    import os
    root2 = base / 'locksym'; root2.mkdir()
    try:
        os.symlink(base / 'target', root2 / '.adm-repair.lock')
    except OSError:
        return
    reject('lock_is_symlink', lambda: exclusive_project(root2).__enter__())


def pass_recovery(base):
    ev = base / 'rec'; ev.mkdir()
    good_root = str(base)
    for bad in ['not json', '{}', 'null', '[1,2]', '{"version":9,"root":"/nope","entries":[]}',
                '{"version":1,"root":"' + good_root.replace('\\', '\\\\') + '","entries":[{"path":"gone.py",'
                '"original_b64":"eA==","original_sha256":"x","replacement_sha256":"y"}]}']:
        (ev / 'repair-journal.json').write_text(bad)
        graceful(f'recover_journal[{bad[:10]}]', lambda: repair_recovery.recover_journal(base, ev))


def pass_status(base):
    st = base / 'status'; st.mkdir()
    for bad in ['not json', '[]', 'null', '"x"', '123', '{"state":123}', '{bad']:
        (st / 'daemon-status.json').write_text(bad)
        graceful(f'read_status[{bad[:6]}]', lambda: daemon.read_status(st))
        graceful(f'status_summary[{bad[:6]}]', lambda: desktop.status_summary(st))


def pass_build_race(base):
    home = base / 'rhome'; home.mkdir(); state = base / 'rstate'
    ans = {'title': 'Race', 'summary': 's', 'features': ['add'], 'tests': ['add 2 3 is 5'],
           'needs_internet': False, 'questions': []}
    plan = intake.approve(intake.create_plan(state, 'a concurrent build race adder', mode='new', folder='',
                          generator=lambda m, p, t: ans, model='ollama/x', home=home)['path'])
    tests = ('import unittest\nfrom app import add\nclass T(unittest.TestCase):\n'
             ' def test(self):\n  self.assertEqual(add(2, 3), 5)\n')
    code = 'def add(a, b):\n    return a + b\n'
    def tgen(m, p, timeout=300): return {'files': [{'path': 'test_app.py', 'content': tests}]}
    def cgen(m, p, timeout=300): return {'files': [{'path': 'app.py', 'content': code}]}
    def runner(argv, cwd, root, timeout=90, output_limit=30000):
        return run_checked(argv, cwd, root, timeout=timeout)
    runner.adm_isolation = 'sandbox'
    results, errors = [], []
    def go():
        try:
            results.append(build.run_build(state, plan['path'], test_generator=tgen, code_generator=cgen,
                                           model='ollama/x', runner=runner, require_sandbox=True)['status'])
        except SafetyError as exc:
            errors.append(f'SafetyError: {exc}')
        except Exception as exc:
            errors.append(f'UNCAUGHT {type(exc).__name__}: {exc}')
    threads = [threading.Thread(target=go) for _ in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    uncaught = [e for e in errors if e.startswith('UNCAUGHT')]
    folder = Path(plan['folder'])
    app_ok = (folder / 'app.py').is_file() and 'def add' in (folder / 'app.py').read_text()
    tests_ok = (folder / 'test_app.py').read_text() == tests
    if uncaught:
        BUGS.append(f'[build_race] uncaught exceptions: {uncaught[:2]}')
    elif 'built' not in results:
        BUGS.append(f'[build_race] no build succeeded: results={results} errors={errors[:2]}')
    elif not (app_ok and tests_ok):
        BUGS.append('[build_race] project corrupted after concurrent builds')
    else:
        OK[0] += 1


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_core_queue(base)
        pass_worker_queue(base)
        pass_worker_concurrency(base)
        pass_lock(base)
        pass_recovery(base)
        pass_status(base)
        pass_build_race(base)
    print(f'checks passed: {OK[0]}')
    if BUGS:
        print(f'\nBUGS FOUND: {len(BUGS)}')
        for b in BUGS:
            print('  -', b)
        return 1
    print('No crashes or corruption found.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
