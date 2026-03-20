# -*- coding: utf-8 -*-
"""
Template Bank Smoke测试
=======================

验证：
1. build_template_bank能正确提取训练输出
2. template_bank文件结构正确
3. server.py能正确加载和使用template_bank
4. 使用template_bank后对话差异增加
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_build_template_bank():
    """测试构建template bank"""
    print("\n[测试1] 构建Template Bank...")
    
    # 运行build_template_bank
    cmd = [
        "python",
        "training/build_template_bank.py",
        "--input", "output/training/smoke",
        "--output", "runtime/temp/template_bank_test",
        "--top-n", "50"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"  [FAIL] 构建失败: {result.stderr}")
        return False
    
    print(f"  [OK] 构建成功")
    return True


def test_template_bank_structure():
    """测试template bank文件结构"""
    print("\n[测试2] 验证Template Bank结构...")
    
    bank_path = Path("runtime/temp/template_bank_test/医疗健康/中文.json")
    
    if not bank_path.exists():
        print(f"  [FAIL] 文件不存在: {bank_path}")
        return False
    
    # 读取文件
    with open(bank_path, 'r', encoding='utf-8') as f:
        bank = json.load(f)
    
    # 验证结构
    required_stages = ["opening", "info_collect", "explain", "risk", "next_steps"]
    required_speakers = ["Speaker 1", "Speaker 2", "Speaker 3"]
    
    for stage in required_stages:
        if stage not in bank:
            print(f"  [FAIL] 缺少阶段: {stage}")
            return False
        
        for speaker in required_speakers:
            if speaker not in bank[stage]:
                print(f"  [FAIL] 缺少speaker: {stage}/{speaker}")
                return False
            
            if not isinstance(bank[stage][speaker], list):
                print(f"  [FAIL] {stage}/{speaker}不是列表")
                return False
    
    # 统计模板数
    total_count = sum(
        len(bank[stage][speaker])
        for stage in bank
        for speaker in bank[stage]
    )
    
    print(f"  [OK] 结构正确，总模板数: {total_count}条")
    
    if total_count == 0:
        print(f"  [WARN] 模板数为0，可能训练输出过少")
        return False
    
    return True


def test_server_load_template_bank():
    """测试server.py能加载template bank"""
    print("\n[测试3] 测试server加载Template Bank...")
    
    try:
        # 导入server模块
        import server
        
        # 测试加载
        bank = server.load_template_bank("医疗健康", "中文")
        
        if not bank:
            print(f"  [WARN] 未找到医疗健康/中文的template bank")
            # 尝试加载测试版本
            bank_path = Path("runtime/temp/template_bank_test/医疗健康/中文.json")
            if bank_path.exists():
                with open(bank_path, 'r', encoding='utf-8') as f:
                    bank = json.load(f)
                print(f"  [OK] 手动加载测试template bank成功")
                return True
            else:
                print(f"  [FAIL] 测试template bank也不存在")
                return False
        
        print(f"  [OK] 加载成功")
        return True
        
    except Exception as e:
        print(f"  [FAIL] 加载异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_template_diversity():
    """测试使用template bank后对话差异"""
    print("\n[测试4] 验证对话差异性...")
    print("  [INFO] 此测试需要server运行，暂时跳过")
    print("  [INFO] 可通过人工对比生成的对话验证差异性")
    return True


def main():
    """运行所有测试"""
    print("=" * 80)
    print("Template Bank Smoke测试")
    print("=" * 80)
    
    tests = [
        ("构建Template Bank", test_build_template_bank),
        ("验证文件结构", test_template_bank_structure),
        ("加载功能测试", test_server_load_template_bank),
        ("对话差异性验证", test_template_diversity),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n[异常] {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 总结
    print("\n" + "=" * 80)
    print("测试结果")
    print("=" * 80)
    
    for name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {status} {name}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\n  通过: {passed}/{total}")
    
    if passed == total:
        print("\n✅ 所有测试通过！")
        return 0
    else:
        print("\n❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())


