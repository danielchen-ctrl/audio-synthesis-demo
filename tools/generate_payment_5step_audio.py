# -*- coding: utf-8 -*-
"""
为payment_5step的5个Step对话文本生成音频
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    print("[WARNING] edge-tts 未安装，请运行: pip install edge-tts")


def parse_dialogue_text(text: str) -> List[Tuple[str, str]]:
    """解析对话文本，提取Speaker和内容"""
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # 匹配 "Speaker 1: 内容" 或 "Speaker 1:内容"
        match = re.match(r'Speaker\s*(\d+)\s*[:：]\s*(.+)', line, re.IGNORECASE)
        if match:
            speaker_id = match.group(1)
            content = match.group(2).strip()
            if content:
                lines.append((f"Speaker {speaker_id}", content))
    
    return lines


def clean_tts_text(text: str) -> str:
    """清洗TTS文本，移除标记和特殊字符"""
    # 移除核心标记
    text = re.sub(r'<<核心:.*?>>', '', text)
    # 移除Speaker前缀（如果还有）
    text = re.sub(r'^Speaker\s*\d+\s*[:：]\s*', '', text, flags=re.IGNORECASE)
    # 移除多余的空白
    text = ' '.join(text.split())
    return text


async def generate_audio_for_step(
    dialogue_file: Path,
    output_audio_file: Path,
    language: str = "中文"
) -> Tuple[bool, str, Dict[str, Any]]:
    """为单个Step生成音频"""
    if not EDGE_TTS_AVAILABLE:
        return False, "edge-tts 未安装", {}
    
    # 读取对话文本
    with open(dialogue_file, 'r', encoding='utf-8') as f:
        dialogue_text = f.read()
    
    # 解析对话行
    lines = parse_dialogue_text(dialogue_text)
    if not lines:
        return False, "未找到对话内容", {}
    
    print(f"[TTS] 开始生成音频: {dialogue_file.name}")
    print(f"[TTS] 对话行数: {len(lines)}")
    
    # 获取中文普通话语音列表（zh-CN）
    voices = await edge_tts.list_voices()
    chinese_voices = [v for v in voices if v['Locale'].startswith('zh-CN')]
    if not chinese_voices:
        # 如果没有zh-CN，fallback到所有中文语音
        chinese_voices = [v for v in voices if v['Locale'].startswith('zh')]
    
    # 为不同Speaker分配不同语音
    voice_map = {}
    used_voices = set()
    for speaker_str, _ in lines:
        speaker_id = re.search(r'Speaker\s*(\d+)', speaker_str)
        if speaker_id:
            sid = int(speaker_id.group(1))
            if sid not in voice_map:
                # 选择不同的语音
                for voice in chinese_voices:
                    if voice['Name'] not in used_voices:
                        voice_map[sid] = voice['Name']
                        used_voices.add(voice['Name'])
                        break
                if sid not in voice_map:
                    # 如果语音不够，循环使用
                    voice_map[sid] = chinese_voices[sid % len(chinese_voices)]['Name']
    
    print(f"[TTS] 语音分配（中文普通话）: {voice_map}")
    if chinese_voices:
        print(f"[TTS] 可用中文普通话语音数: {len(chinese_voices)}")
        print(f"[TTS] 示例语音: {chinese_voices[0]['Name'] if chinese_voices else 'N/A'}")
    
    # 生成音频片段
    audio_segments = []
    temp_files = []
    
    try:
        for idx, (speaker_str, text) in enumerate(lines):
            speaker_id = re.search(r'Speaker\s*(\d+)', speaker_str)
            if not speaker_id:
                continue
            
            sid = int(speaker_id.group(1))
            voice_name = voice_map.get(sid, chinese_voices[0]['Name'])
            
            # 清洗文本
            clean_text = clean_tts_text(text)
            if not clean_text:
                continue
            
            # 生成临时MP3文件（使用绝对路径避免问题）
            import tempfile
            temp_dir = output_audio_file.parent
            temp_file = temp_dir / f"temp_{idx:04d}.mp3"
            temp_files.append(temp_file)
            
            # 调用edge-tts生成音频
            try:
                communicate = edge_tts.Communicate(clean_text, voice_name)
                await communicate.save(str(temp_file))
                # 验证文件是否生成
                if not temp_file.exists():
                    print(f"[WARNING] 临时文件未生成: {temp_file}")
                    continue
            except Exception as e:
                print(f"[ERROR] 生成音频片段失败 [{idx+1}/{len(lines)}]: {e}")
                continue
            
            print(f"[TTS] [{idx+1}/{len(lines)}] Speaker {sid}: {clean_text[:30]}...")
        
        # 合并音频文件
        if temp_files:
            print(f"[TTS] 合并 {len(temp_files)} 个音频片段...")
            # 使用ffmpeg合并（如果可用）或简单拼接
            try:
                import subprocess
                # 创建文件列表（使用绝对路径，但需要转义）
                file_list = output_audio_file.parent / "file_list.txt"
                with open(file_list, 'w', encoding='utf-8') as f:
                    for tf in temp_files:
                        # 只包含实际存在的文件
                        if tf.exists():
                            # 使用绝对路径，Windows路径需要转义反斜杠
                            abs_path = str(tf.absolute()).replace('\\', '/')
                            f.write(f"file '{abs_path}'\n")
                
                # 使用ffmpeg合并
                cmd = [
                    'ffmpeg', '-f', 'concat', '-safe', '0',
                    '-i', str(file_list),
                    '-c', 'copy',
                    str(output_audio_file)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                
                if result.returncode != 0:
                    print(f"[WARNING] ffmpeg合并失败，尝试直接使用MP3: {result.stderr}")
                    # 如果ffmpeg不可用，直接使用第一个文件（或最后一个）
                    import shutil
                    shutil.copy(temp_files[0], output_audio_file)
                else:
                    # 清理临时文件
                    file_list.unlink(missing_ok=True)
            except FileNotFoundError:
                print("[WARNING] ffmpeg 未安装，使用第一个音频文件")
                import shutil
                shutil.copy(temp_files[0], output_audio_file)
            
            # 清理临时文件
            for tf in temp_files:
                tf.unlink(missing_ok=True)
            
            print(f"[TTS] 音频生成完成: {output_audio_file}")
            return True, "", {
                "lines_count": len(lines),
                "voice_map": voice_map,
                "audio_file": str(output_audio_file)
            }
        else:
            return False, "未生成任何音频片段", {}
    
    except Exception as e:
        import traceback
        error_msg = f"生成音频失败: {str(e)}"
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        # 清理临时文件
        for tf in temp_files:
            tf.unlink(missing_ok=True)
        return False, error_msg, {}


async def main():
    """主函数：为所有5个Step生成音频"""
    base_dir = Path(__file__).parent.parent
    payment_5step_dir = base_dir / "output" / "payment_5step"
    
    if not payment_5step_dir.exists():
        print(f"[ERROR] 目录不存在: {payment_5step_dir}")
        return 1
    
    steps = [
        ("step1_支付渠道接入（整体推进）", "step1_支付渠道接入（整体推进）.txt"),
        ("step2_支付下单与回调链路（核心交易）", "step2_支付下单与回调链路（核心交易）.txt"),
        ("step3_退款与资金安全（高风险场景）", "step3_退款与资金安全（高风险场景）.txt"),
        ("step4_对账与差错处理（上线前必过）", "step4_对账与差错处理（上线前必过）.txt"),
        ("step5_稳定性与上线准入（Go-No-Go）", "step5_稳定性与上线准入（Go-No-Go）.txt"),
    ]
    
    results = []
    
    for step_dir_name, dialogue_file_name in steps:
        step_dir = payment_5step_dir / step_dir_name
        dialogue_file = step_dir / dialogue_file_name
        
        if not dialogue_file.exists():
            print(f"[WARNING] 文件不存在: {dialogue_file}")
            continue
        
        # 输出音频文件：step{id}_{title}_中文.mp3
        step_id = step_dir_name.split('_')[0].replace('step', '')
        title = step_dir_name.split('_', 1)[1] if '_' in step_dir_name else step_dir_name
        audio_file = step_dir / f"{step_dir_name}_中文.mp3"
        
        print(f"\n{'='*60}")
        print(f"生成 Step {step_id} 音频")
        print(f"{'='*60}")
        
        success, error, info = await generate_audio_for_step(
            dialogue_file,
            audio_file,
            language="中文"
        )
        
        if success:
            print(f"[SUCCESS] Step {step_id} 音频生成成功: {audio_file}")
            results.append({
                "step_id": step_id,
                "title": title,
                "status": "success",
                "audio_file": str(audio_file),
                **info
            })
        else:
            print(f"[FAILED] Step {step_id} 音频生成失败: {error}")
            results.append({
                "step_id": step_id,
                "title": title,
                "status": "failed",
                "error": error
            })
    
    # 生成汇总报告
    print(f"\n{'='*60}")
    print("生成汇总")
    print(f"{'='*60}")
    
    success_count = sum(1 for r in results if r.get("status") == "success")
    print(f"成功: {success_count}/5")
    print(f"失败: {5 - success_count}/5")
    
    for r in results:
        status_icon = "[OK]" if r.get("status") == "success" else "[FAIL]"
        print(f"{status_icon} Step {r['step_id']}: {r['title']}")
        if r.get("status") == "success":
            print(f"   音频文件: {r.get('audio_file', 'N/A')}")
    
    return 0 if success_count == 5 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
