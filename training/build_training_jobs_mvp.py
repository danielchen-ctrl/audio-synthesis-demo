import argparse
import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training.scenario_bank import JOB_FUNCTIONS, SCENARIO_BANK
from training.translation_helpers import localize_profile_value, translate_scenario_and_core


def generate_seed(profession: str, scene_id: str, language: str, word_count: int, people_count: int) -> int:
    key = f"{profession}_{scene_id}_{language}_{word_count}_{people_count}"
    return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)


def select_work_content(profession: str) -> str:
    mapping = {
        "医疗健康": "医疗服务供应商",
        "人力资源与招聘": "招聘与人才获取",
        "娱乐/媒体": "内容制作",
        "建筑与工程行业": "工程规划与施工",
        "汽车行业": "整车制造",
        "咨询/专业服务": "管理咨询",
        "法律服务": "法务/合规",
        "金融/投资": "投资银行",
        "零售行业": "零售运营",
        "保险行业": "保险销售与理赔",
        "房地产": "房地产开发",
        "人工智能/科技": "产品研发",
        "制造业": "生产运营",
    }
    return mapping.get(profession, "综合管理")


def select_seniority(profession: str, people_count: int) -> str:
    if people_count >= 5:
        return random.choice(["C层/创始人", "总监"])
    if people_count >= 3:
        return random.choice(["经理", "主管"])
    return random.choice(["高级职员", "经理"])


def build_training_jobs_mvp(output_file: str, base_seed: int = 20260126):
    random.seed(base_seed)
    jobs = []
    mvp_languages = ["中文", "英语"]
    mvp_word_counts = [500, 1500, 3000]
    max_scenarios_per_profession = 5

    for profession in JOB_FUNCTIONS:
        scenarios = SCENARIO_BANK.get(profession, [])[:max_scenarios_per_profession]
        for scenario_idx, scenario_obj in enumerate(scenarios):
            scene_id = f"{profession}-{scenario_idx + 1:02d}"
            scenario_cn = scenario_obj.scenario_setting_cn
            core_cn = scenario_obj.core_content_cn
            people_range = scenario_obj.people_count_range
            tags = scenario_obj.tags
            for language in mvp_languages:
                scenario_text, core_text, fallback_used = translate_scenario_and_core(scenario_cn, core_cn, language)
                for word_count in mvp_word_counts:
                    min_people, max_people = people_range
                    people_count = random.choice(
                        [p for p in range(min_people, min(max_people, 5) + 1) if p >= 2]
                    )
                    jobs.append(
                        {
                            "job_function": localize_profile_value(profession, language),
                            "work_content": localize_profile_value(select_work_content(profession), language),
                            "seniority": localize_profile_value(select_seniority(profession, people_count), language),
                            "scenario": scenario_text,
                            "core_content": core_text,
                            "language": language,
                            "people_count": people_count,
                            "word_count": word_count,
                            "seed": generate_seed(profession, scene_id, language, word_count, people_count),
                            "meta": {
                                "tags": tags,
                                "scenario_id": scene_id,
                                "bucket": word_count,
                                "translate_fallback": fallback_used,
                            },
                        }
                    )

    with open(output_file, "w", encoding="utf-8") as f:
        for job in jobs:
            f.write(json.dumps(job, ensure_ascii=False) + "\n")
    return {"total": len(jobs)}


def main():
    parser = argparse.ArgumentParser(description="生成训练任务清单（MVP版本）")
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--seed", type=int, default=20260126)
    args = parser.parse_args()
    build_training_jobs_mvp(args.out, args.seed)


if __name__ == "__main__":
    main()
