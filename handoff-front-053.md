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
