@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0.."
cd /d "%ROOT%"
if "%DEMO_APP_HOST%"=="" set "DEMO_APP_HOST=0.0.0.0"

:: -- Detect Python --
set "PY="
py -3.11 --version >nul 2>&1 && set "PY=py -3.11" && goto :py_ok
python3.11 --version >nul 2>&1 && set "PY=python3.11" && goto :py_ok
py -3 --version >nul 2>&1 && set "PY=py -3" && goto :py_ok
python --version >nul 2>&1 && set "PY=python" && goto :py_ok
python3 --version >nul 2>&1 && set "PY=python3" && goto :py_ok
echo [ERROR] Python not found. Install from https://python.org
pause
exit /b 1

:py_ok
echo [INFO] Python: %PY%

:: -- Kill old process on port 8899 --
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr ":8899 " ^| findstr "LISTENING"') do taskkill /F /PID %%P >nul 2>&1
timeout /t 2 /nobreak >nul

:: -- Start platform server --
%PY% server_platform.py
