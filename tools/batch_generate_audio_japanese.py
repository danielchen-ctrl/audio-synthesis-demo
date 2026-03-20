#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量生成日语对话音频（多角色语音版本）
- 每个speaker使用不同的日语语音
- 自动识别speaker并分配语音
- 使用pydub合并音频段
"""

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict

# 导入edge-tts
try:
    import edge_tts
except ImportError:
    print("错误: 请先安装edge-tts")
    print("运行: pip install edge-tts")
    sys.exit(1)

# 导入pydub（音频处理）
try:
    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent
except ImportError:
    print("错误: 请先安装pydub")
    print("运行: pip install pydub")
    sys.exit(1)

# 确保 UTF-8 输出
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 日语语音池（6种不同的日语语音）
VOICE_POOL_JA = {
    "speaker1": "ja-JP-KeitaNeural",      # 男声1 - 成熟稳重
    "speaker2": "ja-JP-NanamiNeural",     # 女声1 - 专业清晰
    "speaker3": "ja-JP-DaichiNeural",     # 男声2 - 年轻活力
    "speaker4": "ja-JP-MayuNeural",       # 女声2 - 温和亲切
    "speaker5": "ja-JP-NaokiNeural",      # 男声3 - 权威感
    "speaker6": "ja-JP-ShioriNeural",     # 女声3 - 柔和温暖
}

# 默认速率（日语稍慢）
DEFAULT_RATE = "+0%"


def parse_dialogue_lines(text: str) -> List[Tuple[str, str]]:
    """
    解析对话文本，提取(speaker, content)对
    
    示例输入:
        田中 博士（部門長）：こんにちは、皆さん...
        佐藤 部長（病院リーダーシップ）：ありがとうございます...
    
    返回: [("田中 博士（部門長）", "こんにちは、皆さん..."), ...]
    """
    lines = []
    pattern = r'^(.+?)[:：](.+)$'
    
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # 跳过标题行
        if line.startswith('---') or line.startswith('==='):
            continue
        if '对话' in line or '對話' in line or '対話' in line:
            continue
        
        # 匹配 "Speaker: Content" 格式
        match = re.match(pattern, line)
        if match:
            speaker = match.group(1).strip()
            content = match.group(2).strip()
            
            # 跳过空内容或特殊标记
            if not content or content.startswith('<') or content.startswith('['):
                continue
            
            lines.append((speaker, content))
    
    return lines


def assign_voices_to_speakers(speakers: List[str]) -> Dict[str, str]:
    """
    为识别出的speakers分配语音
    
    参数:
        speakers: 唯一的speaker列表（按出现顺序）
    
    返回:
        {speaker: voice_name} 映射
    """
    voice_mapping = {}
    voice_keys = list(VOICE_POOL_JA.keys())
    
    for idx, speaker in enumerate(speakers):
        voice_key = voice_keys[idx % len(voice_keys)]
        voice_mapping[speaker] = VOICE_POOL_JA[voice_key]
    
    return voice_mapping


async def generate_audio_segment(
    text_content: str,
    voice: str,
    output_path: Path,
    rate: str = DEFAULT_RATE
) -> bool:
    """
    生成单个音频段
    
    参数:
        text_content: 要转换的文本
        voice: Edge TTS 语音名称
        output_path: 输出文件路径
        rate: 语速调整
    
    返回:
        是否成功
    """
    try:
        communicate = edge_tts.Communicate(text_content, voice, rate=rate)
        await communicate.save(str(output_path))
        return True
    except Exception as e:
        print(f"  ❌ 音频段生成失败: {e}")
        return False


async def batch_generate_single_file(
    input_file: Path,
    output_dir: Path,
    voice_pool: Dict[str, str] = VOICE_POOL_JA,
    rate: str = DEFAULT_RATE
):
    """
    为单个对话文件生成多角色音频
    
    流程:
        1. 解析对话文本，识别所有speaker
        2. 为每个speaker分配唯一语音
        3. 逐段生成音频
        4. 使用pydub合并所有段，添加间隔
    """
    print(f"\n{'='*80}")
    print(f"処理中: {input_file.name}")
    print(f"{'='*80}")
    
    # 1. 读取对话文本
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            dialogue_text = f.read()
    except Exception as e:
        print(f"  ❌ 読み込みエラー: {e}")
        return
    
    # 2. 解析对话行
    dialogue_lines = parse_dialogue_lines(dialogue_text)
    
    if not dialogue_lines:
        print(f"  ❌ 有効な対話が見つかりません")
        return
    
    print(f"  📝 {len(dialogue_lines)} 行を解析しました")
    
    # 3. 识别唯一的speakers
    speakers_in_order = []
    seen_speakers = set()
    for speaker, _ in dialogue_lines:
        if speaker not in seen_speakers:
            speakers_in_order.append(speaker)
            seen_speakers.add(speaker)
    
    print(f"  👥 {len(speakers_in_order)} 名のスピーカーを識別しました")
    
    # 4. 分配语音
    voice_mapping = assign_voices_to_speakers(speakers_in_order)
    
    print(f"  🎤 音声割り当て:")
    for idx, (speaker, voice) in enumerate(voice_mapping.items(), 1):
        print(f"    {idx}. {speaker} → {voice}")
    
    # 5. 创建临时目录存放音频段
    temp_dir = output_dir / "temp_segments"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # 6. 逐段生成音频
    print(f"  🔊 音声セグメントを生成中...")
    segment_files = []
    
    for idx, (speaker, content) in enumerate(dialogue_lines, 1):
        voice = voice_mapping.get(speaker, list(voice_pool.values())[0])
        segment_path = temp_dir / f"segment_{idx:04d}.mp3"
        
        success = await generate_audio_segment(
            text_content=content,
            voice=voice,
            output_path=segment_path,
            rate=rate
        )
        
        if success and segment_path.exists():
            segment_files.append(segment_path)
        else:
            print(f"    ⚠️ セグメント {idx} 生成失敗: {speaker}")
    
    print(f"  ✅ {len(segment_files)}/{len(dialogue_lines)} セグメント生成完了")
    
    # 7. 合并音频段
    if segment_files:
        print(f"  🔗 音声セグメントを結合中...")
        try:
            # 加载所有音频段
            audio_segments = []
            silence = AudioSegment.silent(duration=500)  # 500ms静音间隔
            
            for seg_file in segment_files:
                audio = AudioSegment.from_mp3(str(seg_file))
                audio_segments.append(audio)
                audio_segments.append(silence)
            
            # 移除最后一个静音
            if audio_segments:
                audio_segments.pop()
            
            # 合并
            combined = sum(audio_segments)
            
            # 输出文件
            output_filename = input_file.stem.replace('_ja', '') + '_ja.mp3'
            output_path = output_dir / output_filename
            
            # 删除旧文件（如果存在）
            if output_path.exists():
                output_path.unlink()
                print(f"  🗑️ 古いファイルを削除しました")
            
            combined.export(str(output_path), format='mp3')
            
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"  ✅ 音声生成完了: {output_path.name}")
            print(f"  📦 ファイルサイズ: {file_size_mb:.2f} MB")
            print(f"  ⏱️ 再生時間: {len(combined) / 1000:.1f} 秒")
        
        except Exception as e:
            print(f"  ❌ 結合エラー: {e}")
            import traceback
            traceback.print_exc()
    
    # 8. 清理临时文件
    try:
        for seg_file in temp_dir.glob("*.mp3"):
            seg_file.unlink()
        temp_dir.rmdir()
    except Exception as e:
        print(f"  ⚠️ 一時ファイルのクリーンアップに失敗: {e}")


async def batch_generate(
    input_dir: Path,
    output_dir: Path,
    voice_pool: Dict[str, str] = VOICE_POOL_JA,
    pattern: str = "*_ja.txt"
):
    """
    批量生成音频
    
    参数:
        input_dir: 输入对话文本目录
        output_dir: 输出音频目录
        voice_pool: 语音池
        pattern: 文件匹配模式
    """
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 获取所有对话文本文件
    txt_files = sorted(input_dir.glob(pattern))
    
    if not txt_files:
        print(f"⚠️ {input_dir} に {pattern} ファイルが見つかりません")
        return
    
    print(f"🎯 {len(txt_files)} ファイルが見つかりました")
    
    # 逐个处理
    for txt_file in txt_files:
        await batch_generate_single_file(txt_file, output_dir, voice_pool)
    
    print(f"\n{'='*80}")
    print(f"✅ バッチ音声生成完了！")
    print(f"{'='*80}")
    print(f"📁 出力ディレクトリ: {output_dir}")
    print(f"🎵 合計: {len(list(output_dir.glob('*.mp3')))} 音声ファイル")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="批量生成日语对话音频（多角色）")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=PROJECT_ROOT / "output_ja",
        help="输入对话文本目录"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "audio_ja",
        help="输出音频目录"
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*_ja.txt",
        help="文件匹配模式"
    )
    parser.add_argument(
        "--rate",
        type=str,
        default=DEFAULT_RATE,
        help="语速调整（如 +10% 或 -10%）"
    )
    
    args = parser.parse_args()
    
    print("="*80)
    print("バッチ音声生成：日本語対話（マルチロール）")
    print("="*80)
    print(f"入力: {args.input_dir}")
    print(f"出力: {args.output_dir}")
    print(f"パターン: {args.pattern}")
    print(f"レート: {args.rate}")
    print("="*80)
    
    # 运行异步批量生成
    asyncio.run(batch_generate(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        voice_pool=VOICE_POOL_JA,
        pattern=args.pattern
    ))


if __name__ == "__main__":
    main()
