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

:: 4. Start Celery worker in new window
:: 必须从项目根目录启动（.env 在根目录），同时设置 PYTHONPATH 指向 backend
echo [4/5] Starting Celery worker...
start "V2-Celery" cmd /k "cd /d %ROOT% && set PYTHONPATH=%ROOT%\backend && backend\.venv\Scripts\celery -A app.celery_app worker --loglevel=info -Q default,audio_synth -c 2"

:: 5. Start frontend in new window
echo [5/5] Starting frontend (http://localhost:5173)...
start "V2-Frontend" cmd /k "cd /d %ROOT%\frontend && npm run dev"

:: Wait for frontend then open browser
echo       Waiting for frontend...
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
echo   Backend  : http://localhost:8000
echo   API Docs : http://localhost:8000/docs
echo   MinIO    : http://localhost:9001
echo              (minioadmin / minioadmin)
echo   Celery   : window "V2-Celery"
echo ============================================
echo.
echo   To stop all services, run stop.bat
echo.
pause
