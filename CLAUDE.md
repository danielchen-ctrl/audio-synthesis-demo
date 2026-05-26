# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 🖥 Platform — Current Status (2026-05-20)

**Phase: Live. 真人 TTS Phase 1 已上线。音色目录已单源化（runtime.yaml 为唯一权威）。支持在线管理（上传/删除）真人克隆音色。生成产物单源化（`storage/generated/<id>/` 一文件夹同时存对话文本 + manifest + 音频）。支持单人（1 speaker）对话文本生成与音频合成。**

### 近期变更（2026-05-20）— 单人对话支持 + 目录合并修复 + 真人音色新增

| 文件 | 改动 |
|------|------|
| `static/app.js` | 删除 `validateLlmBeforeGenerateText()` 中 `speakerCountValue() < 2` 的前端拦截，允许 1 人 LLM 模式生成；`submitRealHumanTask` / `submitEdgeTtsTask` payload 加 `dialogue_id` 字段；`submitEdgeTtsTask` 加 `dialogueId` 参数，调用点传 `state.form.dialogueId` |
| `src/demo_app/embedded_server_main.py` | `_generate_text_payload()` 中 `max(2,...)` → `max(1,...)`，允许单人 LLM 生成；`_load_preset_topics()` 同步修改（preset 的 people_count 也允许为 1） |
| `src/demo_app/multilingual_naturalness.py` | `_prepare_chinese_dialogue_context()` 中 `max(2, people_count)` → `max(1, people_count)`，防止中文稳定化步骤在单人任务里强行补 Speaker 2 台词（`_stabilize_chinese_dialogue` / `_rebuild_chinese_dialogue` / `_build_structured_chinese_dialogue` 三个调用方均同步修复） |
| `src/webapp/db.py` | `create_task()` INSERT 加 `dialogue_id` 列，任务创建时即存储前端传入的 dialogue_id（之前只在任务完成时写入） |
| `src/webapp/task_runner.py` | Step 2 合成音频前：`direct` 模式且 `dialogue_id` 对应目录已存在时，`save_dir` 指向 `dialogue_id` 目录（而非新建 `task_id` 目录），保证 txt + manifest + mp3 落在同一文件夹 |
| `config/runtime.yaml` | 新增音色：新闻联播-女声（`550c362e522f`，中文）、康辉-新闻联播（`da1168ee514b`，中文）、特朗普-总统音（`89d0985d8f4f`，英文） |

**单人对话边界说明：**
- bundle LLM 以 `people_count=1` 生成时会输出 `Speaker 1: ...` 格式的 monologue 文本
- 中文稳定化（`_stabilize_chinese_dialogue`）：1 人时 `order=["Speaker 1"]`，不会补 Speaker 2 行
- `_rebuild_chinese_dialogue`：`secondary = order[1:] or [primary]` → 1 人时 secondary 退化为 `[primary]`，全部内容归属 Speaker 1
- 非中文语言稳定化 `stabilize_dialogue_constraints` 对非中文 early return，不受影响
- TTS / concat 管线：`_concat_audio_segments` 单片段已有快速路径（直接 transcode），无需改动

**目录合并行为：**
- 弹窗生成文本 → `storage/generated/<dialogue_id>/`（txt+manifest），提交任务时携带 `dialogue_id`，task_runner 检测到目录已存在则将 mp3 写入同一目录，一个文件夹三个文件
- 已知边界：direct 模式且前端**未携带 dialogue_id** 时，task_runner 仍只有 `.mp3`，没有 `.txt`/`manifest.json`

### 近期变更（2026-05-16）— 生成产物单源 + 音色管理 UI + 在线注册/删除接口

| 文件 | 改动 |
|------|------|
| `src/demo_app/embedded_server_main.py` | `_generate_text_payload()` / `_create_manual_dialogue_payload()` 默认写 `storage/generated/<dialogue_id>/`，不再写 `demo-data/<timestamp>/`；`_ensure_manifest_cache()` 双源扫描（`storage/generated/` + `demo-data/` 兼容历史任务） |
| `src/webapp/task_runner.py` | 调 `_generate_text_payload` 时显式传 `save_dir=storage/generated/<task_id>/`；复用 `result["basename"]` 作为音频文件 basename（修复 txt/mp3 basename 不一致问题） |
| `static/index.html` | 新增 `#modal-voice-mgmt` 音色管理弹窗（上传参考音频、注册新音色；列出已注册音色并支持删除） |
| `static/app.js` | 新增 `openVoiceMgmt()`、`vmHandleFile()`、`vmRefreshList()`、`vmDeleteVoice()`、`vmSubmit()`；音色目录从硬编码改为启动时调 `/api/voice_catalog` 拉取 |
| `src/webapp/handlers.py` | 新增 `VoiceCatalogHandler`（GET）、`VoiceCreateHandler`（POST）、`VoiceDeleteHandler`（DELETE） |
| `src/demo_app/voice_resolver.py` | `_load_voice_catalog_from_yaml()` 单源加载；`_save_voice_catalog_to_yaml()` 逐行替换保留注释；`create_voice_in_catalog()`；`delete_voice_from_catalog()` |

**目录结构（当前）**：
```
storage/generated/
├── <task_id>/                 ← 平台任务（16 字符 hex）
│   ├── manifest.json
│   ├── <basename>.txt
│   └── <basename>.mp3
└── <dialogue_id>/             ← legacy 模态框任务（8 字符）
    ├── manifest.json
    ├── <basename>.txt
    └── <basename>.mp3
```

The corpus generation platform is a unified Tornado server combining the legacy dialogue/audio generation demo with a full file management platform.

### Start the platform

```bash
python server.py
# or double-click
start_platform.bat
```

Server: `http://127.0.0.1:8899/`
Platform DB: `runtime/platform.db` (SQLite WAL, auto-created)

### Platform API routes

```
Tasks    GET/POST  /api/platform/tasks
         PUT/DELETE /api/platform/tasks/<id>
Files    GET       /api/platform/files
         GET/PUT/DELETE /api/platform/files/<id>
         GET       /api/platform/files/<id>/download
         GET/POST  /api/platform/files/<id>/transcript
Upload   POST      /api/platform/upload
Folders  GET/POST  /api/platform/folders
         PUT/DELETE /api/platform/folders/<id>
Search   GET       /api/platform/search
Trash    GET       /api/platform/trash
         POST      /api/platform/trash/<id>/restore
         DELETE    /api/platform/trash/<id>
Batch    POST      /api/platform/batch/move
         POST      /api/platform/batch/delete
         GET       /api/platform/batch/download
Stats    GET       /api/platform/stats
Voices   GET       /api/voice_catalog               ← 获取前端格式音色目录
         POST      /api/voice_catalog/create        ← 上传参考音频注册新克隆音色（multipart）
         DELETE    /api/voice_catalog/<voice_id>    ← 删除音色（?delete_remote=0|1）
Legacy   GET       /legacy
```

### Preset topics

22 preset dialogue scenarios stored in `config/preset_topics.json`. Loaded at startup by `_load_preset_topics()` in `embedded_server_main.py`. Changing the file requires a server restart.

Schema per entry:
```json
{
  "id": "1",
  "label": "医疗健康｜慢病随访",
  "roles": ["全科医生", "慢病管理护士", "患者本人"],
  "core_keywords": ["症状变化", "用药执行", "复查节点"],
  "topic_description": "围绕一名高血压或糖尿病患者复诊后的随访沟通...",
  "example_topic": "高血压患者复诊后的用药和生活习惯随访沟通",
  "people_count": 3,
  "language": "Chinese",
  "target_words": 1500
}
```

---

## 🎙 真人 TTS — Phase 1 已完成

**Phase: ✅ CosyVoice `/v1/audio/speech` 端点已接入，中英文真人克隆音色可用。**

### CosyVoice API 关键信息

- **端点**：`POST /v1/audio/speech`（OpenAI-compatible，JSON body → WAV bytes 直接返回）
- **请求格式**：`{"model": "cosyvoice-v3", "input": "<text>", "voice": "<voice_id>", "response_format": "wav", "speed": 1.0}`
- **废弃端点**：`/api/tts/async`（仅传 `spk_id` 报 "Invalid file: None"，不要使用）

**当前注册音色**（权威来源：`config/runtime.yaml` → `tts.real_human.voice_catalog`）：

| 语言 | voice_id | 名称 | 性别 |
|------|----------|------|------|
| Chinese | `36d3429a3c98` | maryzhang | female |
| Chinese | `ed35d3674bb0` | lisi | male |
| Chinese | `365689d1619b` | 青年-中文 | male |
| Chinese | `550c362e522f` | 新闻联播-女声 | female |
| Chinese | `da1168ee514b` | 康辉-新闻联播 | male |
| English | `c3e9f75ae993` | willwu | male |
| English | `ce4ac76b992f` | 中年-英文 | male |
| English | `89d0985d8f4f` | 特朗普-总统音 | male |

**扩音色流程：**
1. 编辑 `config/runtime.yaml` 的 `tts.real_human.voice_catalog` 加一条
2. 重启服务器 → `voice_resolver` 模块加载时自动从 yaml 重读
3. 浏览器刷新页面 → `init()` 调 `/api/voice_catalog` 拉到最新值

**CosyVoice 音色注册注意事项：**
- `/v1/voices/create` 成功（返回 voice_id）≠ 合成可用：注册 API 总是成功，但合成时可能返回 500
- 失败原因通常是参考音频质量不足（录音有噪音/背景音/多人/时长不足）
- 推荐参考音频：单人朗读、清晰无噪音、10–30 秒、无背景音乐
- E2E 测试脚本：`tools/test_voice_e2e.py`

### 真人 TTS 合成流程（`task_runner._synthesize_with_real_human`）

1. 从 DB 读取 `voice_assignments`（JSON）→ `build_synthesis_requests()` 将 `line_tuples` 合并为段落级请求（同 speaker 连续行合并，最大 500 字）
2. `asyncio.gather` + `asyncio.Semaphore(max_concurrency)` 并发合成（当前 `max_concurrency=1`，串行安全）
3. 每段调用 `RealHumanProvider.synthesize()` → `_call_speech_v1()` 在 `run_in_executor` 线程中执行 HTTP 请求
4. 超时时按 `max_retries` 重试（当前配置 2 次）
5. 最终失败 → `_fallback_edge_tts()` 降级合成
6. **WAV→MP3 + 静音裁剪**：`silenceremove` 阈值 **-65dB**（保守，仅裁 CosyVoice 数字静音），`-ar 44100 -ac 1` 统一格式
7. **WAV→MP3 失败时**：降级 edge_tts（不保留 WAV 进 concat，避免 codec 混合 → 逐字播放）
8. `_concat_audio_segments()` 用 ffmpeg filter_complex concat 拼接所有 MP3 片段

**并发安全：** `max_concurrency=1` 防止 CosyVoice 响应串扰。WAV 和 MP3 **绝对不能混合** concat。

### voice_id 音色分配规则

**自动分配（`ensureVoiceAssignmentsShape`）**：`cycleVoices` 优先从当前任务语言的目录循环，防止英语任务分配到中文音色。

**显式选择验证**：只要 voice_id 在全局注册音色中存在即合法（跨语言显式使用允许）。

---

## Commands

### Run the server
```bash
python server.py
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
This runs: required-path check → YAML parse → Python compile → repo daily check → multilingual quality check → embedded smoke test.

### Run multilingual quality checks
```bash
python scripts/run_multilingual_quality_checks.py
```

### Install Python dependencies
```bash
pip install -r config/requirements.txt
```

### Training pipeline (v3，已完成 1937 条样本)
```bash
# Short tier（4语言并行，~30分钟）
python tools/training/run_v3_parallel.py

# Long tier（4语言并行，~5小时）
python tools/training/run_v3_parallel.py --long

# 断点续跑
python tools/training/run_v3_parallel.py --long --resume
```
输出目录：`output/training_v3/{batch}/passed/`（已纳入版本管理）。Few-shot 索引 4115 条，覆盖 176 个（场景×语言）组合。

## Branch and PR Workflow

Branch naming convention: `codex/feature/*`, `codex/fix/*`, `codex/chore/*`, `codex/docs/*`. Always branch from `main`, open a PR, merge back.

## Architecture

### Entry point and source layout

```
server.py                          ← thin re-export wrapper → server_platform.py
server_platform.py                 ← unified Tornado app: merges legacy demo + platform routes
src/
  demo_app/
    embedded_server_main.py        ← 2000+ line core: Tornado handlers, TTS pipeline,
    │                                 bundle extraction, manifest cache, text generation
    few_shot_selector.py           ← retrieves few-shot corpus examples by domain+language
    training_few_shot.py           ← retrieves topic-matched samples from training output
    multilingual_naturalness.py    ← three-pass LLM post-processing (repair → keywords → stabilize)
    rule_loader.py                 ← lru_cache loader for the three YAML rule files in config/
    tts_provider.py                ← TTS 数据模型（VoiceSpec/SynthesisRequest/SynthesisResult）+ TTSProvider ABC
    real_human_tts.py              ← RealHumanProvider：CosyVoice /v1/audio/speech 接入
    voice_resolver.py              ← 单源加载 voice_catalog (from runtime.yaml)，提供 resolve_voice_spec /
    │                                 build_synthesis_requests / reload_voice_catalog / get_voice_catalog_for_frontend
  webapp/
    db.py                          ← SQLite helpers (audio_files, tasks, folders tables)；list_tasks JOIN file_duration
    handlers.py                    ← all /api/platform/* Tornado handlers + VoiceCatalogHandler (/api/voice_catalog)
    routes.py                      ← PLATFORM_ROUTES list + register_platform_routes()
    task_runner.py                 ← background task worker；含 _synthesize_with_real_human 真人TTS合成路径
static/
  index.html                       ← single-page platform UI (nav + modals + platform pages)
  app.js                           ← ~100KB: generation modal logic, state machine
  styles.css                       ← CSS variables, light/dark theme, component styles
config/
  app.yaml                         ← host/port/GUI title
  runtime.yaml                     ← backend routing flags + tts.real_human config + **唯一权威 voice_catalog**
  preset_topics.json               ← 22 preset dialogue scenarios (loaded by _load_preset_topics)
  online_audio_ui.json             ← preset theme catalog (18 industry templates) and UI defaults
  text_quality_rules.yaml          ← persona/conflict rules consumed by multilingual_naturalness.py
  text_naturalness_rules.yaml      ← per-language natural speech rules
  text_postprocess_rules.yaml      ← term-rewrite rules per language
demo-data/
  training_long_dialogue/          ← few-shot corpus: 630 files, 14 domains × 9 languages × 5 variants
  <timestamp>/                     ← legacy history pre-migration; manifest cache double-scans for back-compat
  README.md
storage/
  generated/<id>/                  ← **生成产物单源目录**：txt + manifest.json + mp3 同一文件夹
                                       <id> = task_id (16 hex, 平台任务) 或 dialogue_id (8 字符, legacy 模态框)
  uploaded/                        ← 用户上传的音频文件
runtime/
  platform.db                      ← SQLite DB (gitignored; auto-created on first start)
  cache/                           ← bundle extraction cache (gitignored; regenerated at startup)
training/                          ← training pipeline v3
  training_executor.py             ← task runner; adaptive timeout max(300, word_count//50)
  quality_scoring.py / dialogue_validators.py / training_storage.py
  legacy_generation.py             ← dialogue generation adapter; _CHUNK_SIZE=2500 for ja/ko
  data/v3_jobs_*.jsonl             ← pre-built job files for 8 batches (short+long × 4 langs)
output/training_v3/               ← v3 training output (committed to repo)
  {batch}/passed/                  ← 1937 passed samples, 22 scenarios × 4 langs × 500-50k chars
tools/training/
  run_v3_parallel.py               ← v3 parallel runner (current main entry point)
  build_v3_jobs.py                 ← v3 job builder (short + long tier)
docs/
  PROJECT_EXPLANATION.md          ← project overview / file map / module deep dive
```

### The "bundle" concept

The LLM engine is packaged as a PyInstaller `.exe` (`build/demo_app/SceneDialogueDemo.exe`). At startup, `embedded_server_main.py` checks whether `runtime/cache/embedded_bundle/` is stale (`_cache_is_fresh()`), extracts `.pyc` modules from the `.pkg` archive if needed, and loads them via `importlib`. The resulting `BundleServer` object is stored in the global `_BUNDLE_SERVER` and provides `_generate_dialogue_lines()` — the actual LLM call. This means **LLM capability is fixed to whatever version is in the `.exe`** and cannot be changed without rebuilding the bundle.

`runtime/cache/embedded_bundle/` is gitignored and regenerated at each startup — do not commit it.

`config/runtime.yaml` controls fallback behaviour (`text_bundle_fallback: enabled` etc.).

### Platform database (SQLite)

Three tables in `runtime/platform.db`:

| Table | Key columns | Notes |
|-------|-------------|-------|
| `audio_files` | file_id, file_name, file_path, source, duration, language, speaker_count, scene, topic, folder_id, deleted, deleted_at | soft-delete via `deleted=1` |
| `tasks` | task_id, status, generation_mode, topic, language, people_count, word_count, error_msg, file_id, voice_map, output_format, keywords, template, custom_prompt, input_text, include_scripts, tts_provider, tts_fallback_strategy, voice_assignments, dialogue_id | statuses: queued → generating_text → synthesizing → completed / failed |
| `folders` | folder_id, name, parent_id | used to group files in 我的文件 view |

`tasks.voice_assignments` 格式：`{"1": {"provider":"real_human","voice_id":"36d3429a3c98"}}`

`list_tasks()` 通过 `LEFT JOIN audio_files` 附带 `file_duration` 字段（用于任务卡片时长显示）。

### Static file serving

`active_static_dir()` in `embedded_server_main.py` returns `static/` if both `static/index.html` and `static/app.js` exist there; otherwise falls back to `runtime/cache/embedded_bundle/assets/static/`. In development, edits to `static/` take effect immediately without touching the bundle.

### UI pages

The single-page app has five navigable pages rendered inside `#page-{name}` divs:

| Page | nav key | Description |
|------|---------|-------------|
| 全部文件 | `home` | All non-deleted files, sortable/filterable |
| 我的文件 | `myaudio` | Files grouped by folder |
| 生成任务 | `tasks` | Task queue (auto-polls every 3 s when tasks are running) |
| 回收站 | `trash` | Soft-deleted files; restore or permanently delete |
| 文件详情 | `detail` | Per-file metadata, transcript, delete |

Generation modal (`modal-generate`) embeds the legacy `app.js` state machine. Opened via "✨ 生成语料" button.

### UI generation modes

**LLM mode** (`source_mode: "llm"`) — AI generates dialogue text then synthesises audio:
- User picks a preset theme from `templateSelect` (18 industry scenarios from `config/online_audio_ui.json`)
- Optionally inputs a free-text topic (`llmTopic`) or selects from 22 saved preset topics (`config/preset_topics.json`)
- Configures language, word count, keywords, speaker count (min 1)
- Backend calls the bundle LLM, runs three post-processing passes, then synthesises audio

**Manual mode** (`source_mode: "manual"`) — User pastes dialogue text directly:
- Selects language and speaker count
- Pastes pre-written dialogue in `Speaker N: …` format
- Backend skips text generation, goes straight to audio synthesis

### Request lifecycle

**Text generation (`POST /api/generate_text`)**
1. Parameters sanitised (`_safe_profile`, `_safe_generation_context`)
2. Language normalised to canonical form (`_canonical_language`)
3. Non-CJK profile fields translated to the target language (`_sanitize_profile_for_language`)
4. Few-shot example injected: `get_topic_few_shot_example(template_label, language)` → 优先查 `output/training_v3/*/passed/`（v3 long tier 优先），回退到旧语料库 `demo-data/training_long_dialogue/`
5. `_generate_long_dialogue_lines()` → calls bundle LLM, loops with dedup until word-count target is met
6. Three post-processing passes: `repair_dialogue_quality` → `merge_keywords_into_lines` → `stabilize_dialogue_constraints`
7. Written to `storage/generated/{dialogue_id}/{basename}.txt` + `manifest.json`；registered in in-memory LRU cache (`_manifest_cache`, 500-entry cap). 旧任务在 `demo-data/{timestamp}/` 仍可访问——manifest cache 启动时双源扫描兼容历史数据。

**Platform task generation (`POST /api/platform/tasks` → task worker)**
1. Payload params stored as individual columns in DB, status set to `queued`；`tts_provider`、`voice_assignments`、`dialogue_id` 同步写入
2. `src/webapp/task_runner.py` polling loop picks up queued tasks
3. **save_dir 决策**：`direct` 模式且 `dialogue_id` 目录已存在 → 使用 `storage/generated/<dialogue_id>/`（与 txt+manifest 同目录）；否则使用 `storage/generated/<task_id>/`
4. **edge_tts 路径**：调用 `_synthesize_audio_from_lines()`（legacy pipeline）
5. **real_human 路径**（`tts_provider == "real_human"`）：调用 `_synthesize_with_real_human()` → `build_synthesis_requests` 合并段落 → asyncio.gather + Semaphore 并发合成 → WAV→MP3 格式统一 → ffmpeg filter_complex concat
6. On success: writes audio to `save_dir`，`tts_meta` JSON 写入 DB；if `audio_result["warning"]` is set, stores `error_msg="[TTS_WARN] ..."` 显示橙色降级警告
7. On failure: stores error_msg, sets status `failed`

### Key global state in `embedded_server_main.py`

| Variable | Purpose |
|---|---|
| `_BUNDLE_SERVER` | Shared `BundleServer` instance loaded from the `.exe` bundle; initialised once |
| `_manifest_cache` | `OrderedDict` LRU (500 entries) mapping `dialogue_id → (manifest_path, manifest_dict)`; protected by `_manifest_cache_lock` |
| `_ONLINE_AUDIO_CONFIG_CACHE` | UI config loaded once per process from `config/online_audio_ui.json` |
| `_PRESET_TOPICS_CACHE` | 22-entry preset scenario list, loaded once per process from `config/preset_topics.json` |

### showConfirm dual API

`showConfirm` in `static/index.html` supports two calling conventions:

```javascript
// Platform style — callback (void return)
showConfirm("title", "description", () => { /* on OK */ });

// app.js style — Promise (await-able)
const confirmed = await showConfirm("Are you sure?");
if (!confirmed) return;
```

The restoration script (after `<script src="/static/app.js">`) overrides `showConfirm` to detect which style is being used and branch accordingly.

### Training corpus and few-shot

两套 few-shot 语料，由 `training_few_shot.py` 统一索引：

**v3 训练数据**（主要来源，4115 条索引，优先级最高）
- 路径：`output/training_v3/*/passed/`（已纳入版本管理）
- 1937 条通过样本：22 场景 × 4 语言（zh/en/ja/ko）× 500–50000 字
- Long tier（10k-50k 字）样本得分 +15 加成，排序优先
- 最低分门槛 65，excerpt 长度 1200 字符

**旧语料库**（回退来源）
- 路径：`demo-data/training_long_dialogue/`（force-tracked）
- 630 个文件：14 domains × 9 languages × 5 speaker variants（spk2–spk6）

索引在服务器启动时清除（`invalidate_index()`），首次请求时懒加载重建。

### Training quality gates (`training/quality_scoring.py`)

强制拦截规则（`severity="error"`，直接 fail）：

| 规则 | 触发条件 |
|------|---------|
| `language_mismatch` | 日语假名比例 < 8%；韩语韩文比例 < 5% |
| `high_chinese_ratio` | 日语任务中文 > 30%；非CJK任务中文整体占比 > 15% |
| `word_count_critical_short` | 日韩实际字数 < 目标 15%；其余 < 40% |
| `scenario_placeholder_artifact` | 非中文任务对话行中出现 `Scenario: [大写]` |
| `core_marker_artifact` | 对话输出中出现任意 `<<…>>` 标记 |
| `chinese_role_name_leak` | 非CJK任务 >15% 的行含 >5% 中文字符 |
| `high_repetition_rate` | 唯一行率 < 60%（且总行数 > 5）|

### YAML rules and caching

The three config YAML files (`text_quality_rules.yaml`, `text_naturalness_rules.yaml`, `text_postprocess_rules.yaml`) are loaded once via `@lru_cache(maxsize=1)` in `rule_loader.py`. Changes to these files require either a server restart or calling `rule_loader.clear_rule_cache()`.

### PyInstaller packaging

```bash
# Windows
powershell build/build_win.ps1

# macOS
bash build/build_mac.sh
```
Spec file: `build/demo_app.spec`. The built binaries (`build/demo_app/SceneDialogueDemo.exe` on Windows) are committed to the repo and required for LLM capability. Build intermediates (`.toc`, `.pyz`, `.zip`, `warn-*.txt`, `xref-*.html`) are gitignored.

### ffmpeg dependency

`bin/ffmpeg.exe` is the expected binary path on Windows. The server locates it via `_ffmpeg_path()`. On macOS/Linux, it falls back to `ffmpeg` on `PATH`.
