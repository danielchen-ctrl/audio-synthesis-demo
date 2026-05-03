@echo off
setlocal

set "ROOT=%~dp0.."
cd /d "%ROOT%"
set "DEMO_URL=http://127.0.0.1:8899/"
set "DEMO_APP_HOST=0.0.0.0"

echo [INFO] Starting legacy demo server...
start "demo_app_server" /D "%ROOT%" cmd /k scripts\start_server.bat

echo [INFO] Waiting for server (up to 20s)...
set /a N=0
:loop
set /a N+=1
if %N% GTR 20 goto :open
powershell -NoProfile -Command "try{exit (Invoke-WebRequest -UseBasicParsing '%DEMO_URL%' -TimeoutSec 1).StatusCode}catch{exit 0}" 2>nul
if "%ERRORLEVEL%"=="200" goto :open
timeout /t 1 /nobreak >nul
goto :loop

:open
echo [INFO] Opening %DEMO_URL%
start "" "%DEMO_URL%"
echo [INFO] Done. Close the "demo_app_server" window to stop.
pause
