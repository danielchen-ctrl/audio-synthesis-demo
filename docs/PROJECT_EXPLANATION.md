# PROJECT_EXPLANATION.md
> 语料生成平台 — 完整技术说明文档
> 生成时间：2026-05-03

---

## 章节 1：项目总览 / Executive Summary

### 这是一个什么项目？

**语料生成平台（Audio Synthesis Demo）**，是一个面向语音AI团队的**多语言对话语料批量生产系统**，集成了大语言模型对话生成、微软 Edge TTS 语音合成、平台化文件管理三大能力。

### 核心能力

- **LLM 对话生成**：调用本地 PyInstaller 打包的 LLM 引擎，按行业模板 + 角色配置生成多轮对话文本
- **多语言 TTS 合成**：支持 13 种语言（中、英、日、韩、法、德、西、葡、意、俄、阿、印尼、粤），通过 Edge TTS 并发合成音频段落后由 ffmpeg 拼接
- **平台化语料管理**：SQLite 持久化，支持任务队列、文件夹、搜索、回收站、批量操作
- **预置场景体系**：22 个行业场景预置参数，可直接一键发起生成
- **训练数据流水线**：B0–B5 六批次自动化生成 65,628 条训练样本
- **旧版 demo 兼容**：`server.py` 保留原有单页 demo，平台版通过 `server_platform.py` 在此基础上扩展路由

### 适合谁阅读

| 角色 | 建议章节 | 关注重点 |
|------|---------|---------|
| 平台用户 | 1、3 | 快速理解功能入口 |
| 前端开发 | 1、4（app.js） | UI 交互逻辑、API 调用 |
| 后端开发 | 4、5、6 | 路由、任务队列、DB 层 |
| AI/训练工程师 | 1、4（embedded）、7 | LLM 调用链、后处理三遍 |
| 维护者 | 全部 | 深度解读章节7 |

### 快速理解摘要

这个项目起源于一个需要大量多语言对话音频的语音 AI 团队。系统以 Tornado 作为 HTTP 服务框架，前端是单页应用（`static/index.html` + `static/app.js`），提供两种使用模式：**LLM 模式**（让 AI 生成对话文本后合成音频）和**手动模式**（直接粘贴对话文本合成音频）。

平台版（`server_platform.py`）在旧版 demo 基础上追加了 `/api/platform/*` 路由，接入了 SQLite 数据库和异步任务 worker，使生成任务可以排队批量执行。LLM 引擎打包在 `build/demo_app/SceneDialogueDemo.exe` 中，通过 importlib 加载模块，这意味着模型能力固定，不能热更新。生成的语料文件存放在 `demo/` 和 `storage/` 目录，元数据记录在 `runtime/platform.db`。

---

## 章节 2：功能清单 / Feature Breakdown

### 核心功能

#### LLM 对话文本生成

| 字段 | 说明 |
|------|------|
| 对应文件 | `src/demo_app/embedded_server_main.py` → `GenerateTextHandler` |
| 功能作用 | 调用 bundle LLM 按主题/模板生成多说话人对话文本 |
| 输入 | topic, template, language, people_count, word_count, keywords, custom_prompt |
| 输出 | 对话文本文件（`demo/{timestamp}/`）+ manifest.json + dialogue_id |
| 适用场景 | 需要 AI 自动撰写对话内容时 |
| 依赖模块 | PyInstaller bundle (SceneDialogueDemo.exe), few_shot_selector, multilingual_naturalness |

#### TTS 音频合成

| 字段 | 说明 |
|------|------|
| 对应文件 | `src/demo_app/embedded_server_main.py` → `SynthesizeAudioHandler` |
| 功能作用 | 将对话文本按说话人分配 Edge TTS 声线，并发合成后用 ffmpeg 拼接为完整音频 |
| 输入 | dialogue_id, voice_map（可选）, output_format |
| 输出 | MP3/WAV 文件（`demo/{timestamp}/`）+ 音频时长 |
| 适用场景 | LLM 生成或手动输入对话后转为音频 |
| 依赖模块 | edge_tts, pydub, ffmpeg (bin/ffmpeg.exe) |

#### 平台任务队列

| 字段 | 说明 |
|------|------|
| 对应文件 | `webapp/task_runner.py`, `webapp/handlers.py` → TasksHandler |
| 功能作用 | 接收生成请求入队，后台 worker 依次执行文本生成 + 音频合成，状态持久化到 DB |
| 输入 | POST /api/platform/tasks body: topic, language, people_count, word_count, template 等 |
| 输出 | task_id + status 流转（queued → generating_text → synthesizing → completed/failed） |
| 适用场景 | 批量生产语料，页面可关闭后台继续执行 |
| 依赖模块 | webapp.db, embedded_server_main |

### 辅助功能

#### 音频文件管理

| 字段 | 说明 |
|------|------|
| 对应文件 | `webapp/handlers.py` → FilesHandler / FileHandler |
| 功能作用 | 列表/搜索/筛选/软删除/永久删除/下载音频文件，支持文件夹组织 |
| 适用场景 | 语料库整理，按语言/场景/来源筛选 |

#### 文件上传

| 字段 | 说明 |
|------|------|
| 对应文件 | `webapp/handlers.py` → UploadHandler |
| 功能作用 | 接收 WAV/MP3/M4A/MP4 文件上传（≤500MB），保存至 `storage/uploaded/`，记录 DB |
| 输入 | multipart/form-data: file, language, scene, speaker_count, topic, folder_id |

#### 文件夹管理

| 字段 | 说明 |
|------|------|
| 对应文件 | `webapp/handlers.py` → FoldersHandler / FolderHandler |
| 功能作用 | 创建/重命名/删除文件夹，最多 3 层嵌套，返回完整树形结构 |

#### 回收站

| 字段 | 说明 |
|------|------|
| 对应文件 | `webapp/handlers.py` → TrashHandler / TrashRestoreHandler / TrashDeleteHandler |
| 功能作用 | 软删除文件进回收站，支持恢复或永久删除（同时删除磁盘实体文件） |

#### 批量操作

| 字段 | 说明 |
|------|------|
| 对应文件 | `webapp/handlers.py` → BatchMoveHandler / BatchDeleteHandler / BatchDownloadHandler |
| 功能作用 | 批量移动/删除/打包下载（ZIP），单次最多 50 个文件，下载限 2GB |

### 工具功能

#### 训练数据流水线

| 字段 | 说明 |
|------|------|
| 对应文件 | `tools/training/run_all_batches.py` |
| 功能作用 | B0–B5 六批次顺序执行，每批有通过率门控，自动生成 65,628 条训练样本 |
| 输出 | `output/training_v2/{batch}/passed/` |

#### 对话后处理三遍

| 字段 | 说明 |
|------|------|
| 对应文件 | `src/demo_app/multilingual_naturalness.py` |
| 功能作用 | LLM 输出后依次执行 repair → merge_keywords → stabilize，修复质量问题 |

---

## 章节 3：文件与脚本地图 / Project File Map

```
audio-synthesis-demo/
├── server.py                          ← [辅助入口] 旧版 demo 独立启动
├── server_platform.py                 ← [主入口] 语料生成平台，完整功能
│
├── src/demo_app/
│   ├── embedded_server_main.py        ← [核心逻辑] 2173行 Tornado app + LLM + TTS 全流程
│   ├── few_shot_selector.py           ← [辅助模块] 按域名/语言选取 few-shot 示例
│   ├── multilingual_naturalness.py    ← [核心逻辑] 对话后处理三遍（repair/keywords/stabilize）
│   └── rule_loader.py                 ← [工具] YAML 规则 lru_cache 加载器
│
├── webapp/
│   ├── handlers.py                    ← [核心逻辑] 所有平台 REST API Handler（640行）
│   ├── db.py                          ← [核心逻辑] SQLite CRUD 封装（382行）
│   ├── task_runner.py                 ← [核心逻辑] 异步任务 worker + 队列
│   └── routes.py                      ← [配置] 平台路由注册
│
├── static/
│   ├── index.html                     ← [UI] 单页应用 HTML（含平台 CSS + JS）
│   ├── app.js                         ← [UI] 单页应用核心逻辑（2435行）
│   └── styles.css                     ← [UI] 样式表
│
├── config/
│   ├── app.yaml                       ← [配置文件] host/port/GUI title
│   ├── runtime.yaml                   ← [配置文件] bundle fallback 开关
│   ├── online_audio_ui.json           ← [配置文件] 18个行业场景预置 + UI 默认值
│   ├── text_quality_rules.yaml        ← [配置文件] 角色/冲突质量规则
│   ├── text_naturalness_rules.yaml    ← [配置文件] 每语言自然度规则
│   └── text_postprocess_rules.yaml   ← [配置文件] 词语改写规则
│
├── demo/
│   ├── 预置对话情景参数.txt            ← [数据] 22个预置场景参数（force-tracked）
│   └── training_long_dialogue/        ← [数据] few-shot 语料库（630个文件）
│
├── build/demo_app/
│   └── SceneDialogueDemo.exe          ← [二进制] LLM 引擎（PyInstaller bundle，必须存在）
│
├── bin/
│   └── ffmpeg.exe                     ← [二进制] 音频拼接工具（Windows）
│
├── training/
│   ├── quality_scoring.py             ← [工具脚本] 100分质量打分器
│   ├── dialogue_validators.py         ← [工具脚本] 结构校验
│   ├── training_executor.py           ← [工具脚本] retry循环 + 分数门控
│   ├── training_storage.py            ← [工具脚本] 写入 passed/failed 树
│   └── plan_v2_data.py                ← [数据] 正样本对/模板/主题定义
│
├── tools/training/
│   ├── run_all_batches.py             ← [工具脚本] B0→B5 主入口
│   └── run_training_plan.py           ← [工具脚本] 单批次运行器
│
├── runtime/
│   ├── platform.db                    ← [运行时] SQLite 数据库（gitignored）
│   └── cache/embedded_bundle/         ← [运行时] bundle 解包缓存（gitignored）
│
└── storage/
    └── uploaded/                      ← [运行时] 上传文件存储目录（gitignored）
```

---

## 章节 4：脚本能力说明 / What Each Script Can Do

### `server_platform.py` ⭐ 主入口

**这个脚本是干什么的**

平台版服务器入口。它调用 `embedded_server_main.make_app()` 创建包含原有 demo 路由的 Tornado 应用，然后通过 `register_platform_routes()` 追加平台 API 路由，初始化 SQLite 数据库，并在 IOLoop 中启动异步任务 worker。

**它能做哪些事**
- 启动包含全部功能的 Tornado HTTP 服务（默认 `0.0.0.0:8899`）
- 初始化数据库（创建 tasks/audio_files/folders 三张表，幂等）
- 在后台线程预热 manifest 缓存
- 启动异步任务 worker，监听队列执行批量生成任务
- 打印所有局域网访问地址和数据库路径

**如何调用**
```bash
python server_platform.py
# 或用环境变量覆盖
DEMO_APP_PORT=9000 python server_platform.py
```

---

### `src/demo_app/embedded_server_main.py` ⭐ 核心生成引擎（2173行）

**这个脚本是干什么的**

整个系统最重的模块。它既是 Tornado 应用工厂（`make_app()`），又包含 LLM bundle 加载、文本生成、TTS 音频合成的全部逻辑。PyInstaller `.exe` bundle 在此模块中被解包并通过 importlib 加载，提供 `_generate_dialogue_lines()` LLM 调用能力。

**它能做哪些事**
- 检查 bundle 缓存是否新鲜（`_cache_is_fresh()`），必要时从 `.exe` 中提取 `.pyc` 模块
- 向 Tornado 注册所有原始路由（`/`、`/api/generate_text`、`/api/synthesize_audio` 等）
- 接受文本生成请求：参数清洗 → 语言规范化 → few-shot 注入 → LLM 调用 → 三遍后处理 → 写入 `demo/` 目录
- 接受音频合成请求：查找 manifest → 分配声线 → asyncio 并发 TTS → ffmpeg 拼接 → 返回文件路径
- 对外暴露 `_generate_text_payload()` 和 `_synthesize_audio_from_lines()` 供 task_runner 调用

**主要函数**

| 函数 | 职责 |
|------|------|
| `make_app()` | 创建 Tornado Application，注册所有原始路由 |
| `load_bundle_server()` | 解包 .exe，importlib 加载 LLM 模块，返回 BundleServer |
| `_cache_is_fresh()` | 对比 .exe mtime 与缓存元数据，决定是否重新解包 |
| `_generate_long_dialogue_lines()` | 循环调用 bundle LLM，直到达到目标字数 |
| `_synthesize_audio_from_lines()` | 并发 edge_tts.Communicate.save()，pydub 探时长，ffmpeg 拼接 |
| `_canonical_language()` | 中英文/简写统一映射到英文名，如"中文"→"Chinese" |
| `_voice_for_speaker()` | 按语言 + 说话人编号从 VOICE_CATALOG 选声线，支持自定义 voice_map |
| `active_static_dir()` | 优先用 `static/`，否则回退 bundle 内静态资源 |
| `_ensure_manifest_cache()` | 扫描 `demo/` 目录所有 manifest.json，填充 LRU 缓存 |

**VOICE_CATALOG 支持的语言**：Chinese, English, Japanese, Korean, French, German, Spanish, Portuguese, Italian, Russian, Arabic, Indonesian, Cantonese（13种）

---

### `webapp/handlers.py` ⭐ 平台 REST API（640行）

**这个脚本是干什么的**

所有 `/api/platform/*` 路由的 RequestHandler 实现。以 `PlatformHandler` 为基类，统一处理 JSON 序列化、CORS 头、错误响应格式。

**路由清单**

| 路由 | Handler | 说明 |
|------|---------|------|
| GET /api/platform/tasks | TasksHandler | 任务列表（limit/offset 分页） |
| POST /api/platform/tasks | TasksHandler | 创建任务；`_import:true` 时跳过队列直接标记 completed |
| DELETE /api/platform/tasks?status=completed | TasksHandler | 清空已完成任务 |
| GET/POST/DELETE /api/platform/tasks/:id | TaskHandler | 查询/重试/删除单个任务 |
| GET/POST /api/platform/files | FilesHandler | 文件列表/注册旧 demo 生成文件 |
| GET/PUT/DELETE /api/platform/files/:id | FileHandler | 查询/更新元数据/软删除 |
| GET /api/platform/files/:id/download | FileDownloadHandler | 下载音频文件 |
| GET /api/platform/files/:id/transcript | FileTranscriptHandler | 下载转写（JSON/SRT） |
| POST /api/platform/upload | UploadHandler | 上传音频文件（multipart） |
| GET/POST /api/platform/folders | FoldersHandler | 文件夹树/新建文件夹（最深3层） |
| PUT/DELETE /api/platform/folders/:id | FolderHandler | 重命名/删除文件夹 |
| GET /api/platform/search | SearchHandler | 全局搜索 |
| GET /api/platform/trash | TrashHandler | 回收站列表 |
| POST /api/platform/trash/:id/restore | TrashRestoreHandler | 从回收站恢复 |
| DELETE /api/platform/trash/:id | TrashDeleteHandler | 永久删除（含磁盘文件） |
| POST /api/platform/batch/move | BatchMoveHandler | 批量移动文件到文件夹 |
| POST /api/platform/batch/delete | BatchDeleteHandler | 批量软删除 |
| GET /api/platform/batch/download | BatchDownloadHandler | 批量打包为 ZIP 下载 |
| GET /api/platform/stats | StatsHandler | 平台统计：文件数/时长/语言分布/场景分布 |
| GET /legacy | LegacyPageHandler | 旧版 demo 页面 |

**特殊机制：`_import: true`**

当 app.js 旧版弹框生成音频后，会调用 `POST /api/platform/tasks` 并附带 `_import:true`，此时 handler 直接创建已完成状态的任务记录，不入队列，使该文件出现在任务列表中。

---

### `webapp/db.py` ⭐ 数据库层（382行）

**这个脚本是干什么的**

SQLite CRUD 封装。数据库文件路径为 `runtime/platform.db`（相对于项目根目录）。首次运行自动创建表结构，WAL 模式开启。

**三张表**

| 表 | 主键 | 核心字段 |
|----|------|---------|
| tasks | task_id (hex16) | status, generation_mode, topic, language, people_count, word_count, template, keywords, voice_map, file_id |
| audio_files | file_id (hex16) | file_name, file_path, source(generated/uploaded), duration, format, language, scene, folder_id, deleted |
| folders | folder_id (hex16) | name, parent_id（支持嵌套树） |

**status 流转**：`queued` → `generating_text` → `synthesizing` → `completed` / `failed`

**并发限制**：同时 active（queued+generating_text+synthesizing）任务最多 3 个

---

### `webapp/task_runner.py` ⭐ 异步任务 Worker

**这个脚本是干什么的**

维护一个 `asyncio.Queue`，接收 task_id 入队，由单一 async worker 协程依次处理。状态流转全部写入 DB。通过懒加载（在第一个任务到来时才 import embedded_server_main）避免启动时加载 bundle 耽误响应。

**核心流程**（`_process_task(task_id)`）
1. 从 DB 读取任务参数
2. 懒加载 `_generate_text_payload()` 和 `_synthesize_audio_from_lines()`
3. 更新状态 → `generating_text`，调用文本生成
4. 更新状态 → `synthesizing`，调用音频合成
5. 写入 audio_files 表，更新任务 → `completed`（带 file_id）
6. 任何异常 → 更新状态 → `failed`（带 error_msg）

**direct 模式**：任务 `generation_mode == "direct"` 时跳过文本生成，直接用 `input_text` 合成音频。

---

### `static/app.js` ⭐ 前端核心逻辑（2435行）

**这个脚本是干什么的**

单页应用的全部 JS 逻辑，包括 UI 渲染、表单状态管理、API 调用、平台文件管理界面。

**两种生成模式**
- **LLM 模式**：选模板 → 填主题/关键词/字数 → `POST /api/generate_text` → `POST /api/synthesize_audio` → 注册到平台（`POST /api/platform/files` + `POST /api/platform/tasks` with `_import:true`）
- **手动模式**：直接粘贴对话文本 → 跳过文本生成 → 直接合成

**关键 API 函数**（推测，基于 handler 路由分析）
- `renderModeUi()` — 切换 LLM/manual 模式的 UI 状态
- `showConfirm(title, desc, onOk)` — 确认弹框（平台风格，void 回调）；`showConfirm(msg)` — Promise 风格（app.js 原生调用）
- `minimizeGenModal()` / `restoreGenModal()` — 生成弹框最小化到悬浮胶囊

---

## 章节 5：优缺点分析 / Strengths and Limitations

### 优点

- **零外部依赖的 LLM**：LLM 引擎打包为 .exe，无需配置 API Key 或外部服务，离线可用
- **清晰的双模式设计**：LLM 模式和手动模式分工明确，适配不同使用场景
- **13语言 TTS**：Edge TTS 覆盖广，配置简单，无额外成本
- **平台兼容性**：旧版 demo 接口完全保留，server.py 仍可独立运行
- **任务持久化**：SQLite WAL 模式，任务状态在服务重启后不丢失
- **后处理质量保证**：三遍 repair → keywords → stabilize 保证输出自然度

### 局限性

- **LLM 能力固化**：模型版本锁定在 `.exe` bundle 中，升级需重新打包，无法动态调整
- **单 worker 顺序执行**：`asyncio.Queue` + 单协程，无并行生成，高并发下吞吐有限
- **并发上限 3 个**：硬编码的限制，大量任务需排队等待
- **ffmpeg 依赖本地 binary**：Windows 路径硬编码 `bin/ffmpeg.exe`，跨平台需要额外配置
- **前端 2435 行单文件 JS**：无模块化/打包工具，可读性和可测试性较低
- **无认证鉴权**：所有 API 端口无需登录，不适合多用户/网络公开部署

### 潜在风险

- `embedded_server_main.py` 2173行单文件架构，后续扩展极易变得更加难以维护
- 根目录下历史遗留的 `platform.db`/`.db-shm`/`.db-wal` 文件可能与 `runtime/platform.db` 发生混淆

### 评分

| 维度 | 评分 | 理由 |
|------|------|------|
| 可维护性 | ⭐⭐⭐ | embedded_server_main.py 过于庞大；webapp 层分离合理 |
| 可扩展性 | ⭐⭐⭐ | platform 路由可扩展；LLM 层难以扩展（bundle 固化） |

### 最值得重构的地方

1. **`embedded_server_main.py`** — 拆分为 `bundle_loader.py`、`text_pipeline.py`、`audio_pipeline.py`、`http_handlers.py` 四个模块，每个 ≤500 行
2. **`static/app.js`** — 引入模块化构建（Vite/ESBuild），按功能拆分为 `platformApi.js`、`generateModal.js`、`fileManager.js` 等
3. **task_runner.py 并发** — 将单 worker 改为有限并发 worker 池（如 `asyncio.Semaphore(3)`），去掉 handler 层的 count_active_tasks 硬限制

---

## 章节 6：内部调用与实现逻辑 / Internal Flow and Call Graph

### LLM 模式完整请求链

**Step 1** — 用户在 `static/index.html` 填写表单（模板/主题/语言/字数/说话人数）

**Step 2** — `app.js` POST `/api/generate_text`

**Step 3** — `GenerateTextHandler.post()` in `embedded_server_main.py`：
  - `_safe_profile()` 提取用户画像字段
  - `_safe_generation_context()` 提取场景上下文字段
  - `_canonical_language()` 规范化语言
  - `_sanitize_profile_for_language()` 将非 CJK 语言的 profile 字段翻译为目标语言
  - `get_few_shot_example()` 从 `demo/training_long_dialogue/` 查找同域名语料注入 prompt
  - `_generate_long_dialogue_lines()` → 循环调用 `_BUNDLE_SERVER.generate_dialogue_lines()`，直到累积字数满足目标
  - `repair_dialogue_quality()` → `merge_keywords_into_lines()` → `stabilize_dialogue_constraints()`（三遍后处理）
  - 写入 `demo/{timestamp}/{basename}.txt` + `manifest.json`
  - 写入 `_manifest_cache` LRU（上限500条）
  - 返回 `{ dialogue_id, line_count, word_count, title }`

**Step 4** — `app.js` POST `/api/synthesize_audio`

**Step 5** — `SynthesizeAudioHandler.post()` in `embedded_server_main.py`：
  - `_find_manifest()` 先查 LRU 缓存，未命中则扫磁盘
  - `_voice_for_speaker()` 为每个说话人从 VOICE_CATALOG 选声线（或用 voice_map 覆盖）
  - `asyncio.gather` + `Semaphore(5)` 并发调用 `edge_tts.Communicate.save()`，每段一个 `.mp3` 临时文件
  - `pydub.AudioSegment.from_file()` 读取各段时长（仅探测，不保留）
  - `subprocess.run(ffmpeg -f concat -safe 0 -i concat_list.txt ...)` 拼接为最终文件
  - `finally` 块清理所有临时 `.mp3` 片段
  - 返回 `{ audio_url, duration, file_path, title }`

**Step 6** — `app.js` POST `/api/platform/files` 注册文件到 DB

**Step 7** — `app.js` POST `/api/platform/tasks` with `_import:true` 记录已完成任务

### 平台任务队列链（平台页发起任务时）

```
TasksHandler.post()
  └─ db.create_task()                → tasks 表新增 status=queued 行
  └─ enqueue(task_id)                → _task_queue.put_nowait(task_id)
      └─ _worker() (async loop)
           └─ _process_task(task_id)
                ├─ import embedded_server_main (懒加载)
                ├─ db.update_task_status(generating_text)
                ├─ _generate_text_payload()
                │    └─ [same as Step 3 above]
                ├─ db.update_task_status(synthesizing)
                ├─ _synthesize_audio_from_lines()
                │    └─ [same as Step 5 above]
                ├─ db.create_audio_file()
                └─ db.update_task_status(completed, file_id=...)
```

### Bundle 加载链

```
server_platform.py → make_app()
  └─ embedded_server_main 模块加载时
       └─ _BUNDLE_SERVER = None (初始)

首次生成请求 → GenerateTextHandler.post()
  └─ load_bundle_server() [如果 _BUNDLE_SERVER is None]
       ├─ _cache_is_fresh() → 检查 META_FILE vs .exe mtime
       ├─ 如果缓存过期:
       │    └─ CArchiveReader(SceneDialogueDemo.exe) → 提取 .pyc → MODULE_CACHE/
       └─ importlib.util.spec_from_file_location() → 加载 server.pyc → BundleServer()
```

### 数据流

```
用户输入 (topic/template/language/people_count/word_count)
    ↓
embedded_server_main (参数清洗 + few-shot 注入)
    ↓
BundleServer.generate_dialogue_lines() [LLM]
    ↓
multilingual_naturalness (repair → keywords → stabilize)
    ↓
demo/{timestamp}/dialogue.txt + manifest.json
    ↓
edge_tts x N并发 → 临时 .mp3 片段
    ↓
ffmpeg concat → demo/{timestamp}/dialogue.mp3
    ↓
webapp.db (audio_files + tasks 记录)
    ↓
static/ 前端展示 + 下载
```

### 外部资源调用

| 资源类型 | 名称 | 调用位置 | 说明 |
|---------|------|---------|------|
| 本地二进制 | SceneDialogueDemo.exe | embedded_server_main.py:load_bundle_server() | LLM 推理引擎 |
| 本地二进制 | bin/ffmpeg.exe | embedded_server_main.py:_ffmpeg_path() | 音频拼接 |
| 网络服务 | edge-tts (Microsoft Azure) | embedded_server_main.py:SynthesizeAudioHandler | TTS 合成，需联网 |
| 网络服务 | Google Translate | embedded_server_main.py:_sanitize_profile_for_language() | 非 CJK 语言时翻译 profile 字段，import 失败时静默跳过 |
| 本地文件 | demo/training_long_dialogue/ | few_shot_selector.py | few-shot 语料，630个文件 |
| 本地文件 | config/*.yaml | rule_loader.py | YAML 规则，lru_cache，重启才刷新 |

---

## 章节 7：复杂脚本深度解读 / Deep Technical Notes

### `src/demo_app/embedded_server_main.py`（2173行，最复杂）

#### 全局状态清单

| 变量 | 类型 | 用途 | 线程安全 |
|------|------|------|---------|
| `_BUNDLE_SERVER` | `BundleServer \| None` | LLM 引擎实例，首次请求时初始化 | 无锁，初始化后只读（实际安全） |
| `_manifest_cache` | `OrderedDict[str, tuple[Path,dict]]` | LRU 映射 dialogue_id → (path, manifest)，上限500 | `_manifest_cache_lock` 保护 |
| `_manifest_cache_loaded` | `bool` | 是否已完成全量扫描，避免重复扫磁盘 | 同锁保护 |
| `_ONLINE_AUDIO_CONFIG_CACHE` | `dict \| None` | UI 配置缓存，进程内永久有效 | 无写竞争（初始化后只读） |
| `_PRESET_TOPICS_CACHE` | `list \| None` | 预置场景列表缓存 | 同上 |

#### 容易看不懂的设计

**1. `_cache_is_fresh()` 双档案检查**

同时检查 `.exe` 和 `.pkg` 两个 archive 的 mtime，但当 `.pkg` 不存在时只做 module 层检查（for 训练/批量场景，不需要 UI 静态资源）。这个 early-return 防止 fork 后无 asset 包时启动失败。

**2. `Semaphore(5)` TTS 并发**

每个对话有 N 个说话人轮次，最多同时 5 个 edge_tts 连接。设置太高会触发 Azure 速率限制，设置太低合成慢。5 是经验值，没有配置化。

**3. `_generate_long_dialogue_lines()` 循环生成**

单次 LLM 调用可能字数不够，所以有一个 while 循环：检查累积字数，不足则追加调用，同时做说话人去重（避免同一说话人连续出现）。这个循环最多调用 LLM 3 次（推测），每次都会追加 few-shot。

**4. `manifest.json` + `_manifest_cache` LRU**

manifest 记录了对话文件的元数据（路径、标题、行数等）。服务启动时 `_ensure_manifest_cache()` 在后台线程全量扫描 `demo/` 目录。请求到来时先查 OrderedDict（O(1)），未命中才扫磁盘。LRU 超过 500 条时弹出最旧的。

**5. `f-string SQL` 在 `db.py`**

`update_task_status` 和 `update_audio_file` 使用了 f-string 拼接 `SET k=?` 子句，但值通过参数化传入，因此不存在 SQL 注入风险（字段名来自代码内部，不来自用户输入）。

#### 隐式约定

- **对话文本格式**：必须是 `Speaker N: text` 格式，每行一个轮次，`_parse_lines()` 用 `: ` 分割（第一个冒号空格）
- **文件命名**：`{安全题目}_{timestamp}` 格式，`_safe_file_component()` 过滤 `\/:*?"<>|` 和多余空白
- **few-shot 文件名规范**：`{domain_id}_{lang_short}_spk{N}_wc5000.txt`，如 `medical_zh_spk3_wc5000.txt`
- **bundle 模块路径**：`MODULE_CACHE/server.pyc` 是 bundle 加载的锚点文件，不存在则触发重新解包
- **dialogue_id**：与 manifest 文件名的 basename 相同，可通过 `_find_manifest(dialogue_id)` 查找

#### 维护者建议

- **修改 VOICE_CATALOG**：改这个字典立即生效，但注意 edge_tts 声线名称必须精确，拼错会导致合成静默失败
- **修改 YAML 规则**：`config/text_*.yaml` 改完需要调用 `rule_loader.clear_rule_cache()` 或重启服务才生效
- **添加新语言**：需要同时修改 `_canonical_language()` 映射、`VOICE_CATALOG` 声线列表、`few_shot_selector.py` 中的 `_LANG_TO_SHORT`
- **bundle 升级**：必须替换 `build/demo_app/SceneDialogueDemo.exe` 并删除 `runtime/cache/embedded_bundle/`（下次启动自动重新解包）
- **最容易出错的地方**：`_generate_long_dialogue_lines()` 的去重逻辑和字数计算；ffmpeg concat 的临时文件路径（含非 ASCII 字符时需特别注意转义）

---

### `webapp/task_runner.py`

#### 关键设计：懒加载 embedded_server_main

`_process_task()` 在第一个任务到来时才执行 `from demo_app.embedded_server_main import ...`。这是因为 `embedded_server_main` 模块级别会触发 bundle 检查和 PyInstaller 相关 import（`CArchiveReader` 等），如果在 worker 线程启动时立即加载可能出现线程安全问题。懒加载保证了在 IOLoop 内、在第一次真实需要时才做重量级初始化。

#### Worker 单协程模型

```python
async def _worker():
    while True:
        task_id = await _task_queue.get()
        try:
            await _process_task(task_id)
        finally:
            _task_queue.task_done()
```

单协程顺序处理，不会有并发竞争。`enqueue()` 用 `put_nowait()` 非阻塞入队，调用方无需 await。`start_worker()` 通过 `asyncio.ensure_future()` 在当前 IOLoop 中启动，由 `server_platform.py` 在 IOLoop 启动后 0.1 秒延迟调用（确保 IOLoop 已就绪）。

---

*文档生成：通过 generate-demo-docs skill 手动执行，深读 5 个文件（server_platform.py, embedded_server_main.py前350行, handlers.py, db.py, task_runner.py），grep提取其余文件签名，22个预置场景来自 demo/预置对话情景参数.txt 直接读取。*
