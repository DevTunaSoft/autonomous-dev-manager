"""Adversarial harness, round 2: filesystem, locking, resource-exhaustion, repo-mapping,
failure-parsing, model-name and diagnostics edge cases. Exit 0 = clean, 1 = bugs."""
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError, make_broken_demo, run_checked
from adm import backends, context, repomap, model_selection, build, intake, diagnostics

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


def pass_repomap(base):
    # a project whose source has a syntax error / binary content must not crash the repo map
    root = base / 'rm'; root.mkdir()
    (root / 'app.py').write_text('def broken(:\n')                       # invalid syntax
    (root / 'weird.py').write_bytes(b'\x00\x01\x02 not text \xff\xfe')   # binary
    (root / 'test_app.py').write_text('import unittest\nfrom app import x\n')
    (root / 'requirements.json').write_text('{}')
    graceful('repomap.build_map', lambda: repomap.build_map(root))
    graceful('repomap.select_context', lambda: repomap.select_context(root, 'Traceback\n  File "app.py"\nError', 4000))
    graceful('repomap.editable_files', lambda: repomap.editable_files(root))


def pass_context():
    for out in ['', 'x' * 500000, 'no test ids here at all', '\x00\x00', '🤖' * 10000,
                'FAILED a::b\n' * 5000, 'Traceback\n' + 'nested ' * 10000]:
        graceful('excerpt_failure', lambda out=out: context.excerpt_failure(out))
        graceful('failure_signature', lambda out=out: context.failure_signature(out))
        graceful('failing_tests', lambda out=out: context.failing_tests(out))


def pass_models():
    for m in ['ollama/../../etc/passwd', 'ollama/a b', 'ollama/a;rm -rf', 'local/x', 'remote/x',
              'ollama/', 'ollama/\x00', 'OLLAMA/X', 'ollama/' + 'a' * 5000, '', None, 42,
              'ollama/model\nwith\nnewlines']:
        graceful('safe_model', lambda m=m: backends.safe_model(m))
    for models, ram in [(['a' * 999], 16), (['x:999999b'], 16), (['y:-5b'], 16), (['z:0b'], 16),
                        (['ok:3b'] * 10000, 16), ('notalist', 16), ([1, 2, 3], 16), (['m:3b'], -1),
                        (['m:3b'], 10 ** 9), (['m:3b'], 'x')]:
        graceful('select_installed_model', lambda models=models, ram=ram:
                 model_selection.select_installed_model(models if isinstance(models, list) else models,
                                                        ram_gib=ram if isinstance(ram, (int, float)) else 16))


def pass_locking(base):
    from adm.project_lock import exclusive_project
    root = make_broken_demo(base / 'lockproj')
    with exclusive_project(root):
        # a second acquisition of the same project must fail cleanly, not hang or crash
        reject('double_exclusive_lock', lambda: exclusive_project(root).__enter__())


def pass_hang_timeout(base):
    # generated code that hangs must be killed by the test timeout, not hang the build forever
    from adm.intake import create_plan, approve
    home = base / 'hhome'; home.mkdir(); state = base / 'hstate'
    ans = {'title': 'Adder', 'summary': 's', 'features': ['add'], 'tests': ['add 2 3 is 5'],
           'needs_internet': False, 'questions': []}
    plan = approve(create_plan(state, 'a tiny adder tool', mode='new', folder='',
                               generator=lambda m, p, t: ans, model='ollama/x', home=home)['path'])
    tests = ('import unittest\nfrom app import add\nclass T(unittest.TestCase):\n'
             '    def test(self):\n        self.assertEqual(add(2, 3), 5)\n')
    def tgen(m, p, timeout=300): return {'files': [{'path': 'test_app.py', 'content': tests}]}
    def hang(m, p, timeout=300):
        return {'files': [{'path': 'app.py', 'content': 'import time\ndef add(a, b):\n    time.sleep(600)\n'}]}
    def runner(argv, cwd, root, timeout=90, output_limit=30000):
        return run_checked(argv, cwd, root, timeout=timeout)
    runner.adm_isolation = 'sandbox'
    started = time.time()
    report = build.build_from_plan(plan['path'], base / 'hev', test_generator=tgen, code_generator=hang,
                                   model='ollama/x', runner=runner, require_sandbox=True, timeout=5, max_repairs=1)
    elapsed = time.time() - started
    if report['status'] == 'built':
        BUGS.append('[hang_timeout] a hanging program was reported as built')
    elif elapsed > 90:
        BUGS.append(f'[hang_timeout] build took {elapsed:.0f}s (timeout not enforced)')
    else:
        OK[0] += 1


def pass_diagnostics(base):
    # state where plans/ and builds/ are FILES, not directories
    state = base / 'dstate'; state.mkdir()
    (state / 'plans').write_text('i am a file')
    (state / 'builds').write_text('also a file')
    graceful('collect_weird_state', lambda: diagnostics.collect(state))
    graceful('export_weird_state', lambda: diagnostics.export_bundle(state, base / 'b.zip'))
    for v in [float('inf'), float('nan'), -1, 10 ** 15]:
        graceful('fmt_uptime', lambda v=v: __import__('adm.dashboard', fromlist=['_fmt_uptime'])._fmt_uptime(v))


def pass_symlink_project(base):
    # an existing folder containing a symlink must be refused by the build, not followed
    import os
    if not hasattr(os, 'symlink'):
        return
    root = base / 'symproj'; root.mkdir()
    (root / 'app.py').write_text('x = 1')
    (root / 'test_app.py').write_text('import unittest')
    (root / 'requirements.json').write_text('{"source_file": "app.py", "checks_in_plain_words": []}')
    try:
        os.symlink(base / 'secret.txt', root / 'link.py')
    except OSError:
        return
    home = base / 'shome'; home.mkdir(); state = base / 'sstate'
    ans = {'title': 'X', 'summary': 's', 'features': ['f'], 'tests': ['t'], 'needs_internet': False, 'questions': []}
    plan = intake.approve(intake.create_plan(state, 'add to my project please', mode='existing',
                          folder=str(root), generator=lambda m, p, t: ans, model='ollama/x', home=home)['path'])
    graceful('build_symlinked_project', lambda: build.build_from_plan(
        plan['path'], base / 'symev', test_generator=lambda *a, **k: {'files': [{'path': 'test_app.py', 'content':
            'import unittest\nfrom app import x\nclass T(unittest.TestCase):\n def test(self):\n  self.assertTrue(x)\n'}]},
        code_generator=lambda *a, **k: {'files': [{'path': 'app.py', 'content': 'x = 1'}]},
        model='ollama/x', runner=None, require_sandbox=False))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_repomap(base)
        pass_context()
        pass_models()
        pass_locking(base)
        pass_hang_timeout(base)
        pass_diagnostics(base)
        pass_symlink_project(base)
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
