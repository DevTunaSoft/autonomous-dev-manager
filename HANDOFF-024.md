# ADM-024 development handoff

## Delivered
- New `adm/ollama_direct.py`: direct HTTP POST to loopback Ollama `/api/generate`, structured JSON complete-file replacement for existing top-level Python application files, validation of path/syntax, actual unit-test execution, bounded retry and rollback, and evidence JSON.
- New `adm/ollama_cli.py`: command-line entry point for a trusted disposable Python repair trial.
- New `tests/test_ollama_direct.py`: six focused tests covering repair, rollback, protected files, invalid syntax, loopback-only enforcement, and real HTTP protocol against a fake local server.
- Existing `test_agent.py` 10/10 and `test_pipeline.py` 8/8 pass in this development pass.

## Verification status
- New tests: 6/6 passed.
- Adjacent agent tests: 10/10 passed.
- Pipeline tests: 8/8 passed.
- **No live Ollama model is available in this container. No actual AI inference has been verified.**
- **No OS sandbox exists. Only trusted, disposable projects.**
- Full regression not run in this segment. Windows executable not built.
- In-flight crash recovery for this new direct adapter is NOT implemented. It refuses to reuse existing evidence rather than silently resume; interrupted edits may need manual recovery.

## Next work
1. Integrate direct local inference with persistent worker and crash-safe snapshot/recovery.
2. Test against an actual installed local model, recording inference output and actual repair evidence.
3. Add security isolation for executing generated code; avoid running untrusted code without OS-level sandboxing.
4. Build and verify on Windows, then package an installer and end-user GUI workflow.

## Reproduce focused tests
`python -B -m unittest discover -s tests -p test_ollama_direct.py -v`
`python -B -m unittest discover -s tests -p test_agent.py -v`
`python -B -m unittest discover -s tests -p test_pipeline.py -v`

## Run manual local trial (requires running Ollama and installed model)
`python -m adm.agent_cli create-demo --root demo-project`
`python -m adm.ollama_cli --root demo-project --evidence demo-evidence --model ollama/qwen2.5-coder:3b`

The cumulative package contains all retained source and handoff files from ADM-023 and this version. Do not confuse deterministic/fake-server tests with live model verification.
