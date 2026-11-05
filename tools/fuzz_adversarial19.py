"""Adversarial harness, round 19: release.py — verify_source_release against
malformed/hostile archives and manifests, source_files against symlinks, and
create_source_release against bad roots/destinations."""
import hashlib
import json
import os
import sys
import tempfile
import warnings
import zipfile
from pathlib import Path

warnings.filterwarnings('ignore', category=UserWarning)   # we craft duplicate entries on purpose

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm import release

BUGS = []
OK = [0]
GRACEFUL = (ValueError, OSError, zipfile.BadZipFile)


def graceful(label, fn):
    try:
        fn(); OK[0] += 1
    except GRACEFUL:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {str(exc)[:140]}')


def make_zip(base, name, entries, manifest=None, raw_manifest=None):
    """entries: {arcname: bytes}. manifest auto-built from entries unless given."""
    p = base / name
    with zipfile.ZipFile(p, 'w', zipfile.ZIP_DEFLATED) as z:
        for arc, data in entries.items():
            z.writestr(arc, data)
        if raw_manifest is not None:
            z.writestr('ADM/SOURCE-MANIFEST.json', raw_manifest)
        elif manifest is not None:
            z.writestr('ADM/SOURCE-MANIFEST.json', json.dumps(manifest))
    return p


def pass_verify_malformed(base):
    # not a zip at all
    nz = base / 'notzip.zip'; nz.write_bytes(b'this is not a zip file')
    graceful('verify_notzip', lambda: release.verify_source_release(nz))
    # empty zip
    graceful('verify_empty', lambda: release.verify_source_release(make_zip(base, 'empty.zip', {})))
    # zip with files but no manifest
    graceful('verify_no_manifest',
             lambda: release.verify_source_release(make_zip(base, 'nomani.zip', {'ADM/a.py': b'x=1'})))
    # manifest not JSON
    graceful('verify_bad_json',
             lambda: release.verify_source_release(make_zip(base, 'badjson.zip', {'ADM/a.py': b'x'}, raw_manifest='garbage{')))
    # manifest is a list, not a dict
    graceful('verify_manifest_list',
             lambda: release.verify_source_release(make_zip(base, 'mlist.zip', {'ADM/a.py': b'x'}, raw_manifest='[1,2,3]')))
    # manifest files value not a dict
    graceful('verify_files_notdict',
             lambda: release.verify_source_release(make_zip(base, 'fnd.zip', {'ADM/a.py': b'x'}, manifest={'format': 'x', 'files': 'nope'})))
    # manifest entries non-str
    graceful('verify_entries_nonstr',
             lambda: release.verify_source_release(make_zip(base, 'ens.zip', {'ADM/a.py': b'x'}, manifest={'files': {'a.py': 123}})))
    # names/manifest mismatch
    graceful('verify_mismatch',
             lambda: release.verify_source_release(make_zip(base, 'mm.zip', {'ADM/a.py': b'x'},
                     manifest={'files': {'b.py': hashlib.sha256(b'x').hexdigest()}})))
    # traversal / unsafe names in manifest
    for bad in ('../evil.py', '/abs.py', 'a\\b.py'):
        data = b'x'
        graceful(f'verify_unsafe[{bad}]',
                 lambda bad=bad: release.verify_source_release(
                     make_zip(base, f'uns{abs(hash(bad))%1000}.zip', {'ADM/' + bad.replace("\\","_").replace("..","_").replace("/","_"): data},
                              manifest={'files': {bad: hashlib.sha256(data).hexdigest()}})))
    # hash mismatch
    graceful('verify_hashmismatch',
             lambda: release.verify_source_release(make_zip(base, 'hm.zip', {'ADM/a.py': b'actual'},
                     manifest={'files': {'a.py': hashlib.sha256(b'different').hexdigest()}})))
    # duplicate entries (craft manually)
    dup = base / 'dup.zip'
    with zipfile.ZipFile(dup, 'w') as z:
        z.writestr('ADM/a.py', b'x'); z.writestr('ADM/a.py', b'y')
        z.writestr('ADM/SOURCE-MANIFEST.json', json.dumps({'files': {'a.py': hashlib.sha256(b'x').hexdigest()}}))
    graceful('verify_duplicates', lambda: release.verify_source_release(dup))


def pass_verify_valid(base):
    # a genuinely valid archive verifies and returns the file count
    data = {'a.py': b'print(1)\n', 'sub/b.py': b'x=2\n'}
    man = {'format': 'ADM-source-v1', 'files': {k: hashlib.sha256(v).hexdigest() for k, v in data.items()}}
    z = make_zip(base, 'valid.zip', {'ADM/' + k: v for k, v in data.items()}, manifest=man)
    try:
        n = release.verify_source_release(z)
        OK[0] += 1 if n == 2 else BUGS.append(f'[verify_valid] returned {n}, expected 2')
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[verify_valid] raised {type(exc).__name__}: {exc}')


def pass_source_files_symlink(base):
    root = base / 'src'
    (root / 'adm').mkdir(parents=True)
    (root / 'adm' / 'x.py').write_text('x=1\n')
    try:
        os.symlink(root / 'adm' / 'x.py', root / 'adm' / 'link.py')
    except (OSError, NotImplementedError):
        OK[0] += 1
        return
    graceful('source_files_symlink', lambda: list(release.source_files(root)))


def pass_create_release(base):
    # bad root (no adm/tests)
    graceful('create_badroot', lambda: release.create_source_release(base / 'empty', base / 'out1.zip'))
    # destination inside the source tree
    root = base / 'full'
    (root / 'adm').mkdir(parents=True); (root / 'adm' / '__init__.py').write_text('')
    (root / 'tests').mkdir(); (root / 'adm' / 'daemon.py').write_text('x=1\n')
    graceful('create_dest_inside', lambda: release.create_source_release(root, root / 'inner.zip'))
    # a valid create round-trips through verify
    try:
        info = release.create_source_release(root, base / 'release.zip')
        OK[0] += 1 if info['file_count'] >= 2 and (base / 'release.zip').is_file() else BUGS.append('[create_valid] bad result')
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[create_valid] raised {type(exc).__name__}: {exc}')


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_verify_malformed(base)
        pass_verify_valid(base)
        pass_source_files_symlink(base)
        pass_create_release(base)
    print(f'round19: {OK[0]} checks ok, {len(BUGS)} bugs')
    for b in BUGS:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
