"""Adversarial harness, round 13: the diagnostics collector under corrupt
state — collect(), _plan_counts, _recent_builds, _safe's default contract,
and export_bundle with malformed reports/plans and odd evidence."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm import diagnostics

BUGS = []
OK = [0]


def no_raise(label, fn):
    try:
        fn(); OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] raised {type(exc).__name__}: {str(exc)[:160]}')


def check(label, cond):
    if cond:
        OK[0] += 1
    else:
        BUGS.append(f'[{label}] assertion failed')


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding='utf-8')


def seed_corrupt(state):
    # plans: valid, array (not object), garbage
    write(state / 'plans' / 'a' / 'plan.json', {'status': 'approved'})
    write(state / 'plans' / 'b' / 'plan.json', ['not', 'an', 'object'])
    write(state / 'plans' / 'c' / 'plan.json', 'garbage{')
    # builds: valid, array, garbage, non-dict scalar
    write(state / 'builds' / '001.json', {'plan_id': 'x', 'status': 'built', 'checks': []})
    write(state / 'builds' / '002.json', [1, 2, 3])
    write(state / 'builds' / '003.json', 'nope{')
    write(state / 'builds' / '004.json', '42')


def pass_safe_default_contract():
    # _safe must honour the caller's default on error (not return an error string
    # where a dict/list/str is expected).
    check('safe_default_dict', diagnostics._safe(lambda: 1 / 0, {}) == {})
    check('safe_default_list', diagnostics._safe(lambda: 1 / 0, []) == [])
    check('safe_default_str', diagnostics._safe(lambda: 1 / 0, '') == '')
    # with no default, an error string is the documented behaviour
    r = diagnostics._safe(lambda: 1 / 0)
    check('safe_no_default_is_str', isinstance(r, str) and r.startswith('unavailable'))
    # a successful call passes its value through even when a default is given
    check('safe_success_passthrough', diagnostics._safe(lambda: 7, {}) == 7)


def pass_plan_counts_and_builds(state):
    no_raise('plan_counts', lambda: diagnostics._plan_counts(state))
    no_raise('recent_builds', lambda: diagnostics._recent_builds(state))
    counts = diagnostics._plan_counts(state)
    check('plan_counts_is_dict', isinstance(counts, dict))
    builds = diagnostics._recent_builds(state)
    check('recent_builds_is_list', isinstance(builds, list))
    check('recent_builds_items_are_dicts', all(isinstance(x, dict) for x in builds))


def pass_collect_types(state):
    info = diagnostics.collect(state)
    # the fields that pass an explicit default MUST keep that type on failure
    check('collect_plans_dict', isinstance(info['plans_by_status'], dict))
    check('collect_recent_list', isinstance(info['recent_builds'], list))
    check('collect_selfcheck_list', isinstance(info['self_check'], list))
    check('collect_logtail_str', isinstance(info['log_tail'], str))


def pass_export_bundle(base):
    state = base / 'st'
    seed_corrupt(state)
    # a log and some evidence
    (state / 'logs').mkdir(parents=True, exist_ok=True)
    diagnostics.log_line(state, 'hello', component='test')
    write(state / 'evidence' / 'p1' / 'run.log', 'test output')
    dest = base / 'out' / 'bundle.zip'
    no_raise('export_bundle', lambda: diagnostics.export_bundle(state, dest))
    check('bundle_written', dest.is_file() and dest.stat().st_size > 0)
    # empty / missing state must also export without crashing
    no_raise('export_bundle_empty', lambda: diagnostics.export_bundle(base / 'empty', base / 'o2' / 'b.zip'))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        state = base / 'state'
        seed_corrupt(state)
        pass_safe_default_contract()
        pass_plan_counts_and_builds(state)
        pass_collect_types(state)
        pass_export_bundle(base)
    print(f'round13: {OK[0]} checks ok, {len(BUGS)} bugs')
    for b in BUGS:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
