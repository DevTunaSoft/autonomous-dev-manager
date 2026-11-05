"""Adversarial harness, round 12: packaging filesystem and concurrency edges
— main.py present as a directory, read-only roots, racing packaging runs,
and the no-app / no-packager contract under odd roots."""
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm import package

BUGS = []
OK = [0]
GRACEFUL = (SafetyError, ValueError, PermissionError, OSError, IsADirectoryError)


def graceful(label, fn):
    try:
        fn(); OK[0] += 1
    except GRACEFUL:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {str(exc)[:160]}')


def make_app(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / 'app.py').write_text('def add(a, b):\n    return a + b\n', encoding='utf-8')


PLAN = {'content': {'title': 'Demo'}}


def pass_main_is_directory(base):
    root = base / 'dirmain'
    make_app(root)
    (root / 'main.py').mkdir()
    graceful('write_entry_main_is_dir', lambda: package.write_entry(root, PLAN))


def pass_readonly_root(base):
    root = base / 'ro'
    make_app(root)
    os.chmod(root, 0o500)
    try:
        if os.access(root / 'probe', os.W_OK):
            OK[0] += 1  # environment allows writes regardless (e.g. root); nothing to assert
        else:
            graceful('write_entry_readonly', lambda: package.write_entry(root, PLAN))
    finally:
        os.chmod(root, 0o700)


def pass_odd_roots(base):
    missing = base / 'missing'
    graceful('package_missing_root', lambda: package.package_project(missing, missing / 'd', plan=PLAN))
    afile = base / 'afile'
    afile.write_text('x')
    graceful('package_root_is_file', lambda: package.package_project(afile, base / 'd1', plan=PLAN))
    empty = base / 'empty'
    empty.mkdir()
    graceful('package_empty_root', lambda: package.package_project(empty, empty / 'd', plan=PLAN))


def pass_concurrent_write_entry(base):
    root = base / 'race'
    make_app(root)
    errors = []

    def work():
        try:
            package.write_entry(root, PLAN)
        except BaseException as exc:          # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work) for _ in range(12)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    bad = [e for e in errors if not isinstance(e, GRACEFUL)]
    if bad:
        BUGS.append(f'[concurrent_write_entry] uncaught {type(bad[0]).__name__}: {bad[0]}')
    else:
        OK[0] += 1
    src = (root / 'main.py').read_text(encoding='utf-8')
    try:
        compile(src, 'main.py', 'exec')
        OK[0] += 1
    except SyntaxError as exc:
        BUGS.append(f'[concurrent_write_entry_syntax] corrupt entry: {exc}')


def pass_dist_paths(base):
    for title in ['', '***', None, '   ']:
        name = package.exe_name(title)
        cmd = package.package_command('py', Path('main.py'), name, base / 'd', base / 'b')
        i = cmd.index('--name')
        if not cmd[i + 1].strip():
            BUGS.append(f'[package_command_empty_name[{title!r}]]')
        else:
            OK[0] += 1


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_main_is_directory(base)
        pass_readonly_root(base)
        pass_odd_roots(base)
        pass_concurrent_write_entry(base)
        pass_dist_paths(base)
    print(f'round12: {OK[0]} checks ok, {len(BUGS)} bugs')
    for b in BUGS:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
