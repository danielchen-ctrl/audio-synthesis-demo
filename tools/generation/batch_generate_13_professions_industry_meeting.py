#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量生成13个职业场景的行业会议对话文本（改进版）
- 人物数量：3
- 字数：2000~3000
- 语言：纯英文
- 场景：行业会议（非面试）
- 消除占位符、跨行业污染、中英混杂
"""

import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any, Set

# 添加项目根目录到 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# 导入 server.py 核心函数
from server import _generate_dialogue_lines, _render_dialogue_text

# 导入行业模板验证器
sys.path.insert(0, str(PROJECT_ROOT))
from industry_template_loader import (
    detect_industry_slug,
    load_industry_skeleton,
    validate_dialogue_quality,
    repair_dialogue_issues,
    ensure_meeting_closure
)

# 全局配置
INPUT_FILE = PROJECT_ROOT / "demo" / "13个职业最新情景设置参数.txt"
OUTPUT_DIR = PROJECT_ROOT / "output"

# 默认参数（可被文件中的参数覆盖）
DEFAULT_PEOPLE_COUNT = 4
DEFAULT_WORD_COUNT = 1500
DEFAULT_LANGUAGE = "英语"

# 从命令行或全局设置
PEOPLE_COUNT = DEFAULT_PEOPLE_COUNT
WORD_COUNT = DEFAULT_WORD_COUNT
LANGUAGE = DEFAULT_LANGUAGE

# ==================== 行业配置 ====================

# 行业角色映射（替换占位符）- 支持4-5人场景
INDUSTRY_ROLES = {
    "医疗健康": ["Dr. Chen (Department Head)", "Director Liu (Hospital Leadership)", "Manager Wang (IT Center)", "Nurse Li (Nursing/Operations)", "Coordinator Zhang (Project)"],
    "人力资源与招聘": ["Sarah Chen (HRBP Lead)", "Michael Zhang (Business VP)", "Lisa Wang (Finance BP)", "David Liu (Compliance/Legal)"],
    "娱乐/媒体": ["David Lee (General Manager)", "Emma Zhang (Brand Commercialization)", "Tom Wang (Content Director)", "Linda Chen (Channel Distribution)"],
    "建筑与工程行业": ["John Smith (General Manager)", "Kevin Liu (Cost Manager)", "Amy Chen (Supply Chain)", "Steven Wang (Safety Officer)", "Peter Zhao (Project Lead)"],
    "汽车行业": ["Robert Zhang (Marketing Director)", "Linda Wang (Regional Channel)", "Steve Chen (Store Operations)", "Frank Liu (Finance Policy)", "Mary Zhou (Product Manager)"],
    "咨询/专业服务": ["Jennifer Li (Partner)", "Daniel Wu (Delivery Lead)", "Michelle Zhang (Market Lead)", "Tony Chen (Client Manager)"],
    "法律服务": ["Attorney Johnson (Managing Partner)", "Partner Chen (Delivery Partner)", "Manager Liu (Market BD)", "Susan Wang (Operations)"],
    "金融/投资": ["Frank Zhang (Investment Director)", "Helen Liu (Risk Officer)", "Mark Wang (Product Manager)", "Emma Chen (Wealth Manager)"],
    "零售行业": ["Andrew Chen (General Manager)", "Nancy Wang (Merchandising)", "Peter Liu (Store Operations)", "Lucy Zhou (Member Manager)"],
    "保险行业": ["Richard Zhang (Channel Director)", "Susan Liu (Compliance Officer)", "Tony Wang (Training Lead)", "David Chen (Product Manager)"],
    "房地产": ["William Chen (Regional Director)", "Jessica Wang (Channel Manager)", "Chris Liu (Sales Site)", "Amy Zhou (Marketing)"],
    "人工智能/科技": ["Alex Zhang (CTO)", "Emily Chen (Commercialization)", "Kevin Wang (SRE/Cost)", "Lisa Liu (Product Manager)"],
    "制造业": ["James Liu (General Manager)", "Mary Chen (Quality Officer)", "Paul Wang (Equipment Manager)", "Steven Zhang (Supply Chain)", "Amy Zhao (Production)"],
}

# 跨行业污染黑名单（非医疗场景禁用医疗词汇）
MEDICAL_BLACKLIST = [
    "blood test", "imaging", "patient", "clinical", "hospital", "medication", 
    "therapy", "treatment", "diagnosis", "symptoms", "medical", "doctor",
    "healthcare", "physician", "nurse", "clinic", "prescription"
]

# 行业特定指标（用于Risk Alert）
INDUSTRY_METRICS = {
    "医疗健康": ["patient satisfaction", "readmission rate", "wait time", "treatment adherence"],
    "人力资源与招聘": ["time-to-fill", "offer acceptance rate", "retention rate", "cost-per-hire"],
    "娱乐/媒体": ["engagement rate", "content ROI", "audience growth", "brand awareness"],
    "建筑与工程行业": ["schedule variance", "cost variance", "safety incidents", "quality defects"],
    "汽车行业": ["lead conversion", "test-drive conversion", "dealer satisfaction", "inventory turnover"],
    "咨询/专业服务": ["utilization rate", "client retention", "project margin", "proposal win rate"],
    "法律服务": ["case win rate", "billable hours", "client acquisition cost", "case resolution time"],
    "金融/投资": ["volatility", "drawdown", "AUM retention", "risk-adjusted return"],
    "零售行业": ["same-store sales", "inventory turnover", "customer retention", "conversion rate"],
    "保险行业": ["premium growth", "loss ratio", "policy retention", "claims processing time"],
    "房地产": ["sales velocity", "price per sqm", "visitor-to-buyer conversion", "inventory days"],
    "人工智能/科技": ["user retention", "paid conversion rate", "ARPU", "feature adoption rate"],
    "制造业": ["OEE", "defect rate", "capacity utilization", "on-time delivery"],
}

# 占位符模式
PLACEHOLDER_PATTERNS = [
    r'\bProfessional\b',
    r'\bCounterpart\b',
    r'\bCoordinator\b',
    r'\bThird Party\b',
    r'\bConsultant\b',
]

# 近重复句式
REPETITIVE_PHRASES = [
    "What are the pros and cons?",
    "I will consider and reply",
    "I need to learn more about",
    "That's an important point to consider",
    "Could you provide some guidance?",
    "I understand, this indeed needs attention",
]


# ==================== 核心函数 ====================

def parse_input_file(file_path: Path) -> List[Dict[str, Any]]:
    """解析输入文件，提取13个职业场景（新格式）"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 按场景分割（格式：1）医疗健康｜...）
    blocks = re.split(r'\n\d+\）', content)
    blocks = [b.strip() for b in blocks if b.strip()]
    
    jobs = []
    for idx, block in enumerate(blocks, 1):
        lines = block.split('\n')
        
        # 提取职业名称（第一行，格式：医疗健康｜慢病管理+随访体系升级（评审会））
        profession_line = lines[0].strip() if lines else ""
        # 移除可能的序号前缀（如"1）"）
        profession_line = re.sub(r'^\d+[）)]\s*', '', profession_line)
        profession_match = re.match(r'([^｜]+)｜', profession_line)
        profession = profession_match.group(1).strip() if profession_match else profession_line.split('｜')[0].strip()
        
        # 提取场景对话设置
        scenario_match = re.search(
            r'场景对话设置[（(]升级版[)）]：\s*\n?(.*?)(?=\n\n|\*\*对话生成参数|$)',
            block, re.DOTALL
        )
        scenario_setting = scenario_match.group(1).strip() if scenario_match else ""
        
        # 提取对话生成参数（支持"参数："或"对话生成参数："）
        params_match = re.search(
            r'\*\*(?:对话生成)?参数：?\*\*([^\n]+)',
            block
        )
        params_str = params_match.group(1).strip() if params_match else ""
        
        # 解析参数（people_count=4｜language=中文｜target_words=1400~1600）
        people_count = DEFAULT_PEOPLE_COUNT
        language = DEFAULT_LANGUAGE
        target_words = DEFAULT_WORD_COUNT
        
        if params_str:
            # 提取 people_count
            pc_match = re.search(r'people_count[=＝](\d+)', params_str)
            if pc_match:
                people_count = int(pc_match.group(1))
            
            # 提取 language
            lang_match = re.search(r'language[=＝]([^｜\n]+)', params_str)
            if lang_match:
                lang = lang_match.group(1).strip()
                # 统一转换为英语（用户要求）
                language = "英语"
            
            # 提取 target_words
            words_match = re.search(r'target_words[=＝](\d+)~?(\d+)?', params_str)
            if words_match:
                min_words = int(words_match.group(1))
                max_words = int(words_match.group(2)) if words_match.group(2) else min_words + 200
                target_words = (min_words + max_words) // 2
        
        # 提取核心内容（<Core:...>）
        core_match = re.search(
            r'<Core:([^>]+)>',
            block, re.DOTALL
        )
        core_content = core_match.group(1).strip() if core_match else ""
        
        # 如果没找到 <Core:>，尝试旧格式
        if not core_content:
            core_match = re.search(
                r'核心内容[：:]\s*\n(.*?)(?=\n\n|---|\Z)',
                block, re.DOTALL
            )
            core_content = core_match.group(1).strip() if core_match else ""
        
        if not profession or not scenario_setting or not core_content:
            print(f"[警告] 跳过不完整的职业块 #{idx}: profession={profession}, scenario={bool(scenario_setting)}, core={bool(core_content)}")
            continue
        
        jobs.append({
            "index": idx,
            "profession": profession,
            "scenario_setting": scenario_setting,
            "core_content": core_content,
            "people_count": people_count,
            "target_words": target_words,
            "language": language,
        })
    
    print(f"[解析] 成功解析 {len(jobs)} 个职业场景")
    return jobs


def detect_validation_failures(text: str, profession: str) -> List[str]:
    """
    检测验证失败项
    返回失败原因列表
    """
    failures = []
    
    # 检测占位符未替换
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            failures.append(f"发现占位符: {pattern}")
    
    # 检测重复介绍 "I'm X, I'm X"
    if re.search(r"I'm\s+(\w+),\s+I'm\s+\1", text, re.IGNORECASE):
        failures.append("发现重复介绍 (I'm X, I'm X)")
    
    # 检测中英混杂
    if re.search(r'[\u4e00-\u9fff]', text):
        # 排除 <<Core:...>> 标记内的中文
        text_without_core = re.sub(r'<<Core:.*?>>', '', text, flags=re.DOTALL)
        if re.search(r'[\u4e00-\u9fff]', text_without_core):
            failures.append("发现中英混杂")
    
    # 检测非医疗场景中的医疗词汇
    if profession != "医疗健康":
        text_lower = text.lower()
        found_medical = [word for word in MEDICAL_BLACKLIST if word in text_lower]
        if found_medical:
            failures.append(f"发现医疗词汇污染: {', '.join(found_medical[:3])}")
    
    return failures


def replace_placeholders(text: str, profession: str) -> str:
    """替换占位符为真实行业角色"""
    roles = INDUSTRY_ROLES.get(profession, [
        "Manager A (Department Lead)",
        "Manager B (Operations)",
        "Manager C (Support)"
    ])
    
    # 替换 Speaker 1/2/3 为真实角色名
    text = re.sub(r'Speaker\s*1\b', roles[0], text)
    text = re.sub(r'Speaker\s*2\b', roles[1], text)
    text = re.sub(r'Speaker\s*3\b', roles[2] if len(roles) > 2 else "Manager C", text)
    
    # 替换占位符
    text = re.sub(r'\bProfessional\b', roles[0].split('(')[0].strip(), text, flags=re.IGNORECASE)
    text = re.sub(r'\bCounterpart\b', roles[1].split('(')[0].strip(), text, flags=re.IGNORECASE)
    text = re.sub(r'\bCoordinator\b', roles[2].split('(')[0].strip() if len(roles) > 2 else "Manager C", text, flags=re.IGNORECASE)
    text = re.sub(r'\bThird Party\b', roles[2].split('(')[0].strip() if len(roles) > 2 else "Manager C", text, flags=re.IGNORECASE)
    text = re.sub(r'\bConsultant\b', roles[2].split('(')[0].strip() if len(roles) > 2 else "Manager C", text, flags=re.IGNORECASE)
    
    return text


def remove_duplicate_intro(text: str) -> str:
    """移除重复介绍 "I'm X, I'm X" """
    text = re.sub(
        r"(I'm\s+)(\w+),\s+I'm\s+\2",
        r"\1\2",
        text,
        flags=re.IGNORECASE
    )
    return text


def translate_risk_alert(text: str, profession: str) -> str:
    """将Risk Alert中的中文翻译为英文行业指标"""
    metrics = INDUSTRY_METRICS.get(profession, ["efficiency metric", "quality metric"])
    
    # 替换中文风险提示
    def replace_risk(match):
        chinese_term = match.group(1)
        percentage = match.group(2)
        # 随机选择一个行业指标
        import random
        metric = random.choice(metrics)
        return f"Risk Alert: {metric} at {percentage}%, requires attention"
    
    text = re.sub(
        r'Risk Alert:\s*([^/]+?)\s+requires attention,\s*([^/]+?)\s+currently at\s+(\d+)%',
        lambda m: f"Risk Alert: {random.choice(metrics)} at {m.group(3)}%, requires attention",
        text
    )
    
    # 移除残留中文
    text = re.sub(r'Risk Alert:\s*[\u4e00-\u9fff]+', f"Risk Alert: {metrics[0]}", text)
    
    return text


def remove_medical_terms(text: str, profession: str, speaker_prefix: str = "") -> str:
    """移除非医疗场景中的医疗词汇"""
    if profession == "医疗健康":
        return text
    
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # 跳过 <<Core:...>> 行
        if '<<Core:' in line:
            cleaned_lines.append(line)
            continue
        
        # 检测是否包含医疗词汇
        line_lower = line.lower()
        has_medical = any(word in line_lower for word in MEDICAL_BLACKLIST)
        
        if not has_medical:
            cleaned_lines.append(line)
        else:
            print(f"  [过滤] 移除医疗词汇行: {line[:60]}...")
    
    return '\n'.join(cleaned_lines)


def deduplicate_phrases(text: str) -> str:
    """去除重复的套话，保留首次出现"""
    seen_phrases = set()
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # 检查是否包含重复句式
        is_duplicate = False
        for phrase in REPETITIVE_PHRASES:
            if phrase.lower() in line.lower():
                if phrase in seen_phrases:
                    is_duplicate = True
                    print(f"  [去重] 移除重复句式: {phrase}")
                    break
                else:
                    seen_phrases.add(phrase)
        
        if not is_duplicate:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def add_meeting_closure(text: str, profession: str) -> str:
    """
    强制添加会议收尾：Decision + 3条Action Items
    """
    # 检查是否已有 Decision 和 Action Items
    has_decision = "Decision:" in text or "决策" in text
    has_actions = text.count("Action") >= 3 or text.count("行动项") >= 3
    
    if has_decision and has_actions:
        return text
    
    print(f"  [补充] 添加会议收尾（Decision + Action Items）")
    
    # 提取角色名
    roles = INDUSTRY_ROLES.get(profession, ["Manager A", "Manager B", "Manager C"])
    role1 = roles[0].split('(')[0].strip()
    role2 = roles[1].split('(')[0].strip()
    role3 = roles[2].split('(')[0].strip() if len(roles) > 2 else "Manager C"
    
    # 生成会议收尾
    closure = f"""
{role1}: Let's finalize our decision and action items to ensure alignment.

{role1}: Decision: We will proceed with the proposed plan as discussed, with phased implementation starting next quarter.

{role1}: Here are the three key action items:

{role1}: Action Item 1: {role2} will prepare the detailed implementation roadmap and resource allocation plan. Due: Next Friday. Deliverable: Comprehensive project plan with milestones.

{role2}: Understood. I'll coordinate with relevant teams and have the draft ready for review.

{role1}: Action Item 2: {role3} will conduct stakeholder alignment meetings and gather feedback on the proposal. Due: Within two weeks. Deliverable: Stakeholder feedback report with risk assessment.

{role3}: Got it. I'll schedule meetings with key stakeholders starting Monday.

{role1}: Action Item 3: {role1} will secure budget approval and finalize the governance structure. Due: End of this month. Deliverable: Approved budget and governance framework.

{role1}: Let's reconvene in two weeks to review progress on these action items. Thank you all for the productive discussion.

{role2}: Thank you. Looking forward to executing on this plan.

{role3}: Agreed. Let's make this happen.
"""
    
    return text + closure


def post_process_dialogue(text: str, profession: str, scenario: str = "", core: str = "", people_count: int = 3, max_retries: int = 3) -> Tuple[str, bool, List[str], Dict[str, Any]]:
    """
    后处理对话文本（集成行业模板验证 + RoleKPI强制补齐 + Challenge硬约束）
    
    返回:
        (processed_text, is_valid, failure_reasons, role_kpi_report)
    """
    print(f"  [后处理] 开始处理（使用行业模板验证 + RoleKPI补齐）...")
    
    # === 新增：使用行业模板验证器 ===
    # 1. 识别行业并加载模板
    profile = {"job_function": profession}
    slug = detect_industry_slug(profile, scenario, core)
    skeleton = load_industry_skeleton(slug, "en")
    
    print(f"  [行业模板] 使用 {slug} 模板")
    
    # 2. 提取角色列表（根据people_count动态调整）
    base_roles = INDUSTRY_ROLES.get(profession, ["Director A", "Manager B", "Lead C", "Manager D", "Lead E"])
    roles = base_roles[:people_count] if people_count <= len(base_roles) else base_roles
    
    # 3. 旧版后处理（保留兼容性）
    text = replace_placeholders(text, profession)
    text = remove_duplicate_intro(text)
    text = remove_medical_terms(text, profession)
    text = translate_risk_alert(text, profession)
    text = deduplicate_phrases(text)
    
    # 4. 新增：使用行业模板确保会议收尾
    text = ensure_meeting_closure(text, skeleton, roles)
    
    # 【新增】5. RoleKPI强制补齐闭环（含Challenge硬约束）
    role_kpi_report = {}
    try:
        from dialogue_review_expander import ensure_role_kpi_closure, RoleKPIHardFail
        
        # 将文本转换为行列表
        lines = [line for line in text.split('\n') if line.strip()]
        
        # 构建cast映射
        cast = {}
        for i, role in enumerate(roles[:people_count]):
            cast[f"speaker{i+1}"] = role
        
        print(f"  [RoleKPI] 启动强制补齐闭环（people={people_count}）")
        
        # 调用强制补齐
        fixed_lines, fix_report = ensure_role_kpi_closure(
            lines=lines,
            cast=cast,
            industry_slug=slug,
            language="en",
            people_count=people_count,
            min_role_ratio=0.15,
            early_window=10,
            early_min_turns=2,
            max_fix_rounds=4,
            forbid_placeholders=True,
        )
        
        # 更新文本
        text = '\n'.join(fixed_lines)
        
        # 记录报告
        role_kpi_report = {
            "enabled": True,
            "success": True,
            "insertions": fix_report.get("insertions", 0),
            "rounds": fix_report.get("rounds", 0),
            "speaker_contributions": fix_report.get("speaker_contributions", {}),
        }
        
        # 输出补齐贡献统计
        if fix_report.get("insertions", 0) > 0:
            print(f"  [RoleKPI] ✅ 补齐成功: {fix_report['insertions']}句插入, {fix_report['rounds']}轮修复")
            
            # 输出Challenge贡献统计
            speaker_contributions = fix_report.get("speaker_contributions", {})
            if speaker_contributions:
                print(f"  [Challenge] 补齐贡献统计:")
                for speaker, contributions in speaker_contributions.items():
                    challenge_count = contributions.get("challenge", 0)
                    commitment_count = contributions.get("commitment", 0)
                    print(f"    {speaker}: Challenge={challenge_count}, Commitment={commitment_count}")
        else:
            print(f"  [RoleKPI] ✅ 初始验证通过，无需补齐")
        
    except RoleKPIHardFail as e:
        print(f"  [RoleKPI] ❌ 补齐失败: {e}")
        role_kpi_report = {
            "enabled": True,
            "success": False,
            "error": str(e),
            "issues": e.issues
        }
    except Exception as e:
        print(f"  [RoleKPI] ⚠️ 补齐异常: {e}")
        role_kpi_report = {
            "enabled": False,
            "error": str(e)
        }
    
    # 6. 使用行业模板验证（在RoleKPI补齐之后）
    speaker_stats = {}
    for line in text.split('\n'):
        # 跳过Action Item行和Decision行
        if line.strip().startswith("Action Item") or line.strip().startswith("Decision:"):
            continue
        
        match = re.search(r'^([^:]+):', line)
        if match:
            speaker = match.group(1).strip()
            # 只统计真实对话speaker（排除"Owner"等关键词）
            if speaker and not speaker.startswith("Owner:"):
                speaker_stats[speaker] = speaker_stats.get(speaker, 0) + 1
    
    is_valid, failures = validate_dialogue_quality(text, skeleton, "en", speaker_stats)
    
    if not is_valid:
        print(f"  [模板验证] 发现问题: {', '.join(failures[:3])}")
    
    # 7. 移除残留中文（最后清理）
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        if '<<Core:' in line or 'Action Item' in line or 'Decision:' in line:
            cleaned_lines.append(line)
        elif re.search(r'[\u4e00-\u9fff]', line):
            print(f"  [过滤] 移除中文行: {line[:60]}...")
        else:
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    
    if is_valid:
        print(f"  [后处理] ✅ 验证通过")
    else:
        print(f"  [后处理] ⚠️ 部分问题: {', '.join(failures[:2])}")
    
    return text, is_valid, failures, role_kpi_report


def generate_dialogue_text(job: Dict[str, Any], max_retries: int = 3) -> Tuple[str, Dict[str, Any]]:
    """
    生成对话文本，带重试机制
    
    返回:
        (dialogue_text, stats)
    """
    profile = {
        "job_function": job["profession"],
        "work_content": job["scenario_setting"],
        "seniority": "Senior",
        "use_case": "Internal Meeting"
    }
    
    # 使用job中的参数
    people_count = job.get("people_count", DEFAULT_PEOPLE_COUNT)
    target_words = job.get("target_words", DEFAULT_WORD_COUNT)
    language = "英语"  # 强制使用英语（用户要求）
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"  [重试 {attempt}/{max_retries-1}]")
            
            # 生成对话
            lines, rewrite_info = _generate_dialogue_lines(
                profile=profile,
                scenario=job["scenario_setting"],
                core=job["core_content"],
                people=people_count,
                target_len=target_words,
                language=language
            )
            
            # 渲染对话文本
            dialogue_text = _render_dialogue_text(lines)
            
            # 后处理（传入scenario和core用于行业识别）
            processed_text, is_valid, failures, role_kpi_report = post_process_dialogue(
                dialogue_text, 
                job["profession"],
                job["scenario_setting"],
                job["core_content"],
                people_count
            )
            
            # 统计信息（排除Action Item和Decision行）
            speaker_counts = {}
            for line in processed_text.split('\n'):
                # 跳过Action Item和Decision行
                if line.strip().startswith("Action Item") or line.strip().startswith("Decision:"):
                    continue
                
                match = re.search(r'^([^:]+):', line)
                if match:
                    speaker = match.group(1).strip()
                    # 只统计真实对话speaker
                    if speaker and not speaker.startswith("Owner:"):
                        speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
            
            # 统计Challenge和Commitment数量
            challenge_total = 0
            commitment_total = 0
            if role_kpi_report.get("speaker_contributions"):
                for contributions in role_kpi_report["speaker_contributions"].values():
                    challenge_total += contributions.get("challenge", 0)
                    commitment_total += contributions.get("commitment", 0)
            
            stats = {
                "text_length": len(processed_text),
                "line_count": len([l for l in processed_text.split('\n') if l.strip()]),
                "speaker_count": len(speaker_counts),
                "is_valid": is_valid,
                "validation_failures": failures,
                "role_kpi_report": role_kpi_report,
                "challenge_count": challenge_total,
                "commitment_count": commitment_total,
            }
            
            if is_valid:
                return processed_text, stats
            elif attempt < max_retries - 1:
                print(f"  [验证失败，准备重试]")
                continue
            else:
                print(f"  [警告] 达到最大重试次数，使用当前版本")
                return processed_text, stats
        
        except Exception as e:
            print(f"  [错误] 生成失败: {e}")
            if attempt < max_retries - 1:
                continue
            else:
                raise
    
    raise RuntimeError("生成对话失败")


def process_one_job(job: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
    """处理单个任务"""
    profession = job["profession"]
    index = job["index"]
    
    print(f"\n{'='*80}")
    print(f"[开始] 场景{index}: {profession}")
    print(f"{'='*80}")
    
    try:
        # 生成对话文本
        print(f"[场景{index}] 生成行业会议对话...")
        dialogue_text, stats = generate_dialogue_text(job, max_retries=3)
        
        # 生成文件名
        profession_cleaned = profession.replace('/', '_').replace('\\', '_').replace(':', '_').replace('｜', '_')
        people_count = job.get("people_count", DEFAULT_PEOPLE_COUNT)
        target_words = job.get("target_words", DEFAULT_WORD_COUNT)
        filename = f"场景{index}_{profession_cleaned}_people{people_count}_words{target_words}_en.txt"
        output_path = output_dir / filename
        
        # 保存对话文本
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(dialogue_text)
        
        validation_status = "✅ 通过" if stats['is_valid'] else f"⚠️ 部分问题: {', '.join(stats['validation_failures'])}"
        
        print(f"[场景{index}] 📄 已保存: {output_path.name}")
        print(f"[场景{index}] 📊 统计: {stats['text_length']} 字符, {stats['line_count']} 行")
        print(f"[场景{index}] {validation_status}")
        
        # 【新增】输出Challenge统计
        challenge_count = stats.get("challenge_count", 0)
        commitment_count = stats.get("commitment_count", 0)
        if challenge_count > 0 or commitment_count > 0:
            print(f"[场景{index}] 🎯 补齐: Challenge={challenge_count}, Commitment={commitment_count}")
        
        return {
            "index": index,
            "profession": profession,
            "success": True,
            "file_path": filename,
            "chars": stats["text_length"],
            "lines": stats["line_count"],
            "is_valid": stats["is_valid"],
            "validation_failures": stats["validation_failures"],
            "challenge_count": challenge_count,
            "commitment_count": commitment_count,
            "role_kpi_report": stats.get("role_kpi_report", {}),
        }
    
    except Exception as e:
        print(f"[场景{index}] ❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        raise


def main():
    """主函数"""
    print("="*80)
    print("批量生成：13个职业场景行业会议对话文本（最新版）")
    print(f"默认参数: 人物={DEFAULT_PEOPLE_COUNT}, 字数={DEFAULT_WORD_COUNT}, 语言=英语")
    print(f"输入文件: {INPUT_FILE.name}")
    print("="*80)
    
    # 1. 解析输入文件
    print(f"\n[步骤1] 解析输入文件")
    if not INPUT_FILE.exists():
        print(f"[错误] 文件不存在: {INPUT_FILE}")
        return
    
    jobs = parse_input_file(INPUT_FILE)
    
    if len(jobs) != 13:
        print(f"[警告] 解析到 {len(jobs)} 个职业，期望13个")
    
    # 2. 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 3. 批量生成
    print(f"\n[步骤2] 批量生成（共 {len(jobs)} 个）")
    results = []
    
    for job in jobs:
        result = process_one_job(job, OUTPUT_DIR)
        results.append(result)
    
    # 4. 输出摘要
    print("\n" + "="*80)
    print("✅ 批量生成完成！")
    print("="*80)
    
    valid_count = sum(1 for r in results if r['is_valid'])
    challenge_total = sum(r.get('challenge_count', 0) for r in results)
    commitment_total = sum(r.get('commitment_count', 0) for r in results)
    
    print(f"成功: {len(results)}/{len(jobs)}")
    print(f"验证通过: {valid_count}/{len(results)}")
    print(f"总计Challenge补齐: {challenge_total}条")
    print(f"总计Commitment补齐: {commitment_total}条")
    
    print(f"\n各场景统计:")
    for result in results:
        status = "✅" if result['is_valid'] else "⚠️"
        challenge_count = result.get('challenge_count', 0)
        commitment_count = result.get('commitment_count', 0)
        
        # 基本信息
        print(f"  {status} 场景{result['index']} - {result['profession']}: "
              f"{result['chars']} 字符, {result['lines']} 行")
        
        # Challenge/Commitment统计（如果有补齐）
        if challenge_count > 0 or commitment_count > 0:
            print(f"     补齐: Challenge={challenge_count}, Commitment={commitment_count}")
        
        # 验证问题（如果有）
        if not result['is_valid'] and result['validation_failures']:
            print(f"     问题: {', '.join(result['validation_failures'][:2])}")
    
    print(f"\n📁 输出目录: {OUTPUT_DIR}")
    print("="*80)


if __name__ == "__main__":
    main()

