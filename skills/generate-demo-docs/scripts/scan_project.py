#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan_project.py — 项目目录扫描器
==================================
扫描指定目录，输出带标签的文件地图，可直接粘贴进 PROJECT_EXPLANATION.md 的
章节 3（文件与脚本地图）。

用法：
    python scan_project.py [目标目录]
    python scan_project.py .
    python scan_project.py D:/Github/my-project

输出：
    stdout — Markdown 格式的树状文件地图
    stderr — 统计信息（文件总数、跳过的文件数等）

示例输出：
    my-project/
    ├── main.py              ← [主入口] 程序主入口
    ├── src/
    │   ├── core.py          ← [核心逻辑] 待分析
    │   └── utils.py         ← [工具脚本] 待分析
    └── requirements.txt     ← [配置文件] Python 依赖
"""

import os
import sys
import re
from pathlib import Path

# ─── 跳过的目录 ────────────────────────────────────────────────────────────
SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env", ".env",
    "node_modules", "dist", "build", ".mypy_cache", ".pytest_cache",
    ".tox", "htmlcov", ".eggs", "*.egg-info",
    ".idea", ".vscode", ".DS_Store",
}

# ─── 跳过的文件扩展名 ──────────────────────────────────────────────────────
SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib",
    ".lock",  # package-lock.json, Pipfile.lock 等（内容太长）
}

# ─── 文件标签规则 ──────────────────────────────────────────────────────────
# 格式：(优先级, 正则匹配文件名（不含路径）, 标签, 默认描述)
# 优先级越小越优先
LABEL_RULES = [
    # 主入口
    (0,  r"^(main|app|server|cli|run|start|entrypoint|__main__)\.(py|js|ts|sh)$",
     "主入口", "程序启动入口"),
    (0,  r"^index\.(js|ts|mjs|cjs)$",
     "主入口", "Node.js 模块入口"),

    # 配置
    (1,  r"^(requirements.*\.txt|pyproject\.toml|setup\.py|setup\.cfg)$",
     "配置文件", "Python 依赖与包配置"),
    (1,  r"^(package\.json|tsconfig\.json|babel\.config\..*|webpack\.config\..*)$",
     "配置文件", "Node.js 项目配置"),
    (1,  r"^(Makefile|Taskfile\.yml|justfile|\.env\.example)$",
     "配置文件", "构建/任务配置"),
    (1,  r"\.(yaml|yml|toml|ini|cfg|conf)$",
     "配置文件", "配置文件"),
    (1,  r"^(Dockerfile|docker-compose\.yml)$",
     "配置文件", "容器配置"),

    # 文档
    (2,  r"^(README|CHANGELOG|CONTRIBUTING|LICENSE|NOTICE)(\.md|\.txt|\.rst)?$",
     "文档", "项目说明文档"),
    (2,  r"\.md$",
     "文档", "Markdown 文档"),

    # 测试
    (3,  r"^(test_.*|.*_test)\.(py|js|ts)$",
     "测试", "单元/集成测试"),
    (3,  r"^conftest\.py$",
     "测试", "pytest 配置"),
    (3,  r"^(jest\.config|vitest\.config)\.(js|ts)$",
     "测试", "测试框架配置"),

    # 数据/样例
    (4,  r"\.(json|csv|tsv|parquet|xlsx|wav|mp3|mp4|png|jpg|jpeg)$",
     "数据/样例", "数据或样例文件"),

    # 工具/辅助
    (5,  r"^(utils?|helpers?|common|shared|tools?)\.(py|js|ts)$",
     "工具脚本", "通用辅助函数"),

    # 核心逻辑（宽泛匹配，放在工具之后）
    (6,  r"^(core|engine|processor|handler|service|pipeline|worker)\.(py|js|ts)$",
     "核心逻辑", "核心业务实现"),
]

# ─── 辅助函数 ──────────────────────────────────────────────────────────────

def get_label(filename: str) -> tuple[str, str]:
    """返回 (标签, 默认描述)，无匹配时返回 ('辅助脚本', '待分析')"""
    name_lower = filename.lower()
    for _, pattern, label, desc in sorted(LABEL_RULES, key=lambda r: r[0]):
        if re.match(pattern, filename, re.IGNORECASE):
            return label, desc
    # 按扩展名补充
    ext = Path(filename).suffix.lower()
    if ext in {".py", ".js", ".ts", ".sh", ".rb", ".go", ".rs"}:
        return "辅助脚本", "待分析"
    return "其他", "待分析"


def should_skip_dir(dirname: str) -> bool:
    return dirname in SKIP_DIRS or dirname.endswith(".egg-info")


def should_skip_file(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in SKIP_EXTENSIONS


def get_entry_check(filepath: Path) -> bool:
    """检查 Python 文件是否有 __main__ block"""
    if filepath.suffix != ".py":
        return False
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        return 'if __name__ == "__main__"' in content or \
               "if __name__ == '__main__'" in content
    except Exception:
        return False


# ─── 核心渲染函数 ──────────────────────────────────────────────────────────

def scan_directory(root: Path, prefix: str = "", is_last: bool = True,
                   stats: dict = None) -> list[str]:
    """递归扫描目录，返回 Markdown 树状行列表"""
    if stats is None:
        stats = {"files": 0, "dirs": 0, "skipped": 0}

    lines = []
    try:
        entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return [f"{prefix}    ← [权限不足，无法读取]"]

    # 分离目录和文件
    dirs = [e for e in entries if e.is_dir() and not should_skip_dir(e.name)]
    files = [e for e in entries if e.is_file() and not should_skip_file(e.name)]
    skipped = [e for e in entries if e.is_dir() and should_skip_dir(e.name)]
    stats["skipped"] += len(skipped)

    all_items = dirs + files
    for idx, item in enumerate(all_items):
        is_item_last = (idx == len(all_items) - 1)
        connector = "└── " if is_item_last else "├── "
        extension = "    " if is_item_last else "│   "

        if item.is_dir():
            stats["dirs"] += 1
            lines.append(f"{prefix}{connector}{item.name}/")
            sub_lines = scan_directory(
                item, prefix + extension, is_item_last, stats
            )
            lines.extend(sub_lines)
        else:
            stats["files"] += 1
            label, desc = get_label(item.name)

            # 检查是否有 __main__ block（强化主入口识别）
            is_actual_entry = (label == "辅助脚本") and get_entry_check(item)
            if is_actual_entry:
                label = "主入口（推测）"
                desc = "含 __main__ block，可能是入口"

            # 文件大小提示（超大文件标注）
            try:
                size_kb = item.stat().st_size / 1024
                size_note = f"（{size_kb:.0f}KB）" if size_kb > 100 else ""
            except Exception:
                size_note = ""

            # 最终行
            padding = max(1, 40 - len(item.name) - len(prefix) - 4)
            lines.append(
                f"{prefix}{connector}{item.name}{' ' * padding}"
                f"← [{label}]{size_note} {desc}"
            )

    return lines


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    target = target.resolve()

    if not target.exists():
        print(f"❌ 目录不存在：{target}", file=sys.stderr)
        sys.exit(1)

    if not target.is_dir():
        print(f"❌ 不是目录：{target}", file=sys.stderr)
        sys.exit(1)

    print(f"\n```", flush=True)
    print(f"{target.name}/")

    stats: dict = {"files": 0, "dirs": 0, "skipped": 0}
    tree_lines = scan_directory(target, stats=stats)
    for line in tree_lines:
        print(line)
    print("```")

    # 统计信息输出到 stderr
    print(f"\n📊 扫描完成：{stats['files']} 个文件，{stats['dirs']} 个目录，"
          f"跳过 {stats['skipped']} 个噪声目录", file=sys.stderr)


if __name__ == "__main__":
    main()
