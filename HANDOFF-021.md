# ADM-021 — Complete development handoff

## Changes
- Added `adm/windows_startup.py`: opt-in Windows Task Scheduler ONLOGON task command generation. No registration is performed without an explicit `--install` action. No elevation requested (`/RL LIMITED`).
- Corrected `adm/daemon.py`: an existing graceful-stop request is honored rather than deleted at startup.
- Added `tests/test_windows_startup.py` with four focused tests.

## Tests actually executed (Linux)
- `python -B -m unittest discover -s tests -p test_windows_startup.py -v`: 4/4 passed.
- `python -B -m unittest discover -s tests -p test_daemon.py -q`: 4/4 passed.
- `python -B -m unittest discover -s tests -p test_worker.py -q`: 11/11 passed.
- Total 19 focused tests passed. Full regression NOT run in this segment.

## Known limits
- Windows Task Scheduler task has NOT been registered or run on Windows.
- Task invocation via `python -m adm.daemon` requires the `adm` package to be importable in the logon environment; this package currently lacks a production installer. Therefore automatic logon startup is not yet verified or turnkey.
- No independent watchdog, Windows service, real Ollama/OpenCode inference or real AI repair evidence.
- Worker commands are not OS-sandboxed: trusted disposable jobs only.
- This source is cumulative from ADM-020, including all previous handoffs.

## Next engineering actions
1. Produce a self-contained Windows installation/bootstrap flow that makes the package importable without manual Python setup.
2. Test scheduled startup, reboot resume and single-instance enforcement on Windows.
3. Real local model tool-use and repair trial; independent acceptance testing.
4. Complete full regression suite with durable evidence and no skipped tests.
