# ADM-015 — Complete cumulative source handoff

## Scope
Full cumulative ADM source, tests, setup documentation and historical handoffs from ADM-014, plus this segment's changes. This is a prototype, not a finished autonomous builder.

## Fix
`tests/test_worker.py`: `test_timeout_kills_descendant` no longer assumes the child PID file appears within 0.7 seconds under load. It runs the worker with a separate SQLite connection in a background thread, waits for the child startup marker, verifies the timeout exit code, and verifies descendant termination. The first attempt at this fix surfaced a SQLite thread-affinity exception; that was corrected by creating the worker connection in the worker thread.

## Evidence
- Focused `test_worker.py` run: 11/11 PASS.
- Before this change, bounded complete regression run: 103 tests completed; 11 of 12 modules passed; `test_worker.py` failed at the startup race assertion.
- After this change, full regression attempt: interrupted before completion; progress report `regression-015-final.json` contains partial results only. **DO NOT claim complete regression passed.**
- No actual Windows/OpenCode/Ollama acceptance run.

## Next engineering tasks
1. Investigate why test execution sometimes terminates without completing. Collect external runner exit/termination reason, resource pressure, and per-module timing. Do not merely increase timeouts indefinitely.
2. Complete the full regression suite on a stable host and verify the process tree is clean.
3. Connect automatic provisioning and conduct actual local model/agent repair tests on Windows.
4. Maintain full cumulative source ZIP after each segment.

## Commands
`python -B -m unittest discover -s tests -p test_worker.py -q`
`python -B -m adm.regression --timeout 35 --output regression-results.json`
