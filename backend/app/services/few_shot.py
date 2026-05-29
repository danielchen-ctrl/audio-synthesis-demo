"""Few-shot 检索：按 (topic_id, language) 查 v3 训练样本。

数据源：backend/app/data/few_shot/v3_{lang}/passed/...txt
索引在首次调用时懒加载（lru_cache 缓存）。

文件名格式：
  v3_{batch_lang}_t{topic_id}_{lang_label}_p{speakers}_w{words}_{seed}_{hash}.txt
  v3_long_{batch_lang}_t{topic_id}_{lang_label}_p{speakers}_w{words}_{seed}_{hash}.txt

batch_lang ∈ {chinese, english, japanese, korean}
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from loguru import logger

# 质量门槛：低于此分的样本不进入索引（v3 训练默认 passed 阈值 65，这里更严）
MIN_SCORE = 70.0

FEW_SHOT_ROOT = Path(__file__).resolve().parent.parent / "data" / "few_shot"

# v3_chinese_t11_中文_p4_w1000_1000_4_96608126.txt
# v3_long_japanese_t6_日语_p3_w5000_5000_3_1580565793.txt
_FILE_RE = re.compile(
    r"^v3(?:_long)?_(?P<batch_lang>[a-z]+)"
    r"_t(?P<topic>\d+)"
    r"_[^_]+"            # lang_label（中文/英语/日语/韩语）
    r"_p(?P<speakers>\d+)"
    r"_w(?P<words>\d+)"
    r"_.+\.txt$"
)

_LANG_FROM_BATCH = {
    "chinese": "zh",
    "english": "en",
    "japanese": "ja",
    "korean": "ko",
}


@dataclass
class FewShotSample:
    path: Path
    topic_id: str
    language: str
    speaker_count: int
    target_word_count: int
    is_long_tier: bool
    score: float = 0.0


def _load_score(txt_path: Path) -> float | None:
    """读同目录下的 .score.json，拿 score 字段。"""
    score_path = txt_path.with_suffix(".score.json")
    if not score_path.exists():
        return None
    try:
        data = json.loads(score_path.read_text(encoding="utf-8"))
        return float(data.get("score", 0))
    except (json.JSONDecodeError, ValueError, KeyError):
        return None


def _build_index() -> dict[tuple[str, str], list[FewShotSample]]:
    """扫描整个目录建 (topic_id, lang) → samples 索引。"""
    index: dict[tuple[str, str], list[FewShotSample]] = {}
    if not FEW_SHOT_ROOT.exists():
        logger.warning(f"Few-shot root not found: {FEW_SHOT_ROOT}; retrieval will return empty")
        return index

    total = 0
    skipped_filename = 0
    skipped_lowscore = 0
    for path in FEW_SHOT_ROOT.rglob("*.txt"):
        m = _FILE_RE.match(path.name)
        if not m:
            skipped_filename += 1
            continue
        lang = _LANG_FROM_BATCH.get(m.group("batch_lang"))
        if not lang:
            skipped_filename += 1
            continue
        score = _load_score(path)
        # 没分文件视为缺失，丢弃；分数低于阈值也丢弃
        if score is None or score < MIN_SCORE:
            skipped_lowscore += 1
            continue
        sample = FewShotSample(
            path=path,
            topic_id=m.group("topic"),
            language=lang,
            speaker_count=int(m.group("speakers")),
            target_word_count=int(m.group("words")),
            is_long_tier="long" in path.parts[-5] if len(path.parts) >= 5 else False,
            score=score,
        )
        index.setdefault((sample.topic_id, sample.language), []).append(sample)
        total += 1

    # 每个 key 内按分数倒序，方便取 top-K 时优先用高分
    for k in index:
        index[k].sort(key=lambda s: s.score, reverse=True)

    logger.info(
        f"Few-shot index built: {total} samples in {len(index)} (topic, lang) keys "
        f"(filename skipped: {skipped_filename}, low-score skipped: {skipped_lowscore}, "
        f"MIN_SCORE={MIN_SCORE})"
    )
    return index


@lru_cache(maxsize=1)
def get_index() -> dict[tuple[str, str], list[FewShotSample]]:
    return _build_index()


def reload_index() -> dict:
    """清缓存重建索引（用于 admin 端点）。"""
    get_index.cache_clear()
    idx = get_index()
    return {
        "total_keys": len(idx),
        "total_samples": sum(len(v) for v in idx.values()),
    }


def retrieve(
    topic_id: str,
    language: str,
    *,
    k: int = 3,
    max_chars_each: int = 1200,
    target_words: int | None = None,
) -> list[str]:
    """按 (topic_id, language) 抽 top-K 样本（随机），每段最多 max_chars_each 字符。

    若 target_words 提供，优先返回字数接近的样本。
    """
    if not topic_id:
        return []
    index = get_index()
    samples = index.get((topic_id, language), [])
    if not samples:
        return []

    # 选择策略：
    # 1) 若指定 target_words：先按字数差距筛 top-2K 候选，再按分数取 top-K
    # 2) 否则：从分数前 50% 的池子里随机取 K 个（兼顾质量与多样性）
    if target_words is not None:
        by_words = sorted(samples, key=lambda s: abs(s.target_word_count - target_words))
        pool = by_words[: max(k * 2, k)]
        chosen = sorted(pool, key=lambda s: s.score, reverse=True)[:k]
    else:
        top_half = samples[: max(len(samples) // 2, k)]
        chosen = random.sample(top_half, min(k, len(top_half)))

    out: list[str] = []
    for s in chosen:
        try:
            content = s.path.read_text(encoding="utf-8").strip()
            if len(content) > max_chars_each:
                # 截断到完整一行
                truncated = content[:max_chars_each]
                last_nl = truncated.rfind("\n")
                if last_nl > 0:
                    truncated = truncated[:last_nl]
                content = truncated + "\n…（已截断）"
            out.append(content)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to read sample {s.path}: {e}")
    return out


def stats() -> dict:
    """诊断：返回索引概览（供 admin 接口或日志使用）。"""
    index = get_index()
    all_samples = [s for v in index.values() for s in v]

    by_lang: dict[str, int] = {}
    for lang in ("zh", "en", "ja", "ko"):
        by_lang[lang] = sum(len(v) for k, v in index.items() if k[1] == lang)

    by_topic: dict[str, dict[str, int]] = {}
    for (topic_id, lang), samples in index.items():
        by_topic.setdefault(topic_id, {})[lang] = len(samples)

    score_min = min((s.score for s in all_samples), default=0)
    score_max = max((s.score for s in all_samples), default=0)
    score_avg = (
        round(sum(s.score for s in all_samples) / len(all_samples), 2)
        if all_samples else 0
    )

    return {
        "min_score_threshold": MIN_SCORE,
        "total_keys": len(index),
        "total_samples": len(all_samples),
        "score_min": score_min,
        "score_max": score_max,
        "score_avg": score_avg,
        "by_language": by_lang,
        "by_topic": dict(sorted(by_topic.items(), key=lambda x: int(x[0]))),
    }
