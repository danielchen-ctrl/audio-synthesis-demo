"""
训练数据生成系统 - Smoke Test

测试范围：
- 任务生成（JSONL）
- 批量生成（4个任务：1职业×1场景×中英×500字）
- 统一存储输出（score / index / failed）
- 基础质量字段存在性
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


class TestTrainingPipelineSmoke:
    @classmethod
    def setup_class(cls):
        cls.test_jobs_file = "training_jobs_smoke.jsonl"
        cls.test_output_dir = "runtime/temp/training/smoke_test"
        cls.index_file = Path(cls.test_output_dir) / "_index.jsonl"
        cls.failed_file = Path(cls.test_output_dir) / "_failed.jsonl"
        if os.path.exists(cls.test_jobs_file):
            os.remove(cls.test_jobs_file)
        if os.path.exists(cls.test_output_dir):
            shutil.rmtree(cls.test_output_dir)

    @classmethod
    def teardown_class(cls):
        pass

    def _sample_files(self, pattern: str):
        return [f for f in Path(self.test_output_dir).rglob(pattern) if "failed_samples" not in str(f)]

    def test_01_build_training_jobs(self):
        print("\n[Smoke Test] 步骤1：生成任务清单...")
        result = subprocess.run(
            ["python", "-m", "training.build_training_jobs_mvp", "--out", self.test_jobs_file, "--seed", "20260126"],
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
        assert len(jobs) == 390, f"任务数量错误: {len(jobs)}"
        print(f"[OK] 任务生成成功：{len(jobs)} 个任务")

    def test_02_run_training_generation_smoke(self):
        print("\n[Smoke Test] 步骤2：批量生成对话（前4个任务）...")
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
                "4",
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
        assert len(txt_files) >= 3, f"生成文件数量过少: {len(txt_files)}"
        assert len(meta_files) >= 3, f"meta文件数量过少: {len(meta_files)}"
        assert len(score_files) >= 3, f"score文件数量过少: {len(score_files)}"

    def test_03_validate_core_marker(self):
        print("\n[Smoke Test] 步骤3：验证核心标记...")
        txt_files = self._sample_files("*.txt")
        for txt_file in txt_files:
            content = txt_file.read_text(encoding="utf-8")
            core_markers = re.findall(r"<<(核心|Core|コア|Noyau|핵심):.*?>>", content)
            assert len(core_markers) >= 1, f"{txt_file.name}: 缺少核心标记"
            print(f"[OK] {txt_file.name}: 核心标记 x{len(core_markers)}")

    def test_04_validate_no_placeholder_leak(self):
        print("\n[Smoke Test] 步骤4：验证无占位符残留...")
        for txt_file in self._sample_files("*.txt"):
            content = txt_file.read_text(encoding="utf-8")
            assert "[[[CORE" not in content, f"{txt_file.name}: 存在占位符残留"
            print(f"[OK] {txt_file.name}: 无占位符")

    def test_05_validate_chinese_ratio(self):
        print("\n[Smoke Test] 步骤5：验证中文占比...")
        for txt_file in self._sample_files("*.txt"):
            if "英语" not in str(txt_file) and "English" not in str(txt_file):
                continue
            content = txt_file.read_text(encoding="utf-8")
            chinese_chars = len(re.findall(r"[\u4e00-\u9fa5]", content))
            total_chars = len(content)
            chinese_ratio = chinese_chars / total_chars if total_chars > 0 else 0
            assert chinese_ratio < 0.20, f"{txt_file.name}: 中文占比过高({chinese_ratio:.1%})"
            print(f"[OK] {txt_file.name}: 中文占比 {chinese_ratio:.1%}")

    def test_06_validate_meta_and_score_json(self):
        print("\n[Smoke Test] 步骤6：验证meta与score输出...")
        for meta_file in self._sample_files("*.meta.json"):
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            required_fields = [
                "job_function",
                "language",
                "scenario",
                "core_content",
                "people_count",
                "word_count",
                "seed",
                "effective_params",
                "debug_info",
                "stats",
                "quality",
            ]
            for field in required_fields:
                assert field in meta, f"{meta_file.name}: 缺少字段 {field}"
            assert "speaker_distribution" in meta["stats"]
            assert "passed" in meta["quality"]
            assert "score" in meta["quality"]
            print(f"[OK] {meta_file.name}: 包含 quality 字段")

        index_rows = [json.loads(line) for line in self.index_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(index_rows) >= 3, "统一索引记录过少"
        for row in index_rows[:3]:
            assert "task_id" in row and "paths" in row and "score" in row
        print(f"[OK] 索引记录数: {len(index_rows)}")


if __name__ == "__main__":
    if HAS_PYTEST:
        pytest.main([__file__, "-v", "-s"])
    else:
        suite = TestTrainingPipelineSmoke()
        suite.setup_class()
        tests = [
            suite.test_01_build_training_jobs,
            suite.test_02_run_training_generation_smoke,
            suite.test_03_validate_core_marker,
            suite.test_04_validate_no_placeholder_leak,
            suite.test_05_validate_chinese_ratio,
            suite.test_06_validate_meta_and_score_json,
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
