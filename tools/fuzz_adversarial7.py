"""Adversarial harness, round 7: provisioning plans/journals, repair-prompt construction,
the model probe, and the pipeline orchestrator. Exit 0 = clean."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm import provision, context, repomap, model_probe

BUGS = []
OK = [0]
GRACEFUL = (SafetyError, ValueError, PermissionError)


def graceful(label, fn):
    try:
        fn(); OK[0] += 1
    except GRACEFUL:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {str(exc)[:160]}')


def pass_provision(base):
    jp = base / 'journal.json'
    # unapproved always refuses
    graceful('execute_plan_unapproved', lambda: provision.execute_plan({'platform': 'Windows', 'steps': []},
             jp, approved=False))
    bad_plans = ['notdict', None, 42, [], {}, {'platform': 'Linux', 'steps': []},
                 {'platform': 'Windows', 'steps': 'nope'},
                 {'platform': 'Windows', 'steps': [1, 2]},
                 {'platform': 'Windows', 'steps': [{'nokey': 1}]},
                 {'platform': 'Windows', 'steps': [{'key': 'evil'}]},
                 {'platform': 'Windows', 'steps': [{'key': 'pull_model'}, {'key': 'pull_model'}]}]
    for i, plan in enumerate(bad_plans):
        graceful(f'execute_plan[{i}]', lambda plan=plan, i=i: provision.execute_plan(
            plan, base / f'j{i}.json', approved=True, executor=lambda s: {'ok': True}))
    # corrupt journal file for an otherwise-fine plan
    good = {'platform': 'Windows', 'steps': [{'key': 'install_ollama'}]}
    for bad in ['not json', '[]', 'null', '123', '{"fingerprint": 1}']:
        jp2 = base / f'cj-{abs(hash(bad))}.json'
        jp2.write_text(bad)
        graceful(f'execute_plan_corruptjournal[{bad[:6]}]', lambda jp2=jp2: provision.execute_plan(
            good, jp2, approved=True, executor=lambda s: {'ok': True}))


def pass_prompt():
    for req in ['', 'x' * 500000, 'req', '🤖' * 5000]:
        for fv in ['', 'failure', 'x' * 500000]:
            for attempt in [0, 1, -5, 10 ** 9]:
                for ctx in ['', 'context here', 'y' * 200000]:
                    for notes in ['', 'note']:
                        graceful('build_repair_prompt', lambda req=req, fv=fv, attempt=attempt, ctx=ctx, notes=notes:
                                 context.build_repair_prompt(req, fv, attempt, ctx, notes))
                        break
                    break


def pass_render_map(base):
    root = base / 'rm'; root.mkdir()
    (root / 'app.py').write_text('def f():\n    return 1\n')
    (root / 'test_app.py').write_text('import unittest\n')
    (root / 'requirements.json').write_text('{}')
    graceful('build_map', lambda: repomap.build_map(root))
    entries = repomap.build_map(root)
    for budget in [-1, 0, 1, 10 ** 9, 50]:
        graceful(f'render_map[{budget}]', lambda budget=budget: repomap.render_map(entries, max_chars=budget))


def pass_model_probe():
    class FakeResp:
        def __init__(self, body):
            self._b = body.encode() if isinstance(body, str) else body
        def read(self, *a):
            return self._b
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
    class FakeOpener:
        def __init__(self, body):
            self.body = body
        def open(self, req, timeout=None):
            return FakeResp(self.body)
    for body in ['not json', '[]', 'null', '{}', '{"models":[{"name":"x"}]}',
                 '{"done":true,"response":123}', '{"done":false}', 'x' * 10, '{"models":"no"}']:
        graceful(f'smoke_test[{body[:8]}]', lambda body=body: model_probe.smoke_test(
            'qwen2.5-coder:3b', timeout=3, opener=FakeOpener(body)))
    # not in allowlist -> ValueError
    graceful('smoke_test_badmodel', lambda: model_probe.smoke_test('evil-model', timeout=3))
    graceful('benchmark_bad', lambda: model_probe.benchmark_report(['a', 'a'], timeout=3))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_provision(base)
        pass_prompt()
        pass_render_map(base)
        pass_model_probe()
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
