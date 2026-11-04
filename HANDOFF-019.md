# ADM-019 complete cumulative handoff

## Added
- `adm/daemon.py`: an unattended persistent polling loop for the existing trusted-command worker supervisor. It waits for new jobs, executes queued jobs, emits results, and supports cooperative shutdown between jobs.
- `tests/test_daemon.py`: four new integration/unit tests including a job submitted after the daemon starts and automatic execution of three queued jobs.

## Verified
- `python -B -m unittest discover -s tests -p test_daemon.py -v`: **4/4 passed** on Linux.
- Full-suite attempt `timeout 32s python -B -m unittest discover -s tests -q`: **timed out** (exit 124). This is NOT a complete regression pass. See `full-suite-attempt.log`.
- No actual Windows, Ollama or OpenCode inference tested.

## Limitations and safety
- This is a trusted-command prototype; it does not sandbox untrusted code.
- The daemon must be started manually and remain running; Windows autorun, watchdog and installable service are not implemented.
- Ctrl+C stops between jobs; in-progress work is subject to the worker's configured timeout.
- It does not yet autonomously plan or generate jobs from plain-English requests.

## Run
In the project root:
`python -B -m adm.daemon --state .adm-worker-state --poll 1 --timeout 120`
In another terminal, queue a **trusted** command:
`python -B -m adm.worker_cli --state .adm-worker-state add --label example --cwd . -- python -c "print('hello')"`

## Next engineering gates
1. Integrate AI repair pipeline with durable queue jobs and clear idempotent recovery.
2. Implement and verify Windows boot-start supervisor and safe process isolation.
3. Prove live Ollama/OpenCode repair on actual hardware.
4. Run complete regression to completion and investigate remaining timeouts.
5. Finish automatic installation and simple user interface.

All prior application source, tests and handoffs are retained in this archive.
