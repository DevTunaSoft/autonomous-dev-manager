"""Adversarial harness, round 27: apply_patch filesystem containment — the last
line of defence that generated code cannot escape the project folder or edit
protected files. Shape-valid but hostile patches (traversal, absolute, subdir,
symlink, null byte, oversized, protected-file edits) must all raise SafetyError
and write nothing outside root."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm.ollama_direct import apply_patch

BUGS = []
OK = [0]


def graceful(label, fn):
    try:
        fn()
        BUGS.append(f'[{label}] did NOT raise (containment bypass?)')
    except SafetyError:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] raised {type(exc).__name__} (want SafetyError): {str(exc)[:120]}')


def project(base, name):
    root = base / name
    root.mkdir(parents=True, exist_ok=True)
    (root / 'app.py').write_text('x = 1\n', encoding='utf-8')
    (root / 'test_app.py').write_text('def test_x():\n    assert True\n', encoding='utf-8')
    return root


def one(path, content='y = 2\n'):
    return {'files': [{'path': path, 'content': content}]}


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        outside = base / 'OUTSIDE.py'

        hostile = {
            'absolute': one(str(base / 'abs.py')),
            'traversal': one('../escape.py'),
            'traversal_deep': one('../../escape.py'),
            'subdir': one('sub/x.py'),
            'backslash_win': one('..\\escape.py'),
            'not_py': one('app.txt'),
            'protected_test': one('test_app.py'),
            'null_byte': one('x\x00.py'),
            'missing_file': one('doesnotexist.py'),
            'oversized': one('app.py', 'x = 1\n' + '#' * 250_001),
            'invalid_python': one('app.py', 'def (:\n'),
            'extra_key': {'files': [{'path': 'app.py', 'content': 'y=2\n', 'mode': '777'}]},
            'too_many': {'files': [{'path': f'f{i}.py', 'content': 'x=1\n'} for i in range(13)]},
            'dup': {'files': [{'path': 'app.py', 'content': 'a=1\n'},
                              {'path': 'app.py', 'content': 'b=2\n'}]},
        }
        for name, patch in hostile.items():
            root = project(base, 'p_' + name.replace('\\', '_'))
            before = (root / 'app.py').read_text(encoding='utf-8')
            graceful(f'apply_patch[{name}]', lambda root=root, patch=patch: apply_patch(root, patch))
            # app.py must be unchanged and nothing must have been written outside root
            if (root / 'app.py').read_text(encoding='utf-8') != before:
                BUGS.append(f'[{name}] app.py was modified despite rejection')
            if outside.exists() or (base / 'escape.py').exists() or (base / 'abs.py').exists():
                BUGS.append(f'[{name}] a file was written OUTSIDE the project root')

        # symlink target (where supported) must be refused
        root = project(base, 'sym')
        try:
            os.symlink(root / 'app.py', root / 'link.py')
            graceful('apply_patch[symlink]', lambda: apply_patch(root, one('link.py')))
        except (OSError, NotImplementedError):
            OK[0] += 1

        # a legitimate top-level app.py edit SUCCEEDS and rolls nothing back
        root = project(base, 'ok')
        changed = apply_patch(root, one('app.py', 'def add(a, b):\n    return a + b\n'))
        if changed == ['app.py'] and 'add' in (root / 'app.py').read_text(encoding='utf-8'):
            OK[0] += 1
        else:
            BUGS.append(f'[legit_edit] unexpected result {changed}')

        # multi-file edit where ONE file is bad -> nothing is committed (atomicity)
        root = project(base, 'atomic')
        (root / 'helper.py').write_text('h = 0\n', encoding='utf-8')
        before_app = (root / 'app.py').read_text(encoding='utf-8')
        before_help = (root / 'helper.py').read_text(encoding='utf-8')
        graceful('apply_patch[partial_rollback]',
                 lambda: apply_patch(root, {'files': [{'path': 'app.py', 'content': 'a = 9\n'},
                                                      {'path': 'missing.py', 'content': 'm = 1\n'}]}))
        if (root / 'app.py').read_text(encoding='utf-8') != before_app:
            BUGS.append('[atomicity] app.py changed although the batch was rejected')
        else:
            OK[0] += 1

        print(f'round27: {OK[0]} checks ok, {len(BUGS)} bugs')
        for b in BUGS:
            print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
