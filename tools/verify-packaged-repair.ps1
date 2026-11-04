# Runs the BUILT EXE end to end against a fake Ollama: baseline fail -> patch -> retest.
# Proves packaged plumbing (self-dispatch, Python discovery, test run, journal), not model quality.
param([string]$Exe = "$PWD\dist\ADM-Desktop.exe", [string]$Work = "$PWD\packaged-repair-evidence")
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $Work | Out-Null
$proj = Join-Path $Work 'project'; $ev = Join-Path $Work 'evidence'
python -c "from adm.engine import make_broken_demo; make_broken_demo(r'$proj')"
$server = Start-Process python -ArgumentList @('tools\fake_ollama.py') -PassThru -WindowStyle Hidden
try {
  Start-Sleep -Seconds 2
  $p = Start-Process -FilePath $Exe -ArgumentList @('--adm-module','adm.ollama_cli','--root',"`"$proj`"",'--evidence',"`"$ev`"",'--repairs','1') -PassThru -Wait -WindowStyle Hidden
  Write-Host "EXE exit code: $($p.ExitCode)"
  $report = Join-Path $ev 'ollama-direct-report.json'
  if (-not (Test-Path $report)) { throw 'No repair report was written by the packaged EXE' }
  $r = Get-Content $report -Raw | ConvertFrom-Json
  Write-Host "Report status: $($r.status); attempts: $($r.attempts.Count); baseline exit: $($r.baseline.exit_code)"
  Write-Host (Get-Content (Join-Path $proj 'calculator.py') -Raw)
  if ($p.ExitCode -ne 0 -or $r.status -ne 'verified_direct_repair' -or $r.baseline.exit_code -eq 0) { throw 'Packaged repair path FAILED' }
  Write-Host 'PACKAGED REPAIR PLUMBING OK (fake Ollama; not a real model)'
} finally { Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue }
