# ADM-016 — Complete development handoff

## What changed
- Regression runner now accepts `selected_modules` and `max_total_seconds`.
- CLI adds `--module` (repeatable) and `--max-total-seconds`.
- Overall budget exhaustion is recorded as `not_run_budget` and cannot count as a pass.
- Added three focused tests for selection, budget, and invalid budget.
- Preserved all cumulative source code and prior handoffs from ADM-015.

## Test evidence
- `python -B -m unittest discover -s tests -p test_regression.py -q`: **11 tests passed** (Linux container).
- Bounded full regression: **53 completed tests**, `test_agent.py` timed out, `test_recovery.py` timed out due to remaining global budget; three modules not run. Overall **FAIL / incomplete**. See `regression-016.json` and `regression-016-console.txt`.
- This does not prove a root cause for historical full-suite timeouts; no claim of full regression success.
- No Windows runtime, real Ollama/OpenCode repair, automatic installation, or untrusted-code sandbox has been verified.

## How to continue
1. Run modules independently with generous deadlines, starting with `test_agent.py` and `test_recovery.py`; distinguish slow tests from hangs.
2. Investigate child-process handling and CPU/resource contention; do not weaken tests to pass.
3. Complete a successful full regression, then test actual AI coding and Windows setup.
4. Maintain cumulative source packages and honest verification reports after each segment.

## Commands
`python -B -m unittest discover -s tests -p test_regression.py -q`
`python -B -m adm.regression --module test_agent.py --timeout 90 --output agent-tests.json`
`python -B -m adm.regression --timeout 90 --max-total-seconds 900 --output regression.json`
