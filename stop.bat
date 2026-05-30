@echo off
chcp 65001 >nul
title V2 平台 - 停止服务

cd /d "%~dp0"

echo.
echo ========================================
echo   V2 平台 停止服务...
echo ========================================
echo.

:: 停止后端和前端窗口
echo [1/2] 关闭后端和前端进程...
taskkill /FI "WINDOWTITLE eq V2 后端 API" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq V2 前端" /F >nul 2>&1
taskkill /FI "IMAGENAME eq node.exe" /F >nul 2>&1
taskkill /FI "IMAGENAME eq uvicorn.exe" /F >nul 2>&1
echo       后端/前端已停止 ✓

:: 停止 Docker 容器
echo [2/2] 停止 Docker 容器（MySQL / Redis / MinIO）...
docker compose -f docker-compose.dev.yml down >nul 2>&1
echo       Docker 容器已停止 ✓

echo.
echo ========================================
echo   所有服务已停止
echo ========================================
echo.
pause
