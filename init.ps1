$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$Venv = Join-Path $Root ".venv"
$Req = Join-Path $Root "requirements.txt"

if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonExe = "py"
    $PythonArgs = @("-3")
} else {
    $Python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $Python) { throw "Python 3 is required." }
    $PythonExe = "python"
    $PythonArgs = @()
}

if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    & $PythonExe @PythonArgs -m venv $Venv
}

$VenvPython = Join-Path $Venv "Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r $Req
& $VenvPython -m app.desktop_integration --quiet
& $VenvPython (Join-Path $Root "main.py") @args
