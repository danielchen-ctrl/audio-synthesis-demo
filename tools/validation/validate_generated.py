"""快速验证已生成的训练数据质量"""
import json
import re
from pathlib import Path
from collections import Counter

def validate_generated_data(output_dir="output/training/full", sample_size=100):
    """验证已生成的训练数据"""
    
    output_path = Path(output_dir)
    
    # 收集所有txt和meta文件
    txt_files = list(output_path.rglob("*.txt"))
    meta_files = list(output_path.rglob("*.meta.json"))
    
    print(f"=== 训练数据验证报告 ===")
    print(f"txt文件数: {len(txt_files)}")
    print(f"meta.json文件数: {len(meta_files)}")
    print()
    
    # 抽样验证
    import random
    random.seed(42)
    sample_files = random.sample(txt_files, min(sample_size, len(txt_files)))
    
    print(f"抽样验证: {len(sample_files)}个文件")
    print()
    
    issues = {
        "no_core_marker": [],
        "duplicate_core": [],
        "placeholder_found": [],
        "chinese_ratio_high": [],
        "missing_meta": [],
        "meta_error": []
    }
    
    for txt_file in sample_files:
        # 读取txt
        content = txt_file.read_text(encoding='utf-8')
        
        # 1. 核心标记检查
        core_markers_cn = re.findall(r'<<核心:.*?>>', content)
        core_markers_en = re.findall(r'<<Core:.*?>>', content)
        core_markers_ja = re.findall(r'<<コア:.*?>>', content)
        core_markers_fr = re.findall(r'<<Noyau:.*?>>', content)
        core_markers_ko = re.findall(r'<<핵심:.*?>>', content)
        
        all_markers = core_markers_cn + core_markers_en + core_markers_ja + core_markers_fr + core_markers_ko
        
        if len(all_markers) == 0:
            issues["no_core_marker"].append(txt_file.name)
        elif len(all_markers) > 2:
            issues["duplicate_core"].append(txt_file.name)
        
        # 2. 占位符残留
        if "[[[CORE" in content:
            issues["placeholder_found"].append(txt_file.name)
        
        # 3. 检查meta文件
        meta_file = txt_file.with_suffix('.meta.json')
        if not meta_file.exists():
            issues["missing_meta"].append(txt_file.name)
            continue
        
        try:
            meta = json.loads(meta_file.read_text(encoding='utf-8'))
            
            # 4. 中文占比检查（非中文语言）
            if meta.get("language") != "中文":
                chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', content))
                total_chars = len(content)
                chinese_ratio = chinese_chars / total_chars if total_chars > 0 else 0
                
                # 使用80%阈值（比生成时的70%更宽松）
                if chinese_ratio > 0.80:
                    issues["chinese_ratio_high"].append(f"{txt_file.name} ({chinese_ratio:.1%})")
        
        except Exception as e:
            issues["meta_error"].append(f"{txt_file.name}: {str(e)}")
    
    # 打印结果
    print("=" * 60)
    print("验证结果:")
    print()
    
    total_issues = sum(len(v) for v in issues.values())
    
    if total_issues == 0:
        print("[OK] 所有抽样文件验证通过！")
    else:
        print(f"[WARNING] 发现 {total_issues} 个问题:")
        print()
        
        if issues["no_core_marker"]:
            print(f"  缺少核心标记: {len(issues['no_core_marker'])}个")
            for name in issues["no_core_marker"][:5]:
                print(f"    - {name}")
            if len(issues["no_core_marker"]) > 5:
                print(f"    ... 还有 {len(issues['no_core_marker'])-5} 个")
        
        if issues["duplicate_core"]:
            print(f"  核心标记重复: {len(issues['duplicate_core'])}个")
            for name in issues["duplicate_core"][:5]:
                print(f"    - {name}")
        
        if issues["placeholder_found"]:
            print(f"  占位符残留: {len(issues['placeholder_found'])}个")
            for name in issues["placeholder_found"][:5]:
                print(f"    - {name}")
        
        if issues["chinese_ratio_high"]:
            print(f"  中文占比过高: {len(issues['chinese_ratio_high'])}个")
            for name in issues["chinese_ratio_high"][:5]:
                print(f"    - {name}")
        
        if issues["missing_meta"]:
            print(f"  缺少meta文件: {len(issues['missing_meta'])}个")
        
        if issues["meta_error"]:
            print(f"  meta读取错误: {len(issues['meta_error'])}个")
    
    print()
    print("=" * 60)
    
    # 统计分布
    print("\n按语言统计:")
    lang_counter = Counter()
    for meta_file in meta_files[:1000]:  # 统计前1000个
        try:
            meta = json.loads(meta_file.read_text(encoding='utf-8'))
            lang_counter[meta.get("language", "未知")] += 1
        except:
            pass
    
    for lang, count in sorted(lang_counter.items()):
        print(f"  {lang}: {count}个")
    
    print()
    success_rate = (len(sample_files) - total_issues) / len(sample_files) * 100
    print(f"抽样通过率: {success_rate:.1f}%")
    
    return total_issues == 0

if __name__ == "__main__":
    success = validate_generated_data()
    exit(0 if success else 1)

