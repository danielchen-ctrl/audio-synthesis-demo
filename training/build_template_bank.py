# -*- coding: utf-8 -*-
"""
Template Bank构建器 - 从训练输出提取可复用模板
==============================================

功能：
1. 从training_outputs目录读取生成的对话
2. 按阶段分类：opening/info_collect/explain/risk/next_steps
3. 去重（SequenceMatcher>0.85视为重复）
4. 每阶段每类speaker保留topN=200条
5. 输出到template_bank/{profession}/{language}.json

Usage:
    python training/build_template_bank.py
    python training/build_template_bank.py --input output/training/smoke --output template_bank_test
"""

import os
import json
import argparse
from pathlib import Path
from typing import List, Dict, Set, Tuple
from difflib import SequenceMatcher
from collections import defaultdict
import re


def calculate_similarity(text1: str, text2: str) -> float:
    """计算两段文本的相似度"""
    # 去除空格和标点
    clean1 = ''.join(c for c in text1 if c.isalnum())
    clean2 = ''.join(c for c in text2 if c.isalnum())
    
    if not clean1 or not clean2:
        return 0.0
    
    return SequenceMatcher(None, clean1, clean2).ratio()


def classify_stage(text: str, line_index: int, total_lines: int, speaker_id: str) -> str:
    """
    根据内容和位置分类对话阶段
    
    阶段定义：
    - opening: 开场问候（前10%）
    - info_collect: 信息收集（10-40%）
    - explain: 解释说明（40-70%）
    - risk: 风险注意事项（70-90%）
    - next_steps: 下一步行动（最后10%）
    """
    position_ratio = line_index / max(total_lines, 1)
    
    # 关键词判断（优先级最高）
    text_lower = text.lower()
    
    # 风险/注意事项关键词
    risk_keywords = ['风险', '注意', '可能', '需要提醒', '副作用', '禁忌', '不能保证', 
                     '个体差异', '并发症', 'risk', 'caution', 'warning', 'side effect']
    if any(kw in text_lower for kw in risk_keywords):
        return "risk"
    
    # 下一步行动关键词
    next_keywords = ['下一步', '接下来', '回去', '复查', '准备', '联系我', '有问题',
                     '明白了', '好的', '清楚了', 'next step', 'follow up', 'contact me']
    if any(kw in text_lower for kw in next_keywords):
        return "next_steps"
    
    # 解释说明关键词
    explain_keywords = ['因为', '所以', '举个例子', '比如', '根据', '从', '角度',
                       '我给您解释', '打个比方', 'because', 'for example', 'according to']
    if any(kw in text_lower for kw in explain_keywords):
        return "explain"
    
    # 信息收集关键词
    collect_keywords = ['什么时候', '多久', '哪里', '怎么', '能说说', '详细', '具体',
                       '有没有', '是否', 'when', 'where', 'how', 'could you', 'details']
    if any(kw in text_lower for kw in collect_keywords):
        return "info_collect"
    
    # 开场问候关键词
    opening_keywords = ['您好', '你好', '感谢', '我是', '我们', '开始', '今天',
                       'hello', 'thank you', 'let me', 'welcome']
    if any(kw in text_lower for kw in opening_keywords) and position_ratio < 0.2:
        return "opening"
    
    # 位置回退（无明确关键词时使用）
    if position_ratio < 0.1:
        return "opening"
    elif position_ratio < 0.4:
        return "info_collect"
    elif position_ratio < 0.7:
        return "explain"
    elif position_ratio < 0.9:
        return "risk"
    else:
        return "next_steps"


def contains_core_marker(text: str) -> bool:
    """检查是否包含核心内容标记"""
    return '<<核心:' in text or '<<core:' in text.lower()


def extract_speaker_id(line: str) -> Tuple[str, str]:
    """
    提取speaker_id和对话内容
    
    Returns:
        (speaker_id, text) 例如 ("Speaker 1", "您好，我是...")
    """
    # 匹配格式: "Speaker 1: 对话内容" 或 "**Speaker 1: 对话内容**"
    pattern = r'\*?\*?Speaker (\d+):\s*(.*?)(?:\*\*)?$'
    match = re.match(pattern, line.strip())
    
    if match:
        speaker_num = match.group(1)
        text = match.group(2).strip()
        return f"Speaker {speaker_num}", text
    
    return None, line.strip()


def parse_dialogue_file(filepath: Path) -> List[Dict]:
    """
    解析单个对话文件
    
    Returns:
        List[Dict]: [{"speaker": "Speaker 1", "text": "...", "stage": "opening"}, ...]
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"  [警告] 无法读取文件 {filepath}: {e}")
        return []
    
    # 过滤空行和标题行
    dialogue_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('===') or line.startswith('---'):
            continue
        if line.startswith('#'):
            continue
        dialogue_lines.append(line)
    
    # 解析对话
    parsed = []
    total_lines = len(dialogue_lines)
    
    for idx, line in enumerate(dialogue_lines):
        speaker_id, text = extract_speaker_id(line)
        
        if not speaker_id or not text:
            continue
        
        # 跳过包含核心标记的行
        if contains_core_marker(text):
            continue
        
        # 分类阶段
        stage = classify_stage(text, idx, total_lines, speaker_id)
        
        parsed.append({
            "speaker": speaker_id,
            "text": text,
            "stage": stage
        })
    
    return parsed


def deduplicate_templates(templates: List[Dict], threshold: float = 0.85) -> List[Dict]:
    """
    去重模板（相似度>threshold视为重复）
    
    Args:
        templates: 模板列表
        threshold: 相似度阈值（默认0.85）
    
    Returns:
        去重后的模板列表
    """
    if not templates:
        return []
    
    unique = []
    
    for template in templates:
        text = template["text"]
        is_duplicate = False
        
        # 与已有模板比对
        for existing in unique:
            if calculate_similarity(text, existing["text"]) > threshold:
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique.append(template)
    
    return unique


def build_template_bank(input_dir: str, output_dir: str, top_n: int = 200):
    """
    构建template bank
    
    Args:
        input_dir: 训练输出目录（如output/training/mvp）
        output_dir: 输出目录（如template_bank）
        top_n: 每阶段每个speaker保留的最大数量
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    if not input_path.exists():
        print(f"[错误] 输入目录不存在: {input_dir}")
        return
    
    print(f"[Template Bank构建器]")
    print(f"  输入目录: {input_dir}")
    print(f"  输出目录: {output_dir}")
    print(f"  每阶段每speaker保留: {top_n}条")
    print()
    
    # 创建输出目录
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 统计信息
    stats = {
        "total_files": 0,
        "total_lines": 0,
        "skipped_core": 0,
        "before_dedup": 0,
        "after_dedup": 0
    }
    
    # 遍历职业和语言
    professions = [d for d in input_path.iterdir() if d.is_dir() and not d.name.startswith('_')]
    
    for profession_dir in professions:
        profession = profession_dir.name
        print(f"[{profession}]")
        
        languages = [d for d in profession_dir.iterdir() if d.is_dir()]
        
        for language_dir in languages:
            language = language_dir.name
            print(f"  [{language}]")
            
            # 存储模板：{stage: {speaker: [templates]}}
            bank = defaultdict(lambda: defaultdict(list))
            
            # 读取所有txt文件
            txt_files = list(language_dir.glob("*.txt"))
            stats["total_files"] += len(txt_files)
            
            for txt_file in txt_files:
                # 解析对话
                dialogue = parse_dialogue_file(txt_file)
                stats["total_lines"] += len(dialogue)
                
                # 按阶段和speaker分组
                for item in dialogue:
                    stage = item["stage"]
                    speaker = item["speaker"]
                    bank[stage][speaker].append(item)
            
            # 去重和截断
            final_bank = {}
            for stage in ["opening", "info_collect", "explain", "risk", "next_steps"]:
                final_bank[stage] = {}
                
                for speaker in ["Speaker 1", "Speaker 2", "Speaker 3"]:
                    templates = bank[stage][speaker]
                    stats["before_dedup"] += len(templates)
                    
                    # 去重
                    unique = deduplicate_templates(templates, threshold=0.85)
                    stats["after_dedup"] += len(unique)
                    
                    # 截断
                    final_bank[stage][speaker] = [t["text"] for t in unique[:top_n]]
            
            # 输出统计
            total_count = sum(
                len(final_bank[stage][speaker])
                for stage in final_bank
                for speaker in final_bank[stage]
            )
            print(f"    提取模板: {total_count}条")
            
            # 保存到文件
            output_profession_dir = output_path / profession
            output_profession_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = output_profession_dir / f"{language}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(final_bank, f, ensure_ascii=False, indent=2)
            
            print(f"    保存到: {output_file}")
    
    # 总结
    print()
    print(f"[完成]")
    print(f"  处理文件: {stats['total_files']}个")
    print(f"  总行数: {stats['total_lines']}行")
    print(f"  去重前: {stats['before_dedup']}条")
    print(f"  去重后: {stats['after_dedup']}条")
    print(f"  去重率: {(1 - stats['after_dedup'] / max(stats['before_dedup'], 1)) * 100:.1f}%")


def main():
    parser = argparse.ArgumentParser(description="构建Template Bank")
    parser.add_argument(
        '--input',
        default='output/training/mvp',
        help='训练输出目录（默认: output/training/mvp）'
    )
    parser.add_argument(
        '--output',
        default='template_bank',
        help='输出目录（默认: template_bank）'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=200,
        help='每阶段每speaker保留的最大数量（默认: 200）'
    )
    
    args = parser.parse_args()
    
    build_template_bank(
        input_dir=args.input,
        output_dir=args.output,
        top_n=args.top_n
    )


if __name__ == "__main__":
    main()

