$ErrorActionPreference = 'Stop'
$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $pythonLauncher) {
  throw 'Python Launcher was not found. Install Python 3.12 and retry.'
}

$venvPath = Join-Path $PSScriptRoot '.venv-api'
$python = Join-Path $venvPath 'Scripts\python.exe'
if (-not (Test-Path $python)) {
  & py -3.12 -m venv $venvPath
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the API virtual environment.' }
}

& $python -m pip install -r (Join-Path $PSScriptRoot 'api-requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Could not install API dependencies.' }
