#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_pull.py
从 GitHub 自动拉取当前分支的最新代码。
由 Task Scheduler 定期调用，也可手动运行。
日志写入 logs/auto_pull.log
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 确保控制台输出为 UTF-8（Windows 默认 GBK 会乱码）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_DIR = Path(__file__).resolve().parents[1]
LOG_FILE = REPO_DIR / "logs" / "auto_pull.log"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> None:
    # 获取当前分支名
    result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    branch = result.stdout.strip()
    if not branch or branch == "HEAD":
        _log("当前处于 detached HEAD 状态，跳过")
        return

    # 检查已跟踪文件的未提交改动（未跟踪的新文件不影响 pull，不计入）
    dirty = _run(["git", "status", "--porcelain"])
    tracked_changes = [
        line for line in dirty.stdout.splitlines()
        if line and not line.startswith("??")
    ]
    if tracked_changes:
        _log(f"[SKIP] 存在未提交改动，跳过拉取（当前分支：{branch}）")
        return

    # Fetch 远端分支
    _log(f"检查 origin/{branch} ...")
    fetch = _run(["git", "fetch", "origin", branch])
    if fetch.returncode != 0:
        _log(f"[ERROR] git fetch 失败：{fetch.stderr.strip()}")
        return

    # 计算本地落后提交数
    behind_result = _run(["git", "rev-list", "--count", f"HEAD..origin/{branch}"])
    behind = int(behind_result.stdout.strip() or "0")

    if behind == 0:
        _log("已是最新，无需拉取")
        return

    _log(f"远端有 {behind} 个新提交，开始拉取...")
    pull = _run(["git", "pull", "origin", branch])
    if pull.returncode == 0:
        summary = pull.stdout.strip().splitlines()[-1] if pull.stdout.strip() else "ok"
        _log(f"拉取成功：{summary}")
    else:
        _log(f"[ERROR] git pull 失败：{pull.stderr.strip()}")


if __name__ == "__main__":
    main()
