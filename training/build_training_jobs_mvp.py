"""
训练任务生成器 - MVP版本

功能：
- 从scenario_bank.py读取场景，生成训练任务清单（JSONL格式）
- MVP范围：每职业前5场景 × 中英2语言 × 3个字数桶 = ~390任务

Usage:
    python -m training.build_training_jobs_mvp --out training_jobs_mvp.jsonl --seed 20260126
"""

import json
import hashlib
import random
import argparse
import sys
import os

# 添加父目录到path以便import server
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training.scenario_bank import JOB_FUNCTIONS, LANGUAGES, SCENARIO_BANK


def translate_scenario_and_core(scenario_cn: str, core_cn: str, target_language: str) -> tuple:
    """
    翻译scenario和core_content（复用server.py的翻译逻辑）
    
    Args:
        scenario_cn: 中文情景设置
        core_cn: 中文核心内容
        target_language: 目标语言（如"英语"、"日语"）
    
    Returns:
        (translated_scenario, translated_core)
    """
    if target_language == "中文":
        return scenario_cn, core_cn
    
    try:
        # 复用server.py的translate_text（但不保护标签，因为这是纯文本）
        from server import translate_text
        
        # 翻译scenario
        translated_scenario, _ = translate_text(scenario_cn, target_language, protect_tags=False)
        
        # 翻译core_content
        translated_core, _ = translate_text(core_cn, target_language, protect_tags=False)
        
        return translated_scenario, translated_core
        
    except Exception as e:
        print(f"[警告] 翻译失败 ({target_language}): {e}，使用中文原文")
        return scenario_cn, core_cn


def generate_seed(profession: str, scene_id: str, language: str, word_count: int, people_count: int) -> int:
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


def build_training_jobs_mvp(output_file: str, base_seed: int = 20260126):
    """
    生成MVP训练任务清单
    
    MVP范围：
    - 每职业前5个场景
    - 语言：中文、英语
    - 字数桶：500, 1500, 3000
    - people_count：按场景约束采样
    """
    random.seed(base_seed)
    
    jobs = []
    stats = {
        "total": 0,
        "by_profession": {},
        "by_language": {"中文": 0, "英语": 0},
        "by_word_count": {}
    }
    
    # MVP配置
    mvp_languages = ["中文", "英语"]
    mvp_word_counts = [500, 1500, 3000]
    max_scenarios_per_profession = 5  # MVP：每职业前5场景
    
    print(f"[MVP任务生成] 开始生成训练任务...")
    print(f"[MVP任务生成] 职业数: {len(JOB_FUNCTIONS)}, 每职业场景数: {max_scenarios_per_profession}")
    print(f"[MVP任务生成] 语言: {mvp_languages}")
    print(f"[MVP任务生成] 字数桶: {mvp_word_counts}")
    print()
    
    for profession in JOB_FUNCTIONS:
        scenarios = SCENARIO_BANK.get(profession, [])
        
        if not scenarios:
            print(f"[警告] 职业 {profession} 无场景，跳过")
            continue
        
        # MVP：只取前5个场景
        scenarios = scenarios[:max_scenarios_per_profession]
        
        stats["by_profession"][profession] = 0
        
        for scenario_idx, scenario_obj in enumerate(scenarios):
            scene_id = f"{profession}-{scenario_idx+1:02d}"
            
            scenario_cn = scenario_obj.scenario_setting_cn
            core_cn = scenario_obj.core_content_cn
            people_range = scenario_obj.people_count_range
            tags = scenario_obj.tags
            
            # 为每种语言生成任务
            for language in mvp_languages:
                # 翻译scenario和core（中文直接用原文）
                scenario_text, core_text = translate_scenario_and_core(
                    scenario_cn, core_cn, language
                )
                
                # 为每个字数桶生成任务
                for word_count in mvp_word_counts:
                    # 采样people_count（优先2-4人）
                    min_people, max_people = people_range
                    people_count = random.choice([
                        p for p in range(min_people, min(max_people, 5) + 1)
                        if p >= 2
                    ])
                    
                    # 选择资历
                    seniority = select_seniority(profession, people_count)
                    
                    # 生成seed
                    seed = generate_seed(profession, scene_id, language, word_count, people_count)
                    
                    # 构建任务
                    job = {
                        "job_function": profession,
                        "work_content": select_work_content(profession),
                        "seniority": seniority,
                        "scenario": scenario_text,
                        "core_content": core_text,
                        "language": language,
                        "people_count": people_count,
                        "word_count": word_count,
                        "seed": seed,
                        "meta": {
                            "tags": tags,
                            "scenario_id": scene_id,
                            "bucket": word_count
                        }
                    }
                    
                    jobs.append(job)
                    
                    # 更新统计
                    stats["total"] += 1
                    stats["by_profession"][profession] += 1
                    stats["by_language"][language] += 1
                    stats["by_word_count"][word_count] = stats["by_word_count"].get(word_count, 0) + 1
        
        print(f"[MVP任务生成] {profession}: {stats['by_profession'][profession]} 个任务")
    
    # 保存JSONL
    with open(output_file, 'w', encoding='utf-8') as f:
        for job in jobs:
            f.write(json.dumps(job, ensure_ascii=False) + '\n')
    
    print()
    print(f"[MVP任务生成] ✅ 完成！")
    print(f"[MVP任务生成] 总任务数: {stats['total']}")
    print(f"[MVP任务生成] 按语言: {stats['by_language']}")
    print(f"[MVP任务生成] 按字数: {stats['by_word_count']}")
    print(f"[MVP任务生成] 输出文件: {output_file}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="生成训练任务清单（MVP版本）")
    parser.add_argument("--out", type=str, required=True, help="输出JSONL文件路径")
    parser.add_argument("--seed", type=int, default=20260126, help="随机种子")
    
    args = parser.parse_args()
    
    # 生成任务
    stats = build_training_jobs_mvp(args.out, args.seed)
    
    # 打印预览（前3个任务）
    print()
    print("[预览] 前3个任务示例：")
    with open(args.out, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 3:
                break
            job = json.loads(line)
            print(f"\n任务 {i+1}:")
            print(f"  职业: {job['job_function']}")
            print(f"  语言: {job['language']}")
            print(f"  字数: {job['word_count']}")
            print(f"  人数: {job['people_count']}")
            print(f"  场景: {job['scenario'][:50]}...")


if __name__ == "__main__":
    main()
