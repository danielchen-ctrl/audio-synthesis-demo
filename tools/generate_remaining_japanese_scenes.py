#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
继续生成剩余的日语场景（6-13）
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入主脚本的函数
from tools.batch_generate_13_professions_japanese import (
    parse_input_file,
    process_one_job_ja,
    INPUT_FILE,
    OUTPUT_DIR
)

def main():
    """生成剩余场景"""
    print("="*80)
    print("継続生成：残りの日本語シーン（6-13）")
    print("="*80)
    
    # 解析输入文件
    jobs = parse_input_file(INPUT_FILE)
    
    # 只处理场景6-13（索引6-13）
    remaining_jobs = [job for job in jobs if job["index"] >= 6]
    
    print(f"\n処理対象: {len(remaining_jobs)} 個のシーン")
    
    results = []
    for job in remaining_jobs:
        result = process_one_job_ja(job, OUTPUT_DIR)
        results.append(result)
        
        # 每生成一个场景后暂停3秒，避免API限流
        if result.get('success'):
            import time
            time.sleep(3)
    
    # 输出摘要
    print("\n" + "="*80)
    print("✅ 残りのシーン生成完了！")
    print("="*80)
    
    success_count = sum(1 for r in results if r.get('success', False))
    print(f"成功: {success_count}/{len(results)}")
    
    for result in results:
        if result.get('success'):
            print(f"  ✅ 場面{result['index']} - {result['profession']}")
        else:
            print(f"  ❌ 場面{result['index']} - {result['profession']}: {result.get('error', 'Unknown')}")

if __name__ == "__main__":
    main()
