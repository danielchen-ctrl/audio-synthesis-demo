from __future__ import annotations

import argparse
from datetime import datetime
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = ROOT / "runtime" / "temp" / "repo_daily_checks"


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _markdown_report(payload: dict) -> str:
    git_status = payload["git"]["status"].strip() or "(empty)"
    lines = [
        "# Repo Daily Check",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- Git branch summary: `{payload['git']['branch_summary']}`",
        f"- Git clean: `{payload['git']['clean']}`",
        f"- Project guard status: `{payload['project_guard']['status']}`",
        "",
        "## Git Status",
        "",
        "```text",
        git_status,
        "```",
        "",
        "## Project Guard",
        "",
        f"- Exit code: `{payload['project_guard']['exit_code']}`",
        f"- Report path: `{payload['project_guard']['report_path']}`",
        "",
    ]
    stdout = payload["project_guard"]["stdout"].strip()
    stderr = payload["project_guard"]["stderr"].strip()
    if stdout:
        lines.extend(["### Guard Stdout", "", "```text", stdout, "```", ""])
    if stderr:
        lines.extend(["### Guard Stderr", "", "```text", stderr, "```", ""])
    return "\n".join(lines) + "\n"


def _write_reports(payload: dict, report_dir: Path) -> dict:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = report_dir / f"repo_daily_check_{timestamp}.json"
    md_path = report_dir / f"repo_daily_check_{timestamp}.md"
    latest_json = report_dir / "latest.json"
    latest_md = report_dir / "latest.md"
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    md_text = _markdown_report(payload)
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "latest_json": str(latest_json),
        "latest_markdown": str(latest_md),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run git status + project_guard and emit a fixed report.")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="Directory for JSON/Markdown reports.")
    args = parser.parse_args(argv)

    git_status = _run(["git", "status", "--short", "--branch"], cwd=ROOT)
    if git_status.returncode != 0:
        raise SystemExit(git_status.returncode)

    guard_report = Path(args.report_dir) / "project_guard_latest.md"
    project_guard = _run(
        [
            sys.executable,
            "project_guard.py",
            "--report-only",
            "--report",
            str(guard_report),
        ],
        cwd=ROOT,
    )

    status_text = (git_status.stdout or "").strip()
    status_lines = [line for line in status_text.splitlines() if line.strip()]
    branch_summary = status_lines[0] if status_lines else "unknown"
    clean = len(status_lines) <= 1

    payload = {
        "entrypoint": "run_repo_daily_check",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "git": {
            "branch_summary": branch_summary,
            "clean": clean,
            "status": status_text,
            "exit_code": git_status.returncode,
        },
        "project_guard": {
            "status": "ok" if project_guard.returncode == 0 else "error",
            "exit_code": project_guard.returncode,
            "stdout": (project_guard.stdout or "").strip(),
            "stderr": (project_guard.stderr or "").strip(),
            "report_path": str(guard_report),
        },
        "status": "ok" if project_guard.returncode == 0 else "error",
    }
    payload["report_paths"] = _write_reports(payload, Path(args.report_dir))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if project_guard.returncode == 0 else project_guard.returncode


if __name__ == "__main__":
    raise SystemExit(main())
