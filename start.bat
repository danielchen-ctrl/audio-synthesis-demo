@echo off
title V2 Audio Platform - Launcher
set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%

echo.
echo ============================================
echo   V2 Audio Platform - Starting...
echo ============================================
echo.

:: 1. Check Docker
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Desktop is not running. Please start it first.
    pause & exit /b 1
)
echo [1/5] Docker OK

:: 2. Start MySQL / Redis / MinIO
echo [2/5] Starting MySQL / Redis / MinIO...
docker compose -f "%ROOT%\docker-compose.dev.yml" up -d
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start containers.
    pause & exit /b 1
)
:wait_mysql
docker exec audio_mysql mysqladmin ping -h localhost --silent >nul 2>&1
if %errorlevel% neq 0 ( timeout /t 2 /nobreak >nul & goto wait_mysql )
echo       MySQL / Redis / MinIO ready

:: 3. Start backend
echo [3/5] Starting backend (http://localhost:8000)...
start "V2-Backend" "%ROOT%\run\_run_backend.bat"
:wait_backend
timeout /t 2 /nobreak >nul
curl -s http://localhost:8000/api/v1/health >nul 2>&1
if %errorlevel% neq 0 goto wait_backend
echo       Backend ready

:: 4. Start Celery worker
echo [4/5] Starting Celery worker...
start "V2-Celery" "%ROOT%\run\_run_celery.bat"
timeout /t 3 /nobreak >nul
echo       Celery started

:: 5. Start frontend
echo [5/5] Starting frontend (http://localhost:5173)...
start "V2-Frontend" "%ROOT%\run\_run_frontend.bat"
:wait_frontend
timeout /t 2 /nobreak >nul
curl -s http://localhost:5173 >nul 2>&1
if %errorlevel% neq 0 goto wait_frontend
start "" "http://localhost:5173"

echo.
echo ============================================
echo   All services started!
echo --------------------------------------------
echo   Frontend : http://localhost:5173
echo   Backend  : http://localhost:8000/docs
echo   MinIO    : http://localhost:9001
echo              minioadmin / minioadmin
echo ============================================
echo.
echo   Run stop.bat to shut everything down.
echo.
pause
