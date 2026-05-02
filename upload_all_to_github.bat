@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "REPO_URL=https://github.com/danielchen-ctrl/audio-synthesis-demo.git"
set "FORCE_INCLUDE_IGNORED=1"
set "DRY_RUN=0"

if /I "%~1"=="--dry-run" (
    set "DRY_RUN=1"
)

echo [INFO] Current directory: %CD%
echo [INFO] Target repository: %REPO_URL%
echo.

git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git is not installed or not available in PATH.
    goto :fail
)

if not exist ".git" (
    echo [INFO] .git not found. Initializing repository...
    git init
    if errorlevel 1 goto :fail
)

set "CURRENT_BRANCH="
for /f "delims=" %%i in ('git branch --show-current 2^>nul') do set "CURRENT_BRANCH=%%i"
if not defined CURRENT_BRANCH (
    set "CURRENT_BRANCH=main"
    echo [INFO] No active branch found. Creating !CURRENT_BRANCH!...
    git checkout -B !CURRENT_BRANCH!
    if errorlevel 1 goto :fail
)

if "%DRY_RUN%"=="1" (
    echo.
    echo [INFO] Dry run enabled. No files will be staged, committed, or pushed.
    echo [INFO] Current branch: !CURRENT_BRANCH!
    echo [INFO] Planned remote URL: %REPO_URL%
    echo [INFO] Planned stage command: git add -A -f .
    echo [INFO] Planned push command: git push -u origin !CURRENT_BRANCH!
    git status --short --branch
    exit /b 0
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo [INFO] Adding origin remote...
    git remote add origin "%REPO_URL%"
    if errorlevel 1 goto :fail
) else (
    echo [INFO] Updating origin remote...
    git remote set-url origin "%REPO_URL%"
    if errorlevel 1 goto :fail
)

echo [INFO] Staging files...
if "%FORCE_INCLUDE_IGNORED%"=="1" (
    echo [WARN] Force-including files matched by .gitignore.
    git add -A -f .
    if errorlevel 1 goto :fail
) else (
    git add -A
    if errorlevel 1 goto :fail
)

set "HAS_STAGED="
for /f "delims=" %%i in ('git diff --cached --name-only') do (
    set "HAS_STAGED=1"
    goto :staged_check_done
)
:staged_check_done

if defined HAS_STAGED (
    for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"`) do set "STAMP=%%i"
    set "COMMIT_MSG=chore: upload local snapshot !STAMP!"
    echo [INFO] Creating commit: !COMMIT_MSG!
    git commit -m "!COMMIT_MSG!"
    if errorlevel 1 goto :fail
) else (
    echo [INFO] No file changes detected. Skip commit.
)

echo.
echo [INFO] Pushing branch !CURRENT_BRANCH! to origin...
git push -u origin !CURRENT_BRANCH!
if errorlevel 1 goto :fail

echo.
echo [DONE] Upload finished successfully.
pause
exit /b 0

:fail
echo.
echo [ERROR] Upload script failed. Please review the messages above.
pause
exit /b 1
