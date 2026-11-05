"""Adversarial harness, round 3: huge-file amend, log rotation, check_patch, validation
boundaries, path-normalization tricks, plan-file tampering. Exit 0 = clean, 1 = bugs."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm import build, intake, sandbox, context, diagnostics

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


def pass_check_patch():
    from adm.context import check_patch
    root = Path(tempfile.mkdtemp())
    big = 'x = 1\n' + ('# pad\n' * 200)
    (root / 'app.py').write_text(big)
    allowed = {'app.py'}
    for patch in [
        {'files': [{'path': 'app.py', 'content': ''}]},                      # empty
        {'files': [{'path': 'app.py', 'content': 'x'}]},                     # deletes most of a big file
        {'files': [{'path': 'app.py', 'content': 'TODO: implement this'}]},  # placeholder
        {'files': [{'path': 'app.py', 'content': '# ... rest unchanged ...'}]},
        {'files': [{'path': 'other.py', 'content': 'x=1'}]},                 # not in allowed set
        {'files': [{'path': 'app.py', 'content': big + '\ny = 2\n'}]},       # legit growth (should pass)
    ]:
        graceful('check_patch', lambda patch=patch: check_patch(root, patch, allowed))


def pass_validate_boundaries():
    short = 'import app\nx'                                  # < 20 chars, no real test
    exact = 'import app\ndef test_a():\n assert app\n'       # fine
    huge = 'import app\n' + 'def test_a():\n assert app\n' * 5000
    for content in (short, exact, huge, 'x' * 19, 'y' * 60001):
        graceful('validate_tests_boundary',
                 lambda content=content: build.validate_tests({'files': [{'path': 'test_app.py', 'content': content}]}))


def pass_path_tricks():
    for v in ['C:/Users/Public/x', r'C:\Users\Public\..\Public\evil', 'c:/users/PUBLIC/sub',
              r'C:\ProgramData\.\x', 'C:/ProgramData', r'\\?\C:\Users\Public\x']:
        reject('refuse_hardened_trick', lambda v=v: sandbox.refuse_hardened_location(v))


def pass_huge_amend(base):
    # amend a project whose existing app.py is enormous -> must fail gracefully, not blow the context budget
    home = base / 'home'; home.mkdir(); state = base / 'state'
    ans = {'title': 'Big', 'summary': 's', 'features': ['feature'], 'tests': ['a check'],
           'needs_internet': False, 'questions': []}
    plan = intake.approve(intake.create_plan(state, 'add something to my big project', mode='existing',
                          folder=str(_make_big_project(base)), generator=lambda m, p, t: ans,
                          model='ollama/x', home=home)['path'])
    new_tests = ('import unittest\nfrom app import f, g\nclass T(unittest.TestCase):\n'
                 ' def test_f(self):\n  self.assertEqual(f(), 1)\n'
                 ' def test_g(self):\n  self.assertEqual(g(), 2)\n')
    def tgen(m, p, timeout=300): return {'files': [{'path': 'test_app.py', 'content': new_tests}]}
    def cgen(m, p, timeout=300): return {'files': [{'path': 'app.py', 'content': 'nope'}]}
    graceful('huge_amend', lambda: build.build_from_plan(plan['path'], base / 'ev', test_generator=tgen,
             code_generator=cgen, model='ollama/x', runner=None, require_sandbox=False, max_repairs=1))


def _make_big_project(base):
    root = base / 'bigproj'; root.mkdir()
    (root / 'app.py').write_text('def f():\n    return 0\n' + ('# pad line\n' * 400000))   # ~5MB source
    (root / 'test_app.py').write_text('import unittest\nfrom app import f\n'
                                      'class T(unittest.TestCase):\n def test(self):\n  self.assertEqual(f(),1)\n')
    (root / 'requirements.json').write_text('{"source_file": "app.py", "checks_in_plain_words": ["x"]}')
    return root


def pass_log_rotation(base):
    state = base / 'logstate'
    for i in range(6000):                       # push the log past its rotation size
        diagnostics.log_line(state, f'line {i} ' + 'x' * 100)
    graceful('log_after_rotation', lambda: diagnostics.log_line(state, 'after'))
    graceful('export_after_rotation', lambda: diagnostics.export_bundle(state, base / 'big.zip'))


def pass_plan_tampering(base):
    home = base / 'phome'; home.mkdir(); state = base / 'pstate'
    good = {'title': 'T', 'summary': 's', 'features': ['f'], 'tests': ['t'], 'needs_internet': False, 'questions': []}
    plan = intake.create_plan(state, 'a reasonable request to build', mode='new', folder='',
                              generator=lambda m, p, t: good, model='ollama/x', home=home)
    path = Path(plan['path'])
    for bad in ['[]', '{}', 'null', '"x"', '{"status":"approved"}', '[1,2,3]',
                json.dumps({'status': 'approved', 'content': {}, 'sha256': 'deadbeef'})]:
        path.write_text(bad)
        reject('require_approved_tampered', lambda: intake.require_approved(str(path)))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_check_patch()
        pass_validate_boundaries()
        pass_path_tricks()
        pass_huge_amend(base)
        pass_log_rotation(base)
        pass_plan_tampering(base)
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
