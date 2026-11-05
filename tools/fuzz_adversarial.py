"""Adversarial harness: throw hostile/malformed inputs at every layer and report anything that
is NOT handled gracefully. 'Graceful' = returns, or raises SafetyError/ValueError. Anything else
(uncaught TypeError, RecursionError, OSError, a crash, corruption, a false success) is a BUG.

Run: python tools/fuzz_adversarial.py   (exit 0 = clean, 1 = bugs found)
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm import backends, intake, build, sandbox

BUGS = []
OK = [0]
GRACEFUL = (SafetyError, ValueError)


def expect_graceful(label, fn):
    """fn must either return or raise SafetyError/ValueError. Any other exception is a bug."""
    try:
        fn()
        OK[0] += 1
    except GRACEFUL:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001 - we are hunting these
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {exc}')


def expect_reject(label, fn):
    """fn MUST raise SafetyError/ValueError (a reject). Returning is a bug (accepted bad input)."""
    try:
        fn()
        BUGS.append(f'[{label}] accepted bad input (expected a reject)')
    except GRACEFUL:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {exc}')


# ---------------- Pass 1: model-output parsing ----------------
def pass_parsing():
    junk = ['', '   ', 'null', 'true', '42', '"a string"', '{', '}{', '{"a":', 'prose then {"a":1} tail',
            '```json\n{"a":1}\n```', '{"a":1,}', '{"a": NaN}', '{"a":"}"}', '{"n":{"d":[1,2,{"x":3}]}}',
            '[1,2,3,]', 'garbage %%% \x00 more', '{"a":1}{"b":2}', ' [ { "files": [] } ] ',
            '[' * 3000 + ']' * 3000,                      # very deep (unbalanced) nesting
            ('[' * 2500) + '1' + (']' * 2500),            # VALID deep nesting -> RecursionError risk
            '{"a":"unterminated', '{"a":1' + ',"b":2' * 50000 + '}',
            '{' * 4000, 'x' * 500000, None, 123, b'{"a":1}', ['not', 'text'], {'already': 'dict'}]
    for i, v in enumerate(junk):
        expect_graceful(f'extract_json[{i}]', lambda v=v: backends.extract_json(v))
    # shape validators must reject non-conforming structures without crashing
    for v in [None, [], 42, {}, {'files': 'x'}, {'files': [1]}, {'x': 1}, {'files': [{'path': 'a'}]},
              {'files': [{'path': 'test_x.py', 'content': 'x'}]}, 'not json at all', {'files': [{}] * 99}]:
        expect_graceful('validate_tests', lambda v=v: build.validate_tests(v))
        expect_graceful('parse_patch_text', lambda v=v: backends.parse_patch_text(json.dumps(v) if not isinstance(v, str) else v))
    for v in [None, [], 42, {}, {'title': ''}, {'title': 'x'}, {'title': 'x', 'summary': ''},
              {'title': 'x', 'summary': 'y', 'features': 'no', 'tests': []},
              {'title': 'x', 'summary': 'y', 'features': [1, 2], 'tests': [3]},
              {'title': 'a' * 99999, 'summary': 'b' * 99999, 'features': ['f'] * 9999, 'tests': ['t'] * 9999,
               'questions': 'nope'}]:
        expect_graceful('parse_plan', lambda v=v: intake.parse_plan(v))


# ---------------- Pass 2: intake ----------------
def pass_intake(base):
    for v in ['', '   ', 'short', 'x' * 100000, 'line\x00null', '\n\n\n', None, 42, '🤖' * 3000]:
        expect_graceful('validate_request', lambda v=v: intake.validate_request(v))
    for v in ['', 'CON', 'NUL', 'COM1', r'\\server\share', '..', '../../etc', 'C:\\', 'c:', '/', '//x',
              r'C:\Windows\System32', r'C:\Users\Public\x', 'relative/path', 'a' * 5000, None, 42,
              r'C:\ProgramData\ADM', '\x00']:
        expect_graceful('check_existing_folder', lambda v=v: intake.check_existing_folder(v))
    # a plan whose model answer is hostile must never create a folder or a usable plan
    home = base / 'home'; home.mkdir(exist_ok=True)
    state = base / 'state'
    for i, ans in enumerate([None, {}, {'title': 'x'}, 'junk', [1, 2],
                             {'title': '../../evil', 'summary': 's', 'features': ['f'], 'tests': ['t'],
                              'questions': []}]):
        def mk(ans=ans):
            g = lambda m, p, t: ans
            return intake.create_plan(state, 'a reasonable request about a small tool', mode='new',
                                      folder='', generator=g, model='ollama/x', home=home)
        expect_graceful(f'create_plan[{i}]', mk)
    # state-machine abuse on a real plan
    good = {'title': 'T', 'summary': 'does a thing', 'features': ['f1'], 'tests': ['when x then y'],
            'needs_internet': False, 'questions': []}
    plan = intake.create_plan(state, 'a reasonable request about a small tool', mode='new', folder='',
                              generator=lambda m, p, t: good, model='ollama/x', home=home)
    intake.approve(plan['path'])
    expect_reject('double_approve', lambda: intake.approve(plan['path']))
    expect_reject('reject_after_approve', lambda: intake.reject(plan['path']))
    # tamper the approved plan then require_approved must refuse
    data = json.loads(Path(plan['path']).read_text()); data['content']['tests'] = ['tampered']
    Path(plan['path']).write_text(json.dumps(data))
    expect_reject('tampered_plan', lambda: intake.require_approved(plan['path']))
    # corrupted plan file
    Path(plan['path']).write_text('{ not json')
    expect_graceful('corrupt_plan_load', lambda: intake.load_plan(plan['path']))


# ---------------- Pass 3: build / apply_patch ----------------
def pass_build(base):
    from adm.ollama_direct import apply_patch
    root = build.scaffold.__self__ if False else base / 'proj'
    root.mkdir(exist_ok=True)
    (root / 'app.py').write_text('x = 1\n')
    (root / 'test_app.py').write_text('import unittest\n')
    (root / 'requirements.json').write_text('{}')
    original = (root / 'app.py').read_bytes()
    bad_patches = [
        {'files': [{'path': 'test_app.py', 'content': 'x'}]},                 # protected test file
        {'files': [{'path': 'requirements.json', 'content': '{}'}]},          # protected
        {'files': [{'path': '../escape.py', 'content': 'x'}]},                # traversal
        {'files': [{'path': 'C:\\abs.py', 'content': 'x'}]},                  # absolute
        {'files': [{'path': 'sub/dir.py', 'content': 'x'}]},                  # subdir
        {'files': [{'path': 'notpy.txt', 'content': 'x'}]},                   # not .py
        {'files': [{'path': 'missing.py', 'content': 'x'}]},                  # does not exist
        {'files': [{'path': 'app.py', 'content': 'def ('}]},                  # syntax error
        {'files': [{'path': 'app.py', 'content': 'x'}] * 20},                 # too many
        {'files': []},                                                       # empty
        {'files': [{'path': 'app.py'}]},                                     # malformed entry
        {'files': [{'path': 'app.py', 'content': 'y' * 300000}]},            # oversized
        {'files': 'nope'}, {}, None,
    ]
    for i, p in enumerate(bad_patches):
        expect_graceful(f'apply_patch[{i}]', lambda p=p: apply_patch(root, p))
    if (root / 'app.py').read_bytes() != original:
        BUGS.append('[apply_patch] a rejected patch still modified app.py (corruption)')
    else:
        OK[0] += 1
    # build gate / folder classification
    good = {'title': 'T', 'summary': 's', 'features': ['f'], 'tests': ['when x then y'],
            'needs_internet': False, 'questions': []}
    home = base / 'bhome'; home.mkdir(exist_ok=True); state = base / 'bstate'
    plan = intake.create_plan(state, 'a reasonable small tool request', mode='new', folder='',
                              generator=lambda m, p, t: good, model='ollama/x', home=home)
    expect_reject('build_unapproved', lambda: build.build_from_plan(
        plan['path'], base / 'ev1', test_generator=lambda *a, **k: {'files': []},
        code_generator=lambda *a, **k: {}, model='ollama/x', runner=None, require_sandbox=False))


# ---------------- Pass 4: sandbox cmdline ----------------
def pass_sandbox():
    # every one of these must be REJECTED (they would break quoting or inject shell behaviour)
    must_reject = [[], ['a"b'], ['x\x00'], ['%PATH%'], ['a\nb'], ['a&b'], ['a|b'], ['a>b'], ['a<b'],
                   ['ok', 'c:\\path\\'], ['ok', 'a^b'], ['', 'x'], [123], [None]]
    for i, a in enumerate(must_reject):
        expect_reject(f'cmdline_for[{i}]', lambda a=a: sandbox.cmdline_for(a, r'C:\o\out.txt'))
    # a legitimate interpreter command must be accepted
    expect_graceful('cmdline_ok', lambda: sandbox.cmdline_for(
        ['C:\\ProgramData\\ADM\\python\\python.exe', '-m', 'unittest', 'discover', '-s', '.'], r'C:\o\out.txt'))
    for v in [r'C:\Users\Public\p', r'C:\ProgramData', 'C:\\', r'C:\ProgramData\x\y']:
        expect_reject(f'refuse_hardened[{v}]', lambda v=v: sandbox.refuse_hardened_location(v))
    # system folders are rejected by intake.check_existing_folder (not the sandbox location check)
    for v in [r'C:\Windows', r'c:\windows\system32', r'C:\Program Files\x']:
        expect_reject(f'system_folder[{v}]', lambda v=v: intake.check_existing_folder(v))


# ---------------- Pass 5: stats resilience ----------------
def pass_stats(base):
    from adm import dashboard
    state = base / 'sstate'
    (state / 'plans' / 'p1').mkdir(parents=True)
    (state / 'plans' / 'p1' / 'plan.json').write_text('{ corrupt')
    (state / 'builds').mkdir(parents=True)
    (state / 'builds' / 'b1.json').write_text('not json')
    expect_graceful('collect_stats_corrupt', lambda: dashboard.collect_stats(state))
    for v in [-5, 0, 10 ** 12, 'x']:
        expect_graceful(f'fmt_uptime[{v}]', lambda v=v: dashboard._fmt_uptime(v if isinstance(v, (int, float)) else 0))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_parsing()
        pass_intake(base)
        pass_build(base)
        pass_sandbox()
        pass_stats(base)
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
