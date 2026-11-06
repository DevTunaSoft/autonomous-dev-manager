"""Adversarial harness, round 25: fault injection on the TEST RUNNER (not the
model). A flaky executor (disk pressure, process kill, OS error) must not crash
the repair loop, and a runner that never confirms a real pass must never yield
'verified_direct_repair'."""
import random
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError, make_broken_demo
from adm.ollama_direct import direct_repair
from adm.agent import test_command

BUGS = []
OK = [0]
CORRECT = 'def add(a, b):\n    return a + b\n'


def real_runner(cmd, cwd, root, timeout=120):
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    return {'exit_code': p.returncode, 'output': (p.stdout or '') + (p.stderr or '')}


def fixing_generator(model, prompt, timeout):
    return {'files': [{'path': 'calculator.py', 'content': CORRECT}]}


def make_faulty_runner(mode, rng):
    """Return a runner that injects a fault on some calls."""
    calls = {'n': 0}

    def runner(cmd, cwd, root, timeout=120):
        calls['n'] += 1
        if mode == 'raise_oserror':
            raise OSError('simulated disk/process failure')
        if mode == 'timeout':
            raise subprocess.TimeoutExpired(cmd, timeout)
        if mode == 'malformed_no_exit':
            return {'output': 'weird'}                       # missing 'exit_code'
        if mode == 'malformed_not_dict':
            return 'not a dict'
        if mode == 'none':
            return None
        if mode == 'flaky':                                  # fault on some calls, else real
            if rng.random() < 0.5:
                raise OSError('intermittent failure')
            return real_runner(cmd, cwd, root, timeout=timeout)
        if mode == 'always_zero':                            # LIES: always reports success
            return {'exit_code': 0, 'output': ''}
        return real_runner(cmd, cwd, root, timeout=timeout)
    return runner


def run_trial(base, mode, seed):
    rng = random.Random(seed)
    root = base / f'{mode}{seed}'
    ev = base / f'ev_{mode}{seed}'
    make_broken_demo(root)
    runner = make_faulty_runner(mode, rng)
    status = None
    try:
        report = direct_repair(root, ev, max_repairs=3, generator=fixing_generator, runner=runner)
        status = report.get('status')
    except SafetyError:
        status = 'safety_error'
    except subprocess.TimeoutExpired:
        status = 'timeout_propagated'          # acceptable only if handled as such; flag separately
        BUGS.append(f'[{mode}/{seed}] TimeoutExpired propagated out of direct_repair (should be handled)')
        return
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{mode}/{seed}] UNCAUGHT {type(exc).__name__}: {str(exc)[:130]}')
        return

    # A runner that never actually ran passing tests must never be 'verified'.
    if mode in ('raise_oserror', 'timeout', 'malformed_no_exit', 'malformed_not_dict', 'none'):
        if status == 'verified_direct_repair':
            BUGS.append(f'[{mode}/{seed}] FALSE verified despite a runner that never confirmed a pass')
            return
    # 'always_zero' lies that tests pass. The loop requires source to change AND a
    # re-verification pass; it may report success, but then the honesty contract is
    # that calculator.py really was changed by the (correct) generator — acceptable.
    OK[0] += 1


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for mode in ('raise_oserror', 'timeout', 'malformed_no_exit', 'malformed_not_dict', 'none'):
            for seed in range(3):
                run_trial(base, mode, seed)
        for seed in range(6):
            run_trial(base, 'flaky', seed)
        for seed in range(2):
            run_trial(base, 'clean', seed)
    print(f'round25: {OK[0]} trials ok, {len(BUGS)} bugs')
    for b in BUGS[:20]:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
