#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_imports.py — 依赖图提取器
====================================
扫描 Python / JavaScript / TypeScript 项目，提取模块间 import 依赖关系，
输出：
  1. 每个文件的 import 清单（本地模块 vs 外部依赖）
  2. 被引用次数排行（帮助识别"公共模块"）
  3. 简化版依赖图（Markdown 格式）

用法：
    python extract_imports.py [目标目录]
    python extract_imports.py .
    python extract_imports.py src/

输出到 stdout（Markdown），可直接复制到文档中。
"""

import re
import sys
import json
from pathlib import Path
from collections import defaultdict, Counter

# ─── 配置 ──────────────────────────────────────────────────────────────────

SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env",
    "node_modules", "dist", "build", ".mypy_cache",
}

# 标准库（不计入外部依赖）- 常用标准库前缀
STDLIB_PREFIXES = {
    "os", "sys", "re", "json", "time", "datetime", "pathlib", "typing",
    "collections", "itertools", "functools", "io", "abc", "enum",
    "dataclasses", "contextlib", "copy", "math", "random", "string",
    "struct", "hashlib", "base64", "urllib", "http", "email",
    "threading", "multiprocessing", "asyncio", "concurrent", "queue",
    "subprocess", "shutil", "tempfile", "glob", "fnmatch",
    "logging", "warnings", "traceback", "inspect", "types",
    "unittest", "pdb", "argparse", "configparser", "csv",
    "xml", "html", "sqlite3", "pickle", "shelve",
    "socket", "ssl", "select", "signal",
    "platform", "gc", "weakref", "array", "heapq", "bisect",
}

# ─── Python import 提取 ────────────────────────────────────────────────────

PY_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w., ]+))",
    re.MULTILINE
)

def extract_python_imports(filepath: Path) -> dict:
    """返回 {'local': [...], 'external': [...], 'stdlib': [...]}"""
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {"local": [], "external": [], "stdlib": []}

    local, external, stdlib = [], [], []

    for m in PY_IMPORT_RE.finditer(content):
        from_part = m.group(1)
        import_part = m.group(2)

        if from_part:
            modules = [from_part.split(".")[0]]
        elif import_part:
            modules = [s.strip().split(" ")[0].split(".")[0]
                      for s in import_part.split(",")]
        else:
            continue

        for mod in modules:
            mod = mod.strip()
            if not mod:
                continue
            if mod.startswith("."):
                local.append(mod)
            elif mod in STDLIB_PREFIXES or _is_stdlib(mod):
                stdlib.append(mod)
            else:
                external.append(mod)

    return {
        "local": sorted(set(local)),
        "external": sorted(set(external)),
        "stdlib": sorted(set(stdlib)),
    }


def _is_stdlib(module: str) -> bool:
    """尝试用 sys.stdlib_module_names（Python 3.10+）判断"""
    stdlib_names = getattr(sys, "stdlib_module_names", None)
    if stdlib_names:
        return module in stdlib_names
    return module in STDLIB_PREFIXES


# ─── JS/TS import 提取 ────────────────────────────────────────────────────

JS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?\s+from\s+['"]([^'"]+)['"]"""
    r"""|require\s*\(\s*['"]([^'"]+)['"]\s*\)""",
    re.MULTILINE
)

def extract_js_imports(filepath: Path) -> dict:
    """返回 {'local': [...], 'external': [...]}"""
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {"local": [], "external": []}

    local, external = [], []

    for m in JS_IMPORT_RE.finditer(content):
        path = m.group(1) or m.group(2)
        if not path:
            continue
        if path.startswith("."):
            local.append(path)
        elif not path.startswith("node:"):
            external.append(path.split("/")[0])  # scoped packages: @scope/pkg

    return {
        "local": sorted(set(local)),
        "external": sorted(set(external)),
    }


# ─── 主分析函数 ────────────────────────────────────────────────────────────

def analyze_project(root: Path) -> dict:
    """
    扫描整个项目，返回：
    {
      "files": {
        "relative/path/to/file.py": {
          "imports": {"local": [...], "external": [...], "stdlib": [...]},
          "referenced_by": [...]  # 被哪些文件引用
        }
      },
      "external_deps": Counter,  # 外部依赖引用次数
      "local_ref_count": Counter # 本地模块被引用次数
    }
    """
    file_data = {}
    external_deps = Counter()
    local_ref_count = Counter()

    # 第一遍：收集所有文件的 import
    for path in sorted(root.rglob("*")):
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        if not path.is_file():
            continue

        rel = path.relative_to(root)
        ext = path.suffix.lower()

        if ext == ".py":
            imports = extract_python_imports(path)
        elif ext in {".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx"}:
            imports = extract_js_imports(path)
        else:
            continue

        file_data[str(rel)] = {"imports": imports, "referenced_by": []}

        for dep in imports.get("external", []):
            external_deps[dep] += 1

    # 第二遍：建立反向引用（被谁引用）
    # 简化处理：将本地 import 路径转换为文件路径并匹配
    for file_path, data in file_data.items():
        local_imports = data["imports"].get("local", [])
        for local_imp in local_imports:
            # 转换 "from .utils import" → 查找 utils.py 或 utils/__init__.py
            clean = local_imp.lstrip(".")
            for candidate in file_data:
                if (candidate.endswith(clean + ".py") or
                        candidate.endswith(clean.replace(".", "/") + ".py") or
                        candidate.endswith(clean.replace(".", "/") + "/__init__.py")):
                    if file_path not in file_data[candidate]["referenced_by"]:
                        file_data[candidate]["referenced_by"].append(file_path)
                    local_ref_count[candidate] += 1

    return {
        "files": file_data,
        "external_deps": external_deps,
        "local_ref_count": local_ref_count,
    }


# ─── 输出格式化 ────────────────────────────────────────────────────────────

def format_markdown(root: Path, analysis: dict) -> str:
    lines = []

    # 标题
    lines.append("## 依赖分析报告 / Import Dependency Report\n")
    lines.append(f"> 分析目录：`{root}`  \n")
    lines.append(f"> 分析文件数：{len(analysis['files'])} 个\n\n")

    # 外部依赖汇总
    lines.append("### 外部依赖汇总\n")
    if analysis["external_deps"]:
        lines.append("| 依赖库 | 引用次数 | 说明 |\n")
        lines.append("|--------|---------|------|\n")
        for dep, count in analysis["external_deps"].most_common():
            lines.append(f"| `{dep}` | {count} | |\n")
    else:
        lines.append("无外部依赖。\n")
    lines.append("\n")

    # 本地模块引用次数排行
    ref_count = analysis["local_ref_count"]
    if ref_count:
        lines.append("### 本地模块引用排行（被引用次数越多，越是公共模块）\n\n")
        lines.append("| 文件 | 被引用次数 | 优先分析级别 |\n")
        lines.append("|------|-----------|-------------|\n")
        for filepath, count in ref_count.most_common(10):
            priority = "P0（必读）" if count >= 3 else "P1（优先）" if count >= 1 else "P2"
            lines.append(f"| `{filepath}` | {count} | {priority} |\n")
        lines.append("\n")

    # 每个文件的依赖详情
    lines.append("### 文件依赖详情\n\n")
    for filepath, data in sorted(analysis["files"].items()):
        imports = data["imports"]
        ref_by = data["referenced_by"]

        local = imports.get("local", [])
        external = imports.get("external", [])
        stdlib = imports.get("stdlib", [])

        if not local and not external:
            continue  # 跳过无依赖的文件

        lines.append(f"#### `{filepath}`\n\n")

        if external:
            lines.append(f"- **外部依赖**：{', '.join(f'`{d}`' for d in external)}\n")
        if local:
            lines.append(f"- **本地依赖**：{', '.join(f'`{d}`' for d in local)}\n")
        if stdlib:
            lines.append(f"- **标准库**：{', '.join(f'`{d}`' for d in stdlib[:5])}"
                        f"{'...' if len(stdlib) > 5 else ''}\n")
        if ref_by:
            lines.append(f"- **被引用方**：{', '.join(f'`{r}`' for r in ref_by[:5])}\n")
        else:
            lines.append("- **被引用方**：（无，可能是入口文件或独立脚本）\n")

        lines.append("\n")

    return "".join(lines)


# ─── 入口 ──────────────────────────────────────────────────────────────────

def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    target = target.resolve()

    if not target.exists() or not target.is_dir():
        print(f"❌ 无效目录：{target}", file=sys.stderr)
        sys.exit(1)

    print(f"正在分析：{target}", file=sys.stderr)
    analysis = analyze_project(target)
    print(format_markdown(target, analysis))

    # 额外输出：高引用模块提示
    top_modules = analysis["local_ref_count"].most_common(3)
    if top_modules:
        print(f"\n💡 建议优先深度分析的模块（被引用最多）：", file=sys.stderr)
        for mod, count in top_modules:
            print(f"   {mod}（被引用 {count} 次）", file=sys.stderr)


if __name__ == "__main__":
    main()
