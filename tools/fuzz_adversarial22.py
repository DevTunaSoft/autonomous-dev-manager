"""Adversarial harness, round 22: provisioning/setup logic — execute_plan with
corrupt resume journals, execute_step with malformed steps, build_plan with
hostile binaries/hardware/model. Logic-level only (real install is Windows)."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm import provision, setup

BUGS = []
OK = [0]


def graceful(label, fn, allowed):
    try:
        fn(); OK[0] += 1
    except allowed:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] unexpected {type(exc).__name__}: {str(exc)[:130]}')


CLEAN = (ValueError, PermissionError, RuntimeError)


def good_plan():
    return {'platform': 'Windows', 'blockers': [],
            'steps': [{'key': 'install_ollama',
                       'argv': ['winget', 'install', '--exact', '--id', setup.OLLAMA_PACKAGE,
                                '--source', 'winget', '--accept-package-agreements',
                                '--accept-source-agreements'],
                       'description': 'x', 'requires_approval': True},
                      {'key': 'pull_model',
                       'argv': ['ollama', 'pull', list(setup.MODELS.values())[0]],
                       'description': 'y', 'requires_approval': True}]}


def pass_execute_plan_journals(base):
    # corrupt journals of various shapes must raise ValueError, never AttributeError
    plan = good_plan()
    fp = json.dumps(plan['steps'], sort_keys=True)
    bad_journals = [
        'garbage{', '[1,2,3]', '"s"', '42',
        json.dumps({'results': 'notadict', 'fingerprint': fp}),
        json.dumps({'results': {}, 'fingerprint': 'WRONG'}),
        json.dumps({'results': {'install_ollama': 'notadict'}, 'fingerprint': fp}),   # value not a dict
        json.dumps({'results': {'install_ollama': 123}, 'fingerprint': fp}),
        json.dumps({'results': {'install_ollama': None}, 'fingerprint': fp}),
    ]
    for i, text in enumerate(bad_journals):
        jp = base / f'journal{i}.json'
        jp.write_text(text, encoding='utf-8')
        graceful(f'execute_plan_journal[{i}]',
                 lambda jp=jp, plan=plan: provision.execute_plan(plan, jp, approved=True,
                                                                 verify=lambda k: False),
                 CLEAN)
    # malformed plans
    for bad in (None, [], 'x', {}, {'platform': 'Linux'},
                {'platform': 'Windows', 'steps': 'nope'},
                {'platform': 'Windows', 'steps': [{'key': 'evil'}]},
                {'platform': 'Windows', 'steps': [{'key': 'install_ollama'}, {'key': 'install_ollama'}]}):
        graceful(f'execute_plan_badplan[{str(bad)[:20]!r}]',
                 lambda bad=bad: provision.execute_plan(bad, base / 'j.json', approved=True), CLEAN)
    # not approved
    graceful('execute_plan_unapproved',
             lambda: provision.execute_plan(good_plan(), base / 'j2.json', approved=False), CLEAN)


def pass_execute_plan_runs_clean(base):
    # a clean run with an injected verifier and fake executor completes.
    plan = good_plan()
    calls = []
    def fake_exec(step, *, approved, system):
        calls.append(step['key'])
        return {'key': step['key'], 'status': 'completed', 'exit_code': 0}
    state = provision.execute_plan(plan, base / 'okjournal.json', approved=True, executor=fake_exec)
    if state.get('status') in ('steps_completed', 'running') and 'install_ollama' in calls:
        OK[0] += 1
    else:
        BUGS.append(f'[execute_plan_clean] status={state.get("status")} calls={calls}')


def pass_execute_step_malformed():
    # malformed step (non-dict, bad argv) must raise a clean error (ValueError /
    # Permission / RuntimeError), never AttributeError/TypeError. system='Windows'
    # bypasses the OS gate so the argv validation path is reached.
    for step in (None, [], 'x', 42, {}, {'key': 'install_ollama'},
                 {'key': 'install_ollama', 'argv': 'notlist'},
                 {'key': 'install_ollama', 'argv': [1, 2, 3]},
                 {'key': 'unknown', 'argv': ['x']},
                 {'key': 'pull_model', 'argv': ['ollama', 'pull', 'evil-model']}):
        graceful(f'execute_step[{str(step)[:24]!r}]',
                 lambda step=step: setup.execute_step(step, approved=True, system='Windows'), CLEAN)


def pass_build_plan_hostile():
    for binaries in (None, {}, {'ollama': None, 'winget': None}, 'notadict', [1, 2]):
        graceful(f'build_plan_binaries[{str(binaries)[:16]!r}]',
                 lambda binaries=binaries: setup.build_plan(system='Windows', binaries=binaries,
                                                            hardware={'ram_available_bytes': 16 * 1024**3,
                                                                      'disk_free_bytes': 100 * 1024**3},
                                                            model=list(setup.MODELS.values())[0]),
                 CLEAN)   # a non-dict must raise a CLEAN error, not AttributeError
    # bad model
    graceful('build_plan_badmodel',
             lambda: setup.build_plan(system='Windows', binaries={}, hardware={'ram_available_bytes': 8*1024**3,
                     'disk_free_bytes': 50*1024**3}, model='evil/model'), CLEAN)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_execute_plan_journals(base)
        pass_execute_plan_runs_clean(base)
        pass_execute_step_malformed()
        pass_build_plan_hostile()
    print(f'round22: {OK[0]} checks ok, {len(BUGS)} bugs')
    for b in BUGS:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
