# -*- coding: utf-8 -*-
"""
为7个同项目对话场景生成对话文本与音频
参数：字数2000-3000，人物数量4，语言中文（普通话）
"""

import asyncio
import json
import sys
import re
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# 动态导入 server.py
import importlib.util
server_path = PROJECT_ROOT / "server.py"
spec = importlib.util.spec_from_file_location("server", server_path)
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)

_generate_dialogue_lines = server_module._generate_dialogue_lines
_render_dialogue_text = server_module._render_dialogue_text
_generate_tts_audio_for_lines = server_module._generate_tts_audio_for_lines

# FFMPEG 路径
FFMPEG_PATH = PROJECT_ROOT / "bin" / "ffmpeg.exe"


def parse_dialogue_text_file(dialogue_file: Path) -> List[Tuple[str, str]]:
    """
    解析已存在的对话文本文件，提取Speaker和内容
    
    参数:
        dialogue_file: 对话文本文件路径
    
    返回:
        List[Tuple[str, str]]: [(speaker, text), ...]
    """
    try:
        with open(dialogue_file, 'r', encoding='utf-8') as f:
            dialogue_text = f.read()
    except Exception as e:
        print(f"[ERROR] 无法读取对话文件 {dialogue_file}: {e}")
        return []
    
    # 使用server.py中的解析函数
    _robust_parse_speakers = server_module._robust_parse_speakers
    parsed = _robust_parse_speakers(dialogue_text)
    
    # 转换为 (speaker, text) 格式
    lines = []
    for speaker_id, text in parsed:
        lines.append((f"Speaker {speaker_id}", text))
    
    return lines


def parse_scenarios_file(file_path: Path) -> List[Dict[str, Any]]:
    """解析场景文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    scenarios = []
    current_scenario = None
    state = None
    
    for line in lines:
        line = line.rstrip('\n\r')
        # 匹配 "数字）标题"
        match = re.match(r'(\d+)）(.+)', line)
        if match:
            if current_scenario:
                # 清理并保存上一个场景
                current_scenario["setup"] = current_scenario["setup"].strip()
                current_scenario["core"] = current_scenario["core"].strip()
                scenarios.append(current_scenario)
            current_scenario = {
                "num": match.group(1),
                "title": match.group(2).strip(),
                "setup": "",
                "core": ""
            }
            state = None
        elif current_scenario:
            if "场景对话设置：" in line:
                state = "setup"
            elif "对话核心内容（红色标注）：" in line:
                state = "core"
            elif state == "setup" and line.strip():
                if current_scenario["setup"]:
                    current_scenario["setup"] += "\n" + line
                else:
                    current_scenario["setup"] = line
            elif state == "core" and line.strip():
                if current_scenario["core"]:
                    current_scenario["core"] += "\n" + line
                else:
                    current_scenario["core"] = line
    
    # 保存最后一个场景
    if current_scenario:
        current_scenario["setup"] = current_scenario["setup"].strip()
        current_scenario["core"] = current_scenario["core"].strip()
        scenarios.append(current_scenario)
    
    return scenarios


def build_profile_for_scenario(scenario_setup: str, scenario_num: str) -> Dict[str, str]:
    """根据场景设置构建profile"""
    # 所有场景都是测试开发相关，统一使用测试开发profile
    profile = {
        "job_function": "测试开发",
        "work_content": "社交产品测试",
        "seniority": "资深测试开发",
        "use_case": "项目评审"
    }
    
    return profile


async def generate_audio_for_lines(
    lines: List[Tuple[str, str]],
    output_path: Path,
    language: str = "中文"
) -> Tuple[bool, Dict[str, Any]]:
    """
    生成音频
    
    参数:
        lines: 对话行
        output_path: 输出路径（.mp3）
        language: 语言
    
    返回:
        (success, audio_info)
    """
    if not lines:
        return False, {"error": "对话为空"}
    
    # 先生成 WAV
    wav_path = output_path.with_suffix('.wav')
    
    try:
        success, error_msg, voice_map, debug_info, _, _, _ = await _generate_tts_audio_for_lines(
            lines=lines,
            output_wav_path=wav_path,
            language=language,
            pause_ms=200,
            dialogue_id="",
            timestamp=""
        )
        
        if not success:
            return False, {"error": error_msg}
        
        # 转换 WAV 到 MP3
        if not FFMPEG_PATH.exists():
            return False, {"error": f"ffmpeg 不存在: {FFMPEG_PATH}"}
        
        result = subprocess.run(
            [str(FFMPEG_PATH), "-i", str(wav_path), "-y", str(output_path)],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return False, {"error": f"ffmpeg 转换失败: {result.stderr}"}
        
        # 删除 WAV
        if wav_path.exists():
            wav_path.unlink()
        
        # 获取音频文件大小
        audio_size_kb = output_path.stat().st_size / 1024 if output_path.exists() else 0
        
        audio_info = {
            "audio_generated": True,
            "audio_path": str(output_path),
            "audio_size_kb": round(audio_size_kb, 2),
            "voice_map": voice_map
        }
        
        return True, audio_info
    
    except Exception as e:
        print(f"[错误] 音频生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False, {"error": str(e), "exception": traceback.format_exc()}


async def generate_dialogue_for_scenario(
    scenario_num: str,
    scenario_title: str,
    scenario_setup: str,
    core_content: str,
    output_dir: Path,
    people_count: int = 4,
    target_len: int = 2500,
    language: str = "中文"
) -> Tuple[bool, str, Dict[str, Any]]:
    """为单个场景生成对话文本与音频"""
    try:
        # 构建profile
        profile = build_profile_for_scenario(scenario_setup, scenario_num)
        
        print(f"\n{'='*60}")
        print(f"生成场景 {scenario_num} 对话")
        print(f"{'='*60}")
        print(f"标题: {scenario_title}")
        print(f"场景设置: {scenario_setup[:100]}...")
        print(f"核心内容: {core_content[:100]}...")
        print(f"Profile: {profile}")
        print(f"参数: people_count={people_count}, target_len={target_len}, language={language}")
        
        # 生成对话
        lines, rewrite_info = _generate_dialogue_lines(
            profile=profile,
            scenario=scenario_setup,
            core=core_content,
            people=people_count,
            target_len=target_len,
            language=language
        )
        
        if not lines:
            return False, "未生成任何对话内容", {}
        
        # 渲染对话文本
        dialogue_text = _render_dialogue_text(lines)
        
        # 保存文本文件（按照命名规则：场景{num}_{title}.txt）
        scenario_name = f"场景{scenario_num}_{scenario_title}"
        output_file = output_dir / f"{scenario_name}.txt"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(dialogue_text)
        
        # 生成音频：场景{num}_{title}_中文.mp3
        audio_file_cn = output_dir / f"{scenario_name}_中文.mp3"
        print(f"\n[音频] 开始生成音频: {audio_file_cn}")
        audio_success, audio_info = await generate_audio_for_lines(
            lines=lines,
            output_path=audio_file_cn,
            language=language
        )
        
        if audio_success:
            print(f"[SUCCESS] 场景 {scenario_num} 音频生成成功")
            print(f"  音频文件: {audio_file_cn}")
            print(f"  音频大小: {audio_info.get('audio_size_kb', 0):.2f} KB")
        else:
            print(f"[WARNING] 场景 {scenario_num} 音频生成失败: {audio_info.get('error', '未知错误')}")
        
        # 统计信息
        actual_chars = sum(len(text) for _, text in lines)
        speaker_counts = {}
        for speaker, _ in lines:
            speaker_id = re.search(r'Speaker\s*(\d+)', speaker)
            if speaker_id:
                sid = int(speaker_id.group(1))
                speaker_counts[sid] = speaker_counts.get(sid, 0) + 1
        
        # 生成 meta.json
        meta_data = {
            "scenario_num": scenario_num,
            "title": scenario_title,
            "char_count": actual_chars,
            "target_len": target_len,
            "lines_count": len(lines),
            "speaker_counts": speaker_counts,
            "people_count": people_count,
            "language": language,
            "rewrite_info": rewrite_info,
            "audio_success": audio_success,
            "audio_file": str(audio_file_cn) if audio_success else None
        }
        
        meta_file = output_dir / "meta.json"
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)
        
        info = {
            "lines_count": len(lines),
            "actual_chars": actual_chars,
            "target_len": target_len,
            "speaker_counts": speaker_counts,
            "rewrite_info": rewrite_info,
            "output_file": str(output_file),
            "audio_success": audio_success,
            "audio_file": str(audio_file_cn) if audio_success else None,
            "audio_info": audio_info
        }
        
        print(f"[SUCCESS] 场景 {scenario_num} 对话生成成功")
        print(f"  对话行数: {len(lines)}")
        print(f"  实际字符数: {actual_chars}")
        print(f"  说话人分布: {speaker_counts}")
        print(f"  输出文件: {output_file}")
        print(f"  Meta文件: {meta_file}")
        
        return True, "", info
        
    except Exception as e:
        import traceback
        error_msg = f"生成对话失败: {str(e)}"
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        return False, error_msg, {}


async def generate_audio_from_existing_text(
    dialogue_file: Path,
    output_dir: Path,
    language: str = "中文"
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    从已存在的对话文本文件生成音频
    
    参数:
        dialogue_file: 对话文本文件路径
        output_dir: 输出目录
        language: 语言
    
    返回:
        (success, error_msg, info)
    """
    try:
        # 解析对话文本文件
        print(f"\n{'='*60}")
        print(f"从已存在文本生成音频")
        print(f"{'='*60}")
        print(f"对话文件: {dialogue_file}")
        
        lines = parse_dialogue_text_file(dialogue_file)
        if not lines:
            return False, "未解析到任何对话内容", {}
        
        print(f"解析到 {len(lines)} 行对话")
        
        # 从文件名提取场景信息
        file_stem = dialogue_file.stem
        # 匹配 "场景{num}_{title}" 或 "场景{num}_{title}_优化版"
        match = re.match(r'场景(\d+)_(.+?)(?:_优化版)?$', file_stem)
        if match:
            scenario_num = match.group(1)
            scenario_title = match.group(2)
        else:
            # 如果无法匹配，使用文件名作为标题
            scenario_num = "?"
            scenario_title = file_stem
        
        # 生成音频文件名
        audio_file_cn = output_dir / f"{file_stem}_中文.mp3"
        
        # 如果音频文件已存在，跳过
        if audio_file_cn.exists():
            print(f"[SKIP] 音频文件已存在，跳过: {audio_file_cn}")
            audio_size_kb = audio_file_cn.stat().st_size / 1024
            return True, "", {
                "lines_count": len(lines),
                "actual_chars": sum(len(text) for _, text in lines),
                "audio_success": True,
                "audio_file": str(audio_file_cn),
                "audio_info": {
                    "audio_generated": True,
                    "audio_path": str(audio_file_cn),
                    "audio_size_kb": round(audio_size_kb, 2)
                }
            }
        
        print(f"\n[音频] 开始生成音频: {audio_file_cn}")
        audio_success, audio_info = await generate_audio_for_lines(
            lines=lines,
            output_path=audio_file_cn,
            language=language
        )
        
        if audio_success:
            print(f"[SUCCESS] 音频生成成功")
            print(f"  音频文件: {audio_file_cn}")
            print(f"  音频大小: {audio_info.get('audio_size_kb', 0):.2f} KB")
        else:
            print(f"[WARNING] 音频生成失败: {audio_info.get('error', '未知错误')}")
        
        # 统计信息
        actual_chars = sum(len(text) for _, text in lines)
        speaker_counts = {}
        for speaker, _ in lines:
            speaker_id = re.search(r'Speaker\s*(\d+)', speaker)
            if speaker_id:
                sid = int(speaker_id.group(1))
                speaker_counts[sid] = speaker_counts.get(sid, 0) + 1
        
        info = {
            "lines_count": len(lines),
            "actual_chars": actual_chars,
            "speaker_counts": speaker_counts,
            "audio_success": audio_success,
            "audio_file": str(audio_file_cn) if audio_success else None,
            "audio_info": audio_info
        }
        
        return True, "", info
        
    except Exception as e:
        import traceback
        error_msg = f"生成音频失败: {str(e)}"
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        return False, error_msg, {}


async def main_async():
    """主函数：从已存在的对话文本文件生成音频"""
    output_base_dir = PROJECT_ROOT / "output" / "朋友圈项目"
    
    # 确保输出目录存在
    output_base_dir.mkdir(parents=True, exist_ok=True)
    
    if not output_base_dir.exists():
        print(f"[ERROR] 输出目录不存在: {output_base_dir}")
        return 1
    
    # 扫描所有场景目录，查找对话文本文件
    print(f"[扫描] 扫描输出目录: {output_base_dir}")
    scenario_dirs = [d for d in output_base_dir.iterdir() if d.is_dir() and d.name.startswith("场景")]
    scenario_dirs.sort()  # 按名称排序
    
    if not scenario_dirs:
        print(f"[ERROR] 未找到任何场景目录")
        return 1
    
    print(f"[扫描] 找到 {len(scenario_dirs)} 个场景目录")
    
    # 语言设置
    language = "中文"
    
    # 为每个场景生成音频
    results = []
    
    for scenario_dir in scenario_dirs:
        # 查找对话文本文件（优先查找 *_优化版.txt，否则查找 *.txt）
        dialogue_files = list(scenario_dir.glob("*_优化版.txt"))
        if not dialogue_files:
            dialogue_files = list(scenario_dir.glob("*.txt"))
            # 排除meta.json等非对话文件
            dialogue_files = [f for f in dialogue_files if not f.name.startswith("meta") and not f.name.startswith("tts_")]
        
        if not dialogue_files:
            print(f"[WARNING] 场景目录 {scenario_dir.name} 中未找到对话文本文件")
            results.append({
                "scenario_dir": scenario_dir.name,
                "status": "failed",
                "error": "未找到对话文本文件"
            })
            continue
        
        # 使用第一个找到的对话文件
        dialogue_file = dialogue_files[0]
        print(f"\n[处理] 场景目录: {scenario_dir.name}")
        print(f"  对话文件: {dialogue_file.name}")
        
        success, error, info = await generate_audio_from_existing_text(
            dialogue_file=dialogue_file,
            output_dir=scenario_dir,
            language=language
        )
        
        # 从目录名提取场景信息
        match = re.match(r'场景(\d+)_(.+)', scenario_dir.name)
        if match:
            scenario_num = match.group(1)
            scenario_title = match.group(2)
        else:
            scenario_num = "?"
            scenario_title = scenario_dir.name
        
        results.append({
            "scenario_num": scenario_num,
            "title": scenario_title,
            "scenario_dir": scenario_dir.name,
            "status": "success" if success else "failed",
            "error": error,
            **info
        })
    
    # 生成汇总报告
    print(f"\n{'='*60}")
    print("生成汇总")
    print(f"{'='*60}")
    
    success_count = sum(1 for r in results if r.get("status") == "success")
    audio_success_count = sum(1 for r in results if r.get("audio_success", False))
    total_count = len(results)
    print(f"处理场景数: {total_count}")
    print(f"音频生成成功: {audio_success_count}/{total_count}")
    print(f"失败: {total_count - success_count}/{total_count}")
    
    for r in results:
        status_icon = "[OK]" if r.get("status") == "success" else "[FAIL]"
        audio_icon = "[✓]" if r.get("audio_success", False) else "[✗]"
        scenario_num = r.get('scenario_num', '?')
        scenario_title = r.get('title', r.get('scenario_dir', 'N/A'))
        print(f"{status_icon} {audio_icon} 场景 {scenario_num}: {scenario_title}")
        if r.get("status") == "success":
            print(f"   对话行数: {r.get('lines_count', 'N/A')}")
            print(f"   实际字符数: {r.get('actual_chars', 'N/A')}")
            print(f"   说话人分布: {r.get('speaker_counts', {})}")
            if r.get("audio_success"):
                print(f"   音频文件: {r.get('audio_file', 'N/A')}")
                print(f"   音频大小: {r.get('audio_info', {}).get('audio_size_kb', 0):.2f} KB")
            else:
                print(f"   音频错误: {r.get('audio_info', {}).get('error', 'N/A')}")
        else:
            print(f"   错误: {r.get('error', 'N/A')}")
    
    return 0 if success_count == total_count else 1


def main():
    """同步入口函数"""
    return asyncio.run(main_async())


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

