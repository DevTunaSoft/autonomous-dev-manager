# ADM-051 — Master handoff (cumulative)

Generated with `tools/make_handoff.py` from this front matter, the repository, and the verbatim earlier handoffs and research appended below. Nothing earlier has been removed.

## 0. Read first: what is and is not proven

**Proven, with evidence (GitHub Actions, `windows-2022` runner, run 41935328816, commit b24b0a3; log saved as `evidence/windows-run-41935328816-adm051.log`):**
- The complete test suite passes on Windows: 320 tests, 49 modules (`OVERALL: PASS; 320 completed tests`). The same 320 pass on Linux.
- `ADM-Desktop.exe` builds with PyInstaller and its packaged self-test passes (SHA-256 `4cffe8ece738f2bd3617ba92164449531f1e6e7e30e717cda8e5e6f607f32a83`).
- The packaged EXE completes a repair loop **against a fake Ollama server** (`verified_direct_repair`, 1 attempt). That proves plumbing, not model quality.
- A real Tk window opens on the runner and shows the first-run local-AI prompt (what is downloaded, how big, where it goes).

**NOT proven (do not claim any of these):**
- Real Ollama inference or the quality of any real model's repairs. Every ADM-051 behavior was tested with fake generators or fake local HTTP servers only.
- A real click-through of the Ollama install and model download (no Ollama or winget on the runner).
- Any isolation of generated code. **There is still no sandbox.** Generated code runs with the user's permissions.
- Crash and reboot recovery on a live Windows session; human use of the GUI; performance on 16 GB or 32 GB PCs.
- The new `local/` backend against a real Jan, LM Studio or llama.cpp server. The `remote/` path exists in code but is not reachable from the CLI or window, and was tested only for validation rules.
- `live_model_verified` is true whenever the real network generator is used, including against the fake Ollama server. Treat it as "used the network code path", not "a real model was verified".
- The EXE is unsigned; Windows SmartScreen will warn.

## 1. Project goal and standing requirements

Source: the owner's history file (reconstructed by an earlier assistant, not verbatim), the owner's messages in this session, and the owner's other-assistant chat (read 2026-11-04).

1. One Windows 11 app for a non-programmer: plain-language request in, working app out.
2. It plans, writes code, manages dependencies, builds Windows EXE / Android APK / web apps, tests, diagnoses, repairs, regression-tests, and resumes after crashes, reboots or context limits.
3. **AI source policy: local first, then genuinely free cloud tiers. Paid accounts are optional, never required or assumed.**
4. Works on the owner's PC: **16 GB RAM, SATA SSD, Windows 11 Pro**. Slow is acceptable. Also 32 GB PCs.
5. **No babysitting:** one instruction starts the work; the main goal, ahead of token savings.
6. AI participates in every stage; local compilers, linters and tests run first; verified fixes are reused before any AI call.
7. Honest test evidence; passing isolated tests is never presented as a working EXE or finished product.
8. Generated code is isolated: no internet by default; refused if it touches paths outside the project folder.
9. First target: Windows EXE. Existing project folders are accepted too. **Web is deferred.** APK later.
10. Every release: a complete cumulative source ZIP, an extremely detailed self-contained handoff, and an explicit statement of what the owner must provide (even "nothing"). Earlier handoffs are preserved.
11. The app must prompt the owner to download a model and say where it goes.
12. The owner does not code ("I know zero about coding"); ADM must actually build the app.
13. Open question, not yet answered by the owner: whether ADM may stop after a fixed number of attempts. Default kept: a bounded loop that escalates, then writes a plain blocker.

## 2. This segment (ADM-051)

**Decisions recorded from the owner (2026-11-04):** Windows EXE first; web later; existing projects yes; Windows 11 Pro; no internet for generated code; refuse outside-folder paths; free cloud tiers allowed; paid accounts optional; Node-based helper tools acceptable if bundled as separate programs; drop OpenHands/SWE-ReX/Docker; drop Janas.

**Research delivered:** `STACK-COVERAGE-ANALYSIS-050.md` and `STACK-SURVEY-051.md` (appended verbatim below). Headline: no single project meets the requirements; borrow designs (mini-swe-agent loop, little-coder small-model guards, Pullboard / Superpowers methods), build the rest. Other git hosts (Codeberg, GitLab, Hugging Face API) could not be searched from the build sandbox.

**Code added or changed (all tested on Linux and Windows):**
- `adm/context.py` — bounded failure views. **Hard rule: reduce what the model reads, never what is tested.** The view always starts with the complete list of failing test ids; the full output is saved to the evidence directory (`baseline-output.log`, `attempt-N-output.log`); repeated lines are collapsed; the test runner remains the only gate (`report["gate"] == "tests_only"`). Also: an attempt ledger (never re-applies an identical patch; tells the next prompt what already failed), patch guards (file not shown in full, empty, identical, deletes most of the file, placeholder text), and failure fingerprints.
- `adm/repomap.py` — an `ast`-based map of the project. Files implicated by tracebacks and by the failing tests' imports are shown in full; others as a names-and-signatures map. A file that was not shown in full can never be replaced. If a relevant file cannot fit the context, the attempt fails closed with "too large" (as before) instead of truncating.
- `adm/backends.py` — model id forms `ollama/…`, `local/…` (any OpenAI-compatible server on `127.0.0.1`: Jan, LM Studio, llama.cpp), and `remote/…` (HTTPS, refused unless the caller passes `allow_remote=True`, which must come from explicit user approval, because prompts contain the user's source). No redirects, no proxies, no credentials in URLs, JSON-mode fallback, fenced-JSON tolerance, and `probe_local_servers` to find servers already running.
- `adm/ollama_direct.py` — uses all of the above; adds the escalation ladder (`escalation_model`, `escalation_generator`, `escalate_after`: after N failed tries, or when the same failure repeats, use a stronger model; the primary model must run on this PC). A rejected patch no longer replaces the real test output with the error text. CLI: `--model local/…`, `--endpoint`, `--escalate-model`, `--escalate-after`.
- `tools/make_handoff.py` — generates this handoff.
- Tests: `tests/test_context_051.py` (16), `tests/test_repomap_backends_051.py` (17). Two bugs were found by these tests and fixed before release (a unittest summary line read as a test name; a failure fingerprint that ignored all but the last error line).

## 3. How to reproduce

```
python -B -m adm.regression --root . --timeout 300 --output out/regression.json   # expect: OVERALL: PASS; 320 completed tests
python -m unittest tests.test_context_051 tests.test_repomap_backends_051 -v
python -B -m adm.ollama_cli --root <project> --evidence <new-empty-dir> --model ollama/qwen2.5-coder:3b --repairs 4 --escalate-model ollama/qwen2.5-coder:7b --escalate-after 2
```
Windows CI: `.github/workflows/windows-desktop-build.yml` (jobs `windows-build`, `windows-full-regression`).

## 4. Architecture additions

`ollama_direct._direct_repair_unlocked` per attempt: excerpt the failure (context) → choose files (repomap) → build prompt with notes of earlier attempts → generate (primary, or escalation) → reject repeats and bad patches → journal and apply → run tests twice → record. Success needs two passing runs, unchanged protected files, and a changed source. The model's opinion has no vote.

## 5. Open risks, in priority order

1. **No sandbox for generated code (critical).** Plan: Windows Sandbox (Pro) as the strong tier (no network; project mapped; one writable results folder); a dedicated low-privilege local account as fallback. Do not use a plain WRITE_RESTRICTED token until a CI experiment shows pipe capture works (a third-party report says child processes fail with 0xC0000142).
2. The window cannot take a request or a project yet.
3. No real-model evidence; small local models may fail on whole-app tasks; escalation to free cloud tiers needs a consent flow and a provider client.
4. Python 3.10+ must be installed by the user; plan: bundle an embeddable Python, with approval.
5. Blocked/deferred jobs are invisible in the window; duplicate queues (`core` vs `worker`); a placeholder 2 GiB admission figure that defers silently.
6. The EXE is unsigned.

## 6. Next steps (build order)

1. Windows CI experiments for the sandbox: restricted token with pipes; dedicated local user plus permissions plus firewall; Job Object limits.
2. Sandbox adapter (Windows Sandbox strong tier, dedicated account fallback).
3. Plain-language request box and plan-then-Approve screen (new project and existing project).
4. Acceptance tests generated from the request and shown in plain words for approval.
5. Verified-fix cache keyed on the failing test signature (exact match, not semantic).
6. Real-model proof on the owner's PC; the 10-app success-rate measurement.
7. Consent flow and client for free cloud tiers; bundle Python.

## 7. What is needed from the owner

For source development: **nothing.** For acceptance:
- Run `ADM-Desktop.exe` on your PC (download the artifact from the latest Actions run) and tell me what the window shows; press "Set up local AI..." and report what happens. This is the first human check of the GUI and the real Ollama install.
- Later, a short script to test Windows Sandbox on your PC (virtualization must be enabled in BIOS; enabling the feature needs administrator approval and a reboot).
- Answer the open question in section 1, item 13, when you are ready.

## 8. Rules for the next developer

- Never describe isolated or fake-server tests as a working product or a verified model.
- Do not reduce what is tested or recorded to save tokens; reduce only what the model reads.
- Keep every earlier handoff; regenerate this one with `tools/make_handoff.py`.
- Read third-party READMEs critically; stars and vendor numbers are claims, not measurements.
