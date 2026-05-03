@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"
set "PLATFORM_URL=http://127.0.0.1:8899/"
set "DEMO_APP_HOST=0.0.0.0"

echo ============================================
echo  Platform Server - Starting...
echo  URL: %PLATFORM_URL%
echo ============================================
echo.

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

:: -- Start server in new window --
echo [INFO] Starting server...
start "platform_server" /D "%ROOT%" cmd /c %PY% server_platform.py

:: -- Wait up to 30s for server ready --
echo [INFO] Waiting for server (up to 30s)...
set /a N=0
:loop
set /a N+=1
if %N% GTR 30 goto :timeout
powershell -NoProfile -Command "try{exit (Invoke-WebRequest -UseBasicParsing '%PLATFORM_URL%' -TimeoutSec 1).StatusCode}catch{exit 0}" 2>nul
if "%ERRORLEVEL%"=="200" goto :ready
timeout /t 1 /nobreak >nul
goto :loop

:timeout
echo [WARN] Server not ready after 30s - check the server window for errors.
goto :open

:ready
echo [INFO] Server is ready!

:open
start "" "%PLATFORM_URL%"
echo.
echo  Open in browser: %PLATFORM_URL%
echo  To stop: close the "platform_server" window
echo.
