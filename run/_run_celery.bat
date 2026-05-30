@echo off
title V2-Celery
pushd %~dp0..
set PYTHONPATH=%CD%\backend
echo ROOT=%CD%
echo PYTHONPATH=%PYTHONPATH%
echo.
backend\.venv\Scripts\celery -A app.celery_app worker --loglevel=info -Q default,audio_synth -c 2
echo.
echo Celery worker exited
pause
popd
