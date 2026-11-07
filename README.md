# Autonomous Development Manager (ADM)

**Verified baseline:** ADM-054 (merged after Windows CI passed, 479 tests) · **Under development:** ADM-055 immutable amendment tests.

ADM is a **single Windows desktop application** for someone who does not know how to program. Describe a small application in ordinary language; ADM uses a local AI to propose a plan and acceptance checks, creates tests, implements the Python application, repairs failures, and attempts to package a Windows EXE. A test runner—not the AI's confidence—decides whether a build passed.

## How to use ADM (plain language)

1. Get the Windows **ADM-Desktop.exe** artifact from a **successful Windows build** in GitHub Actions. The artifact is explicitly labeled **unverified for real-PC acceptance**.
2. Start ADM on Windows 11. Follow its first-run prompts. Setting up its restricted Windows execution account requires administrator access once.
3. Install and run a **free local model** with Ollama. ADM can detect local endpoints; a fake-model CI test proves the plumbing only, **not actual model quality**.
4. Type what you want to build in the request window. Review the proposed features and checks, then approve.
5. ADM writes tests, attempts code repairs in its configured restricted runner, verifies results and reports failures instead of declaring imaginary success.
6. Packaging a generated application to an EXE may require a separate trusted Python/PyInstaller installation. This packaging dependency is **not yet fully bundled for the end-user machine**.

**Do not execute untrusted generated projects outside the configured sandbox.** The sandbox is Windows-specific and requires setup. No Docker or paid AI subscription is required by default. Remote model access is not automatic.

## What ADM-053, ADM-054 and ADM-055 improve

This branch introduces **local, deterministic workflow skills**, adapting ideas—not copying source—from:

- [Claude Code Best Practice](https://github.com/shanraisshan/claude-code-best-practice): planning, test-design and implementation/review roles; reusable skills and context hygiene.
- [Easy-Vibe](https://github.com/datawhalechina/easy-vibe): beginner-first specification and verification workflows.

ADM still uses its existing local model calls; **there are no new paid services, models, containers or background agents**. New code selects up to two trusted, bounded instructions for each stage based on the task. No user text is copied into the skill itself. Context budgets remain enforced, and acceptance tests remain frozen.

**ADM-053 was merged after Windows CI passed.** ADM-054 adds a fail-closed acceptance-test coverage check: when ADM's local AI creates tests from the checks the user approved, the test file must contain at least that many discoverable, asserting unittest test methods. Amendments must add new test methods for new checks without removing earlier ones; duplicate, skipped and decorated test methods are refused. These checks cannot prove the generated tests match the user's meaning, so a real-device review remains required.

**ADM-054 passed both Windows CI jobs and merged into main.** ADM-055 closes a second integrity gap: during a change to an existing ADM project, its earlier approved tests, assertions, fixtures, imports and helpers must remain structurally unchanged. Additional tests are permitted, but rewriting earlier checks or shadowing imports causes an immediate refusal before any project write. Static AST preservation is not full semantic proof. ADM-055 is under review until its own Windows regression, fuzz and executable jobs pass.

## Development and verification

From a trusted Python 3.12 checkout:

~~~text
python -m compileall -q adm tests
python -m unittest discover -s tests -p "test_skills_053.py" -v
python -I tools/fuzz_adversarial29.py
python -m unittest discover -s tests -p "test_coverage_gate_054.py" -v
python -I tools/fuzz_adversarial30.py
python -m unittest discover -s tests -p "test_amend_preservation_055.py" -v
python -I tools/fuzz_adversarial31.py
python -B -m adm.regression --root . --timeout 300 --output regression-053.json
~~~

The GitHub Actions Windows workflow builds the desktop EXE, runs a full regression job and adversarial harnesses, and tests packaging with a **fake** local model. Actual operation with a real local AI on the intended Windows PC still requires separate acceptance testing.

## Documentation

- [ADM-052 master handoff](HANDOFF-052-MASTER.md): cumulative baseline architecture, history, security boundaries, test and packaging evidence.
- [ADM-053 master handoff](HANDOFF-053-MASTER.md): role and skills integration plus verified CI.
- [ADM-054 master handoff](HANDOFF-054-MASTER.md): accepted-test coverage safeguards and verified CI.
- [ADM-055 master handoff](HANDOFF-055-MASTER.md): immutable amendment assertions, fraud-resistant validation and full cumulative history.
- [Windows desktop verifier](VERIFY-WINDOWS-DESKTOP.ps1) and [build script](BUILD-WINDOWS-DESKTOP.cmd).

**Release status:** Development prototype; not declared production-ready. Keep generated-source test evidence and review the results before distributing software.
