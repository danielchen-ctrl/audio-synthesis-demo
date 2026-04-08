param(
    [string]$TaskName = "DemoAppAutoPull",
    [int]$IntervalMinutes = 5
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
        throw "Python not found. Please install Python 3 first."
    }
    $pythonExe = "py"
    $prefix = "-3 "
}

$script = Join-Path $root "scripts\auto_pull.py"
$command = if ($prefix) {
    "$pythonExe $prefix`"$script`""
} else {
    "`"$pythonExe`" `"$script`""
}

schtasks /Create /F /SC MINUTE /MO $IntervalMinutes /TN $TaskName /TR $command | Out-Null

Write-Host "Task installed: $TaskName"
Write-Host "Interval: every $IntervalMinutes minutes"
Write-Host "Log: $root\logs\auto_pull.log"
Write-Host ""
Write-Host "Manage:"
Write-Host "  Query:  schtasks /Query /TN $TaskName /FO LIST"
Write-Host "  Run now: schtasks /Run /TN $TaskName"
Write-Host "  Remove: schtasks /Delete /TN $TaskName /F"
