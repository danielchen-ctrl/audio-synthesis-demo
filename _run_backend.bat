@echo off
cd /d "%~dp0"
backend\.venv\Scripts\uvicorn app.main:app --reload --port 8000 --app-dir backend
