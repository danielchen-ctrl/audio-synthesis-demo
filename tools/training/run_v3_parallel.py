#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_v3_parallel.py
==================
以 4 个并行进程同时运行 v3 训练方案（每语言一个独立进程）。

用法：
  # short tier（短中对话，默认）
  python tools/training/run_v3_parallel.py

  # long tier（长对话 10k-50k）
  python tools/training/run_v3_parallel.py --long

  # 断点续跑
  python tools/training/run_v3_parallel.py --long --resume

  # 只跑指定语言
  python tools/training/run_v3_parallel.py --long --langs chinese english

输出目录：output/training_v3/{batch_name}/
日志文件：output/training_v3/logs/{lang}[_long].log
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

LANGUAGES = ["chinese", "english", "japanese", "korean"]

LANG_DISPLAY = {
    "chinese": "中文",
    "english": "英语",
    "japanese": "日语",
    "korean": "韩语",
}

# long tier 任务数
LONG_TOTALS = {"chinese": 440, "english": 440, "japanese": 132, "korean": 132}
SHORT_TOTALS = {"chinese": 330, "english": 330, "japanese": 198, "korean": 198}


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _batch_name(lang: str, long: bool) -> str:
    return f"v3_long_{lang}" if long else f"v3_{lang}"


def _jobs_file(lang: str, long: bool) -> Path:
    suffix = f"long_{lang}" if long else lang
    return ROOT / "training" / "data" / f"v3_jobs_{suffix}.jsonl"


def _read_progress(lang: str, out_dir: Path, long: bool = False) -> tuple[int, int]:
    """返回 (passed, total_done) for this language."""
    index_path = out_dir / _batch_name(lang, long) / "_index.jsonl"
    if not index_path.exists():
        return 0, 0
    by_tid: dict[str, dict] = {}
    try:
        with index_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                tid = r.get("task_id", "")
                if not tid:
                    continue
                existing = by_tid.get(tid)
                if existing is None or (not existing.get("passed") and r.get("passed")):
                    by_tid[tid] = r
    except Exception:
        return 0, 0
    passed = sum(1 for r in by_tid.values() if r.get("passed"))
    return passed, len(by_tid)


def _count_total_tasks(lang: str, long: bool) -> int:
    jobs_path = _jobs_file(lang, long)
    if not jobs_path.exists():
        return 0
    with jobs_path.open(encoding="utf-8") as f:
        return sum(1 for l in f if l.strip())


def _ensure_jobs_built(langs: list[str], long: bool) -> bool:
    missing = [l for l in langs if not _jobs_file(l, long).exists()]
    if not missing:
        return True
    tier = "long" if long else "short"
    print(f"[{_ts()}] 任务文件不存在，自动生成 ({tier} tier)…")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "training" / "build_v3_jobs.py"), "--tier", tier],
        cwd=str(ROOT),
    )
    return result.returncode == 0


def _stream_log(proc: subprocess.Popen, log_file: Path, lang: str, stop_event: threading.Event) -> None:
    """后台线程：把子进程 stdout 写到 log 文件（stderr 合并）。"""
    with log_file.open("w", encoding="utf-8", buffering=1) as fout:
        for line in iter(proc.stdout.readline, ""):
            fout.write(line)
            fout.flush()
    stop_event.set()


def run_parallel(langs: list[str], resume: bool, out_dir: Path, max_retries: int, long: bool = False) -> None:
    log_dir = out_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    totals = {l: _count_total_tasks(l, long) for l in langs}
    procs: dict[str, subprocess.Popen] = {}
    stop_events: dict[str, threading.Event] = {}
    threads: dict[str, threading.Thread] = {}

    print(f"\n[{_ts()}] 启动 {len(langs)} 个并行训练进程")
    print(f"  输出目录: {out_dir}")
    print(f"  resume={resume}  max_retries={max_retries}")
    print(f"  语言: {langs}")
    print()

    for lang in langs:
        jobs_path = _jobs_file(lang, long)
        batch_name = _batch_name(lang, long)
        log_suffix = f"{lang}_long" if long else lang
        log_path = log_dir / f"{log_suffix}.log"

        cmd = [
            sys.executable,
            str(ROOT / "tools" / "training" / "run_training_plan.py"),
            "--batch", batch_name,
            "--jobs", str(jobs_path),
            "--out_dir", str(out_dir),
            "--max_retries", str(max_retries),
        ]
        if resume:
            cmd.append("--resume")

        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        procs[lang] = proc
        stop_events[lang] = threading.Event()
        t = threading.Thread(
            target=_stream_log,
            args=(proc, log_path, lang, stop_events[lang]),
            daemon=True,
        )
        t.start()
        threads[lang] = t
        print(f"  [{lang:8}] PID={proc.pid}  log={log_path.name}")

    print(f"\n{'─'*60}")
    print(f"{'语言':8} {'通过/完成':>12} {'总数':>6} {'进度':>6}  状态")
    print(f"{'─'*60}")

    start_time = time.time()
    last_progress: dict[str, tuple[int, int]] = {}

    try:
        while True:
            all_done = all(p.poll() is not None for p in procs.values())

            lines = []
            for lang in langs:
                passed, done = _read_progress(lang, out_dir, long)
                total = totals[lang]
                pct = f"{passed/total*100:.0f}%" if total else "—"
                status = "✓ done" if procs[lang].poll() is not None else "running"
                last_progress[lang] = (passed, done)
                lines.append(f"  {LANG_DISPLAY[lang]:4} ({lang:8}) {passed:>5}/{done:<6} {total:>6} {pct:>6}  {status}")

            elapsed = time.time() - start_time
            print(f"\r[{_ts()}] elapsed={elapsed/60:.0f}min")
            for l in lines:
                print(l)

            if all_done:
                break

            # Print separator to visually separate progress snapshots
            if elapsed > 10:
                time.sleep(30)
            else:
                time.sleep(5)

    except KeyboardInterrupt:
        print("\n[中断] 正在终止子进程…")
        for p in procs.values():
            p.terminate()

    # Final summary
    print(f"\n{'='*60}")
    print("最终结果")
    print(f"{'='*60}")
    grand_passed = 0
    grand_total = 0
    for lang in langs:
        passed, done = _read_progress(lang, out_dir, long)
        total = totals[lang]
        rc = procs[lang].returncode
        rate = f"{passed/done*100:.0f}%" if done else "—"
        print(f"  {LANG_DISPLAY[lang]:4} ({lang:8}): {passed}/{done} passed ({rate}), total={total}, rc={rc}")
        grand_passed += passed
        grand_total += done
    elapsed = time.time() - start_time
    print(f"{'─'*60}")
    print(f"  合计: {grand_passed}/{grand_total} passed  耗时 {elapsed/3600:.1f}h")
    print(f"  日志: {log_dir}/")


def main() -> None:
    parser = argparse.ArgumentParser(description="v3 并行训练（4语言同时运行）")
    parser.add_argument("--langs", nargs="+", default=LANGUAGES,
                        choices=LANGUAGES, metavar="LANG",
                        help=f"运行哪些语言（默认全部）: {LANGUAGES}")
    parser.add_argument("--long", action="store_true",
                        help="运行 long tier（10k-50k字数）；默认运行 short tier")
    parser.add_argument("--resume", action="store_true",
                        help="断点续跑：跳过已通过的任务")
    parser.add_argument("--out_dir", default="output/training_v3",
                        help="输出根目录（默认 output/training_v3）")
    parser.add_argument("--max_retries", type=int, default=2,
                        help="每个任务最大重试次数（默认 2）")
    args = parser.parse_args()

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if not _ensure_jobs_built(args.langs, args.long):
        print("[错误] 任务文件生成失败", file=sys.stderr)
        sys.exit(1)

    run_parallel(args.langs, args.resume, out_dir, args.max_retries, long=args.long)


if __name__ == "__main__":
    main()
