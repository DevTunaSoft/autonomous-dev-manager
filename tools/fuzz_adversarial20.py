"""Adversarial harness, round 20: concurrency stress of the worker queue.

Several independent WorkerSupervisor instances (separate connections, separate
owners) race on ONE shared queue. Each job writes a byte to its own marker
file. Invariants:
  * every job reaches a terminal state ('passed');
  * no job ever executes twice (no double-claim) -> each marker is exactly 1 byte;
  * the shared SQLite database never corrupts under contention.
"""
import sys
import threading
import time
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.worker import WorkerSupervisor

BUGS = []
OK = [0]

N_JOBS = 24
N_WORKERS = 6


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        state = base / 'queue'
        markers = base / 'markers'
        markers.mkdir(parents=True, exist_ok=True)

        # Enqueue jobs from one supervisor; each job appends a byte to its marker.
        boss = WorkerSupervisor(state)
        job_ids = []
        for i in range(N_JOBS):
            marker = markers / f'm{i}'
            code = f'open(r"{marker}", "a").write("x")'
            job_ids.append(boss.add(f'job{i}', [sys.executable, '-c', code], str(base), max_attempts=1))
        boss.close()

        errors = []
        stop = threading.Event()

        def worker():
            try:
                sup = WorkerSupervisor(state)
            except BaseException as exc:          # noqa: BLE001
                errors.append(f'open db: {type(exc).__name__}: {exc}')
                return
            idle = 0
            try:
                while not stop.is_set():
                    try:
                        result = sup.run_once(timeout=15)
                    except BaseException as exc:          # noqa: BLE001
                        errors.append(f'run_once: {type(exc).__name__}: {exc}')
                        return
                    if result is None:
                        idle += 1
                        if idle >= 3:          # queue looks drained
                            return
                        time.sleep(0.05)
                    else:
                        idle = 0
            finally:
                sup.close()

        threads = [threading.Thread(target=worker, name=f'w{i}') for i in range(N_WORKERS)]
        t0 = time.time()
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=120)
        stop.set()

        # ---- invariants ----
        if errors:
            for e in errors[:10]:
                BUGS.append(f'[worker error] {e}')
        else:
            OK[0] += 1

        # Every marker exists and is exactly one byte (ran exactly once).
        ran_once = 0
        for i in range(N_JOBS):
            m = markers / f'm{i}'
            if not m.is_file():
                BUGS.append(f'[job {i}] never executed (no marker)')
            else:
                size = m.stat().st_size
                if size == 1:
                    ran_once += 1
                else:
                    BUGS.append(f'[job {i}] executed {size} times (double-claim / re-run)')
        if ran_once == N_JOBS:
            OK[0] += 1

        # Final DB state: every job terminal and 'passed'; DB still queryable.
        try:
            check = WorkerSupervisor(state)
            rows = check.status()
            check.close()
            states = [r.get('state') for r in rows] if isinstance(rows, list) else []
            if len(states) == N_JOBS and all(s == 'passed' for s in states):
                OK[0] += 1
            else:
                from collections import Counter
                BUGS.append(f'[final states] {dict(Counter(states))} (expected {N_JOBS}x passed)')
        except BaseException as exc:          # noqa: BLE001
            BUGS.append(f'[db readback] {type(exc).__name__}: {exc}')

        print(f'round20: {OK[0]} invariants ok, {len(BUGS)} bugs '
              f'({N_WORKERS} workers x {N_JOBS} jobs in {time.time()-t0:.1f}s)')
        for b in BUGS[:20]:
            print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
