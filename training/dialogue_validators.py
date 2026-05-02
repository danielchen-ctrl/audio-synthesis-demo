# -*- coding: utf-8 -*-
"""对话校验器与质量门。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from training.role_cards import get_all_forbidden_phrases, get_role_cards
from training.training_types import DialogueLines, TrainingTask


class ValidationError:
    def __init__(self, error_type: str, message: str, line_num: int = None, content: str = None):
        self.error_type = error_type
        self.message = message
        self.line_num = line_num
        self.content = content

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "line_num": self.line_num,
            "content": self.content,
        }


def validate_dialogue(dialogue_text: str, scene_id: str, role_cards: List = None) -> Tuple[bool, List[ValidationError]]:
    errors: List[ValidationError] = []
    if role_cards is None:
        role_cards = get_role_cards(scene_id)

    lines = dialogue_text.strip().split("\n")
    valid_names = {role.name for role in role_cards}
    valid_identities = {role.identity for role in role_cards}
    forbidden_placeholders = [
        "Speaker 1",
        "Speaker 2",
        "Speaker 3",
        "对话方",
        "第三方",
        "第三方顾问",
        "第三方/顾问",
        "客户代表",
        "顾问代表",
    ]

    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        for placeholder in forbidden_placeholders:
            if placeholder in line:
                errors.append(ValidationError("角色占位符", f"第{i}行包含禁止的占位符: {placeholder}", i, line[:100]))
        match = re.match(r"^([^:：]+)[:：]", line)
        if match:
            speaker_label = match.group(1).strip()
            has_valid_name = any(name in speaker_label for name in valid_names)
            has_valid_identity = any(identity in speaker_label for identity in valid_identities)
            if role_cards and not (has_valid_name or has_valid_identity):
                errors.append(ValidationError("角色名称不匹配", f"第{i}行speaker名称不在角色卡中: {speaker_label}", i, line[:100]))

    speaker_lines: Dict[str, List[Tuple[int, str]]] = {}
    for i, line in enumerate(lines, 1):
        match = re.match(r"^([^:：]+)[:：]", line)
        if not match:
            continue
        speaker = match.group(1).strip()
        text = re.split(r"[:：]", line, maxsplit=1)[-1].strip()
        speaker_lines.setdefault(speaker, []).append((i, text))

    for speaker, speaker_texts in speaker_lines.items():
        total_lines = len(speaker_texts)
        if total_lines >= 3:
            first_person_count = sum(1 for _, text in speaker_texts if "我" in text)
            if first_person_count < total_lines // 3:
                errors.append(ValidationError("人称使用不足", f"speaker '{speaker}' 第一人称使用不足（{first_person_count}/{total_lines}）"))
        for line_num, text in speaker_texts:
            if any(phrase in text for phrase in ["我是对话方", "我是第三方", "我是第三方顾问", "我是客户代表"]):
                errors.append(ValidationError("禁止的自我介绍", f"第{line_num}行包含禁止的自我介绍", line_num, text[:100]))

    forbidden_phrases = get_all_forbidden_phrases(scene_id)
    for phrase in forbidden_phrases:
        if phrase in dialogue_text:
            errors.append(ValidationError("禁止短语", f"包含禁止短语: {phrase}"))
    return len(errors) == 0, errors


def validate_dialogue_lines(lines: DialogueLines, scene_id: str, role_cards: List = None) -> Tuple[bool, List[ValidationError]]:
    return validate_dialogue("\n".join(f"{speaker}: {text}" for speaker, text in lines), scene_id, role_cards)


def infer_scene_id(task: TrainingTask) -> str:
    scenario_id = str(task.meta.get("scenario_id", ""))
    if scenario_id and scenario_id[-2:].isdigit():
        return str(int(scenario_id[-2:]))
    explicit = task.meta.get("scene_id")
    if explicit:
        return str(explicit)
    return ""


def validate_with_quality_gate(task: TrainingTask, lines: DialogueLines) -> Dict[str, Any]:
    scene_id = infer_scene_id(task)
    is_valid = True
    errors: List[ValidationError] = []
    if scene_id in {"1", "2", "3", "4"}:
        is_valid, errors = validate_dialogue_lines(lines, scene_id)

    full_text = "\n".join(f"{speaker}: {text}" for speaker, text in lines)
    if "[[[CORE" in full_text:
        errors.append(ValidationError("占位符残留", "存在占位符残留 [[[CORE"))
        is_valid = False

    core_markers = re.findall(r"<<(核心|Core|コア|Noyau|핵심|Kern|Núcleo|Esencial):.*?>>", full_text)
    if len(core_markers) == 0 and not task.meta.get("translate_fallback"):
        errors.append(ValidationError("核心标记缺失", "缺少核心标记"))
        is_valid = False
    if len(core_markers) > 2:
        errors.append(ValidationError("核心标记过多", f"核心标记过多({len(core_markers)}次)"))
        is_valid = False

    summary = "; ".join(error.message for error in errors) if errors else "ok"
    return {"passed": is_valid and not errors, "errors": errors, "summary": summary}
