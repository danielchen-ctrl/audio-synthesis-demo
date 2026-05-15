"""
CosyVoice 并发上限实测脚本
==========================
目标：探明 CosyVoice /v1/audio/speech 在生产环境下的安全并发数。

方法：
  扫描并发等级 [1, 2, 3, 5, 8]，每等级用同一组 6 条样本文本
  （3 中文 + 3 英文，不同长度），同时发起请求，记录每条 latency、
  HTTP 状态、返回字节数。

串扰检测：
  - 同一文本在不同并发等级下的返回字节数应当稳定（±10%）
  - 跑 2 轮（warm-up + measure）；同文本两轮字节数也应稳定
  - 异常点（字节数偏离基线 >20%）标记为可疑串扰

用法：
  python tools/tts/cosyvoice_concurrency_probe.py [--url http://10.0.20.10:8188]
                                                  [--levels 1,2,3,5,8]
                                                  [--rounds 2]
                                                  [--out report.json]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path

import requests


# ── 测试样本（固定不变，便于跨轮次比较） ─────────────────────────────────
SAMPLES = [
    # (id, voice_id, text)
    ("zh_short",  "36d3429a3c98",  "今天会议主要讨论三件事。"),
    ("zh_medium", "36d3429a3c98",
        "我们这一季度的业绩有显著提升，特别是在华东地区。"
        "下周需要安排一次和销售团队的复盘会议。"),
    ("zh_long",   "36d3429a3c98",
        "首先，本季度核心指标全部达成预期，营收同比增长百分之十八，"
        "其中线上渠道贡献了一半以上。其次，新产品发布后的用户反馈正面，"
        "但售后服务流程暴露了一些瓶颈，需要在下个迭代中重点优化。"
        "最后，关于明年的预算分配，请各位负责人在本周五前提交初稿。"),
    ("en_short",  "c3e9f75ae993",  "Let me summarize the key points."),
    ("en_medium", "c3e9f75ae993",
        "Our team has been working on the new feature rollout for the past "
        "three weeks. We expect to ship the beta version by the end of "
        "this month."),
    ("en_long",   "c3e9f75ae993",
        "The customer support team has reported a significant uptick in "
        "tickets related to the recent deployment. After investigating, "
        "we identified three root causes that need to be addressed. "
        "First, the caching layer was not properly invalidated. Second, "
        "the database migration introduced a subtle race condition. "
        "Third, our monitoring alerts were misconfigured and failed to "
        "page the on-call engineer in time."),
]

LEVELS_DEFAULT = [1, 2, 3, 5, 8]
ROUNDS_DEFAULT = 2
TIMEOUT_SEC    = 180


@dataclass
class CallResult:
    sample_id:   str
    voice_id:    str
    text_chars:  int
    level:       int
    round_idx:   int
    started_at:  float
    latency_ms:  int
    status_code: int
    bytes_len:   int
    error:       str = ""


# ── HTTP 调用 ─────────────────────────────────────────────────────────────

def _call_one(
    session: requests.Session,
    api_url: str,
    sample_id: str,
    voice_id: str,
    text: str,
    level: int,
    round_idx: int,
) -> CallResult:
    t0 = time.monotonic()
    started = time.time()
    text_chars = len(text)
    payload = {
        "model":           "cosyvoice-v3",
        "input":           text,
        "voice":           voice_id,
        "response_format": "wav",
        "speed":           1.0,
    }
    try:
        resp = session.post(
            f"{api_url.rstrip('/')}/v1/audio/speech",
            json=payload,
            timeout=TIMEOUT_SEC,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        return CallResult(
            sample_id=sample_id,
            voice_id=voice_id,
            text_chars=text_chars,
            level=level,
            round_idx=round_idx,
            started_at=started,
            latency_ms=latency_ms,
            status_code=resp.status_code,
            bytes_len=len(resp.content),
            error="" if resp.status_code == 200 else resp.text[:200],
        )
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        return CallResult(
            sample_id=sample_id,
            voice_id=voice_id,
            text_chars=text_chars,
            level=level,
            round_idx=round_idx,
            started_at=started,
            latency_ms=latency_ms,
            status_code=0,
            bytes_len=0,
            error=f"{type(exc).__name__}: {exc}"[:200],
        )


def _run_level(
    api_url: str,
    level: int,
    round_idx: int,
) -> list[CallResult]:
    """在该并发等级下，把 SAMPLES 切成多批次发起，每批 size=level。"""
    session = requests.Session()
    session.headers.update({"Accept": "*/*"})
    results: list[CallResult] = []

    samples = list(SAMPLES)  # 不打乱顺序，便于跨轮次对比
    i = 0
    while i < len(samples):
        batch = samples[i : i + level]
        with ThreadPoolExecutor(max_workers=level) as pool:
            futures = [
                pool.submit(
                    _call_one, session, api_url,
                    sid, vid, text, level, round_idx,
                )
                for (sid, vid, text) in batch
            ]
            for fut in as_completed(futures):
                results.append(fut.result())
        i += level
    return results


# ── 统计与串扰检测 ─────────────────────────────────────────────────────────

def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * pct
    f, c = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _summarize(results: list[CallResult]) -> dict:
    """按 level 汇总：成功率、p50/p95/max 延迟、平均吞吐。"""
    by_level: dict[int, list[CallResult]] = {}
    for r in results:
        by_level.setdefault(r.level, []).append(r)

    summary = {}
    for level, rs in sorted(by_level.items()):
        succ = [r for r in rs if r.status_code == 200]
        fail = [r for r in rs if r.status_code != 200]
        latencies = [r.latency_ms for r in succ]
        total_chars = sum(r.text_chars for r in succ)
        wall_sec = (
            max(r.started_at + r.latency_ms / 1000 for r in rs)
            - min(r.started_at for r in rs)
        ) if rs else 0.0
        summary[level] = {
            "total":          len(rs),
            "success":        len(succ),
            "failed":         len(fail),
            "p50_ms":         int(_percentile(latencies, 0.50)),
            "p95_ms":         int(_percentile(latencies, 0.95)),
            "max_ms":         int(max(latencies) if latencies else 0),
            "mean_ms":        int(statistics.mean(latencies)) if latencies else 0,
            "wall_sec":       round(wall_sec, 2),
            "throughput_cps": round(total_chars / wall_sec, 1) if wall_sec > 0 else 0.0,
            "errors":         [r.error for r in fail][:5],
        }
    return summary


def _crosstalk_check(results: list[CallResult]) -> dict:
    """
    串扰检测：同 sample_id 在所有 (level, round) 下应该返回近似字节数。
    取每个 sample 的中位数为基线，超过 ±20% 视为可疑。
    """
    by_sample: dict[str, list[CallResult]] = {}
    for r in results:
        if r.status_code == 200 and r.bytes_len > 0:
            by_sample.setdefault(r.sample_id, []).append(r)

    findings = {}
    for sid, rs in by_sample.items():
        sizes = [r.bytes_len for r in rs]
        if len(sizes) < 2:
            continue
        baseline = statistics.median(sizes)
        suspects = []
        for r in rs:
            dev = (r.bytes_len - baseline) / baseline if baseline > 0 else 0
            if abs(dev) > 0.20:
                suspects.append({
                    "level":     r.level,
                    "round":     r.round_idx,
                    "bytes":     r.bytes_len,
                    "deviation": f"{dev*100:+.1f}%",
                })
        findings[sid] = {
            "samples":      len(sizes),
            "baseline":     int(baseline),
            "min":          min(sizes),
            "max":          max(sizes),
            "stdev":        int(statistics.stdev(sizes)) if len(sizes) > 1 else 0,
            "suspects":     suspects,
        }
    return findings


# ── 主入口 ────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url",    default="http://10.0.20.10:8188")
    ap.add_argument("--levels", default=",".join(str(l) for l in LEVELS_DEFAULT))
    ap.add_argument("--rounds", type=int, default=ROUNDS_DEFAULT)
    ap.add_argument("--out",    default="cosyvoice_concurrency_report.json")
    args = ap.parse_args()

    levels = [int(x.strip()) for x in args.levels.split(",") if x.strip()]

    print(f"[probe] api_url={args.url}")
    print(f"[probe] levels={levels}  rounds={args.rounds}")
    print(f"[probe] samples={len(SAMPLES)}  total_calls="
          f"{len(SAMPLES) * len(levels) * args.rounds}")
    print()

    all_results: list[CallResult] = []
    for round_idx in range(1, args.rounds + 1):
        print(f"==== Round {round_idx}/{args.rounds} ====")
        for level in levels:
            t0 = time.monotonic()
            rs = _run_level(args.url, level, round_idx)
            wall = time.monotonic() - t0
            succ = sum(1 for r in rs if r.status_code == 200)
            print(f"  level={level:>2}  calls={len(rs):>2}  "
                  f"success={succ:>2}  wall={wall:>5.1f}s  "
                  f"p50={_percentile([r.latency_ms for r in rs if r.status_code==200], 0.5):.0f}ms  "
                  f"p95={_percentile([r.latency_ms for r in rs if r.status_code==200], 0.95):.0f}ms")
            all_results.extend(rs)
            time.sleep(2)  # 让服务器在并发等级之间稍作喘息
        print()

    summary = _summarize(all_results)
    crosstalk = _crosstalk_check(all_results)

    print("==== Summary by Level ====")
    print(f"{'level':>5}  {'ok/tot':>7}  {'p50':>6}  {'p95':>6}  {'max':>6}  {'wall':>6}  {'cps':>7}")
    for level, s in summary.items():
        print(f"  {level:>3}  {s['success']:>3}/{s['total']:<3}  "
              f"{s['p50_ms']:>5}  {s['p95_ms']:>5}  {s['max_ms']:>5}  "
              f"{s['wall_sec']:>5.1f}  {s['throughput_cps']:>6.1f}")
        if s["errors"]:
            for e in s["errors"][:3]:
                print(f"        err: {e[:120]}")
    print()

    print("==== Crosstalk Check (same sample across levels/rounds) ====")
    has_suspects = False
    for sid, info in crosstalk.items():
        marker = "⚠️" if info["suspects"] else "✓"
        print(f"  {marker} {sid:>10}: n={info['samples']:>2}  "
              f"baseline={info['baseline']:>7}B  "
              f"min/max={info['min']}/{info['max']}  "
              f"stdev={info['stdev']}")
        for sus in info["suspects"]:
            has_suspects = True
            print(f"     suspect: level={sus['level']} round={sus['round']} "
                  f"bytes={sus['bytes']} dev={sus['deviation']}")
    print()
    if has_suspects:
        print("⚠️  发现可疑串扰，请检查上述样本")
    else:
        print("✓  无明显串扰证据")
    print()

    out_path = Path(args.out)
    out_path.write_text(
        json.dumps({
            "url":       args.url,
            "levels":    levels,
            "rounds":    args.rounds,
            "summary":   summary,
            "crosstalk": crosstalk,
            "raw":       [asdict(r) for r in all_results],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[probe] 完整报告写入: {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
