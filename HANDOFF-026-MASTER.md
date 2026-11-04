# ADM-026 — MASTER DEVELOPMENT HANDOFF (COMPLETE, CUMULATIVE)

> **Read this before changing any code.** This handoff describes the actual checked-in source, observed testing, known limitations, and next acceptance gates. Do not equate a test double with a real local model or a Linux test with a Windows release.

## 1. Product contract and nonnegotiable goals

The user is not a programmer. They provide a single plain-language application request; the finished Windows 11 manager must autonomously plan, code, acquire approved tools, build, test, diagnose, repair, regression-test, package and deliver an actual application, without repeated user prompts. It must persist across chat boundaries, crashes, reboots and context loss. Only free/local AI is permitted; paid AI APIs are not permitted. Support 16 GB and 32 GB RAM, with resource-aware concurrency. Protect privacy and require authorization for sensitive access. Provide an understandable UI and clear, honest evidence for every claimed success.

After **every** segment deliver a complete cumulative source ZIP, including all previous source, tests, setup instructions, integrity manifest, prior handoffs and this detailed handoff. Do not deliver diffs only.

## 2. Current acceptance status

| Capability | Evidence/status |
|---|---|
| Durable SQLite trusted job execution | Implemented; focused tests exist |
| Unattended daemon and heartbeat/stop | Implemented; Windows real-world operation not verified |
| Windows startup opt-in | Code exists; Windows acceptance not verified |
| Desktop control panel | Prototype exists; no Windows GUI acceptance |
| Local Ollama HTTP repair | Implemented and tested against fake local server; **no real model inference verified** |
| Queued AI repair | Connected to worker; tests use no live Ollama |
| Crash-safe source edit journal | **New in ADM-026**; focused tests pass |
| Source package/build planning | Exists; actual Windows EXE/installer not built or validated |
| OS sandbox for untrusted code | **MISSING: do not execute untrusted projects** |
| Automatic real application production | **NOT DEMONSTRATED** |
| Full regression in this segment | **Not completed** |

## 3. Exact new change in ADM-026

Added `adm/repair_recovery.py`: before applying a model-generated replacement, persist original bytes and hashes plus replacement hashes in `repair-journal.json` using fsync and atomic rename. Recovery checks project identity, target type, symlink absence, and whether current bytes match original or intended replacement; unexpected edits stop recovery. Successful repair deletes journal; unsuccessful repair restores original bytes. On restarting with an existing report and pending journal, restore files and explicitly stop instead of blindly replaying an uncertain attempt. **Only invoke recovery after confirming no other worker is still writing to this project.**

Tested with `python -B -m unittest discover -s tests -p test_repair_recovery.py -v` (5 passed), `test_ollama_direct.py` (6 passed), `test_queued_ai.py` (5 passed). These are focused tests, not an entire release acceptance.

## 4. Architecture and execution flow

Plain-language request → future requirements planner (not complete) → trusted task admission → SQLite supervisor/daemon → local Ollama or OpenCode adapter → bounded source edits → real tests → evidence/report → independent verification (partial) → future Windows/Android/web packaging (not complete).

The local direct-repair path is `adm.queued_ai.enqueue_repair` → `WorkerSupervisor.add` → daemon/worker launches `adm.ollama_cli` → `ollama_direct.direct_repair` → baseline tests → local `/api/generate` → validated replacement JSON → crash journal → file replacements → independent tests → commit journal or rollback. The model request is limited to loopback HTTP; **that alone does not isolate arbitrary test commands or installed plugins**.

## 5. Source inventory: every Python module and public entrypoint

### `adm/__init__.py`
(no module docstring)
**Top-level symbols:** module entrypoint/constants.

### `adm/__main__.py`
(no module docstring)
**Top-level symbols:** module entrypoint/constants.

### `adm/adaptive.py`
Resource-aware admission decisions; never changes verification requirements.
**Top-level symbols:** Decision, decide, admission_for_build.

### `adm/agent.py`
ADM-003: guarded OpenCode/Ollama adapter and evidence-backed repair trial.
**Top-level symbols:** safe_local_model, validate_project, protected_hashes, source_hashes, atomic_json, test_command, make_prompt, run_agent, agent_repair_proof.

### `adm/agent_cli.py`
ADM-003 real local OpenCode agent trial CLI.
**Top-level symbols:** main.

### `adm/cli.py`
Human-friendly ADM-002 proof command.
**Top-level symbols:** main.

### `adm/core.py`
Durable, resource-aware command verification supervisor (stdlib only).
**Top-level symbols:** resources, mode, Supervisor.

### `adm/daemon.py`
Persistent unattended trusted-job runner with observable lifecycle state.
**Top-level symbols:** _atomic_json, request_stop, read_status, serve, main.

### `adm/desktop.py`
Small dependency-free desktop control panel for the trusted-job supervisor.
**Top-level symbols:** status_summary, launch_supervisor, main.

### `adm/desktop_entry.py`
Frozen GUI entrypoint. Must be built and runtime-tested on Windows.
**Top-level symbols:** module entrypoint/constants.

### `adm/engine.py`
ADM-002: bounded, evidence-backed autonomous repair proof (standard library).
**Top-level symbols:** SafetyError, inside, run_checked, sha256, make_broken_demo, demo_repair, proof.

### `adm/model_probe.py`
Local-only Ollama model readiness and bounded inference smoke benchmark.
**Top-level symbols:** ProbeResult, _request, installed_models, smoke_test, benchmark_report.

### `adm/ollama_cli.py`
Run a local Ollama direct-repair trial on a trusted disposable project.
**Top-level symbols:** main.

### `adm/ollama_direct.py`
Direct local Ollama repair trial, with deterministic evidence and guarded file edits.
**Top-level symbols:** request_patch, apply_patch, direct_repair.

### `adm/pipeline.py`
ADM-006: durable, fail-closed supervised local agent proof.
**Top-level symbols:** start_pipeline, _existing_job, run_pipeline.

### `adm/pipeline_cli.py`
Supervised local AI proof: no paid API, no automatic execution of unknown projects.
**Top-level symbols:** main.

### `adm/preflight.py`
Read-only diagnostics for local-only Ollama / OpenCode availability.
**Top-level symbols:** local_preflight.

### `adm/provision.py`
ADM-008: resumable, dependency-aware local provisioning coordinator.
**Top-level symbols:** _write_atomic, execute_plan.

### `adm/queued_ai.py`
Queue a bounded local-Ollama repair for the persistent ADM supervisor.
**Top-level symbols:** enqueue_repair, main.

### `adm/recovery.py`
Bounded, verified workspace snapshot/restore for disposable repair trials.
**Top-level symbols:** inventory, save_snapshot, restore_snapshot.

### `adm/regression.py`
Isolated, bounded regression runner; does not silently turn timeouts into passes.
**Top-level symbols:** _terminate_group, _save_report, run_suite, main.

### `adm/release.py`
Reproducible source release and opt-in Windows executable build planning.
**Top-level symbols:** source_files, create_source_release, verify_source_release, windows_build_plan, windows_desktop_build_plan, build_windows_executable, main.

### `adm/release_entry.py`
Frozen Windows entrypoint for ADM supervisor (not a graphical interface).
**Top-level symbols:** module entrypoint/constants.

### `adm/repair_recovery.py`
Crash journal for local-model source replacements.
**Top-level symbols:** _digest, _write_atomic, prepare_journal, recover_journal, finish_journal.

### `adm/setup.py`
ADM-007: auditable, explicit-consent local dependency provisioning.
**Top-level symbols:** Step, choose_model, build_plan, execute_step, save_plan.

### `adm/setup_cli.py`
Read-only setup plan by default; --apply is an explicit opt-in.
**Top-level symbols:** main.

### `adm/windows_startup.py`
Opt-in Windows logon launcher. No installation occurs without user action.
**Top-level symbols:** startup_command, windows_task_command, install, main.

### `adm/worker.py`
ADM-005 durable single-owner worker supervision for TRUSTED commands.
**Top-level symbols:** pid_alive, terminate_tree, WorkerSupervisor.

### `adm/worker_cli.py`
Safe-to-understand CLI for the ADM-005 trusted worker proof.
**Top-level symbols:** main.

## 6. Test files and coverage map

- `tests/test_adaptive.py` — 8 declared test methods; classes: AdaptiveTests.
- `tests/test_adaptive_worker.py` — 4 declared test methods; classes: AdaptiveWorkerTests.
- `tests/test_agent.py` — 10 declared test methods; classes: AgentProofTests.
- `tests/test_core.py` — 6 declared test methods; classes: SupervisorTests.
- `tests/test_daemon.py` — 4 declared test methods; classes: DaemonTests.
- `tests/test_daemon_lifecycle.py` — 3 declared test methods; classes: DaemonLifecycleTests.
- `tests/test_desktop.py` — 7 declared test methods; classes: DesktopTests, BuildPlanTests.
- `tests/test_engine.py` — 9 declared test methods; classes: EngineTests.
- `tests/test_model_probe.py` — 10 declared test methods; classes: Response, ProbeTests.
- `tests/test_ollama_direct.py` — 6 declared test methods; classes: DirectTests.
- `tests/test_pipeline.py` — 8 declared test methods; classes: PipelineTests, RealProcessIntegrationTests.
- `tests/test_provision.py` — 8 declared test methods; classes: ProvisionTests.
- `tests/test_queued_ai.py` — 5 declared test methods; classes: QueuedAITests.
- `tests/test_recovery.py` — 7 declared test methods; classes: RecoveryTests.
- `tests/test_regression.py` — 16 declared test methods; classes: RegressionRunnerTests, RegressionProcessTreeTests, RegressionCheckpointTests, RegressionBudgetTests, RegressionEvidenceTests, RegressionResumeTests.
- `tests/test_release.py` — 8 declared test methods; classes: ReleaseTests, FrozenStartupTests.
- `tests/test_repair_recovery.py` — 5 declared test methods; classes: RepairRecoveryTests.
- `tests/test_setup.py` — 14 declared test methods; classes: SetupTests.
- `tests/test_windows_startup.py` — 4 declared test methods; classes: StartupTests.
- `tests/test_worker.py` — 11 declared test methods; classes: WorkerTests.

## 7. Reproduction and runbook

On a machine with Python 3.11+ installed, extract ZIP, open a terminal in the extracted root, and run:

```powershell
py -3 -m unittest discover -s tests -p test_repair_recovery.py -v
py -3 -m unittest discover -s tests -p test_ollama_direct.py -v
py -3 -m unittest discover -s tests -p test_queued_ai.py -v
py -3 -m unittest discover -s tests -v
py -3 -m adm.agent_cli preflight
py -3 -m adm.queued_ai --help
py -3 -m adm.daemon --help
py -3 -m adm.desktop --help
```

`--help` availability for individual GUI entrypoints must be checked before treating the examples as supported. Full regression can be time-consuming; use `adm.regression` checkpoint runner where applicable. Do not treat timeouts as passes.

For a real model trial, install Ollama separately following official instructions, download a suitable free coding model, verify `http://127.0.0.1:11434`, and run ONLY against a disposable, trusted Python demo with no secrets or network credentials. Save the actual model identifier, output, test logs, resource use and final source hashes. **No real model was available during ADM-026 development.**

## 8. Security and trust boundaries

- The worker executes trusted commands with the host user’s privileges. No OS-level sandbox, container or Windows restricted token is established.
- AI-generated source and project tests may be malicious; do not run untrusted repositories, downloaded projects or confidential work projects.
- The Ollama direct HTTP endpoint is loopback-only, and the patch editor restricts edits to existing top-level `.py` files; neither restriction makes execution safe.
- Existing OpenCode integration has not been proven to isolate inherited plugins, credentials, environment variables or paid/cloud providers.
- Journal recovery must run only after the original writer has been stopped. It is not a multi-writer lock and does not provide arbitrary crash-atomic multi-file transactions.
- Evidence may include project source, model output and logs; protect storage, redact secrets, and obtain organizational approval before using work data.
- No Windows SmartScreen signing, code-signing, installer integrity or clean-machine security acceptance has been performed.

## 9. Known defects, risks and unverified claims

1. **Real AI not proven:** fake-server/generator tests validate protocol and workflow, not coding ability.
2. **No robust process sandbox:** arbitrary project tests can execute dangerous commands.
3. **No production Windows EXE or installer:** source/build preparation is not a shipped application.
4. **Incomplete full-suite acceptance:** historical full runs have timed out; only focused suites are confirmed this segment.
5. **Multi-writer safety:** current crash journal cannot safely coordinate concurrent repairs on the same project; add per-project OS lock and worker ownership.
6. **Crash windows:** a power loss during rollback can leave journal in place; recovery is idempotent only while current bytes match expected values.
7. **No durable autonomous requirements planner or acceptance authority for arbitrary apps.**
8. **No demonstrated Android SDK/Gradle APK build or arbitrary web app release path.**
9. **Windows reboot/logon and 16 GB/32 GB model performance unverified.**
10. **Direct-repair model JSON replaces complete files and may be constrained for larger projects.**

## 10. Next development sequence (do not stop after planning)

1. Add exclusive per-project repair locking with stale-owner detection and an explicit journal-recovery command; test crash/kill/restart while applying multiple files.
2. Add a real local-model smoke test (Ollama installed) with an unfamiliar broken project, capture failing baseline, model response, real passing tests, source hashes, duration, and CPU/RAM usage.
3. Enforce isolated unprivileged test execution, no secrets, restricted network and filesystem access before allowing arbitrary projects.
4. Integrate repair attempts into a durable task state machine that resumes safely without repeating already-committed side effects.
5. Implement the requirements-to-tests planner, independent verification, regression and packaging evidence gate.
6. Build and test actual Windows EXE and installer in Windows CI/VM; run clean-machine install, startup, shutdown, reboot, uninstall and recovery tests.
7. Add Android APK and web build adapters with real toolchain acceptance and artifact validation.
8. Test 16 GB/32 GB hardware profiles and adaptive model fallback.
9. Run comprehensive regression, fault injection and security audit; reconcile every user requirement to actual test evidence.

## 11. Definition of done

A noncoder installs one Windows application, types a plain-language project request once, and later receives a working independently tested EXE/APK/web artifact plus complete source, reproducible build, logs, requirements traceability and a plain-English report. Recovery after reboot or a crashed model must be demonstrated, not assumed. Security boundaries must be proven. No paid AI API calls. Anything less is a development prototype.

## 12. Previous handoffs and source continuity

Historical `HANDOFF-011.md` through `HANDOFF-025.md` and `HANDOFF.md` are retained in this package alongside the full cumulative `adm/` and `tests/` trees. The older `README.md` is cumulative historical documentation and its opening ADM-001 heading is not the current version; **this document is the authoritative current status**.

## 13. Package verification

The accompanying `ADM-026-manifest.json` contains SHA-256 hashes for each bundled file except itself. Validate hashes after extraction. Do not remove previous source files when continuing; preserve a full cumulative ZIP each segment.
