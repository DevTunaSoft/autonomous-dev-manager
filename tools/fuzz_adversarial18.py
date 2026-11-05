"""Adversarial harness, round 18: the repair-loop LIFECYCLE and its invariants.

Drive direct_repair on a fresh broken demo many times with a seeded generator
that emits adversarial patches (garbage, path escapes, placeholders, huge /
empty / identical content, non-.py targets, valid-but-wrong code, and
occasionally the real fix). Assert the invariants that make the loop honest:
  * it never raises an UNHANDLED (non-SafetyError) exception;
  * status 'verified_direct_repair' only when the tests actually pass;
  * the frozen test file is never modified;
  * no file is ever created outside the project directory.
"""
import random
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError, make_broken_demo
from adm.ollama_direct import direct_repair

BUGS = []
OK = [0]

CORRECT = 'def add(a, b):\n    return a + b\n'
WRONG = 'def add(a, b):\n    return a * b\n'
FROZEN_TEST = 'test_calculator.py'

ADVERSARIAL = [
    lambda: 'not a dict',
    lambda: {'files': 'x'},
    lambda: {'files': [123]},
    lambda: {'files': [{'path': 'calculator.py'}]},          # missing content
    lambda: {'files': [{'path': 'calculator.py', 'content': ''}]},    # empty
    lambda: {'files': [{'path': 'calculator.py', 'content': 'def add(a,b):\n    # rest unchanged\n'}]},  # placeholder
    lambda: {'files': [{'path': '../escape.py', 'content': CORRECT}]},            # path escape
    lambda: {'files': [{'path': '/abs.py', 'content': CORRECT}]},
    lambda: {'files': [{'path': 'test_calculator.py', 'content': 'x=1\n'}]},      # edit frozen test
    lambda: {'files': [{'path': 'calculator.py', 'content': 'x' * 300000}]},      # oversized
    lambda: {'files': [{'path': 'calculator.py', 'content': 'def add(a, b):\n    return a - b\n'}]},  # identical to broken
    lambda: {'files': [{'path': 'calculator.py', 'content': WRONG}]},             # valid syntax, wrong answer
    lambda: {'files': [{'path': 'calculator.py', 'content': 'def add(:\n'}]},     # syntax error
    lambda: {'files': [{'path': 'notthere.py', 'content': CORRECT}]},             # non-existent file
    lambda: {'files': [{'path': 'calculator.py', 'content': CORRECT}]},           # the real fix
]


def run_trial(base, seed):
    rng = random.Random(seed)
    root = base / f'proj{seed}'
    ev = base / f'ev{seed}'
    make_broken_demo(root)
    frozen_before = (root / FROZEN_TEST).read_text(encoding='utf-8')
    before_files = set(p.name for p in root.iterdir())

    def generator(model, prompt, timeout):
        return rng.choice(ADVERSARIAL)()

    status = None
    try:
        report = direct_repair(root, ev, max_repairs=rng.randint(1, 4), generator=generator)
        status = report.get('status')
    except SafetyError:
        status = 'safety_error'          # a handled refusal is acceptable
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[trial {seed}] UNCAUGHT {type(exc).__name__}: {str(exc)[:140]}')
        return

    # Invariant 1: frozen test never modified.
    if (root / FROZEN_TEST).read_text(encoding='utf-8') != frozen_before:
        BUGS.append(f'[trial {seed}] frozen test file was modified')
        return

    # Invariant 2: no files created outside the project dir (escape attempts).
    for stray in ['escape.py', 'abs.py']:
        if (base / stray).exists() or (root.parent / stray).exists() or Path('/abs.py').exists():
            BUGS.append(f'[trial {seed}] file escaped project dir: {stray}')
            return

    # Invariant 3: verified success must mean the tests really pass now.
    if status == 'verified_direct_repair':
        r = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(root), '-p', 'test_*.py'],
                           cwd=root, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            BUGS.append(f'[trial {seed}] status verified but tests FAIL: {r.stderr[-120:]}')
            return
        if (root / 'calculator.py').read_text(encoding='utf-8') != CORRECT:
            BUGS.append(f'[trial {seed}] verified but calculator.py is not the correct fix')
            return
    OK[0] += 1


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for seed in range(40):
            run_trial(base, seed)
    print(f'round18: {OK[0]} trials ok, {len(BUGS)} bugs')
    for b in BUGS[:20]:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
