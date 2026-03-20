from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_app.app_state import AppState
from demo_app.audio_service import generate_audio
from demo_app.configuration import clear_config_cache, get_config_section
from demo_app.text_service import generate_text


TEXT_PAYLOADS = [
    {
        "profile": {"job_function": "backend", "seniority": "senior"},
        "scenario": "meeting",
        "title": "pre_release_meeting",
        "language": "English",
        "audio_language": "English",
        "people_count": 3,
        "word_count": 700,
        "core_content": "requirements clarification; rollback owner assigned; acceptance gate explicit; monitoring thresholds finalized; action items mapped to owners",
    },
    {
        "profile": {"job_function": "backend", "seniority": "senior"},
        "scenario": "review",
        "title": "pre_release_review",
        "language": "English",
        "audio_language": "English",
        "people_count": 3,
        "word_count": 700,
        "core_content": "architecture review; rollback evidence; acceptance gate; technical review attendance; stress report due before integration testing",
    },
    {
        "profile": {"job_function": "backend", "seniority": "senior"},
        "scenario": "consultation",
        "title": "pre_release_consultation",
        "language": "English",
        "audio_language": "English",
        "people_count": 3,
        "word_count": 700,
        "core_content": "customer asks for trade-offs; owner assigned; monitoring thresholds finalized; rollback checklist published",
    },
]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> int:
    os.environ["DEMO_APP_CONFIG_PROFILE"] = "pre_release"
    clear_config_cache()
    backends = get_config_section("backends")
    _assert(backends.get("text_bundle_fallback") == "disabled", "text bundle fallback must be disabled")
    _assert(backends.get("audio_bundle_fallback") == "disabled", "audio bundle fallback must be disabled")

    state = AppState()
    text_results = []
    for payload in TEXT_PAYLOADS:
        response = generate_text(payload, state)
        debug = response.get("debug") or {}
        item = {
            "scenario": payload["scenario"],
            "text_ok": bool(response.get("ok")),
            "quality_passed": bool(debug.get("quality_gate", {}).get("passed")),
            "text_backend": debug.get("text_backend"),
            "generator_version": debug.get("generator_version"),
            "source_v2_fallback": debug.get("source_v2_fallback"),
            "source_fallback_bundle_fallback": debug.get("source_fallback_bundle_fallback"),
            "dialogue_id": response.get("dialogue_id"),
        }
        text_results.append(item)
        _assert(item["text_ok"], f"text generation failed for {payload['scenario']}")
        _assert(item["quality_passed"], f"quality gate failed for {payload['scenario']}")
        _assert(item["text_backend"] == "SourceTextGenerator", f"unexpected text backend for {payload['scenario']}: {item['text_backend']}")
        _assert(not item["source_v2_fallback"], f"v2 bundle fallback used for {payload['scenario']}")
        _assert(not item["source_fallback_bundle_fallback"], f"text fallback bundle path used for {payload['scenario']}")

    audio_results = []
    for item in text_results[:2]:
        response = await generate_audio({"dialogue_id": item["dialogue_id"], "audio_language": "English"}, state)
        audio_item = {
            "dialogue_id": item["dialogue_id"],
            "audio_ok": bool(response.get("ok")),
            "audio_backend": response.get("audio_backend"),
            "audio_engine": response.get("audio_engine"),
            "segments_exists": Path(response.get("segments_json_path", "")).exists(),
            "vtt_exists": Path(response.get("transcript_vtt_path", "")).exists(),
        }
        audio_results.append(audio_item)
        _assert(audio_item["audio_ok"], f"audio generation failed for {item['dialogue_id']}")
        _assert(audio_item["audio_backend"] == "SourceAudioGenerator", f"unexpected audio backend for {item['dialogue_id']}: {audio_item['audio_backend']}")
        _assert(audio_item["audio_engine"] == "source_audio_engine", f"unexpected audio engine for {item['dialogue_id']}: {audio_item['audio_engine']}")
        _assert(audio_item["segments_exists"], f"segments.json missing for {item['dialogue_id']}")
        _assert(audio_item["vtt_exists"], f"transcript.vtt missing for {item['dialogue_id']}")

    print(
        json.dumps(
            {
                "backends": backends,
                "text_results": text_results,
                "audio_results": audio_results,
                "status": "ok",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
