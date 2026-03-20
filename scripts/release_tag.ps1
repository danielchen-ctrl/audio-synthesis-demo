param(
    [Parameter(Mandatory = $false)]
    [string]$Version
)

# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts/release_tag.ps1 v0.1.0

if ([string]::IsNullOrWhiteSpace($Version)) {
    Write-Host "[ERROR] 缺少版本号参数。用法: scripts/release_tag.ps1 v0.1.0"
    exit 1
}

Write-Host "[INFO] 创建标签: $Version"
git tag $Version
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] git tag 执行失败。"
    exit $LASTEXITCODE
}

Write-Host "[INFO] 推送标签到远程: $Version"
git push origin $Version
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] git push origin $Version 执行失败。"
    exit $LASTEXITCODE
}

Write-Host "[INFO] 完成"
