@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "PLATFORM_URL=http://127.0.0.1:8899/"
set "LEGACY_URL=http://127.0.0.1:8899/legacy"
set "DEMO_APP_HOST=0.0.0.0"

echo.
echo  ============================================
echo   语料生成平台  启动中...
echo  ============================================
echo.
echo  平台地址: %PLATFORM_URL%
echo  旧版Demo : %LEGACY_URL%
echo.

:: ── 检测 Python ──────────────────────────────────────────
set "PY_CMD="
py -3.11 --version >nul 2>&1
if not errorlevel 1 ( set "PY_CMD=py -3.11" & goto :py_ok )
python3.11 --version >nul 2>&1
if not errorlevel 1 ( set "PY_CMD=python3.11" & goto :py_ok )
py -3 --version >nul 2>&1
if not errorlevel 1 ( set "PY_CMD=py -3" & goto :py_ok )
python --version >nul 2>&1
if not errorlevel 1 ( set "PY_CMD=python" & goto :py_ok )
python3 --version >nul 2>&1
if not errorlevel 1 ( set "PY_CMD=python3" & goto :py_ok )

echo [ERROR] 找不到 Python，请先安装 Python 3.11
echo         下载地址: https://python.org
pause
exit /b 1

:py_ok
echo [INFO] Python: %PY_CMD%

:: ── 清理占用 8899 端口的旧进程 ──────────────────────────
echo [INFO] 清理旧进程...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr :8899 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

:: ── 在新窗口启动服务器 ──────────────────────────────────
echo [INFO] 启动服务器...
start "platform_server" /D "%ROOT%" cmd /k "%PY_CMD% server_platform.py"

:: ── 等待服务就绪（最多 30 秒）────────────────────────────
echo [INFO] 等待服务就绪（最多 30 秒）...
set "READY="
set /a COUNT=0
:wait_loop
set /a COUNT+=1
if %COUNT% gtr 30 goto :after_wait
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try{$r=Invoke-WebRequest -UseBasicParsing '%PLATFORM_URL%' -TimeoutSec 2;if($r.StatusCode -eq 200){exit 0}else{exit 1}}catch{exit 1}" >nul 2>&1
if not errorlevel 1 (
    set "READY=1"
    goto :after_wait
)
timeout /t 1 /nobreak >nul
goto :wait_loop

:after_wait
if not defined READY (
    echo [WARN] 服务器未能在 30 秒内响应，请查看服务器窗口排查错误
) else (
    echo [INFO] 服务器就绪！正在打开浏览器...
    start "" "%PLATFORM_URL%"
)

echo.
echo  ============================================
echo   平台已启动
echo   浏览器地址: %PLATFORM_URL%
echo   旧版 Demo : %LEGACY_URL%
echo  ============================================
echo.
echo  关闭服务：直接关掉"platform_server"那个黑窗口
echo  关闭本窗口不影响服务运行
echo.
pause
