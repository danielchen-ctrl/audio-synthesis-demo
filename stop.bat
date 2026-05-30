@echo off
title V2 Audio Platform - Stop

set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%

echo.
echo ============================================
echo   V2 Audio Platform - Stopping...
echo ============================================
echo.

echo [1/2] Closing backend and frontend...
taskkill /FI "WINDOWTITLE eq V2-Backend" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq V2-Frontend" /F >nul 2>&1
taskkill /IM uvicorn.exe /F >nul 2>&1
echo       Done

echo [2/2] Stopping Docker containers...
docker compose -f "%ROOT%\docker-compose.dev.yml" down
echo       Done

echo.
echo ============================================
echo   All services stopped
echo ============================================
echo.
pause
