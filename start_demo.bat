@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "DEMO_URL=http://127.0.0.1:8899/"
set "DEMO_APP_HOST=0.0.0.0"

echo [INFO] Starting demo server...
start "demo_app_server" /D "%ROOT%" cmd /k scripts\start_server.bat

echo [INFO] Waiting for server health check...
set "READY="
for /l %%i in (1,1,20) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "try { $r = Invoke-WebRequest -UseBasicParsing '%DEMO_URL%' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "READY=1"
        goto :open_browser
    )
    timeout /t 1 /nobreak >nul
)

:open_browser
if not defined READY (
    echo [WARN] Server has not returned HTTP 200 yet. Opening the page anyway...
)

echo [INFO] Opening %DEMO_URL%
start "" "%DEMO_URL%"

echo [INFO] Demo server window started.
echo [INFO] Web URL: %DEMO_URL%
exit /b 0
