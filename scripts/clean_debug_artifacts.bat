@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0.."
cd /d "%ROOT%"

set "PY_CMD="
where python >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=python"
) else (
    where py >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=py -3"
    )
)

if "%PY_CMD%"=="" (
    echo [ERROR] Python was not found. Install Python 3.8+ and retry.
    exit /b 1
)

echo [INFO] Cleaning debug artifacts and root screenshots...
%PY_CMD% project_guard.py --execute --report runtime/temp/debug_artifact_cleanup_report.md

