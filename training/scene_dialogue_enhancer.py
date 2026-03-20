# -*- coding: utf-8 -*-
"""
场景对话增强器
- 在生成前应用角色卡约束
- 禁用通用客服模板
- 提供场景专用对话骨架
"""

from typing import List, Dict, Any, Tuple
from training.role_cards import (
    get_role_cards, get_all_forbidden_phrases, 
    SCENARIO_ROLE_MAP, GLOBAL_FORBIDDEN_PHRASES
)


def build_scene_specific_prompt(
    scenario_id: str,
    scenario_setup: str,
    core_content: str,
    role_cards: List = None
) -> str:
    """
    构建场景专用提示词（替代通用客服模板）
    
    Args:
        scenario_id: 场景ID ("1", "2", "3", "4")
        scenario_setup: 场景设置
        core_content: 核心内容
        role_cards: 角色卡列表
    
    Returns:
        场景专用提示词
    """
    if role_cards is None:
        role_cards = get_role_cards(scenario_id)
    
    # 构建角色信息
    role_info = "\n".join([
        f"- {role.name}({role.identity}): {role.speaking_style}"
        for role in role_cards
    ])
    
    # 场景专用对话骨架
    scene_skeletons = {
        "1": """对话结构（战略周会）：
1. 开场：Tim简要说明会议目的
2. 战略要点陈述：Tim提出ABK项目Beta测试结果、增长部对接需求、东南亚市场计划
3. 行动分工：张秘书确认行动项，李总监提出增长方案
4. 资源/节奏讨论：讨论流量支持、市场目标、时间节点
5. 风险与确认：确认风险点，明确下一步行动""",
        
        "2": """对话结构（立项风控）：
1. 开场：M说明风控评审目的
2. 风险陈述：M提出GDPR合规风险、用户画像共享问题、精准投喂的舆论风险
3. 法务澄清：陈律师解释GDPR条款，王经理说明产品实现
4. 舆论推演：讨论用户感知、负面讨论可能性
5. 缓释方案：讨论合规改进、表述优化、用户控制权
6. 风控结论：M给出最终风控意见""",
        
        "3": """对话结构（销售洞察）：
1. 开场：Yoki介绍自己和ASK AI工具
2. 客户战略表达：刘总说明公司战略和业务挑战
3. Yoki卡点：Yoki使用ASK AI分析，提出理解上的疑问
4. 追问清单：Yoki深入挖掘痛点，赵经理提供财务视角
5. 下一步：确定后续跟进和方案""",
        
        "4": """对话结构（咨询反思）：
1. 开场：KK说明使用ASK AI分析咨询过程
2. 咨询片段回放：KK描述来访者的表达方式
3. 关系位置分析：讨论"专家位置"vs"协作探索"
4. 叙事僵化识别：分析"事情就是这样"的单一解释模式
5. 协作失败点：讨论防御行为、安全距离、协作结构薄弱
6. 下一次尝试：讨论如何创造开放空间"""
    }
    
    skeleton = scene_skeletons.get(scenario_id, "")
    
    # 禁止短语提醒
    forbidden = get_all_forbidden_phrases(scenario_id)
    forbidden_list = ", ".join(forbidden[:10])  # 只显示前10个
    
    prompt = f"""场景设置：{scenario_setup}

核心内容：{core_content}

角色信息：
{role_info}

{skeleton}

【严格禁止】以下短语不得出现在对话中：
{forbidden_list}
（共{len(forbidden)}个禁止短语）

【输出要求】
1. 每个角色必须使用真实姓名和身份（格式：name(identity): ...）
2. 禁止使用"Speaker 1/2/3"、"对话方"、"第三方顾问"等占位符
3. 每个角色必须使用第一人称"我"
4. 对话必须自然流畅，符合场景设定
5. 核心内容必须自然融入对话
"""
    
    return prompt


def check_forbidden_phrases(text: str, scenario_id: str = None) -> Tuple[bool, List[str]]:
    """
    检查文本是否包含禁止短语
    
    Returns:
        (has_forbidden, found_phrases)
    """
    forbidden = get_all_forbidden_phrases(scenario_id)
    found = []
    
    for phrase in forbidden:
        if phrase in text:
            found.append(phrase)
    
    return len(found) == 0, found


def apply_role_names_to_lines(
    lines: List[Tuple[str, str]],
    scenario_id: str
) -> List[Tuple[str, str]]:
    """
    将对话行中的Speaker ID转换为角色卡名称
    
    Args:
        lines: List[Tuple[speaker_id, text]]
        scenario_id: 场景ID
    
    Returns:
        List[Tuple[speaker_name, text]]
    """
    import re
    role_cards = get_role_cards(scenario_id)
    role_map = {role.role_id: role for role in role_cards}
    
    new_lines = []
    for speaker, text in lines:
        # 提取Speaker ID
        match = re.search(r'Speaker\s*(\d+)', speaker)
        if match:
            role_id = int(match.group(1))
            if role_id in role_map:
                role = role_map[role_id]
                new_speaker = f"{role.name}({role.identity})"
            else:
                # 回退到默认格式
                new_speaker = f"Speaker {role_id}"
        else:
            # 如果已经是角色名格式，检查是否需要补充
            if '(' not in speaker and speaker.startswith('Speaker'):
                # 仍然需要转换
                match = re.search(r'Speaker\s*(\d+)', speaker)
                if match:
                    role_id = int(match.group(1))
                    if role_id in role_map:
                        role = role_map[role_id]
                        new_speaker = f"{role.name}({role.identity})"
                    else:
                        new_speaker = speaker
                else:
                    new_speaker = speaker
            else:
                new_speaker = speaker
        
        new_lines.append((new_speaker, text))
    
    return new_lines
