# Fail-closed packaged EXE smoke verification. Run from a trusted Windows build host.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Executable,
  [int]$TimeoutSeconds = 60,
  [string]$EvidenceDirectory = ''
)
$ErrorActionPreference = 'Stop'
if ($TimeoutSeconds -lt 5 -or $TimeoutSeconds -gt 600) { throw 'TimeoutSeconds must be between 5 and 600' }
$exe = (Resolve-Path -LiteralPath $Executable -ErrorAction Stop).Path
if (-not [System.IO.Path]::GetExtension($exe).Equals('.exe', [StringComparison]::OrdinalIgnoreCase)) { throw 'Expected Windows .exe' }
if ([string]::IsNullOrWhiteSpace($EvidenceDirectory)) { $EvidenceDirectory = Join-Path $PWD 'build-evidence' }
$evidence = [System.IO.Path]::GetFullPath($EvidenceDirectory)
[System.IO.Directory]::CreateDirectory($evidence) | Out-Null
$report = Join-Path $evidence 'packaged-smoke.json'
$summary = Join-Path $evidence 'windows-build-verification.json'
Remove-Item -LiteralPath $report,$summary -Force -ErrorAction SilentlyContinue
$started = [DateTimeOffset]::UtcNow
$process = $null
$timedOut = $false
$exitCode = $null
try {
  $process = Start-Process -FilePath $exe -ArgumentList @('--adm-self-test', ('"' + $report + '"')) -PassThru -WindowStyle Hidden
  if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    $timedOut = $true
    try { $process.Kill($true) } catch { try { $process.Kill() } catch {} }
    try { $process.WaitForExit(5000) | Out-Null } catch {}
    throw "Packaged smoke test timed out after $TimeoutSeconds seconds"
  }
  $exitCode = $process.ExitCode
  if ($exitCode -ne 0) {
    # Surface the packaged report (if written) so CI logs show WHICH check failed.
    if (Test-Path -LiteralPath $report -PathType Leaf) { Write-Host (Get-Content -LiteralPath $report -Raw -Encoding UTF8) }
    else { Write-Host 'No packaged smoke report was written (EXE may have crashed before the self-test).' }
    throw "Packaged smoke test exited $exitCode"
  }
  if (-not (Test-Path -LiteralPath $report -PathType Leaf)) { throw 'Packaged smoke report missing' }
  $data = Get-Content -LiteralPath $report -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($data.format -cne 'ADM-packaged-smoke-v1' -or $data.passed -cne $true) { throw 'Packaged smoke report failed format/pass validation' }
  if ($null -eq $data.checks -or @($data.checks.PSObject.Properties).Count -eq 0) { throw 'Smoke checks missing' }
  foreach ($check in $data.checks.PSObject.Properties) {
    if ($check.Value -cne 'passed') { throw "Smoke check failed: $($check.Name)" }
  }
  $hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
  $result = [ordered]@{
    format='ADM-windows-build-verification-v1'; passed=$true
    executable_name=[System.IO.Path]::GetFileName($exe)
    sha256=$hash; bytes=(Get-Item -LiteralPath $exe).Length
    smoke_exit_code=$exitCode; smoke_checks=@($data.checks.PSObject.Properties.Name)
    started_utc=$started.ToString('o'); finished_utc=[DateTimeOffset]::UtcNow.ToString('o')
    scope='Packaged imports and SQLite only; GUI, autonomous AI, isolation, and Windows user acceptance NOT verified'
  }
  $result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $summary -Encoding UTF8
  Write-Host "Packaged smoke passed; SHA256: $hash"
  exit 0
} catch {
  $result = [ordered]@{
    format='ADM-windows-build-verification-v1'; passed=$false
    executable_name=[System.IO.Path]::GetFileName($exe)
    timed_out=$timedOut; smoke_exit_code=$exitCode
    error=$_.Exception.Message; started_utc=$started.ToString('o')
    finished_utc=[DateTimeOffset]::UtcNow.ToString('o')
  }
  $result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $summary -Encoding UTF8
  Write-Error "Packaged smoke verification failed: $($_.Exception.Message)"
  exit 1
} finally {
  if ($null -ne $process) { $process.Dispose() }
}
