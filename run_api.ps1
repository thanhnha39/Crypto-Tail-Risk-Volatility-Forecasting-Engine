$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv-api\Scripts\python.exe'
if (-not (Test-Path $python)) {
  throw 'API environment is missing. Run .\backend\setup_api.ps1 first.'
}

$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
$listeners = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
foreach ($listener in $listeners) {
  $listenerProcessId = $listener.OwningProcess
  $process = Get-CimInstance Win32_Process -Filter "ProcessId=$listenerProcessId" -ErrorAction SilentlyContinue
  $commandLine = [string]$process.CommandLine
  $isProjectApi = $commandLine.Contains($projectRoot) -and
    $commandLine.Contains('uvicorn') -and
    $commandLine.Contains('api:app')

  if (-not $isProjectApi) {
    throw "Port 8000 is used by another process (PID $listenerProcessId). Stop that process explicitly, then rerun npm run dev:api. Command: $commandLine"
  }

  Write-Host "Restarting this project's existing API (PID $listenerProcessId) to load the current code..."
  Stop-Process -Id $listenerProcessId -ErrorAction Stop
}

$deadline = (Get-Date).AddSeconds(8)
do {
  Start-Sleep -Milliseconds 250
  $remainingListeners = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
} while ($remainingListeners.Count -gt 0 -and (Get-Date) -lt $deadline)

if ($remainingListeners.Count -gt 0) {
  $remainingPid = $remainingListeners[0].OwningProcess
  throw "Port 8000 did not become available after stopping this project's old API (remaining PID $remainingPid)."
}

Write-Host 'Starting the API from the project virtual environment on http://127.0.0.1:8000 ...'
& $python -m uvicorn api:app --app-dir $PSScriptRoot --host 127.0.0.1 --port 8000
if ($LASTEXITCODE -ne 0) {
  throw "The API server exited with code $LASTEXITCODE."
}
