"""
训练语料批量生成器 - MVP版本

功能：
- 读取training_jobs_mvp.jsonl，调用server.py生成对话
- 保存txt + meta.json
- 硬校验：核心标记唯一、无占位符、中文占比、空话过滤

Usage:
    python -m training.run_training_generation_mvp --jobs training_jobs_mvp.jsonl --out_dir output/training/mvp --max_jobs 999999
"""

import json
import os
import re
import argparse
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any

# 添加父目录到path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 直接import server.py的生成函数
from server import (
    _generate_dialogue_lines,
    _generate_cast,
    _generate_structured_dialogue,
    classify_scene_type,
    validate_and_normalize_payload
)


def generate_for_training(
    job_function: str,
    work_content: str,
    seniority: str,
    scenario: str,
    core_content: str,
    language: str,
    people_count: int,
    word_count: int,
    seed: int
) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
    """
    为训练数据生成对话（直接调用server内部函数）
    
    Returns:
        (lines, debug_info)
        lines: [(speaker_id, text), ...]
        debug_info: {input_hash, from_v2, ...}
    """
    # 构建profile（字符串和dict两种形式）
    profile_str = f"{job_function}|{work_content}|{seniority}"
    profile_dict = {
        "job_function": job_function,
        "work_content": work_content,
        "seniority": seniority
    }
    
    # 场景分类
    scene_type = classify_scene_type(scenario, profile_dict)
    
    # 生成cast（需要dict）
    cast_info = _generate_cast(profile_dict, scenario, people_count, language)
    
    # 生成对话（profile需要dict，people参数名为total_people）
    lines = _generate_structured_dialogue(
        cast_info=cast_info,
        profile=profile_dict,
        scenario=scenario,
        core=core_content,
        target_len=word_count,
        language=language,
        total_people=people_count
    )
    
    # 构建debug_info（模拟server返回的debug）
    debug_info = {
        "scene_type": scene_type,
        "cast_count": len(cast_info),
        "line_count": len(lines),
        "total_chars": sum(len(text) for _, text in lines),
        "from_v2": False,  # 当前V2禁用，都是fallback
        "seed": seed
    }
    
    return lines, debug_info


def validate_dialogue_output(
    lines: List[Tuple[str, str]],
    language: str,
    people_count: int,
    is_fallback: bool = False
) -> Tuple[bool, str]:
    """
    硬校验对话输出
    
    Args:
        is_fallback: 是否为fallback任务（使用更宽松的校验）
    
    Returns:
        (is_valid, error_message)
    """
    full_text = "\n".join([f"{speaker}: {text}" for speaker, text in lines])
    
    # 1. 核心标记检查
    core_markers_cn = re.findall(r'<<核心:.*?>>', full_text)
    core_markers_en = re.findall(r'<<Core:.*?>>', full_text)
    core_markers_ja = re.findall(r'<<コア:.*?>>', full_text)
    core_markers_fr = re.findall(r'<<Noyau:.*?>>', full_text)
    core_markers_ko = re.findall(r'<<핵심:.*?>>', full_text)
    
    all_markers = core_markers_cn + core_markers_en + core_markers_ja + core_markers_fr + core_markers_ko
    
    # fallback任务允许缺少核心标记（因为翻译可能有问题）
    if len(all_markers) == 0 and not is_fallback:
        return False, "缺少核心标记"
    
    if len(all_markers) > 2:  # 放宽到2个（fallback可能重复）
        return False, f"核心标记过多({len(all_markers)}次)"
    
    # 2. 占位符残留检查
    if "[[[CORE" in full_text:
        return False, "存在占位符残留 [[[CORE"
    
    # 3. 非中文：中文占比检查（fallback任务使用更宽松阈值）
    if language != "中文":
        chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', full_text))
        total_chars = len(full_text)
        chinese_ratio = chinese_chars / total_chars if total_chars > 0 else 0
        
        # fallback任务使用70%阈值，正常任务使用10%阈值
        threshold = 0.70 if is_fallback else 0.10
        
        if chinese_ratio > threshold:
            return False, f"中文占比过高({chinese_ratio:.1%})"
    
    # 4. people_count>=3时，Speaker3空话检查
    if people_count >= 3:
        speaker3_lines = [text for speaker, text in lines if speaker == "Speaker 3"]
        
        if len(speaker3_lines) > 0:
            # 空话模式：好的/明白了/收到/确认/了解 等
            filler_patterns = [
                r'^好的[。！，、]*$',
                r'^明白了[。！，、]*$',
                r'^收到[。！，、]*$',
                r'^确认[。！，、]*$',
                r'^了解[。！，、]*$',
                r'^知道了[。！，、]*$',
                r'^好[。！，、]*$',
                r'^嗯[。！，、]*$',
                r'^Okay[\.!\,]*$',
                r'^Got it[\.!\,]*$',
                r'^Understood[\.!\,]*$',
                r'^I see[\.!\,]*$'
            ]
            
            filler_count = 0
            for line in speaker3_lines:
                line_stripped = line.strip()
                if any(re.match(pattern, line_stripped, re.IGNORECASE) for pattern in filler_patterns):
                    filler_count += 1
            
            filler_ratio = filler_count / len(speaker3_lines)
            if filler_ratio > 0.5:
                return False, f"Speaker3空话过多({filler_ratio:.1%})"
    
    return True, ""


def save_dialogue_output(
    lines: List[Tuple[str, str]],
    debug_info: Dict[str, Any],
    job: Dict[str, Any],
    output_dir: Path
) -> Tuple[str, str]:
    """
    保存对话txt和meta.json
    
    Returns:
        (txt_path, meta_path)
    """
    # 兼容两种格式
    if "job_function" in job:
        # MVP版格式
        profession = job["job_function"]
        scene_id = job["meta"]["scenario_id"]
        bucket = job["meta"]["bucket"]
    else:
        # FULL版格式
        profession = job.get("profession", job.get("profile", {}).get("job_function", "未知职业"))
        scene_id = job.get("scenario_id", "未知场景")
        bucket = job["word_count"]  # FULL版没有meta.bucket，直接用word_count
    
    language = job["language"]
    people = job["people_count"]
    seed = job["seed"]
    
    # 清理职业名称中的非法路径字符（如"娱乐/媒体" → "娱乐_媒体"）
    profession_safe = profession.replace("/", "_").replace("\\", "_")
    
    # 清理scene_id中的非法路径字符（如"金融/投资-03" → "金融_投资-03"）
    scene_id_safe = scene_id.replace("/", "_").replace("\\", "_")
    
    # 创建子目录
    sub_dir = output_dir / profession_safe / language
    sub_dir.mkdir(parents=True, exist_ok=True)
    
    # 文件名
    filename_base = f"{scene_id_safe}_{bucket}_{people}_{seed}"
    txt_path = sub_dir / f"{filename_base}.txt"
    meta_path = sub_dir / f"{filename_base}.meta.json"
    
    # 保存txt
    with open(txt_path, 'w', encoding='utf-8') as f:
        for speaker, text in lines:
            f.write(f"{speaker}: {text}\n")
    
    # 保存meta.json
    meta = {
        "job_function": profession,
        "language": language,
        "scenario": job["scenario"],
        "core_content": job["core_content"],
        "people_count": people,
        "word_count": bucket,
        "seed": seed,
        "effective_params": {
            "scenario_head": job["scenario"][:60],
            "core_head": job["core_content"][:60],
            "people_count": people,
            "word_count": bucket,
            "language": language
        },
        "debug_info": debug_info,
        "stats": {
            "line_count": len(lines),
            "total_chars": sum(len(text) for _, text in lines),
            "speaker_distribution": {}
        }
    }
    
    # 统计speaker分布
    for speaker, text in lines:
        meta["stats"]["speaker_distribution"][speaker] = \
            meta["stats"]["speaker_distribution"].get(speaker, 0) + 1
    
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    
    return str(txt_path), str(meta_path)


def run_training_generation_mvp(
    jobs_file: str,
    output_dir: str,
    max_jobs: int = 999999
):
    """
    批量生成训练语料（MVP版本）
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    failed_jobs_path = output_path / "_failed.jsonl"
    
    stats = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "by_profession": {},
        "by_language": {},
        "failure_reasons": {}
    }
    
    print(f"[MVP批量生成] 开始生成训练语料...")
    print(f"[MVP批量生成] 任务文件: {jobs_file}")
    print(f"[MVP批量生成] 输出目录: {output_dir}")
    print()
    
    # 读取任务
    jobs = []
    with open(jobs_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                jobs.append(json.loads(line))
    
    jobs = jobs[:max_jobs]
    print(f"[MVP批量生成] 任务总数: {len(jobs)}")
    print()
    
    # 逐个生成
    for idx, job in enumerate(jobs):
        stats["total"] += 1
        
        # 兼容两种格式：MVP版（job_function顶层）和FULL版（在profile中）
        if "job_function" in job:
            # MVP版格式
            profession = job["job_function"]
            scene_id = job["meta"]["scenario_id"]
        else:
            # FULL版格式
            profession = job.get("profession", job.get("profile", {}).get("job_function", "未知职业"))
            scene_id = job.get("scenario_id", "未知场景")
        
        language = job["language"]
        
        # 初始化统计
        if profession not in stats["by_profession"]:
            stats["by_profession"][profession] = {"success": 0, "failed": 0}
        if language not in stats["by_language"]:
            stats["by_language"][language] = {"success": 0, "failed": 0}
        
        # 尝试生成（最多重试2次）
        max_retries = 2
        success = False
        last_error = ""
        
        for retry in range(max_retries + 1):
            try:
                # 兼容两种格式获取参数
                if "job_function" in job:
                    # MVP版格式
                    job_function = job["job_function"]
                    work_content = job["work_content"]
                    seniority = job["seniority"]
                else:
                    # FULL版格式
                    profile = job.get("profile", {})
                    job_function = profile.get("job_function", profession)
                    work_content = profile.get("work_content", "综合管理")
                    seniority = profile.get("seniority", "经理")
                
                # 生成对话
                lines, debug_info = generate_for_training(
                    job_function=job_function,
                    work_content=work_content,
                    seniority=seniority,
                    scenario=job["scenario"],
                    core_content=job["core_content"],
                    language=job["language"],
                    people_count=job["people_count"],
                    word_count=job["word_count"],
                    seed=job["seed"] + retry  # 重试时seed+1
                )
                
                # 获取fallback标记（FULL版格式）
                is_fallback = job.get("translate_fallback", False)
                
                # 硬校验
                is_valid, error_msg = validate_dialogue_output(
                    lines, job["language"], job["people_count"], is_fallback
                )
                
                if not is_valid:
                    last_error = error_msg
                    if retry < max_retries:
                        print(f"  [{idx+1}/{len(jobs)}] {profession}/{scene_id} - 校验失败({error_msg})，重试{retry+1}/{max_retries}")
                        continue
                    else:
                        raise ValueError(f"校验失败: {error_msg}")
                
                # 保存
                txt_path, meta_path = save_dialogue_output(
                    lines, debug_info, job, output_path
                )
                
                success = True
                stats["success"] += 1
                stats["by_profession"][profession]["success"] += 1
                stats["by_language"][language]["success"] += 1
                
                if (idx + 1) % 10 == 0 or idx == 0:
                    print(f"  [{idx+1}/{len(jobs)}] ✅ {profession}/{scene_id} ({language}, {job['word_count']}字) → {txt_path}")
                
                break  # 成功，跳出重试循环
                
            except Exception as e:
                last_error = str(e)
                if retry < max_retries:
                    print(f"  [{idx+1}/{len(jobs)}] {profession}/{scene_id} - 生成失败({last_error})，重试{retry+1}/{max_retries}")
                    continue
                else:
                    # 所有重试都失败
                    stats["failed"] += 1
                    stats["by_profession"][profession]["failed"] += 1
                    stats["by_language"][language]["failed"] += 1
                    
                    # 记录失败原因
                    reason_key = last_error[:50]  # 取前50字符作为key
                    stats["failure_reasons"][reason_key] = stats["failure_reasons"].get(reason_key, 0) + 1
                    
                    # 写入failed.jsonl
                    with open(failed_jobs_path, 'a', encoding='utf-8') as f:
                        failed_record = job.copy()
                        failed_record["error"] = last_error
                        f.write(json.dumps(failed_record, ensure_ascii=False) + '\n')
                    
                    print(f"  [{idx+1}/{len(jobs)}] ❌ {profession}/{scene_id} - 失败: {last_error}")
    
    # 打印统计
    print()
    print("=" * 60)
    print(f"[MVP批量生成] ✅ 完成！")
    print(f"[MVP批量生成] 总任务数: {stats['total']}")
    print(f"[MVP批量生成] 成功: {stats['success']} ({stats['success']/stats['total']*100:.1f}%)")
    print(f"[MVP批量生成] 失败: {stats['failed']}")
    print()
    
    print("[按职业统计]")
    for profession, counts in sorted(stats["by_profession"].items()):
        print(f"  {profession}: 成功{counts['success']}, 失败{counts['failed']}")
    print()
    
    print("[按语言统计]")
    for language, counts in sorted(stats["by_language"].items()):
        print(f"  {language}: 成功{counts['success']}, 失败{counts['failed']}")
    print()
    
    if stats["failure_reasons"]:
        print("[失败原因 Top5]")
        top_reasons = sorted(stats["failure_reasons"].items(), key=lambda x: x[1], reverse=True)[:5]
        for reason, count in top_reasons:
            print(f"  {count}次: {reason}")
        print()
    
    print(f"[MVP批量生成] 输出目录: {output_dir}")
    print(f"[MVP批量生成] 失败记录: {failed_jobs_path}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="批量生成训练语料（MVP版本）")
    parser.add_argument("--jobs", type=str, required=True, help="任务JSONL文件路径")
    parser.add_argument("--out_dir", type=str, required=True, help="输出目录")
    parser.add_argument("--max_jobs", type=int, default=999999, help="最大任务数")
    
    args = parser.parse_args()
    
    # 批量生成
    stats = run_training_generation_mvp(args.jobs, args.out_dir, args.max_jobs)
    
    # 退出码：有失败则返回1
    if stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

