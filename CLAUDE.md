# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## ⚡ Training Pipeline — Current Status (2026-05-03)

**Phase: Ready to run on main project. No batches have completed yet.**

All pipeline bugs are fixed (commits `9fcaefa4` `1f9867bc` `054d8af8` on branch `codex/fix/legacy-generation-adapter`). Merge/pull to main, then run:

```bash
# Full B0→B5 run (65,628 tasks total)
python tools/training/run_all_batches.py

# Resume after interruption
python tools/training/run_all_batches.py --resume

# Just B0 smoke + B1 foundation (recommended first run)
python tools/training/run_all_batches.py --only-batches b0_smoke b1_foundation
```

Output lands in `output/training_v2/{batch}/passed/` (gitignored). See full execution guide: [`training/docs/training-plan-v2-execution.md`](training/docs/training-plan-v2-execution.md)

**Quick progress check:**
```bash
python3 -c "
import json, os
for batch in ['b0_smoke','b1_foundation','b2_positive_pairs','b3_cross_combo_base','b4_high_risk_boost','b5_extreme_50k']:
    p = f'output/training_v2/{batch}/_index.jsonl'
    if not os.path.exists(p): print(f'{batch:<25} not started'); continue
    records = [json.loads(l) for l in open(p,encoding='utf-8') if l.strip()]
    by_tid = {}
    for r in records: by_tid[r['task_id']] = r
    done = len(by_tid); passed = sum(1 for r in by_tid.values() if r['passed'])
    print(f'{batch:<25} {passed:>5}/{done:<6} passed ({passed/done:.0%} rate)' if done else f'{batch:<25} 0 tasks')
"
```

### Batch plan at a glance

| Batch | Tasks | Key purpose |
|-------|-------|-------------|
| B0 smoke | 594 | Smoke validation — must pass ≥30% to continue |
| B1 foundation | 3,960 | 22 templates × 3 langs × 5 sizes × 2 seeds |
| B2 positive_pairs | 16,038 | 22 topic-template positive pairs, dense coverage |
| B3 cross_combo_base | 24,948 | Full 21×22 topic-template cross, 3 sizes |
| B4 high_risk_boost | 18,900 | 105 high-risk combos, large word counts |
| B5 extreme_50k | 1,188 | 50k-word stress test, selected combos |

---

## Commands

### Run the server
```bash
python server.py
# or
python scripts/start_server.py
```
Server binds to `http://127.0.0.1:8899/` (configured in `config/app.yaml`).

### Run tests

Single test module:
```bash
python -m unittest tests.test_multilingual_naturalness
python -m unittest tests.test_rule_loader
python -m unittest tests.test_server_refactor
```

Full test suite:
```bash
python -m pytest
```

### Syntax check before committing
```bash
python -m py_compile server.py src/demo_app/embedded_server_main.py
```

### Validate YAML rule configs
```bash
python scripts/validate_rule_configs.py
```

### Run the pre-release CI gate (comprehensive check before release)
```bash
python scripts/run_pre_release_ci_gate.py
```
This runs: required-path check → YAML parse → Python compile → repo daily check → multilingual quality check → embedded smoke test. Writes reports to `reports/pre_release_gate/latest.json`.

### Run multilingual quality checks
```bash
python scripts/run_multilingual_quality_checks.py
```

### Install Python dependencies
```bash
pip install -r config/requirements.txt
```

## Branch and PR Workflow

Branch naming convention: `codex/feature/*`, `codex/fix/*`, `codex/chore/*`, `codex/docs/*`. Always branch from `main`, open a PR, merge back.

## Architecture

### Entry point and source layout

```
server.py                          ← thin wrapper, re-exports embedded_server_main.main()
src/demo_app/
  embedded_server_main.py          ← 2000+ line monolith: Tornado app, HTTP handlers, TTS pipeline,
  │                                   bundle extraction, manifest cache, text generation orchestration
  few_shot_selector.py             ← retrieves training corpus examples by domain+language
  multilingual_naturalness.py      ← three-pass LLM output post-processing (repair → keywords → stabilize)
  rule_loader.py                   ← lru_cache loader for the three YAML rule files in config/
static/
  index.html / app.js / styles.css ← single-page UI served by Tornado
config/
  app.yaml                         ← host/port/GUI title
  runtime.yaml                     ← backend routing flags (source_first vs bundle_fallback)
  online_audio_ui.json             ← preset theme catalog (18 industry scenarios) and UI defaults
  text_quality_rules.yaml          ← persona/conflict rules consumed by multilingual_naturalness.py
  text_naturalness_rules.yaml      ← per-language natural speech rules
  text_postprocess_rules.yaml      ← term-rewrite rules per language
demo/
  training_long_dialogue/          ← few-shot corpus: 630 files, 14 domains × 9 languages × 5 speaker variants
  README.md
training/                          ← training pipeline v2
  docs/training-plan-v2-execution.md  ← execution guide (start here)
  quality_scoring.py               ← 100-point scorer; missing_core_marker is WARNING (not error)
  dialogue_validators.py           ← structural validator; core-marker check removed (bundle never emits them)
  training_executor.py             ← retry loop + score gate (passed = no error-severity findings AND score ≥ 60)
  training_storage.py              ← writes passed/ and failed_samples/ trees, _index.jsonl, _failed.jsonl
  plan_v2_data.py                  ← POSITIVE_PAIRS, PRESET_TEMPLATES, MANUAL_TOPICS, B4/B5 combos
  data/training_jobs_b*.jsonl      ← pre-built task files (B0/B1/B5 committed; B2-B4 auto-generated)
tools/training/
  run_all_batches.py               ← B0→B5 sequential runner with gate + auto-cleanup (main entry point)
  run_training_plan.py             ← single-batch runner (--batch / --stage interfaces)
  build_training_plan_jobs.py      ← generates jobs JSONL for a given batch
```

### The "bundle" concept

The LLM engine is packaged as a PyInstaller `.exe` (`build/demo_app/SceneDialogueDemo.exe`). At startup, `embedded_server_main.py` checks whether `runtime/cache/embedded_bundle/` is stale (`_cache_is_fresh()`), extracts `.pyc` modules from the `.pkg` archive if needed, and loads them via `importlib`. The resulting `BundleServer` object is stored in the global `_BUNDLE_SERVER` and provides `_generate_dialogue_lines()` — the actual LLM call. This means **LLM capability is fixed to whatever version is in the `.exe`** and cannot be changed without rebuilding the bundle.

`runtime/cache/embedded_bundle/` is gitignored and regenerated at each startup — do not commit it.

`config/runtime.yaml` controls fallback behaviour (`text_bundle_fallback: enabled` etc.).

### Static file serving

`active_static_dir()` in `embedded_server_main.py` returns `static/` if both `static/index.html` and `static/app.js` exist there; otherwise falls back to `runtime/cache/embedded_bundle/assets/static/`. In development, edits to `static/` take effect immediately without touching the bundle.

### UI generation modes

The single-page UI (`static/index.html` + `static/app.js`) offers two modes:

**LLM mode** (`source_mode: "llm"`) — AI generates dialogue text then synthesises audio:
- User picks a preset theme from `templateSelect` (18 industry scenarios from `config/online_audio_ui.json`)
- Optionally inputs a free-text topic (`llmTopic`) or selects from saved preset topics
- Configures language, word count, keywords, speaker count
- Backend calls the bundle LLM, runs three post-processing passes, then synthesises audio

**Manual mode** (`source_mode: "manual"`) — User pastes dialogue text directly:
- Selects language and speaker count
- Pastes pre-written dialogue in `Speaker N: …` format
- No topic field; `title` and `scenario` in the payload default to `"直接输入"`
- Backend skips text generation, goes straight to audio synthesis

### Request lifecycle

**Text generation (`POST /api/generate_text`)**
1. Parameters sanitised (`_safe_profile`, `_safe_generation_context`)
2. Language normalised to canonical form (`_canonical_language`)
3. Non-CJK profile fields translated to the target language (`_sanitize_profile_for_language`)
4. Few-shot example injected from `demo/training_long_dialogue/` (`few_shot_selector.get_few_shot_example`)
5. `_generate_long_dialogue_lines()` → calls bundle LLM, loops with dedup until word-count target is met
6. Three post-processing passes: `repair_dialogue_quality` → `merge_keywords_into_lines` → `stabilize_dialogue_constraints`
7. Written to `demo/{timestamp}/{basename}.txt` + `manifest.json`; registered in in-memory LRU cache (`_manifest_cache`, 500-entry cap)

**Audio synthesis (`POST /api/synthesize_audio`)**
1. Manifest looked up from cache/disk (`_find_manifest`)
2. Each dialogue line assigned an edge_tts voice (`_voice_for_speaker` → `VOICE_CATALOG`)
3. `asyncio.gather` with `Semaphore(5)` fans out concurrent `edge_tts.Communicate.save()` calls
4. `pydub` probes segment durations (read-then-discard, no accumulation)
5. `subprocess.run(ffmpeg -f concat …)` stitches segments; temporary `.mp3` segment files cleaned up in `finally`

### Key global state in `embedded_server_main.py`

| Variable | Purpose |
|---|---|
| `_BUNDLE_SERVER` | Shared `BundleServer` instance loaded from the `.exe` bundle; initialised once |
| `_manifest_cache` | `OrderedDict` LRU (500 entries) mapping `dialogue_id → (manifest_path, manifest_dict)`; protected by `_manifest_cache_lock` |
| `_ONLINE_AUDIO_CONFIG_CACHE` | UI config loaded once per process from `config/online_audio_ui.json` |
| `_PRESET_TOPICS_CACHE` | Preset scenario list, loaded once per process |

### Training corpus and few-shot

`demo/training_long_dialogue/` is **committed to the repo** (force-tracked despite `demo/` being in `.gitignore`). Files follow the naming pattern `{domain_id}_{lang_short}_spk{N}_wc5000.txt`.

- **14 domains**: `ai_tech`, `commercialization`, `construction`, `consulting`, `finance`, `hr_recruit`, `insurance`, `legal`, `manufacturing`, `media_strategy`, `medical`, `realestate`, `retail`, `test_dev`
- **9 languages**: `zh`, `en`, `ja`, `ko`, `fr`, `de`, `es`, `pt`, `yue`
- **5 speaker variants per combination**: `spk2` through `spk6` (priority order when selecting: spk3 → spk2 → spk4 → spk5)
- Total: 630 files

`few_shot_selector.py` maps human-readable domain/language names to file IDs via `_DOMAIN_TO_ID` and `_LANG_TO_SHORT`. An LRU file cache (32-entry cap) avoids repeated disk reads. If no match is found, an empty string is returned silently — generation still works without few-shot guidance.

### YAML rules and caching

The three config YAML files (`text_quality_rules.yaml`, `text_naturalness_rules.yaml`, `text_postprocess_rules.yaml`) are loaded once via `@lru_cache(maxsize=1)` in `rule_loader.py`. Changes to these files require either a server restart or calling `rule_loader.clear_rule_cache()`.

### PyInstaller packaging

```bash
# Windows
powershell build/build_win.ps1

# macOS
bash build/build_mac.sh
```
Spec file: `build/demo_app.spec`. The built binaries (`build/demo_app/SceneDialogueDemo.exe` on Windows, `build/demo_app/SceneDialogueDemo.pkg` on macOS) are committed to the repo and required for LLM capability. Build intermediates (`.toc`, `.pyz`, `.zip`, `warn-*.txt`, `xref-*.html`) are gitignored and should not be committed. The embedded smoke test in the pre-release gate is skipped with a warning if the binaries are absent.

### ffmpeg dependency

`bin/ffmpeg.exe` is the expected binary path on Windows. The server locates it via `_ffmpeg_path()`. On macOS/Linux, it falls back to `ffmpeg` on `PATH`.
