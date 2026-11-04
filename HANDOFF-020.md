# ADM-020 complete source handoff

## New in this version
- `adm/daemon.py`: atomic heartbeat/status file, cooperative stop request, `--status` and `--stop` CLI commands.
- `tests/test_daemon_lifecycle.py`: status/stop/lifecycle tests.
- Full ADM-019 cumulative code, previous tests, and handoffs retained.

## Verified evidence
- `python -B -m unittest discover -s tests -p 'test_daemon*.py' -v`: **7 tests PASS** on Linux.
- Full regression attempted with a 95-second timeout; execution did not finish in the allotted runtime. **No full regression PASS claim.**
- No Windows runtime, reboot-startup, real local AI repair, or safe untrusted-project execution test performed.

## Run
`python -m adm.daemon --state .adm-worker-state`
`python -m adm.daemon --state .adm-worker-state --status`
`python -m adm.daemon --state .adm-worker-state --stop`

## Known limitations
- Status heartbeat records last poll; while a long job runs, heartbeat can become stale. This is not an independent watchdog.
- Stop is cooperative: active jobs finish before shutdown.
- No single-instance OS-level lock. Do not start multiple daemon instances on the same state folder.
- No Windows automatic startup or secure sandbox. Trusted commands only.
- Current runner does not yet autonomously plan and execute arbitrary AI coding projects.

## Next work
- Independent heartbeat during running jobs, single-instance locking, Windows startup registration and validation.
- Fix complete regression timeout and run all tests.
- Benchmark real Ollama/OpenCode agent and build full installer.
