from __future__ import annotations

import argparse
from datetime import datetime
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = ROOT / "reports" / "multilingual_quality_checks"


def _run_check(script_name: str) -> dict:
    script_path = ROOT / "scripts" / script_name
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if completed.returncode != 0:
        raise RuntimeError(
            f"{script_name} failed with exit code {completed.returncode}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )
    if not stdout:
        raise RuntimeError(f"{script_name} produced no JSON output")
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{script_name} did not return valid JSON:\n{stdout}") from exc


def _markdown_report(payload: dict) -> str:
    lines = [
        "# Multilingual Quality Check Report",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- Status: `{payload['status']}`",
        "",
    ]
    scripted = payload["checks"]["scripted_multilingual_text_service_smoke"]
    source_only = payload["checks"]["multilingual_pre_release_source_only"]
    lines.extend(
        [
            "## Checks",
            "",
            f"- Scripted multilingual text-service smoke: `{scripted.get('status', 'unknown')}`",
            f"- Real multilingual pre-release source-only: `{source_only.get('status', 'unknown')}`",
            "",
            "## Source-only Text Results",
            "",
            "| Language | Scenario | Text Backend | Generator | Quality |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for item in source_only.get("results", []):
        lines.append(
            f"| {item.get('language')} | {item.get('scenario')} | {item.get('text_backend')} | "
            f"{item.get('generator_version')} | {item.get('quality_passed')} |"
        )
    lines.extend(
        [
            "",
            "## Source-only Audio Results",
            "",
            "| Language | Audio Backend | Engine | Segments | VTT |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for item in source_only.get("audio_results", []):
        lines.append(
            f"| {item.get('language')} | {item.get('audio_backend')} | {item.get('audio_engine')} | "
            f"{item.get('segments_exists')} | {item.get('vtt_exists')} |"
        )
    return "\n".join(lines) + "\n"


def _write_reports(payload: dict, report_dir: Path) -> dict:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = report_dir / f"multilingual_quality_checks_{timestamp}.json"
    md_path = report_dir / f"multilingual_quality_checks_{timestamp}.md"
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
    parser = argparse.ArgumentParser(description="Run multilingual quality checks and emit fixed reports.")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="Directory for JSON/Markdown reports.")
    args = parser.parse_args(argv)
    scripted = _run_check("run_multilingual_text_service_smoke.py")
    source_only = _run_check("run_multilingual_pre_release_source_only_check.py")
    payload = {
        "entrypoint": "run_multilingual_quality_checks",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "checks": {
            "scripted_multilingual_text_service_smoke": scripted,
            "multilingual_pre_release_source_only": source_only,
        },
        "status": "ok",
    }
    payload["report_paths"] = _write_reports(payload, Path(args.report_dir))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
