#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量生成对话音频（Edge TTS）"""

import asyncio
import sys
import re
from pathlib import Path
from typing import List, Optional, Dict, Tuple

# 修复Windows控制台UTF-8编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 添加项目根目录到 sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import edge_tts
    from pydub import AudioSegment
    import tempfile
except ImportError as e:
    print(f"❌ 缺少依赖: {e}")
    print("请运行: pip install edge-tts pydub")
    sys.exit(1)

# 配置
OUTPUT_DIR = PROJECT_ROOT / "output"
AUDIO_DIR = PROJECT_ROOT / "audio"

# 英文语音选项（可选多个）
ENGLISH_VOICES = {
    "en-US-JennyNeural": "美式英语-女声（推荐）",
    "en-US-GuyNeural": "美式英语-男声",
    "en-GB-SoniaNeural": "英式英语-女声",
    "en-GB-RyanNeural": "英式英语-男声",
    "en-US-AriaNeural": "美式英语-女声2",
    "en-US-DavisNeural": "美式英语-男声2",
    "en-US-AmberNeural": "美式英语-女声3",
    "en-US-BrandonNeural": "美式英语-男声3",
}

DEFAULT_VOICE = "en-US-JennyNeural"

# 角色语音池（循环分配给不同角色）
ROLE_VOICES = [
    "en-US-GuyNeural",      # 男声1
    "en-US-JennyNeural",    # 女声1
    "en-US-DavisNeural",    # 男声2
    "en-US-AriaNeural",     # 女声2
    "en-US-BrandonNeural",  # 男声3
    "en-US-AmberNeural",    # 女声3
]


def parse_dialogue_lines(text: str) -> List[tuple]:
    """
    解析对话文本，提取角色和对话内容
    
    Returns:
        List of (speaker_name, dialogue_text)
    """
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # 匹配格式：Speaker Name: dialogue content
        match = re.match(r'^([^:]+):\s*(.+)$', line)
        if match:
            speaker = match.group(1).strip()
            content = match.group(2).strip()
            # 过滤掉空内容
            if content:
                lines.append((speaker, content))
    
    return lines


def assign_voices_to_speakers(speakers: List[str]) -> dict:
    """
    为每个角色分配不同的语音
    
    Args:
        speakers: 角色名称列表
    
    Returns:
        Dict mapping speaker name to voice
    """
    speaker_voices = {}
    for i, speaker in enumerate(speakers):
        # 循环分配语音
        voice = ROLE_VOICES[i % len(ROLE_VOICES)]
        speaker_voices[speaker] = voice
    
    return speaker_voices


async def generate_audio_segment(text: str, voice: str, output_path: Path) -> bool:
    """
    生成单个音频片段
    
    Args:
        text: 文本内容
        voice: TTS语音
        output_path: 输出文件路径
    
    Returns:
        是否成功
    """
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(output_path))
        return True
    except Exception as e:
        print(f"  [错误] 生成音频片段失败: {e}")
        return False


async def generate_multi_voice_audio(
    text_file: Path, 
    output_file: Path, 
    verbose: bool = True
) -> bool:
    """
    生成多角色语音的音频文件（每个角色使用不同声音）
    
    Args:
        text_file: 对话文本文件路径
        output_file: 音频输出文件路径
        verbose: 是否输出详细信息
    
    Returns:
        是否成功
    """
    try:
        if verbose:
            print(f"[音频] 处理: {text_file.name}")
        
        # 读取文本
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # 预处理文本
        text = preprocess_text(text)
        
        if not text.strip():
            print(f"[音频] ⚠️ 跳过空文本: {text_file.name}")
            return False
        
        # 解析对话行
        dialogue_lines = parse_dialogue_lines(text)
        
        if not dialogue_lines:
            print(f"[音频] ⚠️ 没有找到对话内容: {text_file.name}")
            return False
        
        # 识别所有唯一的角色
        speakers = list(dict.fromkeys([speaker for speaker, _ in dialogue_lines]))
        
        # 为每个角色分配语音
        speaker_voices = assign_voices_to_speakers(speakers)
        
        if verbose:
            print(f"[音频] 识别到 {len(speakers)} 个角色:")
            for speaker, voice in speaker_voices.items():
                voice_desc = ENGLISH_VOICES.get(voice, voice)
                print(f"  - {speaker}: {voice_desc}")
        
        # 创建临时目录存放音频片段
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            audio_segments = []
            
            # 为每句对话生成音频
            for i, (speaker, content) in enumerate(dialogue_lines):
                voice = speaker_voices.get(speaker, DEFAULT_VOICE)
                segment_path = temp_dir_path / f"segment_{i:04d}.mp3"
                
                # 生成音频片段
                success = await generate_audio_segment(content, voice, segment_path)
                
                if success and segment_path.exists():
                    audio_segments.append(segment_path)
                else:
                    print(f"  [警告] 跳过片段 {i}: {speaker}")
            
            if not audio_segments:
                print(f"[音频] ❌ 没有生成任何音频片段: {text_file.name}")
                return False
            
            # 合并所有音频片段
            if verbose:
                print(f"[音频] 合并 {len(audio_segments)} 个音频片段...")
            
            combined = AudioSegment.empty()
            for segment_path in audio_segments:
                try:
                    audio = AudioSegment.from_mp3(str(segment_path))
                    # 添加短暂停顿（500ms）
                    silence = AudioSegment.silent(duration=500)
                    combined += audio + silence
                except Exception as e:
                    print(f"  [警告] 无法加载音频片段: {segment_path} - {e}")
            
            # 导出最终音频
            combined.export(str(output_file), format="mp3")
        
        # 检查文件大小
        file_size = output_file.stat().st_size
        if file_size < 1024:
            print(f"[音频] ⚠️ 音频文件过小: {text_file.name} ({file_size} bytes)")
            return False
        
        if verbose:
            print(f"[音频] ✅ 完成: {output_file.name} ({file_size // 1024} KB)")
        
        return True
    
    except Exception as e:
        print(f"[音频] ❌ 失败: {text_file.name} - {e}")
        import traceback
        traceback.print_exc()
        return False


# 保留旧的单语音函数作为备用
async def generate_audio(
    text_file: Path, 
    output_file: Path, 
    voice: str = DEFAULT_VOICE,
    verbose: bool = True
) -> bool:
    """
    生成单个音频文件（单一语音，已废弃，请使用 generate_multi_voice_audio）
    
    Args:
        text_file: 对话文本文件路径
        output_file: 音频输出文件路径
        voice: TTS语音
        verbose: 是否输出详细信息
    
    Returns:
        是否成功
    """
    # 直接调用多语音版本
    return await generate_multi_voice_audio(text_file, output_file, verbose)


def preprocess_text(text: str) -> str:
    """
    预处理对话文本，使其适合TTS
    
    处理:
    1. 移除 <<Core:...>> 标记
    2. 移除空行
    3. 保留对话格式（Speaker: content）
    """
    # 移除 <<Core:...>> 标记
    text = re.sub(r'<<Core:.*?>>', '', text, flags=re.DOTALL)
    
    # 移除多余的空行
    lines = [line for line in text.split('\n') if line.strip()]
    
    # 重新组合
    text = '\n'.join(lines)
    
    return text


async def batch_generate(
    input_dir: Path, 
    output_dir: Path, 
    voice: str = DEFAULT_VOICE,
    pattern: str = "场景*_en.txt"
) -> dict:
    """
    批量生成所有对话音频
    
    Args:
        input_dir: 对话文本目录
        output_dir: 音频输出目录
        voice: TTS语音
        pattern: 文件匹配模式
    
    Returns:
        统计信息字典
    """
    # 创建输出目录
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # 查找所有对话文本文件
    text_files = sorted(list(input_dir.glob(pattern)))
    
    if not text_files:
        print(f"❌ 未找到匹配的对话文本文件: {input_dir / pattern}")
        return {"total": 0, "success": 0, "failed": 0}
    
    print("="*80)
    print(f"批量音频生成")
    print(f"输入目录: {input_dir}")
    print(f"输出目录: {output_dir}")
    print(f"TTS语音: {voice} ({ENGLISH_VOICES.get(voice, 'Unknown')})")
    print(f"找到 {len(text_files)} 个对话文本")
    print("="*80)
    print()
    
    # 批量生成
    success_count = 0
    failed_count = 0
    
    for i, text_file in enumerate(text_files, 1):
        print(f"\n[{i}/{len(text_files)}] {text_file.name}")
        
        # 生成音频文件名
        audio_file = output_dir / text_file.name.replace("_en.txt", "_en.mp3")
        
        # 使用多角色语音生成
        success = await generate_multi_voice_audio(text_file, audio_file, verbose=True)
        
        if success:
            success_count += 1
        else:
            failed_count += 1
    
    # 输出摘要
    print("\n" + "="*80)
    print("✅ 批量音频生成完成！")
    print("="*80)
    print(f"总计: {len(text_files)} 个")
    print(f"成功: {success_count} 个")
    print(f"失败: {failed_count} 个")
    print(f"\n📁 输出目录: {output_dir}")
    print("="*80)
    
    # 列出生成的音频文件
    audio_files = sorted(list(output_dir.glob("场景*_en.mp3")))
    if audio_files:
        print(f"\n生成的音频文件:")
        for audio_file in audio_files:
            file_size = audio_file.stat().st_size
            print(f"  ✅ {audio_file.name} ({file_size // 1024} KB)")
    
    return {
        "total": len(text_files),
        "success": success_count,
        "failed": failed_count,
    }


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="批量生成对话音频（多角色语音版本）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
【功能说明】
  - 自动识别对话中的不同角色
  - 为每个角色分配不同的语音声线
  - 支持4-6个角色的混合语音

可用语音池:
{chr(10).join(f'  - {voice}: {desc}' for voice, desc in ENGLISH_VOICES.items())}

使用示例:
  python tools/batch_generate_audio.py
  python tools/batch_generate_audio.py --input output --output audio_multi_voice
        """
    )
    
    parser.add_argument(
        "--input", 
        type=str, 
        default="output", 
        help="对话文本目录 (默认: output)"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        default="audio", 
        help="音频输出目录 (默认: audio)"
    )
    parser.add_argument(
        "--voice", 
        type=str, 
        default=DEFAULT_VOICE, 
        choices=list(ENGLISH_VOICES.keys()),
        help=f"TTS语音 (默认: {DEFAULT_VOICE})"
    )
    parser.add_argument(
        "--pattern", 
        type=str, 
        default="场景*_en.txt", 
        help="文件匹配模式 (默认: 场景*_en.txt)"
    )
    
    args = parser.parse_args()
    
    # 路径解析
    input_dir = PROJECT_ROOT / args.input
    output_dir = PROJECT_ROOT / args.output
    
    if not input_dir.exists():
        print(f"❌ 输入目录不存在: {input_dir}")
        sys.exit(1)
    
    # 运行批量生成
    stats = asyncio.run(batch_generate(
        input_dir=input_dir,
        output_dir=output_dir,
        voice=args.voice,
        pattern=args.pattern
    ))
    
    # 退出码
    sys.exit(0 if stats["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
