@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0backend
backend\.venv\Scripts\celery -A app.celery_app worker --loglevel=info -Q default,audio_synth -c 2
