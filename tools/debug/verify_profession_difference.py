"""
验证职业差异 - P0-1验收脚本

生成同一scenario但不同职业的对话，对比术语差异
"""

import subprocess
import json
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from training.run_training_generation_mvp import generate_for_training


def extract_terms(text: str) -> set:
    """从对话文本中提取关键术语（中文词汇）"""
    # 简单提取：2-4字的中文词
    words = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
    return set(words)


def generate_and_analyze(profession: str, scenario: str, core: str, seed: int = 42) -> dict:
    """生成对话并分析术语"""
    print(f"\n{'='*60}")
    print(f" 生成职业：{profession}")
    print(f"{'='*60}")
    
    # 生成对话
    lines, debug_info = generate_for_training(
        job_function=profession,
        work_content="综合管理",
        seniority="经理",
        scenario=scenario,
        core_content=core,
        language="中文",
        people_count=2,
        word_count=1500,
        seed=seed
    )
    
    # 合并文本
    full_text = "\n".join([f"{speaker}: {text}" for speaker, text in lines])
    
    # 提取术语
    terms = extract_terms(full_text)
    
    # 统计
    total_chars = len(full_text)
    line_count = len(lines)
    
    print(f"\n[生成结果]")
    print(f"  总字数：{total_chars}")
    print(f"  对话行数：{line_count}")
    print(f"  提取术语数：{len(terms)}")
    print(f"  Top 20术语：{list(sorted(terms))[:20]}")
    
    return {
        "profession": profession,
        "lines": lines,
        "text": full_text,
        "terms": terms,
        "total_chars": total_chars,
        "line_count": line_count,
        "debug_info": debug_info
    }


def compare_professions(results: list) -> dict:
    """对比不同职业的术语差异"""
    print(f"\n{'='*60}")
    print(f" 职业差异对比")
    print(f"{'='*60}")
    
    # 计算术语交集和差集
    all_professions = [r["profession"] for r in results]
    all_terms = [r["terms"] for r in results]
    
    # 两两对比
    comparisons = []
    for i in range(len(results)):
        for j in range(i+1, len(results)):
            prof_a = results[i]["profession"]
            prof_b = results[j]["profession"]
            terms_a = results[i]["terms"]
            terms_b = results[j]["terms"]
            
            common = terms_a & terms_b
            unique_a = terms_a - terms_b
            unique_b = terms_b - terms_a
            
            similarity = len(common) / max(len(terms_a), len(terms_b)) if max(len(terms_a), len(terms_b)) > 0 else 0
            
            print(f"\n[{prof_a} vs {prof_b}]")
            print(f"  共同术语数：{len(common)}")
            print(f"  {prof_a}独有：{len(unique_a)} 个，如：{list(unique_a)[:10]}")
            print(f"  {prof_b}独有：{len(unique_b)} 个，如：{list(unique_b)[:10]}")
            print(f"  相似度：{similarity:.1%}")
            
            comparisons.append({
                "prof_a": prof_a,
                "prof_b": prof_b,
                "common": len(common),
                "unique_a": len(unique_a),
                "unique_b": len(unique_b),
                "similarity": similarity
            })
    
    return {
        "professions": all_professions,
        "comparisons": comparisons
    }


def main():
    """运行验证"""
    print("\n" + "="*60)
    print(" P0-1验收：职业差异验证")
    print("="*60)
    
    # 统一场景（去职业化）
    scenario = "两位同事正在讨论一个重要项目的推进情况和资源分配方案"
    core = "项目周期6个月，预算300万元，团队规模15人，需要制定详细的执行计划和风险管理措施"
    
    # 测试3个差异化职业
    professions = [
        "医疗健康",      # 医疗术语
        "人工智能/科技",  # 科技术语
        "零售行业"       # 零售术语
    ]
    
    results = []
    for profession in professions:
        try:
            result = generate_and_analyze(profession, scenario, core, seed=42)
            results.append(result)
        except Exception as e:
            print(f"\n[ERROR] {profession} 生成失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 对比分析
    if len(results) >= 2:
        comparison = compare_professions(results)
        
        # 验收标准
        print(f"\n{'='*60}")
        print(f" 验收标准检查")
        print(f"{'='*60}")
        
        all_passed = True
        
        # 标准1：每个职业术语数>=50（1500字对话）
        for r in results:
            term_count = len(r["terms"])
            passed = term_count >= 50
            status = "[PASS]" if passed else "[FAIL]"
            print(f"{status} {r['profession']}: 术语数={term_count} (目标>=50)")
            if not passed:
                all_passed = False
        
        # 标准2：不同职业相似度<60%（差异明显）
        for comp in comparison["comparisons"]:
            similarity = comp["similarity"]
            passed = similarity < 0.60
            status = "[PASS]" if passed else "[FAIL]"
            print(f"{status} {comp['prof_a']} vs {comp['prof_b']}: 相似度={similarity:.1%} (目标<60%)")
            if not passed:
                all_passed = False
        
        # 标准3：每个职业至少10个独有术语
        for comp in comparison["comparisons"]:
            unique_a = comp["unique_a"]
            unique_b = comp["unique_b"]
            passed_a = unique_a >= 10
            passed_b = unique_b >= 10
            status_a = "[PASS]" if passed_a else "[FAIL]"
            status_b = "[PASS]" if passed_b else "[FAIL]"
            print(f"{status_a} {comp['prof_a']}独有术语: {unique_a} (目标>=10)")
            print(f"{status_b} {comp['prof_b']}独有术语: {unique_b} (目标>=10)")
            if not (passed_a and passed_b):
                all_passed = False
        
        print(f"\n{'='*60}")
        if all_passed:
            print(" ✅ 所有验收标准通过！职业差异显著")
        else:
            print(" ❌ 部分验收标准未通过，需进一步优化")
        print("="*60)
        
        return 0 if all_passed else 1
    else:
        print("\n[ERROR] 生成的职业数量不足，无法对比")
        return 1


if __name__ == "__main__":
    sys.exit(main())

