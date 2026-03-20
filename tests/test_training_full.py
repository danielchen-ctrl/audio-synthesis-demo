# -*- coding: utf-8 -*-
"""
训练数据生成系统 - FULL版测试
==================================

测试范围：
- 测试build_training_jobs_full.py（~7800任务）
- 8项硬校验（扩展版）
- 批量生成质量验证

运行方式：
    python tests/test_training_full.py
    或
    python -m pytest tests/test_training_full.py -v -s
"""

import json
import os
import re
import subprocess
import shutil
import sys
from pathlib import Path

# 尝试导入pytest
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    print("[提示] 未安装pytest，使用standalone模式运行")


class TestTrainingFull:
    """训练系统FULL版测试（8项校验）"""
    
    @classmethod
    def setup_class(cls):
        """测试前准备：清理旧文件"""
        cls.test_jobs_file = "training_jobs_full_test.jsonl"
        cls.test_output_dir = "runtime/temp/training/full_test"
        
        # 清理旧文件
        if os.path.exists(cls.test_jobs_file):
            os.remove(cls.test_jobs_file)
        if os.path.exists(cls.test_output_dir):
            shutil.rmtree(cls.test_output_dir)
    
    @classmethod
    def teardown_class(cls):
        """测试后清理"""
        # 保留输出用于人工检查
        pass
    
    def test_01_build_training_jobs_full(self):
        """校验1：生成FULL任务清单（~7800任务）"""
        print("\n[FULL Test] 步骤1：生成FULL任务清单...")
        
        # 运行build_training_jobs_full
        result = subprocess.run(
            ["python", "-m", "training.build_training_jobs_full",
             "--out", self.test_jobs_file,
             "--seed", "20260126"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        # 安全打印输出
        try:
            print(result.stdout)
        except UnicodeEncodeError:
            print("[输出包含无法显示的字符，已跳过]")
        
        if result.returncode != 0:
            try:
                print(f"[错误输出] {result.stderr}")
            except UnicodeEncodeError:
                print("[错误输出包含无法显示的字符]")
        
        assert result.returncode == 0, f"任务生成失败"
        assert os.path.exists(self.test_jobs_file), "JSONL文件未生成"
        
        # 检查JSONL格式
        jobs = []
        with open(self.test_jobs_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    job = json.loads(line)
                    jobs.append(job)
        
        # FULL版预期任务数
        # 中英日：30场景 × 3语言 × 3字数 × 2人数 = 540 (每职业)
        # 前10场景额外：10场景 × 6语言 × 3字数 × 2人数 = 360 (每职业)
        # 总计每职业：900任务
        # 13职业 × 900 = 11700任务（理论值）
        # 实际可能因场景数量不同有差异
        
        print(f"[OK] 生成任务数: {len(jobs)}")
        assert len(jobs) >= 7000, f"任务数量过少: {len(jobs)} (预期>=7000)"
        assert len(jobs) <= 12000, f"任务数量异常: {len(jobs)} (预期<=12000)"
        
        # 检查第一个任务字段完整性
        job = jobs[0]
        required_fields = [
            "job_id", "profession", "scenario_id", "language",
            "word_count", "people_count", "seed", "profile",
            "scenario", "core_content", "translate_fallback"
        ]
        for field in required_fields:
            assert field in job, f"任务缺少字段: {field}"
        
        # 检查profile子字段
        assert "job_function" in job["profile"]
        assert "work_content" in job["profile"]
        assert "seniority" in job["profile"]
        
        # 检查语言分布
        lang_stats = {}
        for job in jobs:
            lang = job["language"]
            lang_stats[lang] = lang_stats.get(lang, 0) + 1
        
        print(f"[OK] 语言分布: {json.dumps(lang_stats, ensure_ascii=False, indent=2)}")
        
        # 验证中英日任务数应该最多（全30场景覆盖）
        assert lang_stats.get("中文", 0) > 0, "缺少中文任务"
        assert lang_stats.get("英语", 0) > 0, "缺少英语任务"
        assert lang_stats.get("日语", 0) > 0, "缺少日语任务"
        
        print(f"[OK] 任务生成成功：{len(jobs)} 个任务")
    
    def test_02_run_training_generation_sample(self):
        """校验2：批量生成（抽样10个任务）"""
        print("\n[FULL Test] 步骤2：批量生成对话（抽样10个任务）...")
        
        # 运行run_training_generation_mvp（只跑前10个任务）
        result = subprocess.run(
            ["python", "-m", "training.run_training_generation_mvp",
             "--jobs", self.test_jobs_file,
             "--out_dir", self.test_output_dir,
             "--max_jobs", "10"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        # 安全打印输出
        try:
            print(result.stdout)
        except UnicodeEncodeError:
            print("[输出包含无法显示的字符，已跳过]")
        
        if result.returncode != 0:
            try:
                print(f"[错误输出] {result.stderr}")
            except UnicodeEncodeError:
                print("[错误输出包含无法显示的字符]")
        
        # 允许部分失败（但至少8个成功）
        success_in_output = "[MVP批量生成] 成功:" in result.stdout if result.stdout else False
        assert result.returncode == 0 or success_in_output, f"批量生成失败"
        
        # 检查输出目录存在
        assert os.path.exists(self.test_output_dir), "输出目录未创建"
        
        # 检查生成的文件数量
        txt_files = list(Path(self.test_output_dir).rglob("*.txt"))
        meta_files = list(Path(self.test_output_dir).rglob("*.meta.json"))
        
        # 过滤掉 _failed.jsonl 之类的文件
        txt_files = [f for f in txt_files if "failed" not in f.name.lower()]
        
        print(f"[OK] 生成的txt文件: {len(txt_files)}")
        print(f"[OK] 生成的meta文件: {len(meta_files)}")
        
        assert len(txt_files) >= 8, f"生成文件数量过少: {len(txt_files)} (预期>=8)"
        assert len(meta_files) >= 8, f"meta文件数量过少: {len(meta_files)} (预期>=8)"
    
    def test_03_validate_core_marker(self):
        """校验3：核心标记唯一性"""
        print("\n[FULL Test] 步骤3：验证核心标记...")
        
        txt_files = list(Path(self.test_output_dir).rglob("*.txt"))
        txt_files = [f for f in txt_files if "failed" not in f.name.lower()]
        
        for txt_file in txt_files:
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查核心标记（支持多语言）
            core_markers = re.findall(r'<<(核心|Core|コア|Noyau|핵심|Kern|Núcleo|Esencial):.*?>>', content)
            
            assert len(core_markers) >= 1, f"{txt_file.name}: 缺少核心标记"
            assert len(core_markers) <= 2, f"{txt_file.name}: 核心标记过多({len(core_markers)}次)"
            
            print(f"[OK] {txt_file.name}: 核心标记 x{len(core_markers)}")
    
    def test_04_validate_no_placeholder_leak(self):
        """校验4：无占位符残留"""
        print("\n[FULL Test] 步骤4：验证无占位符残留...")
        
        txt_files = list(Path(self.test_output_dir).rglob("*.txt"))
        txt_files = [f for f in txt_files if "failed" not in f.name.lower()]
        
        for txt_file in txt_files:
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查常见占位符
            forbidden_patterns = [
                "[[[CORE",
                "{{{",
                "<<<INSERT",
                "placeholder",
                "TODO:",
                "FIXME:"
            ]
            
            for pattern in forbidden_patterns:
                assert pattern not in content, f"{txt_file.name}: 存在占位符残留: {pattern}"
            
            print(f"[OK] {txt_file.name}: 无占位符")
    
    def test_05_validate_chinese_ratio(self):
        """校验5：非中文语言的中文占比"""
        print("\n[FULL Test] 步骤5：验证中文占比...")
        
        txt_files = list(Path(self.test_output_dir).rglob("*.txt"))
        txt_files = [f for f in txt_files if "failed" not in f.name.lower()]
        
        # 定义非中文语言关键词
        non_chinese_langs = ["英语", "日语", "韩语", "法语", "德语", "西班牙语", "葡萄牙语"]
        
        for txt_file in txt_files:
            # 判断是否非中文文件（从路径判断）
            is_non_chinese = any(lang in str(txt_file) for lang in non_chinese_langs)
            
            if not is_non_chinese:
                continue  # 跳过中文文件
            
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 计算中文占比
            chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', content))
            total_chars = len(content)
            chinese_ratio = chinese_chars / total_chars if total_chars > 0 else 0
            
            # FULL版要求更严格：<15%
            assert chinese_ratio < 0.15, \
                f"{txt_file.name}: 中文占比过高({chinese_ratio:.1%})"
            
            print(f"[OK] {txt_file.name}: 中文占比 {chinese_ratio:.1%}")
    
    def test_06_validate_meta_json(self):
        """校验6：meta.json完整性"""
        print("\n[FULL Test] 步骤6：验证meta.json...")
        
        meta_files = list(Path(self.test_output_dir).rglob("*.meta.json"))
        
        for meta_file in meta_files:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            
            # 检查必要字段
            required_fields = [
                "job_function", "language", "scenario", "core_content",
                "people_count", "word_count", "seed",
                "effective_params", "debug_info", "stats"
            ]
            
            for field in required_fields:
                assert field in meta, f"{meta_file.name}: 缺少字段 {field}"
            
            # 检查debug_info
            assert "line_count" in meta["debug_info"]
            assert "total_chars" in meta["debug_info"]
            
            # 检查stats
            assert "speaker_distribution" in meta["stats"]
            
            print(f"[OK] {meta_file.name}: 字段完整")
    
    def test_07_validate_word_count_compliance(self):
        """校验7：字数合规性（±30%容忍度）"""
        print("\n[FULL Test] 步骤7：验证字数合规性...")
        
        meta_files = list(Path(self.test_output_dir).rglob("*.meta.json"))
        
        for meta_file in meta_files:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            
            target_word_count = meta.get("word_count", 0)
            actual_chars = meta.get("stats", {}).get("total_chars", 0)
            
            # 字数容忍度：±30%
            min_allowed = target_word_count * 0.7
            max_allowed = target_word_count * 1.3
            
            assert min_allowed <= actual_chars <= max_allowed, \
                f"{meta_file.name}: 字数不合规 (目标:{target_word_count}, 实际:{actual_chars})"
            
            deviation = abs(actual_chars - target_word_count) / target_word_count * 100
            print(f"[OK] {meta_file.name}: 字数={actual_chars} (目标={target_word_count}, 偏差={deviation:.1f}%)")
    
    def test_08_validate_dialogue_turns(self):
        """校验8：对话轮次合理性"""
        print("\n[FULL Test] 步骤8：验证对话轮次合理性...")
        
        txt_files = list(Path(self.test_output_dir).rglob("*.txt"))
        txt_files = [f for f in txt_files if "failed" not in f.name.lower()]
        
        for txt_file in txt_files:
            with open(txt_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            
            # 统计Speaker行数
            speaker_lines = [line for line in lines if line.startswith("Speaker")]
            turn_count = len(speaker_lines)
            
            # 合理轮次范围：10-200轮
            assert turn_count >= 10, f"{txt_file.name}: 对话轮次过少({turn_count}轮)"
            assert turn_count <= 200, f"{txt_file.name}: 对话轮次过多({turn_count}轮)"
            
            # 检查Speaker分布（避免一人说话）
            speaker_counts = {}
            for line in speaker_lines:
                speaker = line.split(":")[0].strip()
                speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
            
            # 每个speaker至少说3句话
            for speaker, count in speaker_counts.items():
                assert count >= 3, f"{txt_file.name}: {speaker}发言过少({count}次)"
            
            print(f"[OK] {txt_file.name}: {turn_count}轮, 分布={speaker_counts}")


if __name__ == "__main__":
    if HAS_PYTEST:
        pytest.main([__file__, "-v", "-s"])
    else:
        # Standalone模式：手动运行所有测试
        print("\n" + "="*60)
        print(" 训练系统 FULL版测试 - 8项校验")
        print("="*60 + "\n")
        
        test_suite = TestTrainingFull()
        test_suite.setup_class()
        
        tests = [
            ("校验1: 生成FULL任务清单", test_suite.test_01_build_training_jobs_full),
            ("校验2: 批量生成对话", test_suite.test_02_run_training_generation_sample),
            ("校验3: 核心标记唯一性", test_suite.test_03_validate_core_marker),
            ("校验4: 无占位符残留", test_suite.test_04_validate_no_placeholder_leak),
            ("校验5: 中文占比检查", test_suite.test_05_validate_chinese_ratio),
            ("校验6: meta.json完整性", test_suite.test_06_validate_meta_json),
            ("校验7: 字数合规性", test_suite.test_07_validate_word_count_compliance),
            ("校验8: 对话轮次合理性", test_suite.test_08_validate_dialogue_turns),
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
        
        test_suite.teardown_class()
        
        print("\n" + "="*60)
        print(f" 测试结果: {passed} 通过, {failed} 失败")
        print("="*60)
        
        sys.exit(0 if failed == 0 else 1)

