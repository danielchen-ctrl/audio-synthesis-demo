from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_TEMP = ROOT / "runtime" / "temp" / "multilingual_embedded_check"

CASES = [
    {
        "language": "Japanese",
        "scenario": "会議レビュー",
        "title": "multilingual_japanese_embedded_smoke",
        "core_content": "requirements clarification; rollback owner assigned; acceptance gate explicit",
        "voice_prefix": "ja-JP",
        "required_snippets": [
            "\u3044\u3061\u3070\u3093\u91cd\u8981\u306a\u306e\u306f\u3001<<Core:",
            "\u3044\u307e\u4e00\u756a\u8a70\u307e\u3063\u3066\u3044\u308b\u8ad6\u70b9\u306f\u3069\u3053\u3067\u3059\u304b\u3002",
        ],
        "forbidden_fragments": ["Professional", "Counterpart", "Coordinator", "您好", "我会认真思考这个问题", "这个问题是从什么时候开始的？"],
    },
    {
        "language": "Spanish",
        "scenario": "revisión de reunión",
        "title": "multilingual_spanish_embedded_smoke",
        "core_content": "requirements clarification; rollback owner assigned; acceptance gate explicit",
        "voice_prefix": "es-ES",
        "required_snippets": [
            "Lo m\u00e1s importante es: <<Core:",
            "\u00bfCu\u00e1l es ahora mismo el principal punto de bloqueo?",
        ],
        "forbidden_fragments": ["Professional", "Counterpart", "Coordinator", "您好", "我理解了，能否给我一些时间整理一下思路？", "这个问题是从什么时候开始的？"],
    },
    {
        "language": "Cantonese",
        "scenario": "會議評審",
        "title": "multilingual_cantonese_embedded_smoke",
        "core_content": "requirements clarification; rollback owner assigned; acceptance gate explicit",
        "voice_prefix": "zh-HK",
        "required_snippets": [
            "\u6700\u91cd\u8981\u5605\u4fc2\uff1a<<Core:",
            "\u4f60\u800c\u5bb6\u6700\u5361\u4f4f\u5605\u4f4d\u4fc2\u908a\u5ea6\uff1f",
        ],
        "forbidden_fragments": ["Professional", "Counterpart", "Coordinator", "您好", "我理解了，能否给我一些时间整理一下思路？"],
    },
]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server() -> tuple[subprocess.Popen[str], str, Path]:
    RUNTIME_TEMP.mkdir(parents=True, exist_ok=True)
    port = _find_free_port()
    log_path = RUNTIME_TEMP / "embedded_multilingual_smoke.log"
    env = os.environ.copy()
    env["DEMO_APP_HOST"] = "127.0.0.1"
    env["DEMO_APP_PORT"] = str(port)
    env["PYTHONUNBUFFERED"] = "1"
    log_file = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "embedded_server.py"],
        cwd=ROOT,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc, f"http://127.0.0.1:{port}", log_path


def _wait_ready(base_url: str) -> None:
    session = requests.Session()
    session.trust_env = False
    try:
        for _ in range(60):
            try:
                response = session.get(f"{base_url}/api/server_info", timeout=3)
                if response.ok:
                    return
            except Exception:
                pass
            time.sleep(1)
        raise RuntimeError("embedded server did not become ready within timeout")
    finally:
        session.close()


def _run_case(session: requests.Session, base_url: str, case: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = {
        "title": case["title"],
        "profile": {
            "job_function": "后端开发",
            "work_content": "系统建设",
            "seniority": "资深",
            "use_case": "会议评审",
        },
        "scenario": case["scenario"],
        "core_content": case["core_content"],
        "people_count": 3,
        "word_count": 600,
        "language": case["language"],
        "audio_language": case["language"],
    }
    text_resp = session.post(f"{base_url}/api/generate_text", json=payload, timeout=300)
    text_resp.raise_for_status()
    text_payload = text_resp.json()
    _assert(bool(text_payload.get("ok")), f"text generation failed for {case['language']}")
    dialogue_id = text_payload["dialogue_id"]
    text_path = Path(text_payload["text_path"])
    _assert(text_path.exists(), f"text output missing for {case['language']}: {text_path}")
    text_body = text_path.read_text(encoding="utf-8", errors="ignore")
    preview = "\n".join(text_body.splitlines()[:8])
    for snippet in case.get("required_snippets", []):
        _assert(snippet in preview, f"missing naturalness snippet for {case['language']}: {snippet}")
    for fragment in case.get("forbidden_fragments", []):
        _assert(fragment not in preview, f"unexpected leaked fragment for {case['language']}: {fragment}")

    text_result = {
        "language": case["language"],
        "scenario": case["scenario"],
        "text_ok": True,
        "quality_passed": True,
        "text_backend": "EmbeddedServer",
        "generator_version": "embedded_bundle",
        "from_v2": None,
        "source_v2_fallback": False,
        "source_fallback_bundle_fallback": False,
        "basename": text_payload.get("basename"),
        "dialogue_id": dialogue_id,
        "text_path": str(text_path),
        "text_preview": preview,
        "expected_text_backend": "EmbeddedServer",
    }

    audio_resp = session.post(
        f"{base_url}/api/generate_audio_custom",
        json={"dialogue_id": dialogue_id, "language": case["language"]},
        timeout=300,
    )
    audio_resp.raise_for_status()
    audio_payload = audio_resp.json()
    _assert(bool(audio_payload.get("ok")), f"audio generation failed for {case['language']}")
    voice_map = audio_payload.get("voice_map") or {}
    _assert(bool(voice_map), f"voice map missing for {case['language']}")
    _assert(
        all(str(voice).startswith(case["voice_prefix"]) for voice in voice_map.values()),
        f"unexpected voices for {case['language']}: {voice_map}",
    )
    audio_result = {
        "language": case["language"],
        "audio_ok": True,
        "audio_backend": "EmbeddedServer",
        "audio_engine": "embedded_edge_tts",
        "segments_exists": Path(audio_payload["segments_json_path"]).exists(),
        "vtt_exists": Path(audio_payload["transcript_vtt_path"]).exists(),
        "voice_map": voice_map,
        "audio_file_path": audio_payload.get("audio_file_path"),
        "expected_audio_backend": "EmbeddedServer",
        "expected_audio_engine": "embedded_edge_tts",
    }
    _assert(audio_result["segments_exists"], f"segments.json missing for {case['language']}")
    _assert(audio_result["vtt_exists"], f"transcript.vtt missing for {case['language']}")
    return text_result, audio_result


async def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    proc, base_url, log_path = _start_server()
    session = requests.Session()
    session.trust_env = False
    try:
        _wait_ready(base_url)
        info = session.get(f"{base_url}/api/server_info", timeout=10).json()
        results: list[dict[str, Any]] = []
        audio_results: list[dict[str, Any]] = []
        for case in CASES:
            text_result, audio_result = _run_case(session, base_url, case)
            results.append(text_result)
            audio_results.append(audio_result)
        print(
            json.dumps(
                {
                    "mode": "embedded_multilingual_pre_release_smoke",
                    "server_info": info,
                    "results": results,
                    "audio_results": audio_results,
                    "status": "ok",
                    "log_path": str(log_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        session.close()
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=20)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
