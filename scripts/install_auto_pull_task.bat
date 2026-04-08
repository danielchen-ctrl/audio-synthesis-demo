@echo off
chcp 65001 >nul
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0install_auto_pull_task.ps1" %*
exit /b %ERRORLEVEL%
