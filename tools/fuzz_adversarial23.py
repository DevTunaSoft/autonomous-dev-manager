"""Adversarial harness, round 23: runtime install path logic and AI-repair
reconciliation — fixup_pth on corrupt/odd ._pth files, and inspect_repair /
enqueue_repair guards. Logic-level (no real Ollama, no Windows install)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm import runtime_install
from adm import queued_ai

BUGS = []
OK = [0]


def no_raise(label, fn):
    try:
        fn(); OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] raised {type(exc).__name__}: {str(exc)[:140]}')


def graceful(label, fn, allowed):
    try:
        fn(); OK[0] += 1
    except allowed:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] unexpected {type(exc).__name__}: {str(exc)[:140]}')


def pass_fixup_pth(base):
    # no ._pth present -> returns None, no error
    d0 = base / 'none'; d0.mkdir()
    no_raise('fixup_pth_absent', lambda: runtime_install.fixup_pth(d0))
    # a normal embeddable ._pth
    d1 = base / 'normal'; d1.mkdir()
    (d1 / 'python312._pth').write_text('python312.zip\n#import site\n', encoding='utf-8')
    no_raise('fixup_pth_normal', lambda: runtime_install.fixup_pth(d1))
    got = (d1 / 'python312._pth').read_text(encoding='utf-8')
    if '.' in got.splitlines() and 'import site' in got:
        OK[0] += 1
    else:
        BUGS.append(f'[fixup_pth_normal_result] missing . or import site: {got!r}')
    # a corrupt / non-UTF8 ._pth must not crash the install with UnicodeDecodeError
    d2 = base / 'binary'; d2.mkdir()
    (d2 / 'python312._pth').write_bytes(b'python312.zip\r\n\xff\xfe\x00bad bytes\n#import site\n')
    no_raise('fixup_pth_non_utf8', lambda: runtime_install.fixup_pth(d2))
    # empty ._pth
    d3 = base / 'empty'; d3.mkdir()
    (d3 / 'python312._pth').write_bytes(b'')
    no_raise('fixup_pth_empty', lambda: runtime_install.fixup_pth(d3))
    # after fixup, every file must still be valid-ish text ending with . and import site
    for d in (d2, d3):
        res = runtime_install.fixup_pth(d)
        if res is not None:
            txt = res.read_text(encoding='utf-8', errors='replace')
            OK[0] += 1 if ('.' in txt.splitlines() and 'import site' in txt) else BUGS.append(f'[fixup_pth_fixed[{d.name}]] bad result')


def pass_shared_python_dir():
    # honours an explicit programdata and the env override; always ends with ADM/python
    no_raise('shared_dir_explicit', lambda: runtime_install.shared_python_dir('/tmp/pd'))
    p = runtime_install.shared_python_dir('/tmp/pd')
    OK[0] += 1 if p.as_posix().endswith('ADM/python') else BUGS.append(f'[shared_dir] {p}')


def pass_inspect_repair(base):
    state = base / 'st'
    # invalid job ids (incl. bool, 0, negative, non-int) -> SafetyError
    for jid in (0, -1, True, False, 'x', None, 1.5):
        graceful(f'inspect_repair_badid[{jid!r}]',
                 lambda jid=jid: queued_ai.inspect_repair(state, jid), SafetyError)
    # a valid-looking id that does not exist -> SafetyError (not found)
    graceful('inspect_repair_missing', lambda: queued_ai.inspect_repair(state, 999), SafetyError)


def pass_enqueue_guards(base):
    # repairs out of range, bad model, and overlapping state/project paths rejected
    root = base / 'proj'; root.mkdir()
    (root / 'requirements.json').write_text('{}'); (root / 'app.py').write_text('x=1\n')
    (root / 'test_app.py').write_text('def test_x():\n    assert True\n')
    st = base / 'state'; ev = base / 'ev'
    graceful('enqueue_bad_repairs',
             lambda: queued_ai.enqueue_repair(st, root, ev, model='ollama/x', repairs=99), SafetyError)
    graceful('enqueue_bad_model',
             lambda: queued_ai.enqueue_repair(st, root, ev, model='remote/x', repairs=2), SafetyError)
    # state inside project -> rejected
    graceful('enqueue_overlap',
             lambda: queued_ai.enqueue_repair(root / 'inner', root, ev, model='ollama/x', repairs=2), SafetyError)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_fixup_pth(base)
        pass_shared_python_dir()
        pass_inspect_repair(base)
        pass_enqueue_guards(base)
    print(f'round23: {OK[0]} checks ok, {len(BUGS)} bugs')
    for b in BUGS:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
