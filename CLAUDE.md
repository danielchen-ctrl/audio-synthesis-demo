# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## ⚡ Training Pipeline — Current Status (2026-05-08)

**Phase: v3 训练全部完成 ✅。训练数据已推送到 GitHub 主分支。**

### v3 训练方案（当前主线）

v3 训练以每语言独立进程并行执行，替代了原 v2 的串行方案（v2 需 40 天，v3 约 5 小时完成 short tier）。训练数据位于 `output/training_v3/*/passed/`，已纳入版本管理。

**Short tier 最终结果（2026-05-06 完成）：**

| 语言 | 通过/总数 | 通过率 |
|------|---------|--------|
| 中文 | 330/330 | 100% |
| 英语 | 330/330 | 100% |
| 日语 | 175/198 | 88% |
| 韩语 | 198/198 | 100% |
| **合计** | **1033/1056** | **98%** |

**Long tier 最终结果（2026-05-08 完成）：**

| 语言 | 通过/总数 | 通过率 |
|------|---------|--------|
| 中文 | 393/440 | 89% |
| 英语 | 395/440 | 90% |
| 日语 | 59/132 | 45% |
| 韩语 | 87/132 | 66% |
| **合计** | **934/1144** | **82%** |

> 日语 long tier 通过率低（45%）属于预期内：bundle 对 10k+ 字数日语每次调用仅生成约 300-800 字符，大字数目标被质量门禁（15% 阈值）过滤。

**总计：1937 条高质量样本**，覆盖 22 个场景 × 4 语言 × 500–50000 字数。

**运行命令：**
```bash
# Short tier（4语言并行，~30分钟）
python tools/training/run_v3_parallel.py

# Long tier（4语言并行，~5小时）
python tools/training/run_v3_parallel.py --long

# 断点续跑
python tools/training/run_v3_parallel.py --long --resume
```

输出目录：`output/training_v3/{batch}/passed/`（已纳入版本管理，commit `14eebec9`）

**Quick progress check:**
```bash
python -c "
import json, os
batches = {'chinese':'v3_long_chinese','english':'v3_long_english','japanese':'v3_long_japanese','korean':'v3_long_korean'}
totals = {'chinese':440,'english':440,'japanese':132,'korean':132}
for lang, batch in batches.items():
    p = f'output/training_v3/{batch}/_index.jsonl'
    if not os.path.exists(p): print(f'{lang}: not started'); continue
    records = [json.loads(l) for l in open(p,encoding='utf-8') if l.strip()]
    by_tid = {}
    for r in records:
        tid = r['task_id']
        if tid not in by_tid or (not by_tid[tid]['passed'] and r['passed']): by_tid[tid] = r
    done = len(by_tid); passed = sum(1 for r in by_tid.values() if r['passed'])
    total = totals[lang]
    print(f'{lang:10}: {done}/{total} ({done/total*100:.0f}%), {passed} passed ({passed/max(done,1)*100:.0f}%)')
"
```

### 质量门禁规则

`training/quality_scoring.py` 所有强制拦截规则（`severity="error"`，直接 fail）：

| 规则 | 触发条件 | 拦截原因 |
|------|---------|---------|
| `language_mismatch` | 日语任务假名比例 < 8% | Bundle LLM 生成日语时退化为中文 |
| `language_mismatch` | 韩语任务韩文比例 < 5% | 同上 |
| `high_chinese_ratio` | 日语任务中文 > 30%（即使有足够假名）| 中文混入过多 |
| `high_chinese_ratio` | 非CJK任务中文整体占比 > 15% | 大段中文内容渗入 |
| `word_count_critical_short` | 日韩实际字数 < 目标 15%；其余 < 40% | 内容严重不足 |
| `scenario_placeholder_artifact` | 非中文任务对话行中出现 `Scenario: [大写]` | Bundle 把 scenario 描述直接写入台词 |
| `core_marker_artifact` | 对话输出中出现任意 `<<…>>` 标记 | Bundle 渲染残留 |
| `chinese_role_name_leak` | 非CJK任务 >15% 的行含 >5% 中文字符 | 中文角色名渗漏到英/法/德等语言台词 |
| `high_repetition_rate` | 唯一行率 < 60%（且总行数 > 5）| 内容高度重复，训练价值低 |

**已知 bundle 限制**（无法从外部修复，只能靠门禁过滤）：
- 英语输出：bundle 会把 `Scenario: A professional business discussion...` 嵌入台词
- 日语输出：`<<コア:...>>` 标记未消化直接出现在台词里
- 日语输出：中文角色名混入日语台词
- 日语/韩语：每次 bundle 调用仅生成约 300-800 个字符，大字数目标靠分块累积

### v2 训练数据（已锁定）

v2 数据存于 `output/training_v2/`，已完成部分：
- B0 中文：198/198 通过
- B1 中文：360/361 通过
- B0/B1 英语+日语：已清理（发现系统性质量问题）
- B2–B5：未启动（已被 v3 方案取代）

---

## 🔧 生成管线性能优化（2026-05-04 完成）

以下优化已合并到 `src/demo_app/embedded_server_main.py` 和 `multilingual_naturalness.py`：

| 编号 | 文件 | 改动 | 效果 |
|------|------|------|------|
| T3-1 | `embedded_server_main.py` | `_generate_long_dialogue_lines()` 并发生成：`ThreadPoolExecutor(max_workers=3)` 同时跑 N 段，顺序补充 | 长对话首段生成提速 ~3× |
| T3-2 | `embedded_server_main.py` | `repair_dialogue_quality` 完整重建时跳过 `stabilize_dialogue_constraints` | 避免冗余的第三遍重建 |
| T3-3 | `multilingual_naturalness.py` | `enforce_keywords_in_lines()` 预构建 `{speaker: [倒序位置]}` 字典，O(n×k) → O(n+k) | 关键词注入循环去掉内层扫描 |
| T5-3 | `multilingual_naturalness.py` | 提取 `_prepare_chinese_dialogue_context()` helper，两个中文稳定化函数共用 | 消除 14 个上下文变量的重复计算 |
| T5-4 | `embedded_server_main.py` | 提取 `_normalize_request_params(payload, language)` 封装三个 sanitize 调用 | 生成入口参数预处理统一化 |

---

## 🖥 Platform — Current Status (2026-05-16)

**Phase: Live. 真人 TTS Phase 1 已上线。音色目录已单源化（runtime.yaml 为唯一权威）。支持在线管理（上传/删除）真人克隆音色。**

### 近期变更（2026-05-16）— 音色管理 UI + 在线注册/删除接口

| 文件 | 改动 |
|------|------|
| `static/index.html` | 新增 `#modal-voice-mgmt` 音色管理弹窗（上传参考音频、填写名称/语言/性别、注册新音色；列出已注册音色并支持删除）；按钮从"管理音色"改名为"⚙️ 管理真人音色"并调整到中间位置（真人音色 → 管理真人音色 → 合成音色）；`.mo-overlay` z-index 200→700；`closeModal()` 同步清除内联 style；修复 `--border1`/`--text1` 未定义 CSS 变量（→ `--border`/`--text`） |
| `static/app.js` | 新增 `openVoiceMgmt()`（强制内联 style z-index:9999，绕过 CSS 缓存）、`vmHandleFile()`、`vmRefreshList()`、`vmDeleteVoice()`、`vmSubmit()`；`voiceMgmtBtn` 加入 `el` 对象并在 `bindEvents()` 中以 `addEventListener` 绑定（双保险，兼容 onclick 属性） |
| `src/webapp/handlers.py` | 新增 `VoiceCreateHandler`（`POST /api/voice_catalog/create`）：接收 multipart（audio/name/language/gender/text），代理到 CosyVoice `/v1/voices/create`，支持 3 种 voice_id 响应格式，返回 201；新增 `VoiceDeleteHandler`（`DELETE /api/voice_catalog/<voice_id>`）：可选 `delete_remote=1` 删除 CosyVoice 服务器端音色，始终从本地 catalog 删除 |
| `src/webapp/routes.py` | 注册 `/api/voice_catalog/create`（specific，在 regex 路由前）和 `/api/voice_catalog/([^/]+)` |
| `src/demo_app/voice_resolver.py` | 新增 `_get_cosyvoice_api_url()`（优先环境变量）；`_save_voice_catalog_to_yaml()`（逐行定位 `voice_catalog:` 块替换，**保留文件全部注释**）；`create_voice_in_catalog()`；`delete_voice_from_catalog()` |
| `config/runtime.yaml` | 恢复 maryzhang（36d3429a3c98）到中文目录；移除失效音色 fcd231f52834（合成返回 500）；新增用户上传的 AI-男音（06b1d3b50f22，中文）和 AI-男音2（1d8c3af1d010，英文） |

**音色管理 API（新增）：**
```
POST   /api/voice_catalog/create          ← multipart: audio(file) + name + language + gender + text(可选)
DELETE /api/voice_catalog/<voice_id>      ← ?delete_remote=0|1（默认 0，仅删本地）
GET    /api/voice_catalog                 ← 已有，返回前端格式 catalog
```

**CosyVoice 音色注册注意事项（2026-05-16 实测）：**
- `/v1/voices/create` 成功（返回 voice_id）≠ 合成可用：注册 API 总是成功，但合成时可能返回 500
- 失败原因通常是参考音频质量不足（录音有噪音/背景音/多人/时长不足）
- 推荐参考音频：单人朗读、清晰无噪音、10–30 秒、无背景音乐
- 工具脚本：`tools/test_voice_e2e.py`（完整 E2E：create → verify catalog → verify yaml → delete）

### 近期变更（2026-05-13）— 音色目录单源化

| 文件 | 改动 |
|------|------|
| `config/runtime.yaml` | `voice_catalog` 从 `tts.voice_catalog` 上挪到 `tts.real_human.voice_catalog`（4 格缩进，结构语义对称）；标注为**单一权威源**——新增音色只改这一处即可，无需同步前后端 |
| `src/demo_app/voice_resolver.py` | 删除硬编码 `COSYVOICE_VOICE_CATALOG`；新增 `_load_voice_catalog_from_yaml()` 模块加载时读 yaml；`reload_voice_catalog()` 支持热加载；`get_voice_catalog_for_frontend()` 生成前端格式（含 `label` 字段）。`COSYVOICE_VOICE_CATALOG` 模块级变量保留作为向后兼容导入名，由 yaml 派生而非硬编码 |
| `src/webapp/handlers.py` | 新增 `VoiceCatalogHandler` 处理 `GET /api/voice_catalog`，返回 `get_voice_catalog_for_frontend()` 结果 |
| `src/webapp/routes.py` | 注册 `/api/voice_catalog` 路由 |
| `static/app.js` | `COSYVOICE_VOICE_CATALOG` 从 `const` 改为 `let`（初值 `{}`）；新增 `loadVoiceCatalog()`，`init()` 中并发 fetch + await；删除所有硬编码音色数据 |
| `tools/tts/cosyvoice_concurrency_probe.py` | 新增并发实测脚本（5 等级 × 3 轮 × 6 样本），实测报告写入 `runtime/cosyvoice_probe_full.json` |

**关键结论 — CosyVoice 并发实测（2026-05-13）：** 服务端为单 GPU 队列，吞吐**恒定 6.1 cps**（所有并发等级），并发对总耗时无收益但显著恶化单段 p50（串行 3.5s → 8 并发 32.6s）。`max_concurrency=1` 是最优解。详见 `runtime/cosyvoice_probe_full.json` 和 `tools/tts/cosyvoice_concurrency_probe.py`。

**扩音色流程（已验证）：**
1. 编辑 `config/runtime.yaml` 的 `tts.real_human.voice_catalog` 加一条
2. 重启服务器 → `voice_resolver` 模块加载时自动从 yaml 重读
3. 浏览器刷新页面 → `init()` 调 `/api/voice_catalog` 拉到最新值

### 近期变更（2026-05-10，第三批）

| 文件 | 改动 |
|------|------|
| `src/webapp/task_runner.py` | `_concat_audio_segments()`：concat demuxer（`-f concat`）→ **filter_complex concat**（`[0:a][1:a]...concat=n=N:v=0:a=1[aout]`），全段先解码为 PCM 再拼接重编码，对输入格式/采样率差异完全兼容，消除拼接点爆音/跳帧；单片段路径补 `run_in_executor` 避免阻塞事件循环 |
| `src/webapp/task_runner.py` | `_fallback_edge_tts()`：edge_tts 合成后新增 ffmpeg 重编码步骤（`-ar 44100 -ac 1`），统一降级片段与 real_human 片段的格式，避免 24kHz stereo 混入 44100Hz mono 拼接链；修复 `raw_path.rename()` 在 Windows 目标已存在时报 `FileExistsError`（改为 `replace()`）；修复 `with_suffix(".raw.mp3")` 在 Python 3.12+ 报 `ValueError`（改为 `parent / f"{stem}.raw.mp3"`）；全函数 `get_event_loop` → `get_running_loop` |
| `src/webapp/task_runner.py` | `_convert_wav_to_mp3()`：重新启用 silenceremove，改用极保守阈值 **-65dB**（原 -40dB 阈值误删正常语音，本次修复）；`start_duration=0.05s`、`stop_duration=0.15s`，仅裁 CosyVoice 数字静音（~-90dB），不影响正常语音（> -40dB） |

### 近期变更（2026-05-10，第二批）

| 文件 | 改动 |
|------|------|
| `static/app.js` | 新增 `submitEdgeTtsTask()`：合成音色模式改为提交平台任务队列（非阻塞），与真人音色行为一致；`submitAudioGeneration()` 增加 edge_tts 分支；按钮文案 → "真人音色生成音频" / "合成音色生成音频" |
| `static/app.js` | `gatherRealHumanVoiceAssignments()`：校验改为对**全局**注册音色验证（允许跨语言显式使用）；`ensureVoiceAssignmentsShape()`：`cycleVoices` 改为 maryzhang 固定排第一（任意语言任务 Speaker1=maryzhang，Speaker2=willwu），确保合成质量最好的音色优先分配给主说话人 |
| `static/app.js` | 手动模式新增主题输入框：`el.manualTopic`、`readFormFromDom`、`syncFormToDom`、事件监听；`currentTitle()` 已有逻辑，提交时 `topic` 自动使用输入标题 |
| `static/index.html` | `#manualSection` 新增 `id="manualTopic"` 输入框（主题标题，可选，提交后作为音频文件标题） |
| `src/demo_app/voice_resolver.py` | `resolve_voice_spec()`：voice_id 校验改为对全局注册音色（跨所有语言），允许跨语言克隆音色显式使用 |
| `src/webapp/task_runner.py` | `_synthesize_one_segment()`：WAV→MP3 失败时改为降级 edge_tts（不再保留 WAV 进 concat，避免 codec 混合导致逐字播放） |
| `src/webapp/task_runner.py` | `_convert_wav_to_mp3()`：暂时移除 silenceremove（-40dB 误删正常语音，待后续以保守阈值重新引入） |

### 近期变更（2026-05-10，第一批）

| 文件 | 改动 |
|------|------|
| `src/demo_app/tts_provider.py` | 新增：VoiceSpec / SynthesisRequest / SynthesisResult / ProviderCapabilities 数据模型 + TTSProvider ABC |
| `src/demo_app/real_human_tts.py` | 新增：RealHumanProvider（CosyVoice `/v1/audio/speech`），`_classify_error` 含异常类型名，`error_msg` 字段截断 300 字 |
| `src/demo_app/voice_resolver.py` | 新增：COSYVOICE_VOICE_CATALOG + resolve_voice_spec + build_synthesis_requests（max_chars=500 段落合并）；`resolve_voice_spec` 初版加语言校验 |
| `src/webapp/task_runner.py` | `_synthesize_with_real_human`：asyncio.gather 并发 + Semaphore 限流；`_synthesize_one_segment`：单段合成 + 超时重试 + WAV→MP3 转换；`_convert_wav_to_mp3`：`-ar 44100 -ac 1` 统一格式；`_concat_audio_segments`：`-ar 44100 -ac 1` 标准化输出；`list_tasks` JOIN audio_files 获取 file_duration |
| `src/webapp/db.py` | `list_tasks()` 改为 `LEFT JOIN audio_files` 带回 `file_duration` 字段，任务卡片可显示音频时长 |
| `config/runtime.yaml` | `tts.real_human.max_concurrency` 3→1（防并发响应串扰）；`timeout_sec` 120；`max_retries` 2；完整 voice_catalog 配置 |
| `static/app.js` | 新增 `COSYVOICE_VOICE_CATALOG`（中/英）；`ttsEngine` 默认 `"real_human"`；`gatherRealHumanVoiceAssignments` 加语言目录校验；音色标签去掉语言后缀 |
| `static/index.html` | 真人音色按钮置左并默认选中；tts_meta 诊断表格（含 `error_msg` 红字行）；进度条改为 `onmousedown` 支持拖拽（detail + mini player）；任务卡片显示 `⏱ 时长` |

### 近期变更（2026-05-08，commit 14eebec9）

| 文件 | 改动 |
|------|------|
| `src/demo_app/training_few_shot.py` | `_MIN_NEW_SAMPLE_SCORE` 70→65（覆盖全部 v3 通过样本）；`_MAX_EXCERPT_CHARS` 600→1200；long tier 样本 +15 分优先排序 |
| `training/training_executor.py` | 超时从固定 300s 改为自适应 `max(300, word_count//50)`，修复大字数任务超时无记录问题 |
| `server_platform.py` | 启动时调用 `invalidate_index()`，确保每次重启加载最新训练数据 |

Few-shot 索引现有 **4115 条**（v3 long 934 + v3 short 1033 + v2 1203 + 旧语料 945），覆盖 176 个（场景×语言）组合。

### 近期变更（2026-05-07，commit 9efbba27）

| 文件 | 改动 |
|------|------|
| `src/demo_app/embedded_server_main.py` | VOICE_CATALOG 替换废弃音色：`en-US-DavisNeural`→`BrianNeural`，`ru-RU-DariyaNeural`→`SvetlanaNeural` |
| `src/webapp/task_runner.py` | 合成完成后读取 `audio_result["warning"]`，写入 `error_msg="[TTS_WARN] ..."`，任务卡片正确显示⚠️备用引擎状态 |
| `src/webapp/handlers.py` | `_import` 路径支持 `tts_warning` 字段写入 DB |
| `static/app.js` | 全量音色审计：移除 28 个废弃 Neural 音色（日/韩/英/俄等），保留 56 个有效音色 |
| `static/index.html` | 默认主题改为浅色；底部 LAN 分享栏；任务卡片 TTS 回退橙色警告；语言名称显示中文；首页统计卡等高铺满 |

### 近期变更（2026-05-05）

| 文件 | 改动 |
|------|------|
| `static/index.html` | 任务页改为每页 18 条 + 首/上/下/末分页控件；API 请求上限从 50 → 200 |
| `static/app.js` | 生成开始/结束时调用 `window._incLegacyInProgress` / `_decLegacyInProgress`，使首页统计卡"进行中"数量正确反映 legacy 模态框的生成状态 |

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

## 🎙 真人 TTS API 接入 — Phase 1 已完成（2026-05-10）

**Phase: Phase 1 全部上线 ✅。CosyVoice `/v1/audio/speech` 端点已接入，中英文真人克隆音色可用。**

### 已实现文件

```
src/demo_app/
  tts_provider.py      ← VoiceSpec / SynthesisRequest / SynthesisResult / ProviderCapabilities 数据模型 + TTSProvider ABC
  real_human_tts.py    ← RealHumanProvider（CosyVoice /v1/audio/speech 同步端点）
  voice_resolver.py    ← 单源加载 voice_catalog (from runtime.yaml) + resolve_voice_spec + build_synthesis_requests
  │                       + get_voice_catalog_for_frontend + create_voice_in_catalog + delete_voice_from_catalog
  │                       + _save_voice_catalog_to_yaml（逐行替换，保留所有注释）
src/webapp/
  handlers.py          ← VoiceCatalogHandler (GET) + VoiceCreateHandler (POST) + VoiceDeleteHandler (DELETE)
tools/
  test_voice_e2e.py    ← E2E 测试：create → verify catalog → verify yaml → delete
```

### CosyVoice API 关键信息

- **端点**：`POST /v1/audio/speech`（OpenAI-compatible，JSON body → WAV bytes 直接返回）
- **废弃端点**：`/api/tts/async`（zero_shot 模式需要 `prompt_wav`，仅传 `spk_id` 报 "Invalid file: None"）
- **请求格式**：`{"model": "cosyvoice-v3", "input": "<text>", "voice": "<voice_id>", "response_format": "wav", "speed": 1.0}`
- **当前注册音色**（`GET /v1/voices/custom`，2026-05-16 更新；服务器还有 8 个同名"李四"，5 个可用、3 个返回 500，本平台仅挂载 created_at 最晚的 `ed35d3674bb0`，备用 voice_id 见 runtime.yaml 注释）：

| 语言 | voice_id | 名称 | 性别 | 状态 |
|------|----------|------|------|------|
| Chinese | `36d3429a3c98` | maryzhang | female | ✅ 可用 |
| Chinese | `ed35d3674bb0` | lisi | male | ✅ 可用 |
| Chinese | `06b1d3b50f22` | AI-男音 | male | ✅ 可用（2026-05-16 新增）|
| English | `c3e9f75ae993` | willwu | male | ✅ 可用 |
| English | `1d8c3af1d010` | AI-男音2 | male | ✅ 可用（2026-05-16 新增）|

**新增音色：** 只改 `config/runtime.yaml` 的 `tts.real_human.voice_catalog` → 重启服务器 → 刷新浏览器。后端 `voice_resolver._load_voice_catalog_from_yaml()` 启动时读 yaml；前端 `app.js` 启动时调 `/api/voice_catalog` 拉同一份数据。**三处副本时代已结束**（2026-05-13 单源化）。

### 真人 TTS 合成流程（`task_runner._synthesize_with_real_human`）

1. 从 DB 读取 `voice_assignments`（JSON）→ `build_synthesis_requests()` 将 `line_tuples` 合并为段落级请求（同 speaker 连续行合并，最大 500 字）
2. `asyncio.gather` + `asyncio.Semaphore(max_concurrency)` 并发合成（当前 `max_concurrency=1`，串行安全）
3. 每段调用 `RealHumanProvider.synthesize()` → `_call_speech_v1()` 在 `run_in_executor` 线程中执行 HTTP 请求
4. 超时时按 `max_retries` 重试（当前配置 2 次）
5. 最终失败 → `_fallback_edge_tts()` 降级合成
6. **WAV→MP3 + 静音裁剪**：real_human 成功后调用 `_convert_wav_to_mp3()`，`silenceremove` 过滤器去除头部（≥50ms）和过长尾部静音（保留最多 300ms），`-ar 44100 -ac 1` 统一格式
7. **WAV→MP3 失败时**：不再保留 WAV 进入 concat（会导致 codec 混合 → 逐字播放），改为降级 edge_tts 确保格式统一
8. `_concat_audio_segments()` 用 ffmpeg concat demuxer 拼接所有 MP3 片段，`-ar 44100 -ac 1` 标准化输出

### 并发安全注意事项

- **`max_concurrency: 1`（当前默认）**：串行合成，防止 CosyVoice 服务器并发响应串扰（高并发时曾出现响应内容写入错误片段文件，导致音频重复）
- 若要提速可调为 2，但 ≥3 时 CosyVoice 在负载下偶发响应混淆
- WAV 和 MP3 **绝对不能混合** concat：ffmpeg concat demuxer 要求所有输入 codec 相同，WAV(pcm)/MP3 混合会导致逐字播放或噪音。WAV→MP3 失败时必须降级 edge_tts，不可将 WAV 放入 concat 列表

### voice_id 音色分配规则

**自动分配（`ensureVoiceAssignmentsShape`）**：`cycleVoices` 优先从当前任务语言的目录循环，防止英语任务自动分配到中文音色（maryzhang 合成英文会逐字发音甚至输出中文）。当前语言无专属音色时扩展到全局。

**显式选择验证（`gatherRealHumanVoiceAssignments` + `voice_resolver.resolve_voice_spec`）**：只要 voice_id 在全局注册音色中存在即合法（跨语言显式使用允许，如用 willwu 合成中文）。真正无效的 voice_id（未注册）才被替换为默认音色。

---

## 🗂 仓库维护记录

### Git 历史瘦身（2026-05-05）

用 `git filter-repo` 从所有历史提交中永久删除了以下大文件，并 force push 覆盖了 GitHub：

| 路径 | 原大小 | 说明 |
|------|--------|------|
| `build/DialogDemo/DialogDemo.pkg` | 108 MB | 老 Mac 二进制（通过 Git LFS 存储） |
| `build/demo_app/PYZ-00.pyz` | 11.7 MB | PyInstaller 中间产物，不应提交 |
| `demo/20260308_183515/*.wav` | 9.9 MB | 早期测试音频 |
| `output/payment_5step/*.mp3` | 5.6 MB | 早期输出音频 |

清理结果：`.git/` 从 **329 MB → 62 MB**（节省 267 MB）。

> `.gitattributes` 中保留了 `build/DialogDemo/DialogDemo.pkg filter=lfs` 规则（历史遗留），该文件路径已不再存在，不影响任何功能。

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
  README.md
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
  run_all_batches.py               ← B0→B5 sequential runner (v2, superseded)
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
| `tasks` | task_id, status, generation_mode, topic, language, people_count, word_count, error_msg, file_id, voice_map, output_format, keywords, template, custom_prompt, input_text, include_scripts | statuses: queued → generating_text → synthesizing → completed / failed；参数拆列存储（无 params_json） |
| `folders` | folder_id, name, parent_id | used to group files in 我的文件 view |

**Phase 1 已新增列（`db._run_tts_migration()` 幂等执行）：**

| 表 | 列 | 说明 |
|----|----|------|
| `tasks` | `tts_provider` TEXT DEFAULT 'edge_tts' | 期望 provider（`edge_tts` / `real_human`） |
| `tasks` | `tts_fallback_strategy` TEXT DEFAULT 'edge_then_bundle' | 降级策略 |
| `tasks` | `voice_assignments` TEXT DEFAULT '{}' | 新格式音色参数 JSON，格式：`{"1": {"provider":"real_human","voice_id":"36d3429a3c98"}}` |
| `audio_files` | `tts_meta` TEXT DEFAULT NULL | 逐段合成诊断 JSON（provider、latency、degraded_reason、error_msg 等） |

`list_tasks()` 通过 `LEFT JOIN audio_files` 附带 `file_duration` 字段（用于任务卡片时长显示），不影响其他查询。

`src/webapp/db.py` provides all helpers; `src/webapp/task_runner.py` polls for queued tasks and drives them through the status machine.

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
4. Few-shot example injected: `get_topic_few_shot_example(template_label, language)` → 优先查 `output/training_v3/*/passed/`（v3 long tier 优先），回退到旧语料库 `demo-data/training_long_dialogue/`
5. `_generate_long_dialogue_lines()` → calls bundle LLM, loops with dedup until word-count target is met
6. Three post-processing passes: `repair_dialogue_quality` → `merge_keywords_into_lines` → `stabilize_dialogue_constraints`
7. Written to `demo-data/{timestamp}/{basename}.txt` + `manifest.json`; registered in in-memory LRU cache (`_manifest_cache`, 500-entry cap)

**Audio synthesis (`POST /api/synthesize_audio`)**
1. Manifest looked up from cache/disk (`_find_manifest`)
2. Each dialogue line assigned an edge_tts voice (`_voice_for_speaker` → `VOICE_CATALOG`)
3. Phase 0: `asyncio.gather` with `Semaphore(5)` fans out concurrent `edge_tts.Communicate.save()` calls
4. Phase 0b: failed segments retried sequentially; Phase 0c: still-failed → raise → bundle fallback
5. `pydub` probes segment durations (read-then-discard, no accumulation)
6. `subprocess.run(ffmpeg -f concat …)` stitches segments; temp `.mp3` files cleaned up in `finally`
7. Returns `warning: "edge_tts_fallback:..."` if bundle fallback was used

**TTS voice catalog (`VOICE_CATALOG` in `embedded_server_main.py`)**

56 working voices across 13 languages (28 deprecated voices removed 2026-05-07). Backend auto-assignment uses `VOICE_CATALOG`; frontend dropdown uses `VOICE_LIBRARY` in `app.js`. Both were updated in the same audit.

**Platform task generation (`POST /api/platform/tasks` → task worker)**
1. Payload params stored as individual columns in DB (no params_json), status set to `queued`；`tts_provider`（edge_tts / real_human）、`voice_assignments`（JSON）同步写入
2. `src/webapp/task_runner.py` polling loop picks up queued tasks
3. **edge_tts 路径**：调用 `_synthesize_audio_from_lines()`（legacy pipeline）
4. **real_human 路径**（`tts_provider == "real_human"`）：调用 `_synthesize_with_real_human()` → `build_synthesis_requests` 合并段落 → asyncio.gather + Semaphore 并发合成 → WAV→MP3 格式统一 → ffmpeg concat
5. On success: writes audio to `storage/generated/`，`tts_meta` JSON 写入 DB；if `audio_result["warning"]` is set, stores `error_msg="[TTS_WARN] ..."` 显示橙色降级警告
6. On failure: stores error_msg, sets status `failed`

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
- 最低分门槛 65（覆盖所有 passed 样本），excerpt 长度 1200 字符

**旧语料库**（回退来源）
- 路径：`demo-data/training_long_dialogue/`（force-tracked）
- 630 个文件：14 domains × 9 languages × 5 speaker variants（spk2–spk6）
- `few_shot_selector.py` 通过 `_DOMAIN_TO_ID` / `_LANG_TO_SHORT` 映射查找

索引在服务器启动时清除（`invalidate_index()`），首次请求时懒加载重建。

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
