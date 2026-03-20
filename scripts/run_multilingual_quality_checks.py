from __future__ import annotations

import argparse
from datetime import datetime
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = ROOT / "reports" / "multilingual_quality_checks"


def _timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _decode_output(raw: bytes) -> str:
    if not raw:
        return ""
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _run_check(script_name: str) -> dict[str, Any]:
    script_path = ROOT / "scripts" / script_name
    started_at = _timestamp()
    start_monotonic = time.monotonic()
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=ROOT,
        capture_output=True,
    )
    finished_at = _timestamp()
    stdout = _decode_output(completed.stdout).strip()
    stderr = _decode_output(completed.stderr).strip()
    duration_sec = round(time.monotonic() - start_monotonic, 3)

    parsed_payload: dict[str, Any] | None = None
    parse_error = ""
    if stdout:
        try:
            candidate = json.loads(stdout)
            if isinstance(candidate, dict):
                parsed_payload = candidate
            else:
                parse_error = "stdout JSON is not an object"
        except json.JSONDecodeError as exc:
            parse_error = f"stdout is not valid JSON: {exc}"
    else:
        parse_error = "stdout is empty"

    if completed.returncode == 0 and parsed_payload is not None:
        status = parsed_payload.get("status") or "ok"
    elif completed.returncode != 0:
        status = "error"
    else:
        status = "invalid_output"

    return {
        "script": script_name,
        "script_path": str(script_path),
        "status": status,
        "exit_code": completed.returncode,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_sec": duration_sec,
        "stdout": stdout,
        "stderr": stderr,
        "parse_error": parse_error,
        "payload": parsed_payload,
    }


def _failure_item(
    *,
    check_name: str,
    level: str,
    message: str,
    suggested_action: str,
    language: str | None = None,
    scenario: str | None = None,
    component: str | None = None,
) -> dict[str, Any]:
    item = {
        "check": check_name,
        "level": level,
        "message": message,
        "suggested_action": suggested_action,
    }
    if language:
        item["language"] = language
    if scenario:
        item["scenario"] = scenario
    if component:
        item["component"] = component
    return item


def _script_level_failures(check_name: str, result: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    if result["exit_code"] != 0:
        failures.append(
            _failure_item(
                check_name=check_name,
                level="error",
                component="runner",
                message=f"{result['script']} exited with code {result['exit_code']}",
                suggested_action=f"先在本地执行 `python scripts/{result['script']}`，查看 stdout/stderr 并修复脚本失败。",
            )
        )
    if result["parse_error"]:
        failures.append(
            _failure_item(
                check_name=check_name,
                level="error",
                component="reporting",
                message=f"{result['script']} 没有返回稳定 JSON：{result['parse_error']}",
                suggested_action="检查脚本输出，确保标准输出只打印一段 JSON 结果。",
            )
        )
    return failures


def _analyze_scripted_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    failures = _script_level_failures("scripted_multilingual_text_service_smoke", result)
    payload = result.get("payload") or {}
    for item in payload.get("results", []):
        language = item.get("language") or "unknown"
        if not item.get("ok"):
            failures.append(
                _failure_item(
                    check_name="scripted_multilingual_text_service_smoke",
                    level="error",
                    component="text",
                    language=language,
                    message="scripted multilingual text smoke 未通过",
                    suggested_action=f"先单独运行 `python scripts/run_multilingual_text_service_smoke.py`，定位 {language} 的脚本化用例失败原因。",
                )
            )
        if not item.get("quality_passed", True):
            failures.append(
                _failure_item(
                    check_name="scripted_multilingual_text_service_smoke",
                    level="error",
                    component="quality_gate",
                    language=language,
                    message="quality gate 未通过",
                    suggested_action=f"检查 {language} 的文本后处理和质量规则，确认 persona / conflict / leakage 规则是否仍然生效。",
                )
            )
    return failures


def _analyze_source_only_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    failures = _script_level_failures("multilingual_pre_release_source_only", result)
    payload = result.get("payload") or {}

    for item in payload.get("results", []):
        language = item.get("language") or "unknown"
        scenario = item.get("scenario") or "unknown"
        if not item.get("text_ok"):
            failures.append(
                _failure_item(
                    check_name="multilingual_pre_release_source_only",
                    level="error",
                    component="text",
                    language=language,
                    scenario=scenario,
                    message="真实 source-only 文本生成失败",
                    suggested_action=f"单独运行 `python scripts/run_multilingual_pre_release_source_only_check.py`，重点排查 {language}/{scenario} 的文本生成链。",
                )
            )
        if not item.get("quality_passed", False):
            failures.append(
                _failure_item(
                    check_name="multilingual_pre_release_source_only",
                    level="error",
                    component="quality_gate",
                    language=language,
                    scenario=scenario,
                    message="真实 source-only 文本已生成，但 quality gate 未通过",
                    suggested_action=f"检查 {language}/{scenario} 的失败摘要，优先看内容泄漏、persona、conflict budget 和语言自然度规则。",
                )
            )
        expected_text_backend = item.get("expected_text_backend")
        if expected_text_backend and item.get("text_backend") != expected_text_backend:
            failures.append(
                _failure_item(
                    check_name="multilingual_pre_release_source_only",
                    level="error",
                    component="text_backend",
                    language=language,
                    scenario=scenario,
                    message=f"文本 backend 异常：{item.get('text_backend')}（期望 {expected_text_backend}）",
                    suggested_action="确认当前检查模式和预期 backend 是否一致，避免主路径退回不期望的实现。",
                )
            )
        if item.get("source_v2_fallback"):
            failures.append(
                _failure_item(
                    check_name="multilingual_pre_release_source_only",
                    level="warning",
                    component="v2_fallback",
                    language=language,
                    scenario=scenario,
                    message="source V2 走了 fallback",
                    suggested_action="确认该语言/场景是否仍存在源码 V2 缺口，必要时补规则或补 source generator。",
                )
            )
        if item.get("source_fallback_bundle_fallback"):
            failures.append(
                _failure_item(
                    check_name="multilingual_pre_release_source_only",
                    level="error",
                    component="legacy_text_fallback",
                    language=language,
                    scenario=scenario,
                    message="文本主链退回了 bundle fallback",
                    suggested_action="检查 source fallback 生成器与 legacy fallback policy，确保 pre_release 下不再依赖 bundle。",
                )
            )

    for item in payload.get("audio_results", []):
        language = item.get("language") or "unknown"
        if not item.get("audio_ok"):
            failures.append(
                _failure_item(
                    check_name="multilingual_pre_release_source_only",
                    level="error",
                    component="audio",
                    language=language,
                    message="真实 source-only 音频生成失败",
                    suggested_action=f"检查 {language} 的 voice 选择、TTS 调用和音频引擎日志。",
                )
            )
        expected_audio_backend = item.get("expected_audio_backend")
        if expected_audio_backend and item.get("audio_backend") != expected_audio_backend:
            failures.append(
                _failure_item(
                    check_name="multilingual_pre_release_source_only",
                    level="error",
                    component="audio_backend",
                    language=language,
                    message=f"音频 backend 异常：{item.get('audio_backend')}（期望 {expected_audio_backend}）",
                    suggested_action="确认当前检查模式和预期 backend 是否一致，避免音频链回退到不期望的实现。",
                )
            )
        expected_audio_engine = item.get("expected_audio_engine")
        if expected_audio_engine and item.get("audio_engine") != expected_audio_engine:
            failures.append(
                _failure_item(
                    check_name="multilingual_pre_release_source_only",
                    level="warning",
                    component="audio_engine",
                    language=language,
                    message=f"音频 engine 偏离预期：{item.get('audio_engine')}（期望 {expected_audio_engine}）",
                    suggested_action="确认当前检查模式和音频实现是否一致，并排查是否触发了降级。",
                )
            )
        if not item.get("segments_exists"):
            failures.append(
                _failure_item(
                    check_name="multilingual_pre_release_source_only",
                    level="error",
                    component="segments",
                    language=language,
                    message="segments.json 缺失",
                    suggested_action="检查音频后处理链，确认分段文件是否在生成成功后落盘。",
                )
            )
        if not item.get("vtt_exists"):
            failures.append(
                _failure_item(
                    check_name="multilingual_pre_release_source_only",
                    level="error",
                    component="transcript",
                    language=language,
                    message="transcript.vtt 缺失",
                    suggested_action="检查字幕导出逻辑，确认 transcript.vtt 是否稳定落盘。",
                )
            )

    return failures


def _build_summary(scripted: dict[str, Any], source_only: dict[str, Any], failures: list[dict[str, Any]]) -> dict[str, Any]:
    scripted_payload = scripted.get("payload") or {}
    source_payload = source_only.get("payload") or {}
    scripted_results = scripted_payload.get("results", [])
    source_text_results = source_payload.get("results", [])
    source_audio_results = source_payload.get("audio_results", [])
    error_count = sum(1 for item in failures if item["level"] == "error")
    warning_count = sum(1 for item in failures if item["level"] == "warning")
    passed_checks = sum(
        1
        for item in (scripted, source_only)
        if item.get("status") == "ok" and not _script_level_failures("check", item)
    )
    return {
        "check_count": 2,
        "passed_checks": passed_checks,
        "failed_checks": 2 - passed_checks,
        "scripted_language_count": len(scripted_results),
        "source_text_language_count": len(source_text_results),
        "source_audio_language_count": len(source_audio_results),
        "error_count": error_count,
        "warning_count": warning_count,
        "latest_status": "ok" if error_count == 0 else "error",
    }


def _unique_suggestions(failures: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    suggestions: list[str] = []
    for item in failures:
        suggestion = item.get("suggested_action") or ""
        if suggestion and suggestion not in seen:
            seen.add(suggestion)
            suggestions.append(suggestion)
    return suggestions


def _markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    scripted = payload["checks"]["scripted_multilingual_text_service_smoke"]
    source_only = payload["checks"]["multilingual_pre_release_source_only"]
    failures = payload["failure_summary"]
    suggestions = payload["suggested_actions"]

    lines = [
        "# Multilingual Quality Check Report",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- Status: `{payload['status']}`",
        f"- Report schema version: `{payload['report_schema_version']}`",
        "",
        "## Summary",
        "",
        f"- Checks: `{summary['check_count']}`",
        f"- Passed checks: `{summary['passed_checks']}`",
        f"- Failed checks: `{summary['failed_checks']}`",
        f"- Scripted languages: `{summary['scripted_language_count']}`",
        f"- Source-only text languages: `{summary['source_text_language_count']}`",
        f"- Source-only audio languages: `{summary['source_audio_language_count']}`",
        f"- Errors: `{summary['error_count']}`",
        f"- Warnings: `{summary['warning_count']}`",
        "",
        "## Check Status",
        "",
        f"- Scripted multilingual text-service smoke: `{scripted.get('status', 'unknown')}` (exit `{scripted.get('exit_code')}`)",
        f"- Real multilingual pre-release source-only: `{source_only.get('status', 'unknown')}` (exit `{source_only.get('exit_code')}`)",
        "",
    ]

    if failures:
        lines.extend(
            [
                "## Failure Summary",
                "",
                "| Level | Check | Language | Scenario | Component | Message |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in failures:
            lines.append(
                f"| {item.get('level', '')} | {item.get('check', '')} | {item.get('language', '-')} | "
                f"{item.get('scenario', '-')} | {item.get('component', '-')} | {item.get('message', '')} |"
            )
        lines.append("")
    else:
        lines.extend(["## Failure Summary", "", "- No failures detected.", ""])

    if suggestions:
        lines.extend(["## Suggested Actions", ""])
        for suggestion in suggestions:
            lines.append(f"- {suggestion}")
        lines.append("")

    lines.extend(
        [
            "## Source-only Text Results",
            "",
            "| Language | Scenario | Text Backend | Generator | Quality |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for item in (source_only.get("payload") or {}).get("results", []):
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
    for item in (source_only.get("payload") or {}).get("audio_results", []):
        lines.append(
            f"| {item.get('language')} | {item.get('audio_backend')} | {item.get('audio_engine')} | "
            f"{item.get('segments_exists')} | {item.get('vtt_exists')} |"
        )

    lines.extend(
        [
            "",
            "## Raw Check Diagnostics",
            "",
            f"- Scripted stdout lines: `{len((scripted.get('stdout') or '').splitlines())}`",
            f"- Scripted stderr lines: `{len((scripted.get('stderr') or '').splitlines())}`",
            f"- Source-only stdout lines: `{len((source_only.get('stdout') or '').splitlines())}`",
            f"- Source-only stderr lines: `{len((source_only.get('stderr') or '').splitlines())}`",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_reports(payload: dict[str, Any], report_dir: Path) -> dict[str, str]:
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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run multilingual quality checks and emit fixed reports.")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="Directory for JSON/Markdown reports.")
    args = parser.parse_args(argv)

    scripted = _run_check("run_multilingual_text_service_smoke.py")
    source_only = _run_check("run_multilingual_pre_release_source_only_check.py")

    failures = _analyze_scripted_result(scripted) + _analyze_source_only_result(source_only)
    payload = {
        "entrypoint": "run_multilingual_quality_checks",
        "report_schema_version": "1.0",
        "generated_at": _timestamp(),
        "checks": {
            "scripted_multilingual_text_service_smoke": scripted,
            "multilingual_pre_release_source_only": source_only,
        },
        "failure_summary": failures,
        "suggested_actions": _unique_suggestions(failures),
    }
    payload["summary"] = _build_summary(scripted, source_only, failures)
    payload["status"] = payload["summary"]["latest_status"]
    payload["report_paths"] = _write_reports(payload, Path(args.report_dir))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
