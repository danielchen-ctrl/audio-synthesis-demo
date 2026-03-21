#!/usr/bin/env bash
set -euo pipefail

# 用法：
#   ./scripts/release_tag.sh v0.1.0

if [[ $# -lt 1 ]]; then
  echo "[ERROR] 缺少版本号参数。用法: ./scripts/release_tag.sh v0.1.0"
  exit 1
fi

VERSION="$1"

if [[ ! "${VERSION}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "[ERROR] 版本号格式不合法。请使用类似 v0.1.0 的语义化版本号。"
  exit 1
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [[ "${CURRENT_BRANCH}" != "main" ]]; then
  echo "[ERROR] 当前分支为 '${CURRENT_BRANCH}'。请切换到 main 后再打 tag。"
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "[ERROR] 当前工作区不干净，请先提交或清理改动后再打 tag。"
  exit 1
fi

if git rev-parse --verify --quiet "refs/tags/${VERSION}" >/dev/null; then
  echo "[ERROR] 标签 ${VERSION} 已存在，请使用新的版本号。"
  exit 1
fi

echo "[INFO] 创建标签: ${VERSION}"
git tag "${VERSION}"

echo "[INFO] 推送标签到远程: ${VERSION}"
git push origin "${VERSION}"

echo "[INFO] 完成"
