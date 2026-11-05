# ADM — Autonomous Development Manager · Master Handoff 052

| | |
|---|---|
| **Repository** | https://github.com/DevTunaSoft/autonomous-dev-manager |
| **Branch / commit** | `main` @ `d4c2c7c` (code) · handoff committed on top |
| **Version** | `0.5.2-dev` (`adm/diagnostics.py: VERSION`) |
| **Date** | 2026-11-05 |
| **Language / runtime** | Python 3.12 (the version the EXE bundles); code also runs on 3.13 |
| **Platform** | Windows 11 desktop app; test suite is cross-platform |
| **Size** | 50 modules in `adm/` (~6,640 LOC), 64 test files, 20 fuzz harnesses |
| **Test status** | `OVERALL: PASS; 442 completed tests` |
| **GUI** | Dark-theme dashboard, **plain Tkinter** (no third-party UI deps) |

This handoff is written for an engineer reviewing the project cold and for the maintainers who will extend it. It is intentionally detailed: it documents the product constraints, the architecture, every module group with its key API, the on-disk data formats, the security/sandbox model, the build pipeline semantics, the packaging subsystem, the testing and adversarial-fuzzing strategy, the CI, and an explicit extension guide. Sections 1–4 are orientation; 5–14 are the system in depth; 15–18 are operations; 19–23 are status, caveats, and how to extend.

---

## Table of contents

1. Executive summary
2. Product definition and non-negotiable constraints
3. Glossary
4. Architecture at a glance
5. Repository layout
6. Module reference (by subsystem, with key API)
7. On-disk data model and file formats
8. State directory layout
9. The build pipeline in depth
10. Security and the Windows sandbox
11. Free-first AI backends
12. The packaging subsystem (the 052 work)
13. Diagnostics, logging, and recovery
14. Concurrency and Windows-specific hardening
15. Testing: inventory and how to run
16. Adversarial fuzzing: all 11 rounds
17. CI/CD: what is proven, and where
18. Building the Windows EXE
19. What the user must provide
20. Known limitations, caveats, and open decisions
21. Extension guide (how to add things safely)
22. Suggested review order
23. Appendix: statuses, events, commit highlights

---

## 1. Executive summary

ADM lets a person who **cannot write code** describe software in plain English and get a working Windows program back. A **free, local AI** (Ollama first) plans the program, writes it, writes tests derived from the user's plain-language checks, runs those tests inside a **locked-down Windows sandbox**, repairs the code until the tests pass, verifies twice, and then **packages** the result into a standalone `.exe`. The product's defining value is **honesty**: a build is only ever reported as "built" after its own tests genuinely pass in the sandbox, and a program is only packaged from such a build. Isolated or faked tests are never presented as a working product.

Everything is sized for a **16 GB Windows 11 PC** and uses **only free** AI (a paid account is never required). Generated code is treated as hostile: it gets no network by default and cannot touch anything outside its own project folder.

As of cycle 052 the system has: the full intake→plan→approve→build→repair→package pipeline; a dark Tkinter dashboard; bundled embeddable Python; self-diagnostics; 435 passing tests; and 11 adversarial fuzz rounds wired into CI, each of which found and fixed real defects. The one unfinished piece is that the packaging step's dependency (PyInstaller) is not yet bundled onto the end-user PC — it is proven on CI, and the app says so honestly until a future update bundles it.

---

## 2. Product definition and non-negotiable constraints

**Who it is for:** non-programmers ("know zero about coding"). The UX must never assume coding knowledge.

**Target machine:** Windows 11 Pro, 16 GB RAM, SATA SSD. All resource decisions assume this.

**The constraints below are load-bearing. They are enforced in code and must not be weakened without a deliberate decision:**

1. **Free-only AI.** Local model first (Ollama), then genuinely free cloud tiers. A paid account is **optional, never required**.
2. **Generated code is contained.** No internet by default; it must **refuse and report** any filesystem path outside its own project folder.
3. **Remote model use is opt-in.** Because a prompt to a remote model contains the user's own source, remote use requires **explicit user approval** each time.
4. **No fake success.** A build is "built" only after its tests pass for real, **verified twice** in the sandbox. Trivial tests (that pass before any code is written) are rejected, not celebrated.
5. **Per-release deliverable.** Every release ships a cumulative **source ZIP**, a robust **Markdown handoff** (this file), and an explicit **"what the user must provide"** statement.

---

## 3. Glossary

- **Plan** — the structured result of asking the local model to interpret the user's request: a title, a description, a list of plain-language *checks*, and optional clarifying *questions*. Stored as `plan.json`, unapproved until the user presses Approve.
- **Check** — one plain-language acceptance criterion from the plan (e.g. "adds two numbers"). Checks become the frozen test suite.
- **Frozen tests** — the test file generated from the checks *before* any program is written; it is not allowed to change during repair, so the program is forced to satisfy the user's intent rather than the tests being bent to the code.
- **Baseline-must-fail guard** — if the generated tests pass against the empty scaffold (no program yet), they are trivial and the build is rejected (`rejected_trivial_tests`).
- **Direct repair loop** — run tests in the sandbox → ask the model for a patch → apply → re-run, up to a limit; success requires passing twice.
- **Sandbox** — a Windows confinement (separate low-priv account + firewall + ACLs + Job Object) in which generated code and its tests run.
- **Evidence** — the saved artifacts of a build (test output, report) under a stable per-plan evidence directory.
- **Report** — the dict describing a build's outcome (see §7), persisted under `builds/` and read by the dashboard's stat tiles and the packaging gate.

---

## 4. Architecture at a glance

```
          ┌────────────────────────── adm/dashboard.py (Tkinter GUI) ──────────────────────────┐
          │  New request → Plan → Approve → Pipeline stages → Package → Diagnostics / Export     │
          └───────┬───────────────────────────────┬────────────────────────────┬───────────────┘
                  │                                 │                             │
            intake.py                          build.py                      package.py
         request→plan→approve          orchestrate build+repair           verified build → EXE
                  │                                 │                             │
                  │                     ollama_direct.py  ◄── backends.py (free-first AI transport)
                  │                     direct repair loop        model output parsing, re-ask
                  │                                 │
                  │                           sandbox.py  ◄── provision.py   (Windows confinement)
                  │                     run tests as admsandbox, no net, path-locked
                  │                                 │
             project_lock.py  ───────────── held across the WHOLE build ───────────────┐
                                                                                        │
   diagnostics.py (append-close log, self_check, export)   recovery.py / repair_recovery.py
   worker.py / daemon.py / queued_ai.py (autonomous queue)  release.py / regression.py / selftest.py
```

**Request lifecycle (happy path):**

```
plain text ─intake.validate_request→ create_plan ─(local model)→ PLAN(plan.json, unapproved)
   → user reviews → intake.approve → build.run_build (under project_lock):
        generate frozen tests → scaffold → baseline-must-fail guard →
        ollama_direct.direct_repair (sandbox) → verified twice → report{status:'built'}
   → dashboard.finish_build: if built → package.package_project → dist/<name>.exe
```

---

## 5. Repository layout

```
adm/                50 modules — the application (see §6)
tests/              64 test files — unit, integration, hardening, regression (see §15)
tools/
  fuzz_adversarial{,2..11}.py   11 adversarial harnesses (see §16)
  verify_package.py             CI: package a tiny project, run the EXE, assert output
  fake_ollama.py                a fake model server for deterministic tests
  sandbox_probe.py / sandbox_live_check.py / sandbox_scan.py   sandbox verification
  screenshot_gui.py             render the dashboard for visual review
  verify_bundled_python.py / verify_request_window.py / make_handoff.py
.github/workflows/
  windows-desktop-build.yml     main CI (build job + full-regression job) — see §17
  sandbox-probe.yml             sandbox confinement proof on a real Windows runner
  gui-screenshots.yml           dashboard screenshots
BUILD-WINDOWS-DESKTOP.cmd       one-click PyInstaller EXE build (Windows)
VERIFY-WINDOWS-DESKTOP.ps1      post-build verification
README.md
HANDOFF-0NN-MASTER.md           cumulative handoffs (this is 052)
ADM-0NN-*.json / *.md           per-release manifests, SHA256 sets, evidence
```

---

## 6. Module reference (by subsystem, with key API)

Signatures below are the public surface a reviewer will care about; see the source for full parameters.

### 6.1 Entry points, CLI, GUI
- **`dashboard.py`** (689 LOC) — the dark Tkinter dashboard. Module-level pure helpers `collect_stats(state)->dict` and `_fmt_uptime(seconds)->str` are unit-tested; `main(...)` builds the window. Closures of interest: `set_stage`, `on_build_event`, `finish_build`, `start_package`, `finish_package` (the build→package gate). `win.report_callback_exception` logs + shows a messagebox.
- **`__main__.py` / `cli.py`** — top-level entry and command dispatch.
- **`intake_gui.py`, `desktop_entry.py`** — the request window and desktop entry wiring.
- **`agent_cli.py`, `ollama_cli.py`, `pipeline_cli.py`, `setup_cli.py`, `worker_cli.py`** — thin CLI frontends used by scripts/CI.

### 6.2 Intake — request → plan → approval (`intake.py`, 300 LOC)
Key API: `validate_request`, `slugify`, `check_existing_folder` (strips `\\?\`; OSError→SafetyError on bad/long paths), `describe_existing`, `plan_prompt`, `parse_plan`, `create_plan(...)` (asks the model, saves unapproved), `load_plan` (rejects non-dict), `approve` (atomic folder mkdir with retry), `_save` (unique temp name + `os.replace` retry loop for Windows), `require_approved`, `plan_text`, `test_model`, `choose_model`. Plan integrity is protected by a `sha256` over the body fields (`_digest`/`_body`).

### 6.3 Build pipeline (`build.py`, 335 LOC)
Key API: `build_from_plan(...)` (the whole build, run **inside** `project_lock.exclusive_project`), `run_build(...)` (dashboard path: stable evidence dir + persisted report), `scaffold`, `is_adm_project`, `amend_project`, `validate_tests`, `requirements_doc`, `_recover_interrupted`, `_reset_scaffold`, `builds_root`, `evidence_root`, `_safe_evidence`, `save_report`, `_say(on_event,...)`. Produces the report statuses in §7/§23.

### 6.4 Repair loop & AI transport
- **`ollama_direct.py`** (315 LOC) — `request_json` (tolerant parse + retry), `request_patch`, `apply_patch` (envelope guard; catches `SyntaxError/ValueError/RecursionError` on compile), `_direct_repair_unlocked` / `direct_repair` (the loop; `on_event`/`_emit` streaming), `_RejectRedirects` (HTTP redirect refusal).
- **`backends.py`** (243 LOC) — `safe_model` (rejects `..`/leading slash), `extract_json` + `_match_bracket` + `_no_trailing_commas` + `JSON_REMINDER` (tolerant model-output parsing with one auto re-ask), `request_json_openai`, `make_generator`, `make_json_generator`, `probe_local_servers` (catches RecursionError/TypeError).
- **`ollama_health.py`, `model_probe.py`, `model_selection.py`, `ai_status.py`** — local model detection, health, selection and status.

### 6.5 Autonomous worker/queue
- **`worker.py`** (286 LOC) — `WorkerSupervisor`, `pid_alive`/`_windows_pid_alive`, `terminate_tree`, `_open_db` (retry on transient Windows WAL lock), `run_once` (validates argv before `Popen`).
- **`core.py`** — `add` (rejects non-list argv; caps 1..1000). **`daemon.py`** — `read_status` (tolerant of corrupt/non-dict), `serve` (installs excepthook). **`queued_ai.py`** — `enqueue_repair`/`inspect_repair`. **`adaptive.py`, `agent.py`** — agent helpers (`atomic_json` with `default=str`; `safe_local_model`).

### 6.6 Packaging & runtime (052)
- **`package.py`** (159 LOC) — see §12. `exe_name`, `plan_title`, `write_entry`, `find_packager_python`, `package_command`, `package_project`, and the `ENTRY` template.
- **`runtime_install.py`** (105 LOC) — `shared_python_dir`, `fixup_pth`, `ensure_shared_python` (ICACLS RX /T for the sandbox user), `bundled_source`, `ensure_runtime`. **`pyruntime.py`** — embeddable-runtime helpers.

### 6.7 Sandbox & safety
- **`sandbox.py`** (221 LOC) — `SandboxError(SafetyError)`, `is_admin`, `NEED_ADMIN`, `setup_commands`, `acl_grant_command`, `cmdline_for` (rejects bad chars/empty/trailing backslash), `harden_commands`, `refuse_hardened_location` (strips `\\?\`/`\\.\`), `provision`, `run_confined`, `make_runner(pw)`.
- **`provision.py`** — provision the account/firewall/ACLs. **`engine.py`** — `SafetyError`, demo/broken-project helpers. **`project_lock.py`** (`exclusive_project`, `_acquire`/`_release`; kernel file lock). **`windows_startup.py`** — startup install (SafetyError).

### 6.8 Diagnostics, recovery, release
- **`diagnostics.py`** (220 LOC) — `log_line` (append-and-close; `_rotate_if_big`), `install_excepthook`, `self_check(state)` (Python/Local AI/Bundled Python/Sandbox/Disk/Write/GUI), `collect`, `export_bundle`, `VERSION`.
- **`recovery.py`, `repair_recovery.py`** — interrupted-build recovery; repair-journal validation.
- **`release.py`** (136 LOC) — `source_files`, `create_source_release`, `verify_source_release` (zip-bomb guards: 50MB/entry, 300MB total, 8MB manifest), `windows_build_plan`, `build_windows_executable`.
- **`regression.py`** — the test runner. **`selftest.py`** — `SMOKE_MODULES` (imports every module incl. `adm.package`). **`repomap.py`, `acceptance.py`, `live_acceptance.py`, `setup.py`, `firstrun.py`, `theme.py`, `context.py`, `preflight.py`**.

---

## 7. On-disk data model and file formats

**`plan.json`** (created by `intake.create_plan`, protected by `sha256`):
```json
{
  "id": "20260105-143000-ab12cd",
  "status": "awaiting_approval | needs_answers | approved | rejected",
  "request": "<the user's plain-language request>",
  "mode": "new | existing",
  "folder": "<absolute project folder>",
  "model": "ollama/<name>",
  "created": 1767623400.0,
  "content": {
    "title": "...", "description": "...",
    "tests": ["check 1", "check 2", ...],   // plain-language checks → frozen tests
    "questions": ["optional clarifying question", ...]
  },
  "sha256": "<digest over request/mode/folder/model/content>"
}
```

**Build report** (returned by `build_from_plan`/`run_build`, persisted under `builds/`):
```json
{
  "plan_id": "...", "stage": "done",
  "status": "built | already_passing | rejected_trivial_tests | could_not_build",
  "mode": "new | amend",
  "message": "<human-readable explanation>",
  "repair": { "status": "verified_direct_repair | baseline_passed | ...", ... },
  "isolation": "sandbox | none",
  "checks": ["...plain-language checks..."],
  "evidence": "<absolute evidence dir>"
}
```
The dashboard reads `status` (packaging gate), `checks` (passing count), and `message`.

**`requirements.json`** — the scaffold's declared dependencies (`build.requirements_doc`).
**`pipeline.json`** — higher-level pipeline spec consumed by `pipeline.run_pipeline` (guards against missing/malformed input).
**Repair journal** — validated by `repair_recovery.recover_journal` (checks dict/entries/base64) so a corrupt journal cannot crash recovery.

---

## 8. State directory layout

The dashboard chooses state by OS:
- **Windows:** `%LOCALAPPDATA%\ADM\state` (`Path.home()/AppData/Local/ADM/state`)
- **Other (tests/dev):** `~/.adm-worker-state`

```
<state>/
  plans/<plan_id>/plan.json         intake.create_plan / approve
  builds/<plan_id>.json             build.save_report  (stat tiles, packaging gate)
  evidence/<plan_id>/               build._safe_evidence (stable per-plan)
  dist/<name>.exe                   packaged executables (counts into "builds" tile)
  logs/adm.log                      diagnostics.log_line (append-close, rotated)
```
Generated user projects live under `intake.projects_root(home)` (a per-user projects folder), separate from ADM state. The shared bundled Python lives at `%ProgramData%\ADM\python` (world-readable; RX granted to the sandbox account so it can run cross-account).

---

## 9. The build pipeline in depth

`build.build_from_plan` runs the entire build **inside** `project_lock.exclusive_project(root)` (a kernel file lock on `.adm-repair.lock`), so a second build on the same project cannot corrupt the scaffold. Steps:

1. **Generate frozen tests** from `plan.content.tests` (`stage: generating_tests`). The test file is written once and not modified during repair.
2. **Scaffold** `app.py` (stub) + `requirements.json` (`stage: scaffolding`) for a new project; for an existing ADM project, **amend** instead (`is_adm_project`, `amend_project`).
3. **Baseline-must-fail guard:** run the frozen tests against the empty scaffold.
   - If they already pass on an amend with no change needed → `already_passing`.
   - If they pass before any program exists → `rejected_trivial_tests` (the tests are not real checks).
4. **Direct repair loop** (`ollama_direct.direct_repair`, `stage: writing_and_testing_code`): run tests in the **sandbox** → request a patch from the model → `apply_patch` (compile-guarded) → re-run, up to `max_repairs`. Success is `verified_direct_repair` and requires passing **twice** → `status: built`.
   - If the limit is reached without passing → `could_not_build` (code + output kept as evidence).
5. **Report** is finalized (`stage: done`), `checks`/`evidence` attached, and persisted by `save_report`.

**Packaging gate (the answer to "do we write the EXE if we still have errors?"):** `dashboard.finish_build` computes `built = report['status'] in ('built','already_passing')`. Only then does it call `start_package`; otherwise the Package stage is set to "Not built yet" and **no EXE is produced**. `rejected_trivial_tests` and `could_not_build` never package.

---

## 10. Security and the Windows sandbox

Generated code and model output are treated as hostile. The sandbox (`sandbox.py`, provisioned by `provision.py`) confines execution:

- **Separate identity:** a dedicated low-privilege local account **`admsandbox`**; generated code runs as that user via `CreateProcessWithLogonW` (`make_runner`/`run_confined`).
- **No network:** a per-user outbound **firewall block** for the sandbox account.
- **Filesystem containment:** ACL hardening of shared dirs (Public, ProgramData, Windows\Temp, Windows\Tasks); generated code must refuse/report paths outside its project folder. `refuse_hardened_location` strips and rejects device-path prefixes (`\\?\`, `\\.\`).
- **Resource caps:** a **Job Object** enforces memory and kills the whole tree on timeout/over-limit.
- **Command-line safety:** `cmdline_for` rejects the bad-char set `"%\x00\r\n&|<>^`, trailing backslashes, and empty command lines.
- **One-time admin:** provisioning requires administrator once (`is_admin()` / `NEED_ADMIN`); the app states this plainly. Normal use afterward needs no admin.
- **Model-name safety everywhere:** `safe_model` / `safe_local_model` reject traversal (`..`, leading slash) and null bytes before a name is ever used in a path or command.

All sandbox behaviours are verified on real Windows runners (see `sandbox-probe.yml` and §16): write-inside / refuse-outside / no-network / timeout-kill / memory-cap / child-process / shared-folder-refused.

---

## 11. Free-first AI backends

- **Local first:** `ollama_health`/`model_probe`/`model_selection` detect and health-check a local Ollama model; `backends.make_generator` / `make_json_generator` build the callables the pipeline uses.
- **Tolerant parsing:** models emit messy output, so `extract_json` strips fences, balances brackets, removes trailing commas, and the loop re-asks once with `JSON_REMINDER`. Every untrusted parse catches `ValueError/TypeError/RecursionError` (RecursionError matters on 3.12, which the EXE bundles).
- **Transport safety:** HTTP clients refuse redirects (`_RejectRedirects`) and guard against malformed/oversized/wrong-shape responses (hardened by fuzz round 5).
- **Remote is opt-in:** any remote/cloud model use requires explicit user approval because the prompt contains the user's source. Free cloud tiers are a fallback to local, never a requirement.

---

## 12. The packaging subsystem (the 052 work)

`package.py` turns a verified build into a one-file executable:

1. **`write_entry(root, plan)`** generates `main.py` (only if absent) from the `ENTRY` template. `main.py` uses `inspect.getmembers` to expose the app's public functions as CLI commands, with `--help` listing them and `_convert` coercing numeric args. **Hardened (round 10):** the program title is injected as a `repr()` literal and control chars are stripped, so a backslash, quote, newline, null byte, or the template's own tokens can never produce invalid Python. `plan_title(plan)` reads a title from a plan of **any** shape (non-dict, `content` None/list/str) without raising, falling back to a safe default.
2. **`find_packager_python()`** locates a Python that can `import PyInstaller`, or returns `None`.
3. **`package_command(...)`** builds the PyInstaller invocation (`--onefile --console --name <exe_name>`).
4. **`package_project(root, dist_dir, *, plan, ...)`** raises `SafetyError` if there is no built `app.py` or no packager available (honest message), otherwise runs PyInstaller with a timeout and returns `{status: 'packaged'|'failed', exe, name, returncode, output_tail}`.

`exe_name(title)` sanitizes any title to a bounded, non-empty, alnum/hyphen slug. The generated CLI is proven to actually run (`add 2 3 → 5`) both in unit tests and on CI (`tools/verify_package.py`).

---

## 13. Diagnostics, logging, and recovery

- **Logging that survives Windows file locks:** `log_line` opens, appends one line, and closes (no held handle), with `_rotate_if_big` to cap size. This replaced a `RotatingFileHandler` that caused `WinError 32`.
- **Crash capture:** `install_excepthook(state, component)` logs uncaught exceptions; the GUI additionally sets `win.report_callback_exception` to log + show a messagebox.
- **`self_check(state)`** returns a list of `{name, ok, detail}` health checks (Python, Local AI, Bundled Python, Sandbox, Disk, Write, GUI) — surfaced by the dashboard's "Run diagnostics" button.
- **`export_bundle`** writes a diagnostics zip (logs, health, environment) **without** the user's source, for support.
- **Recovery:** `recovery`/`repair_recovery` validate and recover from interrupted builds and corrupt journals; `build._recover_interrupted` runs inside the build lock.

---

## 14. Concurrency and Windows-specific hardening

These are real defects found and fixed; they are the kind of thing a reviewer should not "simplify" away:

- **Whole-build project lock** (`exclusive_project`) prevents a concurrent-build scaffold race that corrupted projects.
- **Atomic plan writes:** unique temp filename + `os.replace` retry loop tolerates Windows briefly denying a rename-over while another writer holds the target; `approve` retries `mkdir` on `FileExistsError`.
- **Worker DB:** `_open_db` retries on transient Windows WAL locks.
- **Append-close logging** (above) avoids held-handle locks.
- **RecursionError** is caught on all untrusted-input parses (3.12 raises it where 3.13 may not).

---

## 15. Testing: inventory and how to run

**Run everything:** `python -m adm.regression` → expect `OVERALL: PASS; 442 completed tests`.
**One file:** `PYTHONPATH=. python tests/test_package_052.py`.
**One fuzz round:** `python -I tools/fuzz_adversarial11.py`.

**64 test files** (unit, integration, hardening `*_052`, regression/evidence):
`test_acceptance, test_adaptive, test_adaptive_worker, test_agent, test_ai_inspection, test_auto_queue, test_build_052, test_build_hidden_imports_049, test_context_051, test_core, test_daemon, test_daemon_lifecycle, test_daemon_robustness_050, test_dashboard_logic_052, test_desktop, test_desktop_entry_040, test_desktop_entry_exit, test_diagnostics_052, test_engine, test_firstrun_050, test_hardening_050, test_hardening_adversarial_052, test_hardening_agent_052, test_hardening_firstrun_052, test_hardening_queue_052, test_hardening_release_052, test_hardening_round6_052, test_independent_retest, test_intake_052, test_live_acceptance, test_local_transport_security, test_model_probe, test_model_selection, test_ollama_direct, test_ollama_health, test_package_052, test_packaged_smoke_041, test_pid_alive_049, test_pipeline, test_process_tree, test_project_lock, test_provision, test_pyruntime_050, test_queued_ai, test_recovery, test_regression, test_regression_evidence_047, test_regression_guards, test_regression_log_isolation_048, test_regression_retention_049, test_release, test_release_hidden_imports_049, test_repair_commit, test_repair_recovery, test_repomap_backends_051, test_runtime_install_052, test_sandbox_052, test_sandbox_harden_052, test_sandbox_integration_052, test_setup, test_supervisor_singleton_045, test_windows_build_verifier_044, test_windows_startup, test_worker`.

Hardening tests encode the specific bugs each fuzz round found, so a regression cannot silently return.

---

## 16. Adversarial fuzzing: all 11 rounds

Each harness throws hostile/malformed input at a subsystem. **Graceful** = returns or raises an expected `SafetyError/ValueError/PermissionError/OSError` (and, where relevant, `TypeError`); anything else (uncaught crash, corruption, false success) is a **BUG**. Every bug was fixed and locked in with a test. Run under `python -I` in CI; non-zero exit fails the build.

| Round | File | Target | Notable outcomes |
|---|---|---|---|
| 1 | `fuzz_adversarial.py` | every layer, broad | baseline hostile-input sweep |
| 2 | `…2.py` | filesystem, locking, resource exhaustion, repo-map, failure-parse, model names, diagnostics | |
| 3 | `…3.py` | huge-file amend, log rotation, patch checks, path-normalization tricks, plan tampering | |
| 4 | `…4.py` | job queue, worker concurrency, daemon status, project lock, recovery journals, **real concurrent-build race** | concurrency fixes |
| 5 | `…5.py` | hostile model-server HTTP (malformed/oversized/wrong-shape/error/redirect) | transport must never crash/hang/exhaust memory |
| 6 | `…6.py` | release/archive (zip bombs & traversal), provisioning validator, pipeline spec, model_probe HTTP, context math | |
| 7 | `…7.py` | first-run/local-AI setup (parses external command output), concurrent intake approval | |
| 8 | `…8.py` | agent helpers, resource/size parsing, Unicode/locale edges | `atomic_json` never crashes on odd values |
| 9 | `…9.py` | repair enqueue API, windows startup commands, failure excerpting bounds, journal prep | model names with traversal rejected |
| **10** | `…10.py` | **packaging** (entry gen, exe names, hostile plans) + diagnostics self-check | **10 bugs:** backslash/null-byte titles → invalid `main.py`; malformed plan → AttributeError. Fixed via `repr()` injection + `plan_title`. |
| **11** | `…11.py` | **dashboard** `collect_stats` + `_fmt_uptime` under corrupt state | **5 bugs:** non-list `checks` → len() crash; top-level JSON array → .get() crash; `_fmt_uptime(nan/inf)` → ValueError. Fixed via shape checks + float coercion. |
| **12** | `…12.py` | **packaging** filesystem/concurrency: `main.py` as a directory, missing/file/empty roots, 12-thread entry race, empty-name guards | **0 bugs** — round 10's repr() injection + the `is_file()` guard already hold. Locked in as a CI regression. |
| **13** | `…13.py` | **diagnostics collector**: `_safe` default contract, `_plan_counts`/`_recent_builds`/`collect`/`export_bundle` under corrupt plans/reports | **3 bugs:** `_safe` ignored its `default` (returned an error string where a dict/list/str was expected); `_plan_counts`/`_recent_builds` crashed on a top-level JSON array. Fixed via sentinel default + shape guards. |
| **14** | `…14.py` | **model-facing analysis**: `context.patch_key`/`check_patch`/`AttemptLedger` on malformed model patches; `repomap`/`traceback_files` on hostile trees | **24 bugs:** patch shape unchecked before `apply_patch`, so a malformed model patch crashed the repair loop (KeyError/TypeError); `traceback_files` let an over-long filename's `is_file()` raise OSError. Fixed via `context.patch_files()` shape validator (used by patch_key/check_patch and `request_patch`) + widened try. |
| **15** | `…15.py` | **intake**: `plan_text` on corrupt/partial plans; `parse_plan` on hostile model output; digest tamper | **8 bugs:** `plan_text` indexed content/status fields directly, so a partial/hand-edited `plan.json` crashed the GUI renderer. Fixed by rendering defensively. (`parse_plan`/`load_plan`/`require_approved` were already robust.) |
| **16** | `…16.py` | **autonomous recovery**: `repair_recovery` journal + `recovery` snapshot/restore (symlinks, oversize, tamper) | **8 bugs:** `prepare_journal` indexed an unvalidated patch. Fixed by reusing `context.patch_files()`. (`recover_journal` and `recovery` already robust.) |
| **17** | `…17.py` | **AI backends**: `extract_json`, `safe_model`, generator factories, `probe_local_servers` | **3 bugs:** `probe_local_servers` raised `http.client.InvalidURL` (an HTTPException, outside its except) on a malformed port. Fixed: validate port 1..65535 + catch HTTPException. (Rest robust.) |
| **18** | `…18.py` | **lifecycle/interaction**: 40 seeded trials of `direct_repair` under adversarial model patches | **0 bugs** — honesty invariants hold: no false `verified`, frozen test intact, no file escapes, no unhandled crash. End-to-end proof of the round-14 gate. |
| **19** | `…19.py` | **release.py**: `verify_source_release`/`create_source_release`/`source_files` against malformed archives, bad manifests, traversal, symlinks | **0 bugs** — the round-6 archive hardening holds (zip-bomb, traversal, hash, dup guards). |
| **20** | `…20.py` | **concurrency**: 6 `WorkerSupervisor` instances racing on one queue of 24 jobs (marker-verified) | **0 bugs** — single-owner `claim()` holds: every job runs exactly once, all terminal, WAL DB intact. Stable across repeated runs. |

Rounds 10 and 11 each found real bugs on first contact with new code; round 12 found none (the packaging seam was already hardened by round 10), so further rounds against newer seams (packaging filesystem/concurrency, the build→report→stats→package contract, GUI event streaming) would likely still be productive.

---

## 17. CI/CD: what is proven, and where

`.github/workflows/windows-desktop-build.yml` (triggers: push, manual), **`windows-2022`, Python 3.12**:

**Job `windows-build`:** install pinned PyInstaller → verify sources compile → windows-startup & packaged-entry tests → prepare & verify bundled Python runtime → build & run packaged smoke test → **packaged EXE end-to-end repair against a FAKE Ollama** → first-run local-AI prompt (real window, captured) → request window (real window, fake model, plan approved) → **package a generated project into an EXE and run it** (`verify_package.py`) → print evidence → upload build evidence + the unverified EXE artifact.

**Job `windows-full-regression`:** full `adm.regression` → **adversarial fuzz rounds 1–11** (each gated on exit code) → upload regression evidence.

**`sandbox-probe.yml`** proves sandbox confinement on a real Windows runner. **`gui-screenshots.yml`** renders the dashboard.

> Artifact *downloads* are blocked by the build sandbox's proxy, so evidence is read from **job logs**, which are the source of truth.

---

## 18. Building the Windows EXE

On Windows: run **`BUILD-WINDOWS-DESKTOP.cmd`** (PyInstaller one-file, windowed `ADM-Desktop.exe`; hidden-imports include `adm.package`). Verify with **`VERIFY-WINDOWS-DESKTOP.ps1`**. The embeddable Python runtime is bundled via `--add-data pyembed` and installed at first run to `%ProgramData%\ADM\python`.

---

## 19. What the user must provide

- **A Windows 11 PC (16 GB RAM).** ADM is a Windows desktop app; the sandbox uses Windows accounts, firewall, and Job Objects.
- **Administrator access once**, to provision the sandbox account/firewall/ACLs. Normal use afterward needs no admin.
- **A local AI model via Ollama** (free) for real code generation on their own machine. ADM detects and health-checks it. Without a local model, the pipeline logic still runs but cannot generate real programs locally; genuinely free cloud tiers are the fallback, and any remote use is explicit-approval only.
- **Nothing paid.**

## 20. Known limitations, caveats, and open decisions

1. **PyInstaller not yet bundled for the end-user PC.** Packaging is implemented and proven on CI (where PyInstaller is installed). On the user's PC the Package step shows an honest message — *"Packaging needs Python with PyInstaller, which is not available yet on this PC"* — until a future update bundles a packager. The build/test/auto-fix pipeline is unaffected. See `package.find_packager_python`.
2. **Auto-package vs. manual button (open UX decision).** Today a verified build flows straight into packaging (`finish_build → start_package`). A manual "Package to EXE" button was discussed as possibly safer for non-coders; not implemented.
3. **Generated-program quality tracks the local model.** ADM's guarantees are about *process honesty and containment*, not model cleverness.
4. **`VERSION` is `0.5.2-dev`** — a development version.
5. **Admin requirement** may surprise non-technical users; the first-run flow should keep explaining it clearly.

## 21. Extension guide (how to add things safely)

- **Add a pipeline output type (e.g. a new deliverable):** mirror `package.py` — a pure generator + a gated entry in `dashboard.finish_build`; never package unless `status ∈ {built, already_passing}`.
- **Add a module:** register it in `selftest.SMOKE_MODULES` (so it is import-smoke-tested) and in `BUILD-WINDOWS-DESKTOP.cmd` hidden-imports if the EXE needs it.
- **Touch anything that parses untrusted input (model output, files, args):** catch `ValueError/TypeError/RecursionError/OSError`, validate shape with `isinstance` before `.get()`/`len()`, and add a fuzz case.
- **Add a fuzz round:** copy an existing harness's `graceful`/`reject` skeleton, target the new surface, wire `python -I tools/fuzz_adversarialN.py` into the CI fuzz step, and add a `test_hardening_*_052.py` test for each real bug found.
- **Never weaken a §2 constraint** (free-only, no-net generated code, path containment, explicit remote approval, no fake success) without an explicit product decision.
- **Windows file ops:** assume rename-over and open-for-write can transiently fail; use the retry patterns already in `intake._save` / `worker._open_db`.

## 22. Suggested review order

1. `adm/build.py` + `adm/ollama_direct.py` — the pipeline and repair loop (the heart).
2. `adm/sandbox.py` + `adm/provision.py` — the confinement/threat model.
3. `adm/intake.py` — request→plan→approval and the Windows-safe file handling.
4. `adm/package.py` + `tests/test_package_052.py` — the newest subsystem.
5. `adm/dashboard.py` — the GUI and the build→package gate (`finish_build`/`start_package`/`finish_package`).
6. `tools/fuzz_adversarial*.py` + the `test_hardening_*` tests — the adversarial strategy and what is hardened.
7. `.github/workflows/windows-desktop-build.yml` — how it is all verified on real Windows.

## 23. Appendix

**Build report statuses:** `built` (verified twice; packageable), `already_passing` (amend; checks already pass; packageable), `rejected_trivial_tests` (tests passed before code — not packaged), `could_not_build` (repair limit reached — not packaged).

**Build stages (streamed to the GUI):** `generating_tests → scaffolding | amending → writing_and_testing_code → done`. Dashboard pipeline stages: Plan & requirements, Code generation, Build & test, Auto-fix, Package & deliver.

**Repair statuses:** `verified_direct_repair` (success), `baseline_passed` (tests passed with no/empty code), plus in-progress states.

**Recent commit highlights:**
- `d4c2c7c` Fuzz round 11: harden dashboard stats against corrupt reports/plans
- `bf0ad82` Fuzz round 10: harden packaging against hostile titles and malformed plans
- `466744d` Add Package & deliver stage: generated CLI entry + PyInstaller packaging
- `315b14d` Self-diagnostics (health checks, Run/Export diagnostics)
- `9e07fe3` Adversarial round 9 (model-name traversal rejection; fuzz9 in CI)


---

## Appendix A — Complete module index (all 50)

Every file in `adm/` with its purpose. "stdlib-only" is the default; exceptions are noted.

| Module | Purpose |
|---|---|
| `__init__.py` / `__main__.py` | package marker / `python -m adm` entry |
| `acceptance.py` | offline end-to-end acceptance: real HTTP transport + real subprocess tests, fake AI |
| `adaptive.py` | resource-aware admission decisions; never changes verification requirements |
| `agent.py` | guarded OpenCode/Ollama adapter and evidence-backed repair trial |
| `agent_cli.py` | CLI for a real local OpenCode agent trial |
| `ai_status.py` | read-only CLI reconciling a queued AI repair with its evidence |
| `backends.py` | local + optional remote model backends behind one patch-request interface |
| `build.py` | approved plan → frozen tests → scaffold → sandboxed repair loop → honest report |
| `cli.py` | human-friendly proof command |
| `context.py` | local analysis deciding what the model is shown (not what is tested/recorded) |
| `core.py` | durable, resource-aware command verification supervisor |
| `daemon.py` | persistent unattended trusted-job runner with observable lifecycle state |
| `dashboard.py` | the dark Tkinter dashboard main window |
| `desktop.py` | dependency-free desktop control panel helpers |
| `desktop_entry.py` | single-file Windows entrypoint: GUI normally, headless supervisor with a flag |
| `diagnostics.py` | persistent app log + one-click export bundle + self-check |
| `engine.py` | bounded, evidence-backed autonomous repair proof; `SafetyError` lives here |
| `firstrun.py` | first-run local-AI setup: detect missing, ask, install with progress |
| `intake.py` | plain-language request → plan → explicit approval (writes no code) |
| `intake_gui.py` | the "New request" window; thin layer over `intake` |
| `live_acceptance.py` | opt-in real-Ollama acceptance on a disposable fixture |
| `model_probe.py` | local-only Ollama readiness + bounded inference smoke benchmark |
| `model_selection.py` | deterministic offline model selection from installed inventory |
| `ollama_cli.py` | run a local direct-repair trial on a disposable project |
| `ollama_direct.py` | direct local Ollama repair loop with guarded file edits + evidence |
| `ollama_health.py` | read-only, loopback-only Ollama health + installed-model inspection |
| `package.py` | package a verified build into a standalone EXE (generates CLI entry) |
| `pipeline.py` | durable, fail-closed supervised local agent proof |
| `pipeline_cli.py` | supervised local-AI proof CLI (no paid API, no auto-exec of unknown projects) |
| `preflight.py` | read-only diagnostics for local Ollama/OpenCode availability |
| `project_lock.py` | crash-released OS file lock for exclusive project ownership |
| `provision.py` | resumable, dependency-aware local provisioning coordinator (sandbox) |
| `pyruntime.py` | which interpreter runs what, in source vs frozen app |
| `queued_ai.py` | queue a bounded local-Ollama repair for the supervisor |
| `recovery.py` | bounded, verified workspace snapshot/restore for disposable trials |
| `regression.py` | isolated, bounded regression runner (never turns timeouts into passes) |
| `release.py` | reproducible source release + opt-in Windows EXE build planning + zip-bomb guards |
| `release_entry.py` | frozen Windows entrypoint for the supervisor (not a GUI) |
| `repair_recovery.py` | crash journal for local-model source replacements |
| `repomap.py` | dependency-free AST map of a Python project |
| `runtime_install.py` | install a bundled Python runtime so users needn't install Python |
| `sandbox.py` | the Windows sandbox for generated code (low-priv account + firewall + ACL + Job Object) |
| `selftest.py` | bounded, offline, non-executing packaged-app smoke test (`SMOKE_MODULES`) |
| `setup.py` | auditable, explicit-consent local dependency provisioning |
| `setup_cli.py` | read-only setup plan by default; `--apply` is opt-in |
| `theme.py` | shared dark-theme colours/fonts/widget helpers for the dashboard |
| `windows_startup.py` | opt-in Windows logon launcher (no install without user action) |
| `worker.py` | durable single-owner worker supervision for trusted commands |
| `worker_cli.py` | CLI for the trusted worker proof |

## Appendix B — Test-file map (all 64)

| Test file | Covers |
|---|---|
| `test_acceptance` | real HTTP + real tests with fake AI (offline e2e) |
| `test_adaptive` / `test_adaptive_worker` | 16 GB admission decisions; denial defers without consuming an attempt |
| `test_agent` / `test_ai_inspection` | evidence-backed repair; pending ≠ verified |
| `test_auto_queue` | model auto-selection on 16 GB; persistence |
| `test_build_052` | build requires an approved plan; pipeline semantics |
| `test_build_hidden_imports_049` / `test_release_hidden_imports_049` | every smoke module is a PyInstaller hidden-import |
| `test_context_051` | what the model reads is reduced; what is tested/recorded is not |
| `test_core` / `test_worker` | supervisor success+evidence; real run + spooled logs |
| `test_daemon` / `test_daemon_lifecycle` / `test_daemon_robustness_050` | lifecycle state; stale heartbeat reported unresponsive |
| `test_dashboard_logic_052` | headless dashboard logic: stats + uptime (incl. corrupt-state guards) |
| `test_desktop` / `test_desktop_entry_040` / `test_desktop_entry_exit` | GUI build plan; frozen launch; failure propagation to CI |
| `test_diagnostics_052` | logging never raises; collect resilient; export bundle has no source; `_safe` default |
| `test_engine` | end-to-end bounded repair proof |
| `test_firstrun_050` | setup refuses without approval |
| `test_hardening_050` / `test_hardening_*_052` / `test_hardening_round6_052` | regression tests pinning bugs from fuzz rounds 1–8 |
| `test_independent_retest` / `test_repair_commit` / `test_repair_recovery` | second-process verification; commit boundary; crash-journal restore |
| `test_intake_052` | plan saved unapproved; no project folder created yet |
| `test_live_acceptance` | refuses a missing model without writing |
| `test_local_transport_security` | local AI transport never follows redirects |
| `test_model_probe` / `test_model_selection` / `test_ollama_health` | model readiness, selection, health |
| `test_ollama_direct` | successful repair from a fake generator |
| `test_package_052` | exe-name sanitising, generated entry runs, hostile titles, malformed plans |
| `test_packaged_smoke_041` / `test_pyruntime_050` | real offline smoke; frozen self-command re-enters the EXE |
| `test_pid_alive_049` / `test_process_tree` | liveness check must not kill; process-tree timeouts |
| `test_pipeline` | supervised agent process end-to-end |
| `test_project_lock` | persistent lock file + metadata |
| `test_provision` / `test_sandbox_052` / `test_sandbox_harden_052` / `test_sandbox_integration_052` | consent required; password policy; per-dir deny rules; isolation reporting |
| `test_recovery` | snapshot reverts add/change/delete |
| `test_regression` / `test_regression_evidence_047` / `test_regression_guards` / `test_regression_log_isolation_048` / `test_regression_retention_049` | runner rejects vacuous success; evidence integrity; retention |
| `test_release` | frozen launcher uses the EXE directly |
| `test_repomap_backends_051` | repo map, second backend, escalation ladder |
| `test_runtime_install_052` | shared-dir honours `%ProgramData%` override |
| `test_setup` | constrained-machine setup planning |
| `test_supervisor_singleton_045` | supervisor ownership (single owner) |
| `test_windows_build_verifier_044` / `test_windows_startup` | build-verifier contract; startup command is argv, not shell |

## Appendix C — Dependency footprint and rebuild from scratch

**Runtime dependencies:** the application is **Python standard library only** for its core (no third-party runtime deps to run the pipeline or GUI — Tkinter ships with CPython). The only third-party tool is **PyInstaller**, used *at build time* to produce the EXE (and not yet bundled for the end-user PC — see §20). A local **Ollama** model is an external, free, user-provided dependency for real code generation.

**Rebuild and test from scratch (any OS):**
```
# 1. unzip the cumulative package to a clean folder, then:
cd <folder>
python3 -m adm.regression        # expect: OVERALL: PASS; 442 completed tests
python3 -I tools/fuzz_adversarial13.py   # (and 1..12) expect: N checks ok, 0 bugs
```
No install step, no virtualenv, no network needed for the suite. Python 3.12 or 3.13.

**Build the Windows EXE (Windows only):** run `BUILD-WINDOWS-DESKTOP.cmd` (needs `pip install pyinstaller`), then `VERIFY-WINDOWS-DESKTOP.ps1`.

## Appendix D — Exception taxonomy

- **`SafetyError`** (`adm/engine.py`) — the base "we refuse / cannot safely proceed" signal. Raised by intake validation, build guards, packaging (`no app.py` / `no packager`), sandbox, startup, release. Callers and the GUI treat it as an expected, user-facing condition (shown, logged), never a crash.
- **`SandboxError(SafetyError)`** (`adm/sandbox.py`) — confinement-specific refusals (bad command line, hardened location, missing admin).
- **Tolerated-input exceptions** — untrusted parsers catch `ValueError`, `TypeError`, `RecursionError`, `OSError`/`PermissionError`. These never propagate out of a parse/collect step; they become a safe default or a skipped item.
- **Anything else uncaught** = a bug by definition; the fuzz harnesses exist to find exactly these, and `diagnostics.install_excepthook` + the GUI's `report_callback_exception` log any that reach the top.

## Appendix E — Failure-path behaviors (what the user sees)

| Situation | Behavior |
|---|---|
| No local model available | Pipeline logic still runs; `create_plan` raises `SafetyError('No local model is available to make a plan')`; GUI shows it. Real generation needs Ollama. |
| Model returns garbage JSON | `extract_json` repairs common issues + one re-ask (`JSON_REMINDER`); still bad → handled, surfaced, no crash. |
| Build can't pass the tests in the attempt limit | `status: could_not_build`; code + output kept as evidence; **no EXE**. |
| Generated tests pass before any code | `status: rejected_trivial_tests`; **no EXE**; message explains the tests weren't real. |
| Not running as admin (sandbox needed) | `sandbox.is_admin()` false → `NEED_ADMIN` message; user elevates once. |
| PyInstaller absent on user PC | Package step raises `SafetyError('Packaging needs Python with PyInstaller…')`; honest message; build/test unaffected. |
| Corrupt plan.json / build report | Shape-guarded everywhere; stats/diagnostics degrade gracefully (rounds 11 & 13). |
| Interrupted build | `_recover_interrupted` / repair journal restore under the project lock on next run. |

## Appendix F — Security invariants (audit checklist)

A reviewer can audit the code against these; each should hold at all times:

1. **No network for generated code** — sandbox applies a per-user outbound firewall block (`sandbox.provision`).
2. **No path escape** — generated code refuses/reports paths outside its project folder; device-path prefixes stripped (`refuse_hardened_location`); command lines reject the bad-char set (`cmdline_for`).
3. **No fake success** — "built" requires `verified_direct_repair` (passed twice); trivial tests rejected (baseline-must-fail).
4. **No unapproved remote model use** — remote backends are opt-in; local is default; prompts contain user source, so remote needs explicit approval.
5. **No model-name injection** — `safe_model` / `safe_local_model` reject `..`, leading slash, null bytes before any path/command use.
6. **No source in diagnostics** — `export_bundle` includes logs, reports and test *output* only, never generated `app.py` (pinned by `test_diagnostics_052`).
7. **Single-owner builds** — the whole build runs under `project_lock.exclusive_project`; no concurrent scaffold.
8. **One-time admin only** — only sandbox provisioning needs admin; normal use does not.
9. **Free-only** — no code path requires a paid account.


## Appendix G — Defect log (fuzz rounds 10–15, this hardening pass)

Every defect below was found by an adversarial harness, root-caused, fixed permanently, pinned by a regression test, and the full suite re-run. "Verified" = reproduced the crash, then confirmed the fix on Python 3.12/3.13 here; EXE/sandbox behaviour is verified on Windows CI only.

| Round | Defects | Root cause | Fix | Regression test |
|---|---|---|---|---|
| 10 | 10 | packaging injected the program title into the generated `main.py` by raw string replace; malformed plan indexed directly | `repr()` literal injection + control-char strip; `package.plan_title()` reads any plan shape | `test_package_052` |
| 11 | 5 | `collect_stats` assumed report/plan shapes; `_fmt_uptime` assumed finite input | isinstance guards; float coercion → `'0m'` | `test_dashboard_logic_052` |
| 12 | 0 | — (packaging FS/concurrency already hardened by round 10) | — | harness only |
| 13 | 3 | `diagnostics._safe` ignored its `default`; `_plan_counts`/`_recent_builds` assumed dict JSON | sentinel-guarded default; non-dict shape guards | `test_diagnostics_052` |
| 14 | 24 | model patch shape validated only in `apply_patch`, after `patch_key`/`check_patch`/`seen_patch`; `traceback_files` OSError outside try | `context.patch_files()` shape gate used everywhere incl. `request_patch`; widened try | `test_context_051` |
| 15 | 8 | `plan_text` indexed `content`/`status` fields directly | defensive rendering (`.get` + type coercion + defaults) | `test_intake_052` |
| 16 | 8 | `prepare_journal` indexed an unvalidated model patch | reuse `context.patch_files()` shape gate (shared by all 3 patch consumers) | `test_repair_recovery` |
| 17 | 3 | `probe_local_servers` didn't validate port values; `InvalidURL` escaped its except | validate port 1..65535; add `http.client.HTTPException` | `test_repomap_backends_051` |
| 18 | 0 | — (lifecycle invariants held under adversarial patches) | — | harness only (independent re-test inside) |
| 19 | 0 | — (release archive/verify robustness held) | — | harness only |
| 20 | 0 | — (worker single-owner claim held under real concurrency) | — | harness only (marker-verified, 5x stable) |

**Totals this pass:** 61 defects fixed across rounds 10, 11, 13, 14, 15, 16, 17. Rounds 12, 18, 19, 20 found none: 18 proves the repair-loop honesty invariants, 19 confirms archive hardening, 20 confirms the worker single-owner claim under real concurrency. The last four rounds finding zero indicates the frequently-used untrusted-input and concurrency paths are now well-hardened. All are concurrency/robustness/data-corruption classes against untrusted model output, corrupt on-disk state, and hostile inputs — none required target hardware to reproduce.

**Remaining risks / not verified here:** real local-model generation quality (fake model used in this environment); the actual PyInstaller EXE build and the Windows sandbox confinement (Windows CI only, not this Linux workspace); GUI pixel rendering (logic is tested headless, screenshots run in a separate CI job).


*Handoff 052. Code is on `main` @ `d4c2c7c`; the accompanying `ADM-052-source.zip` is a self-contained snapshot of `adm/`, `tests/`, `tools/`, `.github/`, and the build scripts. The session transcript is delivered separately and is intentionally not in the repository.*
