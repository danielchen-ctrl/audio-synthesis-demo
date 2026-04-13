#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量长对话训练数据生成
==============================
生成矩阵：
  - 14 个行业模板
  - 6  个字数档位：5000 / 10000 / 20000 / 30000 / 40000 / 50000
  - 2  种语言：中文 / 英语
  - 5  种说话人数：2 / 3 / 4 / 5 / 6
  = 14 × 6 × 2 × 5 = 840 个训练文件

策略：
  每个 (模板 × 语言 × 说话人数) 组合共 140 个 base job
  每个 base job 调用 API 生成多段（每段 3000 字），拼接至 ≥50000 字
  再按字数切分，导出 6 个档位文件 → 总 840 个文件

用法：
  cd D:/ui_auto_test/audio-synthesis-demo
  python tools/generation/batch_long_dialogue_training.py
"""

import re
import requests
import json
import time
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# ─── 配置 ──────────────────────────────────────────────────────────────────
BASE_URL    = "http://127.0.0.1:8899"
OUT_DIR     = Path(__file__).resolve().parent.parent.parent / "demo" / "training_long_dialogue"
CHARS_PER_SEGMENT  = 3000        # 服务端单次上限
MAX_CHARS_TARGET   = 51000       # 保证 ≥50000
RETRY_TIMES        = 3
RETRY_SLEEP        = 8           # 失败重试等待秒数
INTER_CALL_SLEEP   = 2           # 正常调用间隔秒数

WORD_COUNT_LEVELS = [5000, 10000, 20000, 30000, 40000, 50000]

LANGUAGES = [
    {"short": "zh", "backend": "Chinese",  "display": "中文"},
    {"short": "en", "backend": "English",  "display": "英语"},
]

SPEAKER_COUNTS = [2, 3, 4, 5, 6]

# ─── 14 个行业模板 ──────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "id":               "ai_tech",
        "label":            "人工智能/科技｜付费转化",
        "industry":         "人工智能/科技",
        "scenario":         "AI产品付费转化策略讨论",
        "core_content":     (
            "围绕付费转化漏斗优化、付费门槛设计与试用策略展开深度讨论，"
            "分析数据回收方式和用户价值感知提升方案，形成付费转化优化方案和实验计划"
        ),
        "scenario_en":      "AI Product Paid Conversion Strategy Discussion",
        "core_content_en":  (
            "In-depth discussion on optimizing paid conversion funnels, payment threshold design and free-trial strategies, "
            "analyzing data collection methods and user value perception improvements, "
            "forming a paid conversion optimization plan and experiment roadmap."
        ),
    },
    {
        "id":               "media_strategy",
        "label":            "娱乐/媒体｜战略周会",
        "industry":         "娱乐/媒体",
        "scenario":         "娱乐媒体公司战略周会讨论",
        "core_content":     (
            "围绕业务目标进展、资源投入分配、重点风险识别和下周行动计划展开讨论，"
            "形成战略周会的重点决策和分工安排"
        ),
        "scenario_en":      "Entertainment Media Company Strategic Weekly Meeting",
        "core_content_en":  (
            "Discussion on business objective progress, resource allocation decisions, key risk identification, "
            "and next-week action plans, forming key decisions and clear task assignments for the strategic weekly meeting."
        ),
    },
    {
        "id":               "test_dev",
        "label":            "测试开发｜支付项目",
        "industry":         "测试开发",
        "scenario":         "支付项目测试质量复盘",
        "core_content":     (
            "围绕支付项目的链路完整性、异常兜底策略和上线风险展开讨论，"
            "涵盖支付接入、下单回调、退款安全、对账差错和稳定性准入，"
            "形成测试范围、风险清单和上线准入结论"
        ),
        "scenario_en":      "Payment Project Test Quality Review",
        "core_content_en":  (
            "Discussion on payment project end-to-end link integrity, exception fallback strategies and launch risks, "
            "covering payment gateway integration, order callbacks, refund security, reconciliation errors and stability readiness, "
            "forming test scope, risk checklist and launch acceptance conclusions."
        ),
    },
    {
        "id":               "hr_recruit",
        "label":            "人力资源与招聘｜招聘补岗",
        "industry":         "人力资源与招聘",
        "scenario":         "招聘补岗策略与渠道讨论",
        "core_content":     (
            "围绕岗位缺口分析、候选人画像定义、招聘渠道策略和到岗时间压力展开讨论，"
            "明确补岗优先级、招聘策略和推进节奏"
        ),
        "scenario_en":      "Recruitment Gap-Filling Strategy and Channel Discussion",
        "core_content_en":  (
            "Discussion on headcount gap analysis, candidate profile definition, recruitment channel strategy "
            "and onboarding deadline pressure, clarifying hiring priorities, sourcing strategy and execution pace."
        ),
    },
    {
        "id":               "commercialization",
        "label":            "娱乐/媒体｜艺人商业化",
        "industry":         "商业化",
        "scenario":         "艺人品牌商业化合作策略讨论",
        "core_content":     (
            "围绕艺人商业定位、品牌匹配度、报价策略、执行风险和转化目标展开讨论，"
            "形成艺人商业化推进策略和合作判断"
        ),
        "scenario_en":      "Artist Brand Commercialization Partnership Strategy Discussion",
        "core_content_en":  (
            "Discussion on artist commercial positioning, brand fit assessment, pricing strategy, "
            "execution risks and conversion targets, forming artist commercialization strategy and partnership evaluation."
        ),
    },
    {
        "id":               "construction",
        "label":            "建筑与工程行业｜项目交付",
        "industry":         "建筑与工程行业",
        "scenario":         "建筑工程项目交付进度与风险讨论",
        "core_content":     (
            "围绕项目交付进度、现场施工问题、成本控制、风险处理和验收节点展开讨论，"
            "形成项目交付问题清单和推进方案"
        ),
        "scenario_en":      "Construction Project Delivery Progress and Risk Discussion",
        "core_content_en":  (
            "Discussion on project delivery schedule, on-site construction issues, cost control, "
            "risk mitigation and acceptance milestones, forming a project delivery issue list and advancement plan."
        ),
    },
    {
        "id":               "consulting",
        "label":            "咨询/专业服务｜客户拓展",
        "industry":         "咨询/专业服务",
        "scenario":         "咨询公司客户拓展策略讨论",
        "core_content":     (
            "围绕客户诉求分析、方案切入点、关系推进策略、报价策略和交付匹配性展开讨论，"
            "形成客户拓展策略和下一步推进动作"
        ),
        "scenario_en":      "Consulting Firm Client Development Strategy Discussion",
        "core_content_en":  (
            "Discussion on client needs analysis, solution entry points, relationship advancement strategy, "
            "pricing strategy and delivery fit, forming a client development strategy and concrete next steps."
        ),
    },
    {
        "id":               "legal",
        "label":            "法律服务｜法顾专项",
        "industry":         "法律服务",
        "scenario":         "法律顾问专项案件处理讨论",
        "core_content":     (
            "围绕法律风险识别、证据材料梳理、处理方案设计、边界判断和执行安排展开讨论，"
            "形成法顾专项的处理路径和分工建议"
        ),
        "scenario_en":      "Legal Counsel Special Case Handling Discussion",
        "core_content_en":  (
            "Discussion on legal risk identification, evidence review, solution design, "
            "boundary judgments and execution arrangements, forming a case handling pathway and work division."
        ),
    },
    {
        "id":               "finance",
        "label":            "金融/投资｜资产配置",
        "industry":         "金融/投资",
        "scenario":         "投资组合资产配置策略讨论",
        "core_content":     (
            "围绕配置目标设定、风险偏好评估、资金安排、收益预期和调整策略展开讨论，"
            "形成清晰的资产配置建议和风险提示"
        ),
        "scenario_en":      "Investment Portfolio Asset Allocation Strategy Discussion",
        "core_content_en":  (
            "Discussion on allocation objective setting, risk tolerance assessment, fund arrangement, "
            "return expectations and rebalancing strategy, forming clear asset allocation recommendations and risk disclosures."
        ),
    },
    {
        "id":               "retail",
        "label":            "零售行业｜会员复购",
        "industry":         "零售行业",
        "scenario":         "会员复购提升策略讨论",
        "core_content":     (
            "围绕会员分层运营、活动策略设计、复购触达方式、门店配合和效果验证展开讨论，"
            "形成会员复购提升方案和执行节奏"
        ),
        "scenario_en":      "Member Repurchase Enhancement Strategy Discussion",
        "core_content_en":  (
            "Discussion on member tiered operations, promotional activity strategy, repurchase outreach methods, "
            "store coordination and performance verification, forming a member repurchase improvement plan and execution cadence."
        ),
    },
    {
        "id":               "insurance",
        "label":            "保险行业｜保险质检",
        "industry":         "保险行业",
        "scenario":         "保险销售质检问题复盘讨论",
        "core_content":     (
            "围绕录音质检结果、销售话术合规风险、培训改进方案和问题闭环机制展开讨论，"
            "形成保险质检问题结论和改进动作"
        ),
        "scenario_en":      "Insurance Sales Quality Inspection Problem Review",
        "core_content_en":  (
            "Discussion on call recording quality inspection results, sales script compliance risks, "
            "training improvement plans and issue closure mechanisms, forming quality inspection conclusions and improvement actions."
        ),
    },
    {
        "id":               "medical",
        "label":            "医疗健康｜慢病随访",
        "industry":         "医疗行业",
        "scenario":         "慢病患者随访沟通",
        "core_content":     (
            "围绕患者症状变化、用药执行情况、复查节点安排、风险提示和患者配合度展开真实交流，"
            "形成清晰的随访安排、复查节点和注意事项"
        ),
        "scenario_en":      "Chronic Disease Patient Follow-up Communication",
        "core_content_en":  (
            "Genuine conversation around patient symptom changes, medication compliance, follow-up appointment scheduling, "
            "risk alerts and patient cooperation, forming clear follow-up arrangements, check-up milestones and precautions."
        ),
    },
    {
        "id":               "realestate",
        "label":            "房地产｜项目去化",
        "industry":         "房地产",
        "scenario":         "房地产项目去化策略与渠道讨论",
        "core_content":     (
            "围绕去化压力分析、客源结构、渠道效率提升、价格策略和案场转化率展开讨论，"
            "形成项目去化提效方案和短期动作安排"
        ),
        "scenario_en":      "Real Estate Project Inventory Clearance Strategy and Channel Discussion",
        "core_content_en":  (
            "Discussion on inventory pressure analysis, buyer source structure, channel efficiency improvement, "
            "pricing strategy and sales site conversion rate, forming an inventory clearance improvement plan and short-term actions."
        ),
    },
    {
        "id":               "manufacturing",
        "label":            "制造业｜产线提效",
        "industry":         "制造业",
        "scenario":         "制造业产线效率提升专项讨论",
        "core_content":     (
            "围绕产线瓶颈工序识别、设备效率优化、良率波动分析、排产协同和异常处理机制展开讨论，"
            "形成产线提效方案和关键改善动作"
        ),
        "scenario_en":      "Manufacturing Production Line Efficiency Improvement Discussion",
        "core_content_en":  (
            "Discussion on production line bottleneck identification, equipment efficiency optimization, yield fluctuation analysis, "
            "production scheduling coordination and anomaly handling mechanisms, "
            "forming a production line improvement plan and key improvement actions."
        ),
    },
]


# ─── 翻译工具 ─────────────────────────────────────────────────────────────

def _cjk_ratio(text: str) -> float:
    """Return fraction of non-whitespace characters that are CJK."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    return sum(1 for c in chars if "\u4e00" <= c <= "\u9fff") / len(chars)


_GT_URL   = "https://translate.googleapis.com/translate_a/single"
_GT_CHUNK = 800    # chars per POST request (safe for Chinese text)
_NO_PROXY = {"http": None, "https": None}


def _translate_chunk(chunk: str) -> str:
    """Translate one chunk via Google Translate POST (proxy-bypassed)."""
    # Use POST to avoid URL length limits for Chinese text
    data = {"client": "gtx", "sl": "auto", "tl": "en", "dt": "t", "q": chunk}
    for attempt in range(6):
        try:
            resp = requests.post(_GT_URL, data=data, proxies=_NO_PROXY, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            translated = "".join(item[0] for item in result[0] if item[0])
            translated = re.sub(r"(?i)speaker\s*(\d+)\s*:", r"Speaker \1:", translated)
            return translated
        except Exception as exc:
            exc_str = str(exc)
            if "429" in exc_str:
                # Rate-limited: back off exponentially (60s, 120s, 180s, ...)
                wait = 60 * (attempt + 1)
                _log(f"  [翻译] 第{attempt+1}次429限速，等待{wait}秒后重试...")
                time.sleep(wait)
            else:
                _log(f"  [翻译] 第{attempt+1}次失败: {exc}")
                time.sleep(5)
    return chunk  # return original only after all retries exhausted


def _translate_to_english(text: str) -> str:
    """
    Translate Chinese dialogue text to English, split into safe-size chunks.
    Preserves blank lines and Speaker N: format.
    """
    lines = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        line_len = len(line) + 1
        if current and current_len + line_len > _GT_CHUNK:
            chunks.append("\n".join(current))
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len
    if current:
        chunks.append("\n".join(current))

    translated_parts: list[str] = []
    for chunk in chunks:
        if _cjk_ratio(chunk) < 0.1:
            translated_parts.append(chunk)
            continue
        translated_parts.append(_translate_chunk(chunk))
        time.sleep(2.0)   # respect rate limit: 2s between chunks

    return "\n".join(translated_parts)


# ─── 工具函数 ──────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    safe = msg.encode("gbk", errors="replace").decode("gbk")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {safe}", flush=True)


def generate_segment(template: dict, language_backend: str, speaker_count: int) -> str:
    """调用 /api/generate_text，返回对话文本。

    英文模式：直接使用 scenario_en / core_content_en 原生生成英文，
    不再走中文生成+翻译路径（翻译会被 rate limit 卡死，且引入字段污染）。
    """
    is_english = language_backend == "English"
    scenario     = template["scenario_en"]     if is_english else template["scenario"]
    core_content = template["core_content_en"] if is_english else template["core_content"]

    payload = {
        "scenario":       scenario,
        "core_content":   core_content,
        "people_count":   speaker_count,
        "word_count":     3000,
        "audio_language": language_backend,
        "language":       language_backend,
        "template_label": template["label"],
        "title":          scenario,
        "tags":           ["training", "long_dialogue", template["id"]],
        "folder":         "training_long_dialogue",
        "profile": {
            "job_function": template["industry"],
            "work_content": scenario,
            "use_case":     f"{template['industry']}｜{template['label'].split('｜')[-1]}",
        },
        "generation_context": {
            "domain":      template["industry"],
            "scene_type":  template["label"].split("｜")[-1],
            "scene_goal":  scenario,
            "deliverable": core_content,
        },
    }
    resp = requests.post(
        f"{BASE_URL}/api/generate_text",
        json=payload,
        timeout=180,
        proxies={"http": None, "https": None},
    )
    resp.raise_for_status()
    data = resp.json()
    text = (data.get("dialogue_text") or data.get("text") or "").strip()
    return text


def truncate_at_boundary(full_text: str, target_chars: int) -> str:
    """在对话轮次边界截断，保证结果 ≤ target_chars（从尾部找完整行）"""
    if len(full_text) <= target_chars:
        return full_text
    lines = full_text.split("\n")
    result_lines = []
    total = 0
    for line in lines:
        line_len = len(line) + 1  # +1 for newline
        if total + line_len > target_chars and result_lines:
            break
        result_lines.append(line)
        total += line_len
    return "\n".join(result_lines)


def safe_filename(text: str) -> str:
    for ch in r'\/:*?"<>|':
        text = text.replace(ch, "_")
    return text


# ─── 主流程 ────────────────────────────────────────────────────────────────

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 构建 base jobs（140 个）
    base_jobs = [
        (tmpl, lang, spk)
        for tmpl   in TEMPLATES
        for lang   in LANGUAGES
        for spk    in SPEAKER_COUNTS
    ]
    total_base  = len(base_jobs)
    total_files = total_base * len(WORD_COUNT_LEVELS)

    _log(f"===== 批量长对话训练数据生成 =====")
    _log(f"Base jobs: {total_base} | Output files: {total_files}")
    _log(f"Output dir: {OUT_DIR}")
    _log(f"Word count levels: {WORD_COUNT_LEVELS}")
    _log("=" * 40)

    segments_per_job = -(-MAX_CHARS_TARGET // CHARS_PER_SEGMENT)  # ceiling div
    started_at = time.time()

    done_jobs = 0
    skip_jobs = 0
    fail_jobs = 0

    for job_idx, (tmpl, lang, spk) in enumerate(base_jobs, 1):
        prefix = f"{tmpl['id']}_{lang['short']}_spk{spk}"

        # 检查是否所有档位文件都已存在
        all_paths = {
            wc: OUT_DIR / f"{prefix}_wc{wc}.txt"
            for wc in WORD_COUNT_LEVELS
        }
        if all(p.exists() for p in all_paths.values()):
            skip_jobs += 1
            _log(f"[{job_idx}/{total_base}] SKIP  {prefix}")
            continue

        _log(f"[{job_idx}/{total_base}] START {prefix}  "
             f"(行业={tmpl['industry']}, 语言={lang['display']}, 说话人={spk})")

        # ── 生成足够多的片段 ──────────────────────────
        segments: list[str] = []
        total_chars = 0
        seg_num = 0
        fail_seg = 0

        while total_chars < MAX_CHARS_TARGET:
            seg_num += 1
            text = ""
            for retry in range(RETRY_TIMES):
                try:
                    text = generate_segment(tmpl, lang["backend"], spk)
                    if text:
                        break
                except Exception as exc:
                    _log(f"  片段 {seg_num} 第{retry+1}次失败: {exc}")
                    time.sleep(RETRY_SLEEP)

            if not text:
                fail_seg += 1
                _log(f"  片段 {seg_num} 全部重试失败，跳过此片段")
                if fail_seg >= 5:
                    _log(f"  连续失败过多，放弃 job {prefix}")
                    fail_jobs += 1
                    break
                continue

            fail_seg = 0
            segments.append(text)
            total_chars += len(text)
            _log(f"  片段 {seg_num}/{segments_per_job} +{len(text)}字 → 累计{total_chars}字")
            time.sleep(INTER_CALL_SLEEP)

        if total_chars == 0:
            continue

        # ── 拼接全文 ──────────────────────────────────
        full_text = "\n\n".join(segments)

        # ── 按档位切分并保存 ──────────────────────────
        saved = []
        for wc in WORD_COUNT_LEVELS:
            out_path = all_paths[wc]
            if not out_path.exists():
                chunk = truncate_at_boundary(full_text, wc)
                out_path.write_text(chunk, encoding="utf-8")
                saved.append(f"wc{wc}({len(chunk)}字)")

        done_jobs += 1
        elapsed = time.time() - started_at
        eta_secs = (elapsed / done_jobs) * (total_base - job_idx) if done_jobs else 0
        eta_str  = str(timedelta(seconds=int(eta_secs)))
        _log(f"  ✓ 已保存: {', '.join(saved)}  "
             f"| 耗时 {elapsed/60:.1f}min | 预计剩余 {eta_str}")

    # ── 汇总 ──────────────────────────────────────────
    elapsed_total = time.time() - started_at
    _log("=" * 40)
    _log(f"完成! 完成={done_jobs}, 跳过={skip_jobs}, 失败={fail_jobs}")
    _log(f"总耗时: {timedelta(seconds=int(elapsed_total))}")
    _log(f"输出目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
