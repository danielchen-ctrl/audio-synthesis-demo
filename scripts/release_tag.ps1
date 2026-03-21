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

if ($Version -notmatch '^v\d+\.\d+\.\d+$') {
    Write-Host "[ERROR] 版本号格式不合法。请使用类似 v0.1.0 的语义化版本号。"
    exit 1
}

$CurrentBranch = (git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 无法获取当前分支。"
    exit $LASTEXITCODE
}

if ($CurrentBranch -ne 'main') {
    Write-Host "[ERROR] 当前分支为 '$CurrentBranch'。请切换到 main 后再打 tag。"
    exit 1
}

$WorktreeStatus = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 无法检查工作区状态。"
    exit $LASTEXITCODE
}

if (-not [string]::IsNullOrWhiteSpace($WorktreeStatus)) {
    Write-Host "[ERROR] 当前工作区不干净，请先提交或清理改动后再打 tag。"
    exit 1
}

git rev-parse --verify --quiet "refs/tags/$Version" | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "[ERROR] 标签 $Version 已存在，请使用新的版本号。"
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
