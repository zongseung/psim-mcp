param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pythonExe = if (Test-Path $venvPython) { $venvPython } else { "python" }

$cacheDir = Join-Path $projectRoot "output\pytest_cache"
$baseTemp = Join-Path $projectRoot "output\pytest_tmp"

New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
New-Item -ItemType Directory -Force -Path $baseTemp | Out-Null

$env:PYTHONPATH = "src"
$env:TMP = $baseTemp
$env:TEMP = $baseTemp

& $pythonExe -m pytest @PytestArgs -o "cache_dir=$cacheDir" --basetemp $baseTemp
exit $LASTEXITCODE
