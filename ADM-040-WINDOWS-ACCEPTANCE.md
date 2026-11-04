# ADM-040 Windows acceptance checklist (NOT YET EXECUTED)

Use an isolated, disposable Windows 11 VM for testing. Building an EXE does not validate it.

1. Install trusted Python 3.11+ with tkinter and PyInstaller into the build VM. Check authenticity of downloaded packages.
2. Extract the entire ADM-040 archive. In the extracted `ADM` folder run `BUILD-WINDOWS-DESKTOP.cmd`.
3. Confirm `dist/ADM-Desktop.exe` exists and inspect Windows Defender/signature status. The binary is unsigned and should not be redistributed as production software.
4. Start the GUI with no command line arguments. Verify the job table shows no jobs for a clean profile.
5. Click Start supervisor; observe heartbeat transitions to running and cycles increment. Confirm the process is `ADM-Desktop.exe --adm-supervisor --state ...`, NOT python.exe.
6. Click Stop supervisor; verify graceful shutdown. Close/reopen GUI and confirm persisted state.
7. Reboot the VM and verify truthful status (the app does not automatically install Windows startup).
8. Check local Ollama; verify absent model, present model and unreachable server messaging. No cloud traffic should occur.
9. Test job table with a trusted disposable job; verify queue updates and exit codes.
10. Test duplicate launch, forced process kill, corrupt SQLite, locked database, slow Ollama, and failed/aborted jobs.
11. Capture screenshots, logs, hashes, OS build, Python/PyInstaller versions, and failure evidence.
12. Do not run AI-generated code outside an OS-enforced sandbox; none is provided by ADM-040.

Acceptance result: PENDING. No Windows build or runtime test was performed in this development environment.
