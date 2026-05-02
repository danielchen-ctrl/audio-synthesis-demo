# Fix Python DLL Location
# PyInstaller puts python*.dll in _internal, but it needs to be in root

param(
    [string]$DistDir = "dist\SceneDialogueDemo"
)

Write-Host "Fixing Python DLL location..." -ForegroundColor Yellow

$InternalDir = Join-Path $DistDir "_internal"
$RootDir = $DistDir

# Find and copy Python DLLs
$dllFiles = @("python3.dll", "python311.dll", "python310.dll", "python39.dll", "python38.dll")

$copied = 0
foreach ($dll in $dllFiles) {
    $sourcePath = Join-Path $InternalDir $dll
    if (Test-Path $sourcePath) {
        $destPath = Join-Path $RootDir $dll
        Copy-Item $sourcePath -Destination $destPath -Force
        $size = [math]::Round((Get-Item $destPath).Length / 1MB, 2)
        Write-Host "  Copied: $dll ($size MB)" -ForegroundColor Green
        $copied++
    }
}

if ($copied -eq 0) {
    Write-Host "  WARNING: No Python DLLs found to copy" -ForegroundColor Yellow
} else {
    Write-Host "Fixed $copied Python DLL(s)" -ForegroundColor Green
}
