#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
训练数据生成流水线（顺序执行）
===============================
1. 重新生成受污染的英语训练数据（batch_long_dialogue_training.py）
2. 生成日语/韩语训练数据（batch_ja_ko_training.py）
3. 大说话人压力测试（batch_stress_test_large_speakers.py）若尚未完成

用法:
  cd D:/ui_auto_test/demo_app
  python tools/generation/run_training_pipeline.py
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
SCRIPTS = [
    HERE / "batch_long_dialogue_training.py",
    HERE / "batch_ja_ko_training.py",
    HERE / "batch_stress_test_large_speakers.py",
]


def log(msg: str) -> None:
    safe = msg.encode("gbk", errors="replace").decode("gbk")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {safe}", flush=True)


def run_script(script: Path) -> bool:
    log(f"===== 启动: {script.name} =====")
    start = time.time()
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(script.parent.parent.parent),
    )
    elapsed = time.time() - start
    ok = result.returncode == 0
    log(f"===== {'完成' if ok else '失败'}: {script.name}  耗时 {elapsed/60:.1f}min =====")
    return ok


if __name__ == "__main__":
    for script in SCRIPTS:
        if not script.exists():
            log(f"跳过 (不存在): {script.name}")
            continue
        run_script(script)
    log("全部流水线步骤完成！")
