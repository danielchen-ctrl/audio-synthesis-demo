@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "PLATFORM_URL=http://127.0.0.1:8899/"
set "LEGACY_URL=http://127.0.0.1:8899/legacy"
set "DEMO_APP_HOST=0.0.0.0"

echo.
echo  ╔═══════════════════════════════════════╗
echo  ║        语料生成平台  启动中...         ║
echo  ╚═══════════════════════════════════════╝
echo.
echo  平台地址: %PLATFORM_URL%
echo  原 Demo : %LEGACY_URL%
echo.

:: ── 在新窗口中启动服务器 ─────────────────────────────
start "platform_server" /D "%ROOT%" cmd /k scripts\start_platform_server.bat

:: ── 等待服务就绪（最多 30 秒）────────────────────────
echo [INFO] 等待服务启动（最多 30 秒）...
set "READY="
for /l %%i in (1,1,30) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "try { $r = Invoke-WebRequest -UseBasicParsing '%PLATFORM_URL%' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "READY=1"
        goto :open_browser
    )
    timeout /t 1 /nobreak >nul
)

:open_browser
if not defined READY (
    echo [WARN] 服务尚未响应 HTTP 200，仍尝试打开页面...
) else (
    echo [INFO] 服务就绪！
)

echo [INFO] 打开浏览器 → %PLATFORM_URL%
start "" "%PLATFORM_URL%"

echo.
echo  ┌─────────────────────────────────────────┐
echo  │  语料生成平台已启动                       │
echo  │  平台: %PLATFORM_URL%      │
echo  │  旧版: %LEGACY_URL%  │
echo  └─────────────────────────────────────────┘
echo.
exit /b 0
