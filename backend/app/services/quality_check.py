"""LLM 生成质量门禁（精简 3A 路线，适用于云 LLM）。

保留 3 条对云 LLM 有效的规则；
Bundle 专属规则（language_mismatch / high_chinese_ratio /
scenario_placeholder_artifact / chinese_role_name_leak）不迁移——
云 LLM 不产生 Bundle 特有退化。
"""
from __future__ import annotations

import re


class QualityCheckError(Exception):
    """质量门禁触发；调用方应将任务标记为 failed。"""
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def check_quality(
    lines: list[tuple[str, str]],
    language: str,
    target_word_count: int,
) -> None:
    """对 LLM 输出执行精简质量门禁，触发时 raise QualityCheckError。

    Args:
        lines: [(speaker_id, text), ...] 解析后的对话行
        language: 语言代码（如 "zh" / "en"）
        target_word_count: 目标字数（从 target_duration_sec * 2.5 换算而来）
    """
    if not lines:
        raise QualityCheckError("empty_output", "LLM 返回了空内容")

    full_text = "\n".join(text for _, text in lines)

    # 规则 1：<<…>> 标记残留（云 LLM 偶发，保留作观察）
    if re.search(r"<<[^>]*>>", full_text):
        raise QualityCheckError(
            "core_marker_artifact",
            "对话中含 <<...>> 模板标记残留，内容不合格",
        )

    # 规则 2：唯一行率 < 60%（内容高度重复）
    total = len(lines)
    unique = len({text.strip() for _, text in lines})
    if total > 5 and unique / total < 0.60:
        raise QualityCheckError(
            "high_repetition_rate",
            f"内容高度重复：{total} 行中唯一行仅 {unique} 行（{unique/total:.0%}），低于 60% 阈值",
        )

    # 规则 3：字数严重不足（阈值 30%，与 PR #36 cloud_generation.py 一致）
    char_count = len(full_text.replace("\n", ""))
    min_chars = max(50, int(target_word_count * 0.3))
    if char_count < min_chars:
        raise QualityCheckError(
            "word_count_critical_short",
            f"内容严重不足：实际 {char_count} 字，目标 30% 门槛为 {min_chars} 字",
        )
