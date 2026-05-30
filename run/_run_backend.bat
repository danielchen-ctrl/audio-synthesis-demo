@echo off
title V2-Backend
:: 从 run\ 回退到项目根目录（.env 在根目录）
cd /d "%~dp0.."
backend\.venv\Scripts\uvicorn app.main:app --reload --port 8000 --app-dir backend
