# 语料生成平台 — PROJECT_EXPLANATION.md

> 最后更新：2026-05-05 | 分析文件：深读 4 个，grep 5 个，推测 6 个

---

## 章节 1：项目总览 / Executive Summary

### 一句话定义

这是一个**多说话人对话语料批量生成平台**，用于为 AI 训练自动生成多语言对话文本并合成高质量 TTS 音频。

### 核心能力

- **LLM 对话生成**：调用打包为 PyInstaller `.exe` 的 LLM Bundle，按行业模板生成自然对话脚本
- **多说话人 TTS 合成**：调用 Microsoft edge_tts Neural 声音，并发合成 + 自动重试
- **三轮后处理**：`repair → keywords → stabilize` 三遍 LLM 后处理确保对话质量
- **平台文件管理**：上传、归档、标签、文件夹、软删除/回收站、批量操作
- **异步任务队列**：最多 3 个并发生成任务，自动重试 + 崩溃恢复
- **多语言支持**：中/英/日/韩/法/德/西/葡/粤 9 种语言生成与 TTS 合成
- **训练管道**：B0–B5 共 65,628 个任务的批量训练数据生成

### 适合谁阅读

| 角色 | 建议章节 | 关注重点 |
|------|---------|---------|
| 新接手维护者 | 1→3→6 | 整体架构、文件地图、调用链 |
| 前端开发者 | 2→4（static/） | UI 功能、API 接口契约 |
| 后端开发者 | 4→7 | embedded_server_main / task_runner |
| AI 训练工程师 | 2（训练管道）→7 | 训练批次、质量门禁、few-shot |
| DevOps / 运维 | 3→6（外部资源） | 依赖、进程、数据库、文件路径 |

### 快速理解摘要

这个项目是一套 **本地 Web 服务**，运行在 `http://127.0.0.1:8899/`。用户在浏览器里配置对话参数（行业、语言、说话人数、字数），后端调用内嵌 LLM 生成多轮对话脚本，再由 Microsoft TTS 引擎逐段合成音频，最后用 ffmpeg 拼接成完整 MP3。生成的文件通过 SQLite 数据库统一管理，支持按文件夹组织、标签过滤、回收站还原。平台同时具备训练管道，可批量生成 6.5 万条训练样本，并通过质量门禁过滤低质语料。整个系统无外部云依赖（TTS 除外），可完全本地化运行。

---

## 章节 2：功能清单 / Feature Breakdown

### 核心功能

#### 对话文本生成（LLM 模式）

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/demo_app/embedded_server_main.py` → `_generate_text_payload()` |
| 功能作用 | 调用内嵌 Bundle LLM 生成多说话人对话脚本 |
| 输入 | 行业主题、场景描述、语言、说话人数、字数目标、关键词、few-shot 样例 |
| 输出 | `Speaker N: 文本` 格式对话文本、manifest.json、.txt 文件 |
| 适用场景 | 需要 AI 自动创作对话内容时 |
| 依赖模块 | `multilingual_naturalness.py`、`few_shot_selector.py`、`rule_loader.py` |

#### 对话音频合成（TTS 模式）

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/demo_app/embedded_server_main.py` → `_synthesize_audio_from_lines()` |
| 功能作用 | 将对话文本逐段调用 edge_tts 合成，ffmpeg 拼接为完整音频 |
| 输入 | 对话行列表、语言、音色映射、输出格式（mp3/wav/m4a） |
| 输出 | 完整音频文件、可选 SRT 字幕、可选 segments JSON |
| 适用场景 | 文本已就绪，需要高质量 TTS 音频时 |
| 依赖模块 | `edge_tts`、`pydub`、`ffmpeg`（bin/ffmpeg.exe） |

#### 直接输入模式（Manual）

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/demo_app/embedded_server_main.py` → `CreateDialogueFromTextHandler` |
| 功能作用 | 用户粘贴预写对话文本，跳过 LLM 直接合成音频 |
| 输入 | `Speaker N: 台词` 格式纯文本 |
| 输出 | 音频文件 + manifest.json |
| 适用场景 | 已有脚本，只需 TTS 转音频时 |
| 依赖模块 | 同 TTS 合成 |

### 辅助功能

#### 平台文件管理

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/webapp/handlers.py`、`src/webapp/db.py` |
| 功能作用 | 音频文件的 CRUD、文件夹组织、标签、软删除、搜索、批量操作、下载 |
| 输入 | HTTP REST 请求 |
| 输出 | JSON 响应；ZIP 批量下载 |
| 适用场景 | 整理和检索已生成的语料库 |
| 依赖模块 | SQLite（runtime/platform.db） |

#### 异步任务队列

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/webapp/task_runner.py` |
| 功能作用 | 将生成任务入队，后台 3 个 worker 并发处理，自动崩溃恢复 |
| 输入 | POST `/api/platform/tasks` 的任务参数 |
| 输出 | 任务状态流转：`queued → generating_text → synthesizing → completed/failed` |
| 适用场景 | 批量生成、不需要等待即时结果时 |
| 依赖模块 | `asyncio.Queue`、`embedded_server_main`、`db.py` |

#### 多语言文本后处理

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/demo_app/multilingual_naturalness.py` |
| 功能作用 | 三遍 LLM 后处理：质量修复 → 关键词注入 → 对话稳定化 |
| 输入 | 原始对话行列表、语言、规则配置 |
| 输出 | 质量达标的对话行列表 |
| 适用场景 | LLM 生成后对话存在重复、缺关键词、角色名混乱等问题时自动修复 |
| 依赖模块 | `rule_loader.py`、`text_quality_rules.yaml` 等三个 YAML |

### 工具功能

#### Few-Shot 样例检索

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/demo_app/few_shot_selector.py` |
| 功能作用 | 从 630 个训练语料文件中按行业+语言检索对话片段注入生成上下文 |
| 输入 | domain（行业标签）、language（语言名） |
| 输出 | 对话文本摘录（≤1000 字），无匹配返回空字符串 |
| 适用场景 | 引导 LLM 对齐目标行业风格 |
| 依赖模块 | `demo-data/training_long_dialogue/`（630 个文件） |

#### 训练批次管道

| 字段 | 说明 |
|------|------|
| 对应脚本 | `tools/training/run_all_batches.py` |
| 功能作用 | 按 B0–B5 批次顺序运行 65,628 个训练样本生成任务，支持 --resume |
| 输入 | 批次 JSONL 任务文件（`training/data/training_jobs_b*.jsonl`） |
| 输出 | `output/training_v2/{batch}/passed/` 通过质量门禁的 JSON 样本 |
| 适用场景 | 为 LLM 微调生成高质量对话训练集 |
| 依赖模块 | `training/quality_scoring.py`、`training/training_executor.py` |

---

## 章节 3：文件与脚本地图 / Project File Map

```
audio-synthesis-demo/
│
├── server_platform.py          ← [主入口] 启动 Tornado + 数据库 + 任务 worker
├── server.py                   ← [辅助入口] 仅 demo 路由（无平台功能），向后兼容
├── start_platform.bat          ← [工具脚本] Windows 双击启动
│
├── src/
│   ├── demo_app/
│   │   ├── embedded_server_main.py   ← [核心逻辑] 2204 行：TTS 管道、LLM 调用、Tornado 路由、manifest 缓存
│   │   ├── multilingual_naturalness.py ← [核心逻辑] 2212 行：多语言后处理三遍算法
│   │   ├── few_shot_selector.py      ← [辅助逻辑] Few-shot 语料检索，LRU 文件缓存
│   │   ├── training_few_shot.py      ← [辅助逻辑] 训练输出中的 topic 匹配样例
│   │   └── rule_loader.py            ← [辅助逻辑] YAML 规则 lru_cache 加载器
│   └── webapp/
│       ├── handlers.py               ← [核心逻辑] 所有 /api/platform/* REST handler，758 行
│       ├── db.py                     ← [核心逻辑] SQLite CRUD，3 张表，382 行
│       ├── task_runner.py            ← [核心逻辑] 异步任务 worker，崩溃恢复，401 行
│       └── routes.py                 ← [配置文件] 路由注册表
│
├── static/
│   ├── index.html              ← [核心逻辑] 单页应用 HTML + 内联 JS（平台 UI，导航、模态框、详情页）
│   ├── app.js                  ← [核心逻辑] ~100KB：生成模态框状态机、任务管理、音频播放
│   └── styles.css              ← [辅助脚本] CSS 变量、亮/暗主题、组件样式
│
├── config/
│   ├── app.yaml                ← [配置文件] host/port/TTS 并发数
│   ├── runtime.yaml            ← [配置文件] 后端路由策略（bundle fallback 开关）
│   ├── preset_topics.json      ← [配置文件] 22 个预置对话场景（行业/角色/关键词）
│   ├── online_audio_ui.json    ← [配置文件] 18 个 UI 行业模板 + UI 默认值
│   ├── text_quality_rules.yaml ← [配置文件] 角色/冲突质量规则
│   ├── text_naturalness_rules.yaml ← [配置文件] 各语言自然度规则
│   ├── text_postprocess_rules.yaml ← [配置文件] 术语重写规则
│   └── requirements.txt        ← [配置文件] Python 依赖
│
├── build/
│   ├── demo_app/SceneDialogueDemo.exe ← [数据/样例] LLM Bundle（Windows，已提交）
│   ├── demo_app/SceneDialogueDemo.pkg ← [数据/样例] LLM Bundle（macOS，已提交）
│   └── demo_app.spec           ← [配置文件] PyInstaller 打包规格
│
├── demo-data/
│   ├── training_long_dialogue/ ← [数据/样例] 630 个 Few-shot 语料文件（14 行业 × 9 语言）
│   └── {timestamp}/            ← [数据/样例] 历史生成结果（manifest.json + txt + mp3）
│
├── training/                   ← [工具脚本] 训练管道：质量门禁、执行器、批次构建
├── tools/training/             ← [工具脚本] run_all_batches.py 等运行入口
├── tools/analysis/             ← [工具脚本] 训练结果分析工具
├── scripts/                    ← [工具脚本] CI 门禁、质量检查、项目守护脚本
├── tests/                      ← [测试] pytest 测试套件（约 20 个模块）
├── bin/ffmpeg.exe              ← [数据/样例] ffmpeg 可执行文件（Windows）
├── runtime/platform.db         ← [数据/样例] SQLite 数据库（gitignored，自动创建）
└── storage/generated/          ← [数据/样例] 平台任务生成的音频存储（gitignored）
```

---

## 章节 4：脚本能力说明 / What Each Script Can Do

### `server_platform.py` ⭐ 主入口

**这个脚本是干什么的**

服务启动的唯一入口。它按顺序做 6 件事：初始化 SQLite 数据库 → 构建 Tornado App（含所有 legacy 路由）→ 加载 Bundle LLM → 注册平台 API 路由 → 启动 Tornado 监听 → 后台启动 manifest 缓存预热 + 任务 worker。

**它能做哪些事**
- 启动完整 Web 服务（包含 legacy demo + 平台 API + 静态文件服务）
- 自动初始化数据库表结构（幂等）
- 若 Bundle LLM 加载失败，立即 `sys.exit(1)` 而不是在第一个请求时才崩溃
- 打印所有可访问的本地 URL（含局域网 IP）

**如何调用**
```bash
python server_platform.py
# 或双击
start_platform.bat
```

**成功后产生什么**
- Tornado 在 `http://127.0.0.1:8899/` 开始监听
- `runtime/platform.db` 自动创建（如不存在）
- 后台 3 个任务 worker 协程运行

---

### `src/demo_app/embedded_server_main.py` ⭐ 核心引擎

**这个脚本是干什么的**

2204 行的系统核心。职责包含：Bundle LLM 加载与提取、对话文本生成（含多段并发 + 字数补全循环）、TTS 音频合成（edge_tts 并发 + 重试）、所有 legacy HTTP 路由（`GenerateTextHandler`、`GenerateAudioCustomHandler` 等）、manifest 文件的 LRU 缓存管理。

**主要对外函数**

| 函数 | 作用 |
|------|------|
| `make_app()` | 创建 Tornado Application，注册所有 legacy 路由 |
| `load_bundle_server()` | 加载或返回已缓存的 Bundle LLM 实例 |
| `_generate_text_payload(bundle_server, payload)` | 端到端文本生成（含后处理三遍） |
| `_synthesize_audio_from_lines(lines, language, ...)` | 并发 TTS + ffmpeg 拼接，返回音频路径 |
| `_find_manifest(dialogue_id)` | 从 LRU 缓存或磁盘查找 manifest |
| `ensure_embedded_runtime()` | 提取 Bundle 内嵌模块到 `runtime/cache/` |
| `active_static_dir()` | 返回 `static/` 或 Bundle 内嵌 `static/` |

**如何调用**
```python
# 不直接调用，通过 server_platform.py 启动
# 平台内部调用示例：
from demo_app.embedded_server_main import load_bundle_server, _synthesize_audio_from_lines
```

**注意事项**
- `_BUNDLE_SERVER` 是全局单例，仅初始化一次，线程安全（只读）
- `_manifest_cache` 是 500 条 LRU OrderedDict，受 `_manifest_cache_lock` 保护
- `_TTS_CONCURRENCY` 默认值读自 `config/app.yaml`（tts_concurrency: 12）
- TTS 失败会自动尝试 2 次重试（2s 延迟 + 4s 延迟），仍失败则 fallback 到 Bundle 内置 TTS

---

### `src/demo_app/multilingual_naturalness.py` ⭐ 后处理引擎

**这个脚本是干什么的**

2212 行，专门处理 LLM 生成文本的质量问题。实现三遍后处理：
1. `repair_dialogue_quality` — 修复对话结构问题（说话人角色混乱、内容重复、台词过短）
2. `enforce_keywords_in_lines` — 将业务关键词注入到对话中
3. `stabilize_dialogue_constraints` — 稳定化约束（说话人数量、字数、主题一致性）

同时包含大量语言专用逻辑：中文角色名生成、英文角色名转写、CJK 污染检测等。

**关键函数**

| 函数 | 作用 |
|------|------|
| `polish_generated_lines(lines, language, ...)` | 统一入口：调度三遍后处理 |
| `enforce_keywords_in_lines(lines, keywords, ...)` | 关键词注入（O(n+k) 复杂度） |
| `canonical_language(value)` | 语言名称标准化 |
| `_rewrite_chinese_line(...)` | 中文单行重写（含角色名、主题引用） |
| `_filter_cjk_contamination(...)` | 过滤日/韩/拉丁语中的中文污染 |

---

### `src/webapp/handlers.py` — 平台 API Handler

**这个脚本是干什么的**

758 行，所有 `/api/platform/*` 路由的请求处理器。每个资源（Tasks/Files/Folders/Trash/Batch/Stats）对应一个 Handler 类，继承 `PlatformHandler` 基类（统一 CORS、JSON 序列化、错误格式）。

**覆盖的 API**
- **Tasks**：创建/列表/详情/删除/重试任务；支持 `_import:true` 直接写入已完成任务
- **Files**：列表（含搜索/过滤/分页）、详情、更新元数据、软删除、下载、转写获取
- **Folders**：创建/重命名/删除（级联软删除文件夹内文件）
- **Upload**：接收 multipart 上传，探测音频时长，写库
- **Batch**：批量移动/删除/打包下载（ZIP）
- **Stats**：文件总数/总时长/总大小/进行中任务数/语言分布/场景分布

---

### `src/webapp/db.py` — SQLite 数据层

**这个脚本是干什么的**

382 行纯粹的数据库辅助层。WAL 模式 SQLite，三张表：`tasks`、`audio_files`、`folders`。每次调用都打开新连接（`check_same_thread=False`），靠 WAL 保证并发安全。没有 ORM，全部手写 SQL。

**表结构**

| 表 | 主键 | 关键字段 |
|---|---|---|
| `tasks` | task_id | status, generation_mode, topic, language, file_id |
| `audio_files` | file_id | file_path, duration, format, tags, folder_id, deleted |
| `folders` | folder_id | name, parent_id |

---

### `src/webapp/task_runner.py` — 异步任务 Worker

**这个脚本是干什么的**

401 行，实现"提交即返回，后台处理"的任务队列。使用 `asyncio.Queue` + `asyncio.ensure_future` 在 Tornado IOLoop 内跑 3 个并发 worker 协程。每个任务按状态机：`queued → generating_text → synthesizing → completed/failed`。

**特殊功能**
- `_recover_stuck_tasks()`：启动时自动重置上次崩溃残留的中间状态任务（超 10 分钟的）
- `backfill_scenes()`：启动时一次性回填历史 `scene='other'` 文件的场景分类
- `_guess_scene(template, topic)`：从模板标签和主题文本推断 12 类场景分类

---

### `static/index.html` + `static/app.js` — 单页前端

**index.html（平台 UI）**

内联大量 JavaScript，实现 5 个页面（全部文件/我的文件/生成任务/回收站/文件详情），导航切换不刷新。关键功能：
- 文件列表 + 15 条/页分页
- 生成任务列表 + 18 条/页分页（含 3s 轮询自动刷新）
- 音频详情页：可拖拽进度条、一键复制文本、离开页面自动停止播放
- Stats 卡片：实时显示进行中任务数（含弹窗生成的 `_legacyInProgress` 计数器）

**app.js（生成模态框状态机）**

约 2600 行，控制"在线生成音频"弹窗：LLM 模式/直接输入模式切换、说话人音色选择（仅 Microsoft 当前可用声音）、文本预览编辑、进度状态管理、生成完成后注册到平台文件库。

---

## 章节 5：优缺点分析 / Strengths and Limitations

### 整体优点

- **零外部云依赖**：LLM 本地化（Bundle exe），唯一外部服务是 Microsoft edge_tts
- **单文件部署**：一个 exe + Python 依赖，无需 Docker 或独立数据库服务
- **渐进式加载**：Bundle 按需提取到 `runtime/cache/`，首次启动后热启动极快
- **完整软删除**：文件不会硬删，支持 30 天内回收站还原
- **质量门禁完善**：训练管道有 9 条强制拦截规则（语言混入、重复率、占位符等）

### 局限性

- **LLM 能力冻结**：LLM 打包在 exe 里，不升级 exe 无法改进模型
- **TTS 依赖外部服务**：edge_tts 依赖 Microsoft Azure，网络不稳定时会 fallback 到低质量 bundle TTS
- **单机无法水平扩展**：SQLite 不支持多进程写入，任务 worker 也是单进程
- **前端代码体积大**：`index.html` + `app.js` 合计约 13,000 行，缺乏模块化
- **弹窗生成绕过任务队列**：legacy 模态框直接调 API，不经 `tasks` 表，历史追踪不完整

### 可维护性评分

**⭐⭐⭐ 3/5**

理由：核心文件（`embedded_server_main.py`、`multilingual_naturalness.py`）各约 2200 行，函数粒度细但文件过大，新人定向困难。CLAUDE.md 文档详尽弥补了部分问题。

### 可扩展性评分

**⭐⭐⭐ 3/5**

理由：平台 API 层（handlers/db/routes）结构清晰、扩展容易；但 LLM 和 TTS 层受 Bundle 和 edge_tts 限制，替换成本高。

### 最值得重构的地方

1. **`embedded_server_main.py`（2204 行）**：建议拆分为 `tts_pipeline.py`（合成逻辑）+ `text_generator.py`（LLM 调用）+ `manifest_cache.py`（缓存管理），HTTP Handler 保持薄壳
2. **`multilingual_naturalness.py`（2212 行）**：按语言拆分为 `naturalness_zh.py`、`naturalness_en.py`、`naturalness_ja.py`，共用基类；当前文件中语言判断散布在数十个函数中
3. **弹窗生成与平台任务队列的割裂**：`app.js` 中 `submitAudioGeneration()` 应改为调用 `POST /api/platform/tasks`，让所有任务统一走队列，消除 `_legacyInProgress` 计数器 hack

---

## 章节 6：内部调用与实现逻辑 / Internal Flow and Call Graph

### 主流程 A：LLM 模式生成音频（弹窗）

```
Step 1  用户在弹窗填写参数 → app.js submitAudioGeneration()
Step 2  POST /api/create_dialogue_from_text（若无 dialogueId）
          ↓ CreateDialogueFromTextHandler → _create_manual_dialogue_payload()
          ↓ 分配 dialogue_id，写 .txt 和 manifest.json 到 demo-data/{timestamp}/
Step 3  POST /api/generate_audio_custom  
          ↓ GenerateAudioCustomHandler.post()
          ↓ _find_manifest(dialogue_id) → 从 LRU 缓存或磁盘读 manifest
          ↓ _dialogue_lines_from_text(text) → 解析对话行
          ↓ await _synthesize_audio_from_lines(...)
              ↓ edge_tts 并发合成（Semaphore(3) 限流）
              ↓ 失败：2s 延迟重试 → 4s 延迟二次重试 → 抛异常 fallback bundle TTS
              ↓ ffmpeg concat 拼接为完整 mp3
          ↓ 更新 manifest.json（audio_path / voice_map / warning）
Step 4  app.js 接收响应
          ↓ POST /api/platform/files（注册到平台文件库）
          ↓ POST /api/platform/tasks（_import:true，写入已完成任务记录）
          ↓ 刷新 loadHome() + loadStats()
```

### 主流程 B：平台任务队列生成

```
Step 1  用户点击"新建任务" → POST /api/platform/tasks
          ↓ TasksHandler.post() → db.create_task() → status='queued'
          ↓ enqueue(task_id) → asyncio Queue
Step 2  _worker() 协程取出 task_id → _process_task(task_id)
          ↓ db.update_task_status('generating_text')
          ↓ _generate_text_payload(bundle_server, payload) [run_in_executor，不阻塞 IOLoop]
          ↓ db.update_task_status('synthesizing')
          ↓ await _synthesize_audio_from_lines(...)
          ↓ db.create_audio_file(...) + db.update_task_status('completed', file_id=...)
Step 3  前端 3s 轮询 GET /api/platform/tasks → 显示进度
```

### 调用链（简化）

```
server_platform.main()
  ├─ init_db()                          [db.py]
  ├─ make_app()                         [embedded_server_main.py]
  ├─ load_bundle_server()               [embedded_server_main.py]
  │    └─ ensure_embedded_runtime()
  │         └─ _extract_bundle_modules() → 解压 .exe 内的 .pyc
  ├─ register_platform_routes(app)      [routes.py → handlers.py]
  └─ start_worker()                     [task_runner.py]
       ├─ _recover_stuck_tasks()
       ├─ backfill_scenes()
       └─ asyncio.ensure_future(_worker()) × 3

_generate_text_payload(bundle_server, payload)
  ├─ _normalize_request_params()
  ├─ _sanitize_profile_for_language()
  ├─ get_few_shot_example()             [few_shot_selector.py]
  ├─ _generate_long_dialogue_lines()    [ThreadPoolExecutor × 3 段并发]
  │    └─ bundle_server._generate_dialogue_lines()  ← LLM 调用
  └─ polish_generated_lines()          [multilingual_naturalness.py]
       ├─ repair_dialogue_quality()
       ├─ enforce_keywords_in_lines()
       └─ stabilize_dialogue_constraints()

_synthesize_audio_from_lines(lines, ...)
  ├─ _voice_for_speaker() × N          [VOICE_CATALOG 查表]
  ├─ asyncio.gather(_tts_one_safe × N) [Semaphore(3) 并发]
  ├─ 重试逻辑（2s / 4s）
  ├─ _probe_duration_secs() × N        [ffprobe 探针]
  └─ subprocess ffmpeg -f concat        [拼接最终音频]
```

### 数据流

```
用户输入参数
    │
    ▼
生成请求 payload（topic/language/people_count/keywords）
    │
    ▼ _normalize_request_params
标准化参数 + few-shot 注入
    │
    ▼ bundle_server._generate_dialogue_lines
原始对话行列表 [("Speaker 1", "台词..."), ...]
    │
    ▼ polish_generated_lines (3 遍后处理)
质量达标的对话行列表
    │
    ├──► 写 .txt 文件 + manifest.json → demo-data/{timestamp}/
    │
    ▼ _synthesize_audio_from_lines
N 个 .mp3 片段 (tmpdir)
    │
    ▼ ffmpeg concat
最终音频文件 (.mp3/.wav/.m4a)
    │
    ▼ db.create_audio_file
audio_files 表记录（含时长/大小/转写JSON）
```

### 外部资源调用

| 资源类型 | 名称 / 地址 | 调用位置 | 说明 |
|---------|-----------|---------|------|
| 进程（LLM） | `build/demo_app/SceneDialogueDemo.exe` | `_extract_bundle_modules()` | 提取 .pyc 后 importlib 加载，非 subprocess |
| 网络 API（TTS） | `speech.platform.bing.com`（WebSocket） | `edge_tts.Communicate.save()` | Microsoft Neural TTS，失败有 2 次重试 |
| 进程（音频工具） | `bin/ffmpeg.exe` | `subprocess.run(ffmpeg -f concat)` | 拼接音频片段 |
| 文件系统 | `runtime/platform.db` | `db._conn()` | SQLite WAL，自动创建 |
| 文件系统 | `demo-data/training_long_dialogue/` | `few_shot_selector.py` | 630 个 Few-shot 语料文件 |
| 文件系统 | `storage/generated/{task_id}/` | `task_runner._process_task()` | 平台任务生成结果存储 |
| 网络 API（翻译） | deep-translator | `_sanitize_profile_for_language()` | 非 CJK 语言时翻译 profile 字段（推测） |

---

## 章节 7：复杂脚本深度解读 / Deep Technical Notes

### `embedded_server_main.py` — TTS 合成管道深度解读

#### 全局状态清单

| 变量名 | 类型 | 用途 | 线程安全 |
|--------|------|------|---------|
| `_BUNDLE_SERVER` | `Any`（BundleServer） | 全局 LLM 实例，只读 | ✅ 只初始化一次 |
| `_manifest_cache` | `OrderedDict[str, tuple]` | 500 条 LRU：dialogue_id → (path, dict) | ✅ 受 `_manifest_cache_lock` 保护 |
| `_manifest_cache_lock` | `threading.Lock` | 保护 LRU 读写 | ✅ |
| `_ONLINE_AUDIO_CONFIG_CACHE` | `dict \| None` | UI 配置一次性加载 | ✅ 进程启动时写入，之后只读 |
| `_PRESET_TOPICS_CACHE` | `list \| None` | 22 预置场景，一次性加载 | ✅ 同上 |
| `_TTS_CONCURRENCY` | `int` | 默认 12（app.yaml 读取），控制并发 TTS 请求数 | ✅ 只读常量 |

#### TTS 合成流程（`_synthesize_audio_from_lines`）

1. 为每个对话行分配音色（`_voice_for_speaker`），跳过空行
2. 在临时目录（`tmpdir = demo-data/{timestamp}/_edited_tts_tmp_xxx/`）生成 `line_NNN.mp3`
3. `asyncio.gather` 并发调用 `_tts_one_safe`（Semaphore 限流）
4. 收集失败的索引，顺序重试（2s 延迟），仍失败二次重试（4s 延迟）
5. 若仍有失败，抛出 `RuntimeError` → 外层 `except` 捕获 → fallback 到 Bundle TTS
6. `_probe_duration_secs` 逐段用 ffprobe 探测时长（单次读取立即释放，不积累内存）
7. 写 `_concat.txt`，`subprocess ffmpeg -f concat` 拼接
8. `finally` 块清理所有临时 .mp3 片段

**容易出错的地方**
- `_tts_one_safe` 返回 `Exception | None`（不抛出），必须检查返回值而非 try-catch
- `segment_file = tmp_dir / f"line_{idx:03d}.mp3"` 使用 `/` 操作符（pathlib），不是字符串拼接
- ffmpeg concat 文件路径使用 `.as_posix()`（Windows 反斜杠会导致 ffmpeg 解析失败）

#### Bundle 加载机制（`ensure_embedded_runtime`）

PyInstaller `.exe` 本质是一个自展开 ZIP。`_extract_bundle_modules()` 用 `CArchiveReader` 读取 `.pkg` 存档，将 `.pyc` 模块解压到 `runtime/cache/embedded_bundle/`。`load_bundle_server()` 再用 `importlib.util.spec_from_file_location` 动态加载这些模块，返回 `BundleServer` 实例。缓存新鲜度通过 `_cache_is_fresh()` 检查 `.exe` 修改时间实现。

**隐式约定**：`runtime/cache/embedded_bundle/` 是 gitignored 的临时目录，每次服务启动如果 `.exe` 更新就重新提取；不能提交这个目录的内容。

---

### `multilingual_naturalness.py` — 三遍后处理深度解读

#### 三遍后处理的分工

| 遍次 | 函数 | 处理目标 |
|------|------|---------|
| 第 1 遍 | `repair_dialogue_quality` | 修复结构性缺陷：角色混乱、台词太短、内容重复率过高 |
| 第 2 遍 | `enforce_keywords_in_lines` | 将 `keyword_terms` 注入到指定说话人的台词中（倒序位置优先） |
| 第 3 遍 | `stabilize_dialogue_constraints` | 确保说话人轮次均衡、主题引用频率、行数达标 |

#### `enforce_keywords_in_lines` 算法说明

- 预先构建 `{speaker_id: [倒序行索引]}` 字典，O(n) 一次扫描
- 对每个关键词，选目标说话人最后出现的几行注入
- 总复杂度 O(n + k)（n 行数，k 关键词数），已从原始 O(n×k) 优化

#### CJK 污染检测

`_filter_cjk_contamination` 用于日/韩/拉丁语生成时检测并清除中文字符渗漏。检测逻辑：
- 日语：假名比例 < 8% 且中文比例 > 30% → 视为中文污染
- 韩语：韩文字符比例 < 5% → 污染
- 拉丁语：任意行中文字符 > 5% 且超过 15% 的行受影响 → 污染

#### 维护者建议

- **修改后处理规则前**：先运行 `python -m unittest tests.test_multilingual_naturalness` 验证
- **最容易踩坑**：`repair_dialogue_quality` 在完整重建时会跳过第 3 遍（`stabilize_dialogue_constraints`），这是有意的性能优化，不要恢复
- **新增语言支持**：需要同时修改 `VOICE_CATALOG`（embedded_server_main）、`canonical_language()`、`polish_generated_lines()` 的 dispatch 逻辑、以及 `few_shot_selector.py` 的 `_LANG_TO_SHORT` 映射

---

### `task_runner.py` — 任务 Worker 深度解读

#### 崩溃恢复机制

`_recover_stuck_tasks()` 在 `start_worker()` 时调用一次，用原生 sqlite3（不通过 db.py）将 `updated_at` 超过 10 分钟、状态为 `generating_text` 或 `synthesizing` 的任务重置为 `queued`。10 分钟阈值是保守设计——正常任务不会超过这个时间，但避免误重置正在处理中的任务。

#### 文本模式（text_only）路径

`generation_mode='text_only'` 时，完成 LLM 生成后直接跳过音频合成，将对话文本写为 `.txt` 文件，以 `duration=0.0`、`format='txt'` 注册到 `audio_files` 表。前端详情页通过 `format==='txt'` 判断显示文本预览而非音频播放器。

#### Worker 并发控制

`_MAX_WORKERS = 3`（与 `handlers.py` 中 `count_active_tasks() >= 3` 的上限一致）。每个 worker 是独立的 `asyncio.ensure_future(_worker())` 协程，共享同一个 `_task_queue`。因为都在同一 IOLoop 内，TTS 合成的 `await` 会自动让出，不会阻塞其他 worker 或 HTTP 请求处理。

---

*文档生成工具：generate-demo-docs skill | 分析时间：2026-05-05*
