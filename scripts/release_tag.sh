#!/usr/bin/env bash
set -euo pipefail

# 用法：
#   ./scripts/release_tag.sh v0.1.0

if [[ $# -lt 1 ]]; then
  echo "[ERROR] 缺少版本号参数。用法: ./scripts/release_tag.sh v0.1.0"
  exit 1
fi

VERSION="$1"

echo "[INFO] 创建标签: ${VERSION}"
git tag "${VERSION}"

echo "[INFO] 推送标签到远程: ${VERSION}"
git push origin "${VERSION}"

echo "[INFO] 完成"
