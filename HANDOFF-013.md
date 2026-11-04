# ADM-013 — Complete source handoff

## Changes in this segment
- Strengthened `adm/regression.py` so each test module runs in a dedicated process group.
- On module timeout, terminates the process tree rather than only the test parent.
- Added `RegressionProcessTreeTests.test_timeout_stops_descendant_process`, proving child-process cleanup on Linux.
- All previous ADM-012 application source and test modules remain included.

## Evidence and limitations
- `python -B -m unittest discover -s tests -p test_regression.py -q`: 6 tests PASS, including a real subprocess descendant killed on timeout.
- A bounded full-suite run with a 4-second per-module deadline completed with multiple module timeouts (56 completed tests reported); NOT a full regression pass.
- A longer full-suite attempt did not produce a completed report in the execution environment. The historical full-suite stall is NOT resolved or root-caused.
- No real Ollama/OpenCode repair or Windows test has been performed.
- No sandbox for untrusted project execution. Do not claim production readiness.

## Continue development
1. Investigate resource/process starvation and individual module timing; retain strict bounded test runs.
2. Run all tests to completion in a stable environment; fix genuine defects and re-run.
3. Perform real local AI repair, then Windows acceptance.
4. Keep every segment as cumulative source ZIP with tests, handoff and evidence.

## Commands
`python -B -m unittest discover -s tests -p test_regression.py -v`
`python -B -m adm.regression --timeout 90 --output regression-results.json`

## User-facing promise
Every development segment includes the full cumulative source, not just a patch.
