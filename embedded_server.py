#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import json
import mimetypes
import os
import re
import shutil
import socket
import sys
import tempfile
import urllib.parse
from importlib._bootstrap_external import _code_to_timestamp_pyc
from pathlib import Path
from typing import Any

import edge_tts
from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.loader.pyimod01_archive import PYZ_ITEM_MODULE, PYZ_ITEM_PKG
from tornado.web import HTTPError, RequestHandler


ROOT = Path(__file__).resolve().parent
RUNTIME_CACHE = ROOT / "runtime" / "cache" / "embedded_bundle"
MODULE_CACHE = RUNTIME_CACHE / "modules"
ASSET_CACHE = RUNTIME_CACHE / "assets"
META_FILE = RUNTIME_CACHE / "extract_meta.json"
LOCAL_STATIC_DIR = ROOT / "static"

SERVER_ARCHIVE = ROOT / "build" / "demo_app" / "SceneDialogueDemo.exe"
ASSET_ARCHIVE = ROOT / "build" / "DialogDemo" / "DialogDemo.pkg"

SELECTED_MODULES = [
    "app",
    "server",
    "resource_path_utils",
    "dialogue_distinctness_guard",
    "dialogue_generator_v2",
    "dialogue_intelligence_engine",
    "dialogue_placeholder_checker",
    "dialogue_review_expander",
    "industry_template_loader",
]

_BUNDLE_SERVER: Any | None = None

VOICE_CATALOG = {
    "Chinese": ["zh-CN-YunxiNeural", "zh-CN-XiaoxiaoNeural", "zh-CN-YunyangNeural", "zh-CN-XiaoyiNeural"],
    "English": ["en-US-GuyNeural", "en-US-JennyNeural", "en-US-DavisNeural"],
    "Japanese": ["ja-JP-NanamiNeural", "ja-JP-KeitaNeural"],
    "Korean": ["ko-KR-SunHiNeural", "ko-KR-InJoonNeural"],
    "French": ["fr-FR-DeniseNeural", "fr-FR-HenriNeural"],
    "German": ["de-DE-KatjaNeural", "de-DE-ConradNeural"],
    "Spanish": ["es-ES-ElviraNeural", "es-ES-AlvaroNeural"],
    "Portuguese": ["pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"],
    "Cantonese": ["zh-HK-HiuGaaiNeural", "zh-HK-WanLungNeural", "zh-HK-HiuMaanNeural"],
}


def active_static_dir() -> Path:
    if (LOCAL_STATIC_DIR / "index.html").exists() and (LOCAL_STATIC_DIR / "app.js").exists():
        return LOCAL_STATIC_DIR
    return ASSET_CACHE / "static"


def _canonical_language(value: str) -> str:
    mapping = {
        "中文": "Chinese",
        "Chinese": "Chinese",
        "英文": "English",
        "English": "English",
        "日语": "Japanese",
        "Japanese": "Japanese",
        "韩语": "Korean",
        "Korean": "Korean",
        "法语": "French",
        "French": "French",
        "德语": "German",
        "German": "German",
        "西班牙语": "Spanish",
        "Spanish": "Spanish",
        "葡萄牙语": "Portuguese",
        "Portuguese": "Portuguese",
        "粤语": "Cantonese",
        "Cantonese": "Cantonese",
    }
    return mapping.get(str(value).strip(), "Chinese")


def _speaker_numeric_id(speaker_label: str) -> int:
    match = re.search(r"(\d+)", speaker_label)
    return int(match.group(1)) if match else 1


def _voice_for_speaker(language: str, speaker_label: str) -> str:
    voices = VOICE_CATALOG.get(_canonical_language(language), VOICE_CATALOG["Chinese"])
    speaker_id = _speaker_numeric_id(speaker_label)
    return voices[(speaker_id - 1) % len(voices)]


def _ffmpeg_path() -> str | None:
    candidate = ROOT / "bin" / "ffmpeg.exe"
    return str(candidate) if candidate.exists() else None


def _meta_payload() -> dict[str, Any]:
    return {
        "server_archive": str(SERVER_ARCHIVE),
        "server_mtime": SERVER_ARCHIVE.stat().st_mtime if SERVER_ARCHIVE.exists() else None,
        "asset_archive": str(ASSET_ARCHIVE),
        "asset_mtime": ASSET_ARCHIVE.stat().st_mtime if ASSET_ARCHIVE.exists() else None,
        "modules": SELECTED_MODULES,
    }


def _cache_is_fresh() -> bool:
    if not META_FILE.exists():
        return False
    if not SERVER_ARCHIVE.exists() or not ASSET_ARCHIVE.exists():
        return False
    try:
        saved = json.loads(META_FILE.read_text(encoding="utf-8"))
    except Exception:
        return False
    current = _meta_payload()
    if saved != current:
        return False
    if not (MODULE_CACHE / "server.pyc").exists():
        return False
    if not (ASSET_CACHE / "static" / "index.html").exists():
        return False
    if not (ASSET_CACHE / "static" / "app.js").exists():
        return False
    return True


def _local_ipv4_candidates() -> list[str]:
    candidates = {"127.0.0.1", "localhost"}
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                candidates.add(ip)
    except Exception:
        pass
    return sorted(candidates, key=lambda item: (item == "localhost", item))


def local_urls(port: int) -> list[str]:
    urls = []
    for host in _local_ipv4_candidates():
        if host == "localhost":
            urls.append(f"http://localhost:{port}/")
        else:
            urls.append(f"http://{host}:{port}/")
    return urls


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _find_manifest(dialogue_id: str) -> tuple[Path, dict[str, Any]]:
    manifests = sorted((ROOT / "demo").glob("*/manifest.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for manifest_path in manifests:
        try:
            manifest = _read_json(manifest_path)
        except Exception:
            continue
        if manifest.get("dialogue_id") == dialogue_id:
            return manifest_path, manifest
    raise FileNotFoundError(f"dialogue_id not found: {dialogue_id}")


def _dialogue_lines_from_text(dialogue_text: str) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    current_speaker = ""
    current_text = ""

    for idx, raw_line in enumerate(dialogue_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^(Speaker\s*\d+)\s*[:：]\s*(.+)$", line, flags=re.IGNORECASE)
        if match:
            if current_speaker and current_text:
                lines.append((current_speaker, current_text.strip()))
            current_speaker = match.group(1).replace("  ", " ").title()
            current_text = match.group(2).strip()
            continue
        if current_speaker:
            current_text = f"{current_text} {line}".strip()
            continue
        raise ValueError(f"第 {idx} 行格式无效，必须以 'Speaker N:' 开头")

    if current_speaker and current_text:
        lines.append((current_speaker, current_text.strip()))

    if not lines:
        raise ValueError("未解析出有效对话行，请按 'Speaker 1: 内容' 的格式编辑")

    return lines


def _render_dialogue_text(bundle_server: Any, lines: list[tuple[str, str]]) -> str:
    return bundle_server._render_dialogue_text(lines)


def _normalize_lines(bundle_server: Any, lines: list[tuple[str, str]]) -> list[dict[str, Any]]:
    return bundle_server._normalize_dialogue_lines(lines)


def _save_dialogue_edit(bundle_server: Any, dialogue_id: str, dialogue_text: str) -> dict[str, Any]:
    manifest_path, manifest = _find_manifest(dialogue_id)
    save_dir = Path(manifest.get("save_dir") or manifest_path.parent)
    save_dir.mkdir(parents=True, exist_ok=True)

    lines = _dialogue_lines_from_text(dialogue_text)
    rendered_text = _render_dialogue_text(bundle_server, lines)
    text_path = Path(manifest.get("text_path") or save_dir / f"{manifest.get('basename', dialogue_id)}.txt")
    text_path.write_text(rendered_text, encoding="utf-8")

    manifest["text_path"] = str(text_path)
    manifest["edited_text"] = True
    manifest["edited_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    _write_json(manifest_path, manifest)

    return {
        "dialogue_id": dialogue_id,
        "manifest_path": str(manifest_path),
        "save_dir": str(save_dir),
        "text_path": str(text_path),
        "dialogue_text": rendered_text,
        "lines": _normalize_lines(bundle_server, lines),
        "manifest": manifest,
        "line_tuples": lines,
    }


def _latest_audio_path(save_dir: Path, basename: str) -> Path | None:
    candidates = []
    for suffix in (".mp3", ".wav"):
        path = save_dir / f"{basename}{suffix}"
        if path.exists():
            candidates.append(path)
    if candidates:
        return sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)[0]
    any_audio = sorted(save_dir.glob("*.mp3")) + sorted(save_dir.glob("*.wav"))
    if any_audio:
        return sorted(any_audio, key=lambda item: item.stat().st_mtime, reverse=True)[0]
    return None


def _download_url(dialogue_id: str, kind: str) -> str:
    return f"/api/download?dialogue_id={dialogue_id}&kind={kind}"


def _format_vtt_ts(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3_600_000
    total_ms %= 3_600_000
    minutes = total_ms // 60_000
    total_ms %= 60_000
    secs = total_ms // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


async def _synthesize_audio_from_lines(
    lines: list[tuple[str, str]],
    language: str,
    save_dir: Path,
    basename: str,
    bundle_server: Any,
) -> dict[str, Any]:
    from pydub import AudioSegment

    ffmpeg = _ffmpeg_path()
    if ffmpeg:
        AudioSegment.converter = ffmpeg

    tmp_dir = save_dir / "_edited_tts_tmp"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    combined = AudioSegment.silent(duration=120)
    segments: list[dict[str, Any]] = []
    voice_map: dict[str, str] = {}
    debug_lines: list[str] = []
    cursor_sec = 0.12

    warning_message = None
    try:
        for idx, (speaker, text) in enumerate(lines, start=1):
            cleaned = text.strip()
            if not cleaned:
                continue
            voice = _voice_for_speaker(language, speaker)
            speaker_id = str(_speaker_numeric_id(speaker))
            voice_map[speaker_id] = voice
            segment_file = tmp_dir / f"line_{idx:03d}.mp3"
            communicate = edge_tts.Communicate(cleaned, voice)
            await communicate.save(str(segment_file))

            audio = AudioSegment.from_file(segment_file)
            start_sec = cursor_sec
            duration_sec = len(audio) / 1000.0
            end_sec = start_sec + duration_sec
            segments.append(
                {
                    "speaker": speaker,
                    "start_sec": round(start_sec, 3),
                    "end_sec": round(end_sec, 3),
                    "text": cleaned,
                    "voice": voice,
                    "line_index": idx - 1,
                }
            )
            debug_lines.append(f"{speaker}\t{voice}\t{cleaned}")
            combined += audio + AudioSegment.silent(duration=220)
            cursor_sec = end_sec + 0.22

        wav_path = save_dir / f"{basename}.wav"
        mp3_path = save_dir / f"{basename}.mp3"
        combined.export(wav_path, format="wav")
        combined.export(mp3_path, format="mp3")

        segments_path = save_dir / "segments.json"
        _write_json(segments_path, {"segments": segments, "language": _canonical_language(language)})

        vtt_path = save_dir / "transcript.vtt"
        vtt_lines = ["WEBVTT", ""]
        for idx, item in enumerate(segments, start=1):
            vtt_lines.append(str(idx))
            vtt_lines.append(f"{_format_vtt_ts(item['start_sec'])} --> {_format_vtt_ts(item['end_sec'])}")
            vtt_lines.append(f"{item['speaker']}: {item['text']}")
            vtt_lines.append("")
        vtt_path.write_text("\n".join(vtt_lines), encoding="utf-8")

        debug_path = save_dir / "tts_input_debug.txt"
        debug_path.write_text("\n".join(debug_lines), encoding="utf-8")

        return {
            "audio_file_path": str(mp3_path),
            "mp3_path": str(mp3_path),
            "wav_path": str(wav_path),
            "voice_map": voice_map,
            "segments_json_path": str(segments_path),
            "transcript_vtt_path": str(vtt_path),
            "tts_debug_file": str(debug_path),
            "warning": warning_message,
        }
    except Exception as exc:
        warning_message = f"edge_tts_fallback:{type(exc).__name__}:{exc}"
        wav_path = save_dir / f"{basename}.wav"
        mp3_path = save_dir / f"{basename}.mp3"
        audio = bundle_server._generate_wave_for_lines(lines)
        bundle_server._write_wav(audio, wav_path)
        AudioSegment.from_wav(wav_path).export(mp3_path, format="mp3")

        segments: list[dict[str, Any]] = []
        cursor_sec = 0.0
        for idx, (speaker, text) in enumerate(lines, start=1):
            duration = max(1.2, min(6.0, len(text) / 8.0))
            segments.append(
                {
                    "speaker": speaker,
                    "start_sec": round(cursor_sec, 3),
                    "end_sec": round(cursor_sec + duration, 3),
                    "text": text,
                    "voice": "synthetic_fallback",
                    "line_index": idx - 1,
                }
            )
            cursor_sec += duration

        segments_path = save_dir / "segments.json"
        _write_json(segments_path, {"segments": segments, "language": _canonical_language(language)})

        vtt_path = save_dir / "transcript.vtt"
        vtt_lines = ["WEBVTT", ""]
        for idx, item in enumerate(segments, start=1):
            vtt_lines.append(str(idx))
            vtt_lines.append(f"{_format_vtt_ts(item['start_sec'])} --> {_format_vtt_ts(item['end_sec'])}")
            vtt_lines.append(f"{item['speaker']}: {item['text']}")
            vtt_lines.append("")
        vtt_path.write_text("\n".join(vtt_lines), encoding="utf-8")

        debug_path = save_dir / "tts_input_debug.txt"
        debug_path.write_text("\n".join([f"{speaker}\tsynthetic_fallback\t{text}" for speaker, text in lines]), encoding="utf-8")

        return {
            "audio_file_path": str(mp3_path),
            "mp3_path": str(mp3_path),
            "wav_path": str(wav_path),
            "voice_map": {},
            "segments_json_path": str(segments_path),
            "transcript_vtt_path": str(vtt_path),
            "tts_debug_file": str(debug_path),
            "warning": warning_message,
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


class JsonHandler(RequestHandler):
    def set_default_headers(self) -> None:
        self.set_header("Content-Type", "application/json; charset=utf-8")

    def write_json(self, payload: dict[str, Any], status: int = 200) -> None:
        self.set_status(status)
        self.finish(json.dumps(payload, ensure_ascii=False))

    def read_json(self) -> dict[str, Any]:
        try:
            return json.loads(self.request.body.decode("utf-8") or "{}")
        except Exception as exc:
            raise HTTPError(400, reason=f"Invalid JSON body: {exc}") from exc


class ServerInfoHandler(JsonHandler):
    def get(self) -> None:
        port = self.request.connection.stream.socket.getsockname()[1]
        self.write_json(
            {
                "ok": True,
                "listen_host": os.environ.get("DEMO_APP_HOST", "0.0.0.0"),
                "port": port,
                "local_urls": local_urls(port),
                "share_hint": "同一局域网内的其他电脑可通过上面的 IP 地址访问。如果访问失败，先放行 Windows 防火墙的 8899 端口。",
            }
        )


class UpdateDialogueHandler(JsonHandler):
    def post(self) -> None:
        payload = self.read_json()
        dialogue_id = str(payload.get("dialogue_id", "")).strip()
        dialogue_text = str(payload.get("dialogue_text", "")).strip()
        if not dialogue_id:
            raise HTTPError(400, reason="dialogue_id is required")
        if not dialogue_text:
            raise HTTPError(400, reason="dialogue_text is required")

        bundle_server = load_bundle_server()
        result = _save_dialogue_edit(bundle_server, dialogue_id, dialogue_text)
        self.write_json(
            {
                "ok": True,
                "dialogue_id": dialogue_id,
                "text_path": result["text_path"],
                "dialogue_text": result["dialogue_text"],
                "lines": result["lines"],
                "text_download_url": _download_url(dialogue_id, "text"),
            }
        )


class GenerateAudioCustomHandler(JsonHandler):
    async def post(self) -> None:
        payload = self.read_json()
        dialogue_id = str(payload.get("dialogue_id", "")).strip()
        if not dialogue_id:
            raise HTTPError(400, reason="dialogue_id is required")

        bundle_server = load_bundle_server()
        dialogue_text = str(payload.get("dialogue_text", "")).strip()
        if dialogue_text:
            result = _save_dialogue_edit(bundle_server, dialogue_id, dialogue_text)
            manifest = result["manifest"]
            line_tuples = result["line_tuples"]
            save_dir = Path(result["save_dir"])
        else:
            manifest_path, manifest = _find_manifest(dialogue_id)
            save_dir = Path(manifest.get("save_dir") or manifest_path.parent)
            text_path = Path(manifest["text_path"])
            line_tuples = _dialogue_lines_from_text(text_path.read_text(encoding="utf-8"))

        basename = manifest.get("basename", dialogue_id)
        language = str(payload.get("language") or manifest.get("audio_language") or "中文")
        audio_result = await _synthesize_audio_from_lines(line_tuples, language, save_dir, basename, bundle_server)

        audio_file = audio_result["audio_file_path"]
        manifest["audio_path"] = audio_file
        manifest["voice_map"] = audio_result["voice_map"]
        manifest["audio_language"] = language
        manifest["audio_warning"] = audio_result["warning"]
        manifest["segments_json_path"] = audio_result["segments_json_path"]
        manifest["transcript_vtt_path"] = audio_result["transcript_vtt_path"]
        _write_json(Path(manifest.get("save_dir") or save_dir) / "manifest.json", manifest)

        self.write_json(
            {
                "ok": True,
                "dialogue_id": dialogue_id,
                "audio_file_path": audio_file,
                "mp3_path": audio_result["mp3_path"],
                "wav_path": audio_result["wav_path"],
                "voice_map": audio_result["voice_map"],
                "warning": audio_result["warning"],
                "tts_debug_file": audio_result["tts_debug_file"],
                "segments_json_path": audio_result["segments_json_path"],
                "transcript_vtt_path": audio_result["transcript_vtt_path"],
                "audio_download_url": _download_url(dialogue_id, "audio"),
            }
        )


class DownloadHandler(RequestHandler):
    def get(self) -> None:
        dialogue_id = self.get_query_argument("dialogue_id", "").strip()
        kind = self.get_query_argument("kind", "").strip().lower()
        if not dialogue_id:
            raise HTTPError(400, reason="dialogue_id is required")
        if kind not in {"text", "audio"}:
            raise HTTPError(400, reason="kind must be text or audio")

        _, manifest = _find_manifest(dialogue_id)
        save_dir = Path(manifest.get("save_dir") or ROOT / "demo")

        if kind == "text":
            target = Path(manifest["text_path"])
        else:
            target = None
            audio_path = manifest.get("audio_path")
            if audio_path:
                audio_candidate = Path(audio_path)
                if audio_candidate.exists():
                    target = audio_candidate
            if target is None:
                target = _latest_audio_path(save_dir, manifest.get("basename", dialogue_id))

        if target is None or not target.exists():
            raise HTTPError(404, reason=f"{kind} file not found")

        content_type, _ = mimetypes.guess_type(target.name)
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", target.name)
        quoted_name = urllib.parse.quote(target.name)
        self.set_header("Content-Type", content_type or "application/octet-stream")
        self.set_header(
            "Content-Disposition",
            f"attachment; filename=\"{safe_name}\"; filename*=UTF-8''{quoted_name}",
        )
        self.write(target.read_bytes())


def _reset_cache() -> None:
    if RUNTIME_CACHE.exists():
        shutil.rmtree(RUNTIME_CACHE)
    MODULE_CACHE.mkdir(parents=True, exist_ok=True)
    ASSET_CACHE.mkdir(parents=True, exist_ok=True)


def _extract_bundle_modules() -> None:
    archive = CArchiveReader(str(SERVER_ARCHIVE))
    pyz = archive.open_embedded_archive("PYZ.pyz")
    for module_name in SELECTED_MODULES:
        if module_name not in pyz.toc:
            raise RuntimeError(f"Embedded module not found: {module_name}")
        typecode = pyz.toc[module_name][0]
        code = pyz.extract(module_name)
        destination = MODULE_CACHE.joinpath(*module_name.split("."))
        if typecode == PYZ_ITEM_PKG:
            destination = destination / "__init__.pyc"
        elif typecode == PYZ_ITEM_MODULE:
            destination = destination.with_suffix(".pyc")
        else:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_code_to_timestamp_pyc(code, 0, 0))


def _extract_static_assets() -> None:
    archive = CArchiveReader(str(ASSET_ARCHIVE))
    for name in archive.toc:
        if not name.startswith("static\\"):
            continue
        destination = ASSET_CACHE / name.replace("\\", os.sep)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(archive.extract(name))


def ensure_embedded_runtime() -> None:
    if _cache_is_fresh():
        return
    if not SERVER_ARCHIVE.exists():
        raise FileNotFoundError(f"Missing server archive: {SERVER_ARCHIVE}")
    if not ASSET_ARCHIVE.exists():
        raise FileNotFoundError(f"Missing asset archive: {ASSET_ARCHIVE}")
    _reset_cache()
    _extract_bundle_modules()
    _extract_static_assets()
    META_FILE.write_text(
        json.dumps(_meta_payload(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_bundle_server():
    global _BUNDLE_SERVER
    if _BUNDLE_SERVER is not None:
        return _BUNDLE_SERVER

    ensure_embedded_runtime()

    module_path = MODULE_CACHE / "server.pyc"
    if str(MODULE_CACHE) not in sys.path:
        sys.path.insert(0, str(MODULE_CACHE))

    spec = importlib.util.spec_from_file_location(
        "_demo_embedded_bundle_server",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to create module spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.PROJECT_ROOT = ROOT
    module.STATIC_DIR = active_static_dir()
    module.DEMO_DIR = ROOT / "demo"
    module.DEMO_DIR.mkdir(parents=True, exist_ok=True)

    _BUNDLE_SERVER = module
    return module


def make_app():
    module = load_bundle_server()
    module.PROJECT_ROOT = ROOT
    module.STATIC_DIR = active_static_dir()
    module.DEMO_DIR = ROOT / "demo"
    module.DEMO_DIR.mkdir(parents=True, exist_ok=True)
    app = module.make_app()
    app.add_handlers(
        r".*$",
        [
            (r"/api/server_info", ServerInfoHandler),
            (r"/api/update_dialogue", UpdateDialogueHandler),
            (r"/api/generate_audio_custom", GenerateAudioCustomHandler),
            (r"/api/download", DownloadHandler),
        ],
    )
    return app


def main() -> None:
    import tornado.ioloop

    host = os.environ.get("DEMO_APP_HOST", "0.0.0.0")
    port = int(os.environ.get("DEMO_APP_PORT") or os.environ.get("AUTOGATE_PORT") or "8899")

    app = make_app()
    app.listen(port, address=host)

    print(f"[START] Demo server is running at http://{host}:{port}/")
    for url in local_urls(port):
        print(f"[START] Access URL: {url}")
    print(f"[START] Static assets: {active_static_dir()}")
    print(f"[START] Output directory: {ROOT / 'demo'}")

    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
