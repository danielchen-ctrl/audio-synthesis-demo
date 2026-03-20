@echo off
setlocal
set GH_EXE=C:\Program Files\GitHub CLI\gh.exe
if not exist "%GH_EXE%" (
  echo [ERROR] GitHub CLI not found at: %GH_EXE%
  echo Please reinstall GitHub CLI or update this script path.
  exit /b 1
)

echo [INFO] Starting GitHub CLI login...
echo [INFO] Choose: GitHub.com ^> HTTPS ^> Login with a web browser
echo.
"%GH_EXE%" auth login --hostname github.com --git-protocol https --web
if errorlevel 1 (
  echo.
  echo [ERROR] GitHub CLI login did not complete successfully.
  exit /b 1
)

echo.
echo [INFO] Login completed. Current auth status:
"%GH_EXE%" auth status
endlocal
