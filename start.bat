@echo off
chcp 65001 >nul
title V2 音频语料平台

echo.
echo ========================================
echo   V2 音频语料生成平台 启动中...
echo ========================================
echo.

:: ── 切到脚本所在目录 ──────────────────────────────────────────────────────
cd /d "%~dp0"

:: ── 1. 检查 Docker 是否运行 ───────────────────────────────────────────────
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Desktop 未启动，请先打开 Docker Desktop 再运行此脚本。
    pause
    exit /b 1
)
echo [1/4] Docker 已就绪

:: ── 2. 启动 MySQL / Redis / MinIO ────────────────────────────────────────
echo [2/4] 启动依赖服务（MySQL / Redis / MinIO）...
docker compose -f docker-compose.dev.yml up -d >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker 容器启动失败，请检查 docker-compose.dev.yml。
    pause
    exit /b 1
)
:: 等待 MySQL 就绪
echo       等待 MySQL 就绪...
:wait_mysql
docker exec audio_mysql mysqladmin ping -h localhost --silent >nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 2 /nobreak >nul
    goto wait_mysql
)
echo       MySQL / Redis / MinIO 已就绪 ✓

:: ── 3. 启动后端（FastAPI + uvicorn，新窗口）──────────────────────────────
echo [3/4] 启动后端 API（http://localhost:8000）...
start "V2 后端 API" cmd /k "cd /d "%~dp0" && backend\.venv\Scripts\uvicorn app.main:app --reload --port 8000 --app-dir backend"

:: 等待后端就绪
echo       等待后端启动...
:wait_backend
timeout /t 2 /nobreak >nul
curl -s http://localhost:8000/api/v1/health >nul 2>&1
if %errorlevel% neq 0 goto wait_backend
echo       后端已就绪 ✓

:: ── 4. 启动前端（Vite dev，新窗口）──────────────────────────────────────
echo [4/4] 启动前端（http://localhost:5173）...
start "V2 前端" cmd /k "cd /d "%~dp0\frontend" && npm run dev"

:: ── 完成 ──────────────────────────────────────────────────────────────────
echo.
echo ========================================
echo   启动完成！
echo ----------------------------------------
echo   前端:  http://localhost:5173
echo   后端:  http://localhost:8000
echo   API文档: http://localhost:8000/docs
echo   MinIO:  http://localhost:9001  (minioadmin/minioadmin)
echo ========================================
echo.
echo   关闭所有服务：运行 stop.bat
echo.
pause
