"""对话文本生成。

当前 MVP 版本：单次 LLM 调用，按主题模板和说话人数生成对话。
后续可在此处接入：
- 三遍后处理 (repair → keywords → stabilize)
- few-shot 检索
- 9 条质量门禁规则
"""
from __future__ import annotations

import re

from app.providers.llm import LLMMessage, LLMProvider
from app.services.few_shot import retrieve as retrieve_few_shot
from app.services.preset_topics import get_preset_by_id

_LANG_NAMES = {
    "zh": "中文（普通话）",
    "en": "英语",
    "ja": "日语",
    "ko": "韩语",
    "es": "西班牙语",
    "fr": "法语",
    "de": "德语",
    "pt": "葡萄牙语",
    "it": "意大利语",
    "ru": "俄语",
    "ar": "阿拉伯语",
    "id": "印度尼西亚语",
}

_SPEAKER_LINE_RE = re.compile(r"^\s*Speaker\s*(\d+)\s*[:：]\s*(.+)$")


def build_prompt(
    template: str,
    custom_prompt: str | None,
    topic: str,
    language: str,
    speaker_count: int,
    target_duration_sec: int,
    keywords: list[str],
) -> list[LLMMessage]:
    """构造 LLM prompt。

    - template == "custom"：完全用 custom_prompt 作为额外指令
    - template == 其他 id：从 preset_topics.json 拿出 roles / topic_description / core_keywords
      作为上下文喂给 LLM
    """
    lang_name = _LANG_NAMES.get(language, language)
    # 按 150 字/分钟估算
    target_chars = max(50, int(target_duration_sec * 2.5))

    preset = None if template == "custom" else get_preset_by_id(template)

    # ---- System ----
    system_parts: list[str] = []
    if preset:
        system_parts.append(
            f"你正在为「{preset.get('label', '')}」场景生成一段 {speaker_count} 人对话。"
        )
        if preset.get("topic_description"):
            system_parts.append(f"场景背景：{preset['topic_description']}")
        roles = preset.get("roles") or []
        if roles:
            # 取前 speaker_count 个角色
            picked = roles[:speaker_count]
            roles_str = " / ".join(f"Speaker{i+1}={r}" for i, r in enumerate(picked))
            system_parts.append(f"角色分配建议：{roles_str}")
    else:
        # 自定义模式
        system_parts.append(f"你正在生成一段 {speaker_count} 人对话。")
        if custom_prompt:
            system_parts.append(f"用户需求：{custom_prompt}")

    system_parts.append(
        "通用要求：\n"
        f"- 全程使用{lang_name}，不要混入其他语言\n"
        f"- 共 {speaker_count} 个说话人，编号从 Speaker1 开始连续\n"
        f"- 每行格式严格为: Speaker N: 对话内容\n"
        f"- 总字数约 {target_chars} 字\n"
        "- 内容自然口语化，避免书面化、过度礼貌、AI 腔\n"
        "- 话题切换要合理，符合真实交流节奏"
    )

    # ---- Few-shot 例子（仅预设模板 + 支持的语言）----
    fewshot_block = ""
    if preset:
        # 估算 target_words：用 target_chars / 1.5（中文）或 / 4（英文）粗略换算
        target_words = max(50, int(target_chars / (1.5 if language == "zh" else 4)))
        examples = retrieve_few_shot(
            topic_id=template,
            language=language,
            k=2,                      # 注入 2 段，避免 prompt 太长
            max_chars_each=900,
            target_words=target_words,
        )
        if examples:
            fewshot_block = (
                "\n\n以下是同场景的真实对话样本（参考其风格、口吻、信息密度，但生成不同的内容）：\n\n"
                + "\n\n---\n\n".join(f"【样本 {i+1}】\n{ex}" for i, ex in enumerate(examples))
            )

    system = "\n\n".join(system_parts) + fewshot_block

    # ---- User ----
    user_lines = [f"本次对话的具体主题：{topic}"]

    # 关键词：合并 preset.core_keywords + 用户传入的 keywords，去重
    all_keywords: list[str] = []
    if preset:
        for k in preset.get("core_keywords", []):
            if k and k not in all_keywords:
                all_keywords.append(k)
    for k in keywords:
        if k and k not in all_keywords:
            all_keywords.append(k)
    if all_keywords:
        user_lines.append(f"对话需自然涉及以下关键词：{', '.join(all_keywords)}")

    user_lines.append("请直接输出对话内容，不要添加任何说明、标题或前缀。")

    return [
        LLMMessage(role="system", content=system),
        LLMMessage(role="user", content="\n".join(user_lines)),
    ]


def parse_dialogue(text: str, expected_speaker_count: int) -> list[tuple[str, str]]:
    """解析为 [(speaker_id, line_text), ...]，并校验格式。

    返回的 speaker_id 为 "1"/"2"/... 字符串。
    """
    lines: list[tuple[str, str]] = []
    for raw in text.splitlines():
        m = _SPEAKER_LINE_RE.match(raw)
        if m:
            lines.append((m.group(1), m.group(2).strip()))
    if not lines:
        raise ValueError("LLM 输出未识别到任何 Speaker N: 格式的行")

    speakers = {sid for sid, _ in lines}
    if len(speakers) > expected_speaker_count:
        raise ValueError(
            f"实际出现 {len(speakers)} 个说话人，超过预期 {expected_speaker_count} 个"
        )
    return lines


def generate_dialogue(
    llm: LLMProvider,
    template: str,
    custom_prompt: str | None,
    topic: str,
    language: str,
    speaker_count: int,
    target_duration_sec: int,
    keywords: list[str],
) -> tuple[str, list[tuple[str, str]]]:
    """调用 LLM 生成对话，返回 (原始文本, 解析后的行)。"""
    messages = build_prompt(
        template=template,
        custom_prompt=custom_prompt,
        topic=topic,
        language=language,
        speaker_count=speaker_count,
        target_duration_sec=target_duration_sec,
        keywords=keywords,
    )
    result = llm.complete(messages)
    if not result.text.strip():
        raise ValueError("LLM 返回空内容")
    parsed = parse_dialogue(result.text, speaker_count)
    return result.text, parsed
