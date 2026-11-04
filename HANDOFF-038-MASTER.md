# ADM-038 — COMPLETE CUMULATIVE TECHNICAL MASTER HANDOFF

## 1. Executive status and nontechnical explanation
ADM is a **development prototype**, not an installed Windows autonomous app builder. This delivery contains cumulative source, tests, previous handoffs, evidence, and a hash inventory. ADM-038 specifically prevents a test runner from incorrectly accepting a Python test module that discovers zero tests, and rejects nonexistent explicitly selected test modules. No paid AI API is needed. A real coding model, Windows packaging, and an OS-enforced sandbox remain unverified.

## 2. Binding product contract
The owner supplies a plain-language application specification once. The finished product must autonomously plan, implement, download/manage free local models with appropriate authorization, install build tools, run tests, diagnose and fix errors, resume across failures and reboots, package actual deliverables (EXE/APK/web), and explain genuine blockers without requiring the owner to code or repeatedly issue prompts. It must be a single approachable Windows 11 application suitable for 16 GB and 32 GB PCs. Default inference must be local and incur no paid API charges. No arbitrary AI-generated code may be run on the owner's everyday host without real OS-enforced isolation. Every development segment must deliver a complete cumulative ZIP plus a self-contained, extensive Markdown handoff. Test evidence must distinguish mocks from real models, Linux from Windows, and focused tests from complete regression.

## 3. ADM-038 implementation: root cause, code, and rationale
Previous regression.py accepted a test subprocess's exit code zero as success even when it discovered zero tests. That creates false evidence: no assertion was executed. In addition, a caller requesting a misspelled selected module could accidentally run a subset without detecting the missing requested module. In `adm/regression.py`, after parsing unittest's `Ran N tests` summary, status is now `no_tests` when N=0, whether unittest exits zero or nonzero, provided the summary is present. This is deliberately a failure status; `report.passed` stays false. The selected-module filter validates every requested basename against the actual discovered test modules and raises `ValueError` for unknown names. An initial implementation only checked status `passed`, but Python unittest returned failure for zero tests in the actual test fixture. The guard was corrected and retested. These changes are about test-evidence integrity, not AI inference or execution security.

## 4. New acceptance tests and observed evidence
`tests/test_regression_guards.py` tests (1) zero-test module is not passed, (2) unknown module selection raises an error, (3) a genuine one-test module still passes. Executed `python -B -m unittest tests.test_regression_guards tests.test_regression -q`: **19 tests passed**, about 17.2 seconds, Linux. First run failed 1/19, fixed the actual defect, and second run passed 19/19. A bounded full regression was attempted with per-module 7-second timeout and 65-second total budget, but the hosting tool terminated the invocation before it completed. The on-disk checkpoint captured 9 passing modules and a tenth (`test_engine.py`) in progress. **Do not interpret this as a full regression pass or as proof the tenth passed.** See `regression-038.json`, `regression-038.log`, and individual logs. Earlier ADM-037 full regression also timed out. A full clean regression remains a release blocker.

## 5. Exact reproduction commands
From extracted archive root, with Python 3.10+:
```sh
python -B -m unittest tests.test_regression_guards tests.test_regression -q
python -B -m adm.regression --root . --timeout 90 --output regression-full.json
```
The full suite may take a long time; run only in a disposable test environment. The test runner is NOT a sandbox. For resumable runs use `--resume --output regression-full.json` **only if source is unchanged**; it rejects stale fingerprints. A stopped run may contain a `running` field, which is not a completed test.

## 6. File inventory and module responsibilities
The following is an exact inventory of source modules in this release. For detailed behavior inspect the files and historical handoffs; descriptions are derived from module names and should not be treated as proof of feature completeness.
- `adm/__init__.py`
- `adm/__main__.py`
- `adm/acceptance.py`
- `adm/adaptive.py`
- `adm/agent.py`
- `adm/agent_cli.py`
- `adm/ai_status.py`
- `adm/cli.py`
- `adm/core.py`
- `adm/daemon.py`
- `adm/desktop.py`
- `adm/desktop_entry.py`
- `adm/engine.py`
- `adm/live_acceptance.py`
- `adm/model_probe.py`
- `adm/model_selection.py`
- `adm/ollama_cli.py`
- `adm/ollama_direct.py`
- `adm/ollama_health.py`
- `adm/pipeline.py`
- `adm/pipeline_cli.py`
- `adm/preflight.py`
- `adm/project_lock.py`
- `adm/provision.py`
- `adm/queued_ai.py`
- `adm/recovery.py`
- `adm/regression.py`
- `adm/release.py`
- `adm/release_entry.py`
- `adm/repair_recovery.py`
- `adm/setup.py`
- `adm/setup_cli.py`
- `adm/windows_startup.py`
- `adm/worker.py`
- `adm/worker_cli.py`

## 7. Test module inventory
- `tests/test_acceptance.py`
- `tests/test_adaptive.py`
- `tests/test_adaptive_worker.py`
- `tests/test_agent.py`
- `tests/test_ai_inspection.py`
- `tests/test_auto_queue.py`
- `tests/test_core.py`
- `tests/test_daemon.py`
- `tests/test_daemon_lifecycle.py`
- `tests/test_desktop.py`
- `tests/test_engine.py`
- `tests/test_independent_retest.py`
- `tests/test_live_acceptance.py`
- `tests/test_local_transport_security.py`
- `tests/test_model_probe.py`
- `tests/test_model_selection.py`
- `tests/test_ollama_direct.py`
- `tests/test_ollama_health.py`
- `tests/test_pipeline.py`
- `tests/test_process_tree.py`
- `tests/test_project_lock.py`
- `tests/test_provision.py`
- `tests/test_queued_ai.py`
- `tests/test_recovery.py`
- `tests/test_regression.py`
- `tests/test_regression_guards.py`
- `tests/test_release.py`
- `tests/test_repair_commit.py`
- `tests/test_repair_recovery.py`
- `tests/test_setup.py`
- `tests/test_windows_startup.py`
- `tests/test_worker.py`

## 8. Architecture and operational flow
At a high level: desktop/CLI entry points feed durable supervisor/queue records; a worker and daemon coordinate tasks; local Ollama health/model-selection checks select an eligible installed model; direct repair uses a local HTTP endpoint, guarded file replacement and a recovery journal; test execution returns actual exit codes and evidence; independent verification and rollback are used before a repair is accepted. The project contains demonstration and prototype paths rather than a proven arbitrary-specification-to-finished-application workflow. SQLite WAL and checkpoint files provide partial durability; they do not replace OS isolation, transactionally safe packaging, or comprehensive recovery validation.

## 9. Security boundaries and limitations
- **Critical:** AI-modified programs/tests run with host permissions; do not use on a host containing sensitive data. Process groups and Windows taskkill are cleanup mechanisms, not sandboxing. Implement a VM/container/restricted-token boundary with filesystem and network controls before general use.
- Local Ollama loopback HTTP uses proxy avoidance and redirect refusal, but actual model quality, model installation, offline lifecycle, and Windows compatibility have not been demonstrated.
- File allowlists, hashes, and recovery journals are defense-in-depth, not a substitute for OS-enforced isolation.
- Regression evidence is bounded and checkpointed; no completed full-suite pass for this version.
- Windows Job Objects, Windows installer, real EXE, Android APK, unattended 16/32 GB runtime and arbitrary spec-to-build acceptance are unverified.
- Review archive contents before sharing externally. Do not bundle API keys, secrets, user data, or proprietary work projects.

## 10. Build, setup, and recovery
Extract the entire ZIP to a new disposable folder. Python 3.10+ is needed for portable tests; use `python -m adm --help` or inspect `README.md` for supported prototype commands. A local Ollama service is optional for non-AI tests, but required for genuine AI acceptance. Never enable arbitrary untrusted generated-code execution on the normal host. Inspect persisted queue state, recovery journal, and evidence reports before retrying interrupted repair jobs. Do not manually declare a partially completed job successful. On source changes, rerun all affected tests and invalidate stale regression checkpoints.

## 11. Precise next engineering steps, in priority order
1. Build an OS-enforced isolated runner with explicit writable mounts, denied host secrets, restricted network, memory/time/disk quotas, and kill-on-close process tree semantics; validate on Windows 11 in a disposable VM.
2. Investigate full regression stalls module-by-module using checkpoint and saved logs, fix root causes, rerun complete suite without truncation and preserve exact evidence.
3. Perform real local-model inference on 16 GB and 32 GB Windows machines with measured RAM/latency, and show unfamiliar defects repaired with independent tests (not fake HTTP responses).
4. Implement a durable specification-to-plan-to-code-to-build orchestration with bounded self-repair loops, dependency approval policies, crash/reboot recovery, and accessible single-app UI.
5. Produce and test a truly standalone Windows EXE/installer and representative Android APK/web app artifacts in supported build environments.
6. Reconcile the full user requirement ledger against code, independent acceptance tests, security threat model, and packaging evidence before claiming production readiness.

## 12. What is needed from the user?
**Nothing for continued portable source development.** For actual Windows/model/installer acceptance, an authorized disposable Windows 11 VM or test PC with sufficient RAM, Ollama and a downloaded local coding model will eventually be needed. The user is not required to write code, pay AI API fees, or switch between multiple apps. If such a test machine is unavailable, explicitly mark Windows and live-model acceptance as blocked; do not invent success.

## 13. Cumulative history and continuity
The previous ADM-037 master handoff is preserved **verbatim below**, and all older handoff documents remain separately included. Newer status statements above supersede historical progress claims. Each module and test is included as actual source, not just a patch.

---

# ADM-037 — Comprehensive cumulative master handoff

## Release identity and truthful verification
Version ADM-037, cumulative continuation of ADM-036. This is source code for a prototype, **not a Windows production release**. The only new behavior is reliable termination of spawned test process groups on timeout. The current environment is Linux; Windows `taskkill /T /F` has not been exercised. Local AI inference has not been demonstrated; operating-system sandboxing is still absent.

## What changed and why
`adm/engine.py` `run_checked` previously used `subprocess.run(timeout=...)`, which can terminate the immediate process while leaving grandchildren running. An autonomous repair worker must not leave an indefinite test workload after timeout. ADM-037 uses `subprocess.Popen` with `start_new_session=True` on POSIX and `CREATE_NEW_PROCESS_GROUP` on Windows. On timeout POSIX sends SIGKILL to the process group; Windows requests `taskkill /PID <pid> /T /F`. It then reaps the parent and returns exit code 124. No shell invocation is used. Normal success output and launch failures preserve the existing result structure.

## Files and tests added or changed
- `adm/engine.py`: process group ownership and timeout cleanup. Windows behavior requires actual Windows acceptance testing.
- `tests/test_process_tree.py`: 3 tests covering success, missing executable, and a child that would otherwise write a marker after parent timeout.
- `regression-037.log`: output from attempted full-suite run; full regression timed out before completion and is NOT counted as passed.
- `HANDOFF-037-MASTER.md`: this complete handoff with historical documentation appended.
- `ADM-037-manifest.json`: SHA-256 file inventory (excluding itself).

## Observed tests and limitations
Focused `python -m unittest tests.test_process_tree tests.test_engine -v`: **12 tests, 12 passed**, about 8.45 seconds, on Linux. The child-process test waits beyond the child's intended write time and confirms no marker appears. A full test discovery was attempted with an approximately 105-second timeout and did not finish; no full-suite pass claim. Other tests were not run in this development segment. No Windows runner, no Ollama, no real model, no Android build, no EXE.

## Threat model and unresolved security
Process-group termination is NOT sandboxing. An untrusted child could escape the process group, access user files or credentials, use the network, or create persistent jobs. Never execute AI-generated tests on a host containing sensitive data until operating-system isolation and capability restrictions have been implemented and verified. Windows `taskkill` failure may leave descendants; implement Windows Job Objects with kill-on-close and test under a clean VM. `communicate()` captures output in memory; introduce bounded streaming output and disk quotas before arbitrary project acceptance.

## Reproduction
From extracted project root with Python 3.10+:
```
python -m unittest tests.test_process_tree tests.test_engine -v
python -m unittest discover -s tests -p 'test_*.py' -q
```
The second command may take much longer or hang on known integration tests; use a supervised test runner and report its actual result. Use disposable workspaces only.

## Priority next steps
1. Implement Windows Job Objects for robust kill-on-close child-tree management, including forced cancellation, crash, and reboot tests.
2. Implement an OS-enforced isolated execution boundary (VM/container or restricted token and filesystem/network policies) before arbitrary AI-generated test execution.
3. Run real Ollama coding inference in the isolated environment and verify unfamiliar defects with independent tests.
4. Implement spec-to-application planning, durable multi-stage autonomous workflow, actual Windows EXE and Android APK build, then comprehensive regression.
5. Reconcile every user requirement against executable acceptance evidence; never claim a finished product without it.

## What is needed from the user?
**Nothing for continued portable development.** For real Windows and model acceptance, access to an authorized disposable Windows 11 VM/PC with Ollama and a local model is eventually required. The user does not need to write code or buy API tokens. Do not ask for this prematurely.

## Cumulative documentation continuity
The entire previous ADM-036 master handoff follows verbatim. Older handoffs, modules, tests, and manifests remain in the package. The current section overrides historical status statements where newer test evidence differs.

---

# ADM-036 — COMPLETE CUMULATIVE MASTER HANDOFF

**Project:** Autonomous Development Manager (ADM)  
**Version:** 036  
**Date:** 2026-11-04  
**Delivery:** complete cumulative source, all retained historical handoffs, test code, manifest, this standalone handoff.  
**Acceptance status:** DEVELOPMENT PROTOTYPE; not Windows-production ready.  

## A. Purpose and binding requirements

The owner is not a programmer. ADM is intended to accept plain-language software specifications and autonomously plan, implement, install dependencies with appropriate consent, build, run, diagnose, repair, independently test, regression-test, recover after interruption, and deliver actual application artifacts (Windows EXEs, Android APKs, and web apps as applicable). The target is one integrated Windows 11 desktop application, no app switching or repeated user prompts. Free/local AI only; no paid API charges. It must adapt to 16 GB and 32 GB computers. Source and inference must stay local by default. The owner requires full cumulative source ZIP and increasingly detailed handoff after EVERY segment. Never claim tests or platform support without evidence. Real AI-generated code must not run unsandboxed on the owner's normal machine.

## B. What changed in ADM-036

**Defect:** `adm/ollama_direct.py` wrote `verified_direct_repair` to the evidence JSON *before* clearing `repair-journal.json`. A process crash in that interval could leave a successful report alongside a journal which a subsequent recovery would roll back. This was an inconsistent commit boundary.

**Fix:** after two independent successful test processes and unchanged protected files, persist an intermediate `verification_passed_commit_pending` status, call `finish_journal(evidence)`, and only then persist `verified_direct_repair`. If clearing the journal raises an `OSError`, the existing exception handling records a failed attempt and the `finally` recovery restores original source. This is a narrow fix; it is NOT a transactional filesystem and cannot guarantee crash durability across all storage failures.

**New file:** `tests/test_repair_commit.py` has fault-injection tests for successful commit ordering and journal-cleanup failure. The first observes the filesystem when the verified status is written and requires the journal to be absent. The second simulates an `OSError` and requires rollback, no journal, and no persisted verified status.

**Evidence actually executed in this segment:**

| Test command | Result | Tests |
|---|---|---:|
| `python -B -m unittest discover -s tests -p test_repair_commit.py -v` | PASS | 2 |
| `python -B -m unittest discover -s tests -p test_ollama_direct.py -q` | PASS | 6 |
| `python -B -m unittest discover -s tests -p test_queued_ai.py -q` | PASS | 5 |
| `python -B -m unittest discover -s tests -p test_repair_recovery.py -q` | PASS | 5 |
| `python -B -m unittest discover -s tests -p test_model_selection.py -q` | PASS | 7 |

**Total focused executions:** 25 passing tests. This is not a claim that the full suite passed. No live Ollama model was available in this execution environment; no real-model acceptance test, Windows EXE build, or Windows runtime test was performed.

## C. Known hazards and blocking gaps

1. **No proven OS sandbox.** The repair engine runs AI-modified Python code using ordinary host subprocess permissions. Only use disposable, isolated virtual machines for untrusted AI outputs. Path validation and protected file hashing are not an OS security boundary.
2. **No demonstrated genuine model reasoning.** Fake HTTP servers and simulated generators prove protocol/control-flow only. Live acceptance remains pending.
3. **No actual Windows installer or Windows 11 end-to-end verification.** Desktop and packaging modules exist but are not a validated turnkey release.
4. **No complete autonomous app generation acceptance.** A controlled repair demonstration is not the full natural-language-to-delivered-application workflow.
5. **Commit still not fully atomic.** If writing final verified evidence fails after clearing the journal, the source may remain changed with a pending report. A future version should implement explicit recoverable commit states, checksums and durable reconciliation.
6. **Full suite not rerun in ADM-036.** Previous results are historical evidence only, not proof of this version's entire regression.
7. **Local model resource sizing is heuristic.** Verify on real 16 GB and 32 GB Windows machines.
8. **Network and toolchain security require independent threat modeling**, including subprocess permissions, symlink race conditions, package supply-chain risk, logs, secrets, and network egress controls.

## D. Practical continuation instructions

1. Extract the ZIP into a new folder. Never edit or run directly inside the ZIP.
2. Read this file first, then `README.md`, `HANDOFF-035-MASTER.md`, and source modules listed below.
3. In an isolated development environment, run `python -B -m unittest discover -s tests -q` with adequate time and save exact output. If it times out, use `adm.regression`'s checkpointed runner and retain per-module logs.
4. Prioritize an OS-isolated execution backend (Windows Sandbox/Hyper-V VM or equivalently isolated guest). Deny execution if isolation is absent; verify the isolation boundary with adversarial tests before enabling generated code.
5. Run real local Ollama inference inside the isolated guest using the explicit live-acceptance flow. Capture model ID/hash, test logs, retries, and independently validated repair outcomes. Do not confuse simulated tests with real inference.
6. Build and run a real Windows EXE and installer on Windows 11, test clean install, startup, background job recovery, uninstall, reboot, permissions and failure paths on both memory configurations.
7. Connect natural-language intake to planning, project creation, dependency setup, isolated build/test/repair, verified packaging, and evidence-backed delivery. Include automatic bounded retries and plain-English blocker reporting.
8. After each subsequent segment: rerun affected tests and regression, preserve full cumulative source, update the handoff with actual evidence, hash every included file, and verify ZIP integrity.

## E. Source module inventory

- `adm/__init__.py` — from .core import Supervisor, resources, mode
- `adm/__main__.py` — import argparse, json, time
- `adm/acceptance.py` — """Offline end-to-end acceptance: real HTTP transport and subprocess tests, fake AI.
- `adm/adaptive.py` — """Resource-aware admission decisions; never changes verification requirements.
- `adm/agent.py` — """ADM-003: guarded OpenCode/Ollama adapter and evidence-backed repair trial.
- `adm/agent_cli.py` — """ADM-003 real local OpenCode agent trial CLI."""
- `adm/ai_status.py` — """Read-only CLI for reconciling a queued AI repair with its evidence."""
- `adm/cli.py` — """Human-friendly ADM-002 proof command."""
- `adm/core.py` — """Durable, resource-aware command verification supervisor (stdlib only)."""
- `adm/daemon.py` — """Persistent unattended trusted-job runner with observable lifecycle state.
- `adm/desktop.py` — """Small dependency-free desktop control panel for the trusted-job supervisor.
- `adm/desktop_entry.py` — """Frozen GUI entrypoint. Must be built and runtime-tested on Windows."""
- `adm/engine.py` — """ADM-002: bounded, evidence-backed autonomous repair proof (standard library)."""
- `adm/live_acceptance.py` — """Opt-in real Ollama acceptance on a fresh, disposable fixture.
- `adm/model_probe.py` — """Local-only Ollama model readiness and bounded inference smoke benchmark.
- `adm/model_selection.py` — """Deterministic offline model selection from Ollama's locally installed inventory.
- `adm/ollama_cli.py` — """Run a local Ollama direct-repair trial on a trusted disposable project."""
- `adm/ollama_direct.py` — """Direct local Ollama repair trial, with deterministic evidence and guarded file edits.
- `adm/ollama_health.py` — """Read-only, loopback-only Ollama health and installed-model inspection.
- `adm/pipeline.py` — """ADM-006: durable, fail-closed supervised local agent proof.
- `adm/pipeline_cli.py` — """Supervised local AI proof: no paid API, no automatic execution of unknown projects."""
- `adm/preflight.py` — """Read-only diagnostics for local-only Ollama / OpenCode availability."""
- `adm/project_lock.py` — """Fail-closed cross-process project ownership for source-changing AI jobs.
- `adm/provision.py` — """ADM-008: resumable, dependency-aware local provisioning coordinator.
- `adm/queued_ai.py` — """Queue a bounded local-Ollama repair for the persistent ADM supervisor.
- `adm/recovery.py` — """Bounded, verified workspace snapshot/restore for disposable repair trials.
- `adm/regression.py` — """Isolated, bounded regression runner; does not silently turn timeouts into passes."""
- `adm/release.py` — """Reproducible source release and opt-in Windows executable build planning.
- `adm/release_entry.py` — """Frozen Windows entrypoint for ADM supervisor (not a graphical interface)."""
- `adm/repair_recovery.py` — """Crash journal for local-model source replacements.
- `adm/setup.py` — """ADM-007: auditable, explicit-consent local dependency provisioning.
- `adm/setup_cli.py` — """Read-only setup plan by default; --apply is an explicit opt-in."""
- `adm/windows_startup.py` — """Opt-in Windows logon launcher. No installation occurs without user action.
- `adm/worker.py` — """ADM-005 durable single-owner worker supervision for TRUSTED commands.
- `adm/worker_cli.py` — """Safe-to-understand CLI for the ADM-005 trusted worker proof."""

## F. Test module inventory

- `tests/test_acceptance.py`
- `tests/test_adaptive.py`
- `tests/test_adaptive_worker.py`
- `tests/test_agent.py`
- `tests/test_ai_inspection.py`
- `tests/test_auto_queue.py`
- `tests/test_core.py`
- `tests/test_daemon.py`
- `tests/test_daemon_lifecycle.py`
- `tests/test_desktop.py`
- `tests/test_engine.py`
- `tests/test_independent_retest.py`
- `tests/test_live_acceptance.py`
- `tests/test_local_transport_security.py`
- `tests/test_model_probe.py`
- `tests/test_model_selection.py`
- `tests/test_ollama_direct.py`
- `tests/test_ollama_health.py`
- `tests/test_pipeline.py`
- `tests/test_project_lock.py`
- `tests/test_provision.py`
- `tests/test_queued_ai.py`
- `tests/test_recovery.py`
- `tests/test_regression.py`
- `tests/test_release.py`
- `tests/test_repair_commit.py`
- `tests/test_repair_recovery.py`
- `tests/test_setup.py`
- `tests/test_windows_startup.py`
- `tests/test_worker.py`

## G. Archive verification and provenance

`ADM-036-manifest.json` records SHA-256 hashes for every shipped file other than the manifest itself. Recompute each hash after extraction; any mismatch means the extracted package should not be trusted. ZIP CRC validation confirms archive integrity but is not an authenticity signature. No code signing has been performed. Historical handoffs are preserved for continuity; older claims must not override the latest evidence and limitations.

## H. User input and blockers

**No input needed for continued portable code development.** To verify genuine local AI and Windows packaging later, an isolated Windows 11 test machine/VM, locally installed Ollama and a free coding model will be needed. The user should not need to code or pay API fees. If administrative privileges or Windows features are required, obtain clear permission at installation time rather than bypassing system controls.

---

# COMPLETE PREVIOUS MASTER HANDOFF (ADM-035)

The following is preserved verbatim to prevent historical loss. Current ADM-036 findings above take precedence on conflicts.

# ADM-035 MASTER ENGINEERING HANDOFF — CUMULATIVE SOURCE

## Read this first — product goal and truthful acceptance state
The Autonomous Development Manager (ADM) is intended as a single turnkey Windows 11 desktop application for a nonprogrammer. The user gives plain-English application requirements once. ADM must independently plan, create, build, test, diagnose, repair, regression-test, package, and deliver actual working apps. It must use free/local AI, no paid APIs, preserve recoverable state, and support both 16 GiB and 32 GiB hardware. Every development segment must deliver all cumulative source code, tests, integrity manifest, and an exhaustive self-contained handoff. Never represent mocked AI inference, a passing unit test, or a successful worker exit code as a real autonomous coding success.

**Current version:** ADM-035. **Status:** prototype. **Not a finished Windows installer or production-safe agent.** Real Ollama inference is not demonstrated; Windows packaging is not tested; OS-level sandbox is absent. These are release blockers. A model name being installed or selected is not proof it can run or solve problems.

## Changes in ADM-035
1. `adm/queued_ai.py`: `enqueue_repair(..., model='auto', ram_gib=..., installed_models=...)` now resolves a safe, locally installed coding model before enqueueing; explicit `ollama/...` model names retain previous behavior. Programmatic callers retain explicit default to preserve compatibility; CLI defaults to `auto`.
2. `physical_ram_gib()`: obtains physical memory through `GlobalMemoryStatusEx` on Windows or `sysconf` on POSIX. Fails closed when unknown. This is physical capacity only; free memory, actual context length, model load and performance are not verified.
3. CLI: `python -m adm.queued_ai --state ... --root ... --evidence ... --model auto` chooses an installed local model, without downloading or accessing paid services. `--ram-gib` is a diagnostic/testing override.
4. Queued job record contains the exact resolved `ollama/...` model, not `auto`; the result includes selection evidence and `inference_verified: false`.
5. New `tests/test_auto_queue.py` covers 16/32 GiB choices, persistence, absent models, health inventory usage, explicit-model compatibility, unsafe names, and physical RAM detection.

## Exact commands — development and testing
From the extracted archive root with Python 3.10+ available:

```sh
python -B -m unittest discover -s tests -p 'test_auto_queue.py' -v
python -B -m unittest discover -s tests -p 'test_queued_ai.py' -v
python -B -m unittest discover -s tests -p 'test_model_selection.py' -v
python -B -m unittest discover -s tests -q
python -B -m adm.ollama_health
python -B -m adm.model_selection --ram-gib 16
python -B -m adm.queued_ai --state ./state --root ./DISPOSABLE_PROJECT --evidence ./evidence --model auto
```

**Safety:** Do NOT run AI-generated code against private or valuable projects or on the ordinary host until a verified OS sandbox exists. Use an isolated disposable VM. Running tests may execute arbitrary project code. The sample command requires an existing disposable project with `requirements.json`, Python source, and top-level `test_*.py`.

## ADM-035 test evidence and scope
- `test_auto_queue.py`: 7/7 passed in this environment.
- `test_queued_ai.py`: 5/5 passed in this environment (includes expected no-Ollama failure).
- `test_model_selection.py`: 7/7 passed in this environment.
- Total targeted: 19/19 passed. Full-suite regression **not run this version**; no claim of full-suite success.
- These are mocked/structural tests and failure-path demonstrations, NOT live AI inference, Windows acceptance, or OS sandbox proof.

## Security and threat boundaries
- `inspect_ollama` requires explicit `127.0.0.1` HTTP endpoint, blocks redirects and proxies, and checks response size.
- Selection only uses locally installed models, requires a parseable model size and a conservative RAM tier. Size-name heuristics may be inaccurate; measure real memory before inference.
- Localhost alone does not guarantee all model processes are offline; verify Ollama runtime configuration, firewall rules and dependencies in a VM.
- Model-generated code and tests can read, modify or exfiltrate host files absent OS isolation. Existing project locks, symlink rejection, snapshots and rollback are NOT security boundaries.
- Worker retries remain at 1 for AI repair jobs to avoid blind replay after interruption. Reconcile recovery journals before any retry.
- Never silently download a model, purchase credits, call a paid API, or mark an unverified repair as complete.

## Architecture and data flow
User request → future GUI/planner → SQLite-backed supervisor → queued AI repair → Ollama health/model selection → local Ollama adapter → bounded proposed edits → protected-file checks → independent repeated tests → repair evidence and recovery journal → worker/result reconciliation → future artifact packaging. The GUI, installer, autonomous planning and sandbox are incomplete. State, project, and evidence directories must be separate. Job-specific evidence directories are unique. Recovery is conservative and must not overwrite third-party edits.

## Module inventory — current source tree
- `adm/__init__.py` — from .core import Supervisor, resources, mode
- `adm/__main__.py` — import argparse, json, time
- `adm/acceptance.py` — """Offline end-to-end acceptance: real HTTP transport and subprocess tests, fake AI.
- `adm/adaptive.py` — """Resource-aware admission decisions; never changes verification requirements.
- `adm/agent.py` — """ADM-003: guarded OpenCode/Ollama adapter and evidence-backed repair trial.
- `adm/agent_cli.py` — """ADM-003 real local OpenCode agent trial CLI."""
- `adm/ai_status.py` — """Read-only CLI for reconciling a queued AI repair with its evidence."""
- `adm/cli.py` — """Human-friendly ADM-002 proof command."""
- `adm/core.py` — """Durable, resource-aware command verification supervisor (stdlib only)."""
- `adm/daemon.py` — """Persistent unattended trusted-job runner with observable lifecycle state.
- `adm/desktop.py` — """Small dependency-free desktop control panel for the trusted-job supervisor.
- `adm/desktop_entry.py` — """Frozen GUI entrypoint. Must be built and runtime-tested on Windows."""
- `adm/engine.py` — """ADM-002: bounded, evidence-backed autonomous repair proof (standard library)."""
- `adm/live_acceptance.py` — """Opt-in real Ollama acceptance on a fresh, disposable fixture.
- `adm/model_probe.py` — """Local-only Ollama model readiness and bounded inference smoke benchmark.
- `adm/model_selection.py` — """Deterministic offline model selection from Ollama's locally installed inventory.
- `adm/ollama_cli.py` — """Run a local Ollama direct-repair trial on a trusted disposable project."""
- `adm/ollama_direct.py` — """Direct local Ollama repair trial, with deterministic evidence and guarded file edits.
- `adm/ollama_health.py` — """Read-only, loopback-only Ollama health and installed-model inspection.
- `adm/pipeline.py` — """ADM-006: durable, fail-closed supervised local agent proof.
- `adm/pipeline_cli.py` — """Supervised local AI proof: no paid API, no automatic execution of unknown projects."""
- `adm/preflight.py` — """Read-only diagnostics for local-only Ollama / OpenCode availability."""
- `adm/project_lock.py` — """Fail-closed cross-process project ownership for source-changing AI jobs.
- `adm/provision.py` — """ADM-008: resumable, dependency-aware local provisioning coordinator.
- `adm/queued_ai.py` — """Queue a bounded local-Ollama repair for the persistent ADM supervisor.
- `adm/recovery.py` — """Bounded, verified workspace snapshot/restore for disposable repair trials.
- `adm/regression.py` — """Isolated, bounded regression runner; does not silently turn timeouts into passes."""
- `adm/release.py` — """Reproducible source release and opt-in Windows executable build planning.
- `adm/release_entry.py` — """Frozen Windows entrypoint for ADM supervisor (not a graphical interface)."""
- `adm/repair_recovery.py` — """Crash journal for local-model source replacements.
- `adm/setup.py` — """ADM-007: auditable, explicit-consent local dependency provisioning.
- `adm/setup_cli.py` — """Read-only setup plan by default; --apply is an explicit opt-in."""
- `adm/windows_startup.py` — """Opt-in Windows logon launcher. No installation occurs without user action.
- `adm/worker.py` — """ADM-005 durable single-owner worker supervision for TRUSTED commands.
- `adm/worker_cli.py` — """Safe-to-understand CLI for the ADM-005 trusted worker proof."""

## Test inventory — current source tree
- `tests/test_acceptance.py`
- `tests/test_adaptive.py`
- `tests/test_adaptive_worker.py`
- `tests/test_agent.py`
- `tests/test_ai_inspection.py`
- `tests/test_auto_queue.py`
- `tests/test_core.py`
- `tests/test_daemon.py`
- `tests/test_daemon_lifecycle.py`
- `tests/test_desktop.py`
- `tests/test_engine.py`
- `tests/test_independent_retest.py`
- `tests/test_live_acceptance.py`
- `tests/test_local_transport_security.py`
- `tests/test_model_probe.py`
- `tests/test_model_selection.py`
- `tests/test_ollama_direct.py`
- `tests/test_ollama_health.py`
- `tests/test_pipeline.py`
- `tests/test_project_lock.py`
- `tests/test_provision.py`
- `tests/test_queued_ai.py`
- `tests/test_recovery.py`
- `tests/test_regression.py`
- `tests/test_release.py`
- `tests/test_repair_recovery.py`
- `tests/test_setup.py`
- `tests/test_windows_startup.py`
- `tests/test_worker.py`

## Release blockers and prioritized next work
1. **OS sandbox first:** isolated Windows VM/Hyper-V/Windows Sandbox or other tested isolation; verify network and filesystem denial and cleanup after faults. Windows Sandbox availability differs by edition and policy. Do not pretend subprocess isolation is a sandbox.
2. **Real local AI test:** in a disposable isolated Windows VM, install Ollama, download a supported free coding model with explicit consent, record model digest/size, execute ADM-032 live acceptance, capture prompt, model output, source diff, independent test evidence and resource telemetry. Fail closed on missing evidence.
3. **Unattended project generation:** build a persisted requirements→plan→implementation→build→test→repair→artifact state machine, not only a repair queue. Persist transitions and resume after reboot without replaying unsafe edits.
4. **Windows packaging:** produce and test signed/unsigned EXE and self-contained installer with runtime dependencies, uninstall, upgrades, startup, failure diagnostics, and no manual Python install.
5. **Desktop UX:** single nontechnical entry point, progress, blocker explanations, source/artifact export, stop/resume, settings and model management.
6. **Verification:** run complete checkpointed regression; Windows 11 16/32 GiB hardware tests; negative security tests; backup/restore, reboot, crash and fault injection; release only with actual evidence.

## Explicit information needed from user
**None for further portable source development.** For live acceptance later, user must provide or authorize an isolated Windows 11 test environment with an installed local Ollama coding model; no programming or paid API account is needed. Ask for this only when ready to run that acceptance stage.

## Integrity and handoff rules
All source and historical handoffs are in this ZIP. The adjacent `ADM-035-manifest.json` lists SHA-256 of every included source/document file except the manifest itself. Validate ZIP CRC, recompute hashes and run tests after extraction. Preserve all files, not merely changed files, on subsequent versions. The historical handoff below is included verbatim for continuity, but its past claims are historical and do not supersede this version's evidence.

---

# COMPLETE PREVIOUS MASTER HANDOFF (ADM-034, verbatim)

# ADM-034 — Comprehensive Cumulative Master Handoff

**Version:** ADM-034  
**Date:** 2026-11-04  
**Status:** prototype; NOT production ready; NOT a verified Windows EXE; real local-model inference unverified.  
**Intended audience:** a replacement AI assistant, developer, independent QA engineer, or future maintainer.  
**Document rule:** This is cumulative. The complete preceding master handoff is reproduced below, and all earlier handoffs are also individual files in the source archive.

## 1. Immediate nontechnical overview

Autonomous Development Manager (ADM) aims to let a person who does not code describe an application once and have a locally running Windows application plan, write, build, test, debug, repair, package, and deliver it without ongoing chat prompts. It must prioritize free local AI and never incur paid AI API charges. A self-running background supervisor is required because a ChatGPT conversation cannot continue executing indefinitely after its turn ends. The current implementation is a Python prototype, not the finished turnkey Windows app.

## 2. Exact ADM-034 change

Added `adm/model_selection.py`, a deterministic, read-only, installed-model selector. It consumes model names returned by the already existing loopback-only Ollama `/api/tags` inspection and a physical RAM capacity supplied by the caller. It never downloads models, starts models, tests inference, connects to a remote endpoint, or makes API purchases.

- At less than 20 GiB physical RAM (e.g. 16 GiB), models whose explicit size tags are at most 3.5B are eligible.
- At 20 to less than 40 GiB (e.g. 32 GiB), explicitly tagged models up to 8B are eligible.
- At 40 GiB or more, up to 16B are eligible. These are provisional conservative heuristics, **not benchmarks or guarantees**.
- Only named coding-model families are auto-selected; a manually preferred model must be installed, syntactically valid, and within the same tier.
- Unknown-size tags, malformed names, and non-coding models are excluded from automatic selection. No implicit `latest` size inference.
- Results explicitly say `inference_verified: false` and `automatic_download: false`.
- The CLI is `python -B -m adm.model_selection --ram-gib 16` (or `32`); it needs a running Ollama server with an installed model and will return a clear blocker otherwise.
- This selector is **not yet wired into the production background repair queue**, and total RAM is not a substitute for available RAM, GPU/CPU model compatibility, or measured model performance. Do not claim otherwise.

## 3. Evidence and verification matrix

| Test command | Actual result this segment | Meaning |
| --- | --- | --- |
| `python -B -m unittest discover -s tests -p test_model_selection.py -v` | 7/7 passed | Model selection behavior and negative cases |
| `python -B -m unittest discover -s tests -p test_ollama_health.py -q` | 7/7 passed | Existing loopback model inventory checks |
| `python -B -m unittest discover -s tests -p test_ollama_direct.py -q` | 6/6 passed | Existing direct repair adapter checks using simulated response |
| Complete regression | NOT run in ADM-034 | Do not infer pass from targeted tests |
| Real Ollama inference | NOT run | No running local Ollama service in this environment |
| Windows EXE build and launch | NOT run | Requires Windows acceptance environment |
| OS sandbox and malicious generated-code containment | NOT demonstrated | Major release blocker |

All test evidence above was observed from actual Python test execution in the Linux development container; it is not a claim about Windows execution.

## 4. Source and architecture map

The source tree contains Python modules under `adm/`, unit/integration tests under `tests/`, README and historical handoffs at the root. Main relationships: desktop UI -> daemon/supervisor -> durable SQLite jobs -> queued AI repair -> local Ollama direct adapter -> protected file patching and recovery journal -> independent test execution and evidence reports. The release module prepares source bundles and Windows packaging instructions. See the previous master handoff for detailed diagrams and individual contracts.

### Current Python module inventory

| Module | First-line description / declaration |
| --- | --- |
| `adm/__init__.py` | from .core import Supervisor, resources, mode |
| `adm/__main__.py` | import argparse, json, time |
| `adm/acceptance.py` | Offline end-to-end acceptance: real HTTP transport and subprocess tests, fake AI. |
| `adm/adaptive.py` | Resource-aware admission decisions; never changes verification requirements. |
| `adm/agent.py` | ADM-003: guarded OpenCode/Ollama adapter and evidence-backed repair trial. |
| `adm/agent_cli.py` | ADM-003 real local OpenCode agent trial CLI. |
| `adm/ai_status.py` | Read-only CLI for reconciling a queued AI repair with its evidence. |
| `adm/cli.py` | Human-friendly ADM-002 proof command. |
| `adm/core.py` | Durable, resource-aware command verification supervisor (stdlib only). |
| `adm/daemon.py` | Persistent unattended trusted-job runner with observable lifecycle state. |
| `adm/desktop.py` | Small dependency-free desktop control panel for the trusted-job supervisor. |
| `adm/desktop_entry.py` | Frozen GUI entrypoint. Must be built and runtime-tested on Windows. |
| `adm/engine.py` | ADM-002: bounded, evidence-backed autonomous repair proof (standard library). |
| `adm/live_acceptance.py` | Opt-in real Ollama acceptance on a fresh, disposable fixture. |
| `adm/model_probe.py` | Local-only Ollama model readiness and bounded inference smoke benchmark. |
| `adm/model_selection.py` | Deterministic offline model selection from Ollama's locally installed inventory. |
| `adm/ollama_cli.py` | Run a local Ollama direct-repair trial on a trusted disposable project. |
| `adm/ollama_direct.py` | Direct local Ollama repair trial, with deterministic evidence and guarded file edits. |
| `adm/ollama_health.py` | Read-only, loopback-only Ollama health and installed-model inspection. |
| `adm/pipeline.py` | ADM-006: durable, fail-closed supervised local agent proof. |
| `adm/pipeline_cli.py` | Supervised local AI proof: no paid API, no automatic execution of unknown projects. |
| `adm/preflight.py` | Read-only diagnostics for local-only Ollama / OpenCode availability. |
| `adm/project_lock.py` | Fail-closed cross-process project ownership for source-changing AI jobs. |
| `adm/provision.py` | ADM-008: resumable, dependency-aware local provisioning coordinator. |
| `adm/queued_ai.py` | Queue a bounded local-Ollama repair for the persistent ADM supervisor. |
| `adm/recovery.py` | Bounded, verified workspace snapshot/restore for disposable repair trials. |
| `adm/regression.py` | Isolated, bounded regression runner; does not silently turn timeouts into passes. |
| `adm/release.py` | Reproducible source release and opt-in Windows executable build planning. |
| `adm/release_entry.py` | Frozen Windows entrypoint for ADM supervisor (not a graphical interface). |
| `adm/repair_recovery.py` | Crash journal for local-model source replacements. |
| `adm/setup.py` | ADM-007: auditable, explicit-consent local dependency provisioning. |
| `adm/setup_cli.py` | Read-only setup plan by default; --apply is an explicit opt-in. |
| `adm/windows_startup.py` | Opt-in Windows logon launcher. No installation occurs without user action. |
| `adm/worker.py` | ADM-005 durable single-owner worker supervision for TRUSTED commands. |
| `adm/worker_cli.py` | Safe-to-understand CLI for the ADM-005 trusted worker proof. |

### Test module inventory

- `tests/test_acceptance.py`
- `tests/test_adaptive.py`
- `tests/test_adaptive_worker.py`
- `tests/test_agent.py`
- `tests/test_ai_inspection.py`
- `tests/test_core.py`
- `tests/test_daemon.py`
- `tests/test_daemon_lifecycle.py`
- `tests/test_desktop.py`
- `tests/test_engine.py`
- `tests/test_independent_retest.py`
- `tests/test_live_acceptance.py`
- `tests/test_local_transport_security.py`
- `tests/test_model_probe.py`
- `tests/test_model_selection.py`
- `tests/test_ollama_direct.py`
- `tests/test_ollama_health.py`
- `tests/test_pipeline.py`
- `tests/test_project_lock.py`
- `tests/test_provision.py`
- `tests/test_queued_ai.py`
- `tests/test_recovery.py`
- `tests/test_regression.py`
- `tests/test_release.py`
- `tests/test_repair_recovery.py`
- `tests/test_setup.py`
- `tests/test_windows_startup.py`
- `tests/test_worker.py`

## 5. Requirements and acceptance gates

1. Plain-language request once, no coding expertise or constant prompts required.
2. Autonomous supervisor runs outside chat, resumes after reboot, safely coordinates exclusive project ownership, and preserves crash recovery state.
3. Free/local model selection and inference, no paid AI tokens; explicit opt-in and privacy review before any optional cloud provider.
4. True application generation and repair, not only simulated edits or Python toy tests; actual EXE/APK/web artifacts must be verified.
5. Comprehensive end-to-end QA: failing test -> root cause -> correction -> repeat test -> independent regression -> evidence; no false production-ready claims.
6. Secure isolation of AI-generated code and dependencies, deny unsafe network/file access; **currently missing**.
7. Windows 11 self-contained installer/EXE, auto-start, automatic approved dependency provisioning; **currently unverified**.
8. Adapt to 16 GB and 32 GB hardware without sacrificing acceptance tests; selection heuristics are a starting point only.
9. Complete cumulative source ZIP after each segment, all historical handoffs, tests, manifest and detailed handoff; no partial patches as the only deliverable.
10. Independent backup/recovery of the ADM project itself, evidence provenance, reproducible build logs and explicit blocker reports.

## 6. Security boundaries and nonclaims

The local model HTTP adapter restricts connections to explicit 127.0.0.1, disables proxies, and rejects redirects. That is not a sandbox. Tests execute generated Python source using the host Python interpreter; therefore untrusted generated code must **not** be executed on a personal/work host. Use a disposable isolated VM with network and host filesystem access restricted until a real sandbox exists. The model selector never launches test code. Model names from `/api/tags` are untrusted metadata and are validated before use. A model tagged `3b` may still require more memory than anticipated. Always use actual resource admission and observed inference before selecting it for real work.

## 7. How to reproduce / continue

1. Extract this ZIP to a new working directory; do not overwrite an active ADM project.
2. Install Python 3.11+ in an isolated development environment (no special third-party dependency required for the new selector).
3. From the extracted root, run the three commands in Section 3.
4. Run `python -B -m adm.ollama_health` to inspect local models (only if Ollama is already running).
5. Run `python -B -m adm.model_selection --ram-gib 16` or `--ram-gib 32`.
6. For the live repair acceptance test, use a **disposable isolated VM**, a locally installed Ollama model, and the instructions in `adm/live_acceptance.py` and prior handoffs; do not run untrusted generated code directly on the host.
7. Run complete regression using `adm/regression.py` resumable checkpoints; preserve per-module logs and disclose incomplete modules.
8. Implement the next priority: connect the selector to the queued AI repair worker with preflight, explicit model availability and actual resource checks; then add a secure sandbox, prove live inference, and build/test on Windows.

## 8. Known limitations and concrete next tasks

- Real local AI inference remains unverified; obtaining a working local Ollama service and a suitable coding model is necessary for live acceptance.
- Current selector uses declared parameter counts rather than measured resident memory or quantization; it can reject useful models or accept models that cannot fit. Improve with observed memory and load checks.
- No OS-level sandbox for executing generated code. This is a security blocker, not a cosmetic issue.
- No verified turnkey Windows executable, installer, or Windows end-to-end startup acceptance.
- No verified autonomous creation of arbitrary user-specified applications from plain-language requirements.
- Full regression not completed this segment; do not claim it passed.
- Next engineer should prioritize a functioning live-model, sandboxed end-to-end proof rather than adding more UI polish.

## 9. User input needed

**Nothing required to continue portable code development.** A real Windows 11 machine/VM and an installed local coding model will be required for final Windows and live-model acceptance; request user assistance only when those tests are ready, using simple steps. Never require the user to write code.

---

# Complete previous master handoff (ADM-033), preserved verbatim

# ADM-033 — COMPREHENSIVE CUMULATIVE MASTER HANDOFF

## Read first: status and honesty
This is the cumulative source of Autonomous Development Manager (ADM), a Windows 11 autonomous application-builder prototype. It is NOT production ready. The user wants to provide a plain-English description once and receive a built, tested, repaired, packaged app without repeated chat prompts. The intended platform is 16 GB and 32 GB Windows computers, with free/local AI only and zero paid API charges. The intended outputs include Windows executables, Android APKs and web apps. None of those general-purpose output paths is production verified.

**This release changes one specific acceptance gate:** a local-AI repair now requires TWO separate passing executions of the test suite, not one. If the second test fails, the candidate patch is rejected and the source is restored through the existing recovery journal. The two runs are sequential and use the same project and tests; this is a repeatability check, NOT an independent test author, OS sandbox, proof of requirements coverage, or guarantee against malicious code.

## Implementation details: ADM-033
- `adm/ollama_direct.py`, function `_direct_repair_unlocked`: after a candidate patch, run the existing `test_command()` via `run_checked`; only when the first pass succeeds, protected files remain unchanged and source differs from the original, execute `test_command()` again in a new subprocess. Recheck protected hashes and source difference after the second run. Require both exit codes zero before accepting.
- Evidence: each attempt now has `test` and `independent_retest` (null if the first pass was not eligible), `protected_unchanged` and `passed`. Existing recovery journal and project lock remain in force during both runs.
- `tests/test_independent_retest.py`: verifies two actual passing subprocess executions; injects a failure on the third run (baseline + first pass + retest), verifies failed status, explicit evidence and restoration of original bytes.
- Compatibility: the existing `tests/test_ollama_direct.py` test suite continues to pass. Downstream consumers should not assume `independent_retest` is always a dict; it can be null.

## Actual test evidence this segment
Commands executed on Linux in the sandbox:
`python -B -m unittest discover -s tests -p test_independent_retest.py -v` — 2/2 passed.
`python -B -m unittest discover -s tests -p test_ollama_direct.py -q` — 6/6 passed.
Total focused: 8/8 passed. Full regression NOT run in this segment. Actual Ollama inference NOT run. Windows EXE NOT built. Windows 11, 16 GB and 32 GB runtime acceptance NOT run. No OS sandbox is implemented. Do not label the prototype production-ready.

## Operator setup and commands
Unpack ZIP to a clean folder. Python 3.10+ is recommended for source execution. From project root:
`python -B -m unittest discover -s tests -p test_independent_retest.py -v`
`python -B -m unittest discover -s tests -p test_ollama_direct.py -v`
`python -B -m adm.ollama_health`
Inspect `README.md`, `adm/live_acceptance.py`, `adm/daemon.py`, `adm/desktop.py`, `adm/release.py` before invoking operational commands. The real-model acceptance harness runs AI-written Python without OS-level isolation: only execute it in a disposable, network-restricted VM with no credentials. Do not enable arbitrary execution on a personal computer.

## Requirements and architectural boundaries
User-facing goal: one simple Windows app with autonomous planning, model selection, scaffolding, coding, dependency management, builds, tests, fault diagnosis, retry, crash/reboot recovery, independent verification and packaging. User should not need coding knowledge. Durable supervisor is SQLite-backed; repair runs use project ownership locks, journals and protected hashes; Ollama HTTP adapter restricts connections to loopback. Existing Tkinter control panel is early prototype. Resource admission logic exists, but no real 16/32 GB validation. The current repair supports only existing top-level Python files in a controlled fixture; it cannot create arbitrary full-stack apps yet. No payment-bearing AI APIs may be required. Any remote provider use needs explicit consent and a strict privacy policy.

## Threat model and unresolved blockers
CRITICAL: AI-generated Python is executed with the invoking OS account's permissions. A Python-level path validator, loopback-only Ollama transport and subprocess timeout are NOT a sandbox. Generated code can access files, network, subprocesses and credentials. Require OS isolation before untrusted project execution. Other unresolved work: real Ollama coding inference and model-selection acceptance; durable plain-English request-to-delivery workflow; robust toolchain install; real Windows EXE and installer; process-tree cleanup under Windows; boot/reboot resume; Android and web builds; fault injection; complete regression; genuine requirements traceability and QA evidence. A second test pass does not mitigate a malicious test program.

## Next implementation steps (prioritized)
1. Add an OS-enforced execution boundary (e.g., disposable VM with verified no-shared-secrets configuration); fail closed if unavailable.
2. In that environment, run real Ollama model acceptance and retain complete prompt/response hashes, model details, test logs, exit codes and failures.
3. Build a durable natural-language-to-project job with stage checkpoints and safe tool permissions; make one user request drive all stages.
4. Build Windows GUI EXE/installer and test launch, queue, shutdown, restart, offline operation and fault injection on 16 GB and 32 GB machines.
5. Run complete regression and track every requirement to actual evidence. Never convert timeouts or unrun tests into passes.
6. Produce a full cumulative source ZIP plus a self-contained master handoff after every segment.

## User action required
None for further portable source development. For real-model Windows acceptance, a disposable Windows 11 VM and a downloaded local Ollama coding model are required. User need not write code or purchase an API key.

## Current module and test inventory
- `adm/__init__.py` — from .core import Supervisor, resources, mode
- `adm/__main__.py` — import argparse, json, time
- `adm/acceptance.py` — """Offline end-to-end acceptance: real HTTP transport and subprocess tests, fake AI.
- `adm/adaptive.py` — """Resource-aware admission decisions; never changes verification requirements.
- `adm/agent.py` — """ADM-003: guarded OpenCode/Ollama adapter and evidence-backed repair trial.
- `adm/agent_cli.py` — """ADM-003 real local OpenCode agent trial CLI."""
- `adm/ai_status.py` — """Read-only CLI for reconciling a queued AI repair with its evidence."""
- `adm/cli.py` — """Human-friendly ADM-002 proof command."""
- `adm/core.py` — """Durable, resource-aware command verification supervisor (stdlib only)."""
- `adm/daemon.py` — """Persistent unattended trusted-job runner with observable lifecycle state.
- `adm/desktop.py` — """Small dependency-free desktop control panel for the trusted-job supervisor.
- `adm/desktop_entry.py` — """Frozen GUI entrypoint. Must be built and runtime-tested on Windows."""
- `adm/engine.py` — """ADM-002: bounded, evidence-backed autonomous repair proof (standard library)."""
- `adm/live_acceptance.py` — """Opt-in real Ollama acceptance on a fresh, disposable fixture.
- `adm/model_probe.py` — """Local-only Ollama model readiness and bounded inference smoke benchmark.
- `adm/ollama_cli.py` — """Run a local Ollama direct-repair trial on a trusted disposable project."""
- `adm/ollama_direct.py` — """Direct local Ollama repair trial, with deterministic evidence and guarded file edits.
- `adm/ollama_health.py` — """Read-only, loopback-only Ollama health and installed-model inspection.
- `adm/pipeline.py` — """ADM-006: durable, fail-closed supervised local agent proof.
- `adm/pipeline_cli.py` — """Supervised local AI proof: no paid API, no automatic execution of unknown projects."""
- `adm/preflight.py` — """Read-only diagnostics for local-only Ollama / OpenCode availability."""
- `adm/project_lock.py` — """Fail-closed cross-process project ownership for source-changing AI jobs.
- `adm/provision.py` — """ADM-008: resumable, dependency-aware local provisioning coordinator.
- `adm/queued_ai.py` — """Queue a bounded local-Ollama repair for the persistent ADM supervisor.
- `adm/recovery.py` — """Bounded, verified workspace snapshot/restore for disposable repair trials.
- `adm/regression.py` — """Isolated, bounded regression runner; does not silently turn timeouts into passes."""
- `adm/release.py` — """Reproducible source release and opt-in Windows executable build planning.
- `adm/release_entry.py` — """Frozen Windows entrypoint for ADM supervisor (not a graphical interface)."""
- `adm/repair_recovery.py` — """Crash journal for local-model source replacements.
- `adm/setup.py` — """ADM-007: auditable, explicit-consent local dependency provisioning.
- `adm/setup_cli.py` — """Read-only setup plan by default; --apply is an explicit opt-in."""
- `adm/windows_startup.py` — """Opt-in Windows logon launcher. No installation occurs without user action.
- `adm/worker.py` — """ADM-005 durable single-owner worker supervision for TRUSTED commands.
- `adm/worker_cli.py` — """Safe-to-understand CLI for the ADM-005 trusted worker proof."""
- `tests/test_acceptance.py` — import json
- `tests/test_adaptive.py` — import unittest
- `tests/test_adaptive_worker.py` — import sys
- `tests/test_agent.py` — import json
- `tests/test_ai_inspection.py` — import json
- `tests/test_core.py` — import sys,tempfile,unittest
- `tests/test_daemon.py` — import sys
- `tests/test_daemon_lifecycle.py` — import json
- `tests/test_desktop.py` — import tempfile
- `tests/test_engine.py` — import json
- `tests/test_independent_retest.py` — """Independent second-process verification of model-produced patches."""
- `tests/test_live_acceptance.py` — import tempfile
- `tests/test_local_transport_security.py` — """Regression tests ensuring local AI transport never follows redirects."""
- `tests/test_model_probe.py` — import io
- `tests/test_ollama_direct.py` — import json
- `tests/test_ollama_health.py` — import json
- `tests/test_pipeline.py` — import json
- `tests/test_project_lock.py` — import json
- `tests/test_provision.py` — import json
- `tests/test_queued_ai.py` — import json
- `tests/test_recovery.py` — import json
- `tests/test_regression.py` — import tempfile
- `tests/test_release.py` — import hashlib
- `tests/test_repair_recovery.py` — import json
- `tests/test_setup.py` — import subprocess
- `tests/test_windows_startup.py` — import os
- `tests/test_worker.py` — import os

## Complete ADM-032 master handoff preserved verbatim

# ADM-032 — EXTENSIVE CUMULATIVE MASTER HANDOFF

> **Read this file first.** This is a complete, self-contained development handoff. It contains the prior master handoff verbatim after the ADM-032 addendum. The code, tests, earlier handoffs, and integrity manifest are packaged together. **This is not a production-ready Windows application.**

## Executive status and evidence discipline

- Product: Autonomous Development Manager, a turnkey Windows 11 app builder for a nonprogrammer. User supplies a plain-English specification once; ADM should research, plan, write, test, debug, package, recover and deliver actual usable applications without repeated prompting.
- Mandatory constraints: local/free AI; no paid API usage; work on 16 GB and 32 GB Windows machines; autonomous supervision; end-to-end evidence and independent verification; privacy/security boundaries; recoverable state; full cumulative source and extremely detailed handoff after every segment.
- ADM-032 milestone: an **opt-in, real-model acceptance harness** for a disposable Python coding problem, with local Ollama installed-model preflight, refusal of nonempty destinations, independent success conditions, and explicit acknowledgement of unsandboxed execution.
- What was actually run here: 4/4 new acceptance harness tests; 6/6 existing direct Ollama adapter tests; 7/7 Ollama health tests; 2/2 offline acceptance tests. **19 focused tests passed** in these specific modules. Full regression was not run this segment. Ollama was not reachable on loopback; genuine inference and Windows runtime were **not** tested.
- No real-model success is claimed. The local test environment returned `Connection refused` on the Ollama health check. Fake/mocked tests are labeled as such.

## New files and interfaces

### `adm/live_acceptance.py`

`run_live_acceptance(output_dir, model='ollama/qwen2.5-coder:3b', timeout=120)` verifies that an Ollama model with the exact requested name appears in the installed-model list before writing any project files. Requires a new or empty output directory. Creates a deliberately broken `calculator.py`, associated tests and requirements using the existing `engine.make_broken_demo`; then calls `ollama_direct.direct_repair` with its real default request generator. It inspects the baseline failure, post-repair tests, actual repair status, `live_model_verified` evidence and absence of the recovery journal. It emits `live-acceptance-summary.json` with an explicit true/false result. Failure and errors are not counted as success.

**CLI:** `python -B -m adm.live_acceptance --output PATH --model ollama/qwen2.5-coder:3b --timeout 120 --acknowledge-unsandboxed-code`

**CRITICAL:** The CLI requires `--acknowledge-unsandboxed-code` because it executes model-written Python without an OS sandbox. **Only run inside an isolated, disposable VM with no credentials or valuable files and restricted networking.** The flag is an acknowledgment, NOT a security mechanism. The underlying Python function is for trusted callers and does not itself enforce a sandbox.

### `tests/test_live_acceptance.py`

Four tests cover: no writes when the requested model is missing, no overwrite of existing output files, inability for an injected fake repair to assert genuine model verification, and required CLI acknowledgement. These tests use injected fixtures and do not prove genuine AI inference.

## What to run next — exact sequence

1. Inspect `adm/ollama_direct.py`, `adm/live_acceptance.py`, and `adm/ollama_health.py`. Do not run model-generated code on a personal host without isolation.
2. Inside a disposable Windows 11 VM, install Ollama and a free local coding model. Confirm model name with `python -B -m adm.ollama_health` and `ollama list`.
3. Run `python -B -m adm.live_acceptance --output C:\ADM-acceptance-001 --model ollama/qwen2.5-coder:3b --acknowledge-unsandboxed-code` in the isolated VM, with an empty output directory. Capture the JSON summary, repair report, baseline and post-repair test output, process exit code, model version and hardware information. A failed result is a failure, not a pass.
4. Run the full test suite with the resumable regression harness; do not claim full regression until all modules are actually verified. Use the runner's checkpoint/log functionality to prevent repeated timeouts.
5. Build and test a real Windows EXE and installer on both 16 GB and 32 GB systems. Check desktop launch, daemon startup, restart after reboot, offline mode, backup and recovery, and failure injection.
6. Implement **real OS-level sandboxing** before exposing general AI-written applications to execution. Enforce file/network/process boundaries, resource quotas, tool permissions and per-project isolated workspaces. Existing Python path checks and subprocess timeouts are not a sandbox.
7. Integrate plain-language requirements → planning → project scaffolding → AI coding → independent tests → bounded repairs → artifact packaging into a single unattended job with durable state and UI reporting. The current proof is much narrower.

## Security and reliability risks that remain

- **HIGH:** Generated code can execute arbitrary actions with the user's OS permissions. No OS sandbox is implemented.
- **HIGH:** Genuine local-model coding reliability is unmeasured. The model may fail, hallucinate or generate malicious code.
- **HIGH:** Windows EXE and installer are not actually built/verified on Windows.
- **MEDIUM:** Some subprocess timeout handling may leave descendants or partial outputs; validate on Windows with fault injection.
- **MEDIUM:** A local loopback Ollama endpoint is restricted and redirects/proxies are blocked, but a malicious process on the host could impersonate Ollama. Local process integrity is not authenticated.
- **MEDIUM:** Existing repairs support narrow top-level `.py` replacements, not arbitrary projects, Android builds or web stacks.
- **MEDIUM:** Complete end-to-end autonomous planning, retry orchestration and acceptance gates are unfinished.
- **MEDIUM:** No real 16 GB vs 32 GB memory/throughput evidence.

## Operator and user needs

**Nothing is required from the user to continue portable source development.** For live acceptance, someone must provide a Windows 11 VM or equivalent disposable environment with Ollama and a downloaded local coding model. The user need not write code. Do not request API keys or paid services.

## Current source inventory

- `adm/__init__.py` — from .core import Supervisor, resources, mode
- `adm/__main__.py` — from .core import Supervisor,resources,mode
- `adm/acceptance.py` — """Offline end-to-end acceptance: real HTTP transport and subprocess tests, fake AI.
- `adm/adaptive.py` — """Resource-aware admission decisions; never changes verification requirements.
- `adm/agent.py` — """ADM-003: guarded OpenCode/Ollama adapter and evidence-backed repair trial.
- `adm/agent_cli.py` — """ADM-003 real local OpenCode agent trial CLI."""
- `adm/ai_status.py` — """Read-only CLI for reconciling a queued AI repair with its evidence."""
- `adm/cli.py` — """Human-friendly ADM-002 proof command."""
- `adm/core.py` — """Durable, resource-aware command verification supervisor (stdlib only)."""
- `adm/daemon.py` — """Persistent unattended trusted-job runner with observable lifecycle state.
- `adm/desktop.py` — """Small dependency-free desktop control panel for the trusted-job supervisor.
- `adm/desktop_entry.py` — """Frozen GUI entrypoint. Must be built and runtime-tested on Windows."""
- `adm/engine.py` — """ADM-002: bounded, evidence-backed autonomous repair proof (standard library)."""
- `adm/live_acceptance.py` — """Opt-in real Ollama acceptance on a fresh, disposable fixture.
- `adm/model_probe.py` — """Local-only Ollama model readiness and bounded inference smoke benchmark.
- `adm/ollama_cli.py` — """Run a local Ollama direct-repair trial on a trusted disposable project."""
- `adm/ollama_direct.py` — """Direct local Ollama repair trial, with deterministic evidence and guarded file edits.
- `adm/ollama_health.py` — """Read-only, loopback-only Ollama health and installed-model inspection.
- `adm/pipeline.py` — """ADM-006: durable, fail-closed supervised local agent proof.
- `adm/pipeline_cli.py` — """Supervised local AI proof: no paid API, no automatic execution of unknown projects."""
- `adm/preflight.py` — """Read-only diagnostics for local-only Ollama / OpenCode availability."""
- `adm/project_lock.py` — """Fail-closed cross-process project ownership for source-changing AI jobs.
- `adm/provision.py` — """ADM-008: resumable, dependency-aware local provisioning coordinator.
- `adm/queued_ai.py` — """Queue a bounded local-Ollama repair for the persistent ADM supervisor.
- `adm/recovery.py` — """Bounded, verified workspace snapshot/restore for disposable repair trials.
- `adm/regression.py` — """Isolated, bounded regression runner; does not silently turn timeouts into passes."""
- `adm/release.py` — """Reproducible source release and opt-in Windows executable build planning.
- `adm/release_entry.py` — """Frozen Windows entrypoint for ADM supervisor (not a graphical interface)."""
- `adm/repair_recovery.py` — """Crash journal for local-model source replacements.
- `adm/setup.py` — """ADM-007: auditable, explicit-consent local dependency provisioning.
- `adm/setup_cli.py` — """Read-only setup plan by default; --apply is an explicit opt-in."""
- `adm/windows_startup.py` — """Opt-in Windows logon launcher. No installation occurs without user action.
- `adm/worker.py` — """ADM-005 durable single-owner worker supervision for TRUSTED commands.
- `adm/worker_cli.py` — """Safe-to-understand CLI for the ADM-005 trusted worker proof."""

## Current test inventory

- `tests/test_acceptance.py` — 1134 bytes; run with `python -B -m unittest discover -s tests -p test_acceptance.py -v`
- `tests/test_adaptive.py` — 1422 bytes; run with `python -B -m unittest discover -s tests -p test_adaptive.py -v`
- `tests/test_adaptive_worker.py` — 2367 bytes; run with `python -B -m unittest discover -s tests -p test_adaptive_worker.py -v`
- `tests/test_agent.py` — 5341 bytes; run with `python -B -m unittest discover -s tests -p test_agent.py -v`
- `tests/test_ai_inspection.py` — 2690 bytes; run with `python -B -m unittest discover -s tests -p test_ai_inspection.py -v`
- `tests/test_core.py` — 1760 bytes; run with `python -B -m unittest discover -s tests -p test_core.py -v`
- `tests/test_daemon.py` — 2254 bytes; run with `python -B -m unittest discover -s tests -p test_daemon.py -v`
- `tests/test_daemon_lifecycle.py` — 1919 bytes; run with `python -B -m unittest discover -s tests -p test_daemon_lifecycle.py -v`
- `tests/test_desktop.py` — 2588 bytes; run with `python -B -m unittest discover -s tests -p test_desktop.py -v`
- `tests/test_engine.py` — 2475 bytes; run with `python -B -m unittest discover -s tests -p test_engine.py -v`
- `tests/test_live_acceptance.py` — 1927 bytes; run with `python -B -m unittest discover -s tests -p test_live_acceptance.py -v`
- `tests/test_local_transport_security.py` — 1579 bytes; run with `python -B -m unittest discover -s tests -p test_local_transport_security.py -v`
- `tests/test_model_probe.py` — 2521 bytes; run with `python -B -m unittest discover -s tests -p test_model_probe.py -v`
- `tests/test_ollama_direct.py` — 3756 bytes; run with `python -B -m unittest discover -s tests -p test_ollama_direct.py -v`
- `tests/test_ollama_health.py` — 2944 bytes; run with `python -B -m unittest discover -s tests -p test_ollama_health.py -v`
- `tests/test_pipeline.py` — 4770 bytes; run with `python -B -m unittest discover -s tests -p test_pipeline.py -v`
- `tests/test_project_lock.py` — 2258 bytes; run with `python -B -m unittest discover -s tests -p test_project_lock.py -v`
- `tests/test_provision.py` — 3131 bytes; run with `python -B -m unittest discover -s tests -p test_provision.py -v`
- `tests/test_queued_ai.py` — 2829 bytes; run with `python -B -m unittest discover -s tests -p test_queued_ai.py -v`
- `tests/test_recovery.py` — 3835 bytes; run with `python -B -m unittest discover -s tests -p test_recovery.py -v`
- `tests/test_regression.py` — 9713 bytes; run with `python -B -m unittest discover -s tests -p test_regression.py -v`
- `tests/test_release.py` — 3678 bytes; run with `python -B -m unittest discover -s tests -p test_release.py -v`
- `tests/test_repair_recovery.py` — 2610 bytes; run with `python -B -m unittest discover -s tests -p test_repair_recovery.py -v`
- `tests/test_setup.py` — 3465 bytes; run with `python -B -m unittest discover -s tests -p test_setup.py -v`
- `tests/test_windows_startup.py` — 1317 bytes; run with `python -B -m unittest discover -s tests -p test_windows_startup.py -v`
- `tests/test_worker.py` — 5761 bytes; run with `python -B -m unittest discover -s tests -p test_worker.py -v`

## Packaging and continuation guarantees

- The ZIP includes **all cumulative source**, tests, earlier Markdown handoffs, current master handoff and SHA-256 manifest. It is not a delta.
- Verify manifest hashes after extraction; run tests in a clean environment. Never confuse ZIP integrity with functional correctness.
- Keep the previous master handoff below for original requirements, design rationale, historical status, module behavior, earlier evidence and future plans. When a prior claim conflicts with this addendum, prefer the more recent, evidence-backed statement.

---

# PRESERVED ADM-031 MASTER HANDOFF — FULL TEXT

# ADM-031 MASTER HANDOFF — FULL CUMULATIVE ENGINEERING RECORD

**Version:** ADM-031  
**Status:** prototype; not production-ready  
**Primary objective:** autonomous, no-code Windows application builder using free local AI; 16/32 GB RAM profiles, crash recovery, independent QA, complete deliverables.  
**Intended user workflow:** describe app once; manager handles research/planning/code/build/test/repair/packaging; no repeated continue prompts.  
**Evidence integrity:** never represent fixture inference as a real AI test, Linux tests as Windows acceptance, or a passing unit test as proof of isolation.  

## 1. Current segment: exactly what changed

- `adm/acceptance.py`: executable offline end-to-end fixture that creates a broken Python project, launches a loopback-only HTTP server mimicking the Ollama `/api/generate` JSON response, uses the *real* `request_patch` transport, invokes `direct_repair`, runs actual failing and passing unittest subprocesses, and writes a machine-readable evidence summary.
- `tests/test_acceptance.py`: positive end-to-end verification and a negative test proving the runner refuses to overwrite an occupied output folder.
- No real model is used in this test. The fixture returns a deterministic correct patch; `real_model_verified` is **false**. The fake server binds to 127.0.0.1 and closes on completion.
- Existing direct Ollama, queued-AI, and repair recovery tests were rerun separately.

## 2. Reproduction and observed evidence

Run from extracted source root with Python 3.10+:

```powershell
python -B -m unittest discover -s tests -p test_acceptance.py -v
python -B -m unittest discover -s tests -p test_ollama_direct.py -q
python -B -m unittest discover -s tests -p test_queued_ai.py -q
python -B -m unittest discover -s tests -p test_repair_recovery.py -q
python -B -m adm.acceptance --output .\fresh-empty-acceptance-folder
```

**Recorded this segment:** 2/2 acceptance tests; 6/6 direct Ollama tests; 5/5 queued AI tests; 5/5 recovery tests. These are four separate test runs, not a completed full regression. No real Ollama model was present or exercised. No Windows executable was built or run. No sandbox was demonstrated.

The acceptance command's output directory must be empty or nonexistent. Evidence files: `acceptance-summary.json`, `evidence/ollama-direct-report.json`, and the repaired `demo-project/calculator.py`.

## 3. Architecture and responsibilities

```
User specification -> desktop/CLI -> persistent supervisor queue -> trusted worker
    -> local Ollama adapter -> guarded patch validation -> recovery journal
    -> actual tests -> evidence reconciliation -> reported status
```

The supervisor has durable queue state and a background runner; it is **not** a proven autonomous Windows service. `ollama_direct` supports a narrow existing-file Python repair only. It does not create arbitrary new applications, autonomously select build toolchains, or securely sandbox generated programs. A passing fixture is not general-purpose AI competence.

### Module inventory (source, not invented feature claims)

- `adm/__init__.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/__main__.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/acceptance.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/adaptive.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/agent.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/agent_cli.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/ai_status.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/cli.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/core.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/daemon.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/desktop.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/desktop_entry.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/engine.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/model_probe.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/ollama_cli.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/ollama_direct.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/ollama_health.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/pipeline.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/pipeline_cli.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/preflight.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/project_lock.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/provision.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/queued_ai.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/recovery.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/regression.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/release.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/release_entry.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/repair_recovery.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/setup.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/setup_cli.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/windows_startup.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/worker.py` — inspect this module and its docstrings for exact public interfaces.
- `adm/worker_cli.py` — inspect this module and its docstrings for exact public interfaces.

### Test inventory

- `tests/test_acceptance.py`
- `tests/test_adaptive.py`
- `tests/test_adaptive_worker.py`
- `tests/test_agent.py`
- `tests/test_ai_inspection.py`
- `tests/test_core.py`
- `tests/test_daemon.py`
- `tests/test_daemon_lifecycle.py`
- `tests/test_desktop.py`
- `tests/test_engine.py`
- `tests/test_local_transport_security.py`
- `tests/test_model_probe.py`
- `tests/test_ollama_direct.py`
- `tests/test_ollama_health.py`
- `tests/test_pipeline.py`
- `tests/test_project_lock.py`
- `tests/test_provision.py`
- `tests/test_queued_ai.py`
- `tests/test_recovery.py`
- `tests/test_regression.py`
- `tests/test_release.py`
- `tests/test_repair_recovery.py`
- `tests/test_setup.py`
- `tests/test_windows_startup.py`
- `tests/test_worker.py`

## 4. Operational safety and unresolved engineering risks

- **Untrusted code execution:** Python test subprocesses run with host user permissions; OS-level sandbox, restricted filesystem, network isolation, resource caps and process-tree cleanup are not complete. Only run trusted disposable projects.
- **Real AI:** Ollama HTTP compatibility is tested using a fake loopback server; real model accuracy, latency, memory footprint, prompt sizes, model installation and reliability have not been proven.
- **Crash recovery:** journal and exclusive lock exist, but Windows power-loss and process-kill fault-injection acceptance remain outstanding.
- **Windows distribution:** no verified self-contained Windows EXE or one-click installer. Desktop prototype exists but Windows acceptance is pending.
- **Autonomous generation:** existing direct repair accepts a small JSON patch replacing top-level existing Python files; arbitrary project creation, dependency provisioning and Android/Windows build pipelines remain unfinished.
- **Verification:** record full suite completion and independently run compiled artifacts before release. A worker exit code is insufficient; cross-check test evidence and recovery journals.
- **Privacy:** direct Ollama transport is loopback-only and blocks redirects/proxies; the broader application still needs comprehensive data-flow and secret-scanning tests.
- **Resourcing:** 16 GB and 32 GB profiles are architectural goals; no comparative hardware acceptance has been performed.

## 5. Exact next engineering tasks in priority order

1. Run **real Ollama inference** with an installed free local coding model on a disposable broken app; preserve model version, hardware/RAM, prompt, latency, responses, logs, failing baseline and passing final tests. Never mark a fixture as real-model evidence.
2. Add a durable autonomous specification-to-project planner and project generator with bounded retries, requirement traceability and safe workspace management.
3. Implement and test Windows-safe execution isolation for generated programs; threat-model file writes, subprocess trees, network access, credentials and arbitrary code.
4. Build a fully bundled Windows EXE and one-click installation, including runtime/toolchain bootstrapping and reliable startup/recovery.
5. Independently test EXE and Android APK builds on supported Windows and Android targets; provide tangible outputs, not build instructions alone.
6. Complete a checkpointed full regression and reproducible clean-machine acceptance on 16 GB and 32 GB Windows 11 environments.
7. Improve GUI into the sole user-facing workflow: submit plain-language app, see progress and final deliverables, no CLI required.
8. Produce cumulative full source ZIP and detailed master handoff after each development segment, with evidence, SHA-256 manifest, known limitations, and explicit user needs.

## 6. What the user must supply

**Nothing for portable development or deterministic fixture testing.** For a real local-model/Windows acceptance pass, access to an actual Windows 11 machine with Ollama and a coding model (or authorization to install them) is necessary. Do not ask the user to code or babysit a development process.

## 7. Preservation and continuity

This is a complete cumulative source snapshot, not a diff. Historical handoffs are retained. The prior master handoff follows **verbatim** below so earlier design decisions, commands, requirements and historical caveats are not lost.

---

# COMPLETE ADM-030 MASTER HANDOFF (PRESERVED)

# ADM-030 — COMPLETE CUMULATIVE MASTER HANDOFF

**Status: DEVELOPMENT PROTOTYPE; NOT PRODUCTION READY.**

## 1. Executive transfer instructions

This is the complete cumulative source tree for ADM through version 030. It includes all previous handoffs and test modules. Another engineer or AI should extract the ZIP, read this document and `README.md`, inspect the code, run the tests, and continue without assuming any unverified capability is working. The user does not write code; the intended product is a single, free/local, turnkey autonomous application builder for Windows 11.

## 2. User requirements and nonnegotiable constraints

- User supplies a plain-language software specification once; the finished product must autonomously plan, implement, build, test, diagnose, repair, retest, package and explain genuine blockers.
- Must support Windows EXEs, Android APKs and web apps with appropriate local toolchains; no claims of support without real integration evidence.
- No paid AI API charges; local AI preferred, free external providers only with explicit consent and privacy boundaries.
- Adaptive operation on 16 GB and 32 GB Windows 11 computers, preserving test rigor when parallelism is reduced.
- Durable unattended supervisor, restart/recovery, job queue, retries, logs, and independent verification.
- Protect source, tests, requirements, and evidence; reject unsafe paths and concurrent project writes.
- One integrated application with simple GUI; no manual app switching or programming required.
- After EVERY development segment, deliver the entire cumulative source, tests, previous handoffs, manifest, and a detailed standalone Markdown handoff.
- Do not claim real AI inference, OS sandboxing, Windows packaging or production acceptance without actual evidence.

## 3. Version 030 change: local model inventory and connectivity

`adm/ollama_health.py` implements a read-only Ollama `/api/tags` probe using Python standard library. It only accepts explicit `http://127.0.0.1:<port>` endpoints; disables proxies, refuses redirects using the shared hardened opener, limits response to 1 MB, validates JSON and model names, and always reports `inference_verified: false`. CLI: `python -m adm.ollama_health`. This is not an inference test and does not install Ollama or download models.

### Tests run in this development segment

| Test module | Observed result |
|---|---|
| `test_ollama_health.py` | 7/7 PASS (local fake HTTP server, failure path, redirects, invalid metadata, invalid endpoints) |
| `test_ollama_direct.py` | 6/6 PASS (fake generator and HTTP protocol, not real model) |
| `test_queued_ai.py` | 5/5 PASS |
| `test_project_lock.py` | 6/6 PASS |
| Entire suite | NOT RUN / NOT VERIFIED for ADM-030 |
| Real local Ollama inference | NOT RUN: `ollama` executable unavailable in this Linux environment |
| Windows EXE / installer / GUI | NOT RUN on Windows |

## 4. Architecture and trust boundaries

User input -> desktop/CLI -> durable daemon/worker queue -> bounded trusted execution -> Ollama direct repair / other agent -> protected file validation -> independent tests -> evidence and report. The direct repair subsystem is **NOT** a sandbox; only trusted disposable projects should be used. Model outputs are untrusted. The loopback endpoint is enforced for the direct adapter; OS-level network restrictions for generated code are still missing. Tests are not equivalent to production acceptance.

## 5. Complete Python module inventory

- **`adm/__init__.py`** — 1 lines; opening description: from .core import Supervisor, resources, mode
- **`adm/__main__.py`** — 22 lines; opening description: import argparse, json, time
- **`adm/adaptive.py`** — 53 lines; opening description: Resource-aware admission decisions; never changes verification requirements.
- **`adm/agent.py`** — 195 lines; opening description: ADM-003: guarded OpenCode/Ollama adapter and evidence-backed repair trial.
- **`adm/agent_cli.py`** — 40 lines; opening description: ADM-003 real local OpenCode agent trial CLI.
- **`adm/ai_status.py`** — 18 lines; opening description: Read-only CLI for reconciling a queued AI repair with its evidence.
- **`adm/cli.py`** — 25 lines; opening description: Human-friendly ADM-002 proof command.
- **`adm/core.py`** — 67 lines; opening description: Durable, resource-aware command verification supervisor (stdlib only).
- **`adm/daemon.py`** — 103 lines; opening description: Persistent unattended trusted-job runner with observable lifecycle state.
- **`adm/desktop.py`** — 95 lines; opening description: Small dependency-free desktop control panel for the trusted-job supervisor.
- **`adm/desktop_entry.py`** — 4 lines; opening description: Frozen GUI entrypoint. Must be built and runtime-tested on Windows.
- **`adm/engine.py`** — 127 lines; opening description: ADM-002: bounded, evidence-backed autonomous repair proof (standard library).
- **`adm/model_probe.py`** — 98 lines; opening description: Local-only Ollama model readiness and bounded inference smoke benchmark.
- **`adm/ollama_cli.py`** — 21 lines; opening description: Run a local Ollama direct-repair trial on a trusted disposable project.
- **`adm/ollama_direct.py`** — 192 lines; opening description: Direct local Ollama repair trial, with deterministic evidence and guarded file edits.
- **`adm/ollama_health.py`** — 64 lines; opening description: Read-only, loopback-only Ollama health and installed-model inspection.
- **`adm/pipeline.py`** — 99 lines; opening description: ADM-006: durable, fail-closed supervised local agent proof.
- **`adm/pipeline_cli.py`** — 28 lines; opening description: Supervised local AI proof: no paid API, no automatic execution of unknown projects.
- **`adm/preflight.py`** — 49 lines; opening description: Read-only diagnostics for local-only Ollama / OpenCode availability.
- **`adm/project_lock.py`** — 40 lines; opening description: Fail-closed cross-process project ownership for source-changing AI jobs.
- **`adm/provision.py`** — 80 lines; opening description: ADM-008: resumable, dependency-aware local provisioning coordinator.
- **`adm/queued_ai.py`** — 111 lines; opening description: Queue a bounded local-Ollama repair for the persistent ADM supervisor.
- **`adm/recovery.py`** — 76 lines; opening description: Bounded, verified workspace snapshot/restore for disposable repair trials.
- **`adm/regression.py`** — 183 lines; opening description: Isolated, bounded regression runner; does not silently turn timeouts into passes.
- **`adm/release.py`** — 119 lines; opening description: Reproducible source release and opt-in Windows executable build planning.
- **`adm/release_entry.py`** — 4 lines; opening description: Frozen Windows entrypoint for ADM supervisor (not a graphical interface).
- **`adm/repair_recovery.py`** — 88 lines; opening description: Crash journal for local-model source replacements.
- **`adm/setup.py`** — 113 lines; opening description: ADM-007: auditable, explicit-consent local dependency provisioning.
- **`adm/setup_cli.py`** — 30 lines; opening description: Read-only setup plan by default; --apply is an explicit opt-in.
- **`adm/windows_startup.py`** — 63 lines; opening description: Opt-in Windows logon launcher. No installation occurs without user action.
- **`adm/worker.py`** — 209 lines; opening description: ADM-005 durable single-owner worker supervision for TRUSTED commands.
- **`adm/worker_cli.py`** — 41 lines; opening description: Safe-to-understand CLI for the ADM-005 trusted worker proof.

## 6. Complete automated test inventory

- `tests/test_adaptive.py` — 28 lines
- `tests/test_adaptive_worker.py` — 51 lines
- `tests/test_agent.py` — 104 lines
- `tests/test_ai_inspection.py` — 64 lines
- `tests/test_core.py` — 29 lines
- `tests/test_daemon.py` — 57 lines
- `tests/test_daemon_lifecycle.py` — 51 lines
- `tests/test_desktop.py` — 50 lines
- `tests/test_engine.py` — 64 lines
- `tests/test_local_transport_security.py` — 40 lines
- `tests/test_model_probe.py` — 48 lines
- `tests/test_ollama_direct.py` — 72 lines
- `tests/test_ollama_health.py` — 67 lines
- `tests/test_pipeline.py` — 106 lines
- `tests/test_project_lock.py` — 52 lines
- `tests/test_provision.py` — 60 lines
- `tests/test_queued_ai.py` — 61 lines
- `tests/test_recovery.py` — 82 lines
- `tests/test_regression.py` — 174 lines
- `tests/test_release.py` — 76 lines
- `tests/test_repair_recovery.py` — 61 lines
- `tests/test_setup.py` — 79 lines
- `tests/test_windows_startup.py` — 30 lines
- `tests/test_worker.py` — 126 lines

## 7. Exact commands and environment

From the extracted project root, with Python 3.10+ on PATH:

```powershell
python -B -m unittest discover -s tests -p "test_ollama_health.py" -v
python -B -m unittest discover -s tests -p "test_ollama_direct.py" -v
python -B -m unittest discover -s tests -q
python -m adm.ollama_health
python -m adm.ollama_cli --help
python -m adm.desktop_entry
```

The complete regression suite can take longer than the execution budget; use `adm.regression` checkpointing, preserve logs, and report any unfinished modules. Do not silently treat a timeout as a pass. The Windows GUI may require a graphical session; do not run the desktop command on a headless host.

## 8. Current capabilities vs evidence

| Capability | Current state |
|---|---|
| SQLite supervisor / worker / daemon | Implemented; targeted tests exist; Windows unattended acceptance pending |
| Windows startup / packaging preparation | Source exists; actual Windows executable/installer unverified |
| Desktop interface | Prototype; no final UX acceptance |
| Local Ollama direct patch and tests | Fake-model protocol tested; real inference NOT verified |
| Local model discovery | ADM-030 mock-server tests passed; live Ollama NOT verified |
| Crash journal / exclusive project lock | Implemented; focused tests passed |
| Security sandbox | NOT implemented; do not run arbitrary untrusted generated programs |
| Android / web / Windows application generation | NOT proven end-to-end |
| 16GB/32GB resource adaptation | Partial; no dual-machine Windows benchmarks |

## 9. Known defects, risks and remaining verification

1. No real Ollama model available in this execution environment; install and validate locally on a Windows test machine before claiming autonomous AI success.
2. Running generated code without OS-level sandbox can compromise host or network.
3. No verified one-click Windows installer or executable; Windows lifecycle tests are pending.
4. Full regression was not completed in this version.
5. The probe does not authenticate local Ollama or distinguish malicious loopback services; it is a diagnostic, not proof of model authenticity.
6. Installed model names do not prove model capability, RAM suitability, or actual inference success.
7. Repeated model failures require bounded autonomous retry with independent verification and persistent evidence.

## 10. Precise next engineering sequence

1. Integrate read-only Ollama health into GUI and preflight without exposing source, and provide plain-language readiness guidance.
2. Obtain real Ollama model on authorized Windows test hardware, run an unfamiliar broken-project repair, record model name, latency, test outcomes and complete evidence.
3. Build full autonomous spec-to-project workflow and independent verifier; prevent false-success reporting.
4. Implement OS-level sandbox for AI-produced code, deny outbound network by default, restrict filesystem and credentials.
5. Produce and actually run Windows packaged EXE/installer, automatic startup, recovery and uninstall.
6. Exercise 16GB and 32GB Windows configurations, fault injection, reboot and crash recovery, full regressions and delivery artifacts.

## 11. User involvement

**Nothing is required from the user for further portable-code development.** Real-model and Windows acceptance will eventually require access to authorized Windows test hardware with Ollama and a model installed, or explicit permission to perform those installations. User must not be asked to write or debug code.

## 12. Historical master handoff (verbatim preserved)

# Autonomous Development Manager — ADM-029 comprehensive cumulative master handoff

> **Read this entire file before making changes.** This is a development handoff, not a production-readiness certificate. The ADM-028 master handoff is preserved verbatim below, followed by all previous handoffs and the full source in this archive. Never infer that a feature is complete from a planned architecture, a simulated test, or a Linux-only test.

## 1. User intent and non-negotiable acceptance criteria

The owner is a non-programmer who wants ONE turnkey, autonomous Windows 11 application builder. They must be able to describe desired software in natural language once. ADM should independently plan, research where authorized, create source, resolve dependencies, build, run, test, diagnose, repair, re-test, package actual usable software, and explain genuine blockers in plain English. It must not require repeated prompts, app switching, coding knowledge, or manual interpretation of errors. The product must support Windows 11 machines with 16 GB and 32 GB RAM and select appropriate local AI models, context sizes, and concurrency without sacrificing testing quality. AI inference must be free/local by default, with **zero paid API charges**. Optional free cloud use requires explicit approval and strong privacy controls; no unapproved code exfiltration. Support Windows applications, Android APKs, and web applications eventually. All execution of AI-generated code must occur in a verified OS-level sandbox before general use. Background operation must survive reboot, failures, model interruptions, and context limits. Requirements must be traceable to independent acceptance tests, with real evidence and no fabricated claims.

The owner explicitly requires, **after every development segment**, a complete cumulative source ZIP (not only changed files) with every source module, tests, documentation, past handoffs, integrity manifest, build/setup/run commands, and an exceptionally detailed Markdown handoff sufficient for an entirely different AI or engineer to continue without loss of context. Every delivery must explicitly state whether any user input/action is needed. Prefer completing substantial work in one pass over micro-releases. Do not claim that chat itself can continue executing after the response ends; unattended work must be implemented in the installed application.

## 2. Actual current status — do not overstate

ADM-029 is a **Python prototype** with a SQLite-backed worker, background daemon, simple Tkinter desktop panel, controlled Ollama direct-repair adapter, repair journal, project locking, read-only AI repair reconciliation, and Windows startup/build *preparation*. It is **not** a fully autonomous natural-language-to-artifact app builder. It has **not** been built into and tested as a Windows EXE, **not** been accepted on 16/32 GB Windows systems, **not** demonstrated a genuine local model repair, **not** implemented an adequate OS-level sandbox, and **not** demonstrated reliable end-to-end EXE/APK/web creation. The real Ollama binary/model was unavailable in the current Linux environment. The complete regression suite is not established as passing for this release. No production-ready claim is warranted.

## 3. What changed in ADM-029

- `adm/queued_ai.py` now exports `inspect_repair(state, job_id)`: read-only reconciliation of the durable SQLite worker record with the recorded Ollama repair report and recovery journal. Validates job identity, extracts the evidence path from the actual queued command, reads the report, and requires **all** of the following before marking `verified=True`: worker state `passed`, exit code zero, report status `verified_direct_repair` or `baseline_passed`, and absence of an unfinished recovery journal. It never restarts or edits a job. Disagreements become `evidence_mismatch`, `failed_or_incomplete`, `invalid_evidence`, `blocked`, or `recovery_required` rather than success.
- `adm/ai_status.py`: read-only CLI: `python -m adm.ai_status --state <state-dir> --job <integer>`. Exit 0 only for recorded verification, exit 1 otherwise; prints JSON for inspection. This is *recorded-test verification*, not independent security or full functional acceptance.
- `tests/test_ai_inspection.py`: seven new tests exercise pending state, success with missing evidence, consistent success, conflicting failure, unresolved journal, corrupt report, and unknown job.
- Existing queued AI integration tests rerun; a full regression result is **not claimed**.

### Evidence actually obtained

- `python -B -m unittest discover -s tests -p test_ai_inspection.py -q` — **7/7 passed**.
- `python -B -m unittest discover -s tests -p test_queued_ai.py -q` — **5/5 passed**.
- These tests use synthetic worker state or a missing Ollama endpoint; they **do not** demonstrate real model inference or Windows operation.

## 4. Architecture and data flow

Natural-language app-builder workflow is the TARGET, not a completed feature. Existing flow for a **trusted disposable Python repair**:

1. An operator prepares a trusted project with `requirements.json`, existing `.py` app files, and independent `test_*.py` tests.
2. `adm.queued_ai.enqueue_repair` validates paths/model, allocates a unique evidence directory, and creates a SQLite worker job with `max_attempts=1` to prevent blind replay after a crash.
3. `adm.daemon` polls for jobs, and `adm.worker.WorkerSupervisor` atomically claims and executes the queued command, recording lifecycle events, heartbeats, logs, exit code, and final state.
4. `adm.ollama_cli` calls `adm.ollama_direct.direct_repair`, which takes an exclusive project lock, runs baseline tests, prepares a bounded local Ollama request, validates patch shape and syntax, saves original bytes to a crash journal, replaces permitted app source files, reruns tests, verifies protected files, and rolls back failed repairs.
5. `adm.queued_ai.inspect_repair` now reconciles worker completion and on-disk AI evidence; it refuses to call a job verified if evidence is absent, inconsistent, corrupt, or an unresolved journal remains.
6. The operator may inspect status via `python -m adm.ai_status --state ... --job ...`; the result does not by itself prove the product requirement was satisfied.

Trust boundaries: the Ollama endpoint is constrained to `http://127.0.0.1:<port>` with redirects/proxies disabled; this does **not** authenticate the model server. Generated Python tests still execute without OS isolation. The project lock is conservative and does not steal orphaned locks. Recovery refuses unexpected file changes to avoid overwriting user work. None of these is equivalent to a secure sandbox.

## 5. Complete module responsibilities

### Runtime and tooling

- `adm/__init__.py` — 1 lines; first noncomment line: `from .core import Supervisor, resources, mode`. Read implementation and tests before modifying.
- `adm/__main__.py` — 22 lines; first noncomment line: `import argparse, json, time`. Read implementation and tests before modifying.
- `adm/adaptive.py` — 53 lines; first noncomment line: `Resource-aware admission decisions; never changes verification requirements.`. Read implementation and tests before modifying.
- `adm/agent.py` — 195 lines; first noncomment line: `ADM-003: guarded OpenCode/Ollama adapter and evidence-backed repair trial.`. Read implementation and tests before modifying.
- `adm/agent_cli.py` — 40 lines; first noncomment line: `ADM-003 real local OpenCode agent trial CLI.`. Read implementation and tests before modifying.
- `adm/ai_status.py` — 18 lines; first noncomment line: `Read-only CLI for reconciling a queued AI repair with its evidence.`. Read implementation and tests before modifying.
- `adm/cli.py` — 25 lines; first noncomment line: `Human-friendly ADM-002 proof command.`. Read implementation and tests before modifying.
- `adm/core.py` — 67 lines; first noncomment line: `Durable, resource-aware command verification supervisor (stdlib only).`. Read implementation and tests before modifying.
- `adm/daemon.py` — 103 lines; first noncomment line: `Persistent unattended trusted-job runner with observable lifecycle state.`. Read implementation and tests before modifying.
- `adm/desktop.py` — 95 lines; first noncomment line: `Small dependency-free desktop control panel for the trusted-job supervisor.`. Read implementation and tests before modifying.
- `adm/desktop_entry.py` — 4 lines; first noncomment line: `Frozen GUI entrypoint. Must be built and runtime-tested on Windows.`. Read implementation and tests before modifying.
- `adm/engine.py` — 127 lines; first noncomment line: `ADM-002: bounded, evidence-backed autonomous repair proof (standard library).`. Read implementation and tests before modifying.
- `adm/model_probe.py` — 98 lines; first noncomment line: `Local-only Ollama model readiness and bounded inference smoke benchmark.`. Read implementation and tests before modifying.
- `adm/ollama_cli.py` — 21 lines; first noncomment line: `Run a local Ollama direct-repair trial on a trusted disposable project.`. Read implementation and tests before modifying.
- `adm/ollama_direct.py` — 192 lines; first noncomment line: `Direct local Ollama repair trial, with deterministic evidence and guarded file edits.`. Read implementation and tests before modifying.
- `adm/pipeline.py` — 99 lines; first noncomment line: `ADM-006: durable, fail-closed supervised local agent proof.`. Read implementation and tests before modifying.
- `adm/pipeline_cli.py` — 28 lines; first noncomment line: `Supervised local AI proof: no paid API, no automatic execution of unknown projects.`. Read implementation and tests before modifying.
- `adm/preflight.py` — 49 lines; first noncomment line: `Read-only diagnostics for local-only Ollama / OpenCode availability.`. Read implementation and tests before modifying.
- `adm/project_lock.py` — 40 lines; first noncomment line: `Fail-closed cross-process project ownership for source-changing AI jobs.`. Read implementation and tests before modifying.
- `adm/provision.py` — 80 lines; first noncomment line: `ADM-008: resumable, dependency-aware local provisioning coordinator.`. Read implementation and tests before modifying.
- `adm/queued_ai.py` — 111 lines; first noncomment line: `Queue a bounded local-Ollama repair for the persistent ADM supervisor.`. Read implementation and tests before modifying.
- `adm/recovery.py` — 76 lines; first noncomment line: `Bounded, verified workspace snapshot/restore for disposable repair trials.`. Read implementation and tests before modifying.
- `adm/regression.py` — 183 lines; first noncomment line: `Isolated, bounded regression runner; does not silently turn timeouts into passes.`. Read implementation and tests before modifying.
- `adm/release.py` — 119 lines; first noncomment line: `Reproducible source release and opt-in Windows executable build planning.`. Read implementation and tests before modifying.
- `adm/release_entry.py` — 4 lines; first noncomment line: `Frozen Windows entrypoint for ADM supervisor (not a graphical interface).`. Read implementation and tests before modifying.
- `adm/repair_recovery.py` — 88 lines; first noncomment line: `Crash journal for local-model source replacements.`. Read implementation and tests before modifying.
- `adm/setup.py` — 113 lines; first noncomment line: `ADM-007: auditable, explicit-consent local dependency provisioning.`. Read implementation and tests before modifying.
- `adm/setup_cli.py` — 30 lines; first noncomment line: `Read-only setup plan by default; --apply is an explicit opt-in.`. Read implementation and tests before modifying.
- `adm/windows_startup.py` — 63 lines; first noncomment line: `Opt-in Windows logon launcher. No installation occurs without user action.`. Read implementation and tests before modifying.
- `adm/worker.py` — 209 lines; first noncomment line: `ADM-005 durable single-owner worker supervision for TRUSTED commands.`. Read implementation and tests before modifying.
- `adm/worker_cli.py` — 41 lines; first noncomment line: `Safe-to-understand CLI for the ADM-005 trusted worker proof.`. Read implementation and tests before modifying.

### Test modules

- `tests/test_adaptive.py` — 28 lines; first noncomment line: `import unittest`. Read implementation and tests before modifying.
- `tests/test_adaptive_worker.py` — 51 lines; first noncomment line: `import sys`. Read implementation and tests before modifying.
- `tests/test_agent.py` — 104 lines; first noncomment line: `import json`. Read implementation and tests before modifying.
- `tests/test_ai_inspection.py` — 64 lines; first noncomment line: `import json`. Read implementation and tests before modifying.
- `tests/test_core.py` — 29 lines; first noncomment line: `import sys,tempfile,unittest`. Read implementation and tests before modifying.
- `tests/test_daemon.py` — 57 lines; first noncomment line: `import sys`. Read implementation and tests before modifying.
- `tests/test_daemon_lifecycle.py` — 51 lines; first noncomment line: `import json`. Read implementation and tests before modifying.
- `tests/test_desktop.py` — 50 lines; first noncomment line: `import tempfile`. Read implementation and tests before modifying.
- `tests/test_engine.py` — 64 lines; first noncomment line: `import json`. Read implementation and tests before modifying.
- `tests/test_local_transport_security.py` — 40 lines; first noncomment line: `Regression tests ensuring local AI transport never follows redirects.`. Read implementation and tests before modifying.
- `tests/test_model_probe.py` — 48 lines; first noncomment line: `import io`. Read implementation and tests before modifying.
- `tests/test_ollama_direct.py` — 72 lines; first noncomment line: `import json`. Read implementation and tests before modifying.
- `tests/test_pipeline.py` — 106 lines; first noncomment line: `import json`. Read implementation and tests before modifying.
- `tests/test_project_lock.py` — 52 lines; first noncomment line: `import json`. Read implementation and tests before modifying.
- `tests/test_provision.py` — 60 lines; first noncomment line: `import json`. Read implementation and tests before modifying.
- `tests/test_queued_ai.py` — 61 lines; first noncomment line: `import json`. Read implementation and tests before modifying.
- `tests/test_recovery.py` — 82 lines; first noncomment line: `import json`. Read implementation and tests before modifying.
- `tests/test_regression.py` — 174 lines; first noncomment line: `import tempfile`. Read implementation and tests before modifying.
- `tests/test_release.py` — 76 lines; first noncomment line: `import hashlib`. Read implementation and tests before modifying.
- `tests/test_repair_recovery.py` — 61 lines; first noncomment line: `import json`. Read implementation and tests before modifying.
- `tests/test_setup.py` — 79 lines; first noncomment line: `import subprocess`. Read implementation and tests before modifying.
- `tests/test_windows_startup.py` — 30 lines; first noncomment line: `import os`. Read implementation and tests before modifying.
- `tests/test_worker.py` — 126 lines; first noncomment line: `import os`. Read implementation and tests before modifying.

## 6. Setup, verification, and operational commands

Extract the entire ZIP into a new directory. Use Python 3.10+ (actual supported versions must be independently verified). No cloud AI credentials are required. From the package root:

```powershell
python -B -m unittest discover -s tests -p test_ai_inspection.py -v
python -B -m unittest discover -s tests -p test_queued_ai.py -v
python -B -m unittest discover -s tests -q
python -m adm.ai_status --state C:\path\to\state --job 1
python -m adm.ollama_cli --help
python -m adm.queued_ai --help
python -m adm.daemon --help
```

The complete suite may take time or hang; use `adm.regression`'s checkpointing with module logs to diagnose. Never mark an interrupted suite as passed. For a real AI acceptance test, install Ollama on a **trusted test Windows machine**, download a locally suitable free coding model, confirm model readiness, and run the direct repair on a disposable fixture with known failing tests and separate acceptance tests. Preserve the raw model transcript, before/after source hashes, build/test logs, timing, and evidence report. Do not use real/private code until OS sandboxing is validated.

## 7. Security, integrity, and crash recovery

- Never run arbitrary AI-generated code with administrator rights, broad home-directory access, or unrestricted network privileges. A real Windows sandbox (restricted token/AppContainer/VM or equivalent with measured enforcement) is a blocker for untrusted projects.
- Loopback Ollama transport and redirect blocking are defense-in-depth, not full confidentiality. Treat model responses as untrusted.
- Never automatically remove a project lock or replay a possibly running AI job. Verify PID ownership, project state, and worker lifecycle first.
- If `repair-journal.json` exists, STOP other workers, inspect changes and use the documented `recover_journal` mechanism only when its safety checks pass. It refuses to overwrite unexpected external modifications.
- SQLite WAL is used for job state; verify persistence and recovery across power loss on Windows, including filesystem/antivirus interactions.
- The source ZIP integrity manifest must be independently verified; its hashes detect accidental corruption, not a malicious archive author.
- No payment API or unapproved cloud calls. Never silently install toolchains or models without the necessary permissions and licensing checks.

## 8. Known gaps, defects, and unverified acceptance

1. **Critical:** No demonstrated real Ollama inference repairing a genuinely broken project. Fake HTTP server tests prove protocol behavior only.
2. **Critical:** No operating-system sandbox for untrusted source/test execution. Prototype is for trusted disposable projects.
3. **Critical:** No end-to-end natural-language requirement → project creation → iterative build/repair → distributable artifact orchestrator.
4. **Critical:** No tested Windows EXE/installer or one-click onboarding; no acceptance on 16 GB and 32 GB machines.
5. **High:** No reliable unattended model/toolchain install/selection and resource admission demonstrated end-to-end.
6. **High:** Windows restart/resume, orphan lock handling, safe journal recovery, and process-tree cleanup need fault injection on real Windows.
7. **High:** No independent acceptance for Android APK, Windows EXE, and web deliverables.
8. **High:** The full regression suite is not verified for ADM-029. Previous version's partial results are historical only.
9. **Medium:** AI report status and exit-code reconciliation are useful but do not independently validate output semantics, security, or artifact quality.
10. **Medium:** UI remains an early Tkinter control panel, not the requested nontechnical autonomous builder.
11. **Medium:** Need stronger limits on input/project size, prompt budgets, model context, and model-generated file operations.
12. **Medium:** Need independent, signed/reproducible packaging and update/uninstall validation.

## 9. Exact prioritized next development sequence

1. **Demonstrate real local-model inference** with a reproducible failing Python fixture and separate verifier, not a mocked server. Capture negative and positive runs, exact model digest, and full evidence.
2. Build a genuine **autonomous orchestration loop** that accepts a plain-language specification, generates a project plan and source, runs tests, diagnoses errors, retries within resource limits, and emits a real artifact or specific blocker. Store durable checkpoints and never replay unsafe steps.
3. Introduce **Windows OS-level isolation** before executing arbitrary generated code; write adversarial escape tests (filesystem, network, process, persistence, secrets).
4. Build the **Windows EXE and installer** in a real Windows CI runner and run it on 16 GB/32 GB systems; include installer/upgrader/uninstaller and signed artifact validation as appropriate.
5. Finish one-window GUI: prompt, project queue, progress, error explanation, pause/resume, outputs, and human approval for sensitive operations.
6. Implement toolchain plugins for Windows, Android, and web, with actual build/run/test/install smoke tests and reproducible packaging.
7. Perform full fault-injection, long-duration unattended operation, full regression, security audit, and traceable acceptance for every requirement.
8. Deliver cumulative source + **even more detailed** next master handoff and SHA-256 manifest after each segment.

## 10. User action required

**None to inspect or continue portable Python development.** A genuine real-model and Windows acceptance test will eventually require access to a Windows 11 machine or a Windows CI runner with sufficient RAM, an installed local Ollama model, and authorization for toolchain installation. The user should not be asked to write code. Clearly distinguish what is required *now* from what is required for later verification.

## 11. Prior master handoff — preserved in full

---

# ADM-028 — COMPLETE CUMULATIVE MASTER HANDOFF

## Read this first — status and nonnegotiable requirements
This document supplements and incorporates the FULL ADM-027 master handoff below. Preserve all prior requirements and decisions. The user is a non-programmer seeking a genuinely autonomous, offline-first, zero-paid-API Windows app builder. It must accept a plain-language specification once, research/plan/code/test/debug/repair/package deliverables, resume after interruptions, use free local AI, and present nontechnical outcomes. Support 16 GB and 32 GB Windows machines. Every development segment must ship complete cumulative source plus extremely detailed Markdown handoff and verified manifest. Never report simulated AI as live inference, or Linux tests as Windows acceptance.

## ADM-028 change summary
1. `adm/ollama_direct.py`: introduced `_RejectRedirects` and a dedicated urllib opener configured with `ProxyHandler({})`. Direct repair HTTP requests now refuse all redirects instead of following them, preventing inadvertent transfer of source and prompts to redirected endpoints. Endpoint still requires exact 127.0.0.1 HTTP with explicit port, no path, userinfo, query or fragment.
2. `adm/model_probe.py`: same redirect refusal and proxy bypass for Ollama discovery/smoke requests. Injected test opener remains supported.
3. `tests/test_local_transport_security.py`: two real loopback HTTP-server tests prove redirects are rejected for direct repair and model discovery.
4. Existing Ollama direct repair and model probe tests rerun.

## Evidence obtained in this segment
- `python -B -m unittest discover -s tests -p test_local_transport_security.py -v`: 2/2 passed.
- `python -B -m unittest discover -s tests -p test_ollama_direct.py -q`: 6/6 passed.
- `python -B -m unittest discover -s tests -p test_model_probe.py -q`: 10/10 passed.
- Combined targeted evidence: 18/18 passed.
- Attempted whole-suite `python -B -m unittest discover -s tests -q` with a bounded execution window; no successful full-suite result was obtained. Treat full regression as **NOT VERIFIED** for ADM-028.
- Ollama executable not found in this Linux development environment; **NO LIVE MODEL INFERENCE VERIFIED**.
- No Windows EXE or installer built; Windows acceptance **NOT VERIFIED**.

## Security interpretation and residual risks
Blocking redirects and ignoring proxies protects the local Ollama transport from one class of accidental exfiltration, but does not guarantee all source data stays local if other components are misconfigured. The model process, Python test subprocesses and generated code still run without an operating-system security sandbox. Local services can be malicious; HTTP loopback is not authenticated. There remain TOCTOU/path-race concerns and limitations in atomic multi-file changes. Do not run untrusted projects or give ADM privileged access until security isolation is built and tested. No paid API should be used.

## Module-by-module inventory (ADM-028)
- `adm/__init__.py` — from .core import Supervisor, resources, mode
- `adm/__main__.py` — import argparse, json, time from .core import Supervisor,resources,mode p=argparse.ArgumentParser(description='ADM architecture proof — local command supervisor')
- `adm/adaptive.py` — """Resource-aware admission decisions; never changes verification requirements.  All figures are snapshots, not reservations. The caller must re-check immediately
- `adm/agent.py` — """ADM-003: guarded OpenCode/Ollama adapter and evidence-backed repair trial.  This is NOT a security sandbox. Only use trusted disposable projects until an OS
- `adm/agent_cli.py` — """ADM-003 real local OpenCode agent trial CLI.""" import argparse import json
- `adm/cli.py` — """Human-friendly ADM-002 proof command.""" import argparse import json
- `adm/core.py` — """Durable, resource-aware command verification supervisor (stdlib only).""" import json, os, platform, sqlite3, subprocess, time, hashlib, shutil from pathlib import Path
- `adm/daemon.py` — """Persistent unattended trusted-job runner with observable lifecycle state.  This is not an OS sandbox or a Windows startup service. A running daemon
- `adm/desktop.py` — """Small dependency-free desktop control panel for the trusted-job supervisor.  Tkinter is supplied by many Python installations but must be verified on target
- `adm/desktop_entry.py` — """Frozen GUI entrypoint. Must be built and runtime-tested on Windows.""" from adm.desktop import main if __name__ == '__main__':
- `adm/engine.py` — """ADM-002: bounded, evidence-backed autonomous repair proof (standard library).""" from __future__ import annotations import hashlib
- `adm/model_probe.py` — """Local-only Ollama model readiness and bounded inference smoke benchmark.  This is not a coding-ability benchmark. Only loopback HTTP is contacted; callers
- `adm/ollama_cli.py` — """Run a local Ollama direct-repair trial on a trusted disposable project.""" import argparse import json
- `adm/ollama_direct.py` — """Direct local Ollama repair trial, with deterministic evidence and guarded file edits.  Only for trusted disposable Python projects. This is NOT an OS sandbox.
- `adm/pipeline.py` — """ADM-006: durable, fail-closed supervised local agent proof.  Runs the existing agent CLI in a supervised worker process. This is not a
- `adm/pipeline_cli.py` — """Supervised local AI proof: no paid API, no automatic execution of unknown projects.""" import argparse import json
- `adm/preflight.py` — """Read-only diagnostics for local-only Ollama / OpenCode availability.""" from __future__ import annotations import json
- `adm/project_lock.py` — """Fail-closed cross-process project ownership for source-changing AI jobs.  An orphaned lock is intentionally not stolen: an operator must verify that the
- `adm/provision.py` — """ADM-008: resumable, dependency-aware local provisioning coordinator.  This is not an unattended installer. Every install/download requires explicit approval.
- `adm/queued_ai.py` — """Queue a bounded local-Ollama repair for the persistent ADM supervisor.  Trusted disposable projects only. This is NOT a sandbox. No paid API calls.
- `adm/recovery.py` — """Bounded, verified workspace snapshot/restore for disposable repair trials.  Not a sandbox or a replacement for Git. Refuses symlinks and oversized workspaces.
- `adm/regression.py` — """Isolated, bounded regression runner; does not silently turn timeouts into passes.""" from __future__ import annotations import argparse
- `adm/release.py` — """Reproducible source release and opt-in Windows executable build planning.  Does not install dependencies or run untrusted code. Windows binaries require
- `adm/release_entry.py` — """Frozen Windows entrypoint for ADM supervisor (not a graphical interface).""" from adm.daemon import main if __name__ == "__main__":
- `adm/repair_recovery.py` — """Crash journal for local-model source replacements.  A repair job must be stopped before recovery; this module does not kill workers.
- `adm/setup.py` — """ADM-007: auditable, explicit-consent local dependency provisioning.  No installation, download, or process execution happens on import or in plan().
- `adm/setup_cli.py` — """Read-only setup plan by default; --apply is an explicit opt-in.""" import argparse import json
- `adm/windows_startup.py` — """Opt-in Windows logon launcher. No installation occurs without user action.  Task Scheduler starts a dedicated supervisor at user logon. This is NOT
- `adm/worker.py` — """ADM-005 durable single-owner worker supervision for TRUSTED commands.  Not an OS sandbox or a reboot autorun service. Running processes are reclaimed
- `adm/worker_cli.py` — """Safe-to-understand CLI for the ADM-005 trusted worker proof.""" import argparse import json

## Test inventory (ADM-028)
- `tests/test_adaptive.py` — 8 declared test methods.
- `tests/test_adaptive_worker.py` — 4 declared test methods.
- `tests/test_agent.py` — 10 declared test methods.
- `tests/test_core.py` — 6 declared test methods.
- `tests/test_daemon.py` — 4 declared test methods.
- `tests/test_daemon_lifecycle.py` — 3 declared test methods.
- `tests/test_desktop.py` — 7 declared test methods.
- `tests/test_engine.py` — 9 declared test methods.
- `tests/test_local_transport_security.py` — 2 declared test methods.
- `tests/test_model_probe.py` — 10 declared test methods.
- `tests/test_ollama_direct.py` — 6 declared test methods.
- `tests/test_pipeline.py` — 8 declared test methods.
- `tests/test_project_lock.py` — 6 declared test methods.
- `tests/test_provision.py` — 8 declared test methods.
- `tests/test_queued_ai.py` — 6 declared test methods.
- `tests/test_recovery.py` — 7 declared test methods.
- `tests/test_regression.py` — 33 declared test methods.
- `tests/test_release.py` — 8 declared test methods.
- `tests/test_repair_recovery.py` — 5 declared test methods.
- `tests/test_setup.py` — 14 declared test methods.
- `tests/test_windows_startup.py` — 4 declared test methods.
- `tests/test_worker.py` — 11 declared test methods.

## Setup and execution
From an extracted archive root, use a Python version compatible with the source and execute `python -B -m unittest discover -s tests -q`. For a focused safety check: `python -B -m unittest discover -s tests -p test_local_transport_security.py -v`. Inspect CLI entry points in `adm/ollama_cli.py`, `adm/worker_cli.py`, `adm/daemon.py`, and `adm/desktop_entry.py` before running. Ollama must be separately installed and a local model downloaded to perform real inference. Use trusted disposable projects only. On Windows, package using the release scripts, but DO NOT treat an untested build as a release.

## Precise next actions for another developer/AI
1. Run checkpointed full regression and capture complete evidence; diagnose any stalled modules without claiming success prematurely.
2. Validate the Ollama integration against a genuine installed local coding model, with real failing project tests and independent verification.
3. Build OS-level sandbox and file-system/process/network containment for AI-generated code, with adversarial escape tests.
4. Add crash/fault-injection and restart tests for project locks and repair journals; validate no lost user changes.
5. Implement unattended end-to-end plan→code→test→repair→artifact loop, not merely individual queued repair jobs.
6. Build and verify Windows EXE and installer on real 16 GB and 32 GB machines; test startup, shutdown, upgrades and uninstall.
7. Complete the nontechnical desktop UX and support Android APK/web/Windows outputs with verified toolchains.
8. Every future delivery: full cumulative source ZIP, all tests and prior handoffs, a larger master handoff, exact test evidence and known limitations, hashes, and a statement of what is needed from the user.

## What is needed from the user
Nothing to continue writing and testing portable code. To complete real Windows acceptance, access to a Windows 11 test machine or a Windows CI runner is eventually required. For local model acceptance, an Ollama-capable host with the approved free model is required. Do not ask the user to code or configure a developer toolchain manually.

---

# FULL PREVIOUS MASTER HANDOFF — PRESERVED VERBATIM

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

