# -*- coding: utf-8 -*-
"""
为4个独立对话场景生成对话文本与音频
参数：字数1500，人物数量3，语言中文
"""

import asyncio
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


def parse_scenarios_file(file_path: Path) -> List[Dict[str, Any]]:
    """解析场景文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    scenarios = []
    pattern = r'（(\d+)）\*\*场景对话设置：\*\*\s*(.*?)\*\*对话核心内容（红色标注）：\*\*\s*(.*?)(?=（\d+）\*\*场景对话设置：|$)'
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        scenarios.append({
            "num": match.group(1),
            "setup": match.group(2).strip(),
            "core": match.group(3).strip()
        })
    
    return scenarios


def build_profile_for_scenario(scenario_setup: str, scenario_num: str) -> Dict[str, str]:
    """根据场景设置构建profile"""
    # 场景1: CEO Tim
    if scenario_num == "1":
        profile = {
            "job_function": "企业管理",
            "work_content": "战略规划",
            "seniority": "公司高层",
            "use_case": "会议记录"
        }
    # 场景2: maik 风控负责人
    elif scenario_num == "2":
        profile = {
            "job_function": "风控",
            "work_content": "风险控制",
            "seniority": "部门负责人",
            "use_case": "风险评估"
        }
    # 场景3: Yoki 保险销售
    elif scenario_num == "3":
        profile = {
            "job_function": "销售",
            "work_content": "保险销售",
            "seniority": "业务骨干",
            "use_case": "客户沟通"
        }
    # 场景4: KK 心理咨询师
    elif scenario_num == "4":
        profile = {
            "job_function": "医疗",
            "work_content": "心理咨询",
            "seniority": "专业技术人员",
            "use_case": "专业咨询"
        }
    else:
        profile = {
            "job_function": "其他",
            "work_content": "其他",
            "seniority": "其他",
            "use_case": "其他"
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
    scenario_setup: str,
    core_content: str,
    output_dir: Path,
    people_count: int = 3,
    target_len: int = 1500,
    language: str = "中文"
) -> Tuple[bool, str, Dict[str, Any]]:
    """为单个场景生成对话文本与音频"""
    try:
        # 构建profile
        profile = build_profile_for_scenario(scenario_setup, scenario_num)
        
        print(f"\n{'='*60}")
        print(f"生成场景 {scenario_num} 对话")
        print(f"{'='*60}")
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
        
        # 保存文本文件
        scenario_name = f"scenario{scenario_num}_dialogue"
        output_file = output_dir / f"{scenario_name}.txt"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(dialogue_text)
        
        # 生成音频
        audio_file = output_dir / f"{scenario_name}.mp3"
        print(f"\n[音频] 开始生成音频: {audio_file}")
        audio_success, audio_info = await generate_audio_for_lines(
            lines=lines,
            output_path=audio_file,
            language=language
        )
        
        if audio_success:
            print(f"[SUCCESS] 场景 {scenario_num} 音频生成成功")
            print(f"  音频文件: {audio_file}")
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
        
        info = {
            "lines_count": len(lines),
            "actual_chars": actual_chars,
            "target_len": target_len,
            "speaker_counts": speaker_counts,
            "rewrite_info": rewrite_info,
            "output_file": str(output_file),
            "audio_success": audio_success,
            "audio_file": str(audio_file) if audio_success else None,
            "audio_info": audio_info
        }
        
        print(f"[SUCCESS] 场景 {scenario_num} 对话生成成功")
        print(f"  对话行数: {len(lines)}")
        print(f"  实际字符数: {actual_chars}")
        print(f"  说话人分布: {speaker_counts}")
        print(f"  输出文件: {output_file}")
        
        return True, "", info
        
    except Exception as e:
        import traceback
        error_msg = f"生成对话失败: {str(e)}"
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        return False, error_msg, {}


async def main_async():
    """主函数：为所有4个场景生成对话文本与音频"""
    scenarios_file = PROJECT_ROOT / "demo" / "4个独立对话场景 1.txt"
    output_dir = PROJECT_ROOT / "demo"
    
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not scenarios_file.exists():
        print(f"[ERROR] 场景文件不存在: {scenarios_file}")
        return 1
    
    # 解析场景文件
    print(f"[解析] 读取场景文件: {scenarios_file}")
    scenarios = parse_scenarios_file(scenarios_file)
    
    if not scenarios:
        print(f"[ERROR] 未解析到任何场景")
        return 1
    
    print(f"[解析] 共解析到 {len(scenarios)} 个场景")
    
    # 生成参数
    people_count = 3
    target_len = 1500
    language = "中文"
    
    print(f"\n[参数] 人物数量: {people_count}, 目标字数: {target_len}, 语言: {language}")
    
    # 为每个场景生成对话和音频
    results = []
    
    for scenario in scenarios:
        scenario_num = scenario["num"]
        scenario_setup = scenario["setup"]
        core_content = scenario["core"]
        
        success, error, info = await generate_dialogue_for_scenario(
            scenario_num=scenario_num,
            scenario_setup=scenario_setup,
            core_content=core_content,
            output_dir=output_dir,
            people_count=people_count,
            target_len=target_len,
            language=language
        )
        
        results.append({
            "scenario_num": scenario_num,
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
    print(f"对话生成成功: {success_count}/{len(scenarios)}")
    print(f"音频生成成功: {audio_success_count}/{len(scenarios)}")
    print(f"失败: {len(scenarios) - success_count}/{len(scenarios)}")
    
    for r in results:
        status_icon = "[OK]" if r.get("status") == "success" else "[FAIL]"
        audio_icon = "[✓]" if r.get("audio_success", False) else "[✗]"
        print(f"{status_icon} {audio_icon} 场景 {r['scenario_num']}")
        if r.get("status") == "success":
            print(f"   对话行数: {r.get('lines_count', 'N/A')}")
            print(f"   实际字符数: {r.get('actual_chars', 'N/A')}")
            print(f"   说话人分布: {r.get('speaker_counts', {})}")
            print(f"   文本文件: {r.get('output_file', 'N/A')}")
            if r.get("audio_success"):
                print(f"   音频文件: {r.get('audio_file', 'N/A')}")
                print(f"   音频大小: {r.get('audio_info', {}).get('audio_size_kb', 0):.2f} KB")
            else:
                print(f"   音频错误: {r.get('audio_info', {}).get('error', 'N/A')}")
        else:
            print(f"   错误: {r.get('error', 'N/A')}")
    
    return 0 if success_count == len(scenarios) else 1


def main():
    """同步入口函数"""
    return asyncio.run(main_async())


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

