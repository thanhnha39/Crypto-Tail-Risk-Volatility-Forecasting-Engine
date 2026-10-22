$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$dataPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $dataPython)) {
    throw 'Missing .venv. Follow the environment setup in README.md.'
}
& $dataPython -m src.data.run
if ($LASTEXITCODE -ne 0) {
    throw "Data pipeline failed with exit code $LASTEXITCODE. Check the output above."
}
