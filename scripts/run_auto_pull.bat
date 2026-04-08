@echo off
chcp 65001 >nul
setlocal
python "%~dp0auto_pull.py"
exit /b %ERRORLEVEL%
