# -*- coding: utf-8 -*-
"""
不同职业情景设置 - 快速回归测试
====================================

只测试2个职业×2种语言，用于快速验证
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.run_role_scenario_smoke import (
    parse_profession_document,
    build_test_jobs,
    run_batch_generation
)


def test_role_scenario_smoke():
    """快速回归测试：只测试2个职业"""
    print("="*80)
    print("不同职业情景设置 - 快速回归测试")
    print("="*80)
    
    # 1. 解析文档
    doc_path = PROJECT_ROOT / "demo" / "不同职业情景设置 1.txt"
    assert doc_path.exists(), f"文档不存在: {doc_path}"
    
    professions = parse_profession_document(doc_path)
    assert len(professions) >= 2, "至少需要2个职业数据"
    
    # 2. 只取前2个职业
    test_professions = professions[:2]
    print(f"\n[测试] 选择职业: {[p['profession'] for p in test_professions]}")
    
    # 3. 构建测试任务（2个职业×2种语言=4个任务）
    jobs = build_test_jobs(test_professions)
    assert len(jobs) == 4, f"应该生成4个任务，实际生成{len(jobs)}个"
    
    # 4. 批量生成
    results = run_batch_generation(jobs)
    
    # 5. 断言
    assert len(results) == 4, f"应该有4个结果，实际{len(results)}个"
    
    # 断言所有任务都能落盘（即使校验失败）
    for result in results:
        assert result["output_path"] is not None or "生成失败" in str(result["errors"]), \
            f"{result['profession']} ({result['language']}) 未生成输出文件"
    
    # 断言无占位符泄露
    for result in results:
        has_placeholder_leak = any("占位符" in str(e) for e in result["errors"])
        assert not has_placeholder_leak, \
            f"{result['profession']} ({result['language']}) 存在占位符泄露"
    
    # 统计通过情况
    passed_count = sum(1 for r in results if r["passed"])
    print(f"\n[结果] 通过: {passed_count}/4")
    
    print("="*80)
    print("✅ 快速回归测试完成")
    print("="*80)


if __name__ == "__main__":
    test_role_scenario_smoke()
