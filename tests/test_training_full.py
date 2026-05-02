# -*- coding: utf-8 -*-
"""
训练数据生成系统 - FULL版测试
==================================

测试范围：
- 测试 build_training_jobs_full.py
- 批量生成质量验证
- 统一评分/存储输出验证
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    print("[提示] 未安装pytest，使用standalone模式运行")


class TestTrainingFull:
    @classmethod
    def setup_class(cls):
        cls.test_jobs_file = "training_jobs_full_test.jsonl"
        cls.test_output_dir = "runtime/temp/training/full_test"
        cls.index_file = Path(cls.test_output_dir) / "_index.jsonl"
        if os.path.exists(cls.test_jobs_file):
            os.remove(cls.test_jobs_file)
        if os.path.exists(cls.test_output_dir):
            shutil.rmtree(cls.test_output_dir)

    @classmethod
    def teardown_class(cls):
        pass

    def _sample_files(self, pattern: str):
        return [f for f in Path(self.test_output_dir).rglob(pattern) if "failed_samples" not in str(f)]

    def test_01_build_training_jobs_full(self):
        print("\n[FULL Test] 步骤1：生成FULL任务清单...")
        result = subprocess.run(
            ["python", "-m", "training.build_training_jobs_full", "--out", self.test_jobs_file, "--seed", "20260126"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        assert result.returncode == 0, "任务生成失败"
        assert os.path.exists(self.test_jobs_file), "JSONL文件未生成"
        jobs = []
        with open(self.test_jobs_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    jobs.append(json.loads(line))
        print(f"[OK] 生成任务数: {len(jobs)}")
        assert len(jobs) >= 7000, f"任务数量过少: {len(jobs)}"
        assert len(jobs) <= 12000, f"任务数量异常: {len(jobs)}"
        job = jobs[0]
        for field in ["job_id", "profession", "scenario_id", "language", "word_count", "people_count", "seed", "profile", "scenario", "core_content", "translate_fallback"]:
            assert field in job, f"任务缺少字段: {field}"

    def test_02_run_training_generation_sample(self):
        print("\n[FULL Test] 步骤2：批量生成对话（抽样10个任务）...")
        result = subprocess.run(
            [
                "python",
                "-m",
                "training.run_training_generation_mvp",
                "--jobs",
                self.test_jobs_file,
                "--out_dir",
                self.test_output_dir,
                "--max_jobs",
                "10",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        success_in_output = "[MVP批量生成] 成功:" in (result.stdout or "")
        assert result.returncode == 0 or success_in_output, "批量生成失败"
        assert os.path.exists(self.test_output_dir), "输出目录未创建"
        assert self.index_file.exists(), "统一索引 _index.jsonl 未生成"
        txt_files = self._sample_files("*.txt")
        meta_files = self._sample_files("*.meta.json")
        score_files = self._sample_files("*.score.json")
        print(f"[OK] txt文件: {len(txt_files)} meta文件: {len(meta_files)} score文件: {len(score_files)}")
        assert len(txt_files) >= 8, f"生成文件数量过少: {len(txt_files)}"
        assert len(meta_files) >= 8, f"meta文件数量过少: {len(meta_files)}"
        assert len(score_files) >= 8, f"score文件数量过少: {len(score_files)}"

    def test_03_validate_core_marker(self):
        print("\n[FULL Test] 步骤3：验证核心标记...")
        for txt_file in self._sample_files("*.txt"):
            content = txt_file.read_text(encoding="utf-8")
            core_markers = re.findall(r"<<(核心|Core|コア|Noyau|핵심|Kern|Núcleo|Esencial):.*?>>", content)
            assert len(core_markers) >= 1, f"{txt_file.name}: 缺少核心标记"
            assert len(core_markers) <= 2, f"{txt_file.name}: 核心标记过多({len(core_markers)}次)"

    def test_04_validate_no_placeholder_leak(self):
        print("\n[FULL Test] 步骤4：验证无占位符残留...")
        for txt_file in self._sample_files("*.txt"):
            content = txt_file.read_text(encoding="utf-8")
            for pattern in ["[[[CORE", "{{{", "<<<INSERT", "placeholder", "TODO:", "FIXME:"]:
                assert pattern not in content, f"{txt_file.name}: 存在占位符残留: {pattern}"

    def test_05_validate_chinese_ratio(self):
        print("\n[FULL Test] 步骤5：验证中文占比...")
        non_chinese_langs = ["英语", "日语", "韩语", "法语", "德语", "西班牙语", "葡萄牙语"]
        for txt_file in self._sample_files("*.txt"):
            if not any(lang in str(txt_file) for lang in non_chinese_langs):
                continue
            content = txt_file.read_text(encoding="utf-8")
            chinese_chars = len(re.findall(r"[\u4e00-\u9fa5]", content))
            total_chars = len(content)
            chinese_ratio = chinese_chars / total_chars if total_chars > 0 else 0
            assert chinese_ratio < 0.15, f"{txt_file.name}: 中文占比过高({chinese_ratio:.1%})"

    def test_06_validate_meta_json(self):
        print("\n[FULL Test] 步骤6：验证meta.json...")
        for meta_file in self._sample_files("*.meta.json"):
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            for field in ["job_function", "language", "scenario", "core_content", "people_count", "word_count", "seed", "effective_params", "debug_info", "stats", "quality"]:
                assert field in meta, f"{meta_file.name}: 缺少字段 {field}"
            assert "speaker_distribution" in meta["stats"]
            assert "passed" in meta["quality"]
            assert "score" in meta["quality"]

    def test_07_validate_word_count_compliance(self):
        print("\n[FULL Test] 步骤7：验证字数合规性...")
        for meta_file in self._sample_files("*.meta.json"):
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            target_word_count = meta.get("word_count", 0)
            actual_chars = meta.get("stats", {}).get("total_chars", 0)
            min_allowed = target_word_count * 0.7
            max_allowed = target_word_count * 1.3
            assert min_allowed <= actual_chars <= max_allowed, f"{meta_file.name}: 字数不合规"

    def test_08_validate_dialogue_turns_and_index(self):
        print("\n[FULL Test] 步骤8：验证对话轮次与统一索引...")
        for txt_file in self._sample_files("*.txt"):
            lines = [line.strip() for line in txt_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            speaker_lines = [line for line in lines if line.startswith("Speaker")]
            turn_count = len(speaker_lines)
            assert turn_count >= 10, f"{txt_file.name}: 对话轮次过少({turn_count}轮)"
            assert turn_count <= 200, f"{txt_file.name}: 对话轮次过多({turn_count}轮)"

        index_rows = [json.loads(line) for line in self.index_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(index_rows) >= 8, "统一索引记录过少"
        for row in index_rows[:5]:
            assert "task_id" in row and "stage" in row and "paths" in row and "score" in row


if __name__ == "__main__":
    if HAS_PYTEST:
        pytest.main([__file__, "-v", "-s"])
    else:
        suite = TestTrainingFull()
        suite.setup_class()
        tests = [
            suite.test_01_build_training_jobs_full,
            suite.test_02_run_training_generation_sample,
            suite.test_03_validate_core_marker,
            suite.test_04_validate_no_placeholder_leak,
            suite.test_05_validate_chinese_ratio,
            suite.test_06_validate_meta_json,
            suite.test_07_validate_word_count_compliance,
            suite.test_08_validate_dialogue_turns_and_index,
        ]
        failed = 0
        for test in tests:
            try:
                test()
            except Exception as exc:
                failed += 1
                print(exc)
        suite.teardown_class()
        sys.exit(0 if failed == 0 else 1)
