"""
Domain KB 完整性测试

验证13个职业知识库JSON文件：
- 文件存在性
- 字段完整性
- 字段长度达标
"""

import json
import os
import sys
from pathlib import Path

# 添加父目录到path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDomainKBIntegrity:
    """Domain KB完整性测试"""
    
    # 13个职业对应的JSON文件名
    DOMAIN_FILES = [
        "medical.json",
        "hr_recruiting.json",
        "ai_tech.json",
        "consulting_professional.json",
        "legal.json",
        "finance.json",
        "entertainment_media.json",
        "construction_engineering.json",
        "automotive.json",
        "retail.json",
        "insurance.json",
        "real_estate.json",
        "manufacturing.json",
        "generic.json"  # 通用fallback
    ]
    
    # 字段要求（最小长度）
    FIELD_REQUIREMENTS = {
        "terms": 25,
        "deliverables": 10,
        "metrics": 10,
        "process_steps": 8,
        "risks": 8,
        "common_questions": 10,
        "example_facts": 15
    }
    
    def test_01_all_files_exist(self):
        """测试：所有JSON文件存在"""
        print("\n[Domain KB完整性] 步骤1：检查文件存在性...")
        
        missing_files = []
        for filename in self.DOMAIN_FILES:
            filepath = Path("domain_kb") / filename
            if not filepath.exists():
                missing_files.append(filename)
                print(f"[FAIL] 缺失文件: {filename}")
            else:
                print(f"[OK] 文件存在: {filename}")
        
        assert len(missing_files) == 0, \
            f"缺失{len(missing_files)}个domain_kb文件: {missing_files}"
        
        print(f"\n[PASS] 所有{len(self.DOMAIN_FILES)}个JSON文件存在")
    
    def test_02_fields_complete(self):
        """测试：所有文件字段完整"""
        print("\n[Domain KB完整性] 步骤2：检查字段完整性...")
        
        required_fields = list(self.FIELD_REQUIREMENTS.keys()) + ["domain", "display_name"]
        incomplete_files = []
        
        for filename in self.DOMAIN_FILES:
            filepath = Path("domain_kb") / filename
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    kb = json.load(f)
                
                missing_fields = []
                for field in required_fields:
                    if field not in kb:
                        missing_fields.append(field)
                
                if missing_fields:
                    incomplete_files.append((filename, missing_fields))
                    print(f"[FAIL] {filename} 缺失字段: {missing_fields}")
                else:
                    print(f"[OK] {filename} 字段完整")
                
            except Exception as e:
                print(f"[ERROR] {filename} 读取失败: {e}")
                incomplete_files.append((filename, ["读取失败"]))
        
        assert len(incomplete_files) == 0, \
            f"{len(incomplete_files)}个文件字段不完整: {incomplete_files}"
        
        print(f"\n[PASS] 所有文件字段完整")
    
    def test_03_field_length_sufficient(self):
        """测试：字段长度达标"""
        print("\n[Domain KB完整性] 步骤3：检查字段长度...")
        
        insufficient_files = []
        
        for filename in self.DOMAIN_FILES:
            filepath = Path("domain_kb") / filename
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    kb = json.load(f)
                
                insufficient_fields = []
                for field, min_len in self.FIELD_REQUIREMENTS.items():
                    if field in kb:
                        actual_len = len(kb[field]) if isinstance(kb[field], list) else 0
                        if actual_len < min_len:
                            insufficient_fields.append(f"{field}({actual_len}<{min_len})")
                
                if insufficient_fields:
                    insufficient_files.append((filename, insufficient_fields))
                    print(f"[FAIL] {filename} 长度不足: {insufficient_fields}")
                else:
                    # 打印实际长度
                    lengths = {f: len(kb[f]) for f in self.FIELD_REQUIREMENTS.keys() if f in kb}
                    print(f"[OK] {filename}: {lengths}")
            
            except Exception as e:
                print(f"[ERROR] {filename} 读取失败: {e}")
                insufficient_files.append((filename, ["读取失败"]))
        
        assert len(insufficient_files) == 0, \
            f"{len(insufficient_files)}个文件字段长度不足: {insufficient_files}"
        
        print(f"\n[PASS] 所有文件字段长度达标")
    
    def test_04_content_quality(self):
        """测试：内容质量抽查"""
        print("\n[Domain KB完整性] 步骤4：内容质量抽查...")
        
        quality_issues = []
        
        for filename in self.DOMAIN_FILES:
            filepath = Path("domain_kb") / filename
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    kb = json.load(f)
                
                # 检查example_facts是否包含数字（信息密度）
                facts = kb.get("example_facts", [])
                facts_with_numbers = [f for f in facts if any(c.isdigit() for c in f)]
                
                if len(facts_with_numbers) < len(facts) * 0.8:  # 至少80%包含数字
                    quality_issues.append((
                        filename, 
                        f"example_facts中包含数字的比例过低: {len(facts_with_numbers)}/{len(facts)}"
                    ))
                    print(f"[WARN] {filename}: example_facts数字比例 {len(facts_with_numbers)}/{len(facts)}")
                else:
                    print(f"[OK] {filename}: example_facts数字比例 {len(facts_with_numbers)}/{len(facts)}")
            
            except Exception as e:
                print(f"[ERROR] {filename} 读取失败: {e}")
        
        # 质量问题不阻塞，只warning
        if quality_issues:
            print(f"\n[WARN] {len(quality_issues)}个文件有质量建议：")
            for filename, issue in quality_issues:
                print(f"  - {filename}: {issue}")
        else:
            print(f"\n[PASS] 所有文件内容质量良好")
    
    def test_05_load_all_domains(self):
        """测试：通过server.py加载所有domain_kb"""
        print("\n[Domain KB完整性] 步骤5：测试server.py加载...")
        
        try:
            from server import load_domain_kb
            
            # 13个职业名称（中文）
            professions = [
                "医疗健康", "人力资源与招聘", "人工智能/科技", "咨询/专业服务",
                "法律服务", "金融/投资", "娱乐/媒体", "建筑与工程行业",
                "汽车行业", "零售行业", "保险行业", "房地产", "制造业"
            ]
            
            load_errors = []
            
            for profession in professions:
                try:
                    kb = load_domain_kb(profession)
                    
                    # 验证返回的是dict且包含必要字段
                    assert isinstance(kb, dict), f"{profession}: 返回类型错误"
                    assert "terms" in kb, f"{profession}: 缺少terms字段"
                    assert len(kb["terms"]) > 0, f"{profession}: terms为空"
                    
                    print(f"[OK] {profession}: 加载成功，terms数量={len(kb['terms'])}")
                
                except Exception as e:
                    load_errors.append((profession, str(e)))
                    print(f"[FAIL] {profession}: 加载失败 - {e}")
            
            assert len(load_errors) == 0, \
                f"{len(load_errors)}个职业加载失败: {load_errors}"
            
            print(f"\n[PASS] 所有{len(professions)}个职业加载成功")
        
        except ImportError as e:
            print(f"[ERROR] 无法导入server.py: {e}")
            raise


def main():
    """Standalone运行模式"""
    print("\n" + "="*60)
    print(" Domain KB 完整性测试")
    print("="*60 + "\n")
    
    test_suite = TestDomainKBIntegrity()
    
    tests = [
        ("步骤1: 检查文件存在性", test_suite.test_01_all_files_exist),
        ("步骤2: 检查字段完整性", test_suite.test_02_fields_complete),
        ("步骤3: 检查字段长度", test_suite.test_03_field_length_sufficient),
        ("步骤4: 内容质量抽查", test_suite.test_04_content_quality),
        ("步骤5: server.py加载测试", test_suite.test_05_load_all_domains),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            print(f"\n{'='*60}")
            print(f" {name}")
            print(f"{'='*60}")
            test_func()
            passed += 1
            print(f"\n[PASS] {name} 通过")
        except Exception as e:
            failed += 1
            print(f"\n[FAIL] {name} 失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print(f" 测试结果: {passed} 通过, {failed} 失败")
    print("="*60)
    
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    try:
        import pytest
        pytest.main([__file__, "-v", "-s"])
    except ImportError:
        main()
