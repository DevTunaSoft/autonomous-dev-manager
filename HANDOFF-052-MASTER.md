# ADM — Autonomous Development Manager · Master Handoff 052

**Repository:** https://github.com/DevTunaSoft/autonomous-dev-manager
**Branch / commit at handoff:** `main` @ `d4c2c7c`
**Version:** `0.5.2-dev` (see `adm/diagnostics.py: VERSION`)
**Date:** 2026-11-05
**Status:** All 435 automated tests pass. 11 adversarial fuzz rounds integrated into CI. Build/test/auto-fix pipeline verified on real Windows runners. EXE packaging implemented and proven on CI; one dependency (PyInstaller) not yet bundled for the end-user PC (details below).

This document is written for a software engineer reviewing the project cold. It explains what the product is, the constraints it must honour, how the code is organized, the safety model, the build pipeline, how to run and verify everything, and exactly what is and is not finished.

---

## 1. What ADM is

ADM is a single Windows 11 desktop application for people who **do not write code**. The user describes the software they want in plain language. ADM then, using a **local (free) AI model**, plans the program, writes it, writes tests for it, runs those tests inside a locked-down sandbox, repairs the code until the tests pass, and finally packages the result into a standalone Windows `.exe`. The guiding promise is **honesty**: ADM never presents an isolated or faked test as proof of a working product.

### Target machine
- Windows 11 Pro, **16 GB RAM**, SATA SSD. Everything is sized to run on that machine.

### Non-negotiable product constraints (carried through the whole codebase)
1. **Free-only AI policy.** Local model first (Ollama), then genuinely free cloud tiers. **A paid account is never required** — it is at most an optional, user-chosen extra.
2. **Generated code is sandboxed.** Code ADM writes gets **no internet by default** and must **refuse/report any path outside its own project folder**.
3. **Remote model use requires explicit user approval**, because the prompt sent to a remote model contains the user's own source code.
4. **Never present fake/isolated tests as a working product.** A build is only "built" after its tests genuinely pass, verified twice in the sandbox.
5. **Per-release deliverable:** a cumulative **source ZIP** + a robust **Markdown handoff** + an explicit statement of **what the user must provide**. (This document + `ADM-052-source.zip` are that deliverable for cycle 052.)

---

## 2. Repository layout

```
adm/                50 Python modules (~6,600 LOC) — the application
tests/              64 test files — unit, integration, hardening, regression
tools/              fuzz harnesses (1–11), sandbox probes, screenshot & verify scripts
.github/workflows/  CI: windows-desktop-build.yml, sandbox-probe.yml, gui-screenshots.yml
BUILD-WINDOWS-DESKTOP.cmd   one-click EXE build script (PyInstaller) for Windows
VERIFY-WINDOWS-DESKTOP.ps1  post-build verification
README.md
HANDOFF-0NN-MASTER.md       historical cumulative handoffs (this is 052)
ADM-0NN-*.json / *.md       per-release manifests, SHA256 sets, evidence logs
```

### The 50 `adm/` modules, grouped by role

**Entry points & CLI**
- `__main__.py`, `cli.py` — top-level entry and command dispatch.
- `dashboard.py` — the dark-theme Tkinter desktop GUI (main user surface).
- `intake_gui.py`, `desktop_entry.py` — request window and desktop entry wiring.
- `*_cli.py` (`agent_cli`, `ollama_cli`, `pipeline_cli`, `setup_cli`, `worker_cli`) — thin CLI frontends used by scripts/CI.

**Request → plan → approval**
- `intake.py` — validates the plain-language request, slugifies it, creates/loads/approves a plan, chooses & tests a model. Atomic, Windows-safe file writes (unique temp names + `os.replace` retry).
- `context.py`, `preflight.py` — environment/readiness checks.

**Build pipeline**
- `build.py` — orchestrates classify → scaffold → amend → repair under a whole-build project lock; writes evidence and reports; rejects trivial tests.
- `ollama_direct.py` — the direct repair loop (`direct_repair` / `_direct_repair_unlocked`), patch application with a compile-guard.
- `pipeline.py` — higher-level pipeline runner with guards for missing/malformed `pipeline.json`.
- `agent.py`, `adaptive.py`, `queued_ai.py`, `worker.py`, `core.py`, `daemon.py` — the autonomous worker/queue machinery (enqueue repairs, run jobs, persist state).

**AI backends (free-first)**
- `backends.py` — tolerant JSON extraction from model output, one auto re-ask, OpenAI-compatible transport, local-server probing. Rejects unsafe model names (`..`, leading slash).
- `ollama_health.py`, `model_probe.py`, `model_selection.py`, `ai_status.py` — local model detection, health, selection, status.

**Packaging & runtime (the 052 work)**
- `package.py` — generates a generic CLI entry (`main.py`) exposing the app's public functions, then runs PyInstaller one-file. **Gated** so only verified builds are packaged.
- `runtime_install.py`, `pyruntime.py` — bundle & install the embeddable Python runtime (`%ProgramData%\ADM\python`) with cross-account read+execute for the sandbox user.

**Sandbox & safety**
- `sandbox.py` — the Windows confinement: a dedicated low-privilege local account (`admsandbox`), per-user outbound firewall block, ACL hardening of shared dirs, Job Object memory/kill limits, `CreateProcessWithLogonW`. Needs administrator once. `SandboxError` ⊂ `SafetyError`.
- `provision.py` — provisions the sandbox account/firewall/ACLs.
- `engine.py` — `SafetyError` and demo/broken-project helpers used across tests.
- `project_lock.py` — kernel file lock held across a whole build to prevent concurrent scaffold corruption.

**Diagnostics & recovery**
- `diagnostics.py` — append-and-close logging (avoids the Windows file-lock bug), `install_excepthook`, `self_check` (Python/Local AI/Bundled Python/Sandbox/Disk/Write/GUI), export bundle. `VERSION` lives here.
- `recovery.py`, `repair_recovery.py` — interrupted-build recovery and repair-journal validation.
- `windows_startup.py` — Windows startup command install (uses `SafetyError`).

**Release/verification**
- `release.py`, `release_entry.py` — source-release verification with zip-bomb size guards.
- `regression.py` — the test runner (`python -m adm.regression`).
- `selftest.py` — smoke-imports every module (`SMOKE_MODULES` includes `adm.package`).
- `repomap.py`, `acceptance.py`, `live_acceptance.py`, `setup.py`, `firstrun.py`, `theme.py`.

---

## 3. The build pipeline (how a request becomes an EXE)

```
plain-language request
   │  intake.validate_request → create_plan
   ▼
PLAN (shown to user)  ──► user presses "Approve & build"   (nothing is built before this)
   │
   ▼  build.build_from_plan  (entire build under project_lock.exclusive_project)
   ├─ AI writes test_app.py from plain-language checks        ── tests are then FROZEN
   ├─ scaffold app.py stub + requirements.json
   ├─ baseline-must-fail guard  (rejects trivial/no-op tests)
   ├─ direct_repair loop: run tests in the SANDBOX, patch, repeat
   └─ verified TWICE  ──► status = "built"
   ▼
Package & deliver  (package.package_project)   ── ONLY when status ∈ {built, already_passing}
   ├─ write_entry: generate main.py exposing app's public functions
   └─ PyInstaller --onefile --console  ──►  dist/<name>.exe
```

**Build statuses:** `built`, `already_passing`, `could_not_build`, `rejected_trivial_tests`.
**Packaging gate (critical, and the answer to "do we write the EXE if we still have errors?"):** packaging runs **only** for `built`/`already_passing`. `could_not_build` and `rejected_trivial_tests` set the Package stage to "Not built yet" and produce **no EXE**. See `dashboard.finish_build` → `start_package`.

---

## 4. Safety / threat model

ADM treats **model output and generated code as hostile** and the user's machine as something to protect.

- **Generated code** runs as `admsandbox`, a separate low-privilege account, with outbound networking firewalled off and ACLs hardened so it cannot read/write shared system dirs. Memory and runtime are capped by a Job Object; the tree is killed on timeout/over-limit.
- **Path containment:** generated code must refuse/report any path outside its own project folder; `sandbox.cmdline_for` / `refuse_hardened_location` reject device-path prefixes (`\\?\`, `\\.\`), control chars, and empty/trailing-backslash command lines.
- **Model output parsing is tolerant but defensive:** `backends.extract_json` tolerates messy output and re-asks once; every untrusted-input parse catches `ValueError/TypeError/RecursionError` (RecursionError matters on Python 3.12, which the EXE bundles).
- **Model names** are validated everywhere (`safe_model`, `safe_local_model`) to reject traversal (`..`, leading slash) and null bytes.
- **Admin is required once** to provision the sandbox (`sandbox.is_admin()` / `NEED_ADMIN`); the app states this plainly.

---

## 5. Adversarial fuzzing (11 rounds, all in CI)

Each round is a standalone harness in `tools/fuzz_adversarial{,.py,2..11}.py`, run under `python -I` in the `windows-full-regression` CI job; a non-zero exit fails the build. The pattern is `graceful(label, fn)` (must not raise an *uncaught* error) and `reject(label, fn)` (must reject bad input). Every bug a round found was fixed and locked in with a regression test.

- **Rounds 1–9** (pre-052): intake, sandbox, queue/worker, release (zip-bomb guards), first-run, agent `atomic_json`, backends JSON extraction, windows-startup, repair enqueue/journal. Notable fixes: Windows file-lock on the log (→ append-and-close logging), RecursionError on nested JSON (3.12), concurrent-scaffold corruption (→ whole-build lock), Windows `os.replace` races (→ retry).
- **Round 10** (`fuzz_adversarial10.py`) — **packaging**. Found 10 bugs: a program **title containing a backslash/null byte** generated an invalid `main.py`; a **malformed plan** (non-dict, or `content` None/list/str) raised `AttributeError`. Fixed: inject TITLE/EXE as `repr()` literals, strip control chars; new `package.plan_title()` reads any plan shape safely.
- **Round 11** (`fuzz_adversarial11.py`) — **dashboard stats**. Found 5 bugs: a report whose `checks` is not a list crashed `len()`; a top-level JSON **array** crashed `.get()`; `_fmt_uptime` crashed on `nan/inf`. Fixed: `collect_stats` verifies each parsed report/plan is a dict and treats non-list `checks` as zero; `_fmt_uptime` coerces to float and returns `'0m'` for non-finite/negative/bad input.

Fuzzing was **stopped at the user's request after round 11** (not because the space was exhausted). Rounds 10 and 11 both found real bugs, so additional rounds would likely still be productive against newer seams (e.g. packaging filesystem/concurrency edges, the build→report→stats→package contract).

---

## 6. CI (GitHub Actions)

`.github/workflows/windows-desktop-build.yml` — runs on `windows-2022`, Python 3.12 (the version the EXE bundles):
- **windows-build** job: builds the app, runs the EXE build chain.
- **windows-full-regression** job: full `adm.regression` suite + fuzz rounds 1–11 + a **"Package a generated project into an EXE and run it"** step (`tools/verify_package.py`) that packages a tiny project, runs the resulting EXE, and asserts `add 2 3 → 5` and `--help`.
- `sandbox-probe.yml` — verifies sandbox confinement on a real Windows runner.
- `gui-screenshots.yml` — renders the dashboard for visual review.

Evidence (job logs) is the source of truth; artifact downloads are blocked by the build sandbox proxy, so results are read from logs.

---

## 7. How to run, test, and build

**Run the test suite (any platform):**
```
python -m adm.regression          # expect: OVERALL: PASS; 435 completed tests
```
Individual test file: `PYTHONPATH=. python tests/test_package_052.py`
Individual fuzz round: `python -I tools/fuzz_adversarial11.py`

**Run the dashboard (Windows):**
```
python -m adm            # or the built ADM-Desktop.exe
```

**Build the Windows EXE:** run `BUILD-WINDOWS-DESKTOP.cmd` on Windows (PyInstaller one-file, windowed; hidden-imports include `adm.package`). Verify with `VERIFY-WINDOWS-DESKTOP.ps1`.

---

## 8. What the USER must provide

- **A Windows 11 PC (16 GB RAM).** ADM is a Windows desktop app; the sandbox uses Windows accounts, firewall and Job Objects.
- **Administrator access once**, to let ADM provision the sandbox account/firewall/ACLs. After that, normal use needs no admin.
- **A local AI model via Ollama** (free) for real code generation on their own machine. ADM detects and health-checks it. Without a local model, ADM can still run its pipeline logic but cannot generate real programs locally; genuinely free cloud tiers are the fallback, and any remote use is only after explicit approval.
- Nothing paid is required.

## 9. What a REVIEWER should know is NOT finished / caveats

- **PyInstaller is not yet bundled for the end-user PC.** Packaging works on CI (where PyInstaller is installed) and is proven to yield a runnable EXE. On the user's PC the Package step shows an honest message — *"Packaging needs Python with PyInstaller, which is not available yet on this PC"* — until a future update bundles a packager. The build/test/auto-fix pipeline is unaffected; only the final "turn it into an EXE" step has this dependency. See `package.find_packager_python`.
- **Auto-package vs. manual button:** currently a verified build flows straight into packaging (`finish_build` → `start_package`). A manual "Package to EXE" button was discussed as a possibly safer UX for non-coders but not implemented; this is an open product decision.
- **Local model quality** determines generated-program quality; ADM's guarantees are about *process honesty and containment*, not about the cleverness of any particular free model.
- `VERSION` is `0.5.2-dev` — a development version.

## 10. Suggested review entry points

1. `adm/build.py` + `adm/ollama_direct.py` — the pipeline and repair loop (the heart).
2. `adm/sandbox.py` + `adm/provision.py` — the confinement/threat model.
3. `adm/package.py` + `tests/test_package_052.py` — the newest subsystem.
4. `adm/dashboard.py` — the GUI and the build→package gate (`finish_build`/`start_package`/`finish_package`).
5. `tools/fuzz_adversarial*.py` — the adversarial test strategy and what has been hardened.
6. `.github/workflows/windows-desktop-build.yml` — how everything is verified on real Windows.

---

*Handoff 052. All source referenced here is on `main` @ `d4c2c7c`. The accompanying `ADM-052-source.zip` is a self-contained snapshot of `adm/`, `tests/`, `tools/`, `.github/`, and the build scripts.*
