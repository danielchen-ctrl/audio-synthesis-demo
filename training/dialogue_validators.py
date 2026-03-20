# -*- coding: utf-8 -*-
"""
对话校验器 - 生成后质量检查
校验：角色身份、人称使用、场景词覆盖、跑题检测
"""

import re
from typing import List, Tuple, Dict, Any
from training.role_cards import get_role_cards, get_all_forbidden_phrases, SCENARIO_ROLE_MAP


class ValidationError:
    """校验错误"""
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
            "content": self.content
        }


def validate_dialogue(
    dialogue_text: str,
    scene_id: str,
    role_cards: List = None
) -> Tuple[bool, List[ValidationError]]:
    """
    校验对话质量
    
    Args:
        dialogue_text: 对话文本
        scene_id: 场景ID ("1", "2", "3", "4")
        role_cards: 角色卡列表（可选，会自动获取）
    
    Returns:
        (is_valid, errors)
    """
    errors: List[ValidationError] = []
    
    if role_cards is None:
        role_cards = get_role_cards(scene_id)
    
    lines = dialogue_text.strip().split('\n')
    
    # ========== 1. 角色校验 ==========
    valid_names = {role.name for role in role_cards}
    valid_identities = {role.identity for role in role_cards}
    
    # 禁止的占位符
    forbidden_placeholders = [
        "Speaker 1", "Speaker 2", "Speaker 3",
        "对话方", "第三方", "第三方顾问", "第三方/顾问",
        "客户代表", "顾问代表"
    ]
    
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        
        # 检查是否包含禁止的占位符
        for placeholder in forbidden_placeholders:
            if placeholder in line:
                errors.append(ValidationError(
                    error_type="角色占位符",
                    message=f"第{i}行包含禁止的占位符: {placeholder}",
                    line_num=i,
                    content=line[:100]
                ))
        
        # 检查speaker名称是否来自角色卡
        # 匹配格式：name(identity): 或 name:
        match = re.match(r'^([^:：]+)[:：]', line)
        if match:
            speaker_label = match.group(1).strip()
            # 检查是否包含角色名或身份
            has_valid_name = any(name in speaker_label for name in valid_names)
            has_valid_identity = any(identity in speaker_label for identity in valid_identities)
            
            if not (has_valid_name or has_valid_identity):
                # 允许格式：name(identity) 或 name
                if '(' in speaker_label and ')' in speaker_label:
                    name_part = speaker_label.split('(')[0].strip()
                    if name_part not in valid_names:
                        errors.append(ValidationError(
                            error_type="角色名称不匹配",
                            message=f"第{i}行speaker名称不在角色卡中: {speaker_label}",
                            line_num=i,
                            content=line[:100]
                        ))
    
    # ========== 2. 人称校验 ==========
    # 检查每个speaker是否使用第一人称
    speaker_lines = {}  # {speaker_name: [lines]}
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        match = re.match(r'^([^:：]+)[:：]', line)
        if match:
            speaker = match.group(1).strip()
            text = line.split(':', 1)[-1].split('：', 1)[-1].strip()
            if speaker not in speaker_lines:
                speaker_lines[speaker] = []
            speaker_lines[speaker].append((i, text))
    
    # 检查每个speaker是否使用"我"
    for speaker, speaker_texts in speaker_lines.items():
        # 至少每3句出现一次"我"
        total_lines = len(speaker_texts)
        if total_lines >= 3:
            first_person_count = sum(1 for _, text in speaker_texts if '我' in text)
            if first_person_count < total_lines // 3:
                errors.append(ValidationError(
                    error_type="人称使用不足",
                    message=f"speaker '{speaker}' 第一人称使用不足（{first_person_count}/{total_lines}）",
                    line_num=None,
                    content=f"speaker: {speaker}"
                ))
        
        # 禁止speaker2/speaker3出现"我是对话方/第三方顾问"
        for line_num, text in speaker_texts:
            if any(phrase in text for phrase in ["我是对话方", "我是第三方", "我是第三方顾问", "我是客户代表"]):
                errors.append(ValidationError(
                    error_type="禁止的自我介绍",
                    message=f"第{line_num}行包含禁止的自我介绍",
                    line_num=line_num,
                    content=text[:100]
                ))
    
    # ========== 3. 场景词覆盖校验 ==========
    scene_keywords = {
        "1": ["ABK", "Beta", "增长部", "东南亚", "战略要点", "渠道"],
        "2": ["GDPR", "用户画像", "精准投喂", "合规风险", "舆论风险"],
        "3": ["ASK AI", "痛点", "战略", "购买机会", "客户"],
        "4": ["Collaborative Therapy", "专家位置", "僵化叙事", "防御", "关系", "协作"]
    }
    
    keywords = scene_keywords.get(scene_id, [])
    dialogue_lower = dialogue_text.lower()
    missing_keywords = []
    
    for keyword in keywords:
        if keyword.lower() not in dialogue_lower:
            missing_keywords.append(keyword)
    
    if missing_keywords:
        errors.append(ValidationError(
            error_type="场景词缺失",
            message=f"缺少关键场景词: {', '.join(missing_keywords)}",
            line_num=None,
            content=None
        ))
    
    # ========== 4. 跑题检测 ==========
    off_topic_phrases = {
        "all": ["KPI", "ERP", "ROI", "达标率", "满意度", "订阅"],
        "4": ["血常规", "CT", "心电图", "治疗方案", "检查", "诊断", "药物", "医生", "患者"]
    }
    
    # 通用跑题词
    for phrase in off_topic_phrases.get("all", []):
        if phrase in dialogue_text:
            errors.append(ValidationError(
                error_type="跑题检测",
                message=f"包含禁止的通用跑题词: {phrase}",
                line_num=None,
                content=None
            ))
    
    # 场景4特殊检测
    if scene_id == "4":
        for phrase in off_topic_phrases.get("4", []):
            if phrase in dialogue_text:
                errors.append(ValidationError(
                    error_type="场景4医疗词检测",
                    message=f"场景4禁止出现医疗问诊词: {phrase}",
                    line_num=None,
                    content=None
                ))
    
    # ========== 5. 禁止短语检测 ==========
    forbidden_phrases = get_all_forbidden_phrases(scene_id)
    for phrase in forbidden_phrases:
        if phrase in dialogue_text:
            errors.append(ValidationError(
                error_type="禁止短语",
                message=f"包含禁止短语: {phrase}",
                line_num=None,
                content=None
            ))
    
    return len(errors) == 0, errors


def validate_dialogue_lines(
    lines: List[Tuple[str, str]],
    scene_id: str,
    role_cards: List = None
) -> Tuple[bool, List[ValidationError]]:
    """
    校验对话行列表
    
    Args:
        lines: List[Tuple[speaker, text]]
        scene_id: 场景ID
        role_cards: 角色卡列表
    
    Returns:
        (is_valid, errors)
    """
    # 转换为文本格式
    dialogue_text = "\n".join([f"{speaker}: {text}" for speaker, text in lines])
    return validate_dialogue(dialogue_text, scene_id, role_cards)
