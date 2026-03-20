from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enforce multilingual quality gate from a generated report.")
    parser.add_argument(
        "--report",
        default=str(Path("reports") / "multilingual_quality_checks" / "latest.json"),
        help="Path to the generated multilingual quality report.",
    )
    parser.add_argument(
        "--max-age-hours",
        type=int,
        default=24,
        help="Reject reports older than this many hours.",
    )
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    _assert(report_path.exists(), f"report not found: {report_path}")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    generated_at = payload.get("generated_at")
    _assert(isinstance(generated_at, str) and generated_at, "report missing generated_at")
    age = datetime.now() - datetime.fromisoformat(generated_at)
    _assert(age <= timedelta(hours=args.max_age_hours), f"report is older than {args.max_age_hours} hours: {generated_at}")

    _assert(payload.get("status") == "ok", "top-level status is not ok")
    scripted = payload.get("checks", {}).get("scripted_multilingual_text_service_smoke", {})
    source_only = payload.get("checks", {}).get("multilingual_pre_release_source_only", {})
    _assert(scripted.get("status") == "ok", "scripted multilingual smoke failed")
    _assert(source_only.get("status") == "ok", "source-only multilingual regression failed")

    for item in scripted.get("results", []):
        _assert(bool(item.get("ok")), f"scripted text generation failed for {item.get('language')}")
        _assert(bool(item.get("quality_passed")), f"scripted quality gate failed for {item.get('language')}")

    for item in source_only.get("results", []):
        _assert(bool(item.get("text_ok")), f"text generation failed for {item.get('language')}")
        _assert(bool(item.get("quality_passed")), f"quality gate failed for {item.get('language')}")
        _assert(item.get("text_backend") == "SourceTextGenerator", f"unexpected text backend for {item.get('language')}: {item.get('text_backend')}")
        _assert(not item.get("source_v2_fallback"), f"source V2 fallback used for {item.get('language')}")
        _assert(not item.get("source_fallback_bundle_fallback"), f"text bundle fallback used for {item.get('language')}")

    for item in source_only.get("audio_results", []):
        _assert(bool(item.get("audio_ok")), f"audio generation failed for {item.get('language')}")
        _assert(item.get("audio_backend") == "SourceAudioGenerator", f"unexpected audio backend for {item.get('language')}: {item.get('audio_backend')}")
        _assert(item.get("audio_engine") == "source_audio_engine", f"unexpected audio engine for {item.get('language')}: {item.get('audio_engine')}")
        _assert(bool(item.get("segments_exists")), f"segments.json missing for {item.get('language')}")
        _assert(bool(item.get("vtt_exists")), f"transcript.vtt missing for {item.get('language')}")

    print(json.dumps({"status": "ok", "report": str(report_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
