#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量生成13个职业场景的日语对话文本和音频
- 方法：先生成英语对话，然后翻译成日语
- 人物数量：4-5人（根据参数文件）
- 字数：1400-1700（根据参数文件）
- 输出目录：output_ja/ 和 audio_ja/
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any

# 添加项目根目录到 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# 导入 server.py 核心函数
from server import _generate_dialogue_lines, _render_dialogue_text

# 导入行业模板验证器
from industry_template_loader import (
    detect_industry_slug,
    load_industry_skeleton,
)

# 导入翻译器
try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False
    print("警告: deep_translator 未安装，无法翻译成日语")
    sys.exit(1)

# 全局配置
INPUT_FILE = PROJECT_ROOT / "demo" / "13个职业最新情景设置参数.txt"
OUTPUT_DIR = PROJECT_ROOT / "output_ja"  # 日语输出目录
AUDIO_DIR = PROJECT_ROOT / "audio_ja"     # 日语音频目录

# 默认参数
DEFAULT_PEOPLE_COUNT = 4
DEFAULT_WORD_COUNT = 1500
DEFAULT_LANGUAGE = "日语"  # 最终输出语言（通过英语翻译获得）

# 行业角色映射（日语名字）
INDUSTRY_ROLES_JA = {
    "医疗健康": ["田中 博士（部門長）", "佐藤 部長（病院リーダーシップ）", "鈴木 マネージャー（ITセンター）", "高橋 看護師（看護運営）", "渡辺 コーディネーター（プロジェクト）"],
    "人力资源与招聘": ["陳 サラ（HRBPリード）", "張 マイケル（ビジネスVP）", "王 リサ（財務BP）", "劉 デビッド（コンプライアンス法務）"],
    "娱乐/媒体": ["李 デビッド（総支配人）", "張 エマ（ブランド商業化）", "王 トム（コンテンツディレクター）", "陳 リンダ（チャネル配信）"],
    "建筑与工程行业": ["山田 ジョン（総支配人）", "劉 ケビン（コストマネージャー）", "陳 エイミー（サプライチェーン）", "王 スティーブン（安全責任者）", "趙 ピーター（プロジェクトリード）"],
    "汽车行业": ["張 ロバート（マーケティングディレクター）", "王 リンダ（地域チャネル）", "陳 スティーブ（店舗運営）", "劉 フランク（財務政策）", "周 メアリー（プロダクトマネージャー）"],
    "咨询/专业服务": ["李 ジェニファー（パートナー）", "呉 ダニエル（デリバリーリード）", "張 ミシェル（マーケットリード）", "陳 トニー（クライアントマネージャー）"],
    "法律服务": ["ジョンソン 弁護士（マネージングパートナー）", "陳 パートナー（デリバリーパートナー）", "劉 マネージャー（マーケットBD）", "王 スーザン（運営）"],
    "金融/投资": ["張 フランク（投資ディレクター）", "劉 ヘレン（リスクオフィサー）", "王 マーク（プロダクトマネージャー）", "陳 エマ（ウェルスマネージャー）"],
    "零售行业": ["陳 アンドリュー（総支配人）", "王 ナンシー（商品化）", "劉 ピーター（店舗運営）", "周 ルーシー（会員マネージャー）"],
    "保险行业": ["張 リチャード（チャネルディレクター）", "劉 スーザン（コンプライアンスオフィサー）", "王 トニー（トレーニングリード）", "陳 デビッド（プロダクトマネージャー）"],
    "房地产": ["陳 ウィリアム（地域ディレクター）", "王 ジェシカ（チャネルマネージャー）", "劉 クリス（販売サイト）", "周 エイミー（マーケティング）"],
    "人工智能/科技": ["張 アレックス（CTO）", "陳 エミリー（商業化）", "王 ケビン（SREコスト）", "劉 リサ（プロダクトマネージャー）"],
    "制造业": ["劉 ジェームズ（総支配人）", "陳 メアリー（品質責任者）", "王 ポール（設備マネージャー）", "張 スティーブン（サプライチェーン）", "趙 エイミー（生産）"],
}


def parse_input_file(file_path: Path) -> List[Dict[str, Any]]:
    """解析输入文件，提取13个职业场景（新格式）"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 按场景分割
    blocks = re.split(r'\n\d+\）', content)
    blocks = [b.strip() for b in blocks if b.strip()]
    
    jobs = []
    for idx, block in enumerate(blocks, 1):
        lines = block.split('\n')
        
        # 提取职业名称
        profession_line = lines[0].strip() if lines else ""
        profession_line = re.sub(r'^\d+[）)]\s*', '', profession_line)
        profession_match = re.match(r'([^｜]+)｜', profession_line)
        profession = profession_match.group(1).strip() if profession_match else profession_line.split('｜')[0].strip()
        
        # 提取场景对话设置
        scenario_match = re.search(
            r'场景对话设置[（(]升级版[)）]：\s*\n?(.*?)(?=\n\n|\*\*(?:对话生成)?参数|$)',
            block, re.DOTALL
        )
        scenario_setting = scenario_match.group(1).strip() if scenario_match else ""
        
        # 提取对话生成参数
        params_match = re.search(
            r'\*\*(?:对话生成)?参数：?\*\*([^\n]+)',
            block
        )
        params_str = params_match.group(1).strip() if params_match else ""
        
        # 解析参数
        people_count = DEFAULT_PEOPLE_COUNT
        target_words = DEFAULT_WORD_COUNT
        
        if params_str:
            pc_match = re.search(r'people_count[=＝](\d+)', params_str)
            if pc_match:
                people_count = int(pc_match.group(1))
            
            words_match = re.search(r'target_words[=＝](\d+)~?(\d+)?', params_str)
            if words_match:
                min_words = int(words_match.group(1))
                max_words = int(words_match.group(2)) if words_match.group(2) else min_words + 200
                target_words = (min_words + max_words) // 2
        
        # 提取核心内容
        core_match = re.search(r'<Core:([^>]+)>', block, re.DOTALL)
        core_content = core_match.group(1).strip() if core_match else ""
        
        if not core_content:
            core_match = re.search(r'核心内容[：:]\s*\n(.*?)(?=\n\n|---|\Z)', block, re.DOTALL)
            core_content = core_match.group(1).strip() if core_match else ""
        
        if not profession or not scenario_setting or not core_content:
            print(f"[警告] 不完全なシーンをスキップ #{idx}")
            continue
        
        jobs.append({
            "index": idx,
            "profession": profession,
            "scenario_setting": scenario_setting,
            "core_content": core_content,
            "people_count": people_count,
            "target_words": target_words,
            "language": "日语",
        })
    
    print(f"[解析完了] {len(jobs)} 個のシーンを解析しました")
    return jobs


def has_chinese_chars(text: str) -> bool:
    """检查文本是否包含中文字符"""
    import re
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def translate_line_to_japanese(line: str, translator) -> str:
    """
    翻译单行对话到日语
    保持格式：Speaker: Content
    """
    # 匹配 "Speaker: Content" 格式
    match = re.match(r'^([^:：]+)[：:](.+)$', line.strip())
    
    if not match:
        # 非对话行，直接翻译
        try:
            if has_chinese_chars(line):
                return translator.translate(line.strip())
            return line.strip()
        except:
            return line.strip()
    
    speaker = match.group(1).strip()
    content = match.group(2).strip()
    
    # 跳过空内容
    if not content:
        return line
    
    # 翻译内容部分（多次尝试，确保完全翻译）
    try:
        translated_content = translator.translate(content)
        
        # 如果翻译后仍包含中文，再翻译一次
        retry_count = 0
        while has_chinese_chars(translated_content) and retry_count < 2:
            time.sleep(0.5)  # 避免API限流
            translated_content = translator.translate(translated_content)
            retry_count += 1
        
        # 如果还有中文，分段翻译
        if has_chinese_chars(translated_content):
            parts = translated_content.split('、')
            translated_parts = []
            for part in parts:
                if has_chinese_chars(part):
                    part = translator.translate(part)
                translated_parts.append(part)
            translated_content = '、'.join(translated_parts)
        
        return f"{speaker}: {translated_content}"
    except Exception as e:
        print(f"    ⚠️ 翻訳失敗: {str(e)[:50]}")
        return line


def generate_dialogue_text_ja(job: Dict[str, Any], max_retries: int = 3) -> Tuple[str, Dict[str, Any]]:
    """生成日语对话文本（先生成英语，再翻译成日语）"""
    profile = {
        "job_function": job["profession"],
        "work_content": job["scenario_setting"],
        "seniority": "Senior",
        "use_case": "Internal Meeting"
    }
    
    people_count = job.get("people_count", DEFAULT_PEOPLE_COUNT)
    target_words = job.get("target_words", DEFAULT_WORD_COUNT)
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"  [重試 {attempt}/{max_retries-1}]")
            
            # 步骤1: 生成英语对话
            print(f"  [ステップ1] 英語対話を生成中...")
            lines, rewrite_info = _generate_dialogue_lines(
                profile=profile,
                scenario=job["scenario_setting"],
                core=job["core_content"],
                people=people_count,
                target_len=target_words,
                language="英语"  # 先生成英语
            )
            
            # 渲染对话文本
            dialogue_text_en = _render_dialogue_text(lines)
            
            # 步骤2: 翻译成日语
            print(f"  [ステップ2] 日本語に翻訳中...")
            if not TRANSLATOR_AVAILABLE:
                raise RuntimeError("翻译器不可用")
            
            translator = GoogleTranslator(source='en', target='ja')
            
            # 逐行翻译
            english_lines = dialogue_text_en.split('\n')
            japanese_lines = []
            
            for idx, en_line in enumerate(english_lines, 1):
                if not en_line.strip():
                    japanese_lines.append("")
                    continue
                
                # 跳过分隔线和标题
                if en_line.strip().startswith('---') or en_line.strip().startswith('==='):
                    japanese_lines.append(en_line)
                    continue
                
                ja_line = translate_line_to_japanese(en_line, translator)
                japanese_lines.append(ja_line)
                
                # 每10行显示进度
                if idx % 10 == 0:
                    print(f"    翻訳進捗: {idx}/{len(english_lines)} 行")
            
            dialogue_text_ja = '\n'.join(japanese_lines)
            
            stats = {
                "text_length": len(dialogue_text_ja),
                "line_count": len([l for l in japanese_lines if l.strip()]),
                "speaker_count": people_count,
                "is_valid": True,
            }
            
            print(f"  ✅ 翻訳完了: {stats['line_count']} 行")
            
            return dialogue_text_ja, stats
        
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)  # 等待2秒后重试
                continue
            else:
                raise
    
    raise RuntimeError("対話生成失敗")


def process_one_job_ja(job: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
    """处理单个任务（日语版本）"""
    profession = job["profession"]
    index = job["index"]
    
    print(f"\n{'='*80}")
    print(f"[開始] 場面{index}: {profession}")
    print(f"{'='*80}")
    
    try:
        # 生成对话文本
        print(f"[場面{index}] 日本語対話を生成中...")
        dialogue_text, stats = generate_dialogue_text_ja(job, max_retries=3)
        
        # 生成文件名
        profession_cleaned = profession.replace('/', '_').replace('\\', '_').replace(':', '_').replace('｜', '_')
        people_count = job.get("people_count", DEFAULT_PEOPLE_COUNT)
        target_words = job.get("target_words", DEFAULT_WORD_COUNT)
        filename = f"場面{index}_{profession_cleaned}_people{people_count}_words{target_words}_ja.txt"
        output_path = output_dir / filename
        
        # 保存对话文本
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(dialogue_text)
        
        print(f"[場面{index}] 📄 保存完了: {output_path.name}")
        print(f"[場面{index}] 📊 統計: {stats['text_length']} 文字, {stats['line_count']} 行")
        print(f"[場面{index}] ✅ 完了")
        
        return {
            "index": index,
            "profession": profession,
            "success": True,
            "file_path": filename,
            "chars": stats["text_length"],
            "lines": stats["line_count"],
        }
    
    except Exception as e:
        print(f"[場面{index}] ❌ 失敗: {e}")
        import traceback
        traceback.print_exc()
        return {
            "index": index,
            "profession": profession,
            "success": False,
            "error": str(e)
        }


def main():
    """主函数"""
    print("="*80)
    print("バッチ生成：13職業シーン日本語対話テキスト")
    print(f"デフォルトパラメータ: 人数={DEFAULT_PEOPLE_COUNT}, 単語数={DEFAULT_WORD_COUNT}, 言語=日本語")
    print(f"入力ファイル: {INPUT_FILE.name}")
    print("="*80)
    
    # 1. 解析输入文件
    print(f"\n[ステップ1] 入力ファイルを解析")
    if not INPUT_FILE.exists():
        print(f"[エラー] ファイルが存在しません: {INPUT_FILE}")
        return
    
    jobs = parse_input_file(INPUT_FILE)
    
    if len(jobs) != 13:
        print(f"[警告] {len(jobs)} 個の職業を解析しました（期待: 13個）")
    
    # 2. 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 3. 批量生成
    print(f"\n[ステップ2] バッチ生成（合計 {len(jobs)} 個）")
    results = []
    
    for job in jobs:
        result = process_one_job_ja(job, OUTPUT_DIR)
        results.append(result)
    
    # 4. 输出摘要
    print("\n" + "="*80)
    print("✅ バッチ生成完了！")
    print("="*80)
    
    success_count = sum(1 for r in results if r.get('success', False))
    
    print(f"成功: {success_count}/{len(jobs)}")
    
    print(f"\n各シーンの統計:")
    for result in results:
        if result.get('success'):
            print(f"  ✅ 場面{result['index']} - {result['profession']}: "
                  f"{result['chars']} 文字, {result['lines']} 行")
        else:
            print(f"  ❌ 場面{result['index']} - {result['profession']}: "
                  f"エラー: {result.get('error', 'Unknown')}")
    
    print(f"\n📁 出力ディレクトリ: {OUTPUT_DIR}")
    print("="*80)


if __name__ == "__main__":
    main()

