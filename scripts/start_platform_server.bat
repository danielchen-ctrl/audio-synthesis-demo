@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "ROOT=%~dp0.."
cd /d "%ROOT%"
if "%DEMO_APP_HOST%"=="" set "DEMO_APP_HOST=0.0.0.0"

:: ── Python 检索（优先 3.11，兼容任意已安装版本）──────
set "PY_CMD="

py -3.11 --version >nul 2>&1
if not errorlevel 1 ( set "PY_CMD=py -3.11" & goto :py_found )

python3.11 --version >nul 2>&1
if not errorlevel 1 ( set "PY_CMD=python3.11" & goto :py_found )

py -3 --version >nul 2>&1
if not errorlevel 1 ( set "PY_CMD=py -3" & goto :py_found )

python --version >nul 2>&1
if not errorlevel 1 ( set "PY_CMD=python" & goto :py_found )

python3 --version >nul 2>&1
if not errorlevel 1 ( set "PY_CMD=python3" & goto :py_found )

echo [ERROR] Python was not found. Install Python 3.11 from https://python.org and retry.
pause
exit /b 1

:py_found
echo [INFO] Using Python: %PY_CMD%

:: ── 清理占用 8899 端口的旧进程 ──────────────────────
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8899 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

:: ── 启动语料生成平台 ─────────────────────────────────
%PY_CMD% server_platform.py
