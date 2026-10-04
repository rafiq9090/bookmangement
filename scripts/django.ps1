# Run Django with the local virtualenv, or the bundled Codex runtime if its
# original Python installation has moved. All arguments pass through to manage.py.
$projectRoot = Split-Path $PSScriptRoot -Parent
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$djangoPython = $venvPython
$venvWorks = $false
if (Test-Path -LiteralPath $venvPython) {
    & $venvPython --version 2>$null | Out-Null
    $venvWorks = $LASTEXITCODE -eq 0
}
if (-not $venvWorks) {
    if (-not (Test-Path -LiteralPath $bundledPython)) {
        throw 'Recreate .venv with Python 3.12+ and install requirements/base.txt.'
    }
    $djangoPython = $bundledPython
}
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $projectRoot '.venv\Lib\site-packages'
    & $djangoPython (Join-Path $projectRoot 'manage.py') @args
    $djangoExitCode = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
exit $djangoExitCode
