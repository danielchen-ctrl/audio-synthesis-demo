@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo [INFO] 当前目录: %CD%
echo [INFO] 正在同步 GitHub main 最新代码...
echo.

git --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] 未检测到 Git，请先安装 Git。
  echo.
  pause
  exit /b 1
)

git status --short --branch
echo.
echo [INFO] 执行: git pull origin main
git pull origin main
if errorlevel 1 (
  echo.
  echo [ERROR] 拉取失败。请检查：
  echo 1. 当前目录是否为 Git 仓库
  echo 2. 本地是否有未处理冲突
  echo 3. 网络是否可访问 GitHub
  echo.
  pause
  exit /b 1
)

echo.
echo [INFO] 当前最新提交：
git log --oneline -1
echo.
echo [DONE] 本地已同步到 GitHub 最新 main。
pause
