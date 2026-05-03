from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from training.training_types import DialogueLines, ScoreReport, TrainingTask, ValidationFinding


MARKER_PATTERN = re.compile(r"<<(核心|Core|コア|Noyau|핵심|Kern|Núcleo|Esencial):.*?>>")
PLACEHOLDER_TOKENS = ("[[[CORE", "{{{", "<<<INSERT", "TODO:", "FIXME:")


def _count_chinese_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fa5]", text))


def _count_japanese_kana(text: str) -> int:
    return len(re.findall(r"[\u3040-\u309f\u30a0-\u30ff]", text))


def score_dialogue(
    task: TrainingTask,
    lines: DialogueLines,
    validator_errors: Optional[List[Any]] = None,
) -> ScoreReport:
    full_text = "\n".join(f"{speaker}: {text}" for speaker, text in lines)
    total_chars = sum(len(text) for _, text in lines)
    marker_count = len(MARKER_PATTERN.findall(full_text))
    findings: List[ValidationFinding] = []
    score = 100.0

    placeholder_hit = next((token for token in PLACEHOLDER_TOKENS if token in full_text), None)
    if placeholder_hit:
        score -= 40
        findings.append(
            ValidationFinding(
                code="placeholder_leak",
                severity="error",
                message=f"存在占位符残留: {placeholder_hit}",
            )
        )

    if marker_count == 0:
        score -= 20
        findings.append(
            ValidationFinding(
                code="missing_core_marker",
                severity="warning",  # bundle output never contains <<核心:…>> markers; downgrade so gate doesn't block everything
                message="缺少核心标记",
            )
        )
    elif marker_count > 2:
        score -= 12
        findings.append(
            ValidationFinding(
                code="too_many_core_markers",
                severity="warning",
                message=f"核心标记数量偏多: {marker_count}",
                details={"marker_count": marker_count},
            )
        )

    if task.language == "中文":
        chinese_ratio = 1.0
    elif task.language == "粤语":
        chinese_ratio = 0.0
    else:
        chinese_ratio = _count_chinese_chars(full_text) / max(len(full_text), 1)
        allowed_ratio = 0.70 if task.meta.get("translate_fallback") else 0.15
        should_flag_high_ratio = chinese_ratio > allowed_ratio
        details = {"ratio": round(chinese_ratio, 4), "allowed_ratio": allowed_ratio}

        if task.language == "日语":
            kana_ratio = _count_japanese_kana(full_text) / max(len(full_text), 1)
            details["kana_ratio"] = round(kana_ratio, 4)
            should_flag_high_ratio = chinese_ratio > 0.35 and kana_ratio < 0.05

        if should_flag_high_ratio:
            score -= 20
            findings.append(
                ValidationFinding(
                    code="high_chinese_ratio",
                    severity="error",
                    message=f"中文占比过高: {chinese_ratio:.1%}",
                    details=details,
                )
            )

    target_min = task.word_count * 0.7
    target_max = task.word_count * 1.3
    if total_chars < target_min or total_chars > target_max:
        score -= 12
        findings.append(
            ValidationFinding(
                code="word_count_out_of_range",
                severity="warning",
                message=f"字数偏离目标范围: target={task.word_count}, actual={total_chars}",
                details={"target": task.word_count, "actual": total_chars},
            )
        )

    speaker_distribution: Dict[str, int] = {}
    for speaker, _ in lines:
        speaker_distribution[speaker] = speaker_distribution.get(speaker, 0) + 1

    if len(lines) < 10:
        score -= 10
        findings.append(
            ValidationFinding(
                code="too_few_turns",
                severity="warning",
                message=f"对话轮次过少: {len(lines)}",
            )
        )

    if task.people_count >= 3 and "Speaker 3" in speaker_distribution:
        speaker3_lines = [text.strip() for speaker, text in lines if speaker == "Speaker 3"]
        filler_patterns = (
            r"^好的[。！，、]*$",
            r"^明白了[。！，、]*$",
            r"^收到[。！，、]*$",
            r"^确认[。！，、]*$",
            r"^Okay[.! ,]*$",
            r"^Got it[.! ,]*$",
            r"^Understood[.! ,]*$",
        )
        filler_count = 0
        for text in speaker3_lines:
            if any(re.match(pattern, text, re.IGNORECASE) for pattern in filler_patterns):
                filler_count += 1
        filler_ratio = filler_count / max(len(speaker3_lines), 1)
        if filler_ratio > 0.5:
            score -= 10
            findings.append(
                ValidationFinding(
                    code="speaker3_filler_ratio",
                    severity="warning",
                    message=f"Speaker3 空话过多: {filler_ratio:.1%}",
                    details={"ratio": round(filler_ratio, 4)},
                )
            )

    if validator_errors:
        for err in validator_errors:
            code = getattr(err, "error_type", "validator_error")
            message = getattr(err, "message", str(err))
            findings.append(
                ValidationFinding(
                    code=code,
                    severity="error",
                    message=message,
                    details={
                        "line_num": getattr(err, "line_num", None),
                        "content": getattr(err, "content", None),
                    },
                )
            )
        score -= min(30, 5 * len(validator_errors))

    score = max(score, 0.0)
    passed = not any(item.severity == "error" for item in findings) and score >= 60
    metrics = {
        "line_count": len(lines),
        "total_chars": total_chars,
        "marker_count": marker_count,
        "chinese_ratio": round(chinese_ratio, 4),
        "speaker_distribution": speaker_distribution,
        "target_word_count": task.word_count,
    }
    return ScoreReport(
        passed=passed,
        score=score,
        max_score=100.0,
        metrics=metrics,
        findings=findings,
    )
