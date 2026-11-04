# ADM-011 complete-source handoff

This directory contains the cumulative ADM source, including all prior modules, tests, and documentation, plus `adm/model_probe.py` and `tests/test_model_probe.py`.

## Implemented in this segment
- Loopback-only Ollama installed-model discovery.
- Allowlist-gated local inference smoke test with bounded response and timeout.
- Explicit failure classification and JSON-compatible evidence structure.
- Ten deterministic focused tests passing; eleven worker tests passing independently.

## Not verified
- Live Ollama/OpenCode execution or autonomous AI repair.
- Windows runtime, automatic end-to-end tool installation, self-contained EXE, secure sandbox.
- Full-suite regression: attempted, but execution exceeded allotted time. Do not claim ADM-011 has a clean full regression.

## Next actions
1. Diagnose full-suite hangs under constrained CI and add per-test timeout/isolation without weakening tests.
2. Run real Ollama smoke inference on a Windows host and record evidence.
3. Benchmark actual coding repair ability, then connect model admission to worker supervision.
4. Complete Windows installation and end-to-end runtime testing.

## Run tests
`python -B -m unittest discover -s tests -p test_model_probe.py -v`
`python -B -m unittest discover -s tests -p test_worker.py -v`
`python -B -m unittest discover -s tests -v`

Do not run untrusted source code using the current unsandboxed worker.
