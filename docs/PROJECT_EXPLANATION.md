# 语料生成平台 — PROJECT_EXPLANATION.md

> 最后更新：2026-05-16 | 分析文件：深读 6 个，grep 8 个，推测 4 个

---

## 章节 1：项目总览 / Executive Summary

### 一句话定义

这是一个**多说话人对话语料批量生成平台**，用于为 AI 训练自动生成多语言对话文本，并支持 Microsoft edge_tts 合成音色和 CosyVoice 克隆真人音色两套 TTS 管线合成高质量音频。

### 核心能力

- **LLM 对话生成**：调用打包为 PyInstaller `.exe` 的 LLM Bundle，按 22 个行业模板生成自然对话脚本
- **真人克隆 TTS**：接入 CosyVoice `/v1/audio/speech`（OpenAI-compatible），支持零样本克隆音色合成
- **合成音色 TTS**：调用 Microsoft edge_tts Neural 声音，56 个有效音色，并发合成 + 自动重试
- **TTS 自动降级**：`real_human → edge_tts → bundle` 三级降级链，任意一级失败自动切换
- **三轮后处理**：`repair → keywords → stabilize` 三遍 LLM 后处理确保对话质量
- **平台文件管理**：上传、归档、标签、文件夹、软删除/回收站、批量操作
- **异步任务队列**：后台协程驱动，生成与合成全程异步，支持崩溃恢复
- **音色目录管理**：Web UI 上传参考音频注册克隆音色，单源配置（`runtime.yaml`），前后端自动同步
- **训练管道 v3**：4 语言并行批量生成，5 小时完成 1144 个 long-tier 任务，共 1937 条高质量样本

### 适合谁阅读

| 角色 | 建议章节 | 关注重点 |
|------|---------|---------|
| 新接手维护者 | 1→3→6 | 整体架构、文件地图、调用链 |
| 前端开发者 | 2→4（static/） | UI 功能、音色管理 API、任务状态机 |
| 后端开发者 | 4→7 | task_runner 真人 TTS 路径、voice_resolver、handlers |
| AI 训练工程师 | 2（训练管道）→7 | 训练批次、质量门禁、few-shot 索引 |
| DevOps / 运维 | 3→6（外部资源） | CosyVoice API 配置、依赖、进程、数据库 |

### 快速理解摘要

这个项目是一套**本地 Web 服务**，运行在 `http://127.0.0.1:8899/`。用户在浏览器里配置对话参数（行业、语言、说话人数、字数），后端调用内嵌 LLM 生成多轮对话脚本，再按用户选择的 TTS 引擎逐段合成音频——可以是微软 Neural 声音（edge_tts），也可以是通过 CosyVoice 克隆的真人声音（real_human）。所有段落最后由 ffmpeg filter_complex concat 拼接成完整 MP3。生成的文件通过 SQLite 数据库统一管理，支持文件夹组织、标签过滤、回收站还原。音色目录从 `config/runtime.yaml` 单一来源加载，新增音色只需编辑 yaml 并重启，前端通过 `/api/voice_catalog` 接口自动同步。平台同时具备训练管道，可批量生成 1937 条高质量对话样本并自动纳入 few-shot 索引。整个系统无外部云依赖（TTS API 和 LLM Bundle 除外），可在局域网内完全本地化运行。

---

## 章节 2：功能清单 / Feature Breakdown

### 核心功能

#### 对话文本生成（LLM 模式）

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/demo_app/embedded_server_main.py` → `_generate_long_dialogue_lines()` |
| 功能作用 | 调用内嵌 Bundle LLM 生成多说话人对话脚本 |
| 输入 | 行业主题、场景描述、语言、说话人数、字数目标、关键词、few-shot 样例 |
| 输出 | `Speaker N: 文本` 格式对话文本、manifest.json、.txt 文件 |
| 适用场景 | 需要 AI 自动生成对话内容时 |
| 依赖模块 | 是：bundle LLM、multilingual_naturalness、few_shot_selector、training_few_shot |

#### 真人克隆 TTS 合成（real_human 模式）

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/webapp/task_runner.py` → `_synthesize_with_real_human()` |
| 功能作用 | 将对话行按 speaker 分组合并，调用 CosyVoice 克隆音色生成 WAV，转 MP3 后拼接 |
| 输入 | `voice_assignments` JSON（speaker_id → voice_id），对话行列表 |
| 输出 | 完整 MP3 文件，`tts_meta` 诊断 JSON 写入 DB |
| 适用场景 | 需要真人感克隆音色、高质量音频时 |
| 依赖模块 | 是：voice_resolver、real_human_tts、tts_provider、ffmpeg |

#### 合成音色 TTS 合成（edge_tts 模式）

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/webapp/task_runner.py` → `_synthesize_audio_from_lines()` |
| 功能作用 | 用 Microsoft edge_tts Neural 声音并发合成音频 |
| 输入 | 对话行、voice_map（speaker → edge_tts voice name） |
| 输出 | 完整 MP3 文件 |
| 适用场景 | 快速合成、real_human 不可用时的降级路径 |
| 依赖模块 | 是：edge_tts、ffmpeg |

#### 对话质量三轮后处理

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/demo_app/multilingual_naturalness.py` |
| 功能作用 | repair（修复结构缺陷）→ keywords（注入关键词）→ stabilize（稳定人设约束）三遍 LLM 重写 |
| 输入 | 原始对话行列表、YAML 规则、目标语言 |
| 输出 | 经质量验证的对话行列表 |
| 适用场景 | LLM 生成后自动调用，不可跳过 |
| 依赖模块 | 是：rule_loader、bundle LLM |

### 辅助功能

#### 音色目录管理（Web UI）

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/demo_app/voice_resolver.py` + `src/webapp/handlers.py` |
| 功能作用 | 通过 Web UI 上传参考音频注册克隆音色，或删除已有音色；单源持久化到 runtime.yaml |
| 输入 | 参考音频文件（WAV/MP3）、音色名称、语言、性别 |
| 输出 | CosyVoice 注册的 voice_id，写入 runtime.yaml，热重载生效 |
| 适用场景 | 新增/删除克隆音色时 |
| 依赖模块 | 是：CosyVoice `/v1/voices/create`，runtime.yaml |

#### 平台文件管理

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/webapp/handlers.py`、`src/webapp/db.py` |
| 功能作用 | 文件上传、元数据管理、文件夹树、软删除、批量操作、回收站 |
| 输入 | 文件操作（上传/移动/重命名/删除）请求 |
| 输出 | SQLite 记录更新，`storage/generated/` 文件 |
| 适用场景 | 日常文件组织与管理 |
| 依赖模块 | 是：db.py（SQLite WAL） |

#### Few-shot 索引与检索

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/demo_app/training_few_shot.py`、`src/demo_app/few_shot_selector.py` |
| 功能作用 | 按模板标签+语言从 v3 训练数据和旧语料库检索最相关样例注入生成 prompt |
| 输入 | 行业模板标签、语言 |
| 输出 | 一段示例对话（最多 1200 字符 excerpt） |
| 适用场景 | LLM 生成时自动注入，提升生成质量 |
| 依赖模块 | 否（纯文件读取） |

### 工具功能

#### 训练管道 v3

| 字段 | 说明 |
|------|------|
| 对应脚本 | `tools/training/run_v3_parallel.py` |
| 功能作用 | 4 语言并行批量生成训练数据（short 约 30 分钟，long 约 5 小时） |
| 输入 | `training/data/v3_jobs_*.jsonl` 预构建任务文件 |
| 输出 | `output/training_v3/*/passed/` 通过质量门禁的样本（已纳入版本管理） |
| 适用场景 | 批量生成高质量训练样本 |
| 依赖模块 | 是：bundle LLM、quality_scoring、training_storage |

#### CosyVoice 并发实测工具

| 字段 | 说明 |
|------|------|
| 对应脚本 | `tools/tts/cosyvoice_concurrency_probe.py` |
| 功能作用 | 实测 CosyVoice 在不同并发等级下的吞吐与延迟，输出 JSON 报告 |
| 适用场景 | 调优 `max_concurrency` 配置时使用 |

---

## 章节 3：文件与脚本地图 / Project File Map

```
audio-synthesis-demo/
├── server.py                          ← [主入口] 薄包装，re-export server_platform
├── server_platform.py                 ← [主入口] 统一 Tornado App，合并 legacy + platform 路由
├── start_platform.bat                 ← [工具脚本] Windows 快速启动
│
├── src/
│   ├── demo_app/
│   │   ├── embedded_server_main.py    ← [核心逻辑] 2200+ 行：Tornado Handler、Bundle 调用、文本生成管线
│   │   ├── multilingual_naturalness.py← [核心逻辑] 2200+ 行：三轮 LLM 后处理（repair/keywords/stabilize）
│   │   ├── tts_provider.py            ← [核心逻辑] TTS 数据模型（VoiceSpec/SynthesisRequest/Result）+ TTSProvider ABC
│   │   ├── real_human_tts.py          ← [核心逻辑] RealHumanProvider：CosyVoice /v1/audio/speech 接入
│   │   ├── voice_resolver.py          ← [核心逻辑] 单源 voice_catalog 加载、resolve/build 合成请求、CRUD 操作
│   │   ├── few_shot_selector.py       ← [辅助模块] 旧语料库 few-shot 检索
│   │   ├── training_few_shot.py       ← [辅助模块] v3 训练数据 few-shot 索引
│   │   └── rule_loader.py             ← [辅助模块] YAML 规则 lru_cache 加载器
│   └── webapp/
│       ├── task_runner.py             ← [核心逻辑] 843 行：异步任务队列、真人/合成 TTS 双路径合成
│       ├── handlers.py                ← [核心逻辑] 898 行：所有平台 HTTP Handler，含音色 CRUD
│       ├── db.py                      ← [辅助模块] SQLite helpers（3 表 + LEFT JOIN file_duration）
│       └── routes.py                  ← [辅助模块] PLATFORM_ROUTES 注册（specific 路由先于 regex）
│
├── static/
│   ├── index.html                     ← [前端] 单页平台 UI（导航 + 5 个页面 + 所有 modal）
│   ├── app.js                         ← [前端] ~2900 行：生成状态机、音色管理、任务提交
│   └── styles.css                     ← [前端] CSS 变量、亮/暗主题、组件样式
│
├── config/
│   ├── app.yaml                       ← [配置文件] host/port/GUI title
│   ├── runtime.yaml                   ← [配置文件★] 后端路由 + tts.real_human 配置 + 唯一权威 voice_catalog
│   ├── preset_topics.json             ← [配置文件] 22 个预置对话场景（启动时加载）
│   ├── online_audio_ui.json           ← [配置文件] 18 个行业模板 + UI 默认值
│   ├── text_quality_rules.yaml        ← [配置文件] 人设/冲突规则（multilingual_naturalness 使用）
│   ├── text_naturalness_rules.yaml    ← [配置文件] 各语言自然度规则
│   └── text_postprocess_rules.yaml    ← [配置文件] 词汇重写规则
│
├── training/
│   ├── training_executor.py           ← [工具脚本] 任务执行器，自适应超时
│   ├── quality_scoring.py             ← [核心逻辑] 9 条强制拦截规则（severity=error）
│   ├── dialogue_validators.py         ← [辅助模块] 结构校验
│   ├── training_storage.py            ← [辅助模块] 结果持久化
│   └── legacy_generation.py           ← [辅助模块] 生成适配器（_CHUNK_SIZE=2500 for ja/ko）
│
├── tools/
│   ├── training/
│   │   ├── run_v3_parallel.py         ← [工具脚本] v3 并行训练主入口（当前主线）
│   │   └── build_v3_jobs.py           ← [工具脚本] v3 任务文件构建
│   └── tts/
│       ├── cosyvoice_concurrency_probe.py ← [工具脚本] CosyVoice 并发实测
│       └── test_voice_e2e.py          ← [工具脚本] 端到端音色合成测试
│
├── output/training_v3/               ← [数据] v3 训练输出（已纳入版本管理）
│   └── {batch}/passed/               ← 1937 条通过样本
├── demo-data/training_long_dialogue/ ← [数据] 旧语料库（630 文件，force-tracked）
│
├── docs/
│   └── PROJECT_EXPLANATION.md         ← [文档] 本文档
│
├── runtime/
│   ├── platform.db                    ← [数据] SQLite 主数据库（gitignored，自动创建）
│   ├── cache/                         ← [缓存] Bundle 解压缓存（gitignored）
│   └── cosyvoice_probe_full.json      ← [数据] CosyVoice 并发实测报告
│
└── build/
    ├── demo_app/SceneDialogueDemo.exe ← [二进制] LLM Bundle（Windows，已提交）
    └── demo_app.spec                  ← [配置文件] PyInstaller 打包规格
```

---

## 章节 4：脚本能力说明 / What Each Script Can Do

---

### `src/demo_app/tts_provider.py` ⭐ TTS 数据模型层

**这个脚本是干什么的**

定义 TTS 系统的核心数据模型和抽象接口，是 real_human_tts、voice_resolver、task_runner 三个模块的共同类型基础。不包含任何实际 HTTP 调用或业务逻辑——纯数据结构 + ABC。

**它能做哪些事**

- 定义 `VoiceSpec`：跨 provider 统一音色参数对象（provider/voice_id/language/gender/speed 等），提供带校验的 `from_dict()` 工厂方法
- 定义 `SynthesisRequest`：段落级合成请求（speaker + 连续文本 segments + voice_spec + 原始行号）
- 定义 `SynthesisResult`：合成结果，记录实际 provider、是否降级、延迟、错误分类等可观测数据
- 定义 `ProviderCapabilities`：结构化能力声明（是否支持 SSML、多说话人、字级时间戳等）
- 定义 `TTSProvider` ABC：`synthesize()` / `supports_multi_segment()` / `available_voices()` 三个抽象方法

**注意事项**

- `VALID_PROVIDERS = {"edge_tts", "real_human", "bundle"}`，新增 provider 必须在此扩展
- `SynthesisResult.error_msg` 截断到 300 字符，防止超长错误消息写满 DB

---

### `src/demo_app/real_human_tts.py` ⭐ CosyVoice Provider 实现

**这个脚本是干什么的**

实现 `RealHumanProvider`，封装对 CosyVoice `/v1/audio/speech` 端点的 HTTP 调用，包含错误分类、重试策略声明和能力描述。HTTP 调用在 `run_in_executor` 线程中执行，不阻塞 Tornado 事件循环。

**它能做哪些事**

- `synthesize(request, output_path)`：异步合成一段（实际在线程池跑同步 HTTP），返回 `SynthesisResult`
- `_call_speech_v1(text, voice_id, speed, output_path)`：底层 POST，响应直接写入 WAV 文件
- `_classify_error(exc)`：将 requests 异常转为语义分类（timeout / rate_limit / auth_failure / http_500 / param_error 等）
- `load_real_human_provider(runtime_cfg)`：从 runtime.yaml + 环境变量构建 Provider 实例（环境变量优先）
- 声明 `COSYVOICE_CAPABILITIES`：tier=B，同步接口，不支持 SSML/多说话人/字级时间戳

**如何调用**

```python
from demo_app.real_human_tts import load_real_human_provider
provider = load_real_human_provider(runtime_cfg)
result = await provider.synthesize(request, output_path)
```

**注意事项**

- 当前 CosyVoice 只有同步接口（`/v1/audio/speech`），无异步提交/轮询
- 注册成功 ≠ 合成可用：参考音频质量不足时，注册返回 200 但合成返回 500
- 响应 body < 100 bytes 视为失败（不足以是有效 WAV）

---

### `src/demo_app/voice_resolver.py` ⭐ 音色目录与合成请求构建

**这个脚本是干什么的**

音色系统的统一入口。负责从 `runtime.yaml` 加载克隆音色目录、解析前端传来的 `voice_assignments`、构建段落级 `SynthesisRequest` 列表，以及对 yaml 文件进行保留注释的增删改操作。

**它能做哪些事**

- `_load_voice_catalog_from_yaml()`：安全加载 `tts.real_human.voice_catalog`，字段标准化，失败返回空 dict
- `reload_voice_catalog()`：热重载模块级 `COSYVOICE_VOICE_CATALOG`，供注册/删除后立即生效
- `_save_voice_catalog_to_yaml(catalog)`：逐行定位 `voice_catalog:` 块，只替换该块内容，保留文件其他注释
- `create_voice_in_catalog(language, voice_id, name, gender)`：添加新音色 → 保存 yaml → 热重载
- `delete_voice_from_catalog(voice_id)`：删除指定 voice_id → 保存 yaml → 热重载
- `get_voice_catalog_for_frontend()`：生成前端格式 `{lang: [{value, label, gender, name}]}`，label 含中文性别标注
- `resolve_voice_spec(speaker_id, language, voice_assignments, voice_map, effective_provider)`：三级优先级解析（新格式 → 旧格式 → 自动分配），real_human voice_id 做全局目录校验
- `build_synthesis_requests(...)`：将 `(speaker, text)` 行列表合并为段落级 `SynthesisRequest`，同 speaker 连续行合并，超 `max_chars` 切段
- `default_voice_spec(language, speaker_id, effective_provider)`：按语言自动分配音色（real_human 按说话人序号轮转）

**注意事项**

- `COSYVOICE_VOICE_CATALOG` 模块加载时一次性读 yaml，后续只通过 `reload_voice_catalog()` 更新
- `_save_voice_catalog_to_yaml` 定位逻辑依赖 `    voice_catalog:` 精确匹配（4 个空格缩进），手动修改 yaml 时不能改变缩进
- 音色校验只检查 voice_id 是否在**全局**目录中注册，不限制必须属于当前语言（CosyVoice 支持跨语言克隆）

---

### `src/webapp/task_runner.py` ⭐ 异步任务队列与 TTS 合成

**这个脚本是干什么的**

后台工作协程，从 SQLite 轮询 `queued` 任务，驱动文本生成 + 音频合成全流程。843 行，包含真人 TTS 路径（Phase 1 新增）和合成音色路径两套完整管线。

**它能做哪些事**

- `run_task_worker()`：主轮询循环，每 3 秒查一次 `queued` 任务
- `_process_task(task_id)`：驱动状态机：`generating_text → synthesizing → completed / failed`
- **真人 TTS 路径**：
  - `_synthesize_with_real_human()`：读 `voice_assignments` → `build_synthesis_requests()` → `asyncio.gather + Semaphore` 并发合成 → WAV→MP3 → concat
  - `_synthesize_one_segment(req, provider, semaphore)`：单段合成，WAV→MP3 失败时降级 edge_tts
  - `_convert_wav_to_mp3(wav_path, mp3_path)`：ffmpeg 转 MP3，`silenceremove` 极保守阈值（-65dB）去头尾静音，统一 44100Hz mono
  - `_fallback_edge_tts(req, output_path)`：edge_tts 降级，重编码统一格式，Windows `replace()` 避免 FileExistsError
  - `_concat_audio_segments(seg_files, output_path)`：ffmpeg `filter_complex concat`（所有输入先解码为 PCM 再拼接，解决格式差异拼接噪音）
- **合成音色路径**：`_synthesize_audio_from_lines()`（调用 embedded_server_main 的 legacy pipeline）
- `_guess_scene(template, topic)`：从模板/主题文本推断场景分类（25 个类别）

**如何调用**

```python
# 在 server_platform.py 启动时
asyncio.create_task(task_runner.run_task_worker())
```

**关键注意事项**

- WAV 和 MP3 **绝对不能混合** concat：ffmpeg concat demuxer 要求所有输入 codec 一致，WAV→MP3 失败时必须降级 edge_tts，不可将 WAV 放入 concat 列表
- `max_concurrency: 1`（当前默认）：CosyVoice 为单 GPU 队列，高并发不缩短总耗时但恶化单段延迟（8 路 p50 达 32.6s），串行是最优解
- silenceremove 曾用 -40dB 误裁正常语音，现已改 -65dB（只裁 CosyVoice 数字静音 ~-90dB）

---

### `src/webapp/handlers.py` ⭐ 所有 HTTP Handler

**这个脚本是干什么的**

898 行，定义平台所有 Tornado RequestHandler。Phase 1 新增三个音色管理 Handler。

**新增 Handler**

- `VoiceCatalogHandler`（`GET /api/voice_catalog`）：返回 `get_voice_catalog_for_frontend()` 格式的音色目录
- `VoiceCreateHandler`（`POST /api/voice_catalog/create`）：接收 multipart 表单（name/language/gender + 音频文件）→ 上传到 CosyVoice `/v1/voices/create` → 成功后调 `create_voice_in_catalog()` 持久化
- `VoiceDeleteHandler`（`DELETE /api/voice_catalog/<voice_id>`）：从本地 yaml 删除，可选 `delete_remote=true` 同时调 CosyVoice 删除接口

**路由注册顺序**（`routes.py`，specific 先于 regex）

```python
(r"/api/voice_catalog",          VoiceCatalogHandler),   # specific
(r"/api/voice_catalog/create",   VoiceCreateHandler),    # specific
(r"/api/voice_catalog/([^/]+)",  VoiceDeleteHandler),    # regex（需放最后）
```

**注意事项**

- 注册成功 ≠ 合成可用，`VoiceCreateHandler` 只保证 `/v1/voices/create` 返回 200 和 voice_id
- CosyVoice 对参考音频质量有要求（单说话人、10–30 秒、无背景噪音）；质量不足时注册成功但合成返回 500

---

### `src/demo_app/embedded_server_main.py` ⭐ 核心生成引擎（2200+ 行）

**这个脚本是干什么的**

项目最大、最复杂的文件。包含 Bundle 加载、文本生成管线、三轮后处理调度、旧版 legacy HTTP Handler、全局状态管理。平台模式下此文件的 Handler 仅处理旧版 `/api/generate_text` 和 `/api/synthesize_audio`；新平台任务走 `task_runner` + `handlers.py`。

**主要函数（部分）**

| 函数 | 职责 |
|------|------|
| `_cache_is_fresh()` / `_extract_bundle()` | Bundle `.pkg` 解压缓存管理 |
| `_generate_long_dialogue_lines()` | 主生成循环：调 Bundle LLM，循环直到字数达标，ThreadPoolExecutor 并发生成各段 |
| `_normalize_request_params(payload, language)` | 统一入参 sanitize |
| `repair_dialogue_quality()` | 第一轮后处理：结构修复 |
| `merge_keywords_into_lines()` | 第二轮后处理：关键词注入 |
| `stabilize_dialogue_constraints()` | 第三轮后处理：人设稳定化 |
| `_ffmpeg_path()` | 定位 ffmpeg 可执行文件（Windows 用 `bin/ffmpeg.exe`，其他系统 PATH） |
| `active_static_dir()` | 确定静态文件目录（优先 `static/`，否则 bundle 提取目录） |
| `_load_preset_topics()` | 加载 22 个预置对话场景 |

---

### `src/demo_app/multilingual_naturalness.py`（2200+ 行）

**这个脚本是干什么的**

三轮 LLM 后处理管线。每轮调用 Bundle LLM + YAML 规则，对生成的对话进行结构修复、关键词注入、人设稳定化。包含复杂的多语言处理逻辑和性能优化（T3/T5 系列优化已合并）。

**性能优化（2026-05-04 合并）**

- `enforce_keywords_in_lines()`：O(n×k) → O(n+k)，预构建 `{speaker: [倒序位置]}` 字典
- `_prepare_chinese_dialogue_context()`：提取公共中文上下文初始化，消除重复计算

---

## 章节 5：优缺点分析 / Strengths and Limitations

### 整体优点

- **双 TTS 路径架构**：real_human（高质量克隆）+ edge_tts（广泛覆盖）+ bundle（离线保底），三级降级链保证任务必然完成
- **单源配置原则**：`runtime.yaml` 是音色目录唯一来源，前后端通过 API 同步，彻底消除三处副本不一致问题
- **格式统一策略**：所有音频输出统一为 44100Hz mono MP3，ffmpeg filter_complex concat 完全兼容不同来源片段
- **注释保留 YAML 写入**：`_save_voice_catalog_to_yaml` 只替换 voice_catalog 块，保留文件中的备注、失效 ID 说明等运维知识
- **可观测性**：`tts_meta` JSON、`SynthesisResult` 字段、`error_msg` 红字行，合成失败可精确定位到段落级
- **训练数据内嵌**：1937 条 v3 样本纳入版本管理，服务器重启后 few-shot 索引自动重建
- **Tornado 异步架构**：HTTP 调用和 ffmpeg 通过 `run_in_executor` 不阻塞事件循环，适合长时合成任务

### 局限性

- **Bundle LLM 能力固定**：LLM 能力锁定在 `.exe` 版本，更新需重新打包，无法热升级
- **CosyVoice 音色质量依赖参考音频**：参考音频质量不足时注册成功但合成返回 500，难以在注册时提前验证
- **CosyVoice 吞吐恒定**：~6 chars/s，长任务耗时长（50k 字 ≈ 2.3 小时），无法水平扩展（单 GPU 队列）
- **日韩 long tier 通过率低**：日语 45%、韩语 66%，Bundle 对日韩每次仅生成 300–800 字符，大字数目标靠分块累积，质量门禁过滤损耗高
- **WAV/MP3 混合 concat 坑**：ffmpeg concat demuxer 对 codec 差异敏感，代码中多处防御性检查缺一不可
- **Windows 依赖**：`bin/ffmpeg.exe` 硬编码路径，非 Windows 需依赖 PATH（有 fallback 但文档不显眼）

### 可维护性评分：⭐⭐⭐⭐（4/5）

- 单源配置、清晰的模块边界（tts_provider/real_human_tts/voice_resolver 职责分离）、YAML 规则外部化
- `embedded_server_main.py` 和 `multilingual_naturalness.py` 各 2200+ 行，仍是主要维护负担

### 可扩展性评分：⭐⭐⭐（3/5）

- TTSProvider ABC 定义清晰，新增 provider 只需实现三个方法
- 但 Bundle LLM 固定、新语言需同步更新 `VOICE_CATALOG`/`EDGE_DEFAULT_VOICES`/质量门禁规则多处

### 最值得重构的 3 处

1. **`embedded_server_main.py` 拆分**（2200+ 行）：Bundle 加载、文本生成、旧版 Handler 混在一起；建议提取 `bundle_loader.py` 和 `text_generation.py`
2. **`multilingual_naturalness.py` 函数过长**（2200+ 行）：三个大循环函数各 200–400 行；建议按语言/处理阶段拆子模块
3. **`task_runner.py` 中的 edge_tts legacy 路径**：`_synthesize_audio_from_lines()` 仍调用 embedded_server_main 的 legacy pipeline；Phase 2 应统一到 TTSProvider 接口

---

## 章节 6：内部调用与实现逻辑 / Internal Flow and Call Graph

### 主流程：平台任务生成（真人 TTS 路径）

```
Step 1  浏览器提交 POST /api/platform/tasks（含 tts_provider=real_human, voice_assignments JSON）
Step 2  handlers.py TaskHandler 写入 DB（status=queued）
Step 3  task_runner 轮询发现新任务（每 3 秒）
Step 4  _process_task() 更新 status=generating_text
Step 5  调用 embedded_server_main 文本生成管线（Bundle LLM + 三轮后处理）
Step 6  _process_task() 更新 status=synthesizing
Step 7  _synthesize_with_real_human() 读取 voice_assignments
Step 8  voice_resolver.build_synthesis_requests() 合并同 speaker 连续行（最大 500 字/段）
Step 9  asyncio.gather + Semaphore(1) 串行合成各段（CosyVoice 单 GPU 队列）
Step 10 每段：RealHumanProvider.synthesize() → _call_speech_v1() → WAV 写入临时文件
Step 11 _convert_wav_to_mp3()：silenceremove -65dB + 44100Hz mono 转 MP3
Step 12 MP3 失败时：_fallback_edge_tts() → edge_tts 合成 → 重编码统一格式
Step 13 _concat_audio_segments()：ffmpeg filter_complex concat 拼接所有 MP3
Step 14 tts_meta JSON（每段 provider/latency/degraded_reason）写入 DB
Step 15 audio_files 表新增记录，status=completed
Step 16 前端 3 秒轮询发现完成，更新任务卡片
```

### 调用链（真人 TTS 核心路径）

```
run_task_worker() [task_runner.py]
  └─ _process_task(task_id)
       ├─ _generate_text_via_legacy()       # 文本生成（复用旧路径）
       │    └─ embedded_server_main._generate_long_dialogue_lines()
       │         └─ BundleServer._generate_dialogue_lines()  [bundle LLM]
       └─ _synthesize_with_real_human()
            ├─ voice_resolver.build_synthesis_requests()
            │    └─ voice_resolver.resolve_voice_spec()
            │         └─ voice_resolver.default_voice_spec()
            ├─ asyncio.gather(*[_synthesize_one_segment(req) for req in requests])
            │    ├─ RealHumanProvider.synthesize(req, wav_path)  [real_human_tts.py]
            │    │    └─ _call_speech_v1()  [run_in_executor, requests.Session.post]
            │    ├─ _convert_wav_to_mp3(wav_path, mp3_path)
            │    │    └─ subprocess.run(ffmpeg silenceremove + libmp3lame)
            │    └─ [on failure] _fallback_edge_tts(req, mp3_path)
            │         ├─ edge_tts.Communicate.save()
            │         └─ subprocess.run(ffmpeg reencode 44100Hz mono)
            └─ _concat_audio_segments(seg_files, output_path)
                 └─ subprocess.run(ffmpeg filter_complex concat)
```

### 调用链（音色管理路径）

```
浏览器 POST /api/voice_catalog/create (multipart)
  └─ VoiceCreateHandler.post() [handlers.py]
       ├─ 读取 name/language/gender/audio_file 字段
       ├─ requests.post(cosyvoice_url/v1/voices/create, files=...)
       │    └─ CosyVoice 服务器注册克隆音色 → 返回 voice_id
       └─ voice_resolver.create_voice_in_catalog(language, voice_id, name, gender)
            ├─ _save_voice_catalog_to_yaml(catalog)  # 保留注释写 yaml
            └─ reload_voice_catalog()  # 热重载模块级变量

浏览器 GET /api/voice_catalog
  └─ VoiceCatalogHandler.get() [handlers.py]
       └─ voice_resolver.get_voice_catalog_for_frontend()
            └─ COSYVOICE_VOICE_CATALOG  # 模块级变量，启动时从 yaml 加载
```

### 数据流

```
输入：用户在浏览器配置（语言/场景/字数/音色分配）
  ↓
DB 写入（tasks 表，status=queued，voice_assignments JSON）
  ↓
文本生成（Bundle LLM → 三轮后处理）→ manifest.json + .txt 文件
  ↓
音色解析（voice_assignments → VoiceSpec[provider=real_human, voice_id=xxx]）
  ↓
段落合并（同 speaker 连续行 → SynthesisRequest，max 500 chars）
  ↓
逐段合成（CosyVoice WAV → ffmpeg MP3，失败降级 edge_tts）
  ↓
片段拼接（ffmpeg filter_complex concat → 完整 MP3）
  ↓
DB 更新（audio_files 表，tts_meta JSON 诊断数据）
  ↓
输出：storage/generated/ 下的 MP3 文件，前端可下载播放
```

### 外部资源调用

| 资源类型 | 名称/地址 | 调用位置 | 说明 |
|---------|---------|---------|------|
| HTTP API | CosyVoice `/v1/audio/speech` | `real_human_tts._call_speech_v1()` | 克隆音色合成（同步，WAV 返回）|
| HTTP API | CosyVoice `/v1/voices/create` | `handlers.VoiceCreateHandler.post()` | 注册克隆音色 |
| HTTP API | CosyVoice `/v1/voices/custom` | `tools/tts/cosyvoice_concurrency_probe.py` | 查询已注册音色列表 |
| 本地进程 | Microsoft edge_tts | `task_runner._fallback_edge_tts()` 等 | 合成音色 TTS |
| 本地进程 | `bin/ffmpeg.exe` | `task_runner._concat_audio_segments()` 等 | 音频转码 + 拼接 |
| 本地文件 | PyInstaller `.exe` Bundle | `embedded_server_main._extract_bundle()` | LLM 能力来源 |
| 本地文件 | `runtime/platform.db` | `webapp/db.py` | SQLite 主数据库 |
| 本地文件 | `config/runtime.yaml` | `voice_resolver._load_voice_catalog_from_yaml()` | 音色目录唯一来源 |

---

## 章节 7：复杂脚本深度解读 / Deep Technical Notes for AI and Maintainers

---

### `src/demo_app/voice_resolver.py` — 深度解读

#### 全局状态清单

| 变量 | 类型 | 用途 | 线程安全 |
|------|------|------|---------|
| `COSYVOICE_VOICE_CATALOG` | `dict[str, list[dict]]` | 模块级音色目录，启动时从 yaml 加载 | **不线程安全**：`reload_voice_catalog()` 直接 `.clear()` + `.update()`，但 Tornado 单线程事件循环中仅在注册/删除时调用，实际不并发 |
| `_CONFIG_PATH` | `Path` | runtime.yaml 绝对路径常量 | 只读，安全 |
| `EDGE_DEFAULT_VOICES` | `dict[str, str]` | 各语言 edge_tts 默认音色 | 只读，安全 |

#### 关键函数说明

**`_save_voice_catalog_to_yaml(catalog)`**
- **职责**：只替换 `voice_catalog:` 块，保留文件其余内容（包括注释）
- **算法**：逐行扫描找到 `    voice_catalog:`（精确匹配，4 空格缩进），然后向后找下一个 indent ≤ 4 的非空非注释行作为块结束；用 `yaml.dump` 重新序列化 catalog，加 4 空格前缀，替换原块
- **风险**：如果 yaml 手动修改导致 `voice_catalog:` 的缩进改变，定位会失败，回退到全量重写（注释丢失）
- **副作用**：写磁盘；写失败会抛出异常（调用方需处理）

**`resolve_voice_spec(speaker_id, language, voice_assignments, voice_map, effective_provider)`**
- **优先级链**：`voice_assignments[speaker_id]` → `voice_map[speaker_id]` → `default_voice_spec()`
- **real_human 校验**：从所有语言的 catalog 合并出 `all_valid_ids` 全局集合，voice_id 不在其中时替换为默认音色；允许跨语言使用（英文音色合中文）
- **旧格式 voice_map**：只读，只用于 edge_tts 回退，不会修改

**`build_synthesis_requests(line_tuples, ...)`**
- **切段规则**：speaker 变更时切段；同 speaker 连续文本超 `max_chars` 字符时提前切段
- **不变量**：每个 `SynthesisRequest` 只属于一个 speaker；`line_indices` 保留原始行号用于时间轴回填（Phase 2 规划）
- **性能**：O(n)，n = 行数

#### 容易看不懂的代码段

**`_save_voice_catalog_to_yaml` 中的 `end_idx` 查找逻辑**（第 149–156 行）
```python
for i in range(start_idx + 1, len(lines)):
    stripped = lines[i].lstrip()
    if not stripped or stripped.startswith("#"):
        continue  # 空行和注释行不终止块
    leading = len(lines[i]) - len(stripped)
    if leading <= 4:
        end_idx = i
        break
```
**意图**：在 yaml 文件中，`voice_catalog:` 的子内容缩进是 6–8 空格（4 + 2 + 名语言键）。找到下一个缩进 ≤ 4 的实质行就是块结束。空行和注释行被跳过，防止注释块被误判为块结束。

---

### `src/webapp/task_runner.py` — 深度解读（真人 TTS 路径）

#### 关键函数说明

**`_synthesize_with_real_human(task_id, lines, language, voice_assignments, voice_map, tts_provider)`**
- 职责：完整真人 TTS 合成流程控制器
- 从 `runtime.yaml` 懒加载配置（`_load_runtime_cfg()`，进程级缓存）
- `load_real_human_provider()` 构建 Provider 实例（API URL 优先环境变量）
- `asyncio.Semaphore(max_concurrency)` 控制并发上限（当前默认 1）
- 收集所有 `SynthesisResult`，序列化为 `tts_meta` JSON 写入 DB

**`_synthesize_one_segment(req, provider, semaphore, seg_dir, idx)`**
- 在 Semaphore 控制下调用 `provider.synthesize()`，返回 WAV 路径
- WAV→MP3 转换：调 `_convert_wav_to_mp3()`，成功后删 WAV
- **WAV→MP3 失败时**：降级 `_fallback_edge_tts()` 生成 MP3（不将 WAV 放入 concat）
- 返回 `(mp3_path, result)`，`mp3_path` 可能来自 real_human 或 edge_tts 降级

**`_convert_wav_to_mp3(wav_path, mp3_path)`**
- silenceremove 参数历史：曾用 -40dB 误裁正常语音 → 改 -65dB 后正常
- `start_duration=0.05`：50ms 以上的静音才开始裁（防止爆破音被误裁）
- `stop_duration=0.15`：尾部 150ms 以上才裁（留自然尾音）
- 成功后 `wav_path.unlink(missing_ok=True)` 删 WAV，节省磁盘

**`_concat_audio_segments(seg_files, output_path)`**
- 单片段时走简单 transcode（`-i single -c:a codec`）而非 filter_complex（避免复杂依赖）
- 多片段：`filter_complex "[0:a][1:a]...concat=n=N:v=0:a=1[aout]"`
- filter_complex 方案 vs concat demuxer（`-f concat`）的区别：前者先全解码为 PCM 再拼接，对输入 codec/采样率差异完全兼容；后者要求所有输入 codec 完全一致
- 过滤 `None` 和大小为 0 的片段（降级失败时出现）

#### 核心算法流程（真人 TTS 合成）

1. 读 `runtime.yaml` 获取 `max_concurrency`、`timeout_sec`、`max_retries`、`api_url`
2. `build_synthesis_requests()` 将 N 行对话分组为 M 个段落（M ≤ N）
3. 为每段创建临时 WAV 路径：`{seg_dir}/{idx:03d}_{speaker}.wav`
4. `asyncio.gather(*tasks)` 并发提交，Semaphore 限制同时运行数
5. 每段独立：合成 → 转 MP3 → 降级（如需）；互不依赖
6. 所有段完成后按序号排列有效 MP3 路径
7. ffmpeg concat 拼接 → 写 `storage/generated/` 最终文件
8. 汇总 `tts_meta`（每段 latency/provider_used/degraded_reason），写 DB

#### 隐式约定

- **路径约定**：临时片段文件存 `runtime/tmp_segs/{task_id}/`（推测，需确认），任务完成后清理
- **格式约定**：所有片段输出必须是 44100Hz mono MP3，否则 concat 拼接点会产生噪音或跳帧
- **执行顺序**：WAV→MP3 必须在 concat 之前完成；concat 是最后一步；顺序不可颠倒
- **内存约定**：`seg_files` 列表只保存路径，不保存音频数据在内存中，适合长对话
- **线程安全**：`_runtime_cfg_cache` 是进程级单例，只在 `_load_runtime_cfg()` 第一次调用时写，之后只读，实际安全

#### 维护者建议

- **修改 silenceremove 阈值前必读** `runtime/cosyvoice_probe_full.json`：CosyVoice 静音段 ~-90dB，正常语音 > -40dB，安全区间是 -65dB ~ -50dB
- **新增 TTS provider 最容易出错的地方**：必须在 `_synthesize_one_segment` 的失败路径中保证降级产出 MP3（不是 WAV），否则 concat 步骤会悄无声息地产生音频故障
- **测试建议**：用 `tools/tts/test_voice_e2e.py` 做端到端冒烟测试；用 `tools/tts/cosyvoice_concurrency_probe.py` 实测新配置下的延迟分布

---

### `src/demo_app/embedded_server_main.py` — 关键全局状态

| 变量 | 类型 | 用途 | 线程安全说明 |
|------|------|------|------------|
| `_BUNDLE_SERVER` | `BundleServer` | 从 `.exe` 加载的 LLM 实例，进程内唯一 | 只读（方法无副作用），安全 |
| `_manifest_cache` | `OrderedDict`（LRU 500） | 缓存 `dialogue_id → manifest`，避免重复磁盘读 | 受 `_manifest_cache_lock`（threading.Lock）保护 |
| `_ONLINE_AUDIO_CONFIG_CACHE` | `dict` | 从 `online_audio_ui.json` 加载的 UI 配置，进程启动时一次性读 | 只读，安全 |
| `_PRESET_TOPICS_CACHE` | `list` | 22 个预置场景，进程启动时一次性读 | 只读，安全 |

#### 隐式约定

- **Bundle 提取**：`runtime/cache/embedded_bundle/` 由 `_extract_bundle()` 在启动时生成；gitignored，不可提交；重启时根据 `.pkg` 哈希判断是否重新提取
- **Static 目录**：`active_static_dir()` 在开发时返回 `static/`（优先）；修改 `static/` 下的文件无需重启
- **Few-shot 索引**：服务器每次重启调用 `invalidate_index()`，下次请求时懒加载重建（4115 条索引，覆盖 v3 + v2 + 旧语料）
- **manifest LRU**：500 条上限，超出后淘汰最旧条目；`_manifest_cache_lock` 在每次读写时加锁，防止并发 Handler 竞争
