"""Adversarial harness, round 14: the model-facing analysis layer — context.py
(patch_key, check_patch, AttemptLedger, excerpt_failure, traceback parsing,
failure_signature) and repomap.py (build_map/select_context) against
malformed model patches and hostile project trees."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm import context, repomap

BUGS = []
OK = [0]
GRACEFUL = (SafetyError, ValueError, TypeError, OSError, KeyError)


def graceful(label, fn):
    """Bad model/patch input must raise a HANDLED error (SafetyError preferred),
    never an unhandled crash. We accept the GRACEFUL set but flag anything else."""
    try:
        fn(); OK[0] += 1
    except SafetyError:
        OK[0] += 1
    except GRACEFUL as exc:
        BUGS.append(f'[{label}] raised unhandled {type(exc).__name__} (should be SafetyError): {str(exc)[:120]}')
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {str(exc)[:140]}')


def no_raise(label, fn):
    try:
        fn(); OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] raised {type(exc).__name__}: {str(exc)[:140]}')


BAD_PATCHES = [
    {}, {'files': 'x'}, {'files': None}, {'files': [123]}, {'files': [None]},
    {'files': [{'path': 'a.py'}]},                 # missing content
    {'files': [{'content': 'x'}]},                 # missing path
    {'files': [{'path': 123, 'content': 'x'}]},    # non-str path
    {'files': [{'path': 'a.py', 'content': 999}]}, # non-str content
    {'files': [{'path': 'a.py', 'content': 'x', 'extra': 1}]},  # extra key
    {'files': []},
    {'files': [{'path': 'a.py', 'content': 'x'}, 'oops']},
]


def pass_patch_key():
    for i, p in enumerate(BAD_PATCHES):
        graceful(f'patch_key[{i}]', lambda p=p: context.patch_key(p))


def pass_check_patch(base):
    root = base / 'proj'
    root.mkdir(parents=True, exist_ok=True)
    (root / 'app.py').write_text('x = 1\n' * 100, encoding='utf-8')
    for i, p in enumerate(BAD_PATCHES):
        graceful(f'check_patch[{i}]', lambda p=p: context.check_patch(root, p, {'app.py'}))


def pass_ledger():
    led = context.AttemptLedger()
    for i, p in enumerate(BAD_PATCHES):
        graceful(f'ledger.seen_patch[{i}]', lambda p=p: led.seen_patch(p))
    # record() takes failure output + changed list; must tolerate odd output
    for out in ['', 'x' * 100000, 'FAIL: t (m.C)\n' * 500, '\x00\x01binary', 'Error: boom']:
        no_raise(f'ledger.record[{out[:8]!r}]',
                 lambda out=out: led.record(1, {'files': [{'path': 'a.py', 'content': 'y'}]}, out, ['a.py']))


def pass_failure_parsing():
    outs = ['', 'no failures here', 'FAIL: test_x (mod.Class)',
            'FAILED tests/test_a.py::test_b', 'File "evil.py", line 9999999999999',
            'File "' + 'A' * 5000 + '", line 1', '\x00\x01\x02 binary junk',
            '=' * 100 + '\n' + 'ERROR: t (m.C)\n', 'x' * 500000,
            'Traceback:\n' + 'File "x.py", line 1\n' * 2000]
    for i, out in enumerate(outs):
        no_raise(f'failing_tests[{i}]', lambda out=out: context.failing_tests(out))
        no_raise(f'excerpt_failure[{i}]', lambda out=out: context.excerpt_failure(out))
        no_raise(f'failure_signature[{i}]', lambda out=out: context.failure_signature(out))


def pass_excerpt_bounds():
    for mc in [0, 1, -5, 10, 100000]:
        no_raise(f'excerpt_maxchars[{mc}]',
                 lambda mc=mc: context.excerpt_failure('FAIL: t (m.C)\n' + 'line\n' * 1000, max_chars=mc))


def pass_traceback_files(base):
    root = base / 'tbp'
    root.mkdir(parents=True, exist_ok=True)
    (root / 'real.py').write_text('x=1\n', encoding='utf-8')
    for out in ['File "real.py", line 1', 'File "../../etc/passwd", line 1',
                'File "/abs/outside.py", line 1', 'File "real.py\x00", line 1',
                'File "' + 'A' * 4000 + '", line 2', 'no frames']:
        no_raise(f'traceback_files[{out[:12]!r}]', lambda out=out: context.traceback_files(out, root))


def pass_repomap(base):
    root = base / 'repo'
    (root / 'pkg').mkdir(parents=True, exist_ok=True)
    (root / 'good.py').write_text('import os\ndef f(a, b=1, *c, **d):\n    return a\n', encoding='utf-8')
    (root / 'bad.py').write_text('def oops(:\n', encoding='utf-8')          # syntax error
    (root / 'binary.py').write_bytes(b'\x00\x01\x02\xff\xfe')               # non-utf8
    (root / 'huge.py').write_text('x=1\n' * 50000, encoding='utf-8')
    (root / 'nested.py').write_text('(' * 2000 + '1' + ')' * 2000 + '\n', encoding='utf-8')
    (root / 'adir.py').mkdir()                                              # a directory named *.py
    (root / 'test_good.py').write_text('from good import f\n', encoding='utf-8')
    no_raise('build_map', lambda: repomap.build_map(root))
    no_raise('render_map', lambda: repomap.render_map(repomap.build_map(root)))
    no_raise('editable_files', lambda: repomap.editable_files(root))
    no_raise('select_context_ok',
             lambda: repomap.select_context(root, 'File "good.py", line 2', 100000))
    # tiny budget should raise SafetyError (handled), not crash
    graceful('select_context_tiny',
             lambda: repomap.select_context(root, 'File "good.py", line 2', 10))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_patch_key()
        pass_check_patch(base)
        pass_ledger()
        pass_failure_parsing()
        pass_excerpt_bounds()
        pass_traceback_files(base)
        pass_repomap(base)
    print(f'round14: {OK[0]} checks ok, {len(BUGS)} bugs')
    for b in BUGS:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
