@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python not found on PATH. Install Python 3.11+ with tkinter, then retry.
  exit /b 1
)
python -c "import tkinter; import adm.desktop_entry" || exit /b 1
python -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo PyInstaller missing. Install it in a trusted Windows build environment using: python -m pip install pyinstaller
  exit /b 1
)
python -m PyInstaller --noconfirm --clean --onefile --windowed --name ADM-Desktop --paths "%CD%" adm\desktop_entry.py || exit /b 1
if not exist "dist\ADM-Desktop.exe" (
  echo ERROR: PyInstaller did not produce the expected executable.
  exit /b 1
)
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0VERIFY-WINDOWS-DESKTOP.ps1" -Executable "%CD%\dist\ADM-Desktop.exe" -TimeoutSeconds 60 -EvidenceDirectory "%CD%\build-evidence"
if errorlevel 1 (
  echo ERROR: Packaged EXE verification failed. See build-evidence\windows-build-verification.json
  exit /b 1
)
echo Build complete: dist\ADM-Desktop.exe
 echo IMPORTANT: Runtime acceptance on Windows and OS sandboxing remain unverified.
endlocal
