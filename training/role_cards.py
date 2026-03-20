# -*- coding: utf-8 -*-
"""
角色卡 Role Cards - 为4个独立场景定义真实角色身份
禁止使用占位符（"对话方/第三方顾问/客户代表"）
"""

from typing import Dict, List, Any


class RoleCard:
    """角色卡定义"""
    def __init__(
        self,
        role_id: int,
        name: str,
        identity: str,
        speaking_style: str,
        first_person_pronoun: str = "我",
        address_terms: List[str] = None,
        focus_points: List[str] = None,
        forbidden_phrases: List[str] = None
    ):
        self.role_id = role_id
        self.name = name
        self.identity = identity
        self.speaking_style = speaking_style
        self.first_person_pronoun = first_person_pronoun
        self.address_terms = address_terms or []
        self.focus_points = focus_points or []
        self.forbidden_phrases = forbidden_phrases or []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_id": self.role_id,
            "name": self.name,
            "identity": self.identity,
            "speaking_style": self.speaking_style,
            "first_person_pronoun": self.first_person_pronoun,
            "address_terms": self.address_terms,
            "focus_points": self.focus_points,
            "forbidden_phrases": self.forbidden_phrases
        }


# ============================================================
# 场景1：战略周会（CEO Tim）
# ============================================================
SCENARIO1_ROLES = [
    RoleCard(
        role_id=1,
        name="Tim",
        identity="CEO",
        speaking_style="决策果断、战略导向、直接表达、关注数据指标",
        first_person_pronoun="我",
        address_terms=["你们", "大家", "各位"],
        focus_points=["ABK项目", "Beta测试", "增长部对接", "东南亚市场", "渠道打法", "增长目标"],
        forbidden_phrases=["对话方", "第三方", "顾问", "您目前遇到的具体问题是什么"]
    ),
    RoleCard(
        role_id=2,
        name="张秘书",
        identity="CEO办公室首席助理",
        speaking_style="执行导向、记录要点、确认行动项、协调资源",
        first_person_pronoun="我",
        address_terms=["Tim总", "您", "增长部"],
        focus_points=["战略要点整理", "会议纪要", "行动项跟进", "资源协调"],
        forbidden_phrases=["对话方", "第三方", "顾问", "方案1", "方案2"]
    ),
    RoleCard(
        role_id=3,
        name="李总监",
        identity="增长部负责人",
        speaking_style="数据驱动、目标明确、协作开放、关注流量与转化",
        first_person_pronoun="我",
        address_terms=["Tim总", "张秘书", "ABK团队"],
        focus_points=["流量支持", "增长方案", "市场目标", "数据对接"],
        forbidden_phrases=["对话方", "第三方", "顾问", "准备材料", "提交申请"]
    )
]

# ============================================================
# 场景2：立项风控（M风控负责人）
# ============================================================
SCENARIO2_ROLES = [
    RoleCard(
        role_id=1,
        name="M",
        identity="风控负责人",
        speaking_style="谨慎理性、风险敏感、合规导向、关注细节",
        first_person_pronoun="我",
        address_terms=["产品团队", "法务", "PR"],
        focus_points=["GDPR合规", "用户画像共享", "精准投喂", "舆论风险", "合规红线"],
        forbidden_phrases=["对话方", "第三方", "顾问", "您目前遇到的具体问题是什么"]
    ),
    RoleCard(
        role_id=2,
        name="王经理",
        identity="产品经理",
        speaking_style="产品导向、用户视角、技术理解、平衡风险与收益",
        first_person_pronoun="我",
        address_terms=["M", "风控", "法务"],
        focus_points=["产品功能", "用户体验", "数据使用", "技术实现"],
        forbidden_phrases=["对话方", "第三方", "顾问", "方案1", "方案2"]
    ),
    RoleCard(
        role_id=3,
        name="陈律师",
        identity="法务负责人",
        speaking_style="法律严谨、条款清晰、风险预警、合规建议",
        first_person_pronoun="我",
        address_terms=["M", "产品团队", "PR"],
        focus_points=["GDPR条款", "数据隐私", "合规审查", "法律风险"],
        forbidden_phrases=["对话方", "第三方", "顾问", "准备材料", "提交申请"]
    )
]

# ============================================================
# 场景3：销售洞察（Yoki保险销售）
# ============================================================
SCENARIO3_ROLES = [
    RoleCard(
        role_id=1,
        name="Yoki",
        identity="保险销售人员",
        speaking_style="专业热情、客户导向、善于倾听、使用ASK AI辅助理解",
        first_person_pronoun="我",
        address_terms=["您", "客户", "贵公司"],
        focus_points=["客户痛点", "战略重点", "购买机会", "ASK AI分析"],
        forbidden_phrases=["对话方", "第三方", "顾问", "您目前遇到的具体问题是什么"]
    ),
    RoleCard(
        role_id=2,
        name="刘总",
        identity="客户战略负责人",
        speaking_style="战略表达、业务导向、决策谨慎、关注长期价值",
        first_person_pronoun="我",
        address_terms=["Yoki", "您"],
        focus_points=["公司战略", "业务挑战", "保险需求", "风险管控"],
        forbidden_phrases=["对话方", "第三方", "顾问", "方案1", "方案2"]
    ),
    RoleCard(
        role_id=3,
        name="赵经理",
        identity="客户财务负责人",
        speaking_style="财务严谨、成本敏感、预算导向、关注ROI",
        first_person_pronoun="我",
        address_terms=["Yoki", "刘总"],
        focus_points=["预算规划", "成本控制", "财务评估", "保险方案"],
        forbidden_phrases=["对话方", "第三方", "顾问", "准备材料", "提交申请"]
    )
]

# ============================================================
# 场景4：咨询反思（KK心理咨询师）
# ============================================================
SCENARIO4_ROLES = [
    RoleCard(
        role_id=1,
        name="KK",
        identity="心理咨询师",
        speaking_style="协作式、反思性、关系导向、使用Collaborative Therapy方法论",
        first_person_pronoun="我",
        address_terms=["来访者", "你"],
        focus_points=["关系位置", "叙事模式", "协作结构", "防御行为", "僵化叙事"],
        forbidden_phrases=["对话方", "第三方", "顾问", "血常规", "CT", "心电图", "治疗方案", "检查", "诊断", "药物"]
    ),
    RoleCard(
        role_id=2,
        name="来访者",
        identity="咨询来访者",
        speaking_style="防御性、控制导向、寻求答案、习惯专家位置",
        first_person_pronoun="我",
        address_terms=["KK", "你", "老师"],
        focus_points=["问题描述", "情绪表达", "关系模式", "行为反应"],
        forbidden_phrases=["对话方", "第三方", "顾问", "血常规", "CT", "心电图", "治疗方案", "检查", "诊断", "药物"]
    ),
    RoleCard(
        role_id=3,
        name="督导",
        identity="同侪督导咨询师",
        speaking_style="专业反思、方法论指导、关系分析、协作视角",
        first_person_pronoun="我",
        address_terms=["KK", "来访者"],
        focus_points=["咨询技术", "关系动态", "方法论应用", "协作失败点"],
        forbidden_phrases=["对话方", "第三方", "顾问", "血常规", "CT", "心电图", "治疗方案", "检查", "诊断", "药物"]
    )
]

# ============================================================
# 全局禁止短语（所有场景通用）
# ============================================================
GLOBAL_FORBIDDEN_PHRASES = [
    "您好，我是张先生",
    "对话方",
    "第三方/顾问",
    "第三方顾问",
    "您目前遇到的具体问题是什么",
    "方案1",
    "方案2",
    "准备材料",
    "提交申请",
    "等待审核",
    "下周再安排一次",
    "达标率",
    "满意度",
    "ROI",
    "ERP",
    "订阅",
    "Speaker 1",
    "Speaker 2",
    "Speaker 3"
]

# ============================================================
# 场景映射
# ============================================================
SCENARIO_ROLE_MAP = {
    "1": SCENARIO1_ROLES,
    "2": SCENARIO2_ROLES,
    "3": SCENARIO3_ROLES,
    "4": SCENARIO4_ROLES
}


def get_role_cards(scenario_id: str) -> List[RoleCard]:
    """获取指定场景的角色卡"""
    return SCENARIO_ROLE_MAP.get(scenario_id, [])


def get_role_card(scenario_id: str, role_id: int) -> RoleCard:
    """获取指定场景的指定角色卡"""
    roles = get_role_cards(scenario_id)
    for role in roles:
        if role.role_id == role_id:
            return role
    return None


def get_speaker_name(scenario_id: str, role_id: int) -> str:
    """获取speaker显示名称（格式：name(identity)）"""
    role = get_role_card(scenario_id, role_id)
    if role:
        return f"{role.name}({role.identity})"
    return f"Speaker {role_id}"


def get_all_forbidden_phrases(scenario_id: str = None) -> List[str]:
    """获取所有禁止短语（全局+场景特定）"""
    phrases = GLOBAL_FORBIDDEN_PHRASES.copy()
    if scenario_id:
        roles = get_role_cards(scenario_id)
        for role in roles:
            phrases.extend(role.forbidden_phrases)
    return list(set(phrases))  # 去重
