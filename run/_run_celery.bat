@echo off
title V2-Celery
:: 从 run\ 回退到项目根目录（.env 在根目录）
cd /d "%~dp0.."
set PYTHONPATH=%~dp0..\backend
backend\.venv\Scripts\celery -A app.celery_app worker --loglevel=info -Q default,audio_synth -c 2
