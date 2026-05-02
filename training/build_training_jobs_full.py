import argparse
import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training.scenario_bank import JOB_FUNCTIONS, SCENARIO_BANK
from training.build_training_jobs_mvp import select_seniority, select_work_content
from training.translation_helpers import localize_profile_value, translate_scenario_and_core


def generate_seed(profession: str, scene_id: str, language: str, word_count: int, people_count: int) -> int:
    key = f"{profession}_{scene_id}_{language}_{word_count}_{people_count}"
    return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)


def build_training_jobs_full(output_file: str, base_seed: int = 20260126, use_translate: bool = True):
    random.seed(base_seed)
    word_counts = [500, 1500, 3000]
    people_counts = [2, 3]
    primary_languages = ["中文", "英语", "日语"]
    secondary_languages = ["韩语", "法语", "德语", "西班牙语", "葡萄牙语", "粤语"]
    jobs = []
    job_id = 1

    for profession in JOB_FUNCTIONS:
        scenarios = SCENARIO_BANK.get(profession, [])
        for scene_idx, scene in enumerate(scenarios, 1):
            scene_id = f"{profession}-{scene_idx:02d}"
            scenario_cn = getattr(scene, "scenario_setting_cn", "")
            core_cn = getattr(scene, "core_content_cn", "")
            languages_for_scene = primary_languages.copy() if scene_idx <= 30 else ["中文"]
            if scene_idx <= 10:
                languages_for_scene += secondary_languages
            for language in languages_for_scene:
                if use_translate:
                    translated_scenario, translated_core, fallback_used = translate_scenario_and_core(
                        scenario_cn, core_cn, language
                    )
                else:
                    translated_scenario, translated_core, fallback_used = translate_scenario_and_core(
                        scenario_cn, core_cn, language
                    )
                for word_count in word_counts:
                    for people_count in people_counts:
                        localized_job_function = localize_profile_value(profession, language)
                        localized_work_content = localize_profile_value(select_work_content(profession), language)
                        localized_seniority = localize_profile_value(select_seniority(profession, people_count), language)
                        jobs.append(
                            {
                                "job_id": job_id,
                                "profession": profession,
                                "scenario_id": scene_id,
                                "language": language,
                                "word_count": word_count,
                                "people_count": people_count,
                                "seed": generate_seed(profession, scene_id, language, word_count, people_count),
                                "profile": {
                                    "job_function": localized_job_function,
                                    "work_content": localized_work_content,
                                    "seniority": localized_seniority,
                                    "use_case": localize_profile_value("客户洽谈", language),
                                },
                                "scenario": translated_scenario,
                                "core_content": translated_core,
                                "translate_fallback": fallback_used,
                            }
                        )
                        job_id += 1

    with open(output_file, "w", encoding="utf-8") as f:
        for job in jobs:
            f.write(json.dumps(job, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="生成 FULL 训练任务清单")
    parser.add_argument("--out", default="training_jobs_full.jsonl")
    parser.add_argument("--seed", type=int, default=20260126)
    parser.add_argument("--no-translate", action="store_true")
    args = parser.parse_args()
    build_training_jobs_full(args.out, args.seed, use_translate=not args.no_translate)


if __name__ == "__main__":
    main()
