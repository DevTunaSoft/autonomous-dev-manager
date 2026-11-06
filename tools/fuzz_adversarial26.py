"""Adversarial harness, round 26: build-level concurrency + fault interaction.

Several build_from_plan calls race on the SAME approved project folder (project
lock contention), and one worker's generator raises mid-build. Invariants:
  * no thread raises an UNHANDLED (non-SafetyError) exception;
  * the project lock always releases (a faulting build never deadlocks the rest);
  * the frozen test file is never corrupted;
  * the project ends in a consistent state (a real build produced correct code).
"""
import subprocess
import sys
import threading
import time
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm import build, intake

BUGS = []
OK = [0]

PLAN_ANSWER = {'title': 'Adder', 'summary': 'Adds two numbers.',
               'features': ['add two numbers'],
               'tests': ['When the inputs are 2 and 3, the result is 5'],
               'needs_internet': False, 'questions': []}

GOOD_TESTS = ('import unittest\nfrom app import add\n\n'
              'class T(unittest.TestCase):\n'
              '    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n\n'
              "if __name__ == '__main__':\n    unittest.main()\n")
GOOD_CODE = 'def add(a, b):\n    return a + b\n'


def test_gen(model, prompt, timeout=300):
    time.sleep(0.02)
    return {'files': [{'path': 'test_app.py', 'content': GOOD_TESTS}]}


def code_gen(model, prompt, timeout=300):
    time.sleep(0.02)
    return {'files': [{'path': 'app.py', 'content': GOOD_CODE}]}


def faulting_code_gen(model, prompt, timeout=300):
    raise RuntimeError('simulated generator crash mid-build')


def local_runner(cmd, cwd, root, timeout=120):
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    return {'exit_code': p.returncode, 'output': (p.stdout or '') + (p.stderr or '')}


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        state = base / 'state'
        home = base / 'home'; home.mkdir()

        def g(model, prompt, timeout): return PLAN_ANSWER
        plan = intake.create_plan(state, 'A small program that adds two numbers together',
                                  mode='new', folder='', generator=g, model='ollama/x', home=home)
        plan = intake.approve(plan['path'])
        root = Path(plan['folder'])
        frozen_seen = {}

        results = []
        lock = threading.Lock()

        def worker(i, faulting):
            cg = faulting_code_gen if faulting else code_gen
            ev = base / f'ev{i}'
            try:
                report = build.build_from_plan(plan['path'], ev, test_generator=test_gen,
                                               code_generator=cg, model='ollama/x',
                                               runner=local_runner, require_sandbox=False,
                                               timeout=60, max_repairs=2)
                with lock:
                    results.append(('ok', report.get('status')))
            except SafetyError as exc:
                with lock:
                    results.append(('safety', str(exc)[:40]))
            except BaseException as exc:          # noqa: BLE001
                with lock:
                    results.append(('CRASH', f'{type(exc).__name__}: {exc}'))
            # snapshot the frozen test file if it exists right now
            tp = root / 'test_app.py'
            if tp.is_file():
                with lock:
                    frozen_seen[i] = tp.read_text(encoding='utf-8')

        # 5 real builders + 2 faulting ones, all racing on the same folder
        plan_mix = [(i, i >= 5) for i in range(7)]
        threads = [threading.Thread(target=worker, args=(i, f)) for i, f in plan_mix]
        t0 = time.time()
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=120)

        alive = [th for th in threads if th.is_alive()]
        if alive:
            BUGS.append(f'[deadlock] {len(alive)} build threads did not finish in 120s '
                        '(project lock likely not released on a faulting build)')
        else:
            OK[0] += 1

        # No unhandled crash in any thread.
        crashes = [r for r in results if r[0] == 'CRASH']
        if crashes:
            for c in crashes[:5]:
                BUGS.append(f'[unhandled build crash] {c[1]}')
        else:
            OK[0] += 1

        # At least one real builder must have succeeded (built / already_passing).
        built = [r for r in results if r[0] == 'ok' and r[1] in ('built', 'already_passing')]
        if built:
            OK[0] += 1
        else:
            BUGS.append(f'[no successful build] results={results}')

        # Frozen test file is always exactly the scaffolded content whenever present.
        for i, text in frozen_seen.items():
            if text != GOOD_TESTS:
                BUGS.append(f'[frozen test corrupted] thread {i}')
                break
        else:
            OK[0] += 1

        # Final project state is consistent: app.py has the correct code, tests pass.
        if (root / 'app.py').is_file():
            r = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(root), '-p', 'test_*.py'],
                               cwd=root, capture_output=True, text=True, timeout=60)
            OK[0] += 1 if r.returncode == 0 else BUGS.append(f'[final state] tests fail: {r.stderr[-120:]}')
        else:
            BUGS.append('[final state] no app.py after builds')

        # ---- lock-release-on-fault (sequential, deterministic) ----
        # A build whose generator crashes must release the project lock so a
        # later build on the same folder can proceed (no permanent lock leak).
        state2 = base / 'state2'; home2 = base / 'home2'; home2.mkdir()
        plan2 = intake.approve(intake.create_plan(
            state2, 'A small program that adds two numbers together', mode='new',
            folder='', generator=g, model='ollama/x', home=home2)['path'])
        try:
            build.build_from_plan(plan2['path'], base / 'evf', test_generator=test_gen,
                                  code_generator=faulting_code_gen, model='ollama/x',
                                  runner=local_runner, require_sandbox=False, timeout=60, max_repairs=2)
            BUGS.append('[lock_release] faulting build did not raise')
        except SafetyError:
            BUGS.append('[lock_release] faulting build raised SafetyError before reaching the fault')
        except RuntimeError:
            OK[0] += 1          # the injected generator crash surfaced as expected
        # now a real build on the SAME folder must succeed -> lock was released
        try:
            rep = build.build_from_plan(plan2['path'], base / 'evok', test_generator=test_gen,
                                        code_generator=code_gen, model='ollama/x',
                                        runner=local_runner, require_sandbox=False, timeout=60, max_repairs=2)
            OK[0] += 1 if rep.get('status') in ('built', 'already_passing') else \
                BUGS.append(f'[lock_release] recovery build status={rep.get("status")}')
        except BaseException as exc:          # noqa: BLE001
            BUGS.append(f'[lock_release] recovery build failed: {type(exc).__name__}: {exc}')

        print(f'round26: {OK[0]} invariants ok, {len(BUGS)} bugs '
              f'(7 racing builds in {time.time()-t0:.1f}s; results={results})')
        for b in BUGS[:20]:
            print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
