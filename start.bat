@echo off
title V2 Audio Platform

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
    echo [ERROR] Docker Desktop is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)
echo [1/4] Docker is running

:: 2. Start MySQL / Redis / MinIO
echo [2/4] Starting MySQL / Redis / MinIO...
docker compose -f "%ROOT%\docker-compose.dev.yml" up -d
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start containers.
    pause
    exit /b 1
)

:: Wait for MySQL
echo       Waiting for MySQL...
:wait_mysql
docker exec audio_mysql mysqladmin ping -h localhost --silent >nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 2 /nobreak >nul
    goto wait_mysql
)
echo       MySQL / Redis / MinIO ready

:: 3. Start backend in new window
echo [3/4] Starting backend (http://localhost:8000)...
start "V2-Backend" cmd /k "cd /d %ROOT% && backend\.venv\Scripts\uvicorn app.main:app --reload --port 8000 --app-dir backend"

:: Wait for backend
echo       Waiting for backend...
:wait_backend
timeout /t 2 /nobreak >nul
curl -s http://localhost:8000/api/v1/health >nul 2>&1
if %errorlevel% neq 0 goto wait_backend
echo       Backend ready

:: 4. Start frontend in new window
echo [4/4] Starting frontend (http://localhost:5173)...
start "V2-Frontend" cmd /k "cd /d %ROOT%\frontend && npm run dev"

echo.
echo ============================================
echo   All services started!
echo --------------------------------------------
echo   Frontend : http://localhost:5173
echo   Backend  : http://localhost:8000
echo   API Docs : http://localhost:8000/docs
echo   MinIO    : http://localhost:9001
echo              (minioadmin / minioadmin)
echo ============================================
echo.
echo   To stop all services, run stop.bat
echo.
pause
