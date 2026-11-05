"""Adversarial harness, round 11: the dashboard's real counters
(collect_stats) and uptime formatter under hostile/corrupt state — build
reports with wrong field types, malformed plan.json, odd uptimes."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm import dashboard

BUGS = []
OK = [0]
GRACEFUL = (ValueError, OSError, TypeError, OverflowError)


def graceful(label, fn):
    try:
        fn(); OK[0] += 1
    except GRACEFUL:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {str(exc)[:160]}')


def no_raise(label, fn):
    """These must return normally — crashing is the bug."""
    try:
        fn(); OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] raised {type(exc).__name__}: {str(exc)[:160]}')


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding='utf-8')


def pass_collect_stats(base):
    # Hostile build reports: collect_stats must survive every field-type abuse.
    reports = [
        {'status': 'built', 'checks': 5},            # checks is an int, not a list
        {'status': 'built', 'checks': 'abc'},        # checks is a string
        {'status': 'built', 'checks': {'a': 1}},     # checks is a dict
        {'status': 'built', 'checks': None},
        {'status': 'already_passing'},               # no checks key
        {'status': 'built', 'checks': []},
        {'status': 123},                             # status not a string
        [],                                          # report is a list
        'not json at all',
        {'status': 'built', 'checks': [1, 2, 3]},
    ]
    for i, rep in enumerate(reports):
        state = base / f's{i}'
        write(state / 'builds' / f'{i:03d}.json', rep)
        # also a malformed plan.json
        write(state / 'plans' / 'p' / 'plan.json',
              rep if i % 2 else 'garbage{')
        no_raise(f'collect_stats[{rep!r:.30}]', lambda state=state: dashboard.collect_stats(state))

    # empty / missing / file-instead-of-dir
    no_raise('collect_stats_missing', lambda: dashboard.collect_stats(base / 'nope'))
    f = base / 'afile'
    f.write_text('x')
    no_raise('collect_stats_file', lambda: dashboard.collect_stats(f))


def pass_fmt_uptime():
    for s in [0, 1, 59, 60, 61, 3600, 3661, 86400, -1, -60,
              float('nan'), float('inf'), float('-inf'), 1e308, 0.5, 1e18]:
        no_raise(f'_fmt_uptime[{s}]', lambda s=s: dashboard._fmt_uptime(s))
    # result shape sanity for normal values
    if dashboard._fmt_uptime(0) != '0m':
        BUGS.append(f'[_fmt_uptime_zero] got {dashboard._fmt_uptime(0)!r}')
    else:
        OK[0] += 1
    if dashboard._fmt_uptime(3661) != '1h 01m':
        BUGS.append(f'[_fmt_uptime_hour] got {dashboard._fmt_uptime(3661)!r}')
    else:
        OK[0] += 1


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_collect_stats(base)
        pass_fmt_uptime()
    print(f'round11: {OK[0]} checks ok, {len(BUGS)} bugs')
    for b in BUGS:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
