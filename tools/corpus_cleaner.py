"""corpus_cleaner.py — 旧语料库质量清理脚本

检测并移除各语言文件中的污染内容：
- 日语文件：移除纯中文行（有汉字但无假名，CJK占比>15%）
- 韩语文件：移除纯中文行（有汉字但无韩文，CJK占比>15%）
- 粤语文件：移除普通话行（有汉字但无粤语专属词汇，CJK占比>15%）
- 欧洲语言：移除 CJK 占比 > 5% 的行
- 所有语言：移除英文通用回退行
"""
import re
import shutil
from pathlib import Path

CORPUS = Path("demo-data/training_long_dialogue")
BACKUP = Path("demo-data/training_long_dialogue_backup")

# ── 字符集检测 ────────────────────────────────────────────────────────────────
CJK_RE    = re.compile("[一-鿿]")
KANA_RE   = re.compile("[\\u3040-\\u30ff]")     # 平假名 + 片假名
HANGUL_RE = re.compile("[\\uac00-\\ud7a3]")     # 韩文音节

# 粤语专属字符（在普通话中极少或无此用法，经过保守筛选）
# 去掉了 呢/啦/呀/係 等普通话也常用的字
YUE_UNIQUE = set("哋嘅喺咁唔佢㗎咩乜冇喇囉喎啫噃嗯咋嗰咪俾呐埋晒")

# 英文通用回退行（LLM 降级时注入到多语言文件的固定模板行）
FALLBACK_EN_EXACT = {
    "I'd also like to understand this aspect.",
    "I'd also like to understand this aspect",
    "That's an important consideration. Let me review the relevant details.",
    "I'll need to verify a few things before I can give you a complete response.",
    "That's an important point to consider.",
    "I'll send you a summary of our discussion today along with recommended action items.",
    # Short English acknowledgement fallback lines appearing in ja/ko/yue files
    "Okay, I will cooperate.",
    "Okay, I will prepare carefully.",
    "Indeed, these details need attention.",
    "This explanation is very clear, I understand now.",
    "This suggestion is very helpful, thank you.",
    "Understood, I will cooperate on my end.",
}
FALLBACK_EN_RE = re.compile(
    r"From a .{2,30} perspective, we should focus on"
    r"|I'll be focused on key constraints and risk areas around Scenario"
    r"|Scenario: A professional business discussion conducted in"
    r"|Please review the proposed plan and let me know if you have"
    r"|What steps have you already taken to address this issue"
)

SPEAKER_RE = re.compile(r"^(Speaker|说话人)\s*\d+:\s*")


def _strip_speaker(line):
    return SPEAKER_RE.sub("", line).strip()


def _cjk_ratio(text):
    non_ws = [c for c in text if not c.isspace()]
    if not non_ws:
        return 0.0
    return sum(1 for c in non_ws if CJK_RE.match(c)) / len(non_ws)


def is_bad_line(line, lang):
    """Return True if the line should be removed for the given language."""
    content = _strip_speaker(line)
    if not content:
        return False

    # Remove known English fallback lines from ALL non-English files
    if lang != "en":
        if content in FALLBACK_EN_EXACT or FALLBACK_EN_RE.search(content):
            return True

    cr = _cjk_ratio(content)

    if lang == "ja":
        # Chinese contamination: substantial CJK but NO kana
        # Threshold lowered to 15% to also catch mixed ASCII+Chinese lines
        if cr > 0.15 and not KANA_RE.search(content):
            return True

    elif lang == "ko":
        # Chinese contamination: substantial CJK but NO Hangul
        if cr > 0.15 and not HANGUL_RE.search(content):
            return True

    elif lang == "yue":
        # Mandarin contamination: substantial CJK but no Cantonese-specific chars
        if cr > 0.15 and not any(c in YUE_UNIQUE for c in content):
            return True

    elif lang in ("en", "fr", "de", "es", "pt"):
        # European languages: any significant CJK is contamination
        if cr > 0.05 and len(content) > 5:
            return True

    return False


def parse_lang(stem):
    for lc in ("zh", "en", "ja", "ko", "fr", "de", "es", "pt", "yue"):
        if f"_{lc}_spk" in stem:
            return lc
    return None


def clean_file(path, lang):
    """Return (cleaned_text, lines_removed, original_line_count)."""
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)

    kept = []
    removed = 0
    for line in lines:
        stripped = line.rstrip("\n\r")
        if stripped.strip() and is_bad_line(stripped, lang):
            removed += 1
        else:
            kept.append(line)

    return "".join(kept), removed, len([l for l in lines if l.strip()])


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    files = sorted(CORPUS.glob("*.txt"))
    print(f"Total files: {len(files)}")

    if not BACKUP.exists():
        shutil.copytree(CORPUS, BACKUP)
        print(f"Backup created: {BACKUP}")
    else:
        print(f"Backup exists at {BACKUP}")
    print()

    stats = {}
    short_files = []
    total_removed = 0

    for f in files:
        lang = parse_lang(f.stem)
        if not lang:
            continue

        cleaned, removed, total = clean_file(f, lang)
        clean_lines = [l for l in cleaned.splitlines() if l.strip()]

        stats.setdefault(lang, {"files": 0, "removed": 0, "total": 0, "short_after": 0})
        stats[lang]["files"] += 1
        stats[lang]["removed"] += removed
        stats[lang]["total"] += total
        total_removed += removed

        if len(clean_lines) < 25:
            stats[lang]["short_after"] += 1
            short_files.append((f.name, lang, total, len(clean_lines)))

        if removed > 0:
            f.write_text(cleaned, encoding="utf-8")

    print("=== CLEANING RESULTS ===")
    for lang in sorted(stats):
        s = stats[lang]
        pct = s["removed"] * 100 // s["total"] if s["total"] else 0
        print(
            f"  [{lang}]: {s['files']} files, "
            f"{s['removed']} lines removed ({pct}%), "
            f"{s['short_after']} files < 25 lines after cleaning"
        )
    print(f"\nTotal lines removed: {total_removed}")

    if short_files:
        print(f"\nFiles < 25 lines after cleaning ({len(short_files)} total):")
        for name, lang, before, after in sorted(short_files):
            print(f"  [{lang}] {name}: {before} -> {after} lines")
