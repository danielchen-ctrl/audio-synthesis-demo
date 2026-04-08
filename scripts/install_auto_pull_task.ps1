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
    if (-not $py) { throw "找不到 Python，请先安装 Python 3。" }
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
Write-Host "已安装定时任务：$TaskName"
Write-Host "执行频率：每 $IntervalMinutes 分钟"
Write-Host "日志文件：$root\logs\auto_pull.log"
Write-Host ""
Write-Host "手动管理："
Write-Host "  查看任务：schtasks /Query /TN $TaskName /FO LIST"
Write-Host "  立即运行：schtasks /Run /TN $TaskName"
Write-Host "  删除任务：schtasks /Delete /TN $TaskName /F"
