# -*- coding: utf-8 -*-
"""
场景对话回归测试脚本
为4个独立场景生成对话，复用统一评分与统一索引
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from training.dialogue_validators import validate_dialogue_lines
from training.quality_scoring import score_dialogue
from training.role_cards import get_role_cards
from training.scene_dialogue_enhancer import apply_role_names_to_lines, check_forbidden_phrases
from training.training_storage import TrainingStorage
from training.training_types import ExecutionResult, TrainingTask

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

server_path = PROJECT_ROOT / "server.py"
spec = importlib.util.spec_from_file_location("server", server_path)
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)

_generate_dialogue_lines = server_module._generate_dialogue_lines


def parse_scenarios_file(file_path: Path) -> List[Dict[str, Any]]:
    import re

    content = file_path.read_text(encoding="utf-8")
    scenarios = []
    pattern = r"（(\d+)）\*\*场景对话设置：\*\*\s*(.*?)\*\*对话核心内容（红色标注）：\*\*\s*(.*?)(?=（\d+）\*\*场景对话设置：|$)"
    matches = re.finditer(pattern, content, re.DOTALL)
    for match in matches:
        scenarios.append({"num": match.group(1), "setup": match.group(2).strip(), "core": match.group(3).strip()})
    return scenarios


def build_profile_for_scenario(scenario_num: str) -> Dict[str, str]:
    mapping = {
        "1": {"job_function": "企业管理", "work_content": "战略规划", "seniority": "公司高层", "use_case": "会议记录"},
        "2": {"job_function": "风控", "work_content": "风险控制", "seniority": "部门负责人", "use_case": "风险评估"},
        "3": {"job_function": "销售", "work_content": "保险销售", "seniority": "业务骨干", "use_case": "客户沟通"},
        "4": {"job_function": "医疗", "work_content": "心理咨询", "seniority": "专业技术人员", "use_case": "专业咨询"},
    }
    return mapping.get(scenario_num, {"job_function": "其他", "work_content": "其他", "seniority": "其他", "use_case": "其他"})


def build_scene_task(scenario_num: str, scenario_setup: str, core_content: str, people_count: int, target_len: int, language: str) -> TrainingTask:
    return TrainingTask(
        task_id=f"scene-{scenario_num}-{people_count}-{target_len}-{language}",
        stage="scene_regression",
        profile=build_profile_for_scenario(scenario_num),
        scenario=scenario_setup,
        core_content=core_content,
        language=language,
        people_count=people_count,
        word_count=target_len,
        seed=1000 + int(scenario_num),
        meta={"scenario_id": scenario_num, "scene_id": scenario_num},
        source_format="scene_regression",
    )


def generate_dialogue_for_scenario(
    scenario_num: str,
    scenario_setup: str,
    core_content: str,
    storage: TrainingStorage,
    people_count: int = 3,
    target_len: int = 1000,
    language: str = "中文",
    max_retries: int = 3,
) -> Tuple[bool, str, Dict[str, Any]]:
    task = build_scene_task(scenario_num, scenario_setup, core_content, people_count, target_len, language)
    role_cards = get_role_cards(scenario_num)
    validation_errors = []
    lines = None
    rewrite_info: Dict[str, Any] = {}

    for retry in range(max_retries):
        lines, rewrite_info = _generate_dialogue_lines(
            profile=task.profile,
            scenario=scenario_setup,
            core=core_content,
            people=people_count,
            target_len=target_len,
            language=language,
        )
        if not lines:
            return False, "未生成任何对话内容", {}

        lines = apply_role_names_to_lines(lines, scenario_num)
        prompt_ok, found_phrases = check_forbidden_phrases("\n".join([f"{s}: {t}" for s, t in lines]), scenario_num)
        is_valid, validation_errors = validate_dialogue_lines(lines, scenario_num, role_cards)
        if is_valid and prompt_ok:
            break
        if retry == max_retries - 1:
            break

    if lines is None:
        return False, "未生成任何对话内容", {}

    score_report = score_dialogue(task, lines, validator_errors=validation_errors)
    debug_info = {
        "scene_type": f"scene_{scenario_num}",
        "line_count": len(lines),
        "total_chars": sum(len(text) for _, text in lines),
        "rewrite_info": rewrite_info,
    }
    result = ExecutionResult(task=task, lines=lines, debug_info=debug_info, score_report=score_report)
    result.output_paths = storage.save_result(result, keep_failed_sample=True)

    summary = {
        "lines_count": len(lines),
        "actual_chars": sum(len(text) for _, text in lines),
        "speaker_counts": {},
        "rewrite_info": rewrite_info,
        "validation_passed": score_report.passed,
        "score": score_report.score,
        **result.output_paths,
    }
    for speaker, _ in lines:
        name = speaker.split("(")[0] if "(" in speaker else speaker
        summary["speaker_counts"][name] = summary["speaker_counts"].get(name, 0) + 1

    if not score_report.passed:
        return False, "; ".join(f.message for f in score_report.findings), summary
    return True, "", summary


def main() -> int:
    scenarios_file = PROJECT_ROOT / "demo" / "4个独立对话场景 1.txt"
    storage = TrainingStorage(base_dir="output/training/unified")
    if not scenarios_file.exists():
        print(f"[ERROR] 场景文件不存在: {scenarios_file}")
        return 1

    scenarios = parse_scenarios_file(scenarios_file)
    if not scenarios:
        print("[ERROR] 未解析到任何场景")
        return 1

    results = []
    for scenario in scenarios:
        success, error, info = generate_dialogue_for_scenario(
            scenario_num=scenario["num"],
            scenario_setup=scenario["setup"],
            core_content=scenario["core"],
            storage=storage,
            people_count=3,
            target_len=1000,
            language="中文",
            max_retries=3,
        )
        results.append({"scenario_num": scenario["num"], "status": "success" if success else "failed", "error": error, **info})

    success_count = sum(1 for r in results if r.get("status") == "success")
    validation_passed_count = sum(1 for r in results if r.get("validation_passed", False))
    summary_file = storage.base_dir / "scene_regression_summary.json"
    summary_file.write_text(
        json.dumps(
            {
                "total_scenarios": len(scenarios),
                "success_count": success_count,
                "validation_passed_count": validation_passed_count,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"场景回归完成: success={success_count}/{len(scenarios)} validation={validation_passed_count}/{len(scenarios)}")
    print(f"统一汇总: {summary_file}")
    return 0 if success_count == len(scenarios) and validation_passed_count == len(scenarios) else 1


if __name__ == "__main__":
    sys.exit(main())
