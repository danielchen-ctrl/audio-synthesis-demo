# -*- coding: utf-8 -*-
"""
OutputMode系统 - 系统级文本生成模式定义
用于从系统层面区分不同类型的文本生成
"""

from enum import Enum
from typing import List, Tuple, Dict, Set
import re


class OutputMode(Enum):
    """输出模式枚举"""
    DIALOGUE = "dialogue"  # 多角色对话
    NON_DIALOGUE = "non_dialogue"  # 非对话型结构化文本
    REFLECTION = "reflection"  # 第一人称专业反思
    DECISION = "decision"  # 决策/裁决/结论型输出


# =====================================================
# 场景 → Mode 显式映射（必须写死）
# =====================================================

SCENE_CONFIG: Dict[str, OutputMode] = {
    # 4个独立场景
    "scenario1_ceo": OutputMode.NON_DIALOGUE,
    "scenario2_risk": OutputMode.NON_DIALOGUE,
    "scenario3_sales": OutputMode.REFLECTION,
    "scenario4_therapist": OutputMode.REFLECTION,
    
    # 支付场景（示例）
    "payment_review": OutputMode.DIALOGUE,
    "go_nogo": OutputMode.DECISION,
}


# =====================================================
# 禁用词表（Hard Ban）
# =====================================================

FORBIDDEN_PHRASES: Dict[OutputMode, List[str]] = {
    OutputMode.NON_DIALOGUE: [
        "你好", "您好", "请问", "我们讨论", "对话", "发言", "轮次",
        "你", "你们", "我们刚才", "刚才讨论", "刚才说的",
        "Speaker", "说话人", "请问", "？", "?"
    ],
    OutputMode.REFLECTION: [
        "方案", "产品优势", "价格", "ROI", "订阅", "模块",
        "ERP", "系统方案", "产品价格", "商业指标", "KPI",
        "达标率", "满意度", "完成率", "效率指标"
    ],
    OutputMode.DIALOGUE: [
        "战略要点如下", "总结如下", "我决定", "我判断",
        "我认为", "我的结论是"
    ],
    OutputMode.DECISION: [
        "我觉得", "可以考虑", "后续再看", "暂时", "可能",
        "也许", "或者", "不确定"
    ],
}


# =====================================================
# 结构约束（Hard Structure）
# =====================================================

def validate_structure(text: str, mode: OutputMode) -> Tuple[bool, str]:
    """
    校验文本结构是否符合Mode要求
    
    Returns:
        (is_valid, error_message)
    """
    if mode == OutputMode.NON_DIALOGUE:
        # 禁止问号
        if "?" in text or "？" in text:
            return False, "NON_DIALOGUE模式禁止使用问号"
        # 必须有结构化标记（编号、bullet等）
        has_structure = bool(re.search(r'[0-9]+[\.、]|[-•·]|【|一、|二、|三、', text))
        if not has_structure:
            return False, "NON_DIALOGUE模式必须使用Bullet Points或编号结构"
        # 禁止对话格式（检查Speaker标签）
        if "Speaker" in text:
            return False, "NON_DIALOGUE模式禁止对话格式（包含Speaker标签）"
        # 禁止对话格式（检查Speaker X:模式）
        if re.search(r'Speaker\s*\d+\s*[:：]', text, re.IGNORECASE):
            return False, "NON_DIALOGUE模式禁止对话格式（检测到Speaker X:）"
        # 禁止第二人称对话推进
        if re.search(r'你[^们]|你们', text):
            return False, "NON_DIALOGUE模式禁止使用第二人称'你'"
        # 检查是否包含明显的对话模式（如"："后跟非结构化内容）
        # 允许"："在以下情况：
        # 1. 在"【"之后（标题）
        # 2. 在数字/编号之后（如"1. 标题："）
        # 3. 在"责任人"、"时间"等结构化字段之后
        dialogue_pattern = re.search(r'[：:]\s*[^【\d\s一二三四五六七八九十责任人时间交付物市场侧增长部协同机制执行要求]', text[:500])
        if dialogue_pattern:
            # 检查上下文，如果在结构化标记之后则允许
            before_colon = text[:dialogue_pattern.start()]
            # 允许的情况：在"【"、数字、编号、结构化字段之后
            if not re.search(r'[【\d一二三四五六七八九十责任人时间交付物市场侧增长部协同机制执行要求]+', before_colon[-30:]):
                return False, "NON_DIALOGUE模式禁止对话格式（检测到对话标记）"
    
    elif mode == OutputMode.REFLECTION:
        # 必须使用第一人称"我"（要求≥70%）
        first_person_count = len(re.findall(r'\b我[^们]', text))
        total_sentences = len(re.split(r'[。！？\n]', text))
        if total_sentences > 0:
            first_person_ratio = first_person_count / max(total_sentences, 1)
            if first_person_ratio < 0.7:  # 要求≥70%
                return False, f"REFLECTION模式第一人称比例不足（当前{first_person_ratio:.1%}，要求≥70%）"
        # 禁止"你应该/建议你"
        if re.search(r'你(应该|可以|需要|建议)', text):
            return False, "REFLECTION模式禁止出现'你应该/建议你'等表达"
        # 禁止Speaker标签
        if "Speaker" in text:
            return False, "REFLECTION模式禁止包含Speaker标签"
    
    elif mode == OutputMode.DIALOGUE:
        # 必须有 ≥2 个说话人
        speaker_pattern = r'Speaker\s*\d+'
        speakers = set(re.findall(speaker_pattern, text, re.IGNORECASE))
        if len(speakers) < 2:
            return False, f"DIALOGUE模式必须有≥2个说话人（当前{len(speakers)}个）"
    
    elif mode == OutputMode.DECISION:
        # 必须包含：Judgment, Action, Owner
        has_judgment = bool(re.search(r'判断|决定|结论|态度', text))
        has_action = bool(re.search(r'行动|措施|方案|执行', text))
        has_owner = bool(re.search(r'负责人|责任人|执行人|负责', text))
        
        missing = []
        if not has_judgment:
            missing.append("Judgment（判断/决定）")
        if not has_action:
            missing.append("Action（行动/措施）")
        if not has_owner:
            missing.append("Owner（负责人）")
        
        if missing:
            return False, f"DECISION模式缺少必要元素: {', '.join(missing)}"
    
    return True, ""


# =====================================================
# Mode 校验（综合）
# =====================================================

def validate_mode_output(text: str, mode: OutputMode) -> Tuple[bool, List[str]]:
    """
    综合校验输出是否符合Mode要求
    
    Returns:
        (is_valid, violations)
    """
    violations = []
    
    # 1. 检查禁用词
    forbidden = FORBIDDEN_PHRASES.get(mode, [])
    for phrase in forbidden:
        if phrase.lower() in text.lower():
            violations.append(f"包含禁用词: {phrase}")
    
    # 2. 检查结构约束
    is_valid, error_msg = validate_structure(text, mode)
    if not is_valid:
        violations.append(error_msg)
    
    return len(violations) == 0, violations


# =====================================================
# Mode Prompt 模板
# =====================================================

def get_mode_prompt(mode: OutputMode, scenario_setup: str, core_content: str) -> str:
    """
    根据Mode获取对应的系统提示
    
    Args:
        mode: OutputMode枚举
        scenario_setup: 场景设置
        core_content: 核心内容
    
    Returns:
        完整的prompt字符串
    """
    base_context = f"""场景背景：{scenario_setup}

核心内容：
{core_content}
"""
    
    if mode == OutputMode.NON_DIALOGUE:
        return f"""{base_context}

【输出要求 - NON_DIALOGUE模式】
1. 输出格式：结构化文本（Bullet Points / 编号列表），禁止任何对话轮次
2. 单一叙述主体，不允许出现"你"、"我们讨论"等对话表达
3. 禁止问号、禁止问答形式
4. 每一条必须是：判断/决策/行动
5. 核心内容必须置于最前5行
6. 字数：800-1200字

直接输出结构化要点，不要对话格式。"""
    
    elif mode == OutputMode.REFLECTION:
        return f"""{base_context}

【输出要求 - REFLECTION模式】
1. 输出格式：第一人称专业反思，禁止任何对话轮次
2. 必须使用"我"的视角，聚焦自我认知与盲区
3. 禁止推销、禁止给别人下结论
4. 禁止KPI/商业指标/产品价格等商业系统词汇
5. 字数：800-1200字

直接输出第一人称反思，不要对话格式。"""
    
    elif mode == OutputMode.DIALOGUE:
        return f"""{base_context}

【输出要求 - DIALOGUE模式】
1. 输出格式：多角色对话（Speaker 1: ... / Speaker 2: ...）
2. 必须有≥2个说话人，轮次推进
3. 允许追问、拉扯、讨论
4. 禁止客服话术、禁止KPI填充句
5. 字数：1000-1500字

直接输出对话格式。"""
    
    elif mode == OutputMode.DECISION:
        return f"""{base_context}

【输出要求 - DECISION模式】
1. 输出格式：决策/裁决/结论型输出
2. 必须包含：
   - Judgment（判断/决定）
   - Action（行动/措施）
   - Owner（负责人）
3. 禁止分析展开、禁止情绪表达
4. 字数：500-800字

直接输出决策结论。"""
    
    else:
        raise ValueError(f"未知的OutputMode: {mode}")


# =====================================================
# 场景到Mode的映射函数
# =====================================================

def get_scene_mode(scene_key: str) -> OutputMode:
    """
    获取场景对应的Mode
    
    Args:
        scene_key: 场景标识（如"scenario1_ceo"）
    
    Returns:
        OutputMode枚举
    
    Raises:
        ValueError: 如果场景未配置Mode
    """
    if scene_key not in SCENE_CONFIG:
        raise ValueError(f"场景 '{scene_key}' 未配置OutputMode，请在SCENE_CONFIG中添加")
    
    return SCENE_CONFIG[scene_key]
