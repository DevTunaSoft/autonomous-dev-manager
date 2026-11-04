# ADM-022 complete development handoff

## Implemented in this segment
- `adm/release.py`: deterministic complete-source ZIP builder, SHA-256 manifest and independent verification; rejects symlinks and destinations inside source; excludes runtime state and caches.
- `adm/release_entry.py`: standalone supervisor entry point intended for a future Windows PyInstaller build.
- `adm/windows_startup.py`: recognizes frozen executable so the logon task invokes it directly rather than `python -m`.
- `tests/test_release.py`: 8 focused tests including frozen startup, archive tampering, reproducibility and permission gates.

## Evidence
- 8/8 new tests passed.
- 4/4 existing Windows-startup tests passed on Linux with simulated Windows task arguments.
- A complete `unittest discover` attempt did not finish within the execution window; processes were terminated. **Do not claim full regression pass.**
- No Windows executable was built. PyInstaller and Windows are not available in this test environment. No real Ollama/OpenCode inference was performed.

## Commands
- Run focused tests: `python -B -m unittest discover -s tests -p test_release.py -v`
- Generate full source: `python -m adm.release --root . --source-zip ../ADM-source.zip`
- Windows build plan: `python -m adm.release --root . --windows-build-plan`
- On a configured Windows build host with PyInstaller installed, explicit user-approved build: `python -m adm.release --root . --build-windows`

## Outstanding blockers / risks
- Verify packaged executable launch, user-logon scheduled task, process-tree shutdown, automatic restart and upgrade on actual Windows.
- Full regression suite remains unreliable and is not certified for ADM-022.
- Automatic tool/model installation, sandboxing, real agent repair and GUI are unfinished.
- Source ZIP is not an executable installer. PyInstaller is an optional build dependency, not yet automatically provisioned.
- Release package excludes runtime databases and caches by design; these are not project source and should be backed up separately.

## Next actions
1. Run bounded module-by-module regression and diagnose any hanging modules without treating timeouts as passes.
2. Perform a real Windows packaging/launch acceptance trial.
3. Implement approved tool/model bootstrap with verified downloads and rollback.
4. Demonstrate actual AI repair of an unfamiliar broken project.
