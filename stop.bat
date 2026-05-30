@echo off
title V2 Audio Platform - Stop
set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%

echo.
echo ============================================
echo   V2 Audio Platform - Stopping...
echo ============================================
echo.

echo [1/3] Killing backend / Celery / frontend processes...
:: Kill by process name (most reliable)
taskkill /IM uvicorn.exe  /T /F >nul 2>&1
taskkill /IM celery.exe   /T /F >nul 2>&1
:: Kill node only under our frontend path (avoid killing unrelated node)
for /f "tokens=2" %%p in ('wmic process where "name='node.exe' and CommandLine like '%%vite%%'" get ProcessId /format:list 2^>nul ^| findstr ProcessId') do (
    taskkill /PID %%p /T /F >nul 2>&1
)
echo       Done

echo [2/3] Closing V2 CMD windows...
taskkill /FI "WINDOWTITLE eq V2-Backend"               /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq V2-Celery"                /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq V2-Frontend"              /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq V2 Audio Platform - Lau*" /T /F >nul 2>&1
echo       Done

echo [3/3] Stopping Docker containers...
docker compose -f "%ROOT%\docker-compose.dev.yml" down
echo       Done

echo.
echo ============================================
echo   All services stopped.
echo ============================================
echo.
pause
