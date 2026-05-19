# 真人 TTS 接入与音色管理 — 功能改造说明文档

> 覆盖范围：截止 2026-05-19  
> 对应 UI 功能：生成弹窗中的「真人音色」选项卡 + 「管理真人音色」按钮  
> 涉及改动文件：5 个后端 Python 文件 + 2 个前端文件 + 1 个配置文件

---

## 目录

1. [功能总览](#1-功能总览)
2. [架构概览](#2-架构概览)
3. [功能一：真人 TTS 合成接入](#3-功能一真人-tts-合成接入)
4. [功能二：真人音色管理](#4-功能二真人音色管理)
5. [文件改动清单](#5-文件改动清单)
6. [数据流与调用链](#6-数据流与调用链)
7. [配置项说明](#7-配置项说明)
8. [关键设计决策与注意事项](#8-关键设计决策与注意事项)

---

## 1. 功能总览

### 这两个功能是什么

| 功能 | 一句话描述 |
|------|-----------|
| **真人 TTS 接入** | 将对话文本通过 CosyVoice 零样本克隆 API 合成为克隆自真人声音的音频，替代原有合成音色（edge_tts） |
| **真人音色管理** | 在平台内在线注册新克隆音色（上传参考音频）、删除、重命名，无需手动改配置文件 |

### UI 位置

```
生成弹窗
├── 🎙 真人音色     ← 选择已注册的克隆音色，提交后走 CosyVoice 合成路径
├── ⚙️ 管理真人音色 ← 打开音色管理弹窗（注册/删除/重命名）
└── 🔊 合成音色     ← 原有 edge_tts 路径（未改动）
```

---

## 2. 架构概览

### 新增模块层次

```
config/
  runtime.yaml                  ← 唯一权威音色目录（voice_catalog）

src/demo_app/
  tts_provider.py               ← 数据模型层（VoiceSpec / SynthesisRequest / SynthesisResult）
  real_human_tts.py             ← CosyVoice HTTP 实现（RealHumanProvider）
  voice_resolver.py             ← 音色解析 + 目录 CRUD + YAML 持久化

src/webapp/
  handlers.py                   ← 3 个新 API Handler（Catalog / Create / Delete+Patch）
  task_runner.py                ← 真人合成主流程（_synthesize_with_real_human）

static/
  app.js                        ← 前端音色选择、自动分配、管理弹窗逻辑
  index.html                    ← 管理弹窗 HTML + CSS 修复
```

### 与外部服务的关系

```
语料平台（本项目）
    ↕ HTTP（LAN）
CosyVoice 服务器（10.0.20.10:8188）
    ↓ 模型推理
NVIDIA L20 GPU（Fun-CosyVoice3-0.5B）
```

---

## 3. 功能一：真人 TTS 合成接入

### 3.1 新增文件说明

#### `src/demo_app/tts_provider.py` — 数据模型层

定义跨 Provider 通用的数据结构，不含任何业务逻辑：

| 类 | 作用 |
|----|------|
| `VoiceSpec` | 音色参数对象（provider / voice_id / language / gender / speed 等） |
| `SynthesisRequest` | 段落级合成请求（speaker + 连续文本列表 + voice_spec + 行号） |
| `SynthesisResult` | 合成结果（实际 provider / 是否降级 / 延迟 / 错误信息等） |
| `ProviderCapabilities` | Provider 能力声明（是否支持 SSML / 多说话人 / 字级时间戳等） |
| `TTSProvider` | 抽象基类，定义 `synthesize()` 接口 |

#### `src/demo_app/real_human_tts.py` — CosyVoice Provider 实现

**调用的 CosyVoice 接口：**

```
POST /v1/audio/speech
请求体（JSON）：
  {
    "model":           "cosyvoice-v3",
    "input":           "<文本>",
    "voice":           "<voice_id>",
    "response_format": "wav",
    "speed":           1.0
  }
响应：WAV 音频字节流（直接返回，无需轮询）
```

**为什么不用旧版 `/api/tts/async`？**  
旧版接口的 `zero_shot` 模式要求每次合成都上传参考音频文件（`prompt_wav` 字段），无法单独传 `voice_id`。而 `/v1/audio/speech` 是 OpenAI-compatible 接口，只需 voice_id，CosyVoice 服务端内部查缓存的 speaker embedding。

**HTTP 异步化处理：**  
`_call_speech_v1()` 是同步 HTTP 请求（使用 `requests` 库），通过 `asyncio.run_in_executor(None, ...)` 放入线程池执行，不阻塞 Tornado 事件循环。

**错误分类（`_classify_error`）：**

| 错误类型 | `degraded_reason` 字段值 |
|---------|------------------------|
| 请求超时 | `timeout` |
| HTTP 429 | `rate_limit` |
| HTTP 401/403 | `auth_failure` |
| HTTP 400 | `param_error:<ExcType>` |
| 其他 HTTP | `http_<code>:<ExcType>` |
| 音频文件过小 | `empty_audio` |

#### `src/demo_app/voice_resolver.py` — 音色解析与目录管理

**核心职责：**

| 函数 | 职责 |
|------|------|
| `_load_voice_catalog_from_yaml()` | 启动时从 runtime.yaml 加载音色目录 |
| `reload_voice_catalog()` | 热重载，注册/删除操作后自动调用 |
| `_save_voice_catalog_to_yaml(catalog)` | 逐行替换 yaml 中的 `voice_catalog` 块，**保留所有注释** |
| `resolve_voice_spec(speaker_id, ...)` | 按优先级解析音色：voice_assignments → voice_map → 自动分配 |
| `build_synthesis_requests(line_tuples, ...)` | 将对话行列表按说话人合并为段落级请求 |
| `create_voice_in_catalog(...)` | 添加新音色到目录 |
| `delete_voice_from_catalog(voice_id)` | 从目录删除音色 |
| `update_voice_in_catalog(voice_id, name)` | 更新音色名称 |
| `get_voice_catalog_for_frontend()` | 生成前端格式（含 label 字段，如"青年-英文（男·真人）"） |

**`_save_voice_catalog_to_yaml` 的特殊设计：**  
直接用 `yaml.dump()` 写整个文件会丢失 runtime.yaml 中的所有注释（备用 voice_id 列表、失效音色记录等）。该函数改用逐行定位替换：
1. 找到 `    voice_catalog:` 行（4-space 缩进）
2. 找到下一个同级或更高级 key 为止
3. 只替换中间那段，文件其余部分原样保留

**音色解析优先级：**

```
voice_assignments（DB 存储，精确指定 provider + voice_id）
    ↓ 未找到
voice_map（旧格式，仅 edge_tts）
    ↓ 未找到
default_voice_spec（按语言自动轮转音色）
```

### 3.2 合成主流程（`task_runner._synthesize_with_real_human`）

```
Step 1  从 DB 读取 voice_assignments（JSON）、voice_map
Step 2  加载 RealHumanProvider（读 runtime.yaml api_url + 环境变量）
Step 3  从 runtime.yaml 读取 max_concurrency / max_retries / max_chars_per_segment
Step 4  build_synthesis_requests() — 同说话人连续行合并为段落，单段不超 max_chars
Step 5  asyncio.gather + Semaphore 并发合成所有段落
           每段调用 _synthesize_one_segment()
           → RealHumanProvider.synthesize() → _call_speech_v1() → WAV
           → _convert_wav_to_mp3() — silenceremove + 格式统一（44100Hz mono）
           → 失败时 _fallback_edge_tts()（重编码为 44100Hz mono，消除拼接点爆音）
Step 6  _concat_audio_segments() — ffmpeg filter_complex concat 拼接所有 MP3
           （全段解码为 PCM 再重编码，消除不同来源音频的格式差异）
Step 7  返回结果字典（audio_file_path / tts_meta JSON / warning）
```

**并发策略：**  
`max_concurrency=1`（串行）是最优解。CosyVoice 服务端为单 GPU 队列，无论多少路并发，总吞吐恒定约 6 chars/s。增加并发只会拉高单段延迟（1路=3.5s，8路=32.6s），且高并发下偶发响应内容互相写入错误文件的 bug。

**降级链：**

```
RealHumanProvider 失败（超时 / HTTP 500）
    ↓
_fallback_edge_tts()（边缘 TTS 补位该段）
    ↓ 注意：WAV 不能混入 concat（codec 不同会导致逐字播放）
    ↓ 降级段必须先重编码为 44100Hz mono MP3 再进 concat 列表
```

### 3.3 前端音色选择逻辑

**音色目录加载（`loadVoiceCatalog`）：**  
`init()` 中并发 fetch `/api/voice_catalog`，返回按语言分组的音色列表，赋值给 `COSYVOICE_VOICE_CATALOG`（`let` 变量，运行时动态替换，取代原硬编码 `const`）。

**自动分配（`ensureVoiceAssignmentsShape`）：**  
- 优先从当前任务语言的目录按 Speaker 序号轮转分配
- 当前语言无专属音色时扩展到全局（允许跨语言使用克隆音色）
- `cycleVoices` 固定将质量最好的音色排第一，保证主说话人（Speaker 1）分配到最优音色

**显式选择验证（`gatherRealHumanVoiceAssignments`）：**  
只验证 voice_id 是否在全局已注册音色中存在，不限制语言匹配（允许跨语言显式使用）。

---

## 4. 功能二：真人音色管理

### 4.1 API 接口

| 方法 | 路径 | Handler | 功能 |
|------|------|---------|------|
| `GET` | `/api/voice_catalog` | `VoiceCatalogHandler` | 获取前端格式音色目录 |
| `POST` | `/api/voice_catalog/create` | `VoiceCreateHandler` | 上传参考音频注册新克隆音色 |
| `DELETE` | `/api/voice_catalog/<voice_id>` | `VoiceDeleteHandler` | 删除音色（可选同步删除 CosyVoice 服务端） |
| `PATCH` | `/api/voice_catalog/<voice_id>` | `VoiceDeleteHandler.patch` | 仅更新本地目录中的音色名称 |

> **注意路由顺序**：`/api/voice_catalog/create` 在 routes.py 中必须注册在 `/api/voice_catalog/([^/]+)` 之前，否则 `create` 会被当成 voice_id 参数匹配到 Delete Handler。

### 4.2 注册新音色流程（`VoiceCreateHandler.post`）

```
前端 multipart 请求：
  audio    = 参考音频文件（3-30 秒，WAV 最佳）
  name     = 音色名称
  language = Chinese / English / ...
  gender   = female / male
  text     = 参考文本（可选，留空服务端 ASR 自动识别）

Step 1  参数校验（audio / name 必填）
Step 2  POST /v1/voices/create → CosyVoice 服务器
          响应格式容错：result["id"] || result["voice_id"] || result["voice"]["id"]
          若都为空 → GET /v1/voices/custom 取最新一条 voice_id
Step 3  ⚠️ 合成可用性验证（关键步骤）
          POST /v1/audio/speech 用新 voice_id 合成一句短文本
          若 HTTP 状态 ≠ 200 或响应 < 1000 bytes → 拦截
          → DELETE /v1/voices/{voice_id} 清理无效音色
          → 返回 HTTP 422 + 说明（参考音频质量不足）
Step 4  验证通过 → create_voice_in_catalog() 写入 runtime.yaml → 热重载
Step 5  返回 HTTP 201 + {voice_id, name, language, gender}
```

**为什么需要合成验证？**  
CosyVoice 的 `/v1/voices/create` 接口总是返回 200，无论参考音频质量如何。真正的质量检验发生在首次合成时（GPU 提取 speaker embedding），质量不足则合成返回 HTTP 500。通过 smoke test 可以在写入目录前拦截无效音色，避免用户注册后才发现不可用。

### 4.3 删除音色（`VoiceDeleteHandler.delete`）

```
query param: delete_remote=1（默认）/ 0

若 delete_remote=1 且 api_url 已配置：
    → DELETE /v1/voices/{voice_id}（CosyVoice 服务端）
    → 非 404 失败只记 warning，不阻断本地删除

始终执行：
    → delete_voice_from_catalog(voice_id)（从 runtime.yaml 移除 + 热重载）
    → 若本地目录无此 voice_id → HTTP 404
```

### 4.4 重命名音色（`VoiceDeleteHandler.patch`）

```
PATCH /api/voice_catalog/<voice_id>
请求体：{"name": "新名称"}

→ update_voice_in_catalog(voice_id, name)
→ 仅修改本地 runtime.yaml 的 name 字段
→ CosyVoice 服务端无重命名 API，服务端名称不同步（不影响合成功能）
```

### 4.5 音色管理弹窗（前端）

**弹窗入口：** `⚙️ 管理真人音色` 按钮（`openVoiceMgmt()`）

**功能区块：**

```
┌─ 注册新音色 ──────────────────────────────────┐
│ 上传参考音频（文件选择）                         │
│ 音色名称（必填）                                │
│ 语言选择（Chinese / English / ...）            │
│ 性别选择（女 / 男）                             │
│ 参考文本（可选，留空 ASR 自动识别）               │
│ [注册音色] 按钮                                 │
│ 等待提示：正在上传并注册，随后验证合成（约30-90s）│
└──────────────────────────────────────────────┘

┌─ 已注册音色列表 ────────────────────────────────┐
│ 行格式：名称 | 语言·性别 | voice_id | ✏️ | 🗑️  │
│ ✏️ 点击：名称 span → 输入框，显示 Save/Cancel    │
│    Enter = 保存，Escape = 取消                  │
│ 🗑️ 点击：弹出确认框 → DELETE API               │
└──────────────────────────────────────────────┘
```

**内联编辑实现（`vmRefreshList` 中的 `enterEdit` / `exitEdit` / `doSave`）：**

```
enterEdit()：隐藏名称 span，显示输入框（自动聚焦+全选），隐藏✏️/🗑️，显示 Save/Cancel
doSave()：PATCH /api/voice_catalog/{voice_id}
    成功 → 更新 span 文本 + 重载目录 + renderVoiceRows() + showToast
exitEdit()：恢复到只读状态
```

**z-index 修复（confirm 弹框被遮挡问题）：**  
管理弹窗使用 `openVoiceMgmt()` 中设置 `zIndex: 9999` 的内联样式（绕过 CSS 缓存）。删除确认弹框（`#confirm-overlay`）原 CSS z-index 为 300，会被遮挡。  
修复方案：CSS 改为 `z-index: 20000`，同时在 `showConfirm()` 中通过内联 style 强制设置，`closeConfirm()` 中清除内联 style，保证跨弹窗层级正确。

---

## 5. 文件改动清单

### 后端文件

| 文件 | 改动类型 | 主要内容 |
|------|---------|---------|
| `src/demo_app/tts_provider.py` | **新增** | VoiceSpec / SynthesisRequest / SynthesisResult / ProviderCapabilities / TTSProvider ABC |
| `src/demo_app/real_human_tts.py` | **新增** | RealHumanProvider（CosyVoice /v1/audio/speech 接入）+ load_real_human_provider() |
| `src/demo_app/voice_resolver.py` | **新增** | 全文件新增；音色目录 CRUD + YAML 持久化 + 音色解析 + 段落合并 |
| `src/webapp/handlers.py` | **新增类** | VoiceCatalogHandler / VoiceCreateHandler / VoiceDeleteHandler（含 PATCH）；CORS 头加入 PATCH |
| `src/webapp/routes.py` | **新增路由** | `/api/voice_catalog`、`/api/voice_catalog/create`、`/api/voice_catalog/([^/]+)` |
| `src/webapp/task_runner.py` | **改造** | 新增 `_synthesize_with_real_human` 及全套辅助函数（_synthesize_one_segment / _convert_wav_to_mp3 / _fallback_edge_tts / _concat_audio_segments）；list_tasks JOIN file_duration |
| `src/webapp/db.py` | **新增列** | tasks 表：tts_provider / tts_fallback_strategy / voice_assignments；audio_files 表：tts_meta；list_tasks LEFT JOIN |

### 前端文件

| 文件 | 改动类型 | 主要内容 |
|------|---------|---------|
| `static/app.js` | **改造** | COSYVOICE_VOICE_CATALOG 改为 let + loadVoiceCatalog() 动态拉取；新增 openVoiceMgmt / vmHandleFile / vmRefreshList / vmDeleteVoice / vmSubmit；submitEdgeTtsTask()；gatherRealHumanVoiceAssignments 跨语言校验；ensureVoiceAssignmentsShape 优先分配 |
| `static/index.html` | **改造** | 新增 #modal-voice-mgmt 弹窗 HTML；.confirm-overlay z-index 300→20000；showConfirm/closeConfirm 内联 style 修复；修复 CSS 变量拼写错误（--border1→--border，--text1→--text） |

### 配置文件

| 文件 | 改动类型 | 主要内容 |
|------|---------|---------|
| `config/runtime.yaml` | **新增配置块** | `tts.real_human`（api_url / timeout_sec / max_retries / max_concurrency / max_chars_per_segment / voice_catalog）；voice_catalog 成为前后端唯一权威源 |

---

## 6. 数据流与调用链

### 合成音频（任务队列路径）

```
前端提交任务（POST /api/platform/tasks）
    │  payload: tts_provider="real_human", voice_assignments={"1":{...},"2":{...}}
    ↓
task_runner._process_task(task_id)
    │  读取 task.tts_provider == "real_human"
    ↓
_synthesize_with_real_human(line_tuples, language, save_dir, basename, task)
    ├── load_real_human_provider(runtime_cfg)   → RealHumanProvider 实例
    ├── build_synthesis_requests(line_tuples)   → [SynthesisRequest, ...]（段落合并）
    └── asyncio.gather(_synthesize_one_segment × N)
            ├── RealHumanProvider.synthesize(req, wav_path)
            │       └── _call_speech_v1(text, voice_id, speed, wav_path)  [线程池]
            │               → POST /v1/audio/speech → WAV bytes → 写文件
            ├── 成功 → _convert_wav_to_mp3(wav_path, mp3_path)
            │           → ffmpeg silenceremove + -ar 44100 -ac 1
            └── 失败 → _fallback_edge_tts(req, mp3_path)
                        → edge_tts.Communicate + ffmpeg 重编码（44100 mono）
    ↓
_concat_audio_segments([mp3_1, mp3_2, ...], final_path)
    → ffmpeg filter_complex concat（全 PCM 解码再编码）
    ↓
写入 storage/generated/<task_id>/<basename>.mp3
写入 tts_meta JSON → tasks.tts_meta DB 列
```

### 注册新音色

```
前端 vmSubmit()
    │  multipart: audio + name + language + gender + text
    ↓
POST /api/voice_catalog/create
    ↓
VoiceCreateHandler.post()
    ├── POST /v1/voices/create → CosyVoice    [线程池]
    │       → 返回 voice_id（容错多种格式）
    ├── POST /v1/audio/speech（验证合成）     [线程池]
    │   ├── 失败 → DELETE /v1/voices/{id} 清理 → HTTP 422
    │   └── 成功 → 继续
    └── create_voice_in_catalog(language, voice_id, name, gender)
            ├── _save_voice_catalog_to_yaml(catalog)  ← 逐行替换，保留注释
            └── reload_voice_catalog()  ← 热重载模块级变量
    ↓
返回 HTTP 201 {voice_id, name, language, gender}
    ↓
前端 vmRefreshList()  ← 刷新列表展示新音色
loadVoiceCatalog()    ← 重新拉取目录，更新生成弹窗音色选项
```

### 音色目录同步机制（单源化）

```
runtime.yaml（唯一权威）
    ↑ 写入（_save_voice_catalog_to_yaml，注释保留）
    ↓ 读取（_load_voice_catalog_from_yaml，启动时 + 每次 CRUD 后热重载）

Python 端（COSYVOICE_VOICE_CATALOG 模块级变量）← reload_voice_catalog()
浏览器端（COSYVOICE_VOICE_CATALOG let 变量）   ← GET /api/voice_catalog + loadVoiceCatalog()
```

---

## 7. 配置项说明

`config/runtime.yaml` 中 `tts.real_human` 块：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `api_url` | `"http://10.0.20.10:8188"` | CosyVoice API 地址，优先被环境变量 `REAL_HUMAN_TTS_API_URL` 覆盖 |
| `timeout_sec` | `120` | 单段合成超时秒数，建议 ≥ 90（长文本 GPU 推理耗时） |
| `max_retries` | `2` | 超时后重试次数 |
| `max_concurrency` | `1` | 并发合成路数，**保持 1**（单 GPU 队列，并发无法加速，见注意事项） |
| `max_chars_per_segment` | `500` | 同说话人连续行合并上限（字符数），中文推荐 200-500，英文推荐 400-800 |
| `voice_catalog` | （见文件）| 已注册克隆音色的唯一权威来源，格式见下 |

**voice_catalog 格式：**

```yaml
voice_catalog:
  Chinese:
  - voice_id: 365689d1619b
    name: 青年-英文
    gender: male
  English:
  - voice_id: ce4ac76b992f
    name: 中年-英文
    gender: male
```

**新增音色的正确方式：**

> **方式 A（推荐）：通过平台 UI 注册**  
> 管理弹窗 → 上传参考音频 → 填写名称/语言/性别 → 点击注册  
> 平台自动完成注册 + 验证 + 写入 yaml + 热重载

> **方式 B（手动）：直接编辑 yaml**  
> 在 `voice_catalog` 下对应语言添加条目 → 重启服务器 → 刷新浏览器

---

## 8. 关键设计决策与注意事项

### ⚠️ max_concurrency 必须保持 1

CosyVoice 服务端为单 GPU 队列，吞吐量恒定约 6 chars/s，与并发数无关。  
实测数据（L20 GPU）：

| 并发数 | 单段 p50 延迟 | 总壁钟时间 |
|--------|-------------|----------|
| 1 | 3.5s | ~同 |
| 8 | 32.6s | ~同 |

增加并发只会让每段变慢，且高并发时偶发响应内容写入错误文件（内存竞争），导致音频重复/乱序。

### ⚠️ WAV 与 MP3 绝对不能混合 concat

ffmpeg concat demuxer 要求所有输入 codec 相同。real_human 成功段产出 WAV，edge_tts 降级段产出 MP3，混合 concat 会导致逐字播放或噪音。  
规则：**WAV 转 MP3 失败时，必须降级 edge_tts 重新合成该段**，不可将 WAV 直接放入 concat 列表。

### ⚠️ CosyVoice 注册 ≠ 可用

`/v1/voices/create` 始终返回 200，无论参考音频质量。真正的可用性检验在首次合成时（GPU speaker embedding 提取失败 → HTTP 500）。  
**参考音频质量要求：** 单人朗读、清晰无噪音、10-30 秒、无背景音乐、16kHz mono WAV 最佳。  
M4A/MP4 需先用 ffmpeg 转换：`ffmpeg -i input.m4a -ar 16000 -ac 1 output.wav`

### ⚠️ silenceremove 阈值必须保守

ffmpeg `silenceremove` 用于裁剪 CosyVoice 输出的前后静音。历史问题：`-40dB` 阈值会误删正常语音（正常语音强度通常 > -40dB）。  
当前配置：`-65dB`，仅裁剪 CosyVoice 数字零点静音（~-90dB），不影响正常语音。

### 音色单源化（2026-05-13 完成）

改造前：音色数据在三处维护（Python 硬编码 + 后端 Handler + 前端 JS const），三处易不同步。  
改造后：`config/runtime.yaml` 是唯一权威，Python 端和前端都从这一个来源读取，消除同步问题。

### PATCH 方法 CORS 配置

`VoiceDeleteHandler` 新增 `patch()` 方法后，`PlatformHandler.set_default_headers()` 中的 `Access-Control-Allow-Methods` 需加入 `PATCH`，否则跨域 PATCH 请求会被浏览器预检拦截（`OPTIONS` 返回不含 PATCH）。
