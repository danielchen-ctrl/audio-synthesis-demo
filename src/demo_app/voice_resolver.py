"""
demo_app/voice_resolver.py
==========================
统一音色解析入口，兼容新格式（voice_assignments）和旧格式（voice_map）。

调用方一览：
  - task_runner.py：从 DB 读取 voice_assignments / voice_map，按 speaker_id 解析
  - embedded_server_main.py（Phase 2 后接入）：legacy modal payload 解析
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from demo_app.tts_provider import VoiceSpec

logger = logging.getLogger(__name__)


# ── CosyVoice 已注册克隆音色目录 ─────────────────────────────────────────────
# 单一来源：config/runtime.yaml 的 tts.real_human.voice_catalog
# 新增/修改音色只需改 yaml，重启服务即可生效（前后端自动同步）。
#
# 服务器上注册了多个同名 "李四" voice_id（共 8 个，同一克隆人多次注册），
# 实测 3 个返回 500、5 个可用。yaml 中只挂载 created_at 最晚的 ed35d3674bb0
# （推测为最终调优版）。备用 voice_id 见 runtime.yaml 注释。

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "runtime.yaml"


def _load_voice_catalog_from_yaml() -> dict[str, list[dict]]:
    """
    从 runtime.yaml 加载 voice_catalog；失败时返回空 dict（fail-safe）。
    返回结构与历史硬编码一致：{language: [{voice_id, name, gender}, ...]}
    """
    try:
        import yaml
    except ImportError:
        logger.error("[voice_resolver] PyYAML 未安装，无法加载 voice_catalog")
        return {}
    if not _CONFIG_PATH.exists():
        logger.warning("[voice_resolver] %s 不存在，voice_catalog 为空", _CONFIG_PATH)
        return {}
    try:
        cfg = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.error("[voice_resolver] 解析 %s 失败: %s", _CONFIG_PATH, exc)
        return {}
    raw = cfg.get("tts", {}).get("real_human", {}).get("voice_catalog", {}) or {}
    # 字段标准化：兼容 yaml 中 voice_id 写成数字 / 缺 gender 等场景
    normalized: dict[str, list[dict]] = {}
    for lang, entries in raw.items():
        if not isinstance(entries, list):
            continue
        cleaned = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            vid = str(e.get("voice_id", "")).strip()
            name = str(e.get("name", "")).strip()
            if not vid or not name:
                continue
            cleaned.append({
                "voice_id": vid,
                "name":     name,
                "gender":   str(e.get("gender", "female")).strip() or "female",
            })
        if cleaned:
            normalized[lang] = cleaned
    logger.info(
        "[voice_resolver] 加载 voice_catalog: %s",
        {k: [v["name"] for v in vs] for k, vs in normalized.items()},
    )
    return normalized


COSYVOICE_VOICE_CATALOG: dict[str, list[dict]] = _load_voice_catalog_from_yaml()


def reload_voice_catalog() -> dict[str, list[dict]]:
    """重新从 yaml 加载并更新模块级 COSYVOICE_VOICE_CATALOG。供测试 / hot-reload 使用。"""
    global COSYVOICE_VOICE_CATALOG
    new_catalog = _load_voice_catalog_from_yaml()
    COSYVOICE_VOICE_CATALOG.clear()
    COSYVOICE_VOICE_CATALOG.update(new_catalog)
    return COSYVOICE_VOICE_CATALOG


def _get_cosyvoice_api_url() -> str:
    """从 runtime.yaml 读取 CosyVoice API URL（优先环境变量）。"""
    import os
    env_url = os.environ.get("REAL_HUMAN_TTS_API_URL", "").strip()
    if env_url:
        return env_url
    try:
        import yaml
        cfg = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        return (cfg.get("tts", {}).get("real_human", {}).get("api_url", "") or "").strip()
    except Exception:
        return ""


def _save_voice_catalog_to_yaml(catalog: dict) -> None:
    """
    将 voice_catalog 写回 runtime.yaml，**只替换 voice_catalog 块**，
    保留文件中所有其他配置和注释（包括备用/失效 voice_id 注释）。

    实现：逐行定位 `    voice_catalog:` 行，替换该行到下一个同级或更高级 key 之间的内容，
    不触碰文件其他部分。
    """
    try:
        import yaml
    except ImportError:
        logger.error("[voice_resolver] PyYAML 未安装，无法保存 voice_catalog")
        return
    try:
        text = _CONFIG_PATH.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error("[voice_resolver] 读取 %s 失败: %s", _CONFIG_PATH, exc)
        raise

    lines = text.splitlines(keepends=True)

    # 找到 `    voice_catalog:` 行（real_human 下 4-space indent）
    start_idx: int | None = None
    for i, line in enumerate(lines):
        if line.rstrip() == "    voice_catalog:":
            start_idx = i
            break

    if start_idx is None:
        # 块不存在，回退全量写入（注释丢失，但极少发生）
        logger.warning("[voice_resolver] 未找到 voice_catalog 块，回退全量写入（注释将丢失）")
        try:
            cfg = yaml.safe_load(text) or {}
            cfg.setdefault("tts", {}).setdefault("real_human", {})["voice_catalog"] = catalog
            _CONFIG_PATH.write_text(
                yaml.dump(cfg, allow_unicode=True, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("[voice_resolver] 保存 voice_catalog 失败: %s", exc)
            raise
        return

    # 找到 voice_catalog 块的结束行：下一个 indent ≤ 4 的非空非注释行，或 EOF
    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        stripped = lines[i].lstrip()
        if not stripped or stripped.startswith("#"):
            continue  # 空行和注释行不终止块
        leading = len(lines[i]) - len(stripped)
        if leading <= 4:
            end_idx = i
            break

    # 生成新的 voice_catalog YAML 块（4-space 缩进）
    catalog_yaml = yaml.dump(
        {"voice_catalog": catalog},
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    new_block_lines = [
        ("    " + l if l.strip() else l) + "\n"
        for l in catalog_yaml.splitlines()
    ]

    new_lines = lines[:start_idx] + new_block_lines + lines[end_idx:]
    try:
        _CONFIG_PATH.write_text("".join(new_lines), encoding="utf-8")
        logger.info("[voice_resolver] voice_catalog 已保存到 %s（注释已保留）", _CONFIG_PATH)
    except Exception as exc:
        logger.error("[voice_resolver] 写入 %s 失败: %s", _CONFIG_PATH, exc)
        raise


def create_voice_in_catalog(language: str, voice_id: str, name: str, gender: str = "female") -> None:
    """将新音色添加到 voice_catalog，保存 yaml，并热重载模块级变量。"""
    try:
        import yaml
        cfg = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        catalog: dict = cfg.get("tts", {}).get("real_human", {}).get("voice_catalog", {}) or {}
    except Exception:
        catalog = {}

    entries = catalog.setdefault(language, [])
    # 避免重复插入同一 voice_id
    if not any(str(v.get("voice_id", "")) == voice_id for v in entries):
        entries.append({"voice_id": voice_id, "name": name, "gender": gender})

    _save_voice_catalog_to_yaml(catalog)
    reload_voice_catalog()
    logger.info("[voice_resolver] 新音色已注册: %s / %s (%s) lang=%s", name, voice_id, gender, language)


def delete_voice_from_catalog(voice_id: str) -> bool:
    """从 voice_catalog 移除指定 voice_id，保存 yaml，并热重载。返回是否找到并删除。"""
    try:
        import yaml
        cfg = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        catalog: dict = cfg.get("tts", {}).get("real_human", {}).get("voice_catalog", {}) or {}
    except Exception:
        return False

    found = False
    for lang in list(catalog.keys()):
        before_len = len(catalog[lang])
        catalog[lang] = [v for v in catalog[lang] if str(v.get("voice_id", "")) != voice_id]
        if len(catalog[lang]) < before_len:
            found = True
        if not catalog[lang]:
            del catalog[lang]

    if found:
        _save_voice_catalog_to_yaml(catalog)
        reload_voice_catalog()
        logger.info("[voice_resolver] 音色已删除: %s", voice_id)
    return found


def get_voice_catalog_for_frontend() -> dict[str, list[dict]]:
    """
    生成前端友好格式：{language: [{value, label, gender, name}, ...]}
    label 形如 "maryzhang（女·真人）" — 在后端集中拼装，避免前端格式漂移。
    """
    _GENDER_CN = {"female": "女", "male": "男"}
    out: dict[str, list[dict]] = {}
    for lang, voices in COSYVOICE_VOICE_CATALOG.items():
        out[lang] = [
            {
                "value":  v["voice_id"],
                "name":   v["name"],
                "gender": v.get("gender", "female"),
                "label":  f"{v['name']}（{_GENDER_CN.get(v.get('gender', 'female'), '女')}·真人）",
            }
            for v in voices
        ]
    return out

# edge_tts 各语言默认音色（语言无真人音色时回退）
EDGE_DEFAULT_VOICES: dict[str, str] = {
    "Chinese":    "zh-CN-XiaoxiaoNeural",
    "English":    "en-US-JennyNeural",
    "Japanese":   "ja-JP-NanamiNeural",
    "Korean":     "ko-KR-SunHiNeural",
    "Spanish":    "es-ES-ElviraNeural",
    "French":     "fr-FR-DeniseNeural",
    "German":     "de-DE-KatjaNeural",
    "Portuguese": "pt-BR-FranciscaNeural",
    "Russian":    "ru-RU-SvetlanaNeural",
    "Cantonese":  "zh-HK-HiuGaaiNeural",
    "Italian":    "it-IT-ElsaNeural",
    "Arabic":     "ar-SA-ZariyahNeural",
    "Indonesian": "id-ID-GadisNeural",
}


# ── 公共函数 ──────────────────────────────────────────────────────────────────

def default_voice_spec(
    language: str,
    speaker_id: str,
    effective_provider: str = "edge_tts",
) -> VoiceSpec:
    """
    按语言自动分配默认音色。
    - real_human：从 COSYVOICE_VOICE_CATALOG 按 speaker 序号轮转
    - 无真人音色时自动回退 edge_tts
    """
    if effective_provider == "real_human":
        voices = COSYVOICE_VOICE_CATALOG.get(language, [])
        if voices:
            try:
                idx = (int(speaker_id) - 1) % len(voices)
            except (ValueError, TypeError):
                idx = 0
            v = voices[idx]
            return VoiceSpec(
                provider="real_human",
                voice_id=v["voice_id"],
                language=language,
                gender=v.get("gender", "female"),
            )
        # 该语言没有真人音色 → 自动回退 edge_tts，记录 warning
        logger.warning(
            "[voice_resolver] 语言 '%s' 无真人克隆音色，speaker=%s 回退 edge_tts",
            language, speaker_id,
        )
        effective_provider = "edge_tts"

    voice_id = EDGE_DEFAULT_VOICES.get(language, "zh-CN-XiaoxiaoNeural")
    return VoiceSpec(
        provider="edge_tts",
        voice_id=voice_id,
        language=language,
    )


def resolve_voice_spec(
    speaker_id: str,
    language: str,
    voice_assignments: Optional[dict] = None,
    voice_map: Optional[dict] = None,
    effective_provider: str = "edge_tts",
) -> VoiceSpec:
    """
    统一音色解析。优先级：
      1. voice_assignments（新格式，精确指定 provider + voice_id）
      2. voice_map（旧格式，仅 edge_tts，只读不写）
      3. default_voice_spec（按语言自动分配）
    """
    # 1. 新格式 voice_assignments
    if voice_assignments and speaker_id in voice_assignments:
        spec = VoiceSpec.from_dict(
            voice_assignments[speaker_id],
            language=language,
            fallback_provider=effective_provider,
        )
        # 安全校验：real_human voice_id 必须在全局已注册音色中。
        # CosyVoice zero_shot 支持跨语言合成，允许用英文克隆音色合成中文（反之亦然），
        # 因此只检查 voice_id 是否在全局目录中注册，不限制必须属于当前语言。
        if spec.provider == "real_human":
            all_valid_ids = {
                v["voice_id"]
                for lang_voices in COSYVOICE_VOICE_CATALOG.values()
                for v in lang_voices
            }
            if all_valid_ids and spec.voice_id not in all_valid_ids:
                logger.warning(
                    "[voice_resolver] voice_id=%s 未在全局音色目录中注册，自动替换为默认音色",
                    spec.voice_id,
                )
                return default_voice_spec(language, speaker_id, effective_provider)
        return spec
    # 2. 旧格式 voice_map（只读）
    if voice_map and speaker_id in voice_map:
        return VoiceSpec(
            provider="edge_tts",
            voice_id=voice_map[speaker_id],
            language=language,
        )
    # 3. 自动分配
    return default_voice_spec(language, speaker_id, effective_provider)


def build_synthesis_requests(
    line_tuples: list[tuple[str, str]],
    language: str,
    voice_assignments: Optional[dict],
    voice_map: Optional[dict],
    effective_provider: str,
    max_chars: int = 500,
) -> list:
    """
    将对话行列表转换为 SynthesisRequest 列表。
    相同 speaker 的连续行合并为一个 SynthesisRequest（段落级合并）。
    单个 Request 超过 max_chars 时在换行处切段。

    返回 list[SynthesisRequest]（避免循环导入，动态导入）。
    """
    from demo_app.tts_provider import SynthesisRequest

    if not line_tuples:
        return []

    requests = []
    cur_speaker, cur_segments, cur_indices = "", [], []

    def _flush():
        if not cur_speaker or not cur_segments:
            return
        spec = resolve_voice_spec(
            # speaker_id 取纯数字部分，兼容 "Speaker 1" 格式
            speaker_id=_extract_speaker_num(cur_speaker),
            language=language,
            voice_assignments=voice_assignments,
            voice_map=voice_map,
            effective_provider=effective_provider,
        )
        requests.append(SynthesisRequest(
            speaker=cur_speaker,
            segments=list(cur_segments),
            voice_spec=spec,
            line_indices=list(cur_indices),
        ))

    for i, (speaker, text) in enumerate(line_tuples):
        if speaker != cur_speaker:
            _flush()
            cur_speaker = speaker
            cur_segments = []
            cur_indices = []

        # 超过 max_chars 切段
        if cur_segments and sum(len(s) for s in cur_segments) + len(text) > max_chars:
            _flush()
            cur_speaker = speaker
            cur_segments = []
            cur_indices = []

        cur_segments.append(text)
        cur_indices.append(i)

    _flush()
    return requests


def _extract_speaker_num(speaker: str) -> str:
    """从 'Speaker 1' 提取 '1'，兼容其他格式。"""
    import re
    m = re.search(r"\d+", speaker)
    return m.group() if m else speaker
