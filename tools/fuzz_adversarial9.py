"""Adversarial harness, round 9: the repair enqueue API, windows startup commands,
failure excerpting with extreme bounds, and journal preparation."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError, make_broken_demo
from adm import queued_ai, windows_startup, context, repair_recovery

BUGS = []
OK = [0]
GRACEFUL = (SafetyError, ValueError, PermissionError, OSError)


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


def pass_enqueue(base):
    root = make_broken_demo(base / 'proj')
    state = base / 'state'
    ev = base / 'ev'
    for repairs in [0, 6, -1, 'x', 2.5, None]:
        reject(f'enqueue_repairs[{repairs}]',
               lambda repairs=repairs: queued_ai.enqueue_repair(state, root, ev, model='ollama/x', repairs=repairs))
    for model in ['remote/x', 'ollama/../x', '', None, 'ollama/\x00']:
        reject(f'enqueue_model[{model}]',
               lambda model=model: queued_ai.enqueue_repair(state, root, ev, model=model))
    # overlapping paths must be refused
    reject('enqueue_state_eq_root', lambda: queued_ai.enqueue_repair(root, root, ev, model='ollama/x'))
    reject('enqueue_ev_in_state', lambda: queued_ai.enqueue_repair(state, root, state / 'sub', model='ollama/x'))
    # auto mode with hostile injected inventory
    graceful('enqueue_auto_bad_inventory',
             lambda: queued_ai.enqueue_repair(state, root, ev, model='auto', ram_gib=16, installed_models='notalist'))


def pass_inspect(base):
    for state in [base / 'missing', base / 'empty']:
        state.mkdir(exist_ok=True)
        graceful('inspect_missing', lambda state=state: queued_ai.inspect_repair(state, 1))


def pass_windows_startup(base):
    for state in ['C:\\x', str(base), '', 'relative', '\x00bad']:
        graceful(f'startup_command', lambda state=state: windows_startup.startup_command(state))
        graceful(f'task_command', lambda state=state: windows_startup.windows_task_command(state))
    reject('install_unapproved', lambda: windows_startup.install(str(base), approve=False))


def pass_excerpt():
    outputs = ['', 'x' * 500000, 'FAILED a::b\n' * 10000, '🤖' * 10000, '\x00\x00']
    for out in outputs:
        for mc in [-100, 0, 1, 10, 10 ** 9]:
            graceful(f'excerpt[{mc}]', lambda out=out, mc=mc: context.excerpt_failure(out, max_chars=mc))
    for saved in ['', 'x' * 5000, '../evil', '\x00', 123]:
        graceful('excerpt_saved_to', lambda saved=saved: context.excerpt_failure('FAILED a::b', saved_to=saved if isinstance(saved, str) else ''))


def pass_journal(base):
    root = base / 'jp'; root.mkdir()
    (root / 'app.py').write_text('x = 1\n')
    ev = base / 'jev'
    bad_patches = [
        {'files': [{'path': 'test_app.py', 'content': 'x'}]},     # protected
        {'files': [{'path': '../x.py', 'content': 'x'}]},         # traversal
        {'files': [{'path': 'missing.py', 'content': 'x'}]},      # absent
        {'files': [{'path': 'app.py', 'content': 'y'}]},          # ok
    ]
    for i, patch in enumerate(bad_patches):
        ev_i = base / f'jev{i}'
        graceful(f'prepare_journal[{i}]', lambda patch=patch, ev_i=ev_i: repair_recovery.prepare_journal(root, ev_i, patch))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_enqueue(base)
        pass_inspect(base)
        pass_windows_startup(base)
        pass_excerpt()
        pass_journal(base)
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
