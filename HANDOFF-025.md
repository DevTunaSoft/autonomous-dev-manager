# ADM-025 cumulative development handoff

Base: ADM-024, retained in full with all earlier handoffs and tests.

## Implemented
- `adm/queued_ai.py`: queues a bounded direct-Ollama repair into the persistent WorkerSupervisor; dedicated evidence folder per job, local-only model validation, no worker replay (`max_attempts=1`), no paid APIs.
- `tests/test_queued_ai.py`: five integration tests including actual child-process execution through the daemon and honest failure recording when Ollama is absent.
- README usage instructions.

## Test evidence in this environment
- New queued AI integration tests: 5/5 passed.
- Existing direct Ollama tests: 6/6 passed.
- Existing daemon tests: 4/4 passed.
- Existing worker tests: 11/11 passed.
- Full regression suite: not run in this development segment.
- Live Ollama inference: not run; Ollama/model unavailable.
- Real Windows EXE, installer, sandbox, 16/32 GB hardware tests: not verified.

## Security and reliability limitations
- Trusted disposable Python projects ONLY. No OS sandbox. Python tests can run arbitrary code.
- A crash during model edits can leave partial changes. A job is never blindly replayed; an operator must inspect evidence and source before resubmission.
- No live Ollama validation and no unattended end-to-end production acceptance.

## Next
- Add crash-safe transactional snapshot and recovery to direct Ollama repair.
- Verify actual local inference with a model on Windows.
- Implement OS-level isolation before permitting arbitrary user projects.
- Windows installer/EXE and end-to-end acceptance.
