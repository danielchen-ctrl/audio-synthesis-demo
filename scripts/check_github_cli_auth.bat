@echo off
setlocal
set GH_EXE=C:\Program Files\GitHub CLI\gh.exe
if not exist "%GH_EXE%" (
  echo [ERROR] GitHub CLI not found at: %GH_EXE%
  echo.
  pause
  exit /b 1
)

echo [INFO] Checking GitHub CLI auth status...
echo.
"%GH_EXE%" auth status
set EXIT_CODE=%ERRORLEVEL%
echo.
if %EXIT_CODE% EQU 0 (
  echo [INFO] GitHub CLI auth check completed successfully.
) else (
  echo [ERROR] GitHub CLI auth check failed with exit code %EXIT_CODE%.
)
echo.
pause
endlocal
