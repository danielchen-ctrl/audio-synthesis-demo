@echo off
setlocal
set GH_EXE=C:\Program Files\GitHub CLI\gh.exe
if not exist "%GH_EXE%" (
  echo [ERROR] GitHub CLI not found at: %GH_EXE%
  echo.
  pause
  exit /b 1
)

echo [INFO] Refreshing GitHub CLI scopes for GitHub Project management...
echo [INFO] This step requests the project scope required to create and manage GitHub Projects.
echo [INFO] Please approve the new scope in the browser window.
"%GH_EXE%" auth refresh -s project
if errorlevel 1 (
  echo.
  echo [ERROR] Scope refresh did not complete successfully.
  echo.
  pause
  exit /b 1
)

echo.
echo [INFO] Updated auth status:
"%GH_EXE%" auth status
echo.
pause
endlocal
