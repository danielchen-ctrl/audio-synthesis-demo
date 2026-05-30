@echo off
title V2-Celery
echo Starting Celery worker...

cd /d "%~dp0.."
set PYTHONPATH=%~dp0..\backend

echo ROOT=%CD%
echo PYTHONPATH=%PYTHONPATH%
echo.

backend\.venv\Scripts\celery -A app.celery_app worker --loglevel=info -Q default,audio_synth -c 2

echo.
echo Celery worker exited - press any key to close
pause
