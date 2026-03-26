#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import json
import mimetypes
import os
import re
import secrets
import shutil
import socket
import sys
import tempfile
import urllib.parse
from datetime import datetime
from importlib._bootstrap_external import _code_to_timestamp_pyc
from pathlib import Path
from typing import Any

import edge_tts
from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.loader.pyimod01_archive import PYZ_ITEM_MODULE, PYZ_ITEM_PKG
from tornado.web import HTTPError, RequestHandler


ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from demo_app.multilingual_naturalness import polish_generated_lines

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
    "Italian": ["it-IT-ElsaNeural", "it-IT-DiegoNeural"],
    "Russian": ["ru-RU-DariyaNeural", "ru-RU-DmitryNeural"],
    "Arabic": ["ar-SA-ZariyahNeural", "ar-SA-HamedNeural"],
    "Indonesian": ["id-ID-GadisNeural", "id-ID-ArdiNeural"],
    "Cantonese": ["zh-HK-HiuGaaiNeural", "zh-HK-WanLungNeural", "zh-HK-HiuMaanNeural"],
}

MAX_AUDIO_TEXT_CHARS = 12000
PRESET_TOPIC_FILE = ROOT / "demo" / "预置对话情景参数.txt"
PRESET_BLOCK_RE = re.compile(r"(?ms)^\s*(\d+)[）\)]\s*(.+?)(?=^\s*\d+[）\)]\s*|\Z)")


def active_static_dir() -> Path:
    if (LOCAL_STATIC_DIR / "index.html").exists() and (LOCAL_STATIC_DIR / "app.js").exists():
        return LOCAL_STATIC_DIR
    return ASSET_CACHE / "static"


def _canonical_language(value: str) -> str:
    mapping = {
        "中文": "Chinese",
        "中文（普通话）": "Chinese",
        "Chinese": "Chinese",
        "zh": "Chinese",
        "英文": "English",
        "英语": "English",
        "English": "English",
        "en": "English",
        "日语": "Japanese",
        "Japanese": "Japanese",
        "ja": "Japanese",
        "韩语": "Korean",
        "Korean": "Korean",
        "ko": "Korean",
        "法语": "French",
        "French": "French",
        "fr": "French",
        "德语": "German",
        "German": "German",
        "de": "German",
        "西班牙语": "Spanish",
        "Spanish": "Spanish",
        "es": "Spanish",
        "葡萄牙语": "Portuguese",
        "Portuguese": "Portuguese",
        "pt": "Portuguese",
        "意大利语": "Italian",
        "Italian": "Italian",
        "it": "Italian",
        "俄语": "Russian",
        "Russian": "Russian",
        "ru": "Russian",
        "阿拉伯语": "Arabic",
        "Arabic": "Arabic",
        "ar": "Arabic",
        "印度尼西亚语": "Indonesian",
        "印尼语": "Indonesian",
        "Indonesian": "Indonesian",
        "id": "Indonesian",
        "粤语": "Cantonese",
        "Cantonese": "Cantonese",
    }
    return mapping.get(str(value).strip(), "Chinese")


def _speaker_numeric_id(speaker_label: str) -> int:
    match = re.search(r"(\d+)", speaker_label)
    return int(match.group(1)) if match else 1


def _voice_for_speaker(language: str, speaker_label: str, selected_voice_map: dict[str, str] | None = None) -> str:
    speaker_id = str(_speaker_numeric_id(speaker_label))
    if selected_voice_map and selected_voice_map.get(speaker_id):
        return str(selected_voice_map[speaker_id])
    voices = VOICE_CATALOG.get(_canonical_language(language), VOICE_CATALOG["Chinese"])
    return voices[(int(speaker_id) - 1) % len(voices)]


def _safe_file_component(value: str, fallback: str = "audio") -> str:
    text = str(value or "").strip()
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._")
    return text or fallback


def _basename_from_title(title: str, timestamp: str, fallback: str = "audio") -> str:
    return f"{_safe_file_component(title, fallback)}_{timestamp}"


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


def _safe_profile(payload: dict[str, Any]) -> dict[str, str]:
    profile = payload.get("profile") or {}
    return {
        "job_function": str(profile.get("job_function") or "unknown_job_function").strip() or "unknown_job_function",
        "work_content": str(profile.get("work_content") or "unknown_work_content").strip() or "unknown_work_content",
        "seniority": str(profile.get("seniority") or "unknown_level").strip() or "unknown_level",
        "use_case": str(profile.get("use_case") or "general_use_case").strip() or "general_use_case",
    }


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        normalized = str(item or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _compact_multiline_text(value: str) -> str:
    cleaned: list[str] = []
    for raw_line in str(value or "").splitlines():
        line = raw_line.strip()
        if not line or line == ">":
            continue
        line = re.sub(r"^<Core[:：]?", "", line).strip()
        line = line.rstrip(">").strip()
        line = re.sub(r"^[\-\*•\d\.、\)\(]+", "", line).strip()
        if line:
            cleaned.append(line)
    return " ".join(cleaned).strip()


def _extract_section(block: str, start_tokens: list[str], stop_tokens: list[str]) -> str:
    start_index = -1
    matched_token = ""
    for token in start_tokens:
        idx = block.find(token)
        if idx != -1 and (start_index == -1 or idx < start_index):
            start_index = idx
            matched_token = token
    if start_index == -1:
        return ""

    section = block[start_index + len(matched_token):]
    if section.startswith(("：", ":")):
        section = section[1:]

    stop_index = len(section)
    for token in stop_tokens:
        idx = section.find(token)
        if idx != -1:
            stop_index = min(stop_index, idx)

    return _compact_multiline_text(section[:stop_index])


def _extract_word_count(block: str) -> int:
    range_match = re.search(r"target_words\s*=\s*(\d+)\s*[~～\-]\s*(\d+)", block, flags=re.IGNORECASE)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        return max(100, int(round((low + high) / 2)))
    single_match = re.search(r"target_words\s*=\s*(\d+)", block, flags=re.IGNORECASE)
    if single_match:
        return max(100, int(single_match.group(1)))
    return 1000


def _guess_template_label(title: str, scenario: str) -> str:
    match = re.search(r"[（(]([^()（）]{1,20})[)）]", title)
    if match:
        return match.group(1).strip()

    combined = f"{title} {scenario}"
    if "问诊" in combined or ("医生" in combined and "病" in combined):
        return "问诊"
    if "战略周会" in combined or "周会" in combined:
        return "战略周会"
    if "访谈" in combined:
        return "访谈"
    if "销售" in combined or "洽谈" in combined or "客户" in combined:
        return "客户访谈"
    if "决策" in combined:
        return "方案决策"
    if "排查" in combined or "异常" in combined:
        return "问题排查"
    if "评审" in combined or "准入" in combined or "Go / No-Go" in combined or "Go/No-Go" in combined:
        return "评审会"
    return "会议讨论"


def _preset_topic_text(title: str) -> str:
    source = title.split("｜", 1)[1].strip() if "｜" in title else title.strip()
    source = re.sub(r"[（(].*?[)）]", "", source).strip() or title.strip()
    return source


def _preset_display_title(topic_text: str) -> str:
    compact = re.sub(r"\s+", "", topic_text)
    return compact[:20] if len(compact) > 20 else compact


def _preset_profile(title: str, topic_text: str, template_label: str) -> dict[str, str]:
    industry = title.split("｜", 1)[0].strip() if "｜" in title else template_label or "在线生成音频"
    return {
        "job_function": industry or template_label or "在线生成音频",
        "work_content": topic_text or template_label or "场景对话",
        "seniority": "资深",
        "use_case": template_label or "会议讨论",
    }


def _load_preset_topics() -> list[dict[str, Any]]:
    if not PRESET_TOPIC_FILE.exists():
        return []

    raw_text = PRESET_TOPIC_FILE.read_text(encoding="utf-8")
    presets: list[dict[str, Any]] = []

    for match in PRESET_BLOCK_RE.finditer(raw_text):
        preset_id = match.group(1)
        block = match.group(2).strip()
        title = next((line.strip() for line in block.splitlines() if line.strip()), "")
        if not title:
            continue

        scenario = _extract_section(
            block,
            ["场景对话设置（升级版）", "场景对话设置"],
            ["对话生成参数", "**参数", "参数：", "参数:", "对话核心内容", "核心内容", "全新情景对话", "全新对话", "对话节选"],
        )
        core_content = _extract_section(
            block,
            ["对话核心内容（红色标注）", "对话核心内容", "核心内容"],
            ["全新情景对话", "全新对话", "对话节选", "Action Items"],
        )
        topic_text = _preset_topic_text(title)
        template_label = _guess_template_label(title, scenario)
        people_match = re.search(r"people_count\s*=\s*(\d+)", block, flags=re.IGNORECASE)
        language_match = re.search(r"language\s*=\s*([^\s｜|]+)", block, flags=re.IGNORECASE)

        presets.append(
            {
                "id": preset_id,
                "source_title": title,
                "topic_text": topic_text,
                "display_title": _preset_display_title(topic_text),
                "scenario": scenario or topic_text,
                "core_content": core_content,
                "template_label": template_label,
                "people_count": max(2, min(10, _safe_int(people_match.group(1) if people_match else None, 3))),
                "word_count": min(3000, max(100, _extract_word_count(block))),
                "language": _canonical_language(language_match.group(1) if language_match else "Chinese"),
                "profile": _preset_profile(title, topic_text, template_label),
            }
        )

    return presets


def _keyword_in_text(text: str, keyword: str) -> bool:
    return keyword.casefold() in text.casefold()


def _enforce_keywords_in_lines(lines: list[tuple[str, str]], keywords: list[str], language: str) -> tuple[list[tuple[str, str]], list[str]]:
    normalized_keywords = [item.strip() for item in keywords if item and item.strip()]
    if not normalized_keywords:
        return lines, []

    rendered_text = "\n".join(f"{speaker}: {content}" for speaker, content in lines)
    missing_keywords = [keyword for keyword in normalized_keywords if not _keyword_in_text(rendered_text, keyword)]
    if not missing_keywords:
        return lines, []

    speaker_label = lines[0][0] if lines else "Speaker 1"
    canonical_language = _canonical_language(language)
    if canonical_language == "English":
        appended_text = f"We also need to explicitly cover these keywords: {', '.join(missing_keywords)}."
    else:
        appended_text = f"我们这次讨论还需要明确提到这些关键词：{'、'.join(missing_keywords)}。"
    return [*lines, (speaker_label, appended_text)], missing_keywords


def _new_dialogue_id() -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


def _generate_text_payload(bundle_server: Any, payload: dict[str, Any]) -> dict[str, Any]:
    profile = _safe_profile(payload)
    scenario = str(payload.get("scenario") or "").strip()
    core_content = str(payload.get("core_content") or "").strip()
    people_count = max(2, min(10, _safe_int(payload.get("people_count"), 3)))
    word_count = min(3000, max(100, _safe_int(payload.get("word_count"), 1000)))
    language = _canonical_language(str(payload.get("audio_language") or payload.get("language") or "Chinese"))
    title = str(payload.get("title") or f"{profile['job_function']}_{profile['seniority']}").strip()
    template_label = str(payload.get("template_label") or "").strip()
    tags = payload.get("tags") or []
    keyword_terms = _safe_str_list(payload.get("keyword_terms"))
    folder = str(payload.get("folder") or "默认目录").strip() or "默认目录"

    lines, rewrite_info = bundle_server._generate_dialogue_lines(
        profile,
        scenario,
        core_content,
        people_count,
        word_count,
        language,
    )
    lines, injected_keywords = _enforce_keywords_in_lines(lines, keyword_terms, language)
    dialogue_text = _render_dialogue_text(bundle_server, lines)
    normalized_lines = _normalize_lines(bundle_server, lines)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dialogue_id = _new_dialogue_id()
    basename = _basename_from_title(title, timestamp, bundle_server.generate_basename(profile, language, timestamp))
    save_dir = ROOT / "demo" / timestamp
    save_dir.mkdir(parents=True, exist_ok=True)
    text_path = save_dir / f"{basename}.txt"
    text_path.write_text(dialogue_text, encoding="utf-8")
    updated_at = datetime.now().isoformat(timespec="seconds")

    manifest = {
        "dialogue_id": dialogue_id,
        "timestamp": timestamp,
        "basename": basename,
        "title": title,
        "scenario": scenario,
        "core_content": core_content,
        "profile": profile,
        "people_count": people_count,
        "word_count": word_count,
        "audio_language": language,
        "template_label": template_label,
        "tags": tags,
        "keyword_terms": keyword_terms,
        "folder": folder,
        "source_mode": str(payload.get("source_mode") or "llm").strip() or "llm",
        "save_dir": str(save_dir),
        "text_path": str(text_path),
        "text_updated_at": updated_at,
        "audio_path": "",
        "voice_map": {},
        "edited_text": False,
    }
    _write_json(save_dir / "manifest.json", manifest)

    debug_payload = {
        "generator_version": "embedded_server.generate_text/v2",
        "naturalness_applied": bool((rewrite_info or {}).get("naturalness_applied")),
        "naturalness_language": (rewrite_info or {}).get("naturalness_language"),
        "naturalness_rewrites": (rewrite_info or {}).get("naturalness_rewrites", 0),
        "from_v2": (rewrite_info or {}).get("from_v2"),
        "is_from_v2": (rewrite_info or {}).get("is_from_v2"),
        "source_v2_fallback": (rewrite_info or {}).get("source_v2_fallback"),
        "param_debug": {
            "normalized_echo": {
                "scenario": scenario,
                "core_content": core_content,
                "people_count": people_count,
                "word_count": word_count,
                "audio_language": language,
                "profile": profile,
                "keyword_terms": keyword_terms,
            }
        },
        "keywords_enforced": injected_keywords,
        "raw_rewrite_info": rewrite_info or {},
    }

    return {
        "ok": True,
        "success": True,
        "dialogue_id": dialogue_id,
        "timestamp": timestamp,
        "basename": basename,
        "text_path": str(text_path),
        "file_name": text_path.name,
        "updated_at": updated_at,
        "dialogue_text": dialogue_text,
        "text": dialogue_text,
        "lines": normalized_lines,
        "debug": debug_payload,
        "debug_info": debug_payload,
        "text_download_url": _download_url(dialogue_id, "text"),
    }


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


def _normalize_dialogue_text_for_storage(dialogue_text: str) -> str:
    normalized = str(dialogue_text or "").replace("\r\n", "\n").strip()
    if not normalized:
        raise ValueError("当前对话文本为空，无法保存")
    return normalized


def _render_dialogue_text(bundle_server: Any, lines: list[tuple[str, str]]) -> str:
    return bundle_server._render_dialogue_text(lines)


def _normalize_lines(bundle_server: Any, lines: list[tuple[str, str]]) -> list[dict[str, Any]]:
    return bundle_server._normalize_dialogue_lines(lines)


def _save_dialogue_edit(bundle_server: Any, dialogue_id: str, dialogue_text: str) -> dict[str, Any]:
    manifest_path, manifest = _find_manifest(dialogue_id)
    save_dir = Path(manifest.get("save_dir") or manifest_path.parent)
    save_dir.mkdir(parents=True, exist_ok=True)

    rendered_text = _normalize_dialogue_text_for_storage(dialogue_text)
    text_path = Path(manifest.get("text_path") or save_dir / f"{manifest.get('basename', dialogue_id)}.txt")
    text_path.write_text(rendered_text, encoding="utf-8")
    updated_at = datetime.now().isoformat(timespec="seconds")

    manifest["text_path"] = str(text_path)
    manifest["edited_text"] = True
    manifest["edited_at"] = updated_at
    manifest["text_updated_at"] = updated_at
    _write_json(manifest_path, manifest)

    try:
        line_tuples = _dialogue_lines_from_text(rendered_text)
        normalized_lines = _normalize_lines(bundle_server, line_tuples)
    except Exception:
        line_tuples = None
        normalized_lines = []

    return {
        "dialogue_id": dialogue_id,
        "manifest_path": str(manifest_path),
        "save_dir": str(save_dir),
        "text_path": str(text_path),
        "updated_at": updated_at,
        "dialogue_text": rendered_text,
        "lines": normalized_lines,
        "manifest": manifest,
        "line_tuples": line_tuples,
    }


def _create_manual_dialogue_payload(bundle_server: Any, payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "在线生成音频").strip() or "在线生成音频"
    language = _canonical_language(str(payload.get("language") or payload.get("audio_language") or "Chinese"))
    people_count = max(1, min(10, _safe_int(payload.get("people_count"), 2)))
    dialogue_text = _normalize_dialogue_text_for_storage(str(payload.get("dialogue_text") or ""))
    scenario = str(payload.get("scenario") or "").strip()
    template_label = str(payload.get("template_label") or "").strip()
    folder = str(payload.get("folder") or "默认目录").strip() or "默认目录"
    tags = payload.get("tags") or []
    source_mode = str(payload.get("source_mode") or "manual").strip() or "manual"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dialogue_id = _new_dialogue_id()
    basename = _basename_from_title(title, timestamp, "manual_dialogue")
    save_dir = ROOT / "demo" / timestamp
    save_dir.mkdir(parents=True, exist_ok=True)
    text_path = save_dir / f"{basename}.txt"
    text_path.write_text(dialogue_text, encoding="utf-8")
    updated_at = datetime.now().isoformat(timespec="seconds")

    try:
        line_tuples = _dialogue_lines_from_text(dialogue_text)
        normalized_lines = _normalize_lines(bundle_server, line_tuples)
    except Exception:
        normalized_lines = []

    manifest = {
        "dialogue_id": dialogue_id,
        "timestamp": timestamp,
        "basename": basename,
        "title": title,
        "scenario": scenario,
        "core_content": "",
        "profile": {
            "job_function": "在线生成音频",
            "work_content": template_label or "直接输入",
            "seniority": "标准",
            "use_case": template_label or "直接输入文本生成音频",
        },
        "people_count": people_count,
        "word_count": 0,
        "audio_language": language,
        "template_label": template_label,
        "tags": tags,
        "folder": folder,
        "source_mode": source_mode,
        "save_dir": str(save_dir),
        "text_path": str(text_path),
        "text_updated_at": updated_at,
        "audio_path": "",
        "voice_map": {},
        "edited_text": True,
    }
    _write_json(save_dir / "manifest.json", manifest)

    return {
        "ok": True,
        "success": True,
        "dialogue_id": dialogue_id,
        "timestamp": timestamp,
        "basename": basename,
        "text_path": str(text_path),
        "file_name": text_path.name,
        "updated_at": updated_at,
        "dialogue_text": dialogue_text,
        "text": dialogue_text,
        "lines": normalized_lines,
        "text_download_url": _download_url(dialogue_id, "text"),
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
    selected_voice_map: dict[str, str] | None = None,
    output_format: str = "mp3",
    include_scripts: bool = False,
) -> dict[str, Any]:
    from pydub import AudioSegment

    ffmpeg = _ffmpeg_path()
    if ffmpeg:
        AudioSegment.converter = ffmpeg

    tmp_dir = Path(tempfile.mkdtemp(prefix="_edited_tts_tmp_", dir=save_dir))
    normalized_output_format = str(output_format or "mp3").strip().lower()
    if normalized_output_format not in {"mp3", "wav", "m4a"}:
        normalized_output_format = "mp3"

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
            voice = _voice_for_speaker(language, speaker, selected_voice_map)
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
        m4a_path = save_dir / f"{basename}.m4a"
        combined.export(wav_path, format="wav")
        combined.export(mp3_path, format="mp3")
        if normalized_output_format == "m4a":
            combined.export(m4a_path, format="mp4")

        segments_path = ""
        srt_path = ""
        if include_scripts:
            segments_target = save_dir / f"{basename}_transcript.json"
            _write_json(segments_target, {"segments": segments, "language": _canonical_language(language)})
            segments_path = str(segments_target)

            srt_target = save_dir / f"{basename}_transcript.srt"
            srt_lines: list[str] = []
            for idx, item in enumerate(segments, start=1):
                srt_lines.append(str(idx))
                srt_lines.append(
                    f"{_format_vtt_ts(item['start_sec']).replace('.', ',')} --> "
                    f"{_format_vtt_ts(item['end_sec']).replace('.', ',')}"
                )
                srt_lines.append(f"S{_speaker_numeric_id(item['speaker'])}: {item['text']}")
                srt_lines.append("")
            srt_target.write_text("\n".join(srt_lines), encoding="utf-8")
            srt_path = str(srt_target)

        debug_path = save_dir / "tts_input_debug.txt"
        debug_path.write_text("\n".join(debug_lines), encoding="utf-8")

        selected_audio_path = str(mp3_path)
        if normalized_output_format == "wav":
            selected_audio_path = str(wav_path)
        elif normalized_output_format == "m4a":
            selected_audio_path = str(m4a_path)

        return {
            "audio_file_path": selected_audio_path,
            "mp3_path": str(mp3_path),
            "wav_path": str(wav_path),
            "m4a_path": str(m4a_path) if normalized_output_format == "m4a" else "",
            "output_format": normalized_output_format,
            "voice_map": voice_map,
            "segments_json_path": segments_path,
            "transcript_srt_path": srt_path,
            "tts_debug_file": str(debug_path),
            "warning": warning_message,
        }
    except Exception as exc:
        warning_message = f"edge_tts_fallback:{type(exc).__name__}:{exc}"
        wav_path = save_dir / f"{basename}.wav"
        mp3_path = save_dir / f"{basename}.mp3"
        m4a_path = save_dir / f"{basename}.m4a"
        audio = bundle_server._generate_wave_for_lines(lines)
        bundle_server._write_wav(audio, wav_path)
        AudioSegment.from_wav(wav_path).export(mp3_path, format="mp3")
        if normalized_output_format == "m4a":
            AudioSegment.from_wav(wav_path).export(m4a_path, format="mp4")

        segments: list[dict[str, Any]] = []
        cursor_sec = 0.0
        fallback_voice_map: dict[str, str] = {}
        for idx, (speaker, text) in enumerate(lines, start=1):
            duration = max(1.2, min(6.0, len(text) / 8.0))
            voice = _voice_for_speaker(language, speaker, selected_voice_map)
            speaker_id = str(_speaker_numeric_id(speaker))
            fallback_voice_map[speaker_id] = voice
            segments.append(
                {
                    "speaker": speaker,
                    "start_sec": round(cursor_sec, 3),
                    "end_sec": round(cursor_sec + duration, 3),
                    "text": text,
                    "voice": f"synthetic_fallback:{voice}",
                    "line_index": idx - 1,
                }
            )
            cursor_sec += duration

        segments_path = ""
        srt_path = ""
        if include_scripts:
            segments_target = save_dir / f"{basename}_transcript.json"
            _write_json(segments_target, {"segments": segments, "language": _canonical_language(language)})
            segments_path = str(segments_target)

            srt_target = save_dir / f"{basename}_transcript.srt"
            srt_lines: list[str] = []
            for idx, item in enumerate(segments, start=1):
                srt_lines.append(str(idx))
                srt_lines.append(
                    f"{_format_vtt_ts(item['start_sec']).replace('.', ',')} --> "
                    f"{_format_vtt_ts(item['end_sec']).replace('.', ',')}"
                )
                srt_lines.append(f"S{_speaker_numeric_id(item['speaker'])}: {item['text']}")
                srt_lines.append("")
            srt_target.write_text("\n".join(srt_lines), encoding="utf-8")
            srt_path = str(srt_target)

        debug_path = save_dir / "tts_input_debug.txt"
        debug_path.write_text(
            "\n".join(
                [
                    f"{speaker}\tsynthetic_fallback:{_voice_for_speaker(language, speaker, selected_voice_map)}\t{text}"
                    for speaker, text in lines
                ]
            ),
            encoding="utf-8",
        )

        selected_audio_path = str(mp3_path)
        if normalized_output_format == "wav":
            selected_audio_path = str(wav_path)
        elif normalized_output_format == "m4a":
            selected_audio_path = str(m4a_path)

        return {
            "audio_file_path": selected_audio_path,
            "mp3_path": str(mp3_path),
            "wav_path": str(wav_path),
            "m4a_path": str(m4a_path) if normalized_output_format == "m4a" else "",
            "output_format": normalized_output_format,
            "voice_map": fallback_voice_map,
            "segments_json_path": segments_path,
            "transcript_srt_path": srt_path,
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
        urls = local_urls(port)
        preferred_share_url = next(
            (item for item in urls if "127.0.0.1" not in item and "localhost" not in item),
            urls[0] if urls else f"http://127.0.0.1:{port}/",
        )
        self.write_json(
            {
                "ok": True,
                "success": True,
                "listen_host": os.environ.get("DEMO_APP_HOST", "0.0.0.0"),
                "port": port,
                "local_urls": urls,
                "localhost_url": f"http://127.0.0.1:{port}/",
                "preferred_share_url": preferred_share_url,
                "share_hint": "同一局域网内的其他电脑可通过上面的 IP 地址访问。如果访问失败，先放行 Windows 防火墙的 8899 端口。",
            }
        )


class PresetTopicsHandler(JsonHandler):
    def get(self) -> None:
        self.write_json(
            {
                "ok": True,
                "success": True,
                "presets": _load_preset_topics(),
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
                "success": True,
                "dialogue_id": dialogue_id,
                "text_path": result["text_path"],
                "file_name": Path(result["text_path"]).name,
                "updated_at": result["updated_at"],
                "dialogue_text": result["dialogue_text"],
                "lines": result["lines"],
                "text_download_url": _download_url(dialogue_id, "text"),
            }
        )


class CreateDialogueFromTextHandler(JsonHandler):
    def post(self) -> None:
        payload = self.read_json()
        if not str(payload.get("title", "")).strip():
            raise HTTPError(400, reason="title is required")
        if not str(payload.get("dialogue_text", "")).strip():
            raise HTTPError(400, reason="dialogue_text is required")

        bundle_server = load_bundle_server()
        response = _create_manual_dialogue_payload(bundle_server, payload)
        self.write_json(response)


class GenerateAudioCustomHandler(JsonHandler):
    async def post(self) -> None:
        payload = self.read_json()
        dialogue_id = str(payload.get("dialogue_id", "")).strip()
        if not dialogue_id:
            raise HTTPError(400, reason="dialogue_id is required")

        bundle_server = load_bundle_server()
        dialogue_text = str(payload.get("dialogue_text", "")).strip()
        if dialogue_text:
            normalized_text = _normalize_dialogue_text_for_storage(dialogue_text)
            if len(normalized_text) > MAX_AUDIO_TEXT_CHARS:
                raise HTTPError(400, reason=f"文本过长，请缩短到 {MAX_AUDIO_TEXT_CHARS} 个字符以内后再生成音频")
            result = _save_dialogue_edit(bundle_server, dialogue_id, normalized_text)
            manifest = result["manifest"]
            save_dir = Path(result["save_dir"])
            line_tuples = _dialogue_lines_from_text(normalized_text)
        else:
            manifest_path, manifest = _find_manifest(dialogue_id)
            save_dir = Path(manifest.get("save_dir") or manifest_path.parent)
            text_path = Path(manifest["text_path"])
            normalized_text = _normalize_dialogue_text_for_storage(text_path.read_text(encoding="utf-8"))
            if len(normalized_text) > MAX_AUDIO_TEXT_CHARS:
                raise HTTPError(400, reason=f"文本过长，请缩短到 {MAX_AUDIO_TEXT_CHARS} 个字符以内后再生成音频")
            line_tuples = _dialogue_lines_from_text(normalized_text)

        basename = manifest.get("basename", dialogue_id)
        language = str(payload.get("language") or manifest.get("audio_language") or "中文")
        selected_voice_map = payload.get("voice_map") or {}
        output_format = str(payload.get("format") or manifest.get("audio_output_format") or "mp3")
        include_scripts = bool(payload.get("include_scripts"))
        audio_result = await _synthesize_audio_from_lines(
            line_tuples,
            language,
            save_dir,
            basename,
            bundle_server,
            selected_voice_map=selected_voice_map if isinstance(selected_voice_map, dict) else None,
            output_format=output_format,
            include_scripts=include_scripts,
        )
        generated_at = datetime.now().isoformat(timespec="seconds")

        audio_file = audio_result["audio_file_path"]
        manifest["audio_path"] = audio_file
        manifest["voice_map"] = audio_result["voice_map"]
        manifest["audio_language"] = language
        manifest["audio_output_format"] = audio_result["output_format"]
        manifest["audio_warning"] = audio_result["warning"]
        manifest["segments_json_path"] = audio_result["segments_json_path"]
        manifest["transcript_srt_path"] = audio_result["transcript_srt_path"]
        manifest["audio_updated_at"] = generated_at
        _write_json(Path(manifest.get("save_dir") or save_dir) / "manifest.json", manifest)

        self.write_json(
            {
                "ok": True,
                "success": True,
                "dialogue_id": dialogue_id,
                "audio_file_path": audio_file,
                "file_name": Path(audio_file).name,
                "generated_at": generated_at,
                "updated_at": generated_at,
                "mp3_path": audio_result["mp3_path"],
                "wav_path": audio_result["wav_path"],
                "m4a_path": audio_result["m4a_path"],
                "output_format": audio_result["output_format"],
                "voice_map": audio_result["voice_map"],
                "warning": audio_result["warning"],
                "tts_debug_file": audio_result["tts_debug_file"],
                "segments_json_path": audio_result["segments_json_path"],
                "transcript_srt_path": audio_result["transcript_srt_path"],
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

    if not getattr(module, "_embedded_naturalness_patched", False):
        original_generate_dialogue_lines = module._generate_dialogue_lines

        def _patched_generate_dialogue_lines(
            profile: dict,
            scenario: str,
            core: str,
            people: int,
            target_len: int,
            language: str = "中文",
            payment_mode: bool = None,
            context_pack: dict = None,
        ):
            lines, rewrite_info = original_generate_dialogue_lines(
                profile,
                scenario,
                core,
                people,
                target_len,
                language,
                payment_mode,
                context_pack,
            )
            try:
                polished_lines, naturalness = polish_generated_lines(lines, language)
                if naturalness.get("rewrite_count"):
                    lines = polished_lines
                    rewrite_info = dict(rewrite_info or {})
                    rewrite_info["naturalness_applied"] = True
                    rewrite_info["naturalness_language"] = naturalness.get("language")
                    rewrite_info["naturalness_rewrites"] = naturalness.get("rewrite_count")
            except Exception as exc:
                rewrite_info = dict(rewrite_info or {})
                rewrite_info["naturalness_error"] = f"{type(exc).__name__}:{exc}"
            return lines, rewrite_info

        module._generate_dialogue_lines = _patched_generate_dialogue_lines
        module._embedded_naturalness_patched = True

    if not getattr(module, "_embedded_generate_text_handler_patched", False):
        def _patched_generate_text_post(self):
            try:
                payload = json.loads(self.request.body.decode("utf-8") or "{}")
            except Exception as exc:
                raise HTTPError(400, reason=f"Invalid JSON body: {exc}") from exc

            response = _generate_text_payload(module, payload)
            self.set_header("Content-Type", "application/json; charset=utf-8")
            self.finish(json.dumps(response, ensure_ascii=False))

        module.GenerateTextHandler.post = _patched_generate_text_post
        module._embedded_generate_text_handler_patched = True

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
            (r"/api/preset_topics", PresetTopicsHandler),
            (r"/api/create_dialogue_from_text", CreateDialogueFromTextHandler),
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
