# -*- coding: utf-8 -*-
"""
场景对话回归测试脚本
为4个独立场景生成对话并运行校验器
"""

import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Tuple

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from training.role_cards import get_role_cards, get_speaker_name, SCENARIO_ROLE_MAP
from training.dialogue_validators import validate_dialogue_lines, ValidationError
from training.scene_dialogue_enhancer import apply_role_names_to_lines, check_forbidden_phrases

# 动态导入 server.py
import importlib.util
server_path = PROJECT_ROOT / "server.py"
spec = importlib.util.spec_from_file_location("server", server_path)
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)

_generate_dialogue_lines = server_module._generate_dialogue_lines
_render_dialogue_text = server_module._render_dialogue_text


def parse_scenarios_file(file_path: Path) -> List[Dict[str, Any]]:
    """解析场景文件"""
    import re
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
    if scenario_num == "1":
        profile = {
            "job_function": "企业管理",
            "work_content": "战略规划",
            "seniority": "公司高层",
            "use_case": "会议记录"
        }
    elif scenario_num == "2":
        profile = {
            "job_function": "风控",
            "work_content": "风险控制",
            "seniority": "部门负责人",
            "use_case": "风险评估"
        }
    elif scenario_num == "3":
        profile = {
            "job_function": "销售",
            "work_content": "保险销售",
            "seniority": "业务骨干",
            "use_case": "客户沟通"
        }
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


# 使用scene_dialogue_enhancer中的函数


def generate_dialogue_for_scenario(
    scenario_num: str,
    scenario_setup: str,
    core_content: str,
    output_dir: Path,
    people_count: int = 3,
    target_len: int = 1000,
    language: str = "中文",
    max_retries: int = 3
) -> Tuple[bool, str, Dict[str, Any]]:
    """为单个场景生成对话文本（带角色卡和校验）"""
    try:
        # 构建profile
        profile = build_profile_for_scenario(scenario_setup, scenario_num)
        role_cards = get_role_cards(scenario_num)
        
        print(f"\n{'='*60}")
        print(f"生成场景 {scenario_num} 对话")
        print(f"{'='*60}")
        print(f"场景设置: {scenario_setup[:100]}...")
        print(f"核心内容: {core_content[:100]}...")
        print(f"角色卡: {[f'{r.name}({r.identity})' for r in role_cards]}")
        print(f"参数: people_count={people_count}, target_len={target_len}, language={language}")
        
        # 生成对话（最多重试max_retries次）
        lines = None
        validation_errors = []
        
        for retry in range(max_retries):
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
            
            # 应用角色卡转换
            lines = apply_role_names_to_lines(lines, scenario_num)
            
            # 检查禁止短语
            dialogue_text_check = "\n".join([f"{s}: {t}" for s, t in lines])
            has_forbidden, found_phrases = check_forbidden_phrases(dialogue_text_check, scenario_num)
            if not has_forbidden:
                print(f"[警告] 发现禁止短语: {', '.join(found_phrases[:5])}")
                # 不直接失败，让validator处理
            
            # 校验对话
            is_valid, errors = validate_dialogue_lines(lines, scenario_num, role_cards)
            
            if is_valid:
                print(f"[校验] 场景 {scenario_num} 对话校验通过")
                break
            else:
                validation_errors = errors
                print(f"[校验] 场景 {scenario_num} 对话校验失败（重试 {retry + 1}/{max_retries}）")
                for err in errors[:5]:  # 只显示前5个错误
                    print(f"  - {err.error_type}: {err.message}")
                if retry < max_retries - 1:
                    print(f"[重试] 重新生成...")
        
        # 如果仍然失败，返回错误
        if not is_valid:
            error_msg = f"校验失败: {len(validation_errors)} 个错误"
            return False, error_msg, {"validation_errors": [e.to_dict() for e in validation_errors]}
        
        # 渲染对话文本
        dialogue_text = _render_dialogue_text(lines)
        
        # 保存文本文件
        scenario_name = f"scenario{scenario_num}_dialogue"
        output_file = output_dir / f"{scenario_name}.txt"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(dialogue_text)
        
        # 生成校验报告
        validator_report = {
            "scenario_id": scenario_num,
            "status": "passed",
            "validation_errors": [],
            "role_cards": [r.to_dict() for r in role_cards],
            "lines_count": len(lines),
            "actual_chars": sum(len(text) for _, text in lines),
            "target_len": target_len
        }
        
        report_file = output_dir / f"{scenario_name}_validator_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(validator_report, f, ensure_ascii=False, indent=2)
        
        # 统计信息
        actual_chars = sum(len(text) for _, text in lines)
        speaker_counts = {}
        for speaker, _ in lines:
            # 提取角色名（去掉身份部分）
            name = speaker.split('(')[0] if '(' in speaker else speaker
            speaker_counts[name] = speaker_counts.get(name, 0) + 1
        
        info = {
            "lines_count": len(lines),
            "actual_chars": actual_chars,
            "target_len": target_len,
            "speaker_counts": speaker_counts,
            "rewrite_info": rewrite_info,
            "output_file": str(output_file),
            "validator_report": str(report_file),
            "validation_passed": True
        }
        
        print(f"[SUCCESS] 场景 {scenario_num} 对话生成成功")
        print(f"  对话行数: {len(lines)}")
        print(f"  实际字符数: {actual_chars}")
        print(f"  说话人分布: {speaker_counts}")
        print(f"  输出文件: {output_file}")
        print(f"  校验报告: {report_file}")
        
        return True, "", info
        
    except Exception as e:
        import traceback
        error_msg = f"生成对话失败: {str(e)}"
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        return False, error_msg, {}


def main():
    """主函数：为所有4个场景生成对话并校验"""
    scenarios_file = PROJECT_ROOT / "demo" / "4个独立对话场景 1.txt"
    output_dir = PROJECT_ROOT / "training" / "output"
    
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
    
    # 生成参数（回归测试使用较短长度）
    people_count = 3
    target_len = 1000  # 800-1200范围，先使用1000
    language = "中文"
    
    print(f"\n[参数] 人物数量: {people_count}, 目标字数: {target_len}, 语言: {language}")
    
    # 为每个场景生成对话和校验
    results = []
    
    for scenario in scenarios:
        scenario_num = scenario["num"]
        scenario_setup = scenario["setup"]
        core_content = scenario["core"]
        
        success, error, info = generate_dialogue_for_scenario(
            scenario_num=scenario_num,
            scenario_setup=scenario_setup,
            core_content=core_content,
            output_dir=output_dir,
            people_count=people_count,
            target_len=target_len,
            language=language,
            max_retries=3
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
    validation_passed_count = sum(1 for r in results if r.get("validation_passed", False))
    
    print(f"对话生成成功: {success_count}/{len(scenarios)}")
    print(f"校验通过: {validation_passed_count}/{len(scenarios)}")
    print(f"失败: {len(scenarios) - success_count}/{len(scenarios)}")
    
    for r in results:
        status_icon = "[OK]" if r.get("status") == "success" else "[FAIL]"
        validation_icon = "[✓]" if r.get("validation_passed", False) else "[✗]"
        print(f"{status_icon} {validation_icon} 场景 {r['scenario_num']}")
        if r.get("status") == "success":
            print(f"   对话行数: {r.get('lines_count', 'N/A')}")
            print(f"   实际字符数: {r.get('actual_chars', 'N/A')}")
            print(f"   说话人分布: {r.get('speaker_counts', {})}")
            print(f"   文本文件: {r.get('output_file', 'N/A')}")
            print(f"   校验报告: {r.get('validator_report', 'N/A')}")
        else:
            print(f"   错误: {r.get('error', 'N/A')}")
    
    # 保存汇总报告
    summary_file = output_dir / "regression_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "total_scenarios": len(scenarios),
            "success_count": success_count,
            "validation_passed_count": validation_passed_count,
            "results": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n汇总报告已保存: {summary_file}")
    
    return 0 if success_count == len(scenarios) and validation_passed_count == len(scenarios) else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
