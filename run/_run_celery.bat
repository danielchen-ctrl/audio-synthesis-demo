@echo off
title V2-Celery
echo Starting Celery worker...

:: 从 run\ 回退到项目根目录（.env 在根目录）
cd /d "%~dp0.."

:: 设置 PYTHONPATH 指向 backend 目录（让 Python 能 import app.*）
set PYTHONPATH=%~dp0..\backend

echo ROOT: %CD%
echo PYTHONPATH: %PYTHONPATH%
echo.

:: 启动 Celery worker
backend\.venv\Scripts\celery -A app.celery_app worker --loglevel=info -Q default,audio_synth -c 2

:: 如果 Celery 异常退出，保留窗口显示错误
echo.
echo [Celery worker exited - press any key to close]
pause
