# -*- coding: utf-8 -*-
"""
多语言核心内容标记测试 - P0-1
验证：
1. 英语/日语输出必须包含核心标记
2. 核心内容不能为空
3. 中文占比 < 10%
"""

import json
import requests
import re
import time

def safe_print(text):
    """安全打印（处理编码问题）"""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('gbk', errors='ignore').decode('gbk'))

def calculate_chinese_ratio(text):
    """计算中文占比"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(text)
    return chinese_chars / total_chars if total_chars > 0 else 0

def test_core_marker_english():
    """测试英语输出的核心标记"""
    safe_print("=" * 80)
    safe_print("[测试1] 英语输出 - 核心内容标记验证")
    safe_print("=" * 80)
    
    url = "http://127.0.0.1:8899/api/generate_text"
    
    payload = {
        "scenario": "你是一名外科副主任医生，现在正在跟你的领导王院长谈论关于升职的事情",
        "core_content": "感谢院长栽培，现在把我的职位从外科副主任升职为外科主任，并且还给我颁发今年的优秀员工奖",
        "people_count": 2,
        "word_count": 500,
        "audio_language": "英语",
        "title": "英语核心标记测试",
        "profile": {
            "job_function": "医疗健康",
            "work_content": "医疗服务供应商",
            "seniority": "高级职员",
            "use_case": "生成情景对话"
        }
    }
    
    try:
        safe_print("\n[发送请求] 生成英语对话...")
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
        
        # 检查1：必须包含 <<Core:...>>
        core_pattern = r'<<Core:(.*?)>>'
        matches = re.findall(core_pattern, text)
        
        if not matches:
            safe_print("[失败] 检查1不通过：未找到 <<Core:...>> 标记")
            safe_print("\n前500字符预览:")
            safe_print(text[:500])
            return False
        else:
            safe_print(f"[通过] 检查1：找到 {len(matches)} 个核心标记 ✓")
        
        # 检查2：核心内容不能为空
        empty_cores = [m for m in matches if not m.strip()]
        if empty_cores:
            safe_print(f"[失败] 检查2不通过：发现 {len(empty_cores)} 个空核心内容")
            return False
        else:
            safe_print("[通过] 检查2：所有核心内容非空 ✓")
            safe_print(f"  核心内容示例: {matches[0][:80]}...")
        
        # 检查3：中文占比 < 10%
        chinese_ratio = calculate_chinese_ratio(text)
        if chinese_ratio >= 0.1:
            safe_print(f"[失败] 检查3不通过：中文占比 {chinese_ratio*100:.2f}% >= 10%")
            return False
        else:
            safe_print(f"[通过] 检查3：中文占比 {chinese_ratio*100:.2f}% < 10% ✓")
        
        safe_print("\n" + "=" * 80)
        safe_print("[结论] 英语核心标记测试通过 ✓✓✓")
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

def test_core_marker_japanese():
    """测试日语输出的核心标记"""
    safe_print("\n" + "=" * 80)
    safe_print("[测试2] 日语输出 - 核心内容标记验证")
    safe_print("=" * 80)
    
    url = "http://127.0.0.1:8899/api/generate_text"
    
    payload = {
        "scenario": "你是一名外科副主任医生，现在正在跟你的领导王院长谈论关于升职的事情",
        "core_content": "感谢院长栽培，现在把我的职位从外科副主任升职为外科主任",
        "people_count": 2,
        "word_count": 500,
        "audio_language": "日语",
        "title": "日语核心标记测试",
        "profile": {
            "job_function": "医疗健康",
            "work_content": "医疗服务供应商",
            "seniority": "高级职员",
            "use_case": "生成情景对话"
        }
    }
    
    try:
        safe_print("\n[发送请求] 生成日语对话...")
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
        
        # 检查1：必须包含 <<コア:...>>
        core_pattern = r'<<コア:(.*?)>>'
        matches = re.findall(core_pattern, text)
        
        if not matches:
            safe_print("[失败] 检查1不通过：未找到 <<コア:...>> 标记")
            safe_print("\n前500字符预览:")
            safe_print(text[:500])
            return False
        else:
            safe_print(f"[通过] 检查1：找到 {len(matches)} 个核心标记 ✓")
        
        # 检查2：核心内容不能为空
        empty_cores = [m for m in matches if not m.strip()]
        if empty_cores:
            safe_print(f"[失败] 检查2不通过：发现 {len(empty_cores)} 个空核心内容")
            return False
        else:
            safe_print("[通过] 检查2：所有核心内容非空 ✓")
            safe_print(f"  核心内容示例: {matches[0][:80]}...")
        
        # 检查3：中文占比 < 10%（日语中会有汉字，标准放宽到15%）
        chinese_ratio = calculate_chinese_ratio(text)
        if chinese_ratio >= 0.15:
            safe_print(f"[失败] 检查3不通过：中文/汉字占比 {chinese_ratio*100:.2f}% >= 15%")
            return False
        else:
            safe_print(f"[通过] 检查3：中文/汉字占比 {chinese_ratio*100:.2f}% < 15% ✓")
        
        safe_print("\n" + "=" * 80)
        safe_print("[结论] 日语核心标记测试通过 ✓✓✓")
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
    # 等待server启动
    time.sleep(3)
    
    results = []
    
    # 测试英语
    results.append(("英语核心标记", test_core_marker_english()))
    
    # 测试日语
    results.append(("日语核心标记", test_core_marker_japanese()))
    
    # 汇总
    safe_print("\n\n" + "=" * 80)
    safe_print("【测试汇总】")
    safe_print("=" * 80)
    
    all_passed = True
    for name, passed in results:
        status = "通过 ✓" if passed else "失败 ✗"
        safe_print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    safe_print("=" * 80)
    if all_passed:
        safe_print("[最终结论] P0-1 多语言核心标记修复验证通过 ✓")
    else:
        safe_print("[最终结论] P0-1 多语言核心标记修复验证失败 ✗")
