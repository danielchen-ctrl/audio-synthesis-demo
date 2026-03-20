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
        "language": "Japanese",
        "scenario": "meeting",
        "title": "pre_release_japanese_meeting",
        "core_content": "requirements clarification; rollback owner assigned; acceptance gate explicit; monitoring thresholds finalized; action items mapped to owners",
        "must_contain": [],
        "must_not_contain": [
            "Hello,",
            "Let's discuss your situation",
            "Could you provide more details",
            "Please note that there are risks involved",
            "To add, regarding",
        ],
        "must_from_v2": True,
        "voice_prefix": "ja-JP",
    },
    {
        "language": "Korean",
        "scenario": "review",
        "title": "pre_release_korean_review",
        "core_content": "architecture review; rollback evidence; acceptance gate; technical review attendance; stress report due before integration testing",
        "must_contain": [],
        "must_not_contain": [
            "Hello,",
            "Let's discuss your situation",
            "Could you provide more details",
            "Please note that there are risks involved",
            "To add, regarding",
        ],
        "must_from_v2": True,
        "voice_prefix": "ko-KR",
    },
    {
        "language": "French",
        "scenario": "meeting",
        "title": "pre_release_french_meeting",
        "core_content": "requirements clarification; rollback owner assigned; acceptance gate explicit; monitoring thresholds finalized; action items mapped to owners",
        "must_contain": [],
        "must_not_contain": [
            "Hello,",
            "Let's discuss your situation",
            "Could you provide more details",
            "Please note that there are risks involved",
            "To add, regarding",
        ],
        "must_from_v2": True,
        "voice_prefix": "fr-FR",
    },
    {
        "language": "German",
        "scenario": "review",
        "title": "pre_release_german_review",
        "core_content": "architecture review; rollback evidence; acceptance gate; technical review attendance; stress report due before integration testing",
        "must_contain": [],
        "must_not_contain": [
            "Hello,",
            "Let's discuss your situation",
            "Could you provide more details",
            "Please note that there are risks involved",
            "To add, regarding",
        ],
        "must_from_v2": True,
        "voice_prefix": "de-DE",
    },
    {
        "language": "Spanish",
        "scenario": "meeting",
        "title": "pre_release_spanish_meeting",
        "core_content": "requirements clarification; rollback owner assigned; acceptance gate explicit; monitoring thresholds finalized; action items mapped to owners",
        "must_contain": [
            "Quiero sobre todo aclarar",
            "Necesito el umbral exacto y su impacto.",
        ],
        "must_not_contain": [
            "Hello,",
            "Let's discuss your situation",
            "Could you provide more details",
            "Please note that there are risks involved",
            "To add, regarding",
        ],
        "must_from_v2": True,
        "voice_prefix": "es-ES",
    },
    {
        "language": "Portuguese",
        "scenario": "review",
        "title": "pre_release_portuguese_review",
        "core_content": "architecture review; rollback evidence; acceptance gate; technical review attendance; stress report due before integration testing",
        "must_contain": [
            "Quero principalmente esclarecer",
            "Preciso do limite exato e do impacto.",
        ],
        "must_not_contain": [
            "Hello,",
            "Let's discuss your situation",
            "Could you provide more details",
            "Please note that there are risks involved",
            "To add, regarding",
        ],
        "must_from_v2": True,
        "voice_prefix": "pt-BR",
    },
    {
        "language": "Cantonese",
        "scenario": "consultation",
        "title": "pre_release_cantonese_consultation",
        "core_content": "customer asks for trade-offs; owner assigned; monitoring thresholds finalized; rollback checklist published",
        "must_contain": [
            "我哋先討論一下今次 consultation。",
            "我需要具體閾值同影響。",
        ],
        "must_not_contain": [
            "Hello,",
            "Let's discuss your situation",
            "Could you provide more details",
            "先对齐这次",
            "从backend这边看",
            "监控和执行路径是",
        ],
        "must_from_v2": True,
        "voice_prefix": "zh-HK",
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
    results = []
    audio_results = []
    for item in TEXT_PAYLOADS:
        payload = {
            "profile": {"job_function": "backend", "seniority": "senior"},
            "scenario": item["scenario"],
            "title": item["title"],
            "language": item["language"],
            "audio_language": item["language"],
            "people_count": 3,
            "word_count": 700,
            "core_content": item["core_content"],
        }
        response = generate_text(payload, state)
        debug = response.get("debug") or {}
        joined = " ".join(line["text"] for line in (response.get("lines") or []))
        result = {
            "language": item["language"],
            "scenario": item["scenario"],
            "text_ok": bool(response.get("ok")),
            "quality_passed": bool(debug.get("quality_gate", {}).get("passed")),
            "text_backend": debug.get("text_backend"),
            "generator_version": debug.get("generator_version"),
            "from_v2": debug.get("from_v2"),
            "source_v2_fallback": debug.get("source_v2_fallback"),
            "source_fallback_bundle_fallback": debug.get("source_fallback_bundle_fallback"),
            "basename": response.get("basename"),
            "dialogue_id": response.get("dialogue_id"),
        }
        results.append(result)
        _assert(result["text_ok"], f"text generation failed for {item['language']}")
        _assert(result["quality_passed"], f"quality gate failed for {item['language']}")
        _assert(result["text_backend"] == "SourceTextGenerator", f"unexpected text backend for {item['language']}: {result['text_backend']}")
        if item.get("must_from_v2"):
            _assert(bool(result["from_v2"]), f"expected V2 path for {item['language']}")
        _assert(not result["source_v2_fallback"], f"v2 bundle fallback used for {item['language']}")
        _assert(not result["source_fallback_bundle_fallback"], f"text fallback bundle path used for {item['language']}")
        for text in item["must_contain"]:
            _assert(text in joined, f"expected phrase missing for {item['language']}: {text}")
        for text in item["must_not_contain"]:
            _assert(text not in joined, f"unexpected leakage for {item['language']}: {text}")

        audio = await generate_audio({"dialogue_id": result["dialogue_id"], "audio_language": item["language"]}, state)
        voice_map = audio.get("voice_map") or {}
        audio_item = {
            "language": item["language"],
            "audio_ok": bool(audio.get("ok")),
            "audio_backend": audio.get("audio_backend"),
            "audio_engine": audio.get("audio_engine"),
            "segments_exists": Path(audio.get("segments_json_path", "")).exists(),
            "vtt_exists": Path(audio.get("transcript_vtt_path", "")).exists(),
            "voice_map": voice_map,
        }
        audio_results.append(audio_item)
        _assert(audio_item["audio_ok"], f"audio generation failed for {item['language']}")
        _assert(audio_item["audio_backend"] == "SourceAudioGenerator", f"unexpected audio backend for {item['language']}: {audio_item['audio_backend']}")
        _assert(audio_item["audio_engine"] == "source_audio_engine", f"unexpected audio engine for {item['language']}: {audio_item['audio_engine']}")
        _assert(audio_item["segments_exists"], f"segments.json missing for {item['language']}")
        _assert(audio_item["vtt_exists"], f"transcript.vtt missing for {item['language']}")
        _assert(
            bool(voice_map) and all(str(voice).startswith(item["voice_prefix"]) for voice in voice_map.values()),
            f"unexpected voice locale for {item['language']}: {voice_map}",
        )

    print(
        json.dumps(
            {"backends": backends, "results": results, "audio_results": audio_results, "status": "ok"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
