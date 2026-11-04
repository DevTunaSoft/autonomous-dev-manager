
## Full regression on Windows (error check)

| Run | Result | Notes |
|---|---|---|
| 41915984988 (commit 3822a54) | FAIL: 6 modules | Windows-only bugs, below |
| next run (commit 6977d69) | **PASS: 243 tests, 0 failures** | `windows-regression-run-*.log` |

Windows-only defects found and fixed:
1. **Line endings (real bug):** `ollama_direct` wrote replacement source in text mode, converting LF to CRLF, so the file no longer matched the crash-journal hash and recovery refused to proceed. Fixed with `newline=''`. (4 modules)
2. **Mandatory lock on metadata (real bug):** `project_lock` locked byte 0 where owner metadata lives; Windows byte-range locks block other handles from reading it. Now locks a byte at offset 2^30.
3. **Test-only:** sqlite connection not closed before temp-dir cleanup; tests wrote CRLF source.

Still unverified: GUI behavior, supervisor lifecycle/crash recovery in a real Windows session, sandbox, real Ollama inference.
