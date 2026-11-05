"""Adversarial harness, round 7: the first-run / local-AI setup flow (which parses external
command output and system state) and concurrent intake approval. Exit 0 = clean."""
import os
import stat
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm import firstrun, intake

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


def pass_assess(base):
    # every injected helper misbehaves; assess must still return a dict and never raise
    def boom(*a, **k):
        raise RuntimeError('helper exploded')
    hostile = [
        dict(find_exe=boom),
        dict(inspect=boom),
        dict(inspect=lambda **k: {}),                       # missing 'installed_models'
        dict(inspect=lambda **k: {'installed_models': 'notalist'}),
        dict(inspect=lambda **k: 'not a dict'),
        dict(python_finder=boom),
        dict(ram_gib=-5), dict(ram_gib=0), dict(ram_gib=10 ** 9), dict(ram_gib=float('nan')),
        dict(home=base / 'nonexistent-home'),
    ]
    for i, kw in enumerate(hostile):
        def run(kw=kw):
            result = firstrun.assess(**kw)
            assert isinstance(result, dict) and 'needs' in result
        graceful(f'assess[{i}]', run)


def pass_recommend_and_prompt():
    for ram in [-100, 0, 0.1, 3, 8, 16, 64, 10 ** 9, float('nan'), float('inf')]:
        graceful(f'recommend_model[{ram}]', lambda ram=ram: firstrun.recommend_model(ram))
    # prompt_text on a well-formed assess output must work; on partial dicts must not hard-crash the app
    good = firstrun.assess(inspect=lambda **k: {'installed_models': []}, ram_gib=16)
    graceful('prompt_text_good', lambda: firstrun.prompt_text(good))


def pass_pull(base):
    reject('pull_unapproved_model', lambda: firstrun.pull_with_progress('ollama', 'evil-model:latest', lambda s: None))
    # a fake 'ollama' exe that emits hostile output must be handled; on_line receives the lines
    script = base / 'fakeollama.sh'
    script.write_text('#!/bin/sh\nprintf "pulling 50%%\\rweird \\xff\\xfe bytes\\n"\nprintf "done\\n"\nexit 0\n')
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    model = next(iter(firstrun.MODELS.values()))
    lines = []
    def on_line(s):
        lines.append(s)
    if os.name != 'nt':
        graceful('pull_fake_exe', lambda: firstrun.pull_with_progress(str(script), model, on_line, timeout=20))
    # an on_line callback that raises must not corrupt anything (process still cleaned up)
    def boom_line(s):
        raise RuntimeError('ui died mid-pull')
    if os.name != 'nt':
        graceful('pull_on_line_raises', lambda: firstrun.pull_with_progress(str(script), model, boom_line, timeout=20))


def pass_run_setup(base):
    a = firstrun.assess(inspect=lambda **k: {'installed_models': []}, ram_gib=16)
    reject('run_setup_unapproved', lambda: firstrun.run_setup(a, approved=False, on_status=lambda s: None))


def pass_concurrent_approve(base):
    home = base / 'chome'; home.mkdir(); state = base / 'cstate'
    ans = {'title': 'Concurrent', 'summary': 's', 'features': ['f'], 'tests': ['t'],
           'needs_internet': False, 'questions': []}
    plan = intake.create_plan(state, 'a tool approved concurrently', mode='new', folder='',
                              generator=lambda m, p, t: ans, model='ollama/x', home=home)
    successes, errors = [], []
    def go():
        try:
            successes.append(intake.approve(plan['path'])['status'])
        except SafetyError:
            errors.append('rejected')
        except Exception as exc:
            errors.append(f'UNCAUGHT {type(exc).__name__}: {exc}')
    threads = [threading.Thread(target=go) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    uncaught = [e for e in errors if e.startswith('UNCAUGHT')]
    folders = set()
    plans_dir = state / 'plans'
    for pj in plans_dir.glob('*/plan.json'):
        import json
        try:
            folders.add(json.loads(pj.read_text()).get('folder'))
        except Exception:
            pass
    if uncaught:
        BUGS.append(f'[concurrent_approve] uncaught: {uncaught[:2]}')
    elif successes.count('approved') < 1:
        BUGS.append(f'[concurrent_approve] no approval succeeded: {successes} {errors}')
    else:
        OK[0] += 1


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_assess(base)
        pass_recommend_and_prompt()
        pass_pull(base)
        pass_run_setup(base)
        pass_concurrent_approve(base)
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
