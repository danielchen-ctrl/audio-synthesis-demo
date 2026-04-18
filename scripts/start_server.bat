@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "ROOT=%~dp0.."
cd /d "%ROOT%"
if "%DEMO_APP_HOST%"=="" set "DEMO_APP_HOST=0.0.0.0"

set "PY_CMD="
py -3.11 --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3.11"
) else (
    where python3.11 >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=python3.11"
    )
)

if "%PY_CMD%"=="" (
    echo [ERROR] Python 3.11 was not found. The server bundle requires Python 3.11. Install it from https://python.org and retry.
    pause
    exit /b 1
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8899 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

timeout /t 2 /nobreak >nul

%PY_CMD% scripts\start_server.py
