"""云 LLM 对话生成主模块。

生成流程（精简 3A 路线，基于质量评估结论）：
  1. 从 preset_topics.json 查场景背景
  2. 从 training_few_shot 注入 1-2 条 few-shot 样本
  3. 调用云 LLM 生成 Speaker N: 格式对话
  4. 3 条质量门禁（high_repetition_rate / word_count_critical_short / core_marker_artifact）
  5. enforce_keywords_in_lines（关键词注入，来自 multilingual_naturalness）
  6. stabilize_dialogue_constraints（中文路径幽灵 Speaker 防御，来自 multilingual_naturalness）
  7. 写 txt + manifest.json 到 save_dir，返回与 _generate_text_payload 兼容的结果字典

注：repair_dialogue_quality（Bundle 退化修复遍）不迁移——云 LLM 不产生 Bundle 特有缺陷，
repair 遍无作用对象。如后续发现云 LLM 输出有系统性问题，在此模块内扩展即可。
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
_PRESET_TOPICS_PATH = ROOT / "config" / "preset_topics.json"

# ── 语言名规范化映射 ────────────────────────────────────────────────────────────
_LANG_NAMES = {
    "Chinese": "中文（普通话）",
    "中文": "中文（普通话）",
    "中文（普通话）": "中文（普通话）",
    "English": "英语",
    "英语": "英语",
    "Japanese": "日语",
    "日语": "日语",
    "Korean": "韩语",
    "韩语": "韩语",
    "Spanish": "西班牙语",
    "French": "法语",
    "German": "德语",
}

_SPEAKER_LINE_RE = re.compile(r"^\s*Speaker\s*(\d+)\s*[:：]\s*(.+)$")


# ── 预置主题加载 ────────────────────────────────────────────────────────────────

def _load_preset_topics() -> list[dict]:
    """加载 preset_topics.json，失败时返回空列表。"""
    try:
        return json.loads(_PRESET_TOPICS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("[cloud_gen] 无法加载 preset_topics.json: %s", exc)
        return []


def _find_preset(template_label: str) -> dict | None:
    """按 label 精确查找 preset topic；找不到返回 None。"""
    if not template_label:
        return None
    for t in _load_preset_topics():
        if t.get("label") == template_label:
            return t
    return None


# ── Prompt 构建 ─────────────────────────────────────────────────────────────────

def build_dialogue_prompt(payload: dict) -> list[dict[str, str]]:
    """构造 LLM messages（system + user）。

    Args:
        payload: task_runner 传入的生成参数字典，含 title / template_label /
                 people_count / word_count / language / keyword_terms / core_content

    Returns:
        list of {"role": ..., "content": ...} 字典（供 LLMProvider.complete 使用）
    """
    from demo_app.training_few_shot import get_training_few_shot, resolve_template_id

    topic = (payload.get("title") or payload.get("scenario") or "").strip()
    template_label = (payload.get("template_label") or "").strip()
    people_count = max(1, int(payload.get("people_count") or 2))
    word_count = max(100, int(payload.get("word_count") or 1000))
    language = str(payload.get("language") or "Chinese").strip()
    keywords: list[str] = [k for k in (payload.get("keyword_terms") or []) if k and str(k).strip()]
    core_content = (payload.get("core_content") or "").strip()

    lang_display = _LANG_NAMES.get(language, language)
    # 按 150 字/分钟 估算字数对应时长，再乘以字符密度
    target_chars = max(200, int(word_count * 1.5))

    # ── System ──────────────────────────────────────────────────────────────────
    preset = _find_preset(template_label)
    system_parts: list[str] = []

    if preset:
        system_parts.append(
            f"你正在生成一段专业对话音频语料，场景：「{preset.get('label', '')}」。"
        )
        if preset.get("topic_description"):
            system_parts.append(f"场景背景：{preset['topic_description']}")
        roles = (preset.get("roles") or [])[:people_count]
        if roles:
            roles_str = "、".join(
                f"Speaker{i+1}（{r}）" for i, r in enumerate(roles)
            )
            system_parts.append(f"角色分工建议：{roles_str}")
    else:
        system_parts.append(f"你正在生成一段 {people_count} 人的专业对话音频语料。")
        if core_content:
            system_parts.append(f"对话背景与要求：{core_content}")

    system_parts.append(
        "通用生成规则：\n"
        f"- 全程使用{lang_display}，严禁混入其他语言\n"
        f"- 共 {people_count} 个说话人，编号从 Speaker 1 开始连续递增\n"
        "- 每行严格格式：Speaker N: 对话内容（N 为数字，冒号后有空格）\n"
        f"- 总字数约 {target_chars} 字，内容充实，不要用空洞套话凑字数\n"
        "- 对话要口语化、自然，有真实的信息交换、追问、反馈和推进\n"
        "- 每个说话人要有鲜明的角色立场，不能互换台词\n"
        "- 禁止在对话中出现「核心关键词：」「行动项：」等元评论文字\n"
        "- 禁止出现 <<...>> 或 【...】 等模板标记\n"
        "- 直接输出对话内容，不要添加任何标题、说明或前缀"
    )

    # ── Few-shot 注入（仅支持的语言 + 预置模板）──────────────────────────────────
    fewshot_block = ""
    if preset:
        template_id = resolve_template_id(template_label)
        if template_id:
            # language 规范化为短码
            lang_map = {
                "Chinese": "zh", "中文": "zh", "中文（普通话）": "zh",
                "English": "en", "英语": "en",
                "Japanese": "ja", "日语": "ja",
                "Korean": "ko", "韩语": "ko",
            }
            lang_code_for_fewshot = lang_map.get(language, "zh")
            example = get_training_few_shot(template_id, lang_code_for_fewshot)
            if example:
                fewshot_block = (
                    "\n\n以下是同场景的真实对话样本，请参考其口语化风格、角色立场差异和信息密度，"
                    "生成内容不同但风格接近的新对话：\n\n"
                    f"【参考样本】\n{example}"
                )

    system = "\n\n".join(system_parts) + fewshot_block

    # ── User ────────────────────────────────────────────────────────────────────
    user_parts: list[str] = [f"本次对话的具体主题：{topic or template_label or '专业业务讨论'}"]

    # 合并 preset 核心关键词 + 用户传入关键词
    all_keywords = list(preset.get("core_keywords") or [] if preset else [])
    for kw in keywords:
        if kw not in all_keywords:
            all_keywords.append(kw)
    if all_keywords:
        user_parts.append(f"对话中需自然涉及以下关键词（融入语境，不要生硬堆砌）：{', '.join(all_keywords)}")

    user_parts.append("请直接输出对话内容，不要任何额外说明。")

    return [
        {"role": "system", "content": system},
        {"role": "user",   "content": "\n".join(user_parts)},
    ]


# ── 对话解析 ─────────────────────────────────────────────────────────────────────

def _parse_dialogue(text: str) -> list[tuple[str, str]]:
    """将 LLM 输出解析为 [(speaker_id, line_text), ...]。"""
    lines: list[tuple[str, str]] = []
    for raw in text.splitlines():
        m = _SPEAKER_LINE_RE.match(raw)
        if m:
            lines.append((m.group(1), m.group(2).strip()))
    return lines


# ── 质量门禁（精简 3 条，适用于云 LLM）────────────────────────────────────────────

class QualityGateError(ValueError):
    """质量门禁触发，任务应标记为 failed。"""


def _check_quality_gates(
    lines: list[tuple[str, str]],
    language: str,
    target_word_count: int,
) -> None:
    """精简 3 条质量门禁。触发时 raise QualityGateError。

    保留规则：
      1. core_marker_artifact  — 对话中出现 <<...>> 模板标记
      2. high_repetition_rate  — 唯一行率 < 60%（内容高度重复）
      3. word_count_critical_short — 实际字数 < 目标的 30%
    """
    if not lines:
        raise QualityGateError("LLM 返回了空内容，无法生成对话")

    full_text = "\n".join(text for _, text in lines)

    # 1. 模板标记残留
    if re.search(r"<<[^>]*>>", full_text):
        raise QualityGateError(
            "对话中包含 <<...>> 模板标记残留，内容不合格"
        )

    # 2. 重复率
    total = len(lines)
    unique = len({text.strip() for _, text in lines})
    if total > 5 and unique / total < 0.60:
        raise QualityGateError(
            f"内容高度重复：共 {total} 行但唯一行只有 {unique} 行（{unique/total:.0%}），"
            "低于 60% 阈值"
        )

    # 3. 字数严重不足
    char_count = len(full_text.replace("\n", ""))
    min_chars = max(50, int(target_word_count * 0.3))
    if char_count < min_chars:
        raise QualityGateError(
            f"内容严重不足：实际 {char_count} 字，目标 {target_word_count} 字的 30% 门槛为 {min_chars} 字"
        )


# ── 精简后处理（3A 路线）──────────────────────────────────────────────────────────

def _apply_lite_postprocess(
    lines: list[tuple[str, str]],
    payload: dict,
) -> list[tuple[str, str]]:
    """精简后处理：关键词注入 + 中文稳定化（跳过 repair 遍）。

    云 LLM 输出干净，不需要 repair_dialogue_quality（Bundle 退化修复专用）。
    """
    language = str(payload.get("language") or "Chinese")
    keywords: list[str] = [k for k in (payload.get("keyword_terms") or []) if k and str(k).strip()]
    title = (payload.get("title") or "").strip()
    scenario = (payload.get("scenario") or "").strip()
    core_content = (payload.get("core_content") or "").strip()
    people_count = int(payload.get("people_count") or len({sp for sp, _ in lines}) or 2)
    word_count = int(payload.get("word_count") or 1000)

    try:
        from demo_app.multilingual_naturalness import (
            enforce_keywords_in_lines,
            stabilize_dialogue_constraints,
        )
        # 1. 关键词注入
        if keywords:
            lines, _ = enforce_keywords_in_lines(
                lines, keywords, language,
                title=title, scenario=scenario, core_content=core_content,
            )
        # 2. 中文稳定化（非中文 early return，无副作用）
        lines, _ = stabilize_dialogue_constraints(
            lines, language,
            title=title, scenario=scenario, core_content=core_content,
            target_word_count=word_count, people_count=people_count,
            keywords=keywords,
        )
    except Exception as exc:
        # 后处理失败不阻断主流程，记录警告继续
        logger.warning("[cloud_gen] 后处理异常（已跳过）: %s", exc)

    return lines


# ── 主函数 ───────────────────────────────────────────────────────────────────────

def generate_text_cloud_llm(payload: dict, save_dir: Path) -> dict:
    """云 LLM 对话生成主入口（同步函数，由 run_in_executor 在线程池执行）。

    Args:
        payload: 与 _generate_text_payload 相同的参数字典。
        save_dir: 文本输出目录（由 task_runner 传入，通常是 storage/generated/<task_id>/）。

    Returns:
        与 _generate_text_payload 返回值兼容的字典：
        {
            "ok": True,
            "dialogue_id": "xxxxxxxx",
            "dialogue_text": "Speaker 1: ...\nSpeaker 2: ...",
            "text_path": str(txt_path),
            "basename": basename,
        }

    Raises:
        QualityGateError: 质量门禁触发（调用方标记任务 failed）
        Exception:        LLM 调用失败（调用方可选择 bundle 降级）
    """
    from demo_app.providers.llm.factory import get_llm_provider

    # ── 获取 Provider ────────────────────────────────────────────────────────
    # factory 已从 runtime.yaml 读取配置，task_runner 调用前已确认 provider 非空
    provider = get_llm_provider()
    if provider is None:
        raise RuntimeError("云 LLM 未配置（llm.provider 为空）")

    topic = (payload.get("title") or payload.get("scenario") or "dialogue").strip()
    word_count = int(payload.get("word_count") or 1000)

    # ── 构建并调用 LLM ───────────────────────────────────────────────────────
    from demo_app.providers.llm.base import LLMMessage
    raw_messages = build_dialogue_prompt(payload)
    messages = [LLMMessage(role=m["role"], content=m["content"]) for m in raw_messages]

    logger.info("[cloud_gen] 调用云 LLM, topic=%s, people=%s, words=%s",
                topic, payload.get("people_count"), word_count)
    result = provider.complete(messages)

    if not result.text.strip():
        raise ValueError("云 LLM 返回了空内容")

    # ── 解析对话行 ───────────────────────────────────────────────────────────
    lines = _parse_dialogue(result.text)
    if not lines:
        raise ValueError(
            "云 LLM 输出未识别到任何 'Speaker N: 内容' 格式的行，"
            "原始输出（前 300 字）：" + result.text[:300]
        )

    # ── 质量门禁 ─────────────────────────────────────────────────────────────
    _check_quality_gates(lines, payload.get("language", "Chinese"), word_count)

    # ── 精简后处理（关键词注入 + 中文稳定化）────────────────────────────────
    lines = _apply_lite_postprocess(lines, payload)

    # ── 重建对话文本 ─────────────────────────────────────────────────────────
    dialogue_text = "\n".join(f"Speaker {sp}: {txt}" for sp, txt in lines)

    # ── 写文件 ───────────────────────────────────────────────────────────────
    dialogue_id = uuid.uuid4().hex[:8]
    safe_topic = re.sub(r"[^\w一-龥\-]", "_", topic[:40]).strip("_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    basename = f"{safe_topic}_{ts}" if safe_topic else ts

    save_dir.mkdir(parents=True, exist_ok=True)
    txt_path = save_dir / f"{basename}.txt"
    txt_path.write_text(dialogue_text, encoding="utf-8")

    # 写 manifest.json（与 bundle 路径格式兼容，供 manifest cache 索引）
    manifest = {
        "dialogue_id": dialogue_id,
        "topic": topic,
        "language": payload.get("language", "Chinese"),
        "people_count": payload.get("people_count", 2),
        "word_count": word_count,
        "llm_provider": "cloud",
        "llm_model": result.model,
        "text_path": str(txt_path),
        "basename": basename,
        "generated_at": datetime.now().isoformat(),
    }
    manifest_path = save_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info(
        "[cloud_gen] 生成完成: %d 行，%d 字，model=%s，文件=%s",
        len(lines), len(dialogue_text), result.model, txt_path.name,
    )

    return {
        "ok": True,
        "dialogue_id": dialogue_id,
        "dialogue_text": dialogue_text,
        "text_path": str(txt_path),
        "basename": basename,
    }
