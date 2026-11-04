# ADM-018 — Complete cumulative engineering handoff

## What changed
- Added checkpoint-based resumable regression testing in `adm/regression.py` (`--resume`).
- Each checkpoint is tied to a SHA-256 fingerprint of the Python source and tests. Changes invalidate old passing evidence.
- Only previously **passed** modules are reused; failures, timeouts, and budget-skipped modules are rerun.
- Added three regression-resume tests in `tests/test_regression.py`.
- The full regression suite **passed: 111 tests across 12 modules**. Evidence: `regression-018.json` and `batch1.log` through `batch4.log`.

## Important qualification
- Full regression was completed in multiple resumable runs in a Linux environment, not in one uninterrupted run. It is not Windows acceptance.
- Real Ollama/OpenCode inference and autonomous repair have **not** been tested.
- Automatic dependency/model installation is not complete.
- Running untrusted projects is unsafe without sandboxing.
- The source fingerprint covers Python files; configuration and non-Python artifacts require additional integrity coverage for release-grade verification.

## Reproduce
From the project root:
```
python -B -m unittest discover -s tests -p test_regression.py -q
python -B -m adm.regression --timeout 35 --max-total-seconds 35 --output regression.json --resume
```
Repeat the second command until the report shows `passed: true`. After source changes, start with a new output file or remove the old checkpoint; stale results will be refused.

## Next milestones
1. Verify actual Ollama/OpenCode model inference and real unfamiliar-code repair.
2. Add protected sandbox and Windows process-tree handling.
3. Complete one-click Windows bootstrap, automatic approved tool/model installation and GUI.
4. Verify startup/reboot recovery and package/install tests on both 16 GB and 32 GB Windows computers.

## Cumulative source policy
This ZIP contains the entire ADM project source and test suite, not only changed files. Historical handoffs are retained.
