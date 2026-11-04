# ADM-023 complete source handoff

## What changed
- Added `adm/desktop.py`: dependency-free (standard-library Tkinter) GUI with start/stop/status for the trusted-job supervisor.
- Added `adm/desktop_entry.py` for a future frozen Windows GUI build.
- Added `windows_desktop_build_plan()` in `adm/release.py`.
- Added seven new automated desktop/build-plan tests.
- Source-mode launcher explicitly provides project PYTHONPATH when launching the background process from a different working directory.

## Verified
- `python -B -m unittest discover -s tests -p test_desktop.py -q`: 7 tests passed.
- Full regression suite attempted with a time limit but did not finish within the tool execution window. **Not verified**.
- Complete ZIP package integrity and SHA-256 manifest verified.

## Not yet verified / limitations
- No Windows host was available. Neither Windows GUI launch nor PyInstaller executable was built or tested.
- Tkinter must be present on the Windows target for source execution; frozen GUI build requires Windows testing.
- Status freshness is heartbeat-based; a fresh heartbeat does not prove a responsive worker. Launch prevention is not yet an atomic cross-process singleton guarantee.
- No actual local AI repair, safe sandbox, automatic tool installation, or end-to-end autonomous delivery.
- `ADM-Desktop` and `ADM-Supervisor` are distinct future executables. The current GUI source launcher invokes `python -m adm.daemon`; a frozen GUI will require explicit companion-supervisor path resolution before release.

## How to run from source
From project root: `python -m adm.desktop` (requires Python/Tkinter). Do not run untrusted jobs.

## Immediate engineering work
1. Add a robust singleton/instance lock and ensure the frozen GUI starts the companion supervisor binary.
2. Run full regression reliably; root-cause any remaining stalls.
3. Test on Windows and build an actual installer.
4. Connect a real local AI and verify repair of unfamiliar code.

All earlier code, tests, and handoffs are retained in this cumulative source package.
