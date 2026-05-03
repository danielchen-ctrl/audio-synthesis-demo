#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_all_batches.py
==================
按顺序执行 B0→B5 全部训练批次，包含：
  - B0 通过率门控（默认 ≥ 30% 才继续）
  - 每批次结束后自动清理 failed_samples（可关闭）
  - 主日志 _master_log.jsonl 跨批次汇总
  - 支持 --resume 断点续跑
  - 支持 --only-batches 只跑指定批次

用法示例：
  # 全量跑 B0-B5
  python tools/training/run_all_batches.py

  # 断点续跑（跳过已通过的任务）
  python tools/training/run_all_batches.py --resume

  # 只跑 B0 和 B1
  python tools/training/run_all_batches.py --only-batches b0_smoke b1_foundation

  # 保留所有批次的 failed_samples（调试用）
  python tools/training/run_all_batches.py --keep-failed-all

  # 修改 B0 通过率门槛
  python tools/training/run_all_batches.py --b0-min-pass-rate 0.40
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ─────────────────────────────────────────────────────
# 批次配置
# ─────────────────────────────────────────────────────

BATCH_ORDER = [
    "b0_smoke",
    "b1_foundation",
    "b2_positive_pairs",
    "b3_cross_combo_base",
    "b4_high_risk_boost",
    "b5_extreme_50k",
]

# B0 以外默认不保留 failed_samples（避免产生大量垃圾文件）
KEEP_FAILED_BY_DEFAULT: dict[str, bool] = {
    "b0_smoke": True,   # 验证批，保留失败样本供分析
    "b1_foundation": False,
    "b2_positive_pairs": False,
    "b3_cross_combo_base": False,
    "b4_high_risk_boost": False,
    "b5_extreme_50k": False,
}

# ─────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _batch_storage_dir(batch: str, out_dir: str) -> Path:
    return Path(out_dir) / batch


def _read_index(batch: str, out_dir: str) -> list[dict]:
    p = _batch_storage_dir(batch, out_dir) / "_index.jsonl"
    if not p.exists():
        return []
    records = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
    return records


def _pass_rate(records: list[dict]) -> float:
    if not records:
        return 0.0
    # 每个 task_id 只取最后一条记录（同一任务可能重试多次）
    by_tid: dict[str, dict] = {}
    for r in records:
        tid = r.get("task_id", "")
        by_tid[tid] = r   # 后面的覆盖前面的（最后一次才是最终状态）
    final = list(by_tid.values())
    passed = sum(1 for r in final if r.get("passed"))
    return passed / len(final)


def _count_passed(records: list[dict]) -> tuple[int, int]:
    by_tid: dict[str, dict] = {}
    for r in records:
        tid = r.get("task_id", "")
        by_tid[tid] = r
    final = list(by_tid.values())
    passed = sum(1 for r in final if r.get("passed"))
    return passed, len(final)


def _cleanup_failed_samples(batch: str, out_dir: str) -> int:
    """删除 failed_samples 目录，返回释放的文件数。"""
    failed_dir = _batch_storage_dir(batch, out_dir) / "failed_samples"
    if not failed_dir.exists():
        return 0
    count = sum(1 for _ in failed_dir.rglob("*") if _.is_file())
    shutil.rmtree(failed_dir)
    return count


def _write_master_log(entry: dict, out_dir: str) -> None:
    master = Path(out_dir) / "_master_log.jsonl"
    master.parent.mkdir(parents=True, exist_ok=True)
    with master.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _ensure_jobs_file(batch: str) -> Path:
    """如果 jobs JSONL 不存在，自动生成。"""
    jobs_path = ROOT / "training" / "data" / f"training_jobs_{batch}.jsonl"
    if jobs_path.exists():
        return jobs_path
    print(f"  [build_jobs] {batch} 任务文件不存在，自动生成…")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "training" / "build_training_plan_jobs.py"),
         "--batch", batch],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(f"  [build_jobs] 失败:\n{result.stderr[-2000:]}", file=sys.stderr)
        sys.exit(1)
    print(f"  [build_jobs] 完成: {jobs_path}")
    return jobs_path


# ─────────────────────────────────────────────────────
# 核心：跑单个批次
# ─────────────────────────────────────────────────────

def run_batch(
    batch: str,
    out_dir: str,
    resume: bool,
    keep_failed: bool,
    max_retries: int,
    jobs_path: str = "",
) -> dict:
    """调用 run_training_plan.py 跑一个批次，返回结果摘要 dict。"""
    cmd = [
        sys.executable,
        str(ROOT / "tools" / "training" / "run_training_plan.py"),
        "--batch", batch,
        "--out_dir", out_dir,
        "--max_retries", str(max_retries),
    ]
    if jobs_path:
        cmd += ["--jobs", jobs_path]
    if resume:
        cmd += ["--resume"]
    if keep_failed:
        cmd += ["--keep-failed-samples"]

    print(f"\n{'='*70}")
    print(f"[{_ts()}] 开始批次: {batch}")
    print(f"  命令: {' '.join(cmd)}")
    print(f"  keep_failed={keep_failed}  resume={resume}  max_retries={max_retries}")
    print(f"{'='*70}")
    sys.stdout.flush()

    start = datetime.now()
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = (datetime.now() - start).total_seconds()

    records = _read_index(batch, out_dir)
    passed_n, total_n = _count_passed(records)
    rate = passed_n / total_n if total_n else 0.0

    summary = {
        "batch": batch,
        "timestamp": _ts(),
        "elapsed_seconds": round(elapsed),
        "returncode": proc.returncode,
        "passed": passed_n,
        "total": total_n,
        "pass_rate": round(rate, 4),
        "keep_failed": keep_failed,
    }
    print(f"\n[{_ts()}] {batch} 完成 — "
          f"通过 {passed_n}/{total_n} ({rate:.1%}), "
          f"耗时 {elapsed/60:.1f}min")
    return summary


# ─────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="顺序执行 B0→B5 全部训练批次",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--out_dir", type=str, default="output/training_v2",
        help="输出根目录（默认 output/training_v2）",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="断点续跑：跳过各批次已通过的任务",
    )
    parser.add_argument(
        "--only-batches", nargs="+", default=[],
        metavar="BATCH",
        help=f"只跑指定批次，可选: {BATCH_ORDER}",
    )
    parser.add_argument(
        "--skip-batches", nargs="+", default=[],
        metavar="BATCH",
        help="跳过指定批次",
    )
    parser.add_argument(
        "--b0-min-pass-rate", type=float, default=0.30,
        help="B0 最低通过率门槛（默认 0.30），低于此值终止后续批次",
    )
    parser.add_argument(
        "--keep-failed-all", action="store_true",
        help="所有批次都保留 failed_samples（默认只 B0 保留）",
    )
    parser.add_argument(
        "--no-cleanup", action="store_true",
        help="批次结束后不自动清理 failed_samples",
    )
    parser.add_argument(
        "--max_retries", type=int, default=2,
        help="每个任务最大重试次数（默认 2）",
    )
    args = parser.parse_args()

    batches = args.only_batches if args.only_batches else BATCH_ORDER
    batches = [b for b in batches if b not in args.skip_batches]
    if not batches:
        print("[错误] 没有需要执行的批次", file=sys.stderr)
        sys.exit(1)

    invalid = [b for b in batches if b not in BATCH_ORDER]
    if invalid:
        print(f"[错误] 未知批次: {invalid}，可选: {BATCH_ORDER}", file=sys.stderr)
        sys.exit(1)

    out_dir = args.out_dir
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    print(f"[{_ts()}] 训练方案启动")
    print(f"  批次顺序: {batches}")
    print(f"  输出目录: {out_dir}")
    print(f"  B0门槛: {args.b0_min_pass_rate:.0%}  resume={args.resume}")

    all_summaries: list[dict] = []

    for batch in batches:
        # 确保 jobs 文件存在
        jobs_path = str(_ensure_jobs_file(batch))

        # 决定是否保留 failed_samples
        keep_failed = (
            args.keep_failed_all
            or KEEP_FAILED_BY_DEFAULT.get(batch, False)
        )

        summary = run_batch(
            batch=batch,
            out_dir=out_dir,
            resume=args.resume,
            keep_failed=keep_failed,
            max_retries=args.max_retries,
            jobs_path=jobs_path,
        )
        all_summaries.append(summary)
        _write_master_log(summary, out_dir)

        # 清理 failed_samples（减少磁盘占用）
        if not args.no_cleanup and not keep_failed:
            cleaned = _cleanup_failed_samples(batch, out_dir)
            if cleaned:
                print(f"  [cleanup] 已清理 {batch}/failed_samples ({cleaned} 个文件)")
        elif not args.no_cleanup and keep_failed and batch != "b0_smoke":
            # B0以外保留了failed_samples，批次结束后清理
            cleaned = _cleanup_failed_samples(batch, out_dir)
            if cleaned:
                print(f"  [cleanup] 已清理 {batch}/failed_samples ({cleaned} 个文件)")

        # B0 通过率门控
        if batch == "b0_smoke" and summary["pass_rate"] < args.b0_min_pass_rate:
            print(f"\n[终止] B0 通过率 {summary['pass_rate']:.1%} < 门槛 "
                  f"{args.b0_min_pass_rate:.0%}，停止后续批次。")
            print("  请检查 output/training_v2/b0_smoke/failed_samples/ 排查问题。")
            _print_final_summary(all_summaries)
            sys.exit(1)

        # B0之后清理 failed_samples（已分析完）
        if batch == "b0_smoke" and not args.no_cleanup:
            print(f"  提示：B0 failed_samples 保留在 {out_dir}/b0_smoke/failed_samples/")
            print(f"  分析完毕后可手动删除，或下次用 --no-cleanup 保留。")

    _print_final_summary(all_summaries)

    # 写最终汇总
    final = {
        "event": "all_batches_complete",
        "timestamp": _ts(),
        "batches": all_summaries,
        "total_passed": sum(s["passed"] for s in all_summaries),
        "total_tasks": sum(s["total"] for s in all_summaries),
    }
    _write_master_log(final, out_dir)
    print(f"\n[{_ts()}] 全部批次执行完毕！")
    print(f"  主日志: {out_dir}/_master_log.jsonl")


def _print_final_summary(summaries: list[dict]) -> None:
    print(f"\n{'='*70}")
    print("最终汇总")
    print(f"{'='*70}")
    print(f"{'批次':<22} {'通过':>6} {'总数':>7} {'通过率':>7} {'耗时':>8}")
    print("-" * 60)
    for s in summaries:
        rate_str = f"{s['pass_rate']:.1%}"
        elapsed_str = f"{s['elapsed_seconds']//60}m{s['elapsed_seconds']%60:02d}s"
        print(f"{s['batch']:<22} {s['passed']:>6} {s['total']:>7} {rate_str:>7} {elapsed_str:>8}")
    total_p = sum(s["passed"] for s in summaries)
    total_t = sum(s["total"] for s in summaries)
    overall = total_p / total_t if total_t else 0.0
    print("-" * 60)
    print(f"{'合计':<22} {total_p:>6} {total_t:>7} {overall:.1%}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
