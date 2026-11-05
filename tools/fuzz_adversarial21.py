"""Adversarial harness, round 21: core.Supervisor durability against a corrupt
job row. worker.run_once already guards a malformed stored command; the
ADM-002 core.Supervisor.run_next must do the same instead of crashing the loop.
Also checks core.mode and firstrun.recommend_model degrade on bad input."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm import core
from adm import firstrun

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


def pass_corrupt_job_row(base):
    sup = core.Supervisor(base / 's1')
    # a valid job, then corrupt its argv column directly (simulated DB corruption)
    tid = sup.add('ok', [sys.executable, '-c', 'pass'], str(base))
    for corrupt in ('not json at all', '"a string"', '42', '{"not":"a list"}', '[123]', '[]', 'null'):
        sup.db.execute("UPDATE tasks SET argv=?, state='pending' WHERE id=?", (corrupt, tid))
        sup.db.commit()
        # run_next must not crash the loop on a malformed row; it should fail the
        # one task cleanly (or skip it), returning without raising.
        no_raise(f'run_next_corrupt[{corrupt[:12]!r}]', lambda: sup.run_next(timeout=10))
    sup.close()


def pass_mode_bad_info():
    # core.mode indexes info fields; a malformed info dict should not KeyError.
    for info in ({}, {'ram_available_bytes': None}, {'ram_available_bytes': 1}):
        graceful(f'mode[{info}]', lambda info=info: core.mode(info), (KeyError, TypeError))


def pass_recommend_model():
    # recommend_model with a valid number works; with bad input should raise a
    # clean TypeError/ValueError, not something worse.
    no_raise('recommend_model_ok', lambda: firstrun.recommend_model(16.0))
    for bad in (None, 'x', object()):
        graceful(f'recommend_model[{bad!r:.12}]', lambda bad=bad: firstrun.recommend_model(bad), (TypeError, ValueError))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_corrupt_job_row(base)
        pass_mode_bad_info()
        pass_recommend_model()
    print(f'round21: {OK[0]} checks ok, {len(BUGS)} bugs')
    for b in BUGS:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
