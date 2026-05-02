# Scene Dialogue Demo - Windows Build Script
# PyInstaller packaging for Windows

param(
    [switch]$CleanBuild = $false,
    [switch]$SkipVenv = $false
)

$ErrorActionPreference = "Stop"

Write-Host "================================" -ForegroundColor Cyan
Write-Host "Scene Dialogue Demo - Windows Build" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Project root
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $ProjectRoot

try {
    # Step 1: Clean old build
    if ($CleanBuild) {
        Write-Host "[1/5] Cleaning old build..." -ForegroundColor Yellow
        if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
        if (Test-Path "build/build") { Remove-Item -Recurse -Force "build/build" }
        Write-Host "  Done" -ForegroundColor Green
    }
    else {
        Write-Host "[1/5] Skip cleaning (use -CleanBuild to clean)" -ForegroundColor Gray
    }

    # Step 2: Setup virtual environment
    if (-not $SkipVenv) {
        Write-Host "[2/5] Checking virtual environment..." -ForegroundColor Yellow
        
        if (-not (Test-Path ".venv_build")) {
            Write-Host "  Creating venv .venv_build..." -ForegroundColor Yellow
            python -m venv .venv_build
            Write-Host "  Done" -ForegroundColor Green
        }
        else {
            Write-Host "  Venv exists" -ForegroundColor Green
        }
        
        Write-Host "  Activating venv..." -ForegroundColor Yellow
        & ".venv_build\Scripts\Activate.ps1"
        Write-Host "  Done" -ForegroundColor Green
    }
    else {
        Write-Host "[2/5] Skip venv (using current Python)" -ForegroundColor Gray
    }

    # Step 3: Install dependencies
    Write-Host "[3/5] Installing dependencies..." -ForegroundColor Yellow
    python -m pip install --upgrade pip --quiet
    
    if (Test-Path "requirements.txt") {
        python -m pip install -r requirements.txt --quiet
        Write-Host "  Installed from requirements.txt" -ForegroundColor Green
    } else {
        Write-Host "  Warning: requirements.txt not found, installing core deps" -ForegroundColor Yellow
        python -m pip install tornado numpy deep-translator edge-tts pydub pywebview requests --quiet
    }
    
    python -m pip install pyinstaller --quiet
    Write-Host "  Done" -ForegroundColor Green

    # Step 4: Run PyInstaller
    Write-Host "[4/5] Building application..." -ForegroundColor Yellow
    Write-Host "  Using spec: build/demo_app.spec" -ForegroundColor Yellow
    
    pyinstaller build/demo_app.spec --clean
    
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code: $LASTEXITCODE"
    }
    Write-Host "  Done" -ForegroundColor Green
    
    # Step 4.5: Fix Python DLL location
    Write-Host "[4.5/5] Fixing Python DLL location..." -ForegroundColor Yellow
    & "$PSScriptRoot\fix_python_dll.ps1" -DistDir "dist\SceneDialogueDemo"
    Write-Host "  Done" -ForegroundColor Green

    # Step 5: Create distribution package
    Write-Host "[5/5] Creating distribution package..." -ForegroundColor Yellow
    
    $DistDir = "dist\SceneDialogueDemo"
    if (-not (Test-Path $DistDir)) {
        throw "Build output directory not found: $DistDir"
    }
    
    $ExePath = "$DistDir\SceneDialogueDemo.exe"
    if (-not (Test-Path $ExePath)) {
        throw "Executable not found: $ExePath"
    }
    
    $ExeSize = [math]::Round((Get-Item $ExePath).Length / 1MB, 2)
    Write-Host "  Executable: $ExeSize MB" -ForegroundColor Green
    
    $TotalSize = [math]::Round((Get-ChildItem -Recurse $DistDir | Measure-Object -Property Length -Sum).Sum / 1MB, 2)
    Write-Host "  Total: $TotalSize MB" -ForegroundColor Green
    
    # Create ZIP
    $ZipName = "SceneDialogueDemo_win_x64.zip"
    if (Test-Path $ZipName) { Remove-Item -Force $ZipName }
    
    Write-Host "  Creating ZIP: $ZipName" -ForegroundColor Yellow
    Compress-Archive -Path $DistDir -DestinationPath $ZipName -CompressionLevel Optimal
    
    $ZipSize = [math]::Round((Get-Item $ZipName).Length / 1MB, 2)
    Write-Host "  ZIP size: $ZipSize MB" -ForegroundColor Green
    
    # Output results
    Write-Host ""
    Write-Host "================================" -ForegroundColor Cyan
    Write-Host "Build successful!" -ForegroundColor Green
    Write-Host "================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Output directory: $DistDir" -ForegroundColor White
    Write-Host "Executable: $ExePath" -ForegroundColor White
    Write-Host "Distribution: $ZipName" -ForegroundColor White
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  1. Run SceneDialogueDemo.exe directly" -ForegroundColor White
    Write-Host "  2. Or extract $ZipName and run" -ForegroundColor White
    Write-Host ""
    
}
catch {
    Write-Host ""
    Write-Host "Build failed: $_" -ForegroundColor Red
    Write-Host ""
    exit 1
}
finally {
    Pop-Location
}
