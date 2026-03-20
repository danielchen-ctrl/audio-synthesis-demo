param(
    [string]$TaskName = "DemoAppMultilingualQualityGate",
    [string]$RunTime = "09:00"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    $pythonExe = $python.Source
    $prefix = ""
} else {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if (-not $py) {
        throw "Python was not found."
    }
    $pythonExe = "py"
    $prefix = "-3 "
}

$runScript = Join-Path $root "scripts\run_multilingual_quality_checks.py"
$gateScript = Join-Path $root "scripts\enforce_multilingual_quality_gate.py"
$command = if ($prefix) {
    "$pythonExe $prefix`"$runScript`" && $pythonExe $prefix`"$gateScript`""
} else {
    "`"$pythonExe`" `"$runScript`" && `"$pythonExe`" `"$gateScript`""
}

schtasks /Create /F /SC DAILY /TN $TaskName /TR $command /ST $RunTime | Out-Null
Write-Host "Installed scheduled task: $TaskName at $RunTime"
