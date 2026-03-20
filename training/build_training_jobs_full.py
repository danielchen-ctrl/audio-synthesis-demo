# -*- coding: utf-8 -*-
"""
训练任务生成器 - 完整版
=======================

功能：
- 从scenario_bank.py读取场景，生成训练任务清单（JSONL格式）
- FULL范围：
  - 中英日：全30场景 × 3语言 × 3字数桶 × 2人数 = ~5400任务
  - 其他语言（韩、法、德、西、葡、粤）：每职业前10场景 × 6语言 × 3字数桶 × 2人数 = ~2340任务
  - 总计：~7800任务

Usage:
    python -m training.build_training_jobs_full --out training_jobs_full.jsonl --seed 20260126
"""

import json
import hashlib
import random
import argparse
import sys
import os
import time

# 添加父目录到path以便import server
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training.scenario_bank import JOB_FUNCTIONS, LANGUAGES, SCENARIO_BANK


def translate_scenario_and_core_with_fallback(
    scenario_cn: str, 
    core_cn: str, 
    target_language: str
) -> tuple:
    """
    翻译scenario和core_content（带fallback机制）
    
    策略：
    1. 尝试Google翻译
    2. 失败则使用内置短语表+保留中文兜底
    3. 标记translate_fallback=true（记录到meta）
    
    Args:
        scenario_cn: 中文情景设置
        core_cn: 中文核心内容
        target_language: 目标语言（如"英语"、"日语"）
    
    Returns:
        (translated_scenario, translated_core, fallback_used)
    """
    if target_language == "中文":
        return scenario_cn, core_cn, False
    
    try:
        # 尝试使用server.py的translate_text（增加超时和重试）
        from server import translate_text
        
        max_retries = 2
        for retry in range(max_retries):
            try:
                # 翻译scenario
                translated_scenario, _ = translate_text(
                    scenario_cn, target_language, protect_tags=False
                )
                
                # 短暂延迟，避免被限流
                time.sleep(0.1)
                
                # 翻译core_content
                translated_core, _ = translate_text(
                    core_cn, target_language, protect_tags=False
                )
                
                # 验证翻译是否成功（不应该全是中文）
                if (translated_scenario == scenario_cn and 
                    translated_core == core_cn and 
                    target_language != "中文"):
                    raise ValueError("翻译未生效，返回原文")
                
                return translated_scenario, translated_core, False
                
            except Exception as e:
                if retry < max_retries - 1:
                    print(f"[翻译失败] {target_language}: {e}，重试{retry+1}/{max_retries}")
                    time.sleep(1)  # 重试前等待1秒
                    continue
                else:
                    raise e
        
    except Exception as e:
        print(f"[翻译失败] {target_language}: {e}，使用fallback")
        
        # Fallback策略：保留中文+添加语言标记
        lang_prefixes = {
            "英语": "[EN]",
            "日语": "[JA]",
            "韩语": "[KO]",
            "法语": "[FR]",
            "德语": "[DE]",
            "西班牙语": "[ES]",
            "葡萄牙语": "[PT]",
            "粤语": "[YUE]"
        }
        
        prefix = lang_prefixes.get(target_language, f"[{target_language}]")
        
        # 简单策略：添加语言标记，保留中文内容
        fallback_scenario = f"{prefix} {scenario_cn}"
        fallback_core = f"{prefix} {core_cn}"
        
        return fallback_scenario, fallback_core, True


def generate_seed(
    profession: str, 
    scene_id: str, 
    language: str, 
    word_count: int, 
    people_count: int
) -> int:
    """生成可复现的seed（基于任务参数hash）"""
    key = f"{profession}_{scene_id}_{language}_{word_count}_{people_count}"
    hash_val = hashlib.md5(key.encode('utf-8')).hexdigest()
    return int(hash_val[:8], 16)  # 取前8位hex转int


def select_work_content(profession: str) -> str:
    """根据职业选择合适的工作内容"""
    work_content_map = {
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
        "制造业": "生产运营"
    }
    return work_content_map.get(profession, "综合管理")


def select_seniority(profession: str, people_count: int) -> str:
    """根据职业和人数选择资历"""
    if people_count >= 5:
        return random.choice(["C层/创始人", "总监"])
    elif people_count >= 3:
        return random.choice(["经理", "主管"])
    else:
        return random.choice(["高级职员", "经理"])


def build_training_jobs_full(output_file: str, base_seed: int = 20260126, use_translate: bool = True):
    """
    生成FULL训练任务清单
    
    范围：
    - 中英日：全30场景 × 3语言 × 3字数桶 × 2人数 = ~5400任务
    - 其他语言：前10场景 × 6语言 × 3字数桶 × 2人数 = ~2340任务
    - 总计：~7800任务
    
    Args:
        output_file: 输出文件路径（JSONL格式）
        base_seed: 基础随机种子
        use_translate: 是否使用在线翻译（False则全部使用fallback）
    """
    random.seed(base_seed)
    
    # 定义字数桶和人数
    word_counts = [500, 1500, 3000]
    people_counts = [2, 3]
    
    # 定义语言优先级
    primary_languages = ["中文", "英语", "日语"]  # 全场景覆盖
    secondary_languages = ["韩语", "法语", "德语", "西班牙语", "葡萄牙语", "粤语"]  # 前10场景
    
    jobs = []
    job_id = 1
    
    print(f"[训练任务生成器 - FULL版]")
    print(f"  基础种子: {base_seed}")
    print(f"  输出文件: {output_file}")
    print()
    
    for profession in JOB_FUNCTIONS:
        scenarios = SCENARIO_BANK.get(profession, [])
        
        if not scenarios:
            print(f"[跳过] {profession}: 无场景")
            continue
        
        print(f"[{profession}] 共{len(scenarios)}个场景")
        
        for scene_idx, scene in enumerate(scenarios, 1):
            # 适配ScenarioTemplate对象
            scene_id = f"{profession}-{scene_idx:02d}"
            scenario_cn = getattr(scene, 'scenario_setting_cn', '')
            core_cn = getattr(scene, 'core_content_cn', '')
            
            if not scenario_cn or not core_cn:
                print(f"  [跳过] {scene_id}: 缺少scenario或core_content")
                continue
            
            # 决定该场景使用哪些语言
            if scene_idx <= 30:
                # 前30场景：中英日全覆盖
                languages_for_this_scene = primary_languages.copy()  # 必须copy！
            else:
                # 30场景后：只有中文（如果有的话）
                languages_for_this_scene = ["中文"]
            
            # 前10场景：额外增加其他语言
            if scene_idx <= 10:
                languages_for_this_scene += secondary_languages
            
            for language in languages_for_this_scene:
                # 翻译场景和核心内容（带fallback）
                if use_translate:
                    translated_scenario, translated_core, fallback_used = \
                        translate_scenario_and_core_with_fallback(
                            scenario_cn, core_cn, language
                        )
                else:
                    # 不使用翻译，直接fallback
                    if language == "中文":
                        translated_scenario, translated_core, fallback_used = scenario_cn, core_cn, False
                    else:
                        lang_prefixes = {
                            "英语": "[EN]", "日语": "[JA]", "韩语": "[KO]",
                            "法语": "[FR]", "德语": "[DE]", "西班牙语": "[ES]",
                            "葡萄牙语": "[PT]", "粤语": "[YUE]"
                        }
                        prefix = lang_prefixes.get(language, f"[{language}]")
                        translated_scenario = f"{prefix} {scenario_cn}"
                        translated_core = f"{prefix} {core_cn}"
                        fallback_used = True
                
                for word_count in word_counts:
                    for people_count in people_counts:
                        # 生成任务seed
                        task_seed = generate_seed(
                            profession, scene_id, language, 
                            word_count, people_count
                        )
                        
                        # 构建任务参数
                        job_params = {
                            "job_id": job_id,
                            "profession": profession,
                            "scenario_id": scene_id,
                            "language": language,
                            "word_count": word_count,
                            "people_count": people_count,
                            "seed": task_seed,
                            "profile": {
                                "job_function": profession,
                                "work_content": select_work_content(profession),
                                "seniority": select_seniority(profession, people_count),
                                "use_case": "客户洽谈"
                            },
                            "scenario": translated_scenario,
                            "core_content": translated_core,
                            "translate_fallback": fallback_used
                        }
                        
                        jobs.append(job_params)
                        job_id += 1
    
    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        for job in jobs:
            f.write(json.dumps(job, ensure_ascii=False) + '\n')
    
    # 统计
    print()
    print(f"[完成]")
    print(f"  总任务数: {len(jobs)}")
    print(f"  输出文件: {output_file}")
    
    # 分语言统计
    lang_stats = {}
    fallback_stats = {}
    for job in jobs:
        lang = job["language"]
        lang_stats[lang] = lang_stats.get(lang, 0) + 1
        if job.get("translate_fallback"):
            fallback_stats[lang] = fallback_stats.get(lang, 0) + 1
    
    print()
    print("[语言分布]")
    for lang in sorted(lang_stats.keys()):
        count = lang_stats[lang]
        fallback_count = fallback_stats.get(lang, 0)
        fallback_pct = fallback_count / count * 100 if count > 0 else 0
        print(f"  {lang}: {count}任务 (fallback: {fallback_count}, {fallback_pct:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="生成FULL训练任务清单")
    parser.add_argument(
        '--out',
        default='training_jobs_full.jsonl',
        help='输出文件路径（默认: training_jobs_full.jsonl）'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=20260126,
        help='基础随机种子（默认: 20260126）'
    )
    parser.add_argument(
        '--no-translate',
        action='store_true',
        help='不使用在线翻译，直接使用fallback（避免网络问题）'
    )
    
    args = parser.parse_args()
    
    build_training_jobs_full(
        output_file=args.out,
        base_seed=args.seed,
        use_translate=not args.no_translate
    )


if __name__ == "__main__":
    main()
