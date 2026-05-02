# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

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
  text_quality_rules.yaml          ← persona/conflict rules consumed by multilingual_naturalness.py
  text_naturalness_rules.yaml      ← per-language natural speech rules
  text_postprocess_rules.yaml      ← term-rewrite rules per language
```

### The "bundle" concept

The LLM engine is packaged as a PyInstaller `.exe` (`build/demo_app/SceneDialogueDemo.exe`). At startup, `embedded_server_main.py` checks whether `runtime/cache/embedded_bundle/` is stale (`_cache_is_fresh()`), extracts `.pyc` modules from the `.pkg` archive if needed, and loads them via `importlib`. The resulting `BundleServer` object is stored in the global `_BUNDLE_SERVER` and provides `_generate_dialogue_lines()` — the actual LLM call. This means **LLM capability is fixed to whatever version is in the `.exe`** and cannot be changed without rebuilding the bundle.

`config/runtime.yaml` controls fallback behaviour (`text_bundle_fallback: enabled` etc.).

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

`demo/training_long_dialogue/` is gitignored. Files follow the naming pattern `{domain_id}_{lang_short}_{wordcount}.txt`. `few_shot_selector.py` maps human-readable domain names to `_DOMAIN_TO_ID` keys and language names to `_LANG_TO_SHORT` codes. An LRU file cache (32-entry cap) avoids repeated disk reads. If the directory is empty or no match is found, an empty string is returned silently — generation still works, just without few-shot guidance.

### YAML rules and caching

The three config YAML files (`text_quality_rules.yaml`, `text_naturalness_rules.yaml`, `text_postprocess_rules.yaml`) are loaded once via `@lru_cache(maxsize=1)` in `rule_loader.py`. Changes to these files require either a server restart or calling `rule_loader.clear_rule_cache()`.

### PyInstaller packaging

```bash
# Windows
powershell build/build_win.ps1

# macOS
bash build/build_mac.sh
```
Spec file: `build/demo_app.spec`. The built `.exe` must be present at `build/demo_app/SceneDialogueDemo.exe` and `build/DialogDemo/DialogDemo.pkg` for the embedded smoke test in the pre-release gate to run (otherwise that step is skipped with a warning).

### ffmpeg dependency

`bin/ffmpeg.exe` is the expected binary path on Windows. The server locates it via `_ffmpeg_path()`. On macOS/Linux, it falls back to `ffmpeg` on `PATH`.
