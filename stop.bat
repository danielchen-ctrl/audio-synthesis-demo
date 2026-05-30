@echo off
title V2 Audio Platform - Stop
set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%

echo.
echo ============================================
echo   V2 Audio Platform - Stopping...
echo ============================================
echo.

:: 1. Close windows opened by start.bat (match exact title set by start "V2-xxx")
echo [1/3] Closing backend, Celery, frontend windows...
taskkill /FI "WINDOWTITLE eq V2-Backend" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq V2-Celery"  /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq V2-Frontend" /T /F >nul 2>&1
echo       Done

:: 2. Kill any remaining process by image name (belt-and-suspenders)
echo [2/3] Cleaning up remaining processes...
taskkill /IM uvicorn.exe /F >nul 2>&1
taskkill /IM celery.exe  /F >nul 2>&1
echo       Done

:: 3. Stop Docker containers
echo [3/3] Stopping Docker containers...
docker compose -f "%ROOT%\docker-compose.dev.yml" down
echo       Done

echo.
echo ============================================
echo   All services stopped.
echo ============================================
echo.
pause
