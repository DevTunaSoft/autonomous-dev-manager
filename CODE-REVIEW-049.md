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
