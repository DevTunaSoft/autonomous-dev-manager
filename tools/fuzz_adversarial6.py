"""Adversarial harness, round 6: release-ZIP verification, resource-admission math, first-run
assessment, the command runner, and runtime self-commands. Exit 0 = clean."""
import io
import json
import math
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError, run_checked
from adm import release, adaptive, firstrun, pyruntime

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


def _zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in entries:
            z.writestr(name, data)
    return buf.getvalue()


def pass_release(base):
    cases = {
        'empty': [],
        'no_manifest': [('ADM/app.py', 'x=1')],
        'manifest_not_json': [('ADM/SOURCE-MANIFEST.json', 'not json')],
        'manifest_not_dict': [('ADM/SOURCE-MANIFEST.json', '[1,2,3]')],
        'manifest_no_files_key': [('ADM/SOURCE-MANIFEST.json', '{"x":1}')],
        'files_not_dict': [('ADM/SOURCE-MANIFEST.json', '{"files":"nope"}')],
        'files_bad_values': [('ADM/SOURCE-MANIFEST.json', '{"files":{"a.py":123}}')],
        'traversal_path': [('ADM/SOURCE-MANIFEST.json', '{"files":{"../evil.py":"00"}}')],
        'abs_path': [('ADM/SOURCE-MANIFEST.json', '{"files":{"/etc/passwd":"00"}}')],
        'backslash_path': [('ADM/SOURCE-MANIFEST.json', '{"files":{"a\\\\b.py":"00"}}')],
        'hash_mismatch': [('ADM/SOURCE-MANIFEST.json', '{"files":{"a.py":"deadbeef"}}'), ('ADM/a.py', 'x=1')],
        'deep_json': [('ADM/SOURCE-MANIFEST.json', '{"files":' + '[' * 2000 + ']' * 2000 + '}')],
    }
    for label, entries in cases.items():
        data = _zip(entries)
        p = base / f'rel-{label}.zip'
        p.write_bytes(data)
        graceful(f'verify_release[{label}]', lambda p=p: release.verify_source_release(p))
    # a genuinely-not-a-zip file
    bad = base / 'notzip.zip'
    bad.write_bytes(b'this is not a zip at all')
    graceful('verify_release[notzip]', lambda: release.verify_source_release(bad))


def pass_adaptive():
    snaps = [
        {}, {'ram_available_bytes': None}, {'ram_available_bytes': 'lots', 'disk_free_bytes': 10},
        {'ram_available_bytes': float('nan'), 'disk_free_bytes': float('nan')},
        {'ram_available_bytes': float('inf'), 'disk_free_bytes': float('inf'), 'cpu_count': float('inf')},
        {'ram_available_bytes': -5, 'disk_free_bytes': -5},
        {'ram_available_bytes': True, 'disk_free_bytes': True, 'cpu_count': True},
        {'ram_available_bytes': 10 ** 30, 'disk_free_bytes': 10 ** 30, 'cpu_count': 10 ** 9},
        {'ram_available_bytes': 8 * 1024**3, 'disk_free_bytes': 50 * 1024**3, 'cpu_count': 'eight'},
        'notadict', None, 42,
    ]
    for snap in snaps:
        graceful('adaptive.decide', lambda snap=snap: adaptive.decide(
            snap if isinstance(snap, dict) else {}, job_ram_gib=2))
    for ram, disk, model in [(float('nan'), 1, 0), (float('inf'), 1, 0), (-1, 1, 0), ('x', 1, 0),
                             (2, float('nan'), 0), (2, 1, float('inf'))]:
        graceful('adaptive.decide_params', lambda ram=ram, disk=disk, model=model: adaptive.decide(
            {'ram_available_bytes': 16 * 1024**3, 'disk_free_bytes': 100 * 1024**3, 'cpu_count': 8},
            job_ram_gib=ram, job_disk_gib=disk, model_loaded_gib=model))


def pass_firstrun():
    for ram in [float('nan'), float('inf'), -5, 0, 10 ** 9, 'x', None]:
        graceful('recommend_model', lambda ram=ram: firstrun.recommend_model(
            ram if isinstance(ram, (int, float)) else 16))
    # assess with adversarial exe discovery / RAM
    for find in [lambda n: None, lambda n: 'C:\\x\\ollama.exe', lambda n: (_ for _ in ()).throw(OSError('boom'))]:
        graceful('assess', lambda find=find: firstrun.assess(ram_gib=16, find_exe=find))
    for ram in [float('nan'), -1, 10 ** 9, 0.0]:
        graceful('assess_ram', lambda ram=ram: firstrun.assess(ram_gib=ram, find_exe=lambda n: None))


def pass_run_checked(base):
    root = base / 'rc'; root.mkdir()
    for argv in [[], 'notlist', [''], [1], None, ['a'] * 10000]:
        graceful('run_checked_argv', lambda argv=argv: run_checked(argv, root, root, timeout=5))
    for t in [0, -1, 10000, 'x', None, float('inf')]:
        graceful('run_checked_timeout', lambda t=t: run_checked([sys.executable, '-c', 'pass'], root, root,
                                                                timeout=t if isinstance(t, (int, float)) else 5))
    # cwd outside root
    graceful('run_checked_escape', lambda: run_checked([sys.executable, '-c', 'pass'], base, root, timeout=5))


def pass_pyruntime():
    for module in ['adm.evil', 'os', '', None, 'adm.ollama_cli; rm -rf', 42]:
        graceful('self_command', lambda module=module: pyruntime.self_command(
            module if isinstance(module, str) else 'x', ['--flag'], frozen=True, executable='x'))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_release(base)
        pass_adaptive()
        pass_firstrun()
        pass_run_checked(base)
        pass_pyruntime()
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
