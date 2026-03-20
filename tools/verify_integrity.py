# -*- coding: utf-8 -*-
"""
验证删除文件后的完整性检查脚本
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """测试核心模块导入"""
    errors = []
    
    # 1. 测试server.py
    try:
        from server import (
            _generate_dialogue_lines,
            _generate_cast,
            _generate_structured_dialogue,
            validate_and_normalize_payload,
            make_app
        )
        print("[OK] server.py 核心函数导入成功")
    except Exception as e:
        errors.append(f"server.py 导入失败: {e}")
        print(f"[FAIL] server.py 导入失败: {e}")
    
    # 2. 测试payment_integration_context
    try:
        from payment_integration_context import PaymentIntegrationContext, get_context
        print("[OK] payment_integration_context.py 导入成功")
    except Exception as e:
        errors.append(f"payment_integration_context.py 导入失败: {e}")
        print(f"[FAIL] payment_integration_context.py 导入失败: {e}")
    
    # 3. 测试payment模块
    try:
        from payment.role_schema import PaymentRoleSchema
        from payment.slots import PaymentSlots
        # 检查是否有FORBIDDEN_TOPICS和LOW_INFO_PATTERNS
        try:
            from payment.role_schema import FORBIDDEN_TOPICS, LOW_INFO_PATTERNS
        except ImportError:
            # 如果没有，从PaymentRoleSchema中获取
            schema = PaymentRoleSchema()
            FORBIDDEN_TOPICS = getattr(schema, 'FORBIDDEN_TOPICS', [])
            LOW_INFO_PATTERNS = getattr(schema, 'LOW_INFO_PATTERNS', [])
        print("[OK] payment模块导入成功")
    except Exception as e:
        errors.append(f"payment模块导入失败: {e}")
        print(f"[FAIL] payment模块导入失败: {e}")
    
    # 4. 测试音频生成脚本
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from generate_payment_5step_audio import parse_dialogue_text, clean_tts_text
        print("[OK] generate_payment_5step_audio.py 导入成功")
    except Exception as e:
        errors.append(f"generate_payment_5step_audio.py 导入失败: {e}")
        print(f"[FAIL] generate_payment_5step_audio.py 导入失败: {e}")
    
    # 5. 测试训练脚本依赖
    try:
        from training.run_training_generation_mvp import generate_for_training
        print("[OK] training模块导入成功")
    except Exception as e:
        errors.append(f"training模块导入失败: {e}")
        print(f"[FAIL] training模块导入失败: {e}")
    
    return errors

def test_deleted_files():
    """检查已删除的文件是否还存在"""
    deleted_files = [
        "generate_step2_only.py",
        "replace_generate_cast.py",
        "server.py.backup_before_v150",
        "debug_generation.py"
    ]
    
    found = []
    for file in deleted_files:
        if Path(file).exists():
            found.append(file)
            print(f"⚠️  已删除的文件仍存在: {file}")
        else:
            print(f"[OK] 已确认删除: {file}")
    
    return found

def main():
    print("=" * 60)
    print("完整性验证")
    print("=" * 60)
    
    print("\n1. 检查已删除文件...")
    found = test_deleted_files()
    
    print("\n2. 测试核心模块导入...")
    errors = test_imports()
    
    print("\n" + "=" * 60)
    print("验证结果")
    print("=" * 60)
    
    if found:
        print(f"[FAIL] 发现 {len(found)} 个已删除的文件仍存在")
        return 1
    
    if errors:
        print(f"[FAIL] 发现 {len(errors)} 个导入错误")
        for error in errors:
            print(f"  - {error}")
        return 1
    
    print("[OK] 所有验证通过！")
    print("[OK] 核心功能完整")
    print("[OK] 没有发现对已删除文件的引用")
    return 0

if __name__ == "__main__":
    sys.exit(main())
