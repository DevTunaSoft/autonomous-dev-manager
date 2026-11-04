# ADM full-codebase review (ADM-049)

Scope: all 36 modules in `adm/` (~3,000 lines) read in full, plus pyflakes and bandit, plus targeted experiments on Linux and on a GitHub Windows runner.
Status key: **FIXED** = verified fix pushed. **VERIFIED** = reproduced by experiment, not yet fixed. **LIKELY** = from reading code, not reproduced.

## Fixed in this review
| # | Sev | Finding | Evidence |
|---|---|---|---|
| 1 | Critical | `worker.pid_alive` used `os.kill(pid, 0)`. On Windows signal 0 is `CTRL_C_EVENT`, so the liveness check sends Ctrl+C to the process group. Called from `recover()` after a crash, it can interrupt the supervisor itself or an unrelated process holding a reused PID. | Windows CI run 41918347028: regression runner died with KeyboardInterrupt. **FIXED** (OpenProcess/GetExitCodeProcess), run 41918605700+ passes. Test: `tests/test_pid_alive_049.py` |
| 2 | High | CRLF line endings broke repair-journal hash matching on Windows. | **FIXED** earlier |
| 3 | High | Windows mandatory byte-range lock covered the owner-metadata bytes. | **FIXED** earlier |
| 4 | Medium | `release.py` desktop build plan lacked `--hidden-import`, would rebuild the broken EXE. | **FIXED**, test `test_release_hidden_imports_049.py` |

## Verified, not yet fixed
| # | Sev | Finding |
|---|---|---|
| 5 | **Critical for the product** | The packaged EXE cannot run project tests or AI-repair jobs. `agent.test_command()`, `queued_ai.enqueue_repair()` and `pipeline` build commands from `sys.executable`, which in the frozen app is `ADM-Desktop.exe`; `desktop_entry.main` rejects unknown arguments ("Unknown desktop arguments: -B -m unittest ..."). The EXE also bundles no Python for running the user's generated project. Needs a bundled/embedded Python runtime (or a re-entrant `--run-python` mode) plus tests of the packaged path. |
| 6 | High | GUI reports "unresponsive" during any job longer than ~15 s. The daemon writes its heartbeat only between jobs (`daemon._serve_locked`), `desktop.status_summary` treats >15 s as stale. Reproduced: running x14 s, then unresponsive for the rest of a 19 s job. AI repairs take minutes. Fix: heartbeat from a background thread or from inside `run_once`. |

## Likely (from reading; needs a test or real run)
| # | Sev | Finding |
|---|---|---|
| 7 | High | Daemon default job timeout is 120 s and the GUI starts it without `--timeout`. One AI repair can legitimately take longer (2 inferences up to 90 s each plus 3 test runs per attempt). Jobs would be killed mid-edit and recovered by the journal, never completing. |
| 8 | High | `ollama_direct.request_patch` sends no `options.num_ctx`. Ollama's default context is small and truncates over-long prompts silently, so the model may never see the requirements or failure. Prompt also truncates each source file to 20,000 chars while asking for a *complete replacement*, which can write back a truncated file. |
| 9 | High | `adaptive.py` (resource-aware admission for 16/32 GB machines) is not used anywhere. `daemon` never passes `admission` to `run_once`. The RAM-safety requirement is not enforced at runtime. |
| 10 | Medium | A stale `stop-request.json` (Stop clicked while no daemon was running) makes the next Start exit immediately with 0 cycles. |
| 11 | Medium | `engine.run_checked` collects stdout/stderr in memory via PIPE with no cap during the run; a runaway test can exhaust RAM. `worker` spools to disk correctly. |
| 12 | Medium | Jobs in `blocked` state (crash during spawn, or PID still alive) have no unblock/retry path in code or GUI. |
| 13 | Medium | `setup.py`: after `winget install Ollama`, the current process PATH is stale, so the following `ollama pull` step reports "not available in PATH". |
| 14 | Low-Med | `preflight.py` uses default `urlopen` (honors proxy env vars, follows redirects) unlike the hardened `_LOCAL_OPENER` used elsewhere. bandit B310. |
| 15 | Low-Med | OpenCode path: `shutil.which('opencode')` may find an `.cmd` shim, but the code launches bare `opencode` with `shell=False`, which fails on Windows. The prompt (up to ~24k chars) is also passed on the command line, near the 32k Windows limit. |
| 16 | Low | `schtasks /TR` is limited to 261 characters; long install paths would fail unvalidated. |
| 17 | Low | `recovery.inventory` rejects symlinks inside excluded dirs (`.venv`, `.git`) before applying the exclusion. |

## Known / design-level (already in handoffs, restated)
- **Generated code runs unsandboxed with the user's full privileges.** Critical blocker; nothing mitigates it yet.
- The GUI can only start/stop the supervisor and list jobs. It cannot accept a project or plain-language request; no planning/coding pipeline exists beyond a repair loop on an existing project with `requirements.json` and tests.
- Default model `qwen2.5-coder:3b` is small; real capability is unmeasured.
- Two overlapping queues exist (`core.Supervisor`/`state.sqlite` used by `engine.proof`, and `worker`/`jobs.sqlite`), plus three copies of Windows RAM probing. Consolidate.
- Housekeeping: ~18 unused imports (pyflakes list). Tests are heavily fake-based; no coverage measurement. Only Windows CI evidence so far is source tests + packaged import smoke test.

## Suggested order
5 (packaged Python), 6 (heartbeat), 7+8 (timeouts and context), 9 (wire admission), then sandbox design.

---
# Status update (ADM-050)

| # | Status | How verified |
|---|---|---|
| 1 pid_alive Windows Ctrl+C | FIXED | Windows CI |
| 2,3,4 | FIXED | Windows CI |
| 5 Packaged EXE cannot run repair jobs | **FIXED** (`adm/pyruntime.py`, `--adm-module` dispatch) | Windows CI runs the built EXE through baseline-fail, patch, retest against a FAKE Ollama (`tools/verify-packaged-repair.ps1`). Python itself must already be installed (see open items). |
| 6 GUI "unresponsive" during jobs | **FIXED** (heartbeat thread, `daemon.py`) | `tests/test_daemon_robustness_050.py` |
| 7 Job/inference timeouts | **FIXED** (daemon default 1800 s; separate `inference_timeout` default 300 s) | unit tests; real-model timing still unmeasured |
| 8 Ollama context truncation | **FIXED** (`num_ctx` 8192 requested, oversized prompt or file fails closed) | unit tests; real memory use at 8192 on 16 GB unmeasured |
| 9 Admission not wired | **FIXED** (daemon applies `adaptive` check before each spawn; `--no-admission` to disable) | unit tests. Per-job RAM figure is a placeholder (2 GiB). |
| 10 Stale stop request | **FIXED** in GUI (Stop only writes the request if a supervisor is running) | by design; library behaviour unchanged |
| 11 Unbounded test output in memory | **FIXED** (disk-spooled, 64 MiB cap, process tree killed) | unit tests, Linux and Windows |
| 12 No way to unblock jobs | **PARTIAL**: `WorkerSupervisor.resolve_blocked()` added and tested; no GUI button yet | unit tests |
| 13 PATH stale after winget | **PARTIAL**: `find_executable()` knows the default Ollama folder; not exercised on a real install |
| 14 preflight proxies | FIXED | |
| 15 OpenCode .cmd shim | FIXED (resolved path used); prompt-length limit not addressed | |
| 16 schtasks 261 limit | FIXED (validated, clear error) | |
| 17 symlink check order | FIXED | |

## Still open (new or carried)
- **Python must be installed on the PC** for the packaged app to run a project's tests. `pyruntime` finds it (PATH, python.org default folders, ADM folder) and gives a plain-language error if absent. No automatic install step yet.
- **`live_model_verified` is set when the default request function is used, not when a real model answered.** The Windows CI fake server therefore yields `live_model_verified: true` in the report; CI evidence must not be read as live inference. Needs a stronger check (e.g. model digest from `/api/show`).
- Blocked/deferred jobs are not visible in the GUI (no error column, no resolve button).
- Sandbox for generated code (Critical). GUI cannot accept a project/request. Real Ollama run on real hardware. Reboot/crash-recovery on Windows. Duplicate queue modules (`core` vs `worker`). Unused imports.
