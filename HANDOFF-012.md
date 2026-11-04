# ADM-012 Complete Source Handoff

## Scope
Cumulative source from ADM-011 plus a new isolated regression runner and its tests.

## New
- `adm/regression.py`: executes each test module in its own child Python process, enforces per-module deadlines, captures bounded diagnostics, emits JSON evidence, and returns failure if any module fails or times out.
- `tests/test_regression.py`: five tests for success, failure, timeout, invalid timeout, and missing tests.

## Verification in this environment
- New regression runner: 5/5 tests passed.
- Existing model-probe tests: 10/10 passed.
- Attempted complete suite and isolated module suite, but both exceeded the execution budget in this environment. Do NOT claim a passing full regression.
- Previous full suite stalls near `test_worker.WorkerTests.test_real_run_and_spooled_logs`; root cause is NOT yet proven. The isolated runner helps pinpoint modules but is not itself a fix for worker hangs.

## How to run
`python -B -m unittest discover -s tests -p test_regression.py -v`
`python -B -m adm.regression --timeout 90 --output regression-results.json`

## Unfinished / safety
No real local model coding repair has been verified; no Windows installation or EXE; untrusted code is not sandboxed; no automatic one-click toolchain provisioning. Keep using trusted test projects only.

## Next action
Investigate worker test stall under instrumentation, obtain complete regression PASS, then perform live local Ollama/OpenCode test and Windows acceptance.
