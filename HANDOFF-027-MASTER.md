# ADM-027 — EXTENSIVE CUMULATIVE MASTER HANDOFF

## READ FIRST: operational truth and continuation requirements
This is the full source tree, not a patch. User is a non-programmer and wants a zero-cost, offline-first autonomous Windows application builder that runs unattended after one plain-language instruction. Do not stop after a small feature; prioritize working end-to-end application production and evidence. Every subsequent version must deliver a full cumulative ZIP and an even more detailed self-contained Markdown handoff. Never assert that mock-model tests constitute live Ollama testing or that Linux tests constitute Windows acceptance.

## Current build and evidence, 2026-11-04
- ADM-027 adds `adm/project_lock.py` and six tests in `tests/test_project_lock.py`.
- Exclusive project ownership uses atomic OS `O_CREAT|O_EXCL` file creation, random owner token, PID and timestamp. Held across baseline tests, inference, patching, regression and commit/rollback.
- Second owner fails closed; leftover locks are deliberately not stolen. Only remove a stale lock after confirming no worker still owns the project and reviewing the crash journal.
- Lock cleanup verifies token and refuses to delete a changed lock. Not a substitute for a sandbox; a malicious process with filesystem access can interfere.
- Focused observed results: 6 project-lock tests passed; 6 direct-Ollama adapter tests passed; 5 queued-AI tests passed.
- Full regression attempted but execution was interrupted by the environment timeout. **Not a full-suite pass.**
- Live Ollama model not installed or tested here; no real autonomous code generation demonstrated.
- Windows EXE, installer, 16/32 GB device acceptance, model downloads and operating-system isolation are unverified/incomplete.

## Exact implementation and recovery procedure
`adm.ollama_direct.direct_repair` is now a wrapper that acquires `exclusive_project(root)` before calling `_direct_repair_unlocked`. A lock file `.adm-repair.lock` is created in the project root. This protects against concurrent cooperating ADM repair processes, including distinct evidence folders. The lock persists if a process dies unexpectedly. On restart, a technician or future verified recovery controller must confirm the previous process is dead, check evidence and `repair-journal.json`, and only then clear the stale lock. **Do not automatically delete locks solely based on PID or age** (PID reuse and delayed workers make this unsafe). Source crash journal remains in `adm/repair_recovery.py`.

## Practical development commands
From an extracted archive root, using Python 3.11+:
```powershell
python -B -m unittest discover -s tests -p test_project_lock.py -v
python -B -m unittest discover -s tests -p test_ollama_direct.py -v
python -B -m unittest discover -s tests -p test_queued_ai.py -v
python -B -m unittest discover -s tests -q
python -m adm --help
```
The first three commands are the observed focused gates. Full suite must be run without artificial chat timeouts before release. Tests may spawn processes; do not run unknown third-party projects outside an OS sandbox.

## Priority-ordered next implementation work
1. **Real-model proof:** Install a free local Ollama model on authorized hardware, record model ID/hash, actual output, time/memory, success/failure; run a genuinely unfamiliar broken sample and prove repaired code passes tests without test tampering.
2. **Safe worker recovery:** add durable ownership leases, boot/session identity and reconciliation with `.adm-repair.lock` plus journal; do not blindly remove stale locks or rerun uncertain work.
3. **Independent verifier:** check user requirements, all original tests and adversarial regressions, hashes, artifact startup and functionality, not merely model-reported success.
4. **Sandbox:** use OS isolation for generated code and dependencies; current subprocess tests run with host privileges and are unsafe for untrusted code.
5. **Windows release:** build and smoke-test GUI and background service on Windows 11, include Python runtime, controlled dependency/bootstrap installation and auto-start consent; verify reboot recovery.
6. **Application production:** implement full spec→plan→source→dependencies→build→test→repair→package pipeline for Windows EXE, Android APK and web outputs.
7. **Hardware acceptance:** demonstrate 16 GB and 32 GB model choices and resource-aware concurrency with real metrics.
8. **Cumulative QA:** full regression, fault injection, security audit, real Windows acceptance, ZIP extraction and manifest verification; publish evidence and explicit blockers.

## Security boundaries and limitations
Loopback-only HTTP for Ollama does not prove model authenticity or secure the host. AI-generated source, test scripts and toolchain installers are untrusted. Current code is a prototype for trusted disposable Python projects only. Do not run against production or sensitive work code until sandbox and data governance are established. The lock is cooperative and not a cryptographic authorization boundary. The repair journal is conservative but cannot guarantee all-or-nothing restoration if recovery itself crashes; repeat recovery after checking process ownership.

## Complete current module inventory
### `adm/__init__.py`
**Purpose:** Entry point / internal module
**Top-level interfaces:** No public functions/classes.

### `adm/__main__.py`
**Purpose:** Entry point / internal module
**Top-level interfaces:** No public functions/classes.

### `adm/adaptive.py`
**Purpose:** Resource-aware admission decisions; never changes verification requirements.

All figures are snapshots, not reservations. The caller must re-check immediately
before launching a job. This module does not claim GPU/model capability.
**Top-level interfaces:** Decision, decide, admission_for_build.

### `adm/agent.py`
**Purpose:** ADM-003: guarded OpenCode/Ollama adapter and evidence-backed repair trial.

This is NOT a security sandbox. Only use trusted disposable projects until an OS
isolation mechanism exists. The verification step checks protected source files,
but cannot prevent a coding agent from accessing files outside the project.
**Top-level interfaces:** safe_local_model, validate_project, protected_hashes, source_hashes, atomic_json, test_command, make_prompt, run_agent, agent_repair_proof.

### `adm/agent_cli.py`
**Purpose:** ADM-003 real local OpenCode agent trial CLI.
**Top-level interfaces:** main.

### `adm/cli.py`
**Purpose:** Human-friendly ADM-002 proof command.
**Top-level interfaces:** main.

### `adm/core.py`
**Purpose:** Durable, resource-aware command verification supervisor (stdlib only).
**Top-level interfaces:** resources, mode, Supervisor.

### `adm/daemon.py`
**Purpose:** Persistent unattended trusted-job runner with observable lifecycle state.

This is not an OS sandbox or a Windows startup service. A running daemon
polls the queue, writes atomic heartbeat/status, and accepts graceful stop.
**Top-level interfaces:** _atomic_json, request_stop, read_status, serve, main.

### `adm/desktop.py`
**Purpose:** Small dependency-free desktop control panel for the trusted-job supervisor.

Tkinter is supplied by many Python installations but must be verified on target
Windows. This is a control panel, not an untrusted-code sandbox or AI builder.
**Top-level interfaces:** status_summary, launch_supervisor, main.

### `adm/desktop_entry.py`
**Purpose:** Frozen GUI entrypoint. Must be built and runtime-tested on Windows.
**Top-level interfaces:** No public functions/classes.

### `adm/engine.py`
**Purpose:** ADM-002: bounded, evidence-backed autonomous repair proof (standard library).
**Top-level interfaces:** SafetyError, inside, run_checked, sha256, make_broken_demo, demo_repair, proof.

### `adm/model_probe.py`
**Purpose:** Local-only Ollama model readiness and bounded inference smoke benchmark.

This is not a coding-ability benchmark. Only loopback HTTP is contacted; callers
must explicitly opt in to executing a local inference. No model is downloaded.
**Top-level interfaces:** ProbeResult, _request, installed_models, smoke_test, benchmark_report.

### `adm/ollama_cli.py`
**Purpose:** Run a local Ollama direct-repair trial on a trusted disposable project.
**Top-level interfaces:** main.

### `adm/ollama_direct.py`
**Purpose:** Direct local Ollama repair trial, with deterministic evidence and guarded file edits.

Only for trusted disposable Python projects. This is NOT an OS sandbox.
**Top-level interfaces:** request_patch, apply_patch, _direct_repair_unlocked, direct_repair.

### `adm/pipeline.py`
**Purpose:** ADM-006: durable, fail-closed supervised local agent proof.

Runs the existing agent CLI in a supervised worker process. This is not a
sandbox, an unattended service, or proof of real AI until a live run succeeds.
**Top-level interfaces:** start_pipeline, _existing_job, run_pipeline.

### `adm/pipeline_cli.py`
**Purpose:** Supervised local AI proof: no paid API, no automatic execution of unknown projects.
**Top-level interfaces:** main.

### `adm/preflight.py`
**Purpose:** Read-only diagnostics for local-only Ollama / OpenCode availability.
**Top-level interfaces:** local_preflight.

### `adm/project_lock.py`
**Purpose:** Fail-closed cross-process project ownership for source-changing AI jobs.

An orphaned lock is intentionally not stolen: an operator must verify that the
previous worker is dead before removing it. This is not a security sandbox.
**Top-level interfaces:** exclusive_project.

### `adm/provision.py`
**Purpose:** ADM-008: resumable, dependency-aware local provisioning coordinator.

This is not an unattended installer. Every install/download requires explicit approval.
The journal is durable but is not a security boundary or proof of a working model.
**Top-level interfaces:** _write_atomic, execute_plan.

### `adm/queued_ai.py`
**Purpose:** Queue a bounded local-Ollama repair for the persistent ADM supervisor.

Trusted disposable projects only. This is NOT a sandbox. No paid API calls.
**Top-level interfaces:** enqueue_repair, main.

### `adm/recovery.py`
**Purpose:** Bounded, verified workspace snapshot/restore for disposable repair trials.

Not a sandbox or a replacement for Git. Refuses symlinks and oversized workspaces.
**Top-level interfaces:** inventory, save_snapshot, restore_snapshot.

### `adm/regression.py`
**Purpose:** Isolated, bounded regression runner; does not silently turn timeouts into passes.
**Top-level interfaces:** _terminate_group, _save_report, run_suite, main.

### `adm/release.py`
**Purpose:** Reproducible source release and opt-in Windows executable build planning.

Does not install dependencies or run untrusted code. Windows binaries require
an actual Windows build host and subsequent Windows runtime acceptance tests.
**Top-level interfaces:** source_files, create_source_release, verify_source_release, windows_build_plan, windows_desktop_build_plan, build_windows_executable, main.

### `adm/release_entry.py`
**Purpose:** Frozen Windows entrypoint for ADM supervisor (not a graphical interface).
**Top-level interfaces:** No public functions/classes.

### `adm/repair_recovery.py`
**Purpose:** Crash journal for local-model source replacements.

A repair job must be stopped before recovery; this module does not kill workers.
Recovery is deliberately conservative: restore only when every current file is
identical to either its recorded original or its recorded replacement.
**Top-level interfaces:** _digest, _write_atomic, prepare_journal, recover_journal, finish_journal.

### `adm/setup.py`
**Purpose:** ADM-007: auditable, explicit-consent local dependency provisioning.

No installation, download, or process execution happens on import or in plan().
The installer is deliberately limited to an approved Windows Ollama winget package,
and an Ollama model pull after a local Ollama executable is available.
OpenCode provisioning remains blocked until a verified installation route is added.
**Top-level interfaces:** Step, choose_model, build_plan, execute_step, save_plan.

### `adm/setup_cli.py`
**Purpose:** Read-only setup plan by default; --apply is an explicit opt-in.
**Top-level interfaces:** main.

### `adm/windows_startup.py`
**Purpose:** Opt-in Windows logon launcher. No installation occurs without user action.

Task Scheduler starts a dedicated supervisor at user logon. This is NOT
Windows-service, sandbox, or reboot-recovery acceptance evidence.
**Top-level interfaces:** startup_command, windows_task_command, install, main.

### `adm/worker.py`
**Purpose:** ADM-005 durable single-owner worker supervision for TRUSTED commands.

Not an OS sandbox or a reboot autorun service. Running processes are reclaimed
only after the previous owner is demonstrably gone; never reset live workers.
**Top-level interfaces:** pid_alive, terminate_tree, WorkerSupervisor.

### `adm/worker_cli.py`
**Purpose:** Safe-to-understand CLI for the ADM-005 trusted worker proof.
**Top-level interfaces:** main.

## Complete test-file and test-method inventory
- `tests/test_adaptive.py`: 8 test methods; test_16gb_sequential, test_32gb_parallel, test_model_unload_requires_remeasurement, test_no_memory_cannot_proceed, test_low_disk, test_unknown_resources_fail_closed, test_concurrency_limit, test_invalid_request
- `tests/test_adaptive_worker.py`: 4 test methods; test_denied_is_deferred_without_consuming_attempt, test_deferred_job_runs_after_resources_recover, test_probe_exception_does_not_launch, test_no_admission_keeps_backward_compatibility
- `tests/test_agent.py`: 10 test methods; test_real_test_failure_fake_agent_repair, test_failed_repair_cannot_pass, test_modified_test_is_blocked_even_if_tests_pass, test_local_only_model_guard, test_symlink_project_rejected, test_interrupted_before_agent_can_resume, test_ambiguous_interrupted_agent_is_not_replayed, test_wrong_model_checkpoint_rejected, test_workspace_requirement, test_no_agent_missing_is_clear
- `tests/test_core.py`: 6 test methods; test_success_and_evidence, test_failure_and_bounded_retry, test_recovery_after_restart, test_timeout, test_invalid, test_resource_modes
- `tests/test_daemon.py`: 4 test methods; test_waits_for_new_job_without_reprompt, test_multiple_jobs_processed_without_new_prompt, test_invalid_configuration, test_stop_without_jobs
- `tests/test_daemon_lifecycle.py`: 3 test methods; test_status_unknown_before_start, test_heartbeat_and_graceful_stop, test_max_cycles_stops_and_records
- `tests/test_desktop.py`: 7 test methods; test_missing_status, test_fresh_heartbeat, test_stale_heartbeat, test_future_heartbeat, test_no_duplicate_when_running, test_launch_uses_real_command, test_windows_gui_build_plan
- `tests/test_engine.py`: 9 test methods; test_end_to_end_repair, test_interrupted_resume, test_no_false_success_when_repair_fails, test_no_overwrite, test_cwd_escape_blocked, test_command_timeout, test_safe_path, test_command_argument_validation, test_evidence_not_inside_project
- `tests/test_model_probe.py`: 10 test methods; test_installed, test_success, test_bad_answer, test_missing, test_unfinished, test_connection_error, test_unknown_model_rejected, test_bad_timeout, test_duplicate_models, test_report_not_claiming_coding
- `tests/test_ollama_direct.py`: 6 test methods; test_successful_repair_from_fake_generator, test_failed_patch_restores_source, test_protected_edits_rejected, test_invalid_syntax_rejected_without_edit, test_no_cloud_endpoint, test_http_protocol_fake_local_server
- `tests/test_pipeline.py`: 8 test methods; test_prepare_persists_and_is_idempotent, test_rejects_changed_spec, test_no_paid_models, test_overlapping_state_rejected, test_missing_local_agent_is_not_success, test_worker_exit_alone_never_proves_success, test_protected_file_change_rejects_fake_evidence, test_supervised_agent_process_end_to_end
- `tests/test_project_lock.py`: 6 test methods; test_acquire_release_and_metadata, test_second_owner_refused, test_stale_lock_not_stolen, test_exception_releases_lock, test_modified_lock_not_removed, test_cross_process_exclusion
- `tests/test_provision.py`: 8 test methods; test_consent_required, test_dependency_order, test_failure_stops_before_model_pull, test_resume_verifies_previous_steps, test_resume_rechecks_when_not_verified, test_changed_plan_rejected, test_non_windows_rejected, test_duplicate_step_rejected
- `tests/test_queued_ai.py`: 5 test methods; test_queue_is_durable_and_non_replaying, test_two_jobs_have_separate_evidence, test_invalid_model_rejected, test_invalid_layout_rejected, test_daemon_executes_queued_ai_and_records_real_failure
- `tests/test_recovery.py`: 7 test methods; test_snapshot_reverts_added_changed_deleted, test_damaged_snapshot_is_rejected, test_auto_recover_interrupted_agent_and_complete, test_no_checkpoint_still_refuses_uncertain_state, test_reject_symlink_on_snapshot, test_preflight_reports_unavailable_services_without_crashing, test_preflight_refuses_external_endpoint
- `tests/test_regression.py`: 16 test methods; test_reject_missing_tests, test_reject_invalid_timeout, test_passing_module, test_failure_is_not_success, test_timeout_is_reported, test_timeout_stops_descendant_process, test_partial_progress_is_persisted_before_hanging_module, test_checkpoint_does_not_leave_temporary_files, test_selected_module_only, test_total_budget_marks_unrun_not_pass, test_invalid_total_budget, test_failing_test_keeps_full_diagnostic_log, test_timeout_keeps_partial_output_for_diagnosis, test_resume_skips_only_passed_modules, test_resume_refuses_changed_source, test_resume_requires_checkpoint
- `tests/test_release.py`: 8 test methods; test_complete_package_and_manifest, test_deterministic_package, test_reject_destination_inside_project, test_exclude_sensitive_state_and_cache, test_tamper_detected, test_windows_plan_and_approval, test_symlink_rejected, test_frozen_launcher_uses_exe_directly
- `tests/test_repair_recovery.py`: 5 test methods; test_interrupted_replacement_restores_original, test_unexpected_edit_blocks_recovery, test_project_mismatch_blocks_recovery, test_symlink_swap_blocks_recovery, test_finish_commits_successful_repair
- `tests/test_setup.py`: 14 test methods; test_constrained_machine, test_balanced_machine, test_performance_machine, test_slow_disk_low_space_falls_back, test_windows_plan_no_tools, test_windows_plan_with_winget, test_linux_never_provisions, test_unknown_model_rejected, test_approval_required, test_unknown_commands_rejected, test_unapproved_model_rejected, test_execution_mock, test_missing_executable_blocks, test_timeout_reported
- `tests/test_windows_startup.py`: 4 test methods; test_windows_command_is_argv_not_shell, test_no_automatic_install, test_missing_python_is_rejected, test_existing_stop_request_is_not_discarded
- `tests/test_worker.py`: 11 test methods; test_real_run_and_spooled_logs, test_timeout_and_retry_bound, test_concurrent_claim_unique, test_interrupted_dead_worker_recovered, test_live_pid_blocks_duplicate_start, test_exhausted_after_interruption, test_recent_running_job_is_not_reclaimed, test_ambiguous_starting_is_blocked, test_invalid_input, test_large_output_truncated_in_db, test_timeout_kills_descendant

## Full previous master handoff (preserved verbatim for continuity)

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
