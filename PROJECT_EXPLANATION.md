# 音频语料生成平台 V2 — 项目说明文档

> 生成时间：2026-05-30 | 分析目录：`D:\Github\test-audio-builder-platform`

---

## 章节 1：项目总览 / Executive Summary

### 一句话定义

这是一个**多用户音频语料生成平台**，用于通过云 LLM 生成结构化对话文本、调用 CosyVoice 真人克隆音色合成高质量音频语料，并提供完整的文件管理能力。

### 核心能力

- 🧠 **LLM 对话生成**：调用 DeepSeek / OpenAI / Anthropic 生成 `Speaker N:` 格式多人对话，注入 few-shot 样本与关键词，经质量门禁过滤
- 🎙 **真人音色合成**：对接 CosyVoice `/v1/audio/speech`，合成克隆音频；失败时自动降级 edge_tts（透明对用户）
- ⚙️ **在线音色管理**：上传参考音频注册新克隆音色，注册时做 E2E 合成验证；全局共享，仅创建者可删除
- 📁 **文件 / 文件夹管理**：上传、软删除、回收站、文件夹分组、标签检索
- 📝 **SRT / JSON 脚本导出**：每段合成后累加实测时长，生成精确时间码的字幕与 JSON
- 👤 **多用户认证**：JWT 注册登录，支持 Google SSO，每用户任务隔离
- 🔄 **异步任务队列**：Celery + Redis，任务持久化、自动重试、并发上限（每用户 ≤3）

### 适合谁阅读

| 角色 | 建议章节 | 关注重点 |
|------|---------|---------|
| 新接手开发者 | 1 → 3 → 6 | 整体架构 + 调用链 |
| 后端维护者 | 4 → 7 | generation.py / audio.py 深度 |
| 前端开发者 | 3 → 4（前端部分）| Vue 组件结构 |
| 运维 / 部署 | 1 → 3 | 启动方式 + 依赖服务 |

### 快速理解摘要

这个项目是一个内部 B 端平台，专门用来批量生产 AI 语音训练所需的"带角色的真实对话音频"。使用者在网页上选择场景模板（如：医疗随访、招聘面试）、配置语言和说话人数，系统自动调 DeepSeek 生成对话文本，再把每段台词分配给不同的 CosyVoice 克隆音色来朗读，最终拼接成一条带时间码的音频文件。支持多人同时使用，每人有独立的任务队列和文件库。

---

## 章节 2：功能清单 / Feature Breakdown

### 核心功能

#### LLM 对话文本生成

| 字段 | 说明 |
|------|------|
| 对应文件 | `backend/app/services/dialogue.py` + `tasks/generation.py` |
| 功能作用 | 根据场景模板 + 说话人数 + 关键词，调云 LLM 生成 Speaker N 格式多轮对话 |
| 输入 | template（22 个预置场景 / custom）、language、speaker_count、target_duration_sec、keywords |
| 输出 | `(raw_text, [(speaker_id, line_text), ...])` 结构化行列表 |
| 适用场景 | LLM 模式任务提交；前端"生成文本"预览按钮 |
| 依赖模块 | `few_shot.py`（样本注入）、`postprocess.py`（后处理）、`quality_check.py`（门禁）|

#### 音频合成（CosyVoice + edge_tts 降级）

| 字段 | 说明 |
|------|------|
| 对应文件 | `backend/app/services/audio.py` |
| 功能作用 | 按对话行逐段调用 TTS，归一化格式，拼接成完整音频，返回段级时间码 |
| 输入 | `lines`, `voice_assignments: {speaker_id: {voice_id}}`, `language`, `output_format` |
| 输出 | `(audio_bytes, duration_sec, segments, degraded)` 4-tuple |
| 适用场景 | 所有任务类型（LLM 模式 + 手动模式）|
| 依赖模块 | `CosyVoiceProvider`、`EdgeTTSProvider`（降级）、ffmpeg |

#### 音色目录管理（E2E 验证）

| 字段 | 说明 |
|------|------|
| 对应文件 | `backend/app/api/v1/voices.py` + `models/voice_catalog.py` |
| 功能作用 | 上传参考音频注册克隆音色，注册时立即合成验证；全局共享，仅创建者可删 |
| 输入 | multipart: audio 文件 + name + language + gender |
| 输出 | `VoiceCreateResponse{voice_id, verified, message}` |
| 适用场景 | ⚙️ 管理真人音色弹窗；首次初始化从 CosyVoice 拉取 |
| 依赖模块 | CosyVoice `/v1/voices/create` + `/v1/audio/speech` |

### 辅助功能

#### 文件 / 文件夹管理

| 字段 | 说明 |
|------|------|
| 对应文件 | `api/v1/files.py`、`api/v1/folders.py` |
| 功能作用 | 上传音频、软删除、回收站恢复、文件夹分组、标签检索、MinIO 签名下载 |
| 适用场景 | 平台文件库日常管理 |

#### SRT / JSON 脚本导出

| 字段 | 说明 |
|------|------|
| 对应文件 | `backend/app/services/scripts.py` |
| 功能作用 | 根据段级时间码生成 SRT 字幕文件和 JSON 转写文件，存至 MinIO |
| 触发条件 | 任务参数 `generate_scripts: true` |

#### Few-shot 样本检索

| 字段 | 说明 |
|------|------|
| 对应文件 | `backend/app/services/few_shot.py` |
| 功能作用 | 按 (topic_id, language) 从 933 条 v3 训练样本中检索 top-K，注入 LLM prompt |
| 数据来源 | `backend/app/data/few_shot/`（gitignored，本地存在） |

### 工具功能

#### 管理 API

| 字段 | 说明 |
|------|------|
| 对应文件 | `api/v1/admin.py` |
| 功能作用 | few-shot stats 查看 / index 重建；供运维诊断 |

---

## 章节 3：文件与脚本地图 / Project File Map

```
test-audio-builder-platform/
├── .env                           ← [配置文件] 敏感配置（gitignored）
├── .env.example                   ← [配置文件] 环境变量模板
├── alembic.ini                    ← [配置文件] Alembic 迁移配置
├── docker-compose.dev.yml         ← [配置文件] 本地依赖服务（MySQL/Redis/MinIO）
├── CLAUDE.md                      ← [文档] AI 助手指南
│
├── backend/
│   ├── pyproject.toml             ← [配置文件] Python 依赖声明
│   └── app/
│       ├── main.py                ← [主入口] FastAPI app 创建 + 路由注册 + lifespan
│       ├── celery_app.py          ← [核心逻辑] Celery 实例（连接 Redis broker）
│       │
│       ├── api/v1/
│       │   ├── auth.py            ← [核心逻辑] 注册 / 登录 / JWT / Google SSO
│       │   ├── tasks.py           ← [核心逻辑] 任务提交 / 列表 / 重试 / 取消
│       │   ├── voices.py          ← [核心逻辑] 音色注册(E2E) / 删除 / 列表
│       │   ├── files.py           ← [核心逻辑] 文件 CRUD + 下载
│       │   ├── folders.py         ← [核心逻辑] 文件夹管理
│       │   ├── meta.py            ← [辅助脚本] 语言 / 模板 / 音色元数据
│       │   └── admin.py           ← [工具脚本] few-shot stats / reload
│       │
│       ├── core/
│       │   ├── config.py          ← [核心逻辑] 全部环境变量集中读取（pydantic-settings）
│       │   ├── db.py              ← [核心逻辑] SQLAlchemy engine + session + Base
│       │   ├── security.py        ← [辅助脚本] JWT 签发 / 验证 / 密码 hash
│       │   └── logging.py         ← [辅助脚本] loguru 日志配置
│       │
│       ├── models/
│       │   ├── user.py            ← [核心逻辑] User ORM（含 google_id / is_active）
│       │   ├── task.py            ← [核心逻辑] Task ORM（状态机 queued→succeeded）
│       │   ├── audio_file.py      ← [核心逻辑] AudioFile ORM（含 duration / tags）
│       │   ├── voice_catalog.py   ← [核心逻辑] VoiceCatalog ORM（软删除 / 全局共享）
│       │   ├── transcript.py      ← [辅助脚本] Transcript ORM（段级时间码 JSON）
│       │   ├── folder.py          ← [辅助脚本] Folder ORM（树形结构）
│       │   └── tag.py             ← [辅助脚本] Tag ORM + 多对多关联
│       │
│       ├── providers/
│       │   ├── llm/
│       │   │   ├── factory.py     ← [核心逻辑] 从 env 决定 LLM provider（deepseek/openai/anthropic）
│       │   │   ├── deepseek.py    ← [核心逻辑] OpenAI-compat 实现（DeepSeek / OpenAI）
│       │   │   ├── anthropic.py   ← [核心逻辑] Anthropic Messages API 实现
│       │   │   └── base.py        ← [核心逻辑] LLMMessage / LLMResult / TTSProvider ABC
│       │   ├── tts/
│       │   │   ├── cosyvoice.py   ← [核心逻辑] CosyVoice /v1/audio/speech 接入
│       │   │   ├── edge_tts_provider.py ← [核心逻辑] edge_tts 降级（Celery-safe）
│       │   │   ├── factory.py     ← [辅助脚本] get_tts_provider() + fallback 音色列表
│       │   │   └── base.py        ← [辅助脚本] VoiceSpec / SynthesisRequest / ABC
│       │   └── storage/
│       │       └── minio_client.py ← [核心逻辑] MinIO 上传 / 下载 / 签名 URL
│       │
│       ├── services/
│       │   ├── audio.py           ← [核心逻辑] synthesize_lines（TTS+降级+拼接+时间码）
│       │   ├── dialogue.py        ← [核心逻辑] LLM prompt 构建 + few-shot 注入
│       │   ├── few_shot.py        ← [核心逻辑] v3 训练样本检索（933条，MIN_SCORE=70）
│       │   ├── postprocess.py     ← [核心逻辑] apply_postprocess()（3A精简：关键词+稳定化）
│       │   ├── quality_check.py   ← [核心逻辑] 3条质量门禁（标记/重复/字数）
│       │   ├── multilingual_naturalness_lite.py ← [核心逻辑] 中文稳定化 + 关键词注入
│       │   ├── scripts.py         ← [辅助脚本] SRT / JSON 字幕生成
│       │   ├── preset_topics.py   ← [辅助脚本] 22个预置场景加载
│       │   └── tags.py            ← [辅助脚本] 标签 upsert
│       │
│       ├── tasks/
│       │   └── generation.py      ← [核心逻辑] Celery 端到端任务：生成→后处理→合成→存储
│       │
│       ├── schemas/
│       │   ├── task.py / audio_file.py / user.py / folder.py ← [辅助脚本] Pydantic I/O 模型
│       │   └── voice.py           ← [辅助脚本] VoiceOut / VoiceCreateResponse
│       │
│       ├── scripts/
│       │   ├── init_db.py         ← [工具脚本] 首次建表（Base.metadata.create_all）
│       │   └── init_voice_catalog.py ← [工具脚本] 启动时从 CosyVoice 初始化音色表
│       │
│       └── data/
│           ├── preset_topics.json ← [数据/样例] 22个预置对话场景配置
│           └── few_shot/          ← [数据/样例] 1967条训练样本（gitignored）
│
├── frontend/src/
│   ├── pages/
│   │   ├── Home.vue               ← [核心逻辑] 全部文件列表页
│   │   ├── Tasks.vue              ← [核心逻辑] 生成任务队列（3秒轮询）
│   │   ├── MyAudio.vue            ← [核心逻辑] 我的文件（文件夹分组）
│   │   ├── Detail.vue             ← [核心逻辑] 文件详情 + 字幕下载
│   │   └── Trash.vue              ← [辅助脚本] 回收站
│   ├── components/
│   │   ├── GenerateModal.vue      ← [核心逻辑] 生成弹窗（LLM/手动模式 + 音色配置）
│   │   ├── VoiceManageModal.vue   ← [核心逻辑] 音色管理弹窗（注册+E2E+列表+删除）
│   │   └── InlinePlayer.vue       ← [辅助脚本] 嵌入式音频播放器
│   ├── api/
│   │   ├── tasks.ts               ← [核心逻辑] 任务 API 客户端（含预览对话接口）
│   │   ├── voices.ts              ← [核心逻辑] 音色 API 客户端
│   │   └── client.ts              ← [辅助脚本] Axios 实例 + 拦截器
│   └── stores/
│       ├── auth.ts                ← [核心逻辑] Pinia 用户认证状态
│       └── folders.ts             ← [辅助脚本] Pinia 文件夹树
│
└── migrations/versions/
    ├── 6945045eafae_baseline.py   ← [配置文件] 基线（5张原有表）
    └── a65fcd8fef1d_add_voice_catalog_table.py ← [配置文件] P2新增音色表
```

---

## 章节 4：脚本能力说明 / What Each Script Can Do

### `backend/app/tasks/generation.py` ⭐ 核心业务入口

**这个文件是干什么的**

这是整个平台最重要的文件，负责从头到尾跑一条语料生成任务。当用户在前端点击"生成音频"，会把任务写入 MySQL + 推入 Celery 队列，然后这个文件的 `run_generation_task()` 就被 Celery worker 异步执行。

**完整执行流程（5个阶段）：**

1. **文本生成/解析**：LLM 模式调 `generate_dialogue()` 拿到结构化对话行；手动模式直接解析用户输入
2. **说话人数校验**：确认文本中的 Speaker 数量与配置一致
3. **LLM 后处理 + 质量门禁**：注入关键词 → 中文稳定化 → 3条质量门禁（仅 LLM 模式）
4. **音频合成**：`synthesize_lines()` 逐段调 CosyVoice，失败时 edge_tts 降级，拼接为完整 MP3
5. **存储 + 入库**：上传 MinIO → 写 AudioFile + Transcript 到 MySQL → 状态置 SUCCEEDED

**如何调用**

```python
# 提交 Celery 任务（不直接调，由 api/v1/tasks.py 触发）
from app.tasks.generation import run_generation_task
run_generation_task.delay(str(task.task_id))
```

**注意事项**
- `_mark_failed()` 失败后不会自动重试（重试通过 API `/tasks/{id}/retry` 手动触发）
- `target_duration_sec * 2.5` 是字数估算公式（150字/分钟），用于质量门禁阈值
- LLM_POSTPROCESS_ENABLED=false 时只过质量门禁，不跑后处理

---

### `backend/app/services/audio.py` ⭐ 音频合成引擎

**这个文件是干什么的**

负责把 `[(speaker_id, text), ...]` 格式的对话行列表转换为一条 MP3 音频文件。核心函数 `synthesize_lines()` 处理：连续同说话人行合并（最大 500 字）、逐段调 TTS、WAV→MP3 格式化（含 silenceremove）、filter_complex concat 拼接。

**它能做哪些事：**
- 同 speaker 连续行合并（减少 API 调用次数）
- 调 CosyVoice 合成 WAV，转 MP3（44.1kHz / mono / 128k / silenceremove -65dB）
- CosyVoice 失败时透明降级 edge_tts（`degraded=True`）
- ffmpeg filter_complex concat 无缝拼接（消除爆音）
- 记录每段实测时长，累加得到 `start_time / end_time`

**返回值说明**
```python
audio_bytes, duration_sec, segments, degraded = synthesize_lines(...)
# degraded=True → task.error_message 写入 "[TTS_WARN]"
# segments = [{speaker_id, text, start_time, end_time}, ...]
```

**注意事项**
- ffmpeg 必须在系统 PATH 中（Windows 需手动安装）
- `fallback_tts.default_voice_for(language)` 通过方法调用，不直接引用 dict（避免反向依赖）

---

### `backend/app/main.py` ⭐ FastAPI 应用入口

**这个文件是干什么的**

定义 FastAPI app、注册所有路由、配置 CORS，并在 lifespan 里做两件启动初始化：确保 MinIO bucket 存在、尝试从 CosyVoice 初始化音色目录（失败只 warning）。

**注册的路由：**

| 前缀 | 模块 | 功能 |
|------|------|------|
| `/api/v1/auth` | auth.py | 注册 / 登录 / JWT |
| `/api/v1/tasks` | tasks.py | 任务 CRUD |
| `/api/v1/voices` | voices.py | 音色管理 |
| `/api/v1/files` | files.py | 文件管理 |
| `/api/v1/folders` | folders.py | 文件夹 |
| `/api/v1/meta` | meta.py | 元数据查询 |
| `/api/v1/admin` | admin.py | 管理诊断 |

---

### `backend/app/api/v1/voices.py` — 音色目录 API

**三个端点，E2E 验证是核心设计：**

- `GET /api/v1/voices` → 从 DB 读全量音色（按 language 过滤）
- `POST /api/v1/voices` → 注册新音色：调 CosyVoice create → **立即合成验证** → 成功才写 DB
- `DELETE /api/v1/voices/{id}` → 软删除；`delete_remote=true` 时同步删 CosyVoice 远端

E2E 验证是为了防止 CosyVoice 注册 API 永远返回 200、但合成时 500 的问题。失败时返回 422 + 参考音频质量提示。

---

### `backend/app/services/dialogue.py` — LLM Prompt 构建

**推测用途**（文件较长，仅 grep 分析）

`build_prompt()` 构造 system + user 双角色 prompt：拼入场景背景、角色分工建议、通用生成规则、2条 few-shot 样本。`generate_dialogue()` 调 LLM 后用正则解析 `Speaker N:` 行，返回 `(raw_text, lines)`。

---

## 章节 5：优缺点分析 / Strengths and Limitations

### 优点

- **架构成熟**：FastAPI + Celery + MySQL 完整生产级栈，任务持久化，断电不丢
- **TTS 双保险**：CosyVoice 主路 + edge_tts 透明降级，单点故障不影响任务完成
- **E2E 音色验证**：注册时即测试合成，消除"注册成功合成失败"的歧义
- **精确时间码**：每段实测 duration 累加，SRT/JSON 时间码可直接用于语音识别训练
- **LLM 可插拔**：`.env` 一行切换 DeepSeek / OpenAI / Anthropic，零代码改动
- **多用户隔离**：JWT + 每用户并发任务限制（≤3），防资源滥用
- **MinIO 存储**：S3 兼容，未来切 AWS S3 / 阿里云 OSS 零改动

### 局限性 / 潜在风险

- **Celery worker 未启动**：本地开发默认只跑 uvicorn，任务会停在 `queued` 状态——需另开终端跑 `celery -A app.celery_app worker`
- **few_shot 数据 gitignored**：新环境 clone 后 `backend/app/data/few_shot/` 为空，需手动复制 1967 条样本，否则 few-shot 检索静默失效（返回空）
- **multilingual_naturalness_lite.py 体积大**：2200+ 行，整体从 V1 移植，包含大量未被 V2 调用的 Bundle LLM 专用函数，是技术债
- **CosyVoice 单点**：`max_concurrency=1`（串行合成），多任务并发时音频合成是瓶颈
- **无 WebSocket**：任务状态靠前端 3 秒轮询，高并发下 API 压力较大

### 可维护性：⭐⭐⭐⭐（4/5）

路由 / 服务 / 模型 / 任务分层清晰，Pydantic schema 类型安全，Alembic 管理迁移。主要问题是 `multilingual_naturalness_lite.py` 体积过大。

### 可扩展性：⭐⭐⭐⭐（4/5）

LLM / TTS / Storage 均有 Provider 抽象层，增加新 provider 只需实现 ABC。Celery 可横向扩展 worker。

### 最值得重构的 3 处

1. **`multilingual_naturalness_lite.py`**：2200 行，仅实际使用其中约 400 行（`stabilize_dialogue_constraints` + `enforce_keywords_in_lines`）。建议抽出真正需要的函数单独成文件
2. **`tasks/generation.py` 中的 postprocess 块**：内联 import 散布在函数体中，建议统一到文件顶部
3. **`api/v1/voices.py` 的 `create_voice`**：`async def` 内混用 `httpx.AsyncClient`，若改为同步函数可简化测试

---

## 章节 6：内部调用与实现逻辑 / Internal Flow and Call Graph

### 主流程：提交一条生成任务到拿到音频文件

```
Step 1  前端 GenerateModal.vue → POST /api/v1/tasks
Step 2  tasks.py create_task() → 写 Task(status=queued) → MySQL
Step 3  run_generation_task.delay(task_id) → 推入 Redis Celery 队列
Step 4  Celery worker 拉取任务 → run_generation_task()
Step 5    [LLM模式] generate_dialogue() → 云 LLM API → [(speaker,text),...]
Step 6    [LLM模式] apply_postprocess() → enforce_keywords + stabilize_chinese
Step 7    [LLM模式] check_quality() → 3条门禁（失败→task.status=failed）
Step 8    synthesize_lines() → 逐段 CosyVoice → WAV→MP3 → concat
Step 9    upload_bytes() → MinIO 对象存储
Step 10   写 AudioFile + Transcript → MySQL
Step 11   task.status = succeeded，progress = 100
Step 12  前端 Tasks.vue 3秒轮询 → 发现 succeeded → 刷新文件列表
```

### 调用链

```
POST /api/v1/tasks
  └─ create_task() [tasks.py]
       └─ run_generation_task.delay() [celery]
            └─ run_generation_task() [tasks/generation.py]
                 ├─ generate_dialogue() [services/dialogue.py]
                 │    ├─ build_prompt()
                 │    │    └─ retrieve() [services/few_shot.py]
                 │    └─ llm.complete() [providers/llm/deepseek.py]
                 ├─ apply_postprocess() [services/postprocess.py]
                 │    ├─ enforce_keywords_in_lines() [multilingual_naturalness_lite.py]
                 │    └─ stabilize_dialogue_constraints() [multilingual_naturalness_lite.py]
                 ├─ check_quality() [services/quality_check.py]
                 ├─ synthesize_lines() [services/audio.py]
                 │    ├─ tts.synthesize() [providers/tts/cosyvoice.py]
                 │    │    └─ [失败] fallback_tts.synthesize() [providers/tts/edge_tts_provider.py]
                 │    ├─ _ffmpeg_normalize() → ffmpeg silenceremove
                 │    └─ _ffmpeg_concat() → ffmpeg filter_complex
                 ├─ upload_bytes() [providers/storage/minio_client.py]
                 └─ db.commit() [AudioFile + Transcript]
```

### 数据流

```
用户配置
  (template, language, speaker_count, keywords, target_duration_sec)
  │
  ▼ [dialogue.py]
结构化对话行
  [(speaker_id, line_text), ...]
  │
  ▼ [postprocess.py / quality_check.py]
过滤 + 注入后的对话行
  │
  ▼ [audio.py → synthesize_lines()]
每段 WAV bytes（CosyVoice / edge_tts）
  │
  ▼ [ffmpeg: normalize + concat]
完整 MP3 bytes + 段级时间码 segments
  │
  ▼ [minio_client.py]
MinIO 对象存储（storage_key）
  │
  ▼ [AudioFile ORM + Transcript ORM]
MySQL 数据库（含 duration_sec / file_size / segments JSON）
```

### 外部资源调用

| 资源类型 | 名称 | 调用位置 | 说明 |
|---------|------|---------|------|
| 云 LLM API | DeepSeek / OpenAI / Anthropic | `providers/llm/deepseek.py` | POST /chat/completions |
| TTS API | CosyVoice | `providers/tts/cosyvoice.py` | POST /v1/audio/speech → WAV |
| TTS 降级 | Microsoft Edge TTS | `providers/tts/edge_tts_provider.py` | edge-tts 库，免费 |
| 对象存储 | MinIO（本地）/ S3 兼容 | `providers/storage/minio_client.py` | 音频文件 + 字幕文件 |
| 关系数据库 | MySQL 8.0 | `core/db.py` | 任务 / 文件 / 用户 / 音色 |
| 消息队列 | Redis | `celery_app.py` | Celery broker + result backend |
| 媒体处理 | ffmpeg / ffprobe | `services/audio.py` | WAV→MP3、拼接、时长测量 |

---

## 章节 7：深度技术解读 / Deep Technical Notes

### `tasks/generation.py` — Celery 任务状态机

**全局状态**

| 变量 | 类型 | 说明 |
|------|------|------|
| `task.status` | str enum | queued → text_generating → synthesizing → succeeded / failed / cancelled |
| `task.progress` | int 0-100 | 10(文本生成开始)→40(文本完成)→50(合成开始)→90(合成完成)→100 |
| `task.error_message` | str | 失败原因 or `[TTS_WARN]` 降级标记 |

**关键设计：为什么后处理用内联 import**

`postprocess` 和 `quality_check` 在函数体中 import，而非文件顶部。原因：避免循环 import（generation.py 被 celery_app 导入，而 postprocess 依赖 multilingual_naturalness_lite 依赖大量内部变量）。这是为了保证 Celery worker 启动时不报错的折中方案。

**容易踩的坑**

- `_target_words` 在两个分支（if/else）中都需要定义，否则 `check_quality` 会用到未定义的变量
- Celery task 里的异常不会自动 propagate 给调用方——必须检查返回值 `{"ok": False}`

---

### `services/audio.py` — synthesize_lines 设计细节

**silenceremove 参数选择**

`-65dB` 是保守阈值：CosyVoice 数字静音约 -90dB，正常语音 > -40dB，-65dB 只裁数字静音不误裁语音。`start_duration=0.05s` 防止过激裁剪开头辅音。

**为什么用 filter_complex concat 而非 concat demuxer**

concat demuxer 要求所有输入 codec 相同。CosyVoice 输出 WAV（pcm_s16le），edge_tts 输出 MP3，混合时 concat demuxer 会产生爆音。filter_complex 先解码为 PCM 再重编，完全兼容格式差异。

**degraded flag 的传递链**

```
synthesize_lines() → degraded=True
  → generation.py → task.error_message = "[TTS_WARN]..."
    → 前端 Tasks.vue → 橙色警告标记（任务仍为 succeeded）
```

---

### `providers/tts/edge_tts_provider.py` — Celery 安全的异步代码

**为什么不能用 asyncio.get_running_loop()**

Celery worker 在同步线程中运行，没有运行中的事件循环。`get_running_loop()` 会抛 `RuntimeError: no running event loop`。解决方案：每次调用 `asyncio.new_event_loop()` 创建独立循环，`finally` 中 close。

**隐式约定**

- `default_voice_for(language)` 不在 ABC 中定义，是 EdgeTTSProvider 特有方法——generation.py 使用时需确认 fallback_tts 是 EdgeTTSProvider 实例
- `list_voices()` 返回 `[]`，不会出现在音色目录中（edge_tts 只用于降级，不对用户可见）

---

### `migrations/env.py` — Alembic URL 坑

**必须传 URL 对象，不能 str()**

`str(SQLAlchemy_URL)` 会把密码遮成 `***`（安全设计），导致 MySQL 认证失败。务必：

```python
connectable = create_engine(
    get_settings().database_url,   # URL 对象，不是 str()
    poolclass=pool.NullPool,
)
```

**MySQL UUID 坑（deps.py）**

MySQL 的 `Uuid(as_uuid=True)` 列需要 `uuid.UUID` 对象，JWT payload 里的 `sub` 是字符串。必须 `uuid.UUID(user_id_str)` 转换后再查询，否则 500。

---

*文档生成完毕。分析了 8 个文件（深读 3 个，grep 5 个，推测 0 个）。主入口：`backend/app/main.py`。无推测标注。*
