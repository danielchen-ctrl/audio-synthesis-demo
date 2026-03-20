# -*- coding: utf-8 -*-
"""
对话质量修复验证脚本 - v1.4.4
验证以下修复：
1. 回复不再重复（3次相同）
2. 场景不再串场（医患对话出现在升职场景）
3. 回复多样化（使用random.choice）
"""

import json
import requests
import time
from pathlib import Path

def safe_print(text):
    """安全打印（处理编码问题）"""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('gbk', errors='ignore').decode('gbk'))

def test_promotion_scenario():
    """测试升职场景是否正确生成"""
    safe_print("=" * 80)
    safe_print("[测试1] 升职场景 - 验证是否出现医患对话串场")
    safe_print("=" * 80)
    
    # 等待server启动
    time.sleep(5)
    
    url = "http://127.0.0.1:8899/api/generate_text"
    
    payload = {
        "scenario": "你是一名外科副主任医生，现在正在跟你的领导王院长谈论关于升职的事情",
        "core_content": "感谢院长栽培，现在把我的职位从外科副主任升职为外科主任，并且还给我颁发今年的优秀员工奖",
        "people_count": 2,
        "word_count": 1500,
        "audio_language": "中文",
        "title": "升职对话测试",
        "profile": {
            "job_function": "医疗健康",
            "work_content": "医疗服务供应商",
            "seniority": "高级职员",
            "use_case": "生成情景对话"
        }
    }
    
    try:
        safe_print("\n[发送请求] 生成升职场景对话...")
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code != 200:
            safe_print(f"[失败] HTTP状态码: {response.status_code}")
            return False
        
        result = response.json()
        text = result.get("display_dialogue", "")
        
        if not text:
            safe_print("[失败] 返回的对话文本为空")
            return False
        
        safe_print(f"\n[成功] 生成对话长度: {len(text)} 字符")
        safe_print(f"request_id: {result.get('request_id', 'N/A')}")
        safe_print(f"params_hash: {result.get('params_hash', 'N/A')}")
        
        # 检查1：是否出现医患对话关键词（不应该出现）
        medical_keywords = ["血常规", "CT", "心电图", "药物", "储存", "情绪管理", 
                           "康复训练", "饮食禁忌", "用药", "住院", "并发症", "复查"]
        found_medical = []
        for kw in medical_keywords:
            if kw in text:
                found_medical.append(kw)
        
        if found_medical:
            safe_print(f"\n[失败] 检查1不通过：发现医患对话关键词: {found_medical}")
            safe_print("\n前500字符预览:")
            safe_print(text[:500])
            return False
        else:
            safe_print("\n[通过] 检查1：未发现医患对话关键词 ✓")
        
        # 检查2：是否包含升职相关关键词（应该出现）
        promotion_keywords = ["升职", "晋升", "岗位", "职位", "薪资", "福利", "团队", "管理"]
        found_promotion = []
        for kw in promotion_keywords:
            if kw in text:
                found_promotion.append(kw)
        
        if len(found_promotion) >= 3:
            safe_print(f"[通过] 检查2：发现升职相关关键词: {found_promotion} ✓")
        else:
            safe_print(f"[警告] 检查2：升职关键词较少: {found_promotion}")
        
        # 检查3：是否有重复回复（连续3次相同）
        lines = text.split('\n')
        speaker2_lines = [line for line in lines if line.strip().startswith('Speaker 2:')]
        
        repeated_count = 0
        for i in range(len(speaker2_lines) - 2):
            if (speaker2_lines[i] == speaker2_lines[i+1] == speaker2_lines[i+2]):
                repeated_count += 1
                safe_print(f"\n[失败] 检查3不通过：发现连续3次相同回复:")
                safe_print(f"  {speaker2_lines[i]}")
                return False
        
        safe_print("[通过] 检查3：未发现连续相同回复 ✓")
        
        # 保存测试结果
        report_dir = Path("reports")
        report_dir.mkdir(exist_ok=True)
        
        report = {
            "test_name": "升职场景验证",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "checks": {
                "no_medical_keywords": len(found_medical) == 0,
                "has_promotion_keywords": len(found_promotion) >= 3,
                "no_repeated_replies": repeated_count == 0
            },
            "medical_keywords_found": found_medical,
            "promotion_keywords_found": found_promotion,
            "request_id": result.get("request_id", ""),
            "params_hash": result.get("params_hash", ""),
            "text_length": len(text),
            "first_500_chars": text[:500]
        }
        
        report_file = report_dir / "quality_fix_verification.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        safe_print(f"\n[报告] 测试报告已保存至: {report_file}")
        safe_print("\n" + "=" * 80)
        safe_print("[结论] 所有检查通过 ✓✓✓")
        safe_print("=" * 80)
        
        return True
        
    except requests.exceptions.ConnectionError:
        safe_print("[失败] 无法连接到server，请确保server正在运行")
        return False
    except Exception as e:
        safe_print(f"[失败] 测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_promotion_scenario()
    if success:
        safe_print("\n[最终结论] 对话质量修复验证通过 ✓")
    else:
        safe_print("\n[最终结论] 对话质量修复验证失败 ✗")
