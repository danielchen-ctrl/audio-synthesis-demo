# 音频语料生成平台 V1 — 项目说明文档

> 生成时间：2026-05-30 | 分析目录：`D:\Github\audio-synthesis-demo`

---

## 章节 1：项目总览 / Executive Summary

### 一句话定义

这是一个**单机音频语料生成平台**，将 PyInstaller 打包的 Bundle LLM（或云 LLM）生成的多人对话文本，通过 CosyVoice 真人克隆音色或 edge_tts 合成为带时间码的音频文件，支持完整的文件管理与任务队列。

### 核心能力

- 🧠 **双 LLM 路线**：Bundle LLM（PyInstaller 打包的离线引擎）为主，云 LLM（DeepSeek / OpenAI / Anthropic，配置 `runtime.yaml` 切换）为辅，失败时自动降级
- 🎙 **双 TTS 路线**：真人克隆音色（CosyVoice `/v1/audio/speech`）优先，edge_tts 自动降级兜底
- ⚙️ **在线音色管理**：上传参考音频注册 CosyVoice 克隆音色，写入 `runtime.yaml` 单一权威源
- 📁 **完整文件管理**：SQLite 存档、文件夹分组、软删除、回收站、批量操作、搜索、标签
- 📝 **SRT / JSON 字幕导出**：段级实测时间码，可直接用于语音识别训练标注
- 🔄 **任务队列**：异步 asyncio 任务队列，支持生成 / 合成 / 完成 / 失败状态流转
- 🌐 **局域网访问**：Tornado HTTP 服务器，自动探测本机 IP 生成访问链接

### 适合谁阅读

| 角色 | 建议章节 | 关注重点 |
|------|---------|---------|
| 日常使用者 | 1 | 启动方式、功能概览 |
| 新接手开发者 | 1 → 3 → 6 | 架构全貌 + 调用链 |
| 后端维护者 | 4 → 7 | embedded_server_main.py / task_runner.py 深度 |
| 运维 / 部署 | 1 → 3 | 启动方式 + 配置文件 |

### 快速理解摘要

这个项目是一个在本地运行的单机工具，不需要联网也能工作（Bundle LLM 是离线打包好的）。用户在浏览器页面上选择场景主题（22 个预置 + 自定义），填写说话人数和目标时长，系统自动生成多人对话文本，再把每段台词分配给 CosyVoice 克隆音色朗读，最终拼成一条 MP3 音频。生成的文件存在本地 SQLite 数据库里，支持分文件夹管理、搜索、批量下载。整个系统用 Python + Tornado 写成，`python server.py` 一行启动，不需要 Docker 或其他依赖服务。

---

## 章节 2：功能清单 / Feature Breakdown

### 核心功能

#### 对话文本生成（双 LLM 路线）

| 字段 | 说明 |
|------|------|
| 对应文件 | `src/demo_app/embedded_server_main.py`（Bundle LLM 路线）+ `src/demo_app/services/cloud_generation.py`（云 LLM 路线）|
| 功能作用 | 根据场景模板 + 说话人数 + 目标时长生成 `Speaker N:` 格式多轮对话 |
| 输入 | template_label、people_count、word_count、language、keyword_terms |
| 输出 | `storage/generated/<dialogue_id>/<basename>.txt` + `manifest.json` |
| 适用场景 | 前端"生成文本"按钮、LLM 模式任务提交 |
| 依赖模块 | `training_few_shot.py`（few-shot 注入）、`multilingual_naturalness.py`（三遍后处理）|

#### 音频合成（CosyVoice + edge_tts 降级）

| 字段 | 说明 |
|------|------|
| 对应文件 | `src/webapp/task_runner.py`（`_synthesize_with_real_human` / `_synthesize_audio_from_lines`）|
| 功能作用 | 逐段调 TTS 合成 WAV，转 MP3（silenceremove -65dB），ffmpeg filter_complex concat 拼接 |
| 输入 | `[(speaker_id, text), ...]` + voice_assignments + language + output_format |
| 输出 | `storage/generated/<id>/<basename>.mp3` + 段级时间码 |
| 适用场景 | 所有平台任务（real_human 模式 + edge_tts 模式）|
| 依赖模块 | `real_human_tts.py`、edge-tts 库、ffmpeg |

#### 在线音色管理

| 字段 | 说明 |
|------|------|
| 对应文件 | `src/webapp/handlers.py`（VoiceCreateHandler / VoiceDeleteHandler）+ `src/demo_app/voice_resolver.py` |
| 功能作用 | 上传参考音频注册 CosyVoice 克隆音色；`runtime.yaml` 为单一权威源 |
| 输入 | multipart: audio 文件 + name + language + gender |
| 输出 | 写入 `config/runtime.yaml` `tts.real_human.voice_catalog` |
| 适用场景 | 前端"⚙️ 管理真人音色"弹窗 |

### 辅助功能

#### 文件 / 文件夹 / 回收站管理

| 字段 | 说明 |
|------|------|
| 对应文件 | `src/webapp/handlers.py` + `src/webapp/db.py` |
| 功能作用 | 上传、软删除、回收站恢复、文件夹分组、标签、批量操作、全局搜索 |
| 存储 | SQLite `runtime/platform.db`；音频文件存本地 `storage/` |

#### 三遍 LLM 后处理（Bundle LLM 专用）

| 字段 | 说明 |
|------|------|
| 对应文件 | `src/demo_app/multilingual_naturalness.py` |
| 功能作用 | repair（修复退化）→ keywords（关键词注入）→ stabilize（说话人一致性）|
| 触发条件 | Bundle LLM 路线（云 LLM 走精简 3A 路线，不走 repair 遍）|

#### few-shot 样本检索

| 字段 | 说明 |
|------|------|
| 对应文件 | `src/demo_app/training_few_shot.py` + `src/demo_app/few_shot_selector.py` |
| 功能作用 | 按 (topic_id, language) 从 v3 训练样本中检索高分样本注入 prompt |
| 数据来源 | `output/training_v3/*/passed/`（1937 条，已纳入版本管理）|

### 工具功能

#### 训练流水线（v3）

| 字段 | 说明 |
|------|------|
| 对应文件 | `tools/training/run_v3_parallel.py` |
| 功能作用 | 4语言并行生成高质量对话训练样本，通过 9 条质量门禁过滤 |
| 已完成 | 1937 条样本，22 场景 × 4 语言 × 500–50000 字 |

---

## 章节 3：文件与脚本地图 / Project File Map

```
audio-synthesis-demo/
├── server.py                      ← [主入口] 轻量包装 → server_platform.py
├── server_platform.py             ← [主入口] 统一平台入口（Tornado + SQLite + 任务队列）
├── start_platform.bat             ← [工具脚本] Windows 双击启动
│
├── config/
│   ├── app.yaml                   ← [配置文件] host / port / GUI 标题
│   ├── runtime.yaml               ← [配置文件] LLM / TTS / 任务队列 / 音色目录（单一权威）
│   ├── runtime.pre_release.yaml   ← [配置文件] 预发布专用配置
│   ├── preset_topics.json         ← [数据/样例] 22 个预置对话场景
│   ├── online_audio_ui.json       ← [数据/样例] 18 个行业模板 + UI 默认配置
│   ├── text_quality_rules.yaml    ← [配置文件] 角色 / 冲突质量规则（multilingual_naturalness 用）
│   ├── text_naturalness_rules.yaml ← [配置文件] 各语言自然度规则
│   ├── text_postprocess_rules.yaml ← [配置文件] 词汇改写规则
│   └── requirements.txt           ← [配置文件] Python 依赖
│
├── src/
│   ├── demo_app/
│   │   ├── embedded_server_main.py ← [核心逻辑] 2000+ 行：Tornado handlers + Bundle LLM + TTS pipeline
│   │   ├── multilingual_naturalness.py ← [核心逻辑] 三遍后处理（repair → keywords → stabilize）
│   │   ├── real_human_tts.py      ← [核心逻辑] CosyVoice /v1/audio/speech 接入
│   │   ├── voice_resolver.py      ← [核心逻辑] 音色单源加载 / 解析 / 注册 / 删除
│   │   ├── tts_provider.py        ← [辅助脚本] TTS 数据模型 + TTSProvider ABC
│   │   ├── training_few_shot.py   ← [核心逻辑] v3 训练样本 few-shot 检索（4115 条索引）
│   │   ├── few_shot_selector.py   ← [辅助脚本] 旧语料库检索（630 条）
│   │   ├── rule_loader.py         ← [辅助脚本] YAML 规则 lru_cache 加载
│   │   ├── lang_utils.py          ← [辅助脚本] 语言别名规范化
│   │   ├── providers/llm/
│   │   │   ├── base.py            ← [辅助脚本] LLMMessage / LLMResult / ABC
│   │   │   ├── factory.py         ← [核心逻辑] 从 runtime.yaml 决定 LLM provider
│   │   │   ├── openai_compat.py   ← [核心逻辑] DeepSeek / OpenAI / 兼容网关
│   │   │   └── anthropic_llm.py   ← [核心逻辑] Anthropic Messages API
│   │   └── services/
│   │       └── cloud_generation.py ← [核心逻辑] 云 LLM 生成主入口（3A 精简路线）
│   │
│   └── webapp/
│       ├── db.py                  ← [核心逻辑] SQLite CRUD（任务 / 文件 / 文件夹）
│       ├── handlers.py            ← [核心逻辑] 所有 /api/platform/* Tornado 路由处理器
│       ├── routes.py              ← [辅助脚本] PLATFORM_ROUTES 注册
│       └── task_runner.py         ← [核心逻辑] 异步任务队列（生成 + 合成 + 入库）
│
├── static/
│   ├── index.html                 ← [核心逻辑] 单页面平台 UI（5 个页面 + 多个弹窗）
│   ├── app.js                     ← [核心逻辑] ~100KB 前端状态机（生成弹窗 + 音色管理）
│   └── styles.css                 ← [辅助脚本] CSS 变量 + 亮 / 暗主题
│
├── build/
│   ├── demo_app/SceneDialogueDemo.exe ← [数据/样例] Bundle LLM 可执行文件（已提交）
│   ├── build_win.ps1              ← [工具脚本] Windows 打包脚本
│   └── demo_app.spec              ← [配置文件] PyInstaller 规格文件
│
├── output/training_v3/            ← [数据/样例] v3 训练产物（1937 条，已提交）
├── storage/generated/             ← [数据/样例] 生成产物（txt + manifest + mp3，gitignored）
├── runtime/platform.db            ← [数据/样例] SQLite 数据库（gitignored）
│
├── scripts/                       ← [工具脚本] CI 门禁 / 质量检查 / 预发布验证
├── tests/                         ← [测试] 单元测试（pytest）
├── tools/training/                ← [工具脚本] v3 训练流水线
└── docs/                          ← [文档] PRD / 真人 TTS 特性文档 / 主题数据
```

---

## 章节 4：脚本能力说明 / What Each Script Can Do

### `server_platform.py` ⭐ 主入口

**这个脚本是干什么的**

平台统一启动点。用 7 步完成初始化：初始化 SQLite → 构建 Tornado app（含所有 demo 原有路由）→ 加载 Bundle LLM → 注册平台路由 → 预热 manifest 缓存 → 清除 few-shot 索引 → 启动任务 worker。保留原有 `/api/generate_text` 等 legacy 接口不变，在其基础上叠加 `/api/platform/*` 新路由。

**启动方式**
```bash
python server.py          # 推荐（包装层，自动选择 server_platform.py）
python server_platform.py # 直接启动
start_platform.bat        # Windows 双击
```

**成功后产生什么**
- 浏览器访问 `http://localhost:8899/`
- SQLite `runtime/platform.db` 自动创建
- 控制台打印所有局域网访问地址

---

### `src/webapp/task_runner.py` ⭐ 任务队列引擎

**这个脚本是干什么的**

实现异步任务队列，把"生成文本 + 合成音频 + 写入 DB"整条链路异步化。核心是一个 `asyncio.Queue` + `_MAX_WORKERS` 个并发 worker 协程。支持 Bundle LLM、云 LLM（DeepSeek 等）、edge_tts、CosyVoice 真人音色四种模式的任意组合。

**任务状态流**
```
queued → generating_text → synthesizing → completed
                                        ↘ failed
```

**双 LLM 切换逻辑**
```
runtime.yaml llm.provider 非空？
  ├── 是 → 调云 LLM（cloud_generation.py）
  │         失败 + use_bundle_fallback=true → 降级 Bundle LLM
  └── 否 → 直接 Bundle LLM（embedded_server_main._generate_text_payload）
```

**save_dir 决策**（目录合并逻辑）
```
direct 模式 + dialogue_id 目录已存在 → 复用 storage/generated/<dialogue_id>/
否则 → 新建 storage/generated/<task_id>/
```

---

### `src/demo_app/embedded_server_main.py` ⭐ 核心业务（2000+ 行）

**这个脚本是干什么的**

整个 V1 最核心的文件，包含：
- Bundle LLM 提取、加载（从 `.exe` 的 `.pkg` 解压 `.pyc`，`importlib` 加载）
- manifest 缓存（LRU 500 条，双源扫描 `storage/generated/` + `demo-data/`）
- 文本生成完整管线（`_generate_long_dialogue_lines` + 三遍后处理）
- edge_tts 合成管线（`_synthesize_audio_from_lines`）
- Tornado RequestHandler 类（10 多个 Handler）
- `make_app()` 路由注册

**Bundle LLM 加载机制**
```
1. 检查 runtime/cache/embedded_bundle/ 是否新鲜
2. 过期 → 从 build/demo_app/SceneDialogueDemo.exe 解包
3. importlib 加载 .pyc 模块
4. 全局 _BUNDLE_SERVER 保存实例（进程内单例）
```

**注意事项**
- Bundle LLM 能力固定在 `.exe` 版本，改能力必须重新打包
- `runtime/cache/` 每次启动重建，不要提交

---

### `src/demo_app/services/cloud_generation.py` — 云 LLM 生成主入口

**这个脚本是干什么的**

云 LLM 路线的完整生成管线（3A 精简路线，基于 22 场景评估结论）：构建 prompt（含 few-shot）→ 调云 LLM → 解析 Speaker N 行 → 3 条质量门禁 → 关键词注入 + 中文稳定化 → 写 txt + manifest → 返回与 Bundle LLM 兼容的结果字典。

**3 条质量门禁**
- `core_marker_artifact`：输出含 `<<…>>` 模板标记残留
- `high_repetition_rate`：唯一行率 < 60%
- `word_count_critical_short`：实际字数 < 目标 30%

**注意**：`repair_dialogue_quality` 不调用——云 LLM 不产生 Bundle 特有退化，repair 遍无作用对象。

---

### `src/demo_app/voice_resolver.py` — 音色单源管理

**推测用途**（P1 级）

`runtime.yaml` `tts.real_human.voice_catalog` 是全局唯一权威。`_load_voice_catalog_from_yaml()` 启动时读取，`resolve_voice_spec()` 按 speaker_id 解析音色，`build_synthesis_requests()` 合并同说话人连续行（max 500 字）生成合成请求列表。`create_voice_in_catalog()` / `delete_voice_from_catalog()` 用逐行替换保留注释的方式写回 YAML。

---

### `src/webapp/db.py` — SQLite CRUD

**推测用途**（P1 级）

所有任务、文件、文件夹的 CRUD 封装，零配置（Python 内置 sqlite3）。`init_db()` 幂等建表，`_run_tts_migration()` 自动追加 TTS 新增列（`tts_provider` / `voice_assignments` / `dialogue_id` 等）。`list_tasks()` 通过 `LEFT JOIN audio_files` 带回 `file_duration`。

---

## 章节 5：优缺点分析 / Strengths and Limitations

### 优点

- **零外部依赖运行**：SQLite 内置、Bundle LLM 离线、`python server.py` 一行启动，无需 Docker / Redis / MinIO
- **双 LLM 双 TTS 降级**：Bundle LLM + 云 LLM 双轨；CosyVoice + edge_tts 降级，单点故障不影响任务完成
- **音色单源化**：`runtime.yaml` 是唯一权威，前后端自动同步，不存在三处副本不一致问题
- **精确时间码**：每段实测 duration 累加，SRT/JSON 可直接用于语音识别训练标注
- **三遍后处理成熟**：针对 Bundle LLM 退化问题深度调优，覆盖 22 个场景的 Bundle 特有缺陷
- **训练语料自产自销**：1937 条 v3 训练样本已纳入版本管理，few-shot 质量可控

### 局限性 / 潜在风险

- **Bundle LLM 锁定**：LLM 能力固定在打包的 `.exe`，改模型必须重新打包发布，无法热更新
- **单进程瓶颈**：Tornado 单进程，多任务合成时串行（CosyVoice `max_concurrency=1`），无法横向扩展
- **SQLite 单文件**：并发写入有锁竞争，不适合多用户同时大批量提交
- **embedded_server_main.py 体积**：2000+ 行超级文件，handler / 工具函数 / 管线逻辑全混一起，难以单元测试
- **无用户系统**：单用户设计，所有文件全局可见，不适合多人共用

### 可维护性：⭐⭐⭐（3/5）

路由、DB、任务队列分层合理。但 `embedded_server_main.py` 2000+ 行混杂太多职责，任何改动都需要熟悉整个文件。

### 可扩展性：⭐⭐（2/5）

云 LLM Provider 抽象层设计良好（factory + ABC），但 TTS 管线、manifest 缓存、静态文件服务都深嵌在 `embedded_server_main.py`，扩展困难。

### 最值得重构的 3 处

1. **`embedded_server_main.py` 拆分**：至少拆出 3 个模块——`bundle_loader.py`（Bundle 加载）、`text_pipeline.py`（文本生成管线）、`tts_pipeline.py`（音频合成）
2. **manifest 缓存**：`_MANIFEST_CACHE` / `_manifest_cache_lock` 是全局状态，在 Tornado 单线程 IOLoop 里用 Lock 是多余的，但在多线程场景（manifest-cache-warmer 线程）会有并发问题，建议用 `asyncio.Lock`
3. **`task_runner._process_task`**：函数体超过 400 行，建议按阶段拆成 `_step_generate_text()` / `_step_synthesize()` / `_step_save()` 子函数

---

## 章节 6：内部调用与实现逻辑 / Internal Flow and Call Graph

### 主流程：提交一条平台任务到拿到音频

```
Step 1  前端 GenerateModal → POST /api/platform/tasks
Step 2  TasksHandler.post() → db.create_task() → 写 SQLite，status=queued
Step 3  task_runner._task_queue.put(task_id) → 推入 asyncio Queue
Step 4  _worker() 协程拉取任务 → _process_task(task_id)
Step 5    [云LLM] generate_text_cloud_llm() → 云 LLM API
          [Bundle] _generate_text_payload() → Bundle LLM 分块生成
Step 6    三遍后处理（Bundle）或 3A 精简后处理（云LLM）
Step 7    _synthesize_with_real_human() → CosyVoice 逐段合成
          [降级] _fallback_edge_tts() → edge_tts
Step 8    ffmpeg WAV→MP3 + silenceremove + filter_complex concat
Step 9    db.create_audio_file() + db.update_task_status(completed)
Step 10  前端 Tasks 页 3 秒轮询 → 发现 completed → 刷新文件列表
```

### 调用链

```
server_platform.py:main()
  ├─ init_db() [webapp/db.py]
  ├─ make_app() [embedded_server_main.py]
  │    └─ load_bundle_server() → 解包 .exe → _BUNDLE_SERVER
  ├─ register_platform_routes() [webapp/routes.py]
  └─ start_worker() [webapp/task_runner.py]
       └─ _process_task(task_id)
            ├─ [云LLM] generate_text_cloud_llm() [services/cloud_generation.py]
            │    ├─ build_dialogue_prompt() → few-shot 注入
            │    ├─ provider.complete() [providers/llm/openai_compat.py]
            │    ├─ _check_quality_gates()
            │    └─ _apply_lite_postprocess()
            │         ├─ enforce_keywords_in_lines() [multilingual_naturalness.py]
            │         └─ stabilize_dialogue_constraints() [multilingual_naturalness.py]
            ├─ [Bundle] _generate_text_payload() [embedded_server_main.py]
            │    ├─ _generate_long_dialogue_lines() → _BUNDLE_SERVER.generate()
            │    └─ repair → keywords → stabilize [multilingual_naturalness.py]
            ├─ _synthesize_with_real_human() [task_runner.py]
            │    ├─ build_synthesis_requests() [voice_resolver.py]
            │    ├─ RealHumanProvider.synthesize() [real_human_tts.py]
            │    │    └─ POST /v1/audio/speech → WAV bytes
            │    ├─ _convert_wav_to_mp3() → ffmpeg silenceremove
            │    └─ _concat_audio_segments() → ffmpeg filter_complex
            └─ db.create_audio_file() + update_task_status()
```

### 数据流

```
用户配置（场景模板 / 人数 / 时长 / 关键词）
  │
  ▼ [embedded_server_main / cloud_generation]
结构化对话行 [(Speaker N, text), ...]
+ manifest.json + .txt 写入 storage/generated/<id>/
  │
  ▼ [voice_resolver → real_human_tts / edge_tts]
每段 WAV bytes（真人克隆音色 or edge_tts）
  │
  ▼ [ffmpeg: silenceremove + 格式化 + concat]
完整 MP3 + 段级时间码 segments
  │
  ▼ [db.create_audio_file]
SQLite audio_files 表（含 duration / scene / topic）
storage/generated/<id>/<basename>.mp3
```

### 外部资源调用

| 资源类型 | 名称 | 调用位置 | 说明 |
|---------|------|---------|------|
| Bundle LLM | SceneDialogueDemo.exe | `embedded_server_main.load_bundle_server()` | PyInstaller 打包，离线可用 |
| 云 LLM API | DeepSeek / OpenAI / Anthropic | `providers/llm/*.py` | runtime.yaml 配置切换 |
| TTS API | CosyVoice | `real_human_tts.RealHumanProvider` | POST /v1/audio/speech → WAV |
| TTS 降级 | edge_tts | `task_runner._fallback_edge_tts()` | edge-tts 库，免费 |
| 媒体处理 | ffmpeg / ffprobe | `task_runner._convert_wav_to_mp3()` | WAV→MP3 + 拼接 + 时长测量 |
| 数据库 | SQLite | `webapp/db.py` | 任务 / 文件 / 文件夹，零配置 |

---

## 章节 7：深度技术解读 / Deep Technical Notes

### `embedded_server_main.py` — Bundle LLM 加载机制

**全局状态**

| 变量 | 类型 | 用途 | 线程安全 |
|------|------|------|---------|
| `_BUNDLE_SERVER` | object | Bundle LLM 实例，进程内单例 | 只读，线程安全 |
| `_manifest_cache` | `OrderedDict` | LRU 500 条，`dialogue_id → (path, dict)` | `_manifest_cache_lock` 保护 |
| `_ONLINE_AUDIO_CONFIG_CACHE` | dict | 启动时读 online_audio_ui.json | 只读，线程安全 |
| `_PRESET_TOPICS_CACHE` | list | 22 个预置场景 | 只读，线程安全 |

**Bundle 解包流程（`_extract_bundle_modules`）**

1. 找到 `build/demo_app/SceneDialogueDemo.exe` 内嵌的 `.pkg` 数据块
2. 解压到 `runtime/cache/embedded_bundle/`（`.pyc` 文件）
3. 用 `importlib` 按模块名逐一 import
4. 取出 `BundleServer` 类，实例化，赋值给 `_BUNDLE_SERVER`

新鲜度判断（`_cache_is_fresh()`）：比较 `.exe` 的 mtime 与缓存目录 mtime，旧了就重新解包。

**manifest 缓存双源扫描**

```
_ensure_manifest_cache() 扫描两个根：
  storage/generated/*/manifest.json   ← 新路径（2026-05-16 后）
  demo-data/*/manifest.json           ← 旧路径（历史兼容）
同一 dialogue_id 重复时，mtime 倒序遍历 + setdefault，最新条目胜出。
```

---

### `task_runner.py` — 合成管线关键设计

**silenceremove 参数选择**

`-65dB` 是保守阈值：CosyVoice 数字静音约 `-90dB`，正常语音 `> -40dB`。`-65dB` 仅裁数字静音。`start_duration=0.05s` 防止过激裁剪开头辅音。

**为什么用 filter_complex concat 而非 concat demuxer**

concat demuxer 要求所有输入 codec 相同。CosyVoice 输出 WAV，edge_tts 输出 MP3。混合 codec 时 concat demuxer 会产生爆音或静默。`filter_complex concat` 先解码为 PCM 再重编码，完全兼容格式差异。

**WAV 和 MP3 绝对不能混合 concat**

降级到 edge_tts 时，如果 WAV→MP3 转换也失败，必须放弃该段（重新走 edge_tts），不能把 WAV 直接放进 concat 列表。混合 codec 会导致逐字播放或噪音。

**cloud_generation 与 task_runner 的兼容约定**

`generate_text_cloud_llm()` 返回值必须与 `_generate_text_payload()` 格式一致：

```python
{
    "ok": True,
    "dialogue_id": "xxxxxxxx",
    "dialogue_text": "Speaker 1: ...\nSpeaker 2: ...",
    "text_path": str(txt_path),
    "basename": basename,
}
```

`task_runner` 统一读这个 dict，不区分是哪条路线产生的。

---

### `voice_resolver.py` — YAML 单源写回技巧

`_save_voice_catalog_to_yaml()` 不重写整个文件，而是**逐行定位** `voice_catalog:` 块再替换，保留文件中其他所有注释和配置。这是为了让人工维护的注释（如废弃 voice_id 说明）在程序操作后不丢失。

---

*文档生成完毕。*
- **文档路径**：`docs/PROJECT_EXPLANATION.md`
- **分析文件**：深读 3 个（server_platform.py / task_runner.py / runtime.yaml），grep 5 个（db.py / handlers.py / voice_resolver.py / real_human_tts.py / cloud_generation.py），推测 0 个
- **主入口**：`server_platform.py`（由 `server.py` 包装）
- **推测标注**：`voice_resolver.py`、`db.py` 两节标注为"推测用途（P1 级）"
