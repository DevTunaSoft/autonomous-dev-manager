"""Adversarial harness, round 16: autonomous recovery — repair_recovery
(prepare/recover journal) against malformed patches and corrupt/tampered
journals, and recovery.py snapshot/restore against symlinks, oversize,
and unexpected edits."""
import base64
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm import repair_recovery as rr
from adm import recovery

BUGS = []
OK = [0]


def graceful(label, fn):
    try:
        fn(); OK[0] += 1
    except SafetyError:
        OK[0] += 1
    except (ValueError, TypeError, OSError, KeyError) as exc:
        BUGS.append(f'[{label}] unhandled {type(exc).__name__} (want SafetyError): {str(exc)[:120]}')
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {str(exc)[:140]}')


def returns(label, fn, expect):
    try:
        got = fn()
        if got == expect:
            OK[0] += 1
        else:
            BUGS.append(f'[{label}] returned {got!r}, expected {expect!r}')
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] raised {type(exc).__name__}: {str(exc)[:140]}')


def proj(base, name='p'):
    root = base / name
    root.mkdir(parents=True, exist_ok=True)
    (root / 'app.py').write_text('x = 1\n', encoding='utf-8')
    return root


def pass_prepare_malformed(base):
    bad = [{}, {'files': 'x'}, {'files': None}, {'files': [123]}, {'files': [{'path': 'app.py'}]},
           {'files': [{'content': 'y'}]}, {'files': [{'path': 1, 'content': 'y'}]},
           {'files': [{'path': 'app.py', 'content': 2}]}]
    for i, p in enumerate(bad):
        root = proj(base, f'pm{i}')
        ev = base / f'ev{i}'
        graceful(f'prepare_journal[{i}]', lambda root=root, ev=ev, p=p: rr.prepare_journal(root, ev, p))


def pass_recover_corrupt(base):
    root = proj(base, 'rc')
    ev = base / 'evrc'
    ev.mkdir(parents=True, exist_ok=True)
    j = ev / 'repair-journal.json'
    corrupt = ['garbage{', '[1,2,3]', '"str"', '42',
               json.dumps({'version': 2, 'root': str(root.resolve()), 'entries': []}),
               json.dumps({'version': 1, 'root': '/wrong', 'entries': []}),
               json.dumps({'version': 1, 'root': str(root.resolve()), 'entries': 'x'}),
               json.dumps({'version': 1, 'root': str(root.resolve()), 'entries': [123]}),
               json.dumps({'version': 1, 'root': str(root.resolve()),
                           'entries': [{'path': 'app.py', 'original_b64': '!!notb64!!',
                                        'original_sha256': 'x', 'replacement_sha256': 'y'}]}),
               json.dumps({'version': 1, 'root': str(root.resolve()),
                           'entries': [{'path': '../escape.py', 'original_b64': base64.b64encode(b'x').decode(),
                                        'original_sha256': 'x', 'replacement_sha256': 'y'}]})]
    for i, text in enumerate(corrupt):
        j.write_text(text, encoding='utf-8')
        graceful(f'recover_journal[{i}]', lambda: rr.recover_journal(root, ev))
    # no journal -> returns False
    j.unlink(missing_ok=True)
    returns('recover_journal_absent', lambda: rr.recover_journal(root, ev), False)


def pass_journal_roundtrip(base):
    # a genuine prepare -> (simulate interruption) -> recover restores the original
    root = proj(base, 'rt')
    ev = base / 'evrt'
    patch = {'files': [{'path': 'app.py', 'content': 'x = 2   # changed\n'}]}
    rr.prepare_journal(root, ev, patch)
    (root / 'app.py').write_text('x = 2   # changed\n', encoding='utf-8')   # the replacement got written
    returns('recover_roundtrip', lambda: rr.recover_journal(root, ev), True)
    if (root / 'app.py').read_text() != 'x = 1\n':
        BUGS.append('[recover_roundtrip] original not restored')
    else:
        OK[0] += 1


def pass_recovery_snapshot(base):
    root = proj(base, 'snap')
    (root / 'sub').mkdir()
    (root / 'sub' / 'b.py').write_text('y = 2\n', encoding='utf-8')
    dest = base / 'snapbackup'
    returns_hashes = {}
    try:
        returns_hashes = recovery.save_snapshot(root, dest)
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[save_snapshot] raised {type(exc).__name__}: {exc}')
    # overwrite refusal
    graceful('save_snapshot_overwrite', lambda: recovery.save_snapshot(root, dest))
    # dest inside root refused
    graceful('save_snapshot_inside', lambda: recovery.save_snapshot(root, root / 'inner'))
    # restore after an edit + an added file
    (root / 'app.py').write_text('x = 999\n', encoding='utf-8')
    (root / 'extra.py').write_text('junk = 1\n', encoding='utf-8')
    try:
        recovery.restore_snapshot(root, dest, returns_hashes)
        ok = (root / 'app.py').read_text() == 'x = 1\n' and not (root / 'extra.py').exists()
        OK[0] += 1 if ok else BUGS.append('[restore_snapshot] did not restore cleanly')
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[restore_snapshot] raised {type(exc).__name__}: {exc}')
    # tampered snapshot -> refuse
    (dest / 'app.py').write_text('tampered\n', encoding='utf-8')
    graceful('restore_tampered', lambda: recovery.restore_snapshot(root, dest, returns_hashes))


def pass_recovery_symlink_and_limits(base):
    root = proj(base, 'sym')
    try:
        os.symlink(root / 'app.py', root / 'link.py')
    except (OSError, NotImplementedError):
        OK[0] += 1  # platform without symlink support; nothing to test
        return
    graceful('inventory_symlink_refused', lambda: recovery.inventory(root))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_prepare_malformed(base)
        pass_recover_corrupt(base)
        pass_journal_roundtrip(base)
        pass_recovery_snapshot(base)
        pass_recovery_symlink_and_limits(base)
    print(f'round16: {OK[0]} checks ok, {len(BUGS)} bugs')
    for b in BUGS:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
