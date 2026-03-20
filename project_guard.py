#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import fnmatch
import hashlib
import logging
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


LOGGER = logging.getLogger("project_guard")

DEFAULT_RULES_FILE = "project_guard_rules.yaml"
DEFAULT_IGNORE_FILE = ".cleanupignore"
DEFAULT_REPORT_FILE = "project_guard_report.md"
TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".bat",
    ".ps1",
    ".sh",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


@dataclass
class Action:
    kind: str
    source: Path
    destination: Path | None = None
    reason: str = ""


@dataclass
class GuardPlan:
    moves: list[Action] = field(default_factory=list)
    archives: list[Action] = field(default_factory=list)
    deletes: list[Action] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    health: dict[str, Any] = field(default_factory=dict)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    argv = list(sys.argv[1:] if argv is None else argv)
    subcommand = None
    if argv and argv[0] in {"cleanup-compat", "guard"}:
        subcommand = argv.pop(0)

    parser = argparse.ArgumentParser(description="Self-healing project organization tool.")
    parser.add_argument("--dry-run", action="store_true", help="Plan changes without mutating the repository.")
    parser.add_argument("--execute", action="store_true", help="Apply the planned changes.")
    parser.add_argument("--report-only", action="store_true", help="Only scan and generate the health report.")
    parser.add_argument("--watch", action="store_true", help="Continuously watch the repository and rerun the guard.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to the current directory.")
    parser.add_argument("--rules", default=DEFAULT_RULES_FILE, help="Rules YAML file.")
    parser.add_argument("--ignore-file", default=DEFAULT_IGNORE_FILE, help="Cleanup ignore file.")
    parser.add_argument("--report", default=DEFAULT_REPORT_FILE if subcommand != "cleanup-compat" else "cleanup_report.md", help="Report path.")
    parser.add_argument("--interval", type=int, default=None, help="Watch interval override in seconds.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Console log level.")
    parser.add_argument("--aggressive", action="store_true", help="Compat mode: widen suspicious script and artifact detection.")
    parser.set_defaults(command=subcommand or "guard")
    return parser.parse_args(argv if argv else None)


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level), format="[%(levelname)s] %(message)s")


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Rules file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Rules file must contain a top-level mapping: {path}")
    return data


def normalize_rules(raw_rules: dict[str, Any]) -> dict[str, Any]:
    rules = copy.deepcopy(raw_rules)

    if "target_directories" not in rules:
        target_dirs = {
            "src/demo_app",
            "config",
            "runtime/logs",
            "runtime/cache",
            "runtime/temp",
            "scripts",
            "tools/debug",
            "docs/archive",
            "archive/deprecated",
            "archive/deprecated/debug_scripts",
            "archive/deprecated/debug_images",
            "archive/failed_artifacts",
            "docs/archive/root_artifacts",
            "reports",
            "output",
        }
        for value in (
            rules.get("log_target_dir"),
            rules.get("cache_target_dir"),
            rules.get("temp_target_dir"),
            rules.get("asset_target_dir"),
            rules.get("domain_target_dir"),
            rules.get("core_module_target"),
            rules.get("debug_tool_target"),
            rules.get("doc_target"),
            rules.get("doc_archive_target"),
            rules.get("archive_target", {}).get("deprecated_scripts"),
            rules.get("archive_target", {}).get("deprecated_images"),
            rules.get("archive_target", {}).get("failed_artifacts"),
            rules.get("archive_target", {}).get("root_artifacts"),
            rules.get("runtime_artifact_target"),
        ):
            if value:
                target_dirs.add(value)
        rules["target_directories"] = sorted(target_dirs)

    if "targets" not in rules:
        archive_target = rules.get("archive_target", {})
        rules["targets"] = {
            "src_demo_app": rules.get("core_module_target", "src/demo_app"),
            "logs": rules.get("log_target_dir", "runtime/logs"),
            "tools_debug": rules.get("debug_tool_target", "tools/debug"),
            "archive_debug": archive_target.get("deprecated_scripts", "archive/deprecated/debug_scripts"),
            "archive_debug_images": archive_target.get("deprecated_images", "archive/deprecated/debug_images"),
            "failed_artifacts": archive_target.get("failed_artifacts", "archive/failed_artifacts"),
            "archive_root_artifacts": archive_target.get("root_artifacts", "docs/archive/root_artifacts"),
            "assets": rules.get("asset_target_dir", "src/demo_app/assets"),
            "domains": rules.get("domain_target_dir", "src/demo_app/domains"),
            "runtime": rules.get("runtime_artifact_target", "runtime"),
        }

    if "asset_directories" not in rules:
        rules["asset_directories"] = rules.get("asset_dirs", [])
    if "domain_directories" not in rules:
        rules["domain_directories"] = rules.get("domain_dirs", [])
    if "core_modules" not in rules:
        rules["core_modules"] = rules.get("core_module_patterns", [])
    if "failed_artifact_patterns" not in rules:
        rules["failed_artifact_patterns"] = rules.get("archive_patterns", [])
    if "cache_patterns" not in rules:
        rules["cache_patterns"] = {"files": rules.get("delete_patterns", [])}
    else:
        rules["cache_patterns"].setdefault("files", [])

    if "suspicious_scripts" not in rules:
        rules["suspicious_scripts"] = {
            "name_patterns": rules.get("temp_script_patterns", []),
            "keywords": rules.get("temp_script_keywords", []),
        }

    if "suspicious_images" not in rules:
        rules["suspicious_images"] = {
            "name_patterns": rules.get("temp_image_patterns", []),
            "keywords": rules.get("temp_image_keywords", []),
            "root_only": rules.get("temp_image_root_only", True),
        }

    if "protected" not in rules:
        rules["protected"] = {
            "exact_paths": rules.get("protected_files", []),
            "patterns": rules.get("protected_patterns", []),
        }

    if "root_whitelist" not in rules:
        rules["root_whitelist"] = list(rules.get("root_allowlist", [])) + list(rules.get("root_allow_dirs", []))

    rules.setdefault("runtime_artifact_patterns", [])
    rules.setdefault("report", {})
    rules.setdefault("watch", {})
    return rules


def build_cleanup_compat_rules(base_rules: dict[str, Any], aggressive: bool) -> dict[str, Any]:
    rules = copy.deepcopy(base_rules)
    suspicious = rules.setdefault("suspicious_scripts", {})
    suspicious["name_patterns"] = ["__tmp_*.py", "tmp_*.py", "probe_*.py"]
    suspicious["keywords"] = []
    rules["failed_artifact_patterns"] = ["*_failed", "*_corrupted"]
    rules["cache_patterns"] = {"files": ["*.pyc", "*.pyo"]}
    if aggressive:
        suspicious["name_patterns"] = [
            "__tmp_*.py",
            "tmp_*.py",
            "probe_*.py",
            "debug_*.py",
            "test_loader*.py",
            "inspect*.py",
            "check_*.py",
        ]
        suspicious["keywords"] = ["probe", "introspect", "verify", "loader_test", "compat"]
        rules["failed_artifact_patterns"] = ["*_failed", "*_corrupted", "*_legacy"]
        rules["cache_patterns"] = {"files": ["*.pyc", "*.pyo", "*.tmp"]}
    return rules


def load_ignore_patterns(root: Path, ignore_file: str) -> list[str]:
    path = (root / ignore_file).resolve()
    if not path.exists():
        return []
    patterns: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def normalize_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def is_ignored(path: Path, root: Path, patterns: list[str]) -> bool:
    rel = normalize_path(path, root)
    for pattern in patterns:
        normalized = pattern.replace("\\", "/")
        if fnmatch.fnmatch(rel, normalized) or fnmatch.fnmatch(path.name, normalized):
            return True
    return False


def ensure_structure(root: Path, rules: dict[str, Any]) -> None:
    directories = rules.get("target_directories", [])
    for directory in directories:
        (root / directory).mkdir(parents=True, exist_ok=True)


def iter_repo_paths(root: Path, ignore_patterns: list[str]) -> tuple[list[Path], list[Path]]:
    files: list[Path] = []
    dirs: list[Path] = []
    for path in root.rglob("*"):
        if is_ignored(path, root, ignore_patterns):
            continue
        if path.is_dir():
            dirs.append(path)
        else:
            files.append(path)
    return files, dirs


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""
    except OSError:
        return ""


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_collision(source: Path, destination: Path) -> Path:
    if not destination.exists():
        return destination
    if source.is_file() and destination.is_file():
        try:
            if file_hash(source) == file_hash(destination):
                return destination
        except OSError:
            pass
    stem = destination.stem
    suffix = destination.suffix
    index = 1
    while True:
        candidate = destination.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def merge_directory(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir() and target.exists():
            merge_directory(child, target)
            child.rmdir()
        else:
            shutil.move(str(child), str(target))
    source.rmdir()


def is_protected(path: Path, root: Path, rules: dict[str, Any]) -> bool:
    rel = normalize_path(path, root)
    name = path.name
    protected = rules.get("protected", {})
    exact = set(protected.get("exact_paths", []))
    patterns = protected.get("patterns", [])
    if rel in exact or name in exact:
        return True
    return any(fnmatch.fnmatch(rel, pattern.replace("\\", "/")) or fnmatch.fnmatch(name, pattern) for pattern in patterns)


def is_core_root_file(path: Path, root: Path, rules: dict[str, Any]) -> bool:
    if path.parent != root:
        return False
    return is_protected(path, root, rules)


def should_preserve_script_location(path: Path, root: Path, rules: dict[str, Any]) -> bool:
    safety = rules.get("safety", {})
    if not safety.get("prevent_import_breakage", False):
        return False
    rel = normalize_path(path, root)
    if rel.startswith("training/"):
        return True
    if rel.startswith("tests/") and path.name.startswith("test_"):
        return True
    if path.name.startswith("run_"):
        return True
    return False


def file_is_referenced(target: Path, root: Path, include_stem: bool = True) -> bool:
    markers = {
        target.name,
        normalize_path(target, root),
        normalize_path(target, root).replace("/", "\\"),
    }
    if include_stem:
        markers.add(target.stem)
    for path in root.rglob("*"):
        if path == target or path.is_dir():
            continue
        rel = normalize_path(path, root)
        if rel.startswith("runtime/temp/"):
            continue
        if path.name == DEFAULT_RULES_FILE:
            continue
        if path.name.startswith("project_guard") and path.suffix.lower() == ".md":
            continue
        if path.name.startswith("cleanup_report") and path.suffix.lower() == ".md":
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        text = read_text(path)
        if text and any(marker in text for marker in markers):
            return True
    return False


def looks_suspicious_python(path: Path, rules: dict[str, Any]) -> bool:
    if path.suffix != ".py":
        return False
    name = path.name
    suspicious = rules.get("suspicious_scripts", {})
    if any(fnmatch.fnmatch(name, pattern) for pattern in suspicious.get("name_patterns", [])):
        return True
    lower_name = name.lower()
    if any(keyword.lower() in lower_name for keyword in suspicious.get("keywords", [])):
        return True
    text = read_text(path)[:4096].lower()
    return any(keyword.lower() in text for keyword in suspicious.get("keywords", []))


def looks_suspicious_image(path: Path, root: Path, rules: dict[str, Any]) -> bool:
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        return False
    suspicious = rules.get("suspicious_images", {})
    if suspicious.get("root_only", True) and path.parent != root:
        return False
    name = path.name.lower()
    if any(fnmatch.fnmatch(path.name, pattern) for pattern in suspicious.get("name_patterns", [])):
        return True
    if any(keyword.lower() in name for keyword in suspicious.get("keywords", [])):
        return True
    return path.parent == root


def classify_files(root: Path, files: list[Path], dirs: list[Path], rules: dict[str, Any], ignore_patterns: list[str]) -> dict[str, list[Path]]:
    classified: dict[str, list[Path]] = {
        "logs": [],
        "cache_files": [],
        "cache_dirs": [],
        "temp_scripts": [],
        "temp_images": [],
        "root_artifacts": [],
        "failed_artifacts": [],
        "asset_dirs": [],
        "domain_dirs": [],
        "core_modules": [],
        "runtime_artifacts": [],
    }
    asset_dirs = set(rules.get("asset_directories", []))
    domain_dirs = set(rules.get("domain_directories", []))
    core_modules = set(rules.get("core_modules", []))
    failed_patterns = rules.get("failed_artifact_patterns", [])
    cache_patterns = rules.get("cache_patterns", {}).get("files", [])
    runtime_patterns = rules.get("runtime_artifact_patterns", [])
    log_patterns = rules.get("log_patterns", ["*.log"])
    delete_dirs = set(rules.get("delete_dirs", ["__pycache__"]))
    root_archive_patterns = rules.get("root_archive_patterns", [])

    for file_path in files:
        rel = normalize_path(file_path, root)
        under_archive = rel.startswith("archive/")
        if any(fnmatch.fnmatch(file_path.name, pattern) for pattern in log_patterns):
            classified["logs"].append(file_path)
        if file_path.parent == root and any(fnmatch.fnmatch(file_path.name, pattern) for pattern in root_archive_patterns):
            classified["root_artifacts"].append(file_path)
        if any(file_path.match(pattern) for pattern in cache_patterns):
            classified["cache_files"].append(file_path)
        if not under_archive and any(fnmatch.fnmatch(file_path.name, pattern) for pattern in failed_patterns):
            classified["failed_artifacts"].append(file_path)
        if (
            not under_archive
            and looks_suspicious_python(file_path, rules)
            and not is_protected(file_path, root, rules)
            and not should_preserve_script_location(file_path, root, rules)
        ):
            classified["temp_scripts"].append(file_path)
        if (
            not under_archive
            and looks_suspicious_image(file_path, root, rules)
            and not is_protected(file_path, root, rules)
        ):
            classified["temp_images"].append(file_path)
        if file_path.parent == root and file_path.name in core_modules and not is_core_root_file(file_path, root, rules):
            classified["core_modules"].append(file_path)
        if file_path.parent == root and any(fnmatch.fnmatch(file_path.name, pattern) for pattern in runtime_patterns):
            classified["runtime_artifacts"].append(file_path)

    for dir_path in dirs:
        rel = normalize_path(dir_path, root)
        under_archive = rel.startswith("archive/")
        if dir_path.name in delete_dirs:
            classified["cache_dirs"].append(dir_path)
        if dir_path.parent == root and dir_path.name in asset_dirs:
            classified["asset_dirs"].append(dir_path)
        if dir_path.parent == root and dir_path.name in domain_dirs:
            classified["domain_dirs"].append(dir_path)
        if not under_archive and any(fnmatch.fnmatch(dir_path.name, pattern) for pattern in failed_patterns):
            classified["failed_artifacts"].append(dir_path)
        if dir_path.parent == root and any(fnmatch.fnmatch(dir_path.name, pattern) for pattern in runtime_patterns):
            classified["runtime_artifacts"].append(dir_path)

    return classified


def add_move(plan: GuardPlan, source: Path, destination: Path, reason: str) -> None:
    plan.moves.append(Action("move", source, destination, reason))


def add_archive(plan: GuardPlan, source: Path, destination: Path, reason: str) -> None:
    plan.archives.append(Action("archive", source, destination, reason))


def add_delete(plan: GuardPlan, source: Path, reason: str) -> None:
    plan.deletes.append(Action("delete", source, None, reason))


def plan_actions(root: Path, classified: dict[str, list[Path]], rules: dict[str, Any]) -> GuardPlan:
    plan = GuardPlan()
    targets = rules.get("targets", {})

    for log_path in classified["logs"]:
        target_root = root / targets["logs"]
        if str(log_path).startswith(str(target_root)):
            continue
        if log_path.stat().st_size == 0:
            add_delete(plan, log_path, "empty log file")
            continue
        add_move(plan, log_path, resolve_collision(log_path, target_root / log_path.name), "centralize log file")

    for script in classified["temp_scripts"]:
        if str(script).startswith(str(root / targets["archive_debug"])) or str(script).startswith(str(root / targets["tools_debug"])):
            plan.skipped.append(f"skip {normalize_path(script, root)}: already organized")
            continue
        referenced = file_is_referenced(script, root, include_stem=True)
        bucket = "tools_debug" if referenced else "archive_debug"
        destination = resolve_collision(script, root / targets[bucket] / script.name)
        reason = "referenced suspicious script" if referenced else "unreferenced suspicious script"
        if referenced:
            add_move(plan, script, destination, reason)
        else:
            add_archive(plan, script, destination, reason)

    for image in classified["temp_images"]:
        archive_root = root / targets["archive_debug_images"]
        if str(image).startswith(str(archive_root)):
            plan.skipped.append(f"skip {normalize_path(image, root)}: already organized")
            continue
        referenced = file_is_referenced(image, root, include_stem=False)
        if referenced:
            plan.warnings.append(f"referenced debug image left in place: {normalize_path(image, root)}")
            continue
        destination = resolve_collision(image, archive_root / image.name)
        add_archive(plan, image, destination, "unreferenced debug image")

    for artifact in classified["failed_artifacts"]:
        destination = resolve_collision(artifact, root / targets["failed_artifacts"] / artifact.name)
        if normalize_path(artifact, root).startswith(targets["failed_artifacts"].replace("\\", "/")):
            plan.skipped.append(f"skip {normalize_path(artifact, root)}: already archived")
            continue
        add_archive(plan, artifact, destination, "failed/corrupted artifact")

    for artifact in classified["root_artifacts"]:
        archive_root = root / targets["archive_root_artifacts"]
        if str(artifact).startswith(str(archive_root)):
            plan.skipped.append(f"skip {normalize_path(artifact, root)}: already organized")
            continue
        referenced = file_is_referenced(artifact, root, include_stem=False)
        if referenced:
            plan.warnings.append(f"referenced root artifact left in place: {normalize_path(artifact, root)}")
            continue
        destination = resolve_collision(artifact, archive_root / artifact.name)
        add_archive(plan, artifact, destination, "root-level historical artifact")

    for path in classified["cache_dirs"]:
        add_delete(plan, path, "python cache directory")
    for path in classified["cache_files"]:
        add_delete(plan, path, "compiled cache file")

    for directory in classified["asset_dirs"]:
        destination = resolve_collision(directory, root / targets["assets"] / directory.name)
        add_move(plan, directory, destination, "asset directory")

    for directory in classified["domain_dirs"]:
        destination = resolve_collision(directory, root / targets["domains"] / directory.name)
        add_move(plan, directory, destination, "domain directory")

    for module in classified["core_modules"]:
        destination = resolve_collision(module, root / targets["src_demo_app"] / module.name)
        add_move(plan, module, destination, "core module")

    for artifact in classified["runtime_artifacts"]:
        destination = resolve_collision(artifact, root / targets.get("runtime", "runtime") / artifact.name)
        add_move(plan, artifact, destination, "runtime artifact")

    add_root_clutter_warnings(root, rules, plan)
    return plan


def add_root_clutter_warnings(root: Path, rules: dict[str, Any], plan: GuardPlan) -> None:
    whitelist = set(rules.get("root_whitelist", []))
    extras = sorted(path.name for path in root.iterdir() if path.name not in whitelist)
    if extras:
        plan.warnings.append(f"root clutter detected: {', '.join(extras)}")


def execute_plan(root: Path, plan: GuardPlan, execute: bool) -> None:
    if not execute:
        return
    for action in plan.moves + plan.archives:
        assert action.destination is not None
        action.destination.parent.mkdir(parents=True, exist_ok=True)
        LOGGER.info("%s %s -> %s (%s)", action.kind.upper(), normalize_path(action.source, root), normalize_path(action.destination, root), action.reason)
        if action.source.is_dir() and action.destination.exists():
            merge_directory(action.source, action.destination)
        else:
            shutil.move(str(action.source), str(action.destination))
    for action in plan.deletes:
        LOGGER.info("DELETE %s (%s)", normalize_path(action.source, root), action.reason)
        if action.source.is_dir():
            shutil.rmtree(action.source, ignore_errors=True)
        else:
            action.source.unlink(missing_ok=True)


def collect_health(root: Path, rules: dict[str, Any], files: list[Path], dirs: list[Path], classified: dict[str, list[Path]], plan: GuardPlan) -> dict[str, Any]:
    required_dirs = rules.get("target_directories", [])
    missing_dirs = [directory for directory in required_dirs if not (root / directory).exists()]
    return {
        "file_count": len(files),
        "directory_count": len(dirs),
        "logs_found": len(classified["logs"]),
        "cache_files_found": len(classified["cache_files"]),
        "cache_dirs_found": len(classified["cache_dirs"]),
        "suspicious_scripts_found": len(classified["temp_scripts"]),
        "suspicious_images_found": len(classified["temp_images"]),
        "root_artifacts_found": len(classified["root_artifacts"]),
        "failed_artifacts_found": len(classified["failed_artifacts"]),
        "runtime_artifacts_found": len(classified["runtime_artifacts"]),
        "planned_moves": len(plan.moves),
        "planned_archives": len(plan.archives),
        "planned_deletes": len(plan.deletes),
        "warnings": len(plan.warnings),
        "missing_required_directories": missing_dirs,
    }


def write_report(root: Path, report_name: str, mode: str, plan: GuardPlan) -> Path:
    report_path = (root / report_name).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    def rel(path: Path | None) -> str:
        return "-" if path is None else normalize_path(path, root)

    lines = [
        "# Project Guard Report",
        "",
        f"- mode: {mode}",
        f"- planned_moves: {len(plan.moves)}",
        f"- planned_archives: {len(plan.archives)}",
        f"- planned_deletes: {len(plan.deletes)}",
        f"- warnings: {len(plan.warnings)}",
        "",
        "## Repository Health",
        "",
    ]
    for key, value in plan.health.items():
        lines.append(f"- {key}: {value}")

    lines += ["", "## Planned Moves", ""]
    lines += [f"- `{rel(action.source)}` -> `{rel(action.destination)}` ({action.reason})" for action in plan.moves] or ["- none"]

    lines += ["", "## Planned Archives", ""]
    lines += [f"- `{rel(action.source)}` -> `{rel(action.destination)}` ({action.reason})" for action in plan.archives] or ["- none"]

    lines += ["", "## Planned Deletes", ""]
    lines += [f"- `{rel(action.source)}` ({action.reason})" for action in plan.deletes] or ["- none"]

    lines += ["", "## Warnings", ""]
    lines += [f"- {warning}" for warning in plan.warnings] or ["- none"]

    lines += ["", "## Skipped", ""]
    lines += [f"- {item}" for item in plan.skipped] or ["- none"]

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def make_snapshot(root: Path, ignore_patterns: list[str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if is_ignored(path, root, ignore_patterns):
            continue
        rel = normalize_path(path, root)
        try:
            stat = path.stat()
            digest.update(f"{rel}|{int(stat.st_mtime)}|{stat.st_size}|{path.is_dir()}".encode("utf-8", errors="ignore"))
        except OSError:
            continue
    return digest.hexdigest()


def run_guard(root: Path, rules: dict[str, Any], ignore_patterns: list[str], mode: str, report_name: str) -> GuardPlan:
    ensure_structure(root, rules)
    files, dirs = iter_repo_paths(root, ignore_patterns)
    classified = classify_files(root, files, dirs, rules, ignore_patterns)
    plan = plan_actions(root, classified, rules)
    plan.health = collect_health(root, rules, files, dirs, classified, plan)
    write_report(root, report_name, mode, plan)
    return plan


def watch_loop(root: Path, rules: dict[str, Any], ignore_patterns: list[str], primary_mode: str, report_name: str, interval: int) -> int:
    LOGGER.info("watch mode active: interval=%ss primary_mode=%s", interval, primary_mode)
    previous = ""
    try:
        while True:
            current = make_snapshot(root, ignore_patterns)
            if current != previous:
                previous = current
                plan = run_guard(root, rules, ignore_patterns, f"watch:{primary_mode}", report_name)
                if primary_mode == "execute":
                    execute_plan(root, plan, execute=True)
                    plan = run_guard(root, rules, ignore_patterns, "watch:post-execute", report_name)
                LOGGER.info(
                    "scan complete: moves=%d archives=%d deletes=%d warnings=%d",
                    len(plan.moves),
                    len(plan.archives),
                    len(plan.deletes),
                    len(plan.warnings),
                )
            time.sleep(interval)
    except KeyboardInterrupt:
        LOGGER.info("watch mode stopped")
        return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)
    root = Path(args.root).resolve()
    rules = normalize_rules(load_yaml((root / args.rules).resolve()))
    if args.command == "cleanup-compat":
        rules = build_cleanup_compat_rules(rules, aggressive=args.aggressive)
    if args.report == DEFAULT_REPORT_FILE:
        args.report = rules.get("report", {}).get("report_file", DEFAULT_REPORT_FILE)
    ignore_patterns = load_ignore_patterns(root, args.ignore_file)

    selected_modes = [args.dry_run, args.execute, args.report_only]
    if sum(bool(flag) for flag in selected_modes) > 1:
        raise SystemExit("Choose only one of --dry-run, --execute, or --report-only.")
    primary_mode = "execute" if args.execute else "report-only" if args.report_only else "dry-run"

    if args.watch:
        interval = args.interval or int(rules.get("watch", {}).get("interval_seconds", 8))
        return watch_loop(root, rules, ignore_patterns, primary_mode, args.report, interval)

    plan = run_guard(root, rules, ignore_patterns, primary_mode, args.report)
    if primary_mode == "execute":
        execute_plan(root, plan, execute=True)
        plan = run_guard(root, rules, ignore_patterns, "post-execute", args.report)

    LOGGER.info(
        "mode=%s moves=%d archives=%d deletes=%d warnings=%d",
        primary_mode,
        len(plan.moves),
        len(plan.archives),
        len(plan.deletes),
        len(plan.warnings),
    )
    LOGGER.info("report written to %s", (root / args.report).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
