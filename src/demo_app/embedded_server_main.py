#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import functools
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
import threading
import urllib.parse
from datetime import datetime
from importlib._bootstrap_external import _code_to_timestamp_pyc
from pathlib import Path
from typing import Any

import edge_tts
from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.loader.pyimod01_archive import PYZ_ITEM_MODULE, PYZ_ITEM_PKG
from tornado.web import HTTPError, RequestHandler


try:
    from deep_translator import GoogleTranslator as _GoogleTranslator
    _HAS_DEEP_TRANSLATOR = True
except ImportError:
    _HAS_DEEP_TRANSLATOR = False

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from demo_app.multilingual_naturalness import enforce_keywords_in_lines as merge_keywords_into_lines
from demo_app.multilingual_naturalness import polish_generated_lines, repair_dialogue_quality, stabilize_dialogue_constraints
from demo_app.few_shot_selector import get_few_shot_example

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

# ── Manifest index ─────────────────────────────────────────────────────────────
# Lazily populated on first access; keeps O(1) lookup by dialogue_id.
_manifest_cache: dict[str, tuple[Path, dict]] = {}
_manifest_cache_lock = threading.Lock()
_manifest_cache_loaded = False

# ── Config / preset caches (refresh requires server restart) ───────────────────
_ONLINE_AUDIO_CONFIG_CACHE: dict[str, Any] | None = None
_PRESET_TOPICS_CACHE: list[dict[str, Any]] | None = None

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
PRESET_TOPIC_FILE_NAME = "预置对话情景参数.txt"
ONLINE_AUDIO_CONFIG_FILE_NAME = "online_audio_ui.json"
PRESET_BLOCK_RE = re.compile(r"(?ms)^\s*(\d+)[）\)]\s*(.+?)(?=^\s*\d+[）\)]\s*|\Z)")
DEFAULT_PRESET_DISPLAY_TITLE_OVERRIDES = {
    "1": "医疗健康｜慢病随访",
    "2": "人力资源与招聘｜招聘补岗",
    "3": "娱乐/媒体｜艺人商业化",
    "4": "建筑与工程行业｜项目交付",
    "5": "汽车行业｜车型投放",
    "6": "咨询/专业服务｜客户拓展",
    "7": "法律服务｜法顾专项",
    "8": "金融/投资｜资产配置",
    "9": "零售行业｜会员复购",
    "10": "保险行业｜保险质检",
    "11": "房地产｜项目去化",
    "12": "人工智能/科技｜付费转化",
    "13": "制造业｜产线提效",
    "14": "娱乐/媒体｜战略周会",
    "15": "法律服务｜广告合规",
    "16": "保险行业｜销售洞察",
    "17": "测试开发｜支付接入",
    "18": "测试开发｜下单回调",
    "19": "测试开发｜退款安全",
    "20": "测试开发｜对账差错",
    "21": "测试开发｜稳定性准入",
    "22": "测试开发｜朋友圈项目",
    "23": "测试开发｜内容发布",
    "24": "测试开发｜多端分发",
    "25": "测试开发｜互动一致性",
    "26": "测试开发｜隐私可见性",
    "27": "测试开发｜内容审核",
    "28": "测试开发｜容量与准入",
}


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


def _safe_generation_context(payload: dict[str, Any]) -> dict[str, Any]:
    context = payload.get("generation_context") or {}
    if not isinstance(context, dict):
        return {}
    return {
        "domain": str(context.get("domain") or "").strip(),
        "scene_type": str(context.get("scene_type") or "").strip(),
        "scene_goal": str(context.get("scene_goal") or "").strip(),
        "deliverable": str(context.get("deliverable") or "").strip(),
        "role_briefs": _safe_str_list(context.get("role_briefs")),
        "role_objectives": _safe_str_list(context.get("role_objectives")),
        "discussion_axes": _safe_str_list(context.get("discussion_axes")),
        "stage_prompts": _safe_str_list(context.get("stage_prompts")),
        "risk_checks": _safe_str_list(context.get("risk_checks")),
        "success_signals": _safe_str_list(context.get("success_signals")),
        "quality_constraints": _safe_str_list(context.get("quality_constraints")),
    }


# ── 行业名中→英映射（profile / generation_context 字段净化用）────────────────
_INDUSTRY_ZH_TO_EN: dict[str, str] = {
    "人工智能/科技":   "AI / Technology",
    "娱乐/媒体":       "Entertainment / Media",
    "商业化":          "Commercialization",
    "测试开发":        "Software Testing & Development",
    "人力资源与招聘":  "HR & Recruitment",
    "建筑与工程行业":  "Construction & Engineering",
    "咨询/专业服务":   "Consulting / Professional Services",
    "法律服务":        "Legal Services",
    "金融/投资":       "Finance / Investment",
    "零售行业":        "Retail",
    "保险行业":        "Insurance",
    "医疗行业":        "Healthcare",
    "医疗健康":        "Healthcare",
    "房地产":          "Real Estate",
    "制造业":          "Manufacturing",
    "汽车行业":        "Automotive",
}

# 场景类型中→英（use_case 后缀部分）
_SCENE_ZH_TO_EN: dict[str, str] = {
    "付费转化":     "Paid Conversion",
    "战略周会":     "Strategic Weekly Meeting",
    "支付项目":     "Payment Project",
    "招聘补岗":     "Recruitment",
    "艺人商业化":   "Artist Commercialization",
    "项目交付":     "Project Delivery",
    "客户拓展":     "Client Development",
    "法顾专项":     "Legal Advisory",
    "资产配置":     "Asset Allocation",
    "会员复购":     "Member Repurchase",
    "理赔服务":     "Claims Service",
    "医疗咨询":     "Medical Consultation",
    "项目融资":     "Project Financing",
    "产线提效":     "Production Line Efficiency",
    "场景讨论":     "Scene Discussion",
    "会议讨论":     "Meeting Discussion",
}


def _cjk_heavy(text: str, threshold: float = 0.15) -> bool:
    """Return True if text is predominantly CJK (Chinese)."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False
    return sum(1 for c in chars if "\u4e00" <= c <= "\u9fff") / len(chars) >= threshold


def _translate_field(value: str, mapping: dict[str, str]) -> str:
    """Replace a known Chinese value with its English equivalent; keep original if unknown."""
    return mapping.get(value, value)


def _sanitize_profile_for_language(profile: dict[str, Any], generation_context: dict[str, Any], language: str) -> None:
    """
    For non-Chinese languages, replace Chinese strings in profile and generation_context
    with English equivalents so the LLM prompt stays in the target language.
    Mutates both dicts in-place.
    """
    if language == "Chinese":
        return

    # profile.job_function
    jf = str(profile.get("job_function") or "")
    if _cjk_heavy(jf):
        profile["job_function"] = _translate_field(jf, _INDUSTRY_ZH_TO_EN)

    # profile.use_case  (pattern: "行业｜场景" or plain industry)
    uc = str(profile.get("use_case") or "")
    if _cjk_heavy(uc) and uc not in ("general_use_case",):
        if "｜" in uc:
            industry_part, scene_part = uc.split("｜", 1)
            en_industry = _translate_field(industry_part, _INDUSTRY_ZH_TO_EN)
            en_scene    = _translate_field(scene_part,    _SCENE_ZH_TO_EN)
            profile["use_case"] = f"{en_industry} | {en_scene}"
        else:
            profile["use_case"] = _translate_field(uc, _INDUSTRY_ZH_TO_EN)

    # profile.work_content
    wc = str(profile.get("work_content") or "")
    if _cjk_heavy(wc):
        profile["work_content"] = _translate_field(wc, _INDUSTRY_ZH_TO_EN)

    # generation_context.domain
    domain = str(generation_context.get("domain") or "")
    if _cjk_heavy(domain):
        generation_context["domain"] = _translate_field(domain, _INDUSTRY_ZH_TO_EN)

    # generation_context.scene_type
    st = str(generation_context.get("scene_type") or "")
    if _cjk_heavy(st):
        generation_context["scene_type"] = _translate_field(st, _SCENE_ZH_TO_EN)


def _merge_text_parts(*parts: str, sep: str = "；") -> str:
    merged: list[str] = []
    for part in parts:
        normalized = str(part or "").strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    return sep.join(merged)


def _prompt_labels(language: str) -> dict[str, str]:
    """Return prompt construction labels in the target language.
    Non-Chinese languages use English labels to avoid Chinese injection."""
    if language == "Chinese":
        return {
            "scene_type_default": "场景讨论",
            "participants":       "参与角色：",
            "discussion":         "重点讨论：",
            "role_objectives":    "角色目标：",
            "stages":             "推进阶段：",
            "risk_checks":        "风险检查点：",
            "success_signals":    "成功标准：",
            "deliverable":        "目标输出：",
            "quality_constraints":"写作要求：",
            "title_default":      "对话",
            "sep":                "；",
            "enum_sep":           "、",
        }
    return {
        "scene_type_default": "Scene Discussion",
        "participants":       "Participants: ",
        "discussion":         "Key discussion points: ",
        "role_objectives":    "Role objectives: ",
        "stages":             "Progression stages: ",
        "risk_checks":        "Risk checkpoints: ",
        "success_signals":    "Success criteria: ",
        "deliverable":        "Target output: ",
        "quality_constraints":"Writing requirements: ",
        "title_default":      "Dialogue",
        "sep":                "; ",
        "enum_sep":           ", ",
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


def _default_online_audio_config() -> dict[str, Any]:
    template_catalog = []
    for label in list(DEFAULT_PRESET_DISPLAY_TITLE_OVERRIDES.values())[:18]:
        domain, scene = (label.split("｜", 1) + ["场景讨论"])[:2]
        template_catalog.append(
            {
                "label": label,
                "domain": domain.strip() or "通用业务",
                "sceneType": scene.strip() or "场景讨论",
                "primaryRole": "业务负责人",
                "supportingRoles": [],
                "discussionAxes": [],
                "deliverable": "",
                "goalStem": "",
            }
        )
    return {
        "defaults": {
            "wordCount": "1000",
            "wordCountMin": 100,
            "wordCountMax": 3000,
            "folder": "默认目录",
        },
        "folderOptions": ["默认目录", "项目 A / 会议语料", "项目 A / 访谈语料", "项目 B"],
        "presetDisplayTitles": dict(DEFAULT_PRESET_DISPLAY_TITLE_OVERRIDES),
        "templateAliasGroups": {},
        "templateCatalog": template_catalog,
    }


def _resolve_online_audio_config_file() -> Path | None:
    candidates: list[Path] = []
    for base in [ROOT, ROOT.parent, ROOT.parent.parent]:
        candidates.extend(
            [
                base / "config" / ONLINE_AUDIO_CONFIG_FILE_NAME,
                base / "demo_app" / "config" / ONLINE_AUDIO_CONFIG_FILE_NAME,
            ]
        )

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate
    return None


def _load_online_audio_config() -> dict[str, Any]:
    config_file = _resolve_online_audio_config_file()
    if not config_file:
        return _default_online_audio_config()

    try:
        loaded = json.loads(config_file.read_text(encoding="utf-8"))
    except Exception:
        return _default_online_audio_config()

    fallback = _default_online_audio_config()
    merged = {
        "defaults": {**fallback["defaults"], **(loaded.get("defaults") or {})},
        "folderOptions": list(loaded.get("folderOptions") or fallback["folderOptions"]),
        "presetDisplayTitles": {**fallback["presetDisplayTitles"], **(loaded.get("presetDisplayTitles") or {})},
        "templateAliasGroups": {**fallback["templateAliasGroups"], **(loaded.get("templateAliasGroups") or {})},
        "templateCatalog": list(loaded.get("templateCatalog") or fallback["templateCatalog"]),
    }
    return merged


def _resolve_preset_topic_file() -> Path | None:
    candidates: list[Path] = []
    for base in [ROOT, ROOT.parent, ROOT.parent.parent]:
        candidates.extend(
            [
                base / "demo" / "对话情景参数" / PRESET_TOPIC_FILE_NAME,
                base / "demo" / PRESET_TOPIC_FILE_NAME,
                base / "demo_app" / "demo" / "对话情景参数" / PRESET_TOPIC_FILE_NAME,
                base / "demo_app" / "demo" / PRESET_TOPIC_FILE_NAME,
            ]
        )

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate
    return None


def _load_preset_topics() -> list[dict[str, Any]]:
    preset_topic_file = _resolve_preset_topic_file()
    if not preset_topic_file:
        return []

    online_audio_config = _load_online_audio_config()
    preset_display_titles = online_audio_config.get("presetDisplayTitles") or {}
    raw_text = preset_topic_file.read_text(encoding="utf-8")
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
                "display_title": str(preset_display_titles.get(preset_id) or _preset_display_title(topic_text)),
                "scenario": scenario or topic_text,
                "core_content": core_content,
                "template_label": template_label,
                "people_count": max(2, min(10, _safe_int(people_match.group(1) if people_match else None, 3))),
                "word_count": min(5000, max(300, _extract_word_count(block))),
                "language": _canonical_language(language_match.group(1) if language_match else "Chinese"),
                "profile": _preset_profile(title, topic_text, template_label),
            }
        )

    return presets


def _new_dialogue_id() -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


# ── Latin-language translation fallback ──────────────────────────────────────
# When the bundle LLM generates CJK for a Latin-script language (FR/DE/ES/PT),
# we generate English first and translate via deep_translator.

_LATIN_LANG_GT_CODE: dict[str, str] = {
    "French": "fr", "German": "de", "Spanish": "es", "Portuguese": "pt",
}


def _translate_dialogue_lines(
    lines: list[tuple[str, str]], target_language: str
) -> list[tuple[str, str]]:
    """
    Translate dialogue lines (already in English) to a Latin-script target language.
    Renders as 'Speaker N: text' block, translates in chunks, normalises speaker
    labels, then re-parses back into (original_speaker, translated_text) tuples.
    Returns the original lines unchanged if translation is unavailable or fails.
    """
    if not _HAS_DEEP_TRANSLATOR:
        return lines
    gt_code = _LATIN_LANG_GT_CODE.get(target_language)
    if not gt_code or not lines:
        return lines

    import time as _time

    # Render with stable Speaker N: labels so we can re-parse after translation
    text_block = "\n".join(f"Speaker {i}: {text}" for i, (_, text) in enumerate(lines, 1))
    idx_to_speaker = {i: spk for i, (spk, _) in enumerate(lines, 1)}

    # Split into ≤4500-char chunks on line boundaries
    CHUNK_SIZE = 4500
    raw_lines = text_block.splitlines(keepends=True)
    chunks: list[str] = []
    current = ""
    for raw_line in raw_lines:
        if len(current) + len(raw_line) > CHUNK_SIZE and current:
            chunks.append(current)
            current = raw_line
        else:
            current += raw_line
    if current:
        chunks.append(current)

    translated_parts: list[str] = []
    for idx, chunk in enumerate(chunks):
        for attempt in range(3):
            try:
                t = _GoogleTranslator(source="auto", target=gt_code).translate(chunk)
                if t:
                    translated_parts.append(t)
                    break
            except Exception:
                _time.sleep(10 * (attempt + 1))
        else:
            translated_parts.append(chunk)   # keep original chunk on total failure
        if idx < len(chunks) - 1:
            _time.sleep(1.5)

    translated_text = "".join(translated_parts)

    # Normalise translated speaker labels (e.g. "Haut-parleur 1 :", "Sprecher 1:")
    normalised = re.sub(
        r"^[A-Za-z\xc0-\xff\-\s\xa0]+?\s*(\d+)\s*[\xa0\s]*[:\uff1a]\s*",
        r"Speaker \1: ",
        translated_text,
        flags=re.MULTILINE,
    )

    result: list[tuple[str, str]] = []
    for line in normalised.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^Speaker\s+(\d+):\s*(.+)$", line)
        if m:
            spk_num = int(m.group(1))
            text = m.group(2).strip()
            orig_speaker = idx_to_speaker.get(spk_num, f"说话人{spk_num}")
            result.append((orig_speaker, text))

    # Reject result if too few lines parsed (likely translation/parse failure)
    if len(result) < max(3, len(lines) // 2):
        return lines
    return result


# ── Long-dialogue multi-segment generation ────────────────────────────────────
# The bundle LLM generates ~3 000 chars per call.  For word_count > 5 000 we
# make multiple calls and concatenate the results, deduplicating on the text
# content of each line so the same sentence doesn't appear twice.

_LONG_DIALOGUE_SEGMENT_TARGET = 3000   # chars requested per segment call
_LONG_DIALOGUE_THRESHOLD      = 5000   # above this, switch to multi-segment


def _generate_long_dialogue_lines(
    bundle_server: Any,
    profile: dict,
    scenario: str,
    core_content: str,
    people_count: int,
    total_target: int,
    language: str,
) -> tuple[list[tuple[str, str]], dict]:
    """
    Single call for total_target ≤ _LONG_DIALOGUE_THRESHOLD.
    Multi-segment (loop) for larger targets: repeatedly calls
    _generate_dialogue_lines with segment-sized targets and concatenates
    unique lines until the accumulated character count meets total_target.
    """
    if total_target <= _LONG_DIALOGUE_THRESHOLD:
        return bundle_server._generate_dialogue_lines(
            profile, scenario, core_content, people_count, total_target, language
        )

    accumulated: list[tuple[str, str]] = []
    seen_texts: set[str] = set()
    last_rewrite_info: dict = {}
    consecutive_empty = 0

    while True:
        current_chars = sum(len(t) for _, t in accumulated)
        if current_chars >= total_target:
            break

        seg_lines, rewrite_info = bundle_server._generate_dialogue_lines(
            profile, scenario, core_content, people_count,
            _LONG_DIALOGUE_SEGMENT_TARGET, language,
        )
        last_rewrite_info = rewrite_info

        added = 0
        for spk, text in (seg_lines or []):
            if text and text not in seen_texts:
                seen_texts.add(text)
                accumulated.append((spk, text))
                added += 1

        if added == 0:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                break   # LLM is looping; give up rather than spinning forever
        else:
            consecutive_empty = 0

    return accumulated, last_rewrite_info


def _generate_text_payload(bundle_server: Any, payload: dict[str, Any]) -> dict[str, Any]:
    profile = _safe_profile(payload)
    generation_context = _safe_generation_context(payload)
    scenario = str(payload.get("scenario") or "").strip()
    core_content = str(payload.get("core_content") or "").strip()
    people_count = max(2, min(10, _safe_int(payload.get("people_count"), 3)))
    word_count = min(50000, max(300, _safe_int(payload.get("word_count"), 1000)))
    language = _canonical_language(str(payload.get("audio_language") or payload.get("language") or "Chinese"))
    lbl = _prompt_labels(language)

    # Sanitize Chinese strings in profile/generation_context for non-Chinese languages
    _sanitize_profile_for_language(profile, generation_context, language)

    title = str(
        payload.get("title") or
        payload.get("scenario") or
        profile.get("work_content") or
        profile.get("job_function") or
        lbl["title_default"]
    ).strip()
    template_label = str(payload.get("template_label") or "").strip()
    tags = payload.get("tags") or []
    keyword_terms = _safe_str_list(payload.get("keyword_terms"))
    folder = str(payload.get("folder") or "默认目录").strip() or "默认目录"

    if generation_context.get("domain") and profile["use_case"] == "general_use_case":
        scene_type = generation_context.get("scene_type") or template_label or lbl["scene_type_default"]
        profile["use_case"] = f"{generation_context['domain']}｜{scene_type}"
    if generation_context.get("role_briefs") and profile["job_function"] == "unknown_job_function":
        profile["job_function"] = generation_context["role_briefs"][0]
    if generation_context.get("scene_goal"):
        scenario = _merge_text_parts(
            scenario,
            generation_context["scene_goal"],
            f"{lbl['participants']}{lbl['enum_sep'].join(generation_context.get('role_briefs', []))}",
            sep=lbl["sep"],
        )
    if (
        generation_context.get("discussion_axes")
        or generation_context.get("deliverable")
        or generation_context.get("quality_constraints")
        or generation_context.get("role_objectives")
        or generation_context.get("stage_prompts")
        or generation_context.get("risk_checks")
        or generation_context.get("success_signals")
    ):
        core_content = _merge_text_parts(
            core_content,
            f"{lbl['discussion']}{lbl['enum_sep'].join(generation_context.get('discussion_axes', []))}" if generation_context.get("discussion_axes") else "",
            f"{lbl['role_objectives']}{lbl['sep'].join(generation_context.get('role_objectives', []))}" if generation_context.get("role_objectives") else "",
            f"{lbl['stages']}{lbl['sep'].join(generation_context.get('stage_prompts', []))}" if generation_context.get("stage_prompts") else "",
            f"{lbl['risk_checks']}{lbl['sep'].join(generation_context.get('risk_checks', []))}" if generation_context.get("risk_checks") else "",
            f"{lbl['success_signals']}{lbl['sep'].join(generation_context.get('success_signals', []))}" if generation_context.get("success_signals") else "",
            f"{lbl['deliverable']}{generation_context.get('deliverable', '')}" if generation_context.get("deliverable") else "",
            f"{lbl['quality_constraints']}{lbl['sep'].join(generation_context.get('quality_constraints', []))}" if generation_context.get("quality_constraints") else "",
            sep=lbl["sep"],
        )

    # Few-shot 注入：从训练语料取同行业示例，引导 LLM 对齐行业对话风格
    _fs_domain = generation_context.get("domain", "")
    if _fs_domain:
        _fs_example = get_few_shot_example(_fs_domain, language)
        if _fs_example:
            _fs_label = "Reference dialogue style (match the tone and rhythm, do not copy content):" if language in ("English", "Japanese", "Korean") else "参考对话风格示例（仅参考语气和节奏，请勿照抄内容）："
            core_content = core_content + f"\n\n{_fs_label}\n---\n{_fs_example}\n---"

    lines, rewrite_info = _generate_long_dialogue_lines(
        bundle_server,
        profile,
        scenario,
        core_content,
        people_count,
        word_count,
        language,
    )

    # Bug 3 fix: if LLM generated CJK for a Latin-script language, fall back to
    # generating English first and translating via deep_translator.
    if (rewrite_info or {}).get("cjk_heavy") and language in _LATIN_LANG_GT_CODE:
        en_lines, _ = _generate_long_dialogue_lines(
            bundle_server,
            profile,
            scenario,
            core_content,
            people_count,
            word_count,
            "English",
        )
        if en_lines:
            translated = _translate_dialogue_lines(en_lines, language)
            if translated:
                lines = translated
                rewrite_info = dict(rewrite_info or {})
                rewrite_info["used_translate_fallback"] = True
                rewrite_info["cjk_heavy"] = False

    repaired_lines, repair_meta = repair_dialogue_quality(
        lines,
        language,
        title=title,
        scenario=scenario,
        core_content=core_content,
        profile=profile,
        target_word_count=word_count,
        people_count=people_count,
        keywords=keyword_terms,
        generation_context=generation_context,
    )
    if repair_meta.get("repaired"):
        lines = repaired_lines
    lines, injected_keywords = merge_keywords_into_lines(
        lines,
        keyword_terms,
        language,
        title=title,
        scenario=scenario,
        core_content=core_content,
        profile=profile,
        generation_context=generation_context,
    )
    lines, stabilize_meta = stabilize_dialogue_constraints(
        lines,
        language,
        title=title,
        scenario=scenario,
        core_content=core_content,
        profile=profile,
        target_word_count=word_count,
        people_count=people_count,
        keywords=keyword_terms,
        generation_context=generation_context,
    )
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
        "topic_input_mode": str(payload.get("topic_input_mode") or "manual").strip() or "manual",
        "preset_id": str(payload.get("preset_id") or "").strip(),
        "preset_source_title": str(payload.get("preset_source_title") or "").strip(),
        "generation_context": generation_context,
        "save_dir": str(save_dir),
        "text_path": str(text_path),
        "text_updated_at": updated_at,
        "audio_path": "",
        "voice_map": {},
        "edited_text": False,
    }
    _write_json(save_dir / "manifest.json", manifest)
    _register_manifest(dialogue_id, save_dir / "manifest.json", manifest)

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
        "repair_meta": repair_meta,
        "stabilize_meta": stabilize_meta,
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
        "text_download_url": _download_url(dialogue_id, "text"),
    }


def _ensure_manifest_cache() -> None:
    global _manifest_cache_loaded
    if _manifest_cache_loaded:
        return
    with _manifest_cache_lock:
        if _manifest_cache_loaded:
            return
        demo_root = ROOT / "demo"
        if demo_root.exists():
            for manifest_path in demo_root.glob("*/manifest.json"):
                try:
                    manifest = _read_json(manifest_path)
                    did = manifest.get("dialogue_id")
                    if did:
                        _manifest_cache[did] = (manifest_path, manifest)
                except Exception:
                    continue
        _manifest_cache_loaded = True


def _register_manifest(dialogue_id: str, manifest_path: Path, manifest: dict[str, Any]) -> None:
    _ensure_manifest_cache()
    with _manifest_cache_lock:
        _manifest_cache[dialogue_id] = (manifest_path, manifest)


def _evict_manifest(dialogue_id: str) -> None:
    with _manifest_cache_lock:
        _manifest_cache.pop(dialogue_id, None)


def _find_manifest(dialogue_id: str) -> tuple[Path, dict[str, Any]]:
    _ensure_manifest_cache()
    with _manifest_cache_lock:
        entry = _manifest_cache.get(dialogue_id)
    if entry:
        manifest_path, manifest = entry
        if manifest_path.exists():
            return manifest_path, manifest
        _evict_manifest(dialogue_id)
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
    keyword_terms = _safe_str_list(payload.get("keyword_terms"))
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
        "keyword_terms": keyword_terms,
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
    _register_manifest(dialogue_id, save_dir / "manifest.json", manifest)

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
    for suffix in (".mp3", ".wav", ".m4a"):
        path = save_dir / f"{basename}{suffix}"
        if path.exists():
            candidates.append(path)
    if candidates:
        return sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)[0]
    any_audio = sorted(save_dir.glob("*.mp3")) + sorted(save_dir.glob("*.wav")) + sorted(save_dir.glob("*.m4a"))
    if any_audio:
        return sorted(any_audio, key=lambda item: item.stat().st_mtime, reverse=True)[0]
    return None


def _audio_output_paths(save_dir: Path, basename: str) -> dict[str, Path]:
    return {
        "mp3": save_dir / f"{basename}.mp3",
        "wav": save_dir / f"{basename}.wav",
        "m4a": save_dir / f"{basename}.m4a",
    }


def _cleanup_extra_audio_formats(audio_paths: dict[str, Path], keep_format: str) -> None:
    for output_format, path in audio_paths.items():
        if output_format == keep_format:
            continue
        try:
            if path.exists():
                path.unlink()
        except OSError:
            continue


def _resolve_audio_target(manifest: dict[str, Any], dialogue_id: str) -> Path | None:
    save_dir = Path(manifest.get("save_dir") or ROOT / "demo")
    basename = str(manifest.get("basename") or dialogue_id)
    audio_path = str(manifest.get("audio_path") or "").strip()
    if audio_path:
        candidate = Path(audio_path)
        if candidate.exists():
            return candidate

    output_format = str(manifest.get("audio_output_format") or "").strip().lower()
    if output_format in {"mp3", "wav", "m4a"}:
        expected = _audio_output_paths(save_dir, basename)[output_format]
        if expected.exists():
            return expected

    return _latest_audio_path(save_dir, basename)


def _task_storage_dir(manifest_path: Path, manifest: dict[str, Any]) -> Path:
    candidate = Path(str(manifest.get("save_dir") or manifest_path.parent))
    try:
        resolved = candidate.resolve()
    except OSError:
        resolved = candidate.absolute()

    demo_root = (ROOT / "demo").resolve()
    try:
        resolved.relative_to(demo_root)
    except ValueError as exc:
        raise HTTPError(400, reason="task save_dir is outside demo directory") from exc

    if resolved == demo_root:
        raise HTTPError(400, reason="refuse to delete demo root")

    return resolved


def _delete_task_artifacts(dialogue_id: str) -> dict[str, Any]:
    try:
        manifest_path, manifest = _find_manifest(dialogue_id)
    except FileNotFoundError:
        return {"dialogue_id": dialogue_id, "deleted": False, "not_found": True}

    target_dir = _task_storage_dir(manifest_path, manifest)
    deleted = False
    if target_dir.exists():
        shutil.rmtree(target_dir)
        deleted = True
    elif manifest_path.exists():
        manifest_path.unlink()
        deleted = True

    _evict_manifest(dialogue_id)
    return {
        "dialogue_id": dialogue_id,
        "deleted": deleted,
        "not_found": False,
        "deleted_path": str(target_dir),
    }


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


def _build_scripts(save_dir: Path, basename: str, segments: list[dict[str, Any]], language: str) -> tuple[str, str]:
    """Write transcript JSON and SRT file; return (segments_path, srt_path)."""
    segments_target = save_dir / f"{basename}_transcript.json"
    _write_json(segments_target, {"segments": segments, "language": _canonical_language(language)})

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
    return str(segments_target), str(srt_target)


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

    # Build ordered segment list (skip blank lines)
    valid_segments: list[tuple[int, str, str, str, str, Path]] = []
    for idx, (speaker, text) in enumerate(lines, start=1):
        cleaned = text.strip()
        if not cleaned:
            continue
        voice = _voice_for_speaker(language, speaker, selected_voice_map)
        speaker_id = str(_speaker_numeric_id(speaker))
        segment_file = tmp_dir / f"line_{idx:03d}.mp3"
        valid_segments.append((idx, speaker, cleaned, voice, speaker_id, segment_file))

    warning_message = None
    try:
        # Synthesize all segments concurrently (rate-limited to 5 parallel requests)
        sem = asyncio.Semaphore(5)

        async def _tts_one(voice: str, text: str, path: Path) -> None:
            async with sem:
                await edge_tts.Communicate(text, voice).save(str(path))

        await asyncio.gather(*[
            _tts_one(voice, cleaned, segment_file)
            for (_, _, cleaned, voice, _, segment_file) in valid_segments
        ])

        # Combine in order and build metadata
        combined = AudioSegment.silent(duration=120)
        segments: list[dict[str, Any]] = []
        voice_map: dict[str, str] = {}
        debug_lines: list[str] = []
        cursor_sec = 0.12

        for idx, speaker, cleaned, voice, speaker_id, segment_file in valid_segments:
            voice_map[speaker_id] = voice
            audio = AudioSegment.from_file(segment_file)
            start_sec = cursor_sec
            duration_sec = len(audio) / 1000.0
            end_sec = start_sec + duration_sec
            segments.append({
                "speaker": speaker,
                "start_sec": round(start_sec, 3),
                "end_sec": round(end_sec, 3),
                "text": cleaned,
                "voice": voice,
                "line_index": idx - 1,
            })
            debug_lines.append(f"{speaker}\t{voice}\t{cleaned}")
            combined += audio + AudioSegment.silent(duration=220)
            cursor_sec = end_sec + 0.22

        audio_paths = _audio_output_paths(save_dir, basename)
        selected_audio_path = audio_paths[normalized_output_format]
        export_format = {"mp3": "mp3", "wav": "wav", "m4a": "mp4"}[normalized_output_format]
        combined.export(selected_audio_path, format=export_format)
        _cleanup_extra_audio_formats(audio_paths, normalized_output_format)

        segments_path, srt_path = ("", "")
        if include_scripts:
            segments_path, srt_path = _build_scripts(save_dir, basename, segments, language)

        debug_path = save_dir / "tts_input_debug.txt"
        debug_path.write_text("\n".join(debug_lines), encoding="utf-8")

        return {
            "audio_file_path": str(selected_audio_path),
            "mp3_path": str(audio_paths["mp3"]) if normalized_output_format == "mp3" else "",
            "wav_path": str(audio_paths["wav"]) if normalized_output_format == "wav" else "",
            "m4a_path": str(audio_paths["m4a"]) if normalized_output_format == "m4a" else "",
            "output_format": normalized_output_format,
            "voice_map": voice_map,
            "segments_json_path": segments_path,
            "transcript_srt_path": srt_path,
            "tts_debug_file": str(debug_path),
            "warning": warning_message,
        }
    except Exception as exc:
        warning_message = f"edge_tts_fallback:{type(exc).__name__}:{exc}"
        audio_paths = _audio_output_paths(save_dir, basename)
        selected_audio_path = audio_paths[normalized_output_format]
        temp_wav_path = tmp_dir / f"{basename}.wav"
        audio = bundle_server._generate_wave_for_lines(lines)
        bundle_server._write_wav(audio, temp_wav_path)
        if normalized_output_format == "wav":
            shutil.copyfile(temp_wav_path, selected_audio_path)
        else:
            export_format = "mp3" if normalized_output_format == "mp3" else "mp4"
            AudioSegment.from_wav(temp_wav_path).export(selected_audio_path, format=export_format)
        _cleanup_extra_audio_formats(audio_paths, normalized_output_format)

        fallback_segments: list[dict[str, Any]] = []
        fallback_voice_map: dict[str, str] = {}
        cursor_sec = 0.0
        for idx, (speaker, text) in enumerate(lines, start=1):
            duration = max(1.2, min(6.0, len(text) / 8.0))
            voice = _voice_for_speaker(language, speaker, selected_voice_map)
            speaker_id = str(_speaker_numeric_id(speaker))
            fallback_voice_map[speaker_id] = voice
            fallback_segments.append({
                "speaker": speaker,
                "start_sec": round(cursor_sec, 3),
                "end_sec": round(cursor_sec + duration, 3),
                "text": text,
                "voice": f"synthetic_fallback:{voice}",
                "line_index": idx - 1,
            })
            cursor_sec += duration

        segments_path, srt_path = ("", "")
        if include_scripts:
            segments_path, srt_path = _build_scripts(save_dir, basename, fallback_segments, language)

        debug_path = save_dir / "tts_input_debug.txt"
        debug_path.write_text(
            "\n".join(
                f"{spk}\tsynthetic_fallback:{_voice_for_speaker(language, spk, selected_voice_map)}\t{txt}"
                for spk, txt in lines
            ),
            encoding="utf-8",
        )

        return {
            "audio_file_path": str(selected_audio_path),
            "mp3_path": str(audio_paths["mp3"]) if normalized_output_format == "mp3" else "",
            "wav_path": str(audio_paths["wav"]) if normalized_output_format == "wav" else "",
            "m4a_path": str(audio_paths["m4a"]) if normalized_output_format == "m4a" else "",
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

    def write_error(self, status_code: int, **kwargs: Any) -> None:
        reason = self._reason or f"HTTP {status_code}"
        exc_info = kwargs.get("exc_info")
        if exc_info:
            exception = exc_info[1]
            if isinstance(exception, HTTPError) and exception.reason:
                reason = exception.reason
            elif isinstance(exception, Exception) and str(exception):
                reason = str(exception)
        if self._finished:
            return
        self.write_json({"ok": False, "success": False, "error": reason, "status": status_code}, status=status_code)

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


class OnlineAudioConfigHandler(JsonHandler):
    def get(self) -> None:
        global _ONLINE_AUDIO_CONFIG_CACHE
        if _ONLINE_AUDIO_CONFIG_CACHE is None:
            _ONLINE_AUDIO_CONFIG_CACHE = _load_online_audio_config()
        self.write_json({"ok": True, "success": True, "config": _ONLINE_AUDIO_CONFIG_CACHE})


class PresetTopicsHandler(JsonHandler):
    def get(self) -> None:
        global _PRESET_TOPICS_CACHE
        if _PRESET_TOPICS_CACHE is None:
            _PRESET_TOPICS_CACHE = _load_preset_topics()
        self.write_json({"ok": True, "success": True, "presets": _PRESET_TOPICS_CACHE})


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
        manifest["include_scripts"] = include_scripts
        manifest["precise_duration"] = str(payload.get("precise_duration") or "").strip()
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

        try:
            _, manifest = _find_manifest(dialogue_id)
        except FileNotFoundError as exc:
            raise HTTPError(404, reason=str(exc)) from exc
        save_dir = Path(manifest.get("save_dir") or ROOT / "demo")

        if kind == "text":
            target = Path(manifest["text_path"])
        else:
            target = _resolve_audio_target(manifest, dialogue_id)

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
        try:
            payload = target.read_bytes()
        except OSError as exc:
            raise HTTPError(500, reason=f"Unable to read {kind} file: {exc}") from exc
        self.set_header("Content-Length", str(len(payload)))
        self.finish(payload)


class DialogueDetailHandler(JsonHandler):
    def get(self) -> None:
        dialogue_id = self.get_query_argument("dialogue_id", "").strip()
        if not dialogue_id:
            raise HTTPError(400, reason="dialogue_id is required")

        try:
            _, manifest = _find_manifest(dialogue_id)
        except FileNotFoundError as exc:
            raise HTTPError(404, reason=str(exc)) from exc
        text_path = Path(str(manifest.get("text_path") or ""))
        dialogue_text = text_path.read_text(encoding="utf-8") if text_path.exists() else ""
        audio_path = _resolve_audio_target(manifest, dialogue_id)

        self.write_json(
            {
                "ok": True,
                "success": True,
                "dialogue_id": dialogue_id,
                "dialogue_text": dialogue_text,
                "text_file_name": text_path.name if text_path.exists() else "",
                "audio_file_name": audio_path.name if audio_path and audio_path.exists() else "",
                "manifest": manifest,
            }
        )


class DeleteTaskHandler(JsonHandler):
    def post(self) -> None:
        payload = self.read_json()
        dialogue_id = str(payload.get("dialogue_id") or "").strip()
        if not dialogue_id:
            raise HTTPError(400, reason="dialogue_id is required")
        self.write_json({"ok": True, "success": True, **_delete_task_artifacts(dialogue_id)})


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
                polished_lines, naturalness = polish_generated_lines(
                    lines,
                    language,
                    title=str(scenario or profile.get("work_content") or ""),
                    scenario=scenario,
                    core_content=core,
                    profile=profile,
                )
                if naturalness.get("rewrite_count"):
                    lines = polished_lines
                    rewrite_info = dict(rewrite_info or {})
                    rewrite_info["naturalness_applied"] = True
                    rewrite_info["naturalness_language"] = naturalness.get("language")
                    rewrite_info["naturalness_rewrites"] = naturalness.get("rewrite_count")
                if naturalness.get("cjk_heavy"):
                    rewrite_info = dict(rewrite_info or {})
                    rewrite_info["cjk_heavy"] = True
            except Exception as exc:
                rewrite_info = dict(rewrite_info or {})
                rewrite_info["naturalness_error"] = f"{type(exc).__name__}:{exc}"
            return lines, rewrite_info

        module._generate_dialogue_lines = _patched_generate_dialogue_lines
        module._embedded_naturalness_patched = True

    if not getattr(module, "_embedded_generate_text_handler_patched", False):
        async def _patched_generate_text_post(self):
            try:
                payload = json.loads(self.request.body.decode("utf-8") or "{}")
            except Exception as exc:
                raise HTTPError(400, reason=f"Invalid JSON body: {exc}") from exc

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                functools.partial(_generate_text_payload, module, payload),
            )
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
            (r"/api/online_audio_config", OnlineAudioConfigHandler),
            (r"/api/preset_topics", PresetTopicsHandler),
            (r"/api/create_dialogue_from_text", CreateDialogueFromTextHandler),
            (r"/api/update_dialogue", UpdateDialogueHandler),
            (r"/api/generate_audio_custom", GenerateAudioCustomHandler),
            (r"/api/dialogue_detail", DialogueDetailHandler),
            (r"/api/download", DownloadHandler),
            (r"/api/delete_task", DeleteTaskHandler),
        ],
    )
    return app


def main() -> None:
    import tornado.ioloop

    host = os.environ.get("DEMO_APP_HOST", "0.0.0.0")
    port = int(os.environ.get("DEMO_APP_PORT") or os.environ.get("AUTOGATE_PORT") or "8899")

    app = make_app()
    app.listen(port, address=host)

    # Pre-warm the manifest index in the background so the first request doesn't stall
    threading.Thread(target=_ensure_manifest_cache, daemon=True, name="manifest-cache-warmer").start()

    print(f"[START] Demo server is running at http://{host}:{port}/")
    for url in local_urls(port):
        print(f"[START] Access URL: {url}")
    print(f"[START] Static assets: {active_static_dir()}")
    print(f"[START] Output directory: {ROOT / 'demo'}")

    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
