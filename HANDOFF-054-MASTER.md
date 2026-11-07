# ADM-054 — Cumulative Master Engineering Handoff

**Date:** 2026-11-07
**Repository:** https://github.com/DevTunaSoft/autonomous-dev-manager (NOT ForgeOS)
**Working branch:** feat/adm-054-test-coverage-gate
**Verified baseline:** ADM-053 merged into main at 424064f278c9cef4d9cd8776f358976f7a660384.
**Baseline CI:** https://github.com/DevTunaSoft/autonomous-dev-manager/actions/runs/42417238103 — both Windows jobs passed; fuzz round 29 had 3,063 checks and zero errors.
**054 status:** Under development. Do not claim 054 Windows CI or real-Ollama acceptance until separately verified.

## Mission

ADM is a novice-facing, single-app Windows desktop autonomous software builder. The user describes the desired program once, and ADM plans plain-language acceptance checks, allows plan approval, generates tests and code via a free local AI, executes generated code inside the configured Windows restricted runner, repairs defects, verifies test results twice and attempts standalone EXE packaging. No Docker or paid AI is required by default.

ADM-053 integrated local, deterministic, role-specific, skill-like guidance without introducing new model calls. ADM-054 corrects a structural test-integrity gap: the AI previously could generate fewer discoverable methods than the number of approved checks while the test runner would still report the incomplete suite passing.

## Root cause and consequence

Earlier adm/build.py validate_tests required only one test method and one assertion anywhere in an AST, without comparing the number of discoverable TestCase methods to the approved plan's checks. If a user approved five checks and the AI generated one actual test, the program could be reported as built and all five checks passing when only one was tested. Duplicate methods/classes are silently overwritten by Python and skip/decorator constructs can disguise missing tests.

No semantic automatic test oracle can guarantee that a test matches the original requirement. This fix enforces the necessary structural minimum, not a sufficient semantic correctness proof.

## Exact ADM-054 files

- adm/build.py: New _discoverable_tests AST inventory of unittest.TestCase and IsolatedAsyncioTestCase methods; supports aliased imports. Reject duplicate class and method names, disabled/skipped/decorated and nonasserting methods. validate_tests receives required_checks and previous_names. build_from_plan checks counts before scaffold and inference, and amendment requires additional new method names.
- tests/test_build_052.py: Existing trivial-tests baseline fixture now includes one trivially passing test per approved check, preserving the original test that such tests must be rejected because they pass before code generation.
- tests/test_coverage_gate_054.py: Structured unit and integration checks for test counting, duplicate names, skips/decorators, malformed data, aliases, amendments, randomized coverage and fail-before-scaffolding behavior.
- tools/fuzz_adversarial30.py: Independent seeded fuzz harness for omitted tests, duplicate methods, skips, decorators, non-discoverable methods and malformed envelopes.
- .github/workflows/windows-desktop-build.yml: Pull-request Windows regression/build remains active; adds fuzz round 30 and exports complete source ZIP, checksum, cumulative 054 handoff and regression evidence.
- README.md: Novice-facing instructions and accurate 053/054 status.
- HANDOFF-054-MASTER.md: This cumulative document, including the complete earlier 053 and 052 handoffs.

## Safety and functionality contracts

1. Local/free AI first; no silent paid API usage. Do not leak user source to remote AI without explicit consent.
2. Generated code may run only in the configured restricted Windows runner. No Docker requirement. Never run generated model code on the host as part of checking its AST.
3. Only approved plans can build. Each new approved check requires a discoverable, asserting unittest test method; amendments must contribute new method names and must preserve existing tests.
4. Test files/requirements remain frozen through implementation and repair. Tests must fail before new code exists, then pass in two independent test processes before reporting success.
5. Edits remain constrained to reviewed application files and crash-journal recovery; preserve full failure evidence, project lock behavior and rollback safeguards.
6. Packaged ADM and generated EXEs are distinct deliverables with distinct acceptance criteria; an EXE packaged on GitHub runners is not verified on the user's Windows computer.

## Build, regression and fuzz reproduction

From the repository root with Python 3.12 or 3.13 in a trusted development environment:

    python -m compileall -q adm tests
    python -m unittest discover -s tests -p test_coverage_gate_054.py -v
    python -m unittest discover -s tests -p test_build_052.py -v
    python -I tools/fuzz_adversarial30.py
    python -B -m adm.regression --root . --timeout 300 --output regression-054.json

The Windows Actions workflow runs source compilation, GUI startup, packaged EXE smoke, simulated Ollama repair, request window and generated-project packaging; independent full Windows regression and fuzz rounds 1-30; and uploads source/handoff artifacts. Do not merge unless both jobs succeed, logs show no concealed failures, and artifacts actually exist.

## Risks and open defects

- Static AST validation cannot determine whether a distinct test matches each individual approved check. Add explicit check-to-test traceability, mutation testing and independent review later.
- Amendments presently preserve old method names but not the complete old assertion bodies. This needs a separate, test-driven hardening step to prevent weakening earlier requirements. The new quantity guard alone is insufficient to fix this.
- The generated-program capabilities remain Python-focused and resource-limited; local model quality and CPU performance need real-world measurement.
- Real local-Ollama and user's physical Windows 11 acceptance are not verified by fake-server CI.
- A Windows sandbox based on a restricted account and firewall denies many capabilities but is not identical to hardware virtualization.
- End-user generated-project packaging still needs trusted PyInstaller on the target machine.
- The current role skills are not independent multiagent orchestration. Future agents must not bypass test gates or create paid/cloud dependencies.

## Recovery and continuation instructions

1. Use DevTunaSoft/autonomous-dev-manager, not ForgeOS. Compare main with the feature branch and latest PR. Read this handoff, adm/build.py, tests/test_coverage_gate_054.py, tools/fuzz_adversarial30.py and CI workflow.
2. Run focused tests and fuzz round 30, then full regression. Investigate any failure's original evidence, fix the root cause, add a new adversarial regression and rerun the entire suite.
3. Verify both Windows jobs and inspect their logs. Verify the source ZIP, SHA-256 file, full cumulative handoff, Windows executable and regression artifacts exist; track run IDs and head commit SHAs.
4. Once green, merge with expected head SHA. Do not claim production readiness based solely on CI; conduct live-model, real-Windows sandbox and packaged EXE acceptance.
5. Next: protect amendment test bodies and class identity, then persist phase checkpoints and restartable queued tasks; add proper local model routing and explicit independent evaluator; improve novice GUI guidance and executable packaging.
6. Every development cycle must include the entire current tracked code tree, tests, relevant setup instructions, source ZIP with integrity checksum, thorough cumulative master handoff, latest build evidence, defects and recovery procedure.
7. Never request repeated approval for routine scoped engineering, never weaken safety invariants to get a green build, and never claim tests/builds succeeded without evidence.

## Architecture decisions (ADM-054)

- Enforce generated-test coverage count before scaffolding because the user-approved plan, not a model's opinion, defines the minimum number of checks.
- Count discoverable unittest class methods through static AST parsing, not by executing untrusted generated tests on the host.
- Reject skipped or decorated methods and duplicate definitions because their runtime behavior cannot safely represent independent approved checks.
- Keep the new count guard additive to the earlier baseline-must-fail and two-pass verification gates.
- Preserve cumulative history by embedding the complete ADM-053 master handoff (which embeds 052).

---

# Previous complete ADM-053 master handoff (including ADM-052)

# ADM-053 — Complete Engineering Handoff and Recovery Instructions

**Date:** 2026-11-07
**Correct repository:** https://github.com/DevTunaSoft/autonomous-dev-manager
**Working branch:** feat/adm-053-local-workflow-skills
**Base:** main at 92f823560b0985869f4c651766bb3282b001a114
**Version:** ADM-052 baseline plus ADM-053 development integration; do not relabel the executable as a verified new release.
**Commit/test honesty:** all 053 source changes are on an isolated branch. Commits prove uploads, not runtime correctness. Historical Windows CI success belongs to ADM-052 (run 42157070851); new PR results must be evaluated independently.
**Scope:** one unified Windows desktop app, free/local-first inference, no Docker required, user need not code, do not weaken frozen tests or sandbox isolation.

## 1. User goal and project identity

ADM is a turnkey, plain-language software builder. The person states a requirement once; ADM plans a small Windows deliverable, presents understandable acceptance checks, asks for approval only when genuinely needed, writes code and frozen tests, runs the generated program in a configured sandbox, analyzes failures and attempts recovery, and packages a deliverable only after evidence-based success. The whole experience must remain one app. It is **not** the separate DevTunaSoft/ForgeOS repository.

Prior work was incorrectly audited under ForgeOS; this branch and handoff concern ONLY DevTunaSoft/autonomous-dev-manager. Preserve the existing working ADM-052 architecture. The user's broader requested ADM evolution includes multi-model local orchestration, multi-agent-style specialist roles, durable checkpoints, resumable executions, context/token economy, secure extensible skills, automatic testing and high-quality novice-facing guidance.

## 2. Sources of architectural ideas and licensing boundary

Reviewed projects:
- https://github.com/shanraisshan/claude-code-best-practice — role separation, skill instructions, context discipline, plan/code/review methodology and agent orchestration design.
- https://github.com/datawhalechina/easy-vibe — beginner-first software specifications, project-oriented learning, explicit validation and staged development.

These are **conceptual references**. ADM-053 contains a fresh standard-library implementation, does not bundle or invoke the Claude Code CLI, and does not copy educational source files. Each reference repo's license must be checked before any future code/assets are copied. Current changes do not introduce external runtime dependencies.

## 3. Changes made in 053 — what each file does

| File | Change and rationale |
|---|---|
| adm/skills.py | New fixed, offline workflow roles and context-selected skills; bounded deterministic instructions for planning, testing, and repair |
| adm/intake.py | Inject trusted planner guidance before user request without changing plan JSON schema or approval requirements |
| adm/build.py | Attach test-design guidance to frozen-test generation; existing baseline-must-fail rule remains intact |
| adm/context.py | Attach implementer/reviewer guidance to model repair prompts; failure evidence and full-source replacement contract unchanged |
| adm/ollama_direct.py | Reserve additional token-context budget for new guidance to prevent silent context truncation |
| adm/selftest.py | Include the new runtime module in packaged import-smoke coverage |
| BUILD-WINDOWS-DESKTOP.cmd | Include the new module explicitly in PyInstaller hidden imports |
| tests/test_skills_053.py | Role selection, prompt integration, malformed inputs, injection resistance, boundedness and seeded fuzz tests |
| tools/fuzz_adversarial29.py | Independent randomized role/skill safety harness (three roles, four budgets, 250 iterations each) |
| .github/workflows/windows-desktop-build.yml | Enable pull-request validation as well as main pushes; execute fuzz harness 29 |
| README.md | Replace stale ADM-051 overview with current workflow, user instructions and explicit limitations |
| HANDOFF-053-MASTER.md | New cumulative handoff covering baseline, changes, testing, defects and future recovery |

### Role and skill selection

The new code makes **no additional AI inference calls**. It uses the current model request for each phase; it simply supplies a small, trusted, deterministic role section:
- PLANNER: observable requirements, narrow scope, novice language, blocking questions only.
- TEST DESIGNER: deterministic nontrivial tests grounded in approved checks, no weakening tests.
- IMPLEMENTER AND REVIEWER: smallest complete fix grounded in real failure output; no claims of success without tests.

Optional skill headings cover security, data integrity, concurrency, desktop UX, resource limits and network/error handling. Requests are scanned as **data** using whole-word keywords, a maximum input scan of 12,000 characters, and at most two extra static skill descriptions. No user request text is repeated in the selected skill. This is **not yet a real parallel agent system**, an autonomous skills marketplace or an external plugin executor.

### Invariants deliberately preserved

1. No automatic paid inference. Ollama/local remains first; any remotely sent source must require explicit consent.
2. No speculative passing status: verify with real frozen tests, repeat passing verification, reject trivial tests, retain full evidence.
3. Generated code stays inside Windows sandbox; avoid running untrusted model-generated code on host.
4. Only application source files presented in full to the model may be replaced; protected files and tests are not edited by the repair loop.
5. Bounded context and output sizes; incomplete or malformed patch shapes refuse safely.
6. Existing program behavior and GUI must remain usable; no second app or Docker setup for the user.

## 4. Build and test procedure

Run on Python 3.12 or 3.13 in a trusted checkout. On Windows also verify the EXE and sandbox separately.

~~~text
python -m compileall -q adm tests
python -m unittest discover -s tests -p test_skills_053.py -v
python -I tools/fuzz_adversarial29.py
python -B -m adm.regression --root . --timeout 300 --output regression-053.json
~~~

Existing GitHub Actions workflow windows-desktop-build.yml contains two Windows jobs:
- windows-build: module compile, Windows GUI startup, bundled Python, PyInstaller, real packaged EXE smoke, fake-Ollama packaged repair, request-window and generated-project packaging checks.
- windows-full-regression: project-wide test runner and 29 standalone adversarial fuzz harnesses.

**Evidence as of drafting this handoff:** ADM-052's November 6 Windows workflow succeeded, and branch source updates have been recorded. ADM-053's full Windows CI, real local Ollama model, executable on the target Windows 11 laptop, independent installer/sandbox containment, and production acceptance are **not yet demonstrated** here. DO NOT claim this release is tested until those checks have actual evidence.

## 5. Known risks, limitations and blockers

- A skill only influences the model; it is not a separately scheduled agent and cannot provide independent review. The approved frozen tests, not skill text, remain the gate.
- Static word matching does not recognize semantic synonyms or every language; safe fallback is the trusted stage instruction.
- The finite inference window remains limiting for large projects; the larger fixed budget intentionally reserves space for skill guidance.
- The current Python project pipeline supports constrained deliverables, not arbitrary platforms or instant full-stack applications.
- Actual model ability depends on the chosen local model and memory/CPU; CI fake-model tests are not representative of quality.
- The sandbox is Windows-specific and requires initial administrator provisioning. The current deny-list reduces risk but is not equivalent to hardware virtualization.
- Packaging the app ADM itself is supported in CI; packaging a generated app on the end-user machine still needs an available trusted PyInstaller installation.
- User's real Windows installation with local inference and generated EXE must be independently validated.
- Live hosted CI may take time to complete; any PR should remain unmerged until its jobs pass or failures are fully resolved.

## 6. Immediate continuation checklist

1. Open a PR from feat/adm-053-local-workflow-skills to main; check the pull-request CI workflow is registered and the jobs actually start.
2. Inspect all tests, especially tests/test_skills_053.py, role minimum context budget, call-site wiring, hidden-import tests, prior prompt assertions and complete regression. Repair root causes and rerun, never weaken frozen gate.
3. Run fuzz_adversarial29.py and all earlier 28 harnesses. Add further fault-injection coverage for oversized and malicious requirements, missing model transport and prompt context calculations.
4. Verify a generated project in Windows sandbox using a fake test model; verify it separately using the actual selected local model on a Windows computer.
5. Generate or update complete code archive and SHA-256 integrity report; keep the current master handoff with the same snapshot.
6. Once PR is green and independently reviewed, merge it without discarding any prior ADM-052 work.
7. Next major engineering phases: durable phase checkpoints; idempotent task resumption, staged independent evaluator, efficient local multi-model routing, crash-safe transaction journal for generated edits, skill extension API with strict trust policy, all within the one ADM GUI.
8. Reconcile accumulated documentation and prepare detailed nontechnical instructions for first run, model selection, approval, build, diagnostics, restore and ZIP export.

## 7. Exact recovery protocol for a new AI, machine, or chat

- Clone/download **the correct ADM repository** and inspect both main and the named 053 branch; never use ForgeOS as the project base.
- Inspect README.md and this handoff first, then adm/intake.py, adm/build.py, adm/context.py, adm/ollama_direct.py, adm/skills.py, adm/sandbox.py and the 053 tests.
- Do not infer production-readiness from earlier historical counts. Use GitHub Actions/CI run IDs and local command output as evidence.
- For a failed or interrupted file edit, inspect adm/repair_recovery.py, adm/recovery.py and adm/project_lock.py before attempting recovery. Preserve originals and avoid concurrent writes.
- For local build failure, retain regression JSON and Windows build-evidence artifacts. Isolate the first failing test, root-cause the defect, patch it, rerun focused tests **and full suite**, then add a new independent adversarial condition.
- Do not prompt the user to approve routine development steps. Ask only when a security boundary, new paid dependency, privileged access or irreversible consequential action demands it.
- After each development cycle, provide the complete repository source, cumulative handoff, test evidence, discovered defects and concrete next steps.

## 8. Remaining ADRs / design decisions

**ADR-053-01:** Integrate role and skill guidance by extending existing inference prompts, not spinning up more models. Reasons: zero extra paid cost; minimal tokens; preserves current stable state machine. Constraint: cannot claim independent multi-agent execution.

**ADR-053-02:** Keep selected skills static and trusted. Keyword matching is used solely to choose existing instructions; raw user text is never turned into an executable skill. Future user-authored skills require validation, explicit trust boundaries and security review.

**ADR-053-03:** Reserve conservative context for skills in direct repair rather than allowing the existing Ollama context to silently truncate important evidence.

**ADR-053-04:** Isolate all work in a feature branch and require pull-request CI to establish measured progress before merge.

**ADR-053-05:** Source history is cumulative. The current Git commit already contains all tracked source files, historical handoffs, tests and previous source manifests. The next artifact must be a complete ZIP of that source plus this handoff; not a patch-only delivery.

---

The full ADM-052 handoff is embedded below unchanged as the historical baseline. The source inventory above is regenerated from the current feature branch at the point this handoff is committed. Treat past test outcomes as historical, not as proof for current modifications.


---

## ADM-053 repository source inventory

| Tracked source path | Baseline Git blob bytes / status |
|---|---:|
| .github/workflows/gui-screenshots.yml | 501 |
| .github/workflows/sandbox-probe.yml | 1195 |
| .github/workflows/windows-desktop-build.yml | 7812 |
| adm/__init__.py | 46 |
| adm/__main__.py | 1265 |
| adm/acceptance.py | 4193 |
| adm/adaptive.py | 3251 |
| adm/agent_cli.py | 1699 |
| adm/agent.py | 10660 |
| adm/ai_status.py | 605 |
| adm/backends.py | 11200 |
| adm/build.py | 17438 |
| adm/cli.py | 1065 |
| adm/context.py | 9327 |
| adm/core.py | 5610 |
| adm/daemon.py | 6621 |
| adm/dashboard.py | 31421 |
| adm/desktop_entry.py | 1358 |
| adm/desktop.py | 3878 |
| adm/diagnostics.py | 8694 |
| adm/engine.py | 8621 |
| adm/firstrun.py | 11018 |
| adm/intake_gui.py | 7909 |
| adm/intake.py | 14214 |
| adm/live_acceptance.py | 3428 |
| adm/model_probe.py | 4342 |
| adm/model_selection.py | 3540 |
| adm/ollama_cli.py | 2691 |
| adm/ollama_direct.py | 18180 |
| adm/ollama_health.py | 2782 |
| adm/package.py | 6455 |
| adm/pipeline_cli.py | 1143 |
| adm/pipeline.py | 5190 |
| adm/preflight.py | 2593 |
| adm/project_lock.py | 2739 |
| adm/provision.py | 3853 |
| adm/pyruntime.py | 4139 |
| adm/queued_ai.py | 7078 |
| adm/recovery.py | 2997 |
| adm/regression.py | 12905 |
| adm/release_entry.py | 146 |
| adm/release.py | 7276 |
| adm/repair_recovery.py | 4167 |
| adm/repomap.py | 6280 |
| adm/runtime_install.py | 4134 |
| adm/sandbox.py | 11337 |
| adm/selftest.py | 3077 |
| adm/setup_cli.py | 1167 |
| adm/setup.py | 6124 |
| adm/skills.py | branch addition |
| adm/theme.py | 8610 |
| adm/windows_startup.py | 2841 |
| adm/worker_cli.py | 1510 |
| adm/worker.py | 13843 |
| BUILD-WINDOWS-DESKTOP.cmd | 1931 |
| HANDOFF-052-MASTER.md | 58086 |
| HANDOFF-053-MASTER.md | branch addition |
| handoff-front-053.md | branch addition |
| README.md | 829 |
| tests/test_acceptance.py | 1134 |
| tests/test_adaptive_worker.py | 2367 |
| tests/test_adaptive.py | 1422 |
| tests/test_agent.py | 5341 |
| tests/test_ai_inspection.py | 2690 |
| tests/test_auto_queue.py | 2593 |
| tests/test_build_052.py | 15570 |
| tests/test_build_hidden_imports_049.py | 581 |
| tests/test_context_051.py | 10884 |
| tests/test_core.py | 2298 |
| tests/test_daemon_lifecycle.py | 1997 |
| tests/test_daemon_robustness_050.py | 4181 |
| tests/test_daemon.py | 2254 |
| tests/test_dashboard_logic_052.py | 4181 |
| tests/test_desktop_entry_040.py | 2355 |
| tests/test_desktop_entry_exit.py | 1749 |
| tests/test_desktop.py | 2588 |
| tests/test_diagnostics_052.py | 5252 |
| tests/test_engine.py | 2475 |
| tests/test_firstrun_050.py | 6138 |
| tests/test_hardening_050.py | 4546 |
| tests/test_hardening_adversarial_052.py | 6084 |
| tests/test_hardening_agent_052.py | 1706 |
| tests/test_hardening_firstrun_052.py | 2673 |
| tests/test_hardening_queue_052.py | 3900 |
| tests/test_hardening_release_052.py | 2905 |
| tests/test_hardening_round6_052.py | 3428 |
| tests/test_independent_retest.py | 1910 |
| tests/test_intake_052.py | 8694 |
| tests/test_live_acceptance.py | 1955 |
| tests/test_local_transport_security.py | 1579 |
| tests/test_model_probe.py | 2521 |
| tests/test_model_selection.py | 1690 |
| tests/test_ollama_direct.py | 5479 |
| tests/test_ollama_health.py | 2944 |
| tests/test_package_052.py | 5334 |
| tests/test_packaged_smoke_041.py | 1534 |
| tests/test_pid_alive_049.py | 1121 |
| tests/test_pipeline.py | 4770 |
| tests/test_process_tree.py | 1492 |
| tests/test_project_lock.py | 2959 |
| tests/test_provision.py | 3888 |
| tests/test_pyruntime_050.py | 2534 |
| tests/test_queued_ai.py | 2829 |
| tests/test_recovery.py | 3835 |
| tests/test_regression_evidence_047.py | 3256 |
| tests/test_regression_guards.py | 1550 |
| tests/test_regression_log_isolation_048.py | 1929 |
| tests/test_regression_retention_049.py | 2345 |
| tests/test_regression.py | 10731 |
| tests/test_release_hidden_imports_049.py | 497 |
| tests/test_release.py | 3702 |
| tests/test_repair_commit.py | 2203 |
| tests/test_repair_recovery.py | 3276 |
| tests/test_repomap_backends_051.py | 11769 |
| tests/test_runtime_install_052.py | 2932 |
| tests/test_sandbox_052.py | 2214 |
| tests/test_sandbox_harden_052.py | 1014 |
| tests/test_sandbox_integration_052.py | 2585 |
| tests/test_setup.py | 4113 |
| tests/test_skills_053.py | branch addition |
| tests/test_supervisor_singleton_045.py | 1828 |
| tests/test_windows_build_verifier_044.py | 1374 |
| tests/test_windows_startup.py | 1977 |
| tests/test_worker.py | 5761 |
| tools/fake_ollama.py | 1180 |
| tools/fuzz_adversarial.py | 10373 |
| tools/fuzz_adversarial10.py | 4771 |
| tools/fuzz_adversarial11.py | 3368 |
| tools/fuzz_adversarial12.py | 3662 |
| tools/fuzz_adversarial13.py | 4232 |
| tools/fuzz_adversarial14.py | 5855 |
| tools/fuzz_adversarial15.py | 5067 |
| tools/fuzz_adversarial16.py | 6369 |
| tools/fuzz_adversarial17.py | 4779 |
| tools/fuzz_adversarial18.py | 4574 |
| tools/fuzz_adversarial19.py | 6310 |
| tools/fuzz_adversarial2.py | 7596 |
| tools/fuzz_adversarial20.py | 4199 |
| tools/fuzz_adversarial21.py | 2686 |
| tools/fuzz_adversarial22.py | 5742 |
| tools/fuzz_adversarial23.py | 4475 |
| tools/fuzz_adversarial24.py | 4917 |
| tools/fuzz_adversarial25.py | 4108 |
| tools/fuzz_adversarial26.py | 7692 |
| tools/fuzz_adversarial27.py | 4687 |
| tools/fuzz_adversarial28.py | 3661 |
| tools/fuzz_adversarial29.py | branch addition |
| tools/fuzz_adversarial3.py | 6021 |
| tools/fuzz_adversarial4.py | 6927 |
| tools/fuzz_adversarial5.py | 3900 |
| tools/fuzz_adversarial6.py | 7897 |
| tools/fuzz_adversarial7.py | 5457 |
| tools/fuzz_adversarial8.py | 5247 |
| tools/fuzz_adversarial9.py | 4243 |
| tools/make_handoff.py | 2552 |
| tools/sandbox_live_check.py | 10827 |
| tools/sandbox_probe.py | 7337 |
| tools/sandbox_scan.py | 426 |
| tools/screenshot_gui.py | 1960 |
| tools/verify_bundled_python.py | 876 |
| tools/verify_package.py | 1322 |
| tools/verify_request_window.py | 1542 |
| tools/verify-packaged-repair.ps1 | 1559 |
| VERIFY-WINDOWS-DESKTOP.ps1 | 3828 |

**Note:** Paths updated since the 052 baseline retain baseline blob sizes here. The Git checkout or 053 source archive, not this table, is the authoritative code source.

---

## Appendix: complete earlier ADM-052 master handoff (unchanged)

# ADM — Autonomous Development Manager · Master Handoff 052

| | |
|---|---|
| **Repository** | https://github.com/DevTunaSoft/autonomous-dev-manager |
| **Branch / commit** | `main` @ `d4c2c7c` (code) · handoff committed on top |
| **Version** | `0.5.2-dev` (`adm/diagnostics.py: VERSION`) |
| **Date** | 2026-11-05 |
| **Language / runtime** | Python 3.12 (the version the EXE bundles); code also runs on 3.13 |
| **Platform** | Windows 11 desktop app; test suite is cross-platform |
| **Size** | 50 modules in `adm/` (~6,640 LOC), 64 test files, 28 fuzz harnesses |
| **Test status** | `OVERALL: PASS; 450 completed tests` — **green on Windows CI too** (both windows-build and windows-full-regression jobs pass; EXE artifact produced) |
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

**Run everything:** `python -m adm.regression` → expect `OVERALL: PASS; 450 completed tests`.
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
| **21** | `…21.py` | **core.Supervisor** durability: corrupt job row (bad JSON / non-list / empty / non-str) | **5 bugs:** `run_next` did an unguarded `json.loads` + unvalidated argv, crashing the loop. Fixed to mirror `worker.run_once` (fail the one task cleanly). |
| **22** | `…22.py` | **provisioning/setup**: `execute_plan` corrupt journals, `execute_step`/`build_plan` malformed inputs | **9 bugs:** a tampered resume journal (non-dict result value) and non-dict `step`/`binaries`/`hardware` crashed with `AttributeError` on `.get()`. Fixed with dict-shape validation → `ValueError`. |
| **23** | `…23.py` | **runtime install / AI reconcile**: `fixup_pth` on corrupt `._pth`; `inspect_repair`/`enqueue_repair` guards | **1 bug:** `fixup_pth` read the embeddable `._pth` as strict UTF-8, so a corrupt/non-UTF8 file crashed the runtime install. Fixed with `errors='replace'`. (`queued_ai` robust.) |
| **24** | `…24.py` | **model_probe**: hostile Ollama responses to `/api/tags` & `/api/generate` (injected opener) | **0 bugs** — redirect refusal, size cap, shape validation, broad except all hold. |
| **25** | `…25.py` | **fault injection on the TEST RUNNER**: raises/timeouts/malformed/None results | **18 bugs:** the baseline runner call was unguarded, so a flaky executor crashed the build (OSError/TimeoutExpired/KeyError/TypeError). Fixed with a normalising `_invoke_runner()` at every call site. |
| **26** | `…26.py` | **build-level concurrency + fault**: 7 `build_from_plan` racing on one folder; a generator crashing mid-build | **0 bugs** — project lock serialises cleanly (one builds, rest fail with clear SafetyError), releases on a faulting build (later build on same folder succeeds), no deadlock/corruption. |
| **27** | `…27.py` | **apply_patch containment**: traversal/absolute/subdir/symlink/control-char/oversized/protected-file patches | **0 crashes; 1 cross-version hardening:** all escapes rejected; added a control-char (null byte) guard so containment raises SafetyError on Python 3.12 too (not just 3.13). |
| **28** | `…28.py` | **sandbox command-builders**: `cmdline_for` argv+stdout quoting, `refuse_hardened_location` bypass attempts | **6 bugs:** `cmdline_for` validated argv but not the `stdout_path` it interpolates into the same command line → a quote/metachar there could inject a command. Fixed: same validation for the output path. (`refuse_hardened_location` solid.) |

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

0. **Windows CI is green and produces `ADM-Desktop.exe`** (artifact `ADM-Desktop-Windows-unverified`), with the embeddable Python runtime bundled (`pyembed`), so the ADM app itself runs as a standalone EXE on Windows without a Python install. Runtime *acceptance* on a real machine (below) is still unproven.
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
python3 -m adm.regression        # expect: OVERALL: PASS; 450 completed tests
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
| 21 | 5 | `core.Supervisor.run_next` unguarded `json.loads` + unvalidated argv | validate stored command; fail the one task cleanly (mirror `worker.run_once`) | `test_core` |
| 22 | 9 | `execute_plan` didn't check result values are dicts; `execute_step`/`build_plan` called `.get` on possibly-non-dict args | dict-shape validation → `ValueError` | `test_provision`, `test_setup` |
| 23 | 1 | `fixup_pth` decoded `._pth` as strict UTF-8 | decode with `errors='replace'` | `test_runtime_install_052` |
| 24 | 0 | — (model_probe hostile-response parsing held) | — | harness only (injected opener) |
| 25 | 18 | baseline test-runner call unguarded; a flaky executor crashed the build | normalising `_invoke_runner()` at baseline/attempt/verification | `test_ollama_direct` |
| 26 | 0 | — (build-lock contention + release-on-fault held) | — | harness only (3x stable) |
| 27 | 0* | *proactive cross-version hardening:* null-byte path raised ValueError on Py3.12 (EXE) vs False on 3.13 | explicit control-char guard in `apply_patch` → SafetyError on all versions | `test_ollama_direct` |
| 28 | 6 | `cmdline_for` didn't validate the sandbox `stdout_path` → command-injection vector | hold the output path to the same metachar/empty/backslash rule | `test_sandbox_052` |
| Win | 1 | **Windows-only product bug:** the generated program crashed (`UnicodeEncodeError`, cp1252) when its title/output contained non-ASCII (e.g. an accented or emoji program name) | generated entry reconfigures stdout/stderr to UTF-8 at startup | `test_package_052` |

**Totals this pass:** 100 defects fixed across rounds 10, 11, 13, 14, 15, 16, 17, 21, 22, 23, 25, 28, plus a cross-version containment hardening in round 27. Rounds 12, 18, 19, 20 found none: 18 proves the repair-loop honesty invariants, 19 confirms archive hardening, 20 confirms the worker single-owner claim under real concurrency. Round 21 then found a latent corrupt-DB-row crash in the secondary (ADM-002) supervisor, fixed for consistency with the hardened worker. The hot untrusted-input and concurrency paths are well-hardened; occasional latent issues remain in secondary code paths — e.g. round 25 found an unguarded baseline test-runner call that crashed the build under a flaky executor, a genuine autonomous fault-tolerance gap now fixed. All are concurrency/robustness/data-corruption classes against untrusted model output, corrupt on-disk state, and hostile inputs — none required target hardware to reproduce.

**Remaining risks / not verified here:** real local-model generation quality (fake model used in this environment); the actual PyInstaller EXE build and the Windows sandbox confinement (Windows CI only, not this Linux workspace); GUI pixel rendering (logic is tested headless, screenshots run in a separate CI job).


*Handoff 052. Code is on `main` @ `d4c2c7c`; the accompanying `ADM-052-source.zip` is a self-contained snapshot of `adm/`, `tests/`, `tools/`, `.github/`, and the build scripts. The session transcript is delivered separately and is intentionally not in the repository.*
