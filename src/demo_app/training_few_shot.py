#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
training_few_shot.py
====================
从训练产出数据（output/training_v2/*/passed/）中检索主题匹配的对话样本，
作为 few-shot 示例注入到生成请求中，提升生成对话的主题贴合度与质量。

与 few_shot_selector.py 的区别：
  few_shot_selector  基于 domain/language 匹配通用语料（demo/training_long_dialogue/）
  本模块            基于 template_id/language 匹配主题专属训练样本，优先级更高。
"""
from __future__ import annotations

import json
import logging
import random
import re
from collections import OrderedDict
from pathlib import Path

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[2]
_TRAINING_OUT_DIR = _ROOT / "output" / "training_v2"
_OLD_CORPUS_DIR   = _ROOT / "demo" / "training_long_dialogue"

# 旧语料库 domain_id → 对应的 template_id 列表
# 旧语料比新训练数据粒度粗（行业级 vs 主题级），用作兜底
_OLD_DOMAIN_TO_TEMPLATES: dict[str, list[str]] = {
    "medical":          ["t01_medical_chronic"],
    "hr_recruit":       ["t02_hr_recruitment"],
    "media_strategy":   ["t03_entertainment_celebrity", "t14_media_weekly"],
    "construction":     ["t04_engineering_delivery"],
    "ai_tech":          ["t05_auto_launch", "t12_ai_paid_conversion"],
    "consulting":       ["t06_consulting_expansion"],
    "legal":            ["t07_legal_retainer", "t15_legal_ad_compliance"],
    "finance":          ["t08_wealth_allocation"],
    "retail":           ["t09_retail_repurchase"],
    "insurance":        ["t10_insurance_qc", "t16_insurance_sales_insight"],
    "realestate":       ["t11_realestate_destock"],
    "manufacturing":    ["t13_manufacturing_efficiency"],
    "commercialization":["t12_ai_paid_conversion", "t14_media_weekly"],
    "test_dev":         ["t17_payment_integration", "t18_payment_refund_security",
                         "t19_payment_reconciliation", "t20_moments_publish",
                         "t21_moments_interaction", "t22_moments_privacy"],
}

# 旧语料库文件的基础分（低于新训练数据最低分 80，确保新数据优先）
_OLD_CORPUS_BASE_SCORE = 65.0

# ── Template label → ID（22 个预置模板，对应训练计划 t01-t22）────────────────
_LABEL_TO_TEMPLATE_ID: dict[str, str] = {
    "医疗健康｜慢病随访":          "t01_medical_chronic",
    "人力资源与招聘｜招聘补岗":    "t02_hr_recruitment",
    "娱乐/媒体｜艺人商业化":       "t03_entertainment_celebrity",
    "建筑与工程行业｜项目交付":    "t04_engineering_delivery",
    "汽车行业｜车型投放":          "t05_auto_launch",
    "咨询/专业服务｜客户拓展":     "t06_consulting_expansion",
    "法律服务｜法顾专项":          "t07_legal_retainer",
    "金融/投资｜资产配置":         "t08_wealth_allocation",
    "零售行业｜会员复购":          "t09_retail_repurchase",
    "保险行业｜保险质检":          "t10_insurance_qc",
    "房地产｜项目去化":            "t11_realestate_destock",
    "人工智能/科技｜付费转化":     "t12_ai_paid_conversion",
    "制造业｜产线提效":            "t13_manufacturing_efficiency",
    "娱乐/媒体｜战略周会":         "t14_media_weekly",
    "法律服务｜广告合规":          "t15_legal_ad_compliance",
    "保险行业｜销售洞察":          "t16_insurance_sales_insight",
    "测试开发｜支付接入与交易链路": "t17_payment_integration",
    "测试开发｜退款与资金安全":    "t18_payment_refund_security",
    "测试开发｜对账与稳定性准入":  "t19_payment_reconciliation",
    "测试开发｜朋友圈内容发布与多端分发": "t20_moments_publish",
    "测试开发｜社交互动与状态一致性": "t21_moments_interaction",
    "测试开发｜隐私权限与内容审核": "t22_moments_privacy",
    # UI 合并标签（online_audio_ui.json 中的简写形式）
    "测试开发｜支付项目":          "t17_payment_integration",
    "测试开发｜朋友圈项目":        "t20_moments_publish",
}

# ── 关键词 → template_id（用于手动输入主题文本的模糊匹配）──────────────────
_KEYWORD_RULES: list[tuple[list[str], str]] = [
    (["高血压", "糖尿病", "慢病", "随访", "复诊", "用药", "血压", "血糖", "慢性病"],
     "t01_medical_chronic"),
    (["补岗", "招聘", "HRBP", "HC", "候选人", "面试", "offer", "岗位空缺", "到岗"],
     "t02_hr_recruitment"),
    (["艺人", "代言", "经纪", "品牌代言", "商务合作", "报价", "档期", "宣发"],
     "t03_entertainment_celebrity"),
    (["工程交付", "施工", "工程验收", "延期", "监理", "甲方", "交付节点", "工程进度"],
     "t04_engineering_delivery"),
    (["新车", "车型", "汽车", "经销商", "试驾", "新能源车", "投放", "竞品"],
     "t05_auto_launch"),
    (["咨询", "客户拓展", "商机", "提案", "售前", "合伙人", "需求诊断"],
     "t06_consulting_expansion"),
    (["法律顾问", "法顾", "合同审查", "合规顾问", "律师", "法务", "专项服务"],
     "t07_legal_retainer"),
    (["资产配置", "理财", "投资组合", "高净值", "风险偏好", "基金", "再平衡"],
     "t08_wealth_allocation"),
    (["会员", "复购", "积分", "优惠券", "沉睡", "零售", "用户分层", "复购率"],
     "t09_retail_repurchase"),
    (["保险质检", "录音质检", "话术合规", "质检专员", "违规话术", "销售录音"],
     "t10_insurance_qc"),
    (["楼盘", "去化", "房地产", "置业", "库存", "成交转化", "渠道分销"],
     "t11_realestate_destock"),
    (["AI产品", "付费转化", "免费用户", "订阅", "付费会员", "人工智能", "转化率"],
     "t12_ai_paid_conversion"),
    (["产线", "制造业", "设备稼动率", "良品率", "瓶颈工序", "生产效率", "产线效率"],
     "t13_manufacturing_efficiency"),
    (["战略周会", "内容平台", "商业化策略", "增长数据", "内容策略", "周会"],
     "t14_media_weekly"),
    (["广告合规", "广告素材", "极限词", "宣传用语", "广告审查"],
     "t15_legal_ad_compliance"),
    (["保险销售", "销售转化", "客户异议", "销售洞察", "成交原因", "拒保"],
     "t16_insurance_sales_insight"),
    (["支付接入", "第三方支付", "支付回调", "支付联调", "支付接口", "支付项目",
       "下单接口", "支付验收", "签名校验", "幂等", "接口联调", "支付系统",
       "支付上线", "支付", "联调验收"],
     "t17_payment_integration"),
    (["退款安全", "资金安全", "越权退款", "重复退款", "退款流程", "退款校验"],
     "t18_payment_refund_security"),
    (["对账", "稳定性准入", "压测", "性能基线", "容量评估", "熔断", "账单核对"],
     "t19_payment_reconciliation"),
    (["朋友圈", "动态发布", "多端分发", "小程序", "状态同步", "发布失败", "图文发布"],
     "t20_moments_publish"),
    (["点赞", "评论互动", "互动计数", "社交互动", "并发互动", "状态一致"],
     "t21_moments_interaction"),
    (["隐私可见", "权限控制", "内容审核", "敏感词", "违规内容", "分组可见", "权限校验"],
     "t22_moments_privacy"),
]

# ── 语言目录名 → short code ────────────────────────────────────────────────
_DIR_LANG_TO_SHORT: dict[str, str] = {
    "中文": "zh", "英语": "en", "日语": "ja", "韩语": "ko",
    "法语": "fr", "德语": "de", "西班牙语": "es", "葡萄牙语": "pt", "粤语": "yue",
}

# 语言名别名 → short code（兼容平台任务和 UI 传参）
_LANG_ALIASES: dict[str, str] = {
    "Chinese": "zh", "中文": "zh", "中文（普通话）": "zh",
    "English": "en", "英语": "en",
    "Japanese": "ja", "日语": "ja",
    "Korean": "ko", "韩语": "ko",
    "French": "fr", "法语": "fr",
    "German": "de", "德语": "de",
    "Spanish": "es", "西班牙语": "es",
    "Portuguese": "pt", "葡萄牙语": "pt",
    "Cantonese": "yue", "粤语": "yue",
}

# ── 训练样本索引（懒加载）──────────────────────────────────────────────────
# key: (template_id, lang_short) → [(score, path), ...] sorted by score desc
_INDEX: dict[tuple[str, str], list[tuple[float, Path]]] | None = None

# 文件内容 LRU 缓存
_FILE_CACHE: OrderedDict[str, str] = OrderedDict()
_FILE_CACHE_MAX = 48

# 新训练数据最低分门槛：低于此分的文件不纳入 few-shot 索引（旧语料库不受此限制）
_MIN_NEW_SAMPLE_SCORE = 70.0

# ── 低质量占位符行过滤正则 ────────────────────────────────────────────────
_PLACEHOLDER_RE = re.compile(
    # 中文模板占位符
    r"从(参与者|.*?)角度来看[，,](需要|可以|应该|重点)"
    r"|根据(实际情况|行业惯例|以往经验)[，,]"
    r"|行动项：Speaker\s*\d+跟进"
    r"|T\+\d+天给到方案"
    r"|最新的(达标率|效率指标|完成率|准确率|完成情况)数据显示达到了\d+%"
    r"|通常(耗时|涉及)[X\d]+[天周]"
    # 英文模板占位符（LLM 降级时生成的通用角色描述）
    r"|From a .{2,30} perspective, we should focus on"
    r"|Scenario: A professional business discussion"
    r"|I'll be focused on key constraints and risk areas around Scenario"
    # 英文通用对话降级行
    r"|What steps have you already taken to address this issue"
    r"|I'll need to verify a few things before I can give you"
    r"|Please review the proposed plan and let me know if you have"
)

_MAX_EXCERPT_CHARS = 600
_SKIP_HEAD_RATIO = 0.15

# CJK 字符范围（用于检测非中文文件中的中文污染）
_CJK_RE = re.compile(r"[一-鿿]")


# ── 内部工具 ────────────────────────────────────────────────────────────────

def _read_cached(path: Path) -> str:
    key = str(path)
    if key in _FILE_CACHE:
        _FILE_CACHE.move_to_end(key)
        return _FILE_CACHE[key]
    text = path.read_text(encoding="utf-8")
    _FILE_CACHE[key] = text
    _FILE_CACHE.move_to_end(key)
    while len(_FILE_CACHE) > _FILE_CACHE_MAX:
        _FILE_CACHE.popitem(last=False)
    return text


def _parse_template_id(stem: str) -> str | None:
    """从文件名 stem 解析 template_id。
    格式: {batch}_{t_id}_{m_id}_{wc}_{pc}_{seed}
    示例: b0_smoke_t01_medical_chronic_m01_hypertension_followup_10000_2_123
    """
    m = re.search(r"_(t\d{2}_[a-z_]+?)_m\d{2}_", stem)
    return m.group(1) if m else None


def _parse_old_corpus_stem(stem: str) -> tuple[str, str] | None:
    """从旧语料库文件名 stem 解析 (domain_id, lang_code)。
    格式: {domain_id}_{lang_short}_spk{N}_wc5000
    示例: medical_zh_spk3_wc5000 / hr_recruit_zh_spk3_wc5000
    """
    for lang_code in ("zh", "en", "ja", "ko", "fr", "de", "es", "pt", "yue"):
        marker = f"_{lang_code}_spk"
        if marker in stem:
            domain_id = stem.split(marker)[0]
            return domain_id, lang_code
    return None


def _index_old_corpus(index: dict[tuple[str, str], list[tuple[float, Path]]]) -> int:
    """将 demo/training_long_dialogue/ 的文件按 domain→template 映射纳入索引。
    旧语料打 _OLD_CORPUS_BASE_SCORE 分，确保新训练数据优先命中。
    返回新增条目数。
    """
    if not _OLD_CORPUS_DIR.exists():
        return 0
    added = 0
    for txt_file in _OLD_CORPUS_DIR.glob("*.txt"):
        parsed = _parse_old_corpus_stem(txt_file.stem)
        if not parsed:
            continue
        domain_id, lang_code = parsed
        template_ids = _OLD_DOMAIN_TO_TEMPLATES.get(domain_id, [])
        for t_id in template_ids:
            key = (t_id, lang_code)
            index.setdefault(key, []).append((_OLD_CORPUS_BASE_SCORE, txt_file))
            added += 1
    return added


def _build_index() -> dict[tuple[str, str], list[tuple[float, Path]]]:
    """扫描新训练产出 + 旧语料库，构建统一的 (template_id, lang) → samples 索引。

    优先级：新训练产出（score 80+）> 旧语料库（score 65）
    """
    index: dict[tuple[str, str], list[tuple[float, Path]]] = {}

    # ── 新训练产出：output/training_v2/*/passed/ ──────────────────────────
    new_count = 0
    if _TRAINING_OUT_DIR.exists():
        for batch_dir in _TRAINING_OUT_DIR.iterdir():
            if not batch_dir.is_dir():
                continue
            passed_root = batch_dir / "passed"
            if not passed_root.exists():
                continue
            # 目录层级: passed/{batch_name}/{Category}/{language}/{files}
            for batch_sub in passed_root.iterdir():
                if not batch_sub.is_dir():
                    continue
                for cat_dir in batch_sub.iterdir():
                    if not cat_dir.is_dir():
                        continue
                    for lang_dir in cat_dir.iterdir():
                        if not lang_dir.is_dir():
                            continue
                        lang_code = _DIR_LANG_TO_SHORT.get(lang_dir.name)
                        if not lang_code:
                            continue
                        for txt_file in lang_dir.glob("*.txt"):
                            t_id = _parse_template_id(txt_file.stem)
                            if not t_id:
                                continue
                            score = _read_score(txt_file)
                            if score < _MIN_NEW_SAMPLE_SCORE:
                                continue  # exclude low-quality samples from few-shot
                            key = (t_id, lang_code)
                            index.setdefault(key, []).append((score, txt_file))
                            new_count += 1

    # ── 旧语料库：demo/training_long_dialogue/ ────────────────────────────
    old_count = _index_old_corpus(index)

    # 每个 key 按分数降序排列（新数据分高，自然排在前面）
    for key in index:
        index[key].sort(key=lambda x: x[0], reverse=True)

    total = sum(len(v) for v in index.values())
    logger.info(
        "[training_few_shot] 索引构建完成: %d 个(模板,语言)组合, %d 条目 "
        "（新训练 %d + 旧语料 %d）",
        len(index), total, new_count, old_count,
    )
    return index


def _read_score(txt_file: Path) -> float:
    score_file = txt_file.with_suffix(".score.json")
    if not score_file.exists():
        return 0.0
    try:
        data = json.loads(score_file.read_text(encoding="utf-8"))
        return float(data.get("score", 0))
    except Exception:
        return 0.0


def _get_index() -> dict[tuple[str, str], list[tuple[float, Path]]]:
    global _INDEX
    if _INDEX is None:
        _INDEX = _build_index()
    return _INDEX


def _extract_excerpt(lines: list[str], lang_code: str = "zh") -> str:
    """从 lines 中取一段高质量对话片段（过滤占位符、去重、限长）。"""
    total = len(lines)
    skip = max(0, int(total * _SKIP_HEAD_RATIO))
    max_start = max(skip, total - 40)
    start = random.randint(skip, max_start)

    non_zh = lang_code not in ("zh", "yue")  # non-Chinese files should not contain CJK

    seen: set[str] = set()
    result: list[str] = []
    chars = 0

    for line in lines[start:]:
        if "<<" in line or ">>" in line:
            continue
        if _PLACEHOLDER_RE.search(line):
            continue
        # For non-Chinese files, skip lines with significant CJK content (Chinese bleed-in)
        if non_zh:
            non_ws = [c for c in line if not c.isspace()]
            if non_ws and sum(1 for c in non_ws if _CJK_RE.match(c)) / len(non_ws) > 0.05:
                continue
        content = re.sub(r"^(Speaker|说话人)\s*\d+:\s*", "", line).strip()
        if not content or content in seen:
            continue
        seen.add(content)
        if chars + len(line) + 1 > _MAX_EXCERPT_CHARS:
            break
        result.append(line)
        chars += len(line) + 1

    return "\n".join(result)


# ── 公开 API ──────────────────────────────────────────────────────────────

def resolve_template_id(label_or_topic: str) -> str | None:
    """将 UI 模板标签或手动输入主题文本映射到 template_id。

    策略：
    1. 精确匹配 _LABEL_TO_TEMPLATE_ID（模板下拉选择）
    2. 关键词匹配 _KEYWORD_RULES（手动输入主题文本）
    """
    if not label_or_topic:
        return None
    text = label_or_topic.strip()

    # 精确匹配
    tid = _LABEL_TO_TEMPLATE_ID.get(text)
    if tid:
        return tid

    # 关键词匹配（得分最高的模板）
    best_id, best_hits = None, 0
    for keywords, tid in _KEYWORD_RULES:
        hits = sum(1 for kw in keywords if kw in text)
        if hits > best_hits:
            best_hits, best_id = hits, tid
    return best_id if best_hits >= 1 else None


def get_training_few_shot(template_id: str, language: str) -> str:
    """返回训练数据中 (template_id, language) 对应的对话片段。

    无可用样本时返回空字符串，不抛异常。

    Args:
        template_id: 如 "t01_medical_chronic"
        language:    规范化语言名，如 "Chinese" / "English" / "中文（普通话）"
    """
    if not template_id or not language:
        return ""

    lang_code = _DIR_LANG_TO_SHORT.get(language) or _LANG_ALIASES.get(language)
    if not lang_code:
        return ""

    idx = _get_index()
    samples = idx.get((template_id, lang_code), [])
    if not samples:
        return ""

    # 最多尝试前 3 个高分样本
    for _, path in samples[:3]:
        try:
            text = _read_cached(path)
            lines = [ln for ln in text.splitlines() if ln.strip()]
            excerpt = _extract_excerpt(lines, lang_code=lang_code)
            if excerpt.strip():
                return excerpt
        except Exception:
            continue

    return ""


def invalidate_index() -> None:
    """训练数据有更新时调用，下次请求时重建索引。"""
    global _INDEX
    _INDEX = None
    logger.info("[training_few_shot] 索引已清除，下次访问时重建")
