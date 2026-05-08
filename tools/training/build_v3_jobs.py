#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_v3_jobs.py
================
生成 v3 训练方案的任务 JSONL 文件（按语言分拆，支持并行执行）。

两个 tier：
  short（默认）：短中对话，覆盖宽泛
    中文/英语  说话人 2-6  字数 1k/2k/5k          各 330 tasks
    日语/韩语  说话人 2-4  字数 500/1k/2k          各 198 tasks
    合计：1056 tasks

  long：长对话生成能力专项
    中文/英语  说话人 2-5  字数 10k/20k/30k/40k/50k  各 440 tasks
    日语/韩语  说话人 2-3  字数 2k/3k/5k（bundle上限） 各 132 tasks
    合计：1144 tasks

日语/韩语 long tier 说明：
  bundle 每次生成约 300-800 日文字符，10k+ 目标会被质量门禁（15%阈值）过滤。
  将长目标上限设为 5000（2-chunk路径，实测可达 86-98%），避免产生大量无效数据。

用法：
  python tools/training/build_v3_jobs.py               # 生成 short tier
  python tools/training/build_v3_jobs.py --tier long    # 生成 long tier
  python tools/training/build_v3_jobs.py --tier all     # 生成两个 tier
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from training.translation_helpers import (
    LANGUAGE_DISPLAY_MAP,
    localize_profile_value,
)

# ─────────────────────────────────────────────────────
# 方案参数
# ─────────────────────────────────────────────────────

# short tier：短中对话基础覆盖
LANG_CONFIGS_SHORT = {
    "中文":  {"people_counts": [2, 3, 4, 5, 6], "word_counts": [1000, 2000, 5000],           "batch": "v3_chinese"},
    "英语":  {"people_counts": [2, 3, 4, 5, 6], "word_counts": [1000, 2000, 5000],           "batch": "v3_english"},
    "日语":  {"people_counts": [2, 3, 4],        "word_counts": [500, 1000, 2000],            "batch": "v3_japanese"},
    "韩语":  {"people_counts": [2, 3, 4],        "word_counts": [500, 1000, 2000],            "batch": "v3_korean"},
}

# long tier：长对话专项（字数 10k-50k；日韩上限 5k）
LANG_CONFIGS_LONG = {
    "中文":  {"people_counts": [2, 3, 4, 5],    "word_counts": [10000, 20000, 30000, 40000, 50000], "batch": "v3_long_chinese"},
    "英语":  {"people_counts": [2, 3, 4, 5],    "word_counts": [10000, 20000, 30000, 40000, 50000], "batch": "v3_long_english"},
    "日语":  {"people_counts": [2, 3],           "word_counts": [2000, 3000, 5000],                 "batch": "v3_long_japanese"},
    "韩语":  {"people_counts": [2, 3],           "word_counts": [2000, 3000, 5000],                 "batch": "v3_long_korean"},
}

SEED_BASE = 42


def _make_seed(*parts) -> int:
    key = "|".join(str(p) for p in parts)
    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16) % (2 ** 31)


def _job_function_from_label(label: str) -> str:
    return label.split("｜")[0] if "｜" in label else label


_WORK_CONTENT_MAP = {
    "医疗健康":      "医疗服务供应商",
    "人力资源与招聘": "招聘与人才获取",
    "娱乐/媒体":     "内容制作",
    "建筑与工程行业": "工程规划与施工",
    "汽车行业":      "整车制造",
    "咨询/专业服务": "管理咨询",
    "法律服务":      "法务/合规",
    "金融/投资":     "投资银行",
    "零售行业":      "零售运营",
    "保险行业":      "保险销售与理赔",
    "房地产":        "房地产开发",
    "人工智能/科技": "产品研发",
    "制造业":        "生产运营",
    "测试开发":      "产品研发",
}


def _build_scenario_core(topic: dict, language: str) -> tuple[str, str]:
    """构建任务的 scenario 和 core_content 字段。"""
    example_topic = topic.get("example_topic", "")
    topic_desc = topic.get("topic_description", "")
    keywords = topic.get("core_keywords", [])

    if language == "中文":
        scenario = f"【主题】{example_topic}\n{topic_desc}"
        core = "核心关键词：{}。{}".format("、".join(keywords), topic_desc)
    else:
        lang_tmpl = LANGUAGE_DISPLAY_MAP.get(language) or LANGUAGE_DISPLAY_MAP["英语"]
        # 附带中文原题目作为上下文提示
        scenario = "{}\n[Topic context: {}]".format(lang_tmpl["scenario"], example_topic)
        core = "{}\n[Keywords: {}]".format(lang_tmpl["core"], ", ".join(keywords))

    return scenario, core


def build_jobs_for_language(topics: list[dict], language: str, cfg: dict) -> list[dict]:
    batch = cfg["batch"]
    jobs = []
    for topic in topics:
        jf_cn = _job_function_from_label(topic["label"])
        wc_cn = _WORK_CONTENT_MAP.get(jf_cn, "综合管理")
        scenario, core = _build_scenario_core(topic, language)

        jf = localize_profile_value(jf_cn, language)
        wc = localize_profile_value(wc_cn, language)
        seniority = localize_profile_value("主管", language)

        for people in cfg["people_counts"]:
            for word_count in cfg["word_counts"]:
                seed = _make_seed(topic["id"], language, people, word_count, SEED_BASE)
                jobs.append({
                    "job_function": jf,
                    "work_content": wc,
                    "seniority": seniority,
                    "scenario": scenario,
                    "core_content": core,
                    "language": language,
                    "people_count": people,
                    "word_count": word_count,
                    "seed": seed,
                    "meta": {
                        "batch": batch,
                        "topic_id": f"t{topic['id']}",
                        "template_name": topic["label"],
                        "topic_cn": topic.get("example_topic", ""),
                        "translate_fallback": language != "中文",
                        "scenario_id": f"{batch}_t{topic['id']}_{language}_p{people}_w{word_count}",
                    },
                })
    return jobs


def _build_tier(tier_name: str, lang_configs: dict, topics: list[dict], out_dir: Path) -> int:
    total = 0
    for language, cfg in lang_configs.items():
        jobs = build_jobs_for_language(topics, language, cfg)
        # filename: strip "v3_" prefix for short tier, keep full batch name for long
        fname = f"v3_jobs_{cfg['batch'].replace('v3_', '')}.jsonl"
        out_path = out_dir / fname
        with out_path.open("w", encoding="utf-8") as f:
            for job in jobs:
                f.write(json.dumps(job, ensure_ascii=False) + "\n")
        expected = len(topics) * len(cfg["people_counts"]) * len(cfg["word_counts"])
        print(f"  {language:6} → {fname}  {len(jobs)} tasks  (expected {expected})")
        total += len(jobs)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 v3 训练任务 JSONL 文件")
    parser.add_argument("--tier", choices=["short", "long", "all"], default="short",
                        help="生成哪个 tier：short（默认）/ long / all")
    args = parser.parse_args()

    topics_path = ROOT / "config" / "preset_topics.json"
    topics = json.loads(topics_path.read_text(encoding="utf-8"))
    print(f"Loaded {len(topics)} preset topics  tier={args.tier}")

    out_dir = ROOT / "training" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    grand_total = 0

    if args.tier in ("short", "all"):
        print("\n--- short tier (短/中对话) ---")
        grand_total += _build_tier("short", LANG_CONFIGS_SHORT, topics, out_dir)

    if args.tier in ("long", "all"):
        print("\n--- long tier (长对话 10k-50k) ---")
        grand_total += _build_tier("long", LANG_CONFIGS_LONG, topics, out_dir)

    print(f"\nTotal: {grand_total} tasks")
    print("Run parallel training with:")
    if args.tier in ("long", "all"):
        print("  python tools/training/run_v3_parallel.py --langs chinese english japanese korean --long")
    else:
        print("  python tools/training/run_v3_parallel.py")


if __name__ == "__main__":
    main()
