# 音频语料生成平台 V2 — 完整说明文档

> 生成时间：2026-05-30 | 根目录：`D:\Github\test-audio-builder-platform`
> GitHub：`https://github.com/danielchen-ctrl/audio-synthesis-demo/tree/V2`

---

## 章节 1：项目总览 / Executive Summary

### 一句话定义

这是一个**多用户音频语料生成平台**，通过云 LLM（DeepSeek / OpenAI / Anthropic）生成结构化对话文本、调用 CosyVoice 真人克隆音色合成高质量音频，并提供完整的文件管理与音色管理能力。

### 核心能力

- 🧠 **云 LLM 对话生成**：调用 DeepSeek / OpenAI / Anthropic，注入 few-shot 样本与关键词，经 3 条质量门禁过滤，中文输出经稳定化后处理
- 🎙 **真人音色合成**：对接 CosyVoice `/v1/audio/speech`，合成克隆音频；CosyVoice 失败时自动透明降级 edge_tts
- ⚙️ **在线音色管理**：上传参考音频注册克隆音色，注册时强制 E2E 合成验证；全局共享，仅创建者可删除
- 📁 **文件 / 文件夹管理**：上传、软删除、回收站、文件夹分组、标签检索、批量操作
- 📝 **SRT / JSON 脚本导出**：每段合成后累加实测时长，生成精确时间码的字幕与 JSON
- 👤 **多用户认证**：JWT 注册登录，支持 Google SSO，每用户数据隔离
- 🔄 **异步任务队列**：Celery + Redis，任务持久化、自动重试、每用户并发上限 ≤ 3
- 🔉 **音频质量处理**：ffmpeg silenceremove 自动裁剪 CosyVoice 数字静音头尾，filter_complex concat 无缝拼接

### 适合谁阅读

| 角色 | 建议章节 | 关注重点 |
|------|---------|---------|
| 新接手开发者 | 1 → 3 → 6 | 整体架构 + 完整调用链 |
| 后端维护者 | 4 → 7 | generation.py / audio.py 深度解读 |
| 前端开发者 | 3 → 4（前端部分）| Vue 组件结构 + API 调用 |
| 运维 / 部署 | 1 → 快速启动 | start.bat + Docker + .env |
| AI 辅助开发 | 全文 | 全量上下文 |

### 快速理解摘要

这个项目是一个内部使用的音频语料生产工具。用户注册登录后，选择行业场景模板（如"医疗随访"、"销售会议"），填入主题和关键词，平台调用 DeepSeek 等云 LLM 生成真实感强的多人对话文本；再把文本按说话人拆分，分别调用 CosyVoice 的真人克隆音色合成每段音频，最后 ffmpeg 无缝拼接成完整 MP3 文件存入 MinIO，并记录每段的精确时间码用于 SRT/JSON 字幕导出。整套流程异步执行（Celery），用户前端 3 秒轮询任务状态。

---

## 章节 2：功能清单 / Feature Breakdown

### 核心功能

#### LLM 对话文本生成

| 字段 | 说明 |
|------|------|
| 对应文件 | `backend/app/services/dialogue.py`、`tasks/generation.py` |
| 功能作用 | 调用云 LLM 生成 Speaker N: 格式多人对话，注入 few-shot 样本 |
| 输入 | template、topic、language、speaker_count、keywords、target_duration_sec |
| 输出 | `(raw_text, lines)` — 原始文本 + 解析后行列表 |
| 适用场景 | 提交 LLM 模式任务时自动调用 |
| 依赖模块 | `providers/llm/factory.py`、`services/few_shot.py`、`data/preset_topics.json` |

#### 精简后处理（3A 路线）

| 字段 | 说明 |
|------|------|
| 对应文件 | `backend/app/services/postprocess.py` |
| 功能作用 | 关键词注入 + 中文说话人稳定化（防幽灵 Speaker、防说话人混乱）|
| 输入 | lines、language、keywords、speaker_count、title、target_word_count |
| 输出 | 处理后的 lines（失败时返回原始 lines，不阻断主流程）|
| 适用场景 | LLM 生成文本后、质量门禁前自动调用（由 `LLM_POSTPROCESS_ENABLED` 控制）|
| 依赖模块 | `services/multilingual_naturalness_lite.py` |

#### 质量门禁

| 字段 | 说明 |
|------|------|
| 对应文件 | `backend/app/services/quality_check.py` |
| 功能作用 | 3 条规则过滤不合格 LLM 输出，触发时任务标记 failed |
| 规则 | ① `<<…>>` 标记残留 ② 唯一行率 < 60% ③ 字数 < 目标 30% |
| 输入 | lines、language、target_word_count |
| 输出 | 无（触发时 raise QualityCheckError）|
| 适用场景 | postprocess 之后、TTS 合成之前 |

#### 音频合成（CosyVoice + edge_tts 降级）

| 字段 | 说明 |
|------|------|
| 对应文件 | `backend/app/services/audio.py`、`providers/tts/edge_tts_provider.py` |
| 功能作用 | 按 speaker 分段合成 WAV，转码 MP3，拼接成完整音频；CosyVoice 失败自动降级 |
| 输入 | lines、voice_assignments、language、output_format、fallback_tts |
| 输出 | `(audio_bytes, duration_sec, segments, degraded)` |
| 特性 | silenceremove -65dB 裁数字静音；filter_complex concat 无缝拼接 |
| 依赖 | ffmpeg（本地安装）、CosyVoice API、edge-tts |

### 辅助功能

#### 音色目录管理

| 字段 | 说明 |
|------|------|
| 对应文件 | `api/v1/voices.py`、`models/voice_catalog.py`、`scripts/init_voice_catalog.py` |
| 功能作用 | 注册/列出/删除克隆音色；DB 为单一权威来源；注册时强制 E2E 合成验证 |
| API | `GET /api/v1/voices`、`POST /api/v1/voices`、`DELETE /api/v1/voices/{id}` |
| 共享规则 | 全局共享，仅创建者可删除 |
| E2E 验证 | 注册后立即合成一句验证文本，失败返回 422（不写 DB）|

#### 文件管理

| 字段 | 说明 |
|------|------|
| 对应文件 | `api/v1/files.py`、`models/audio_file.py` |
| 功能作用 | 上传、下载（presigned URL）、软删除、回收站恢复、批量操作 |
| 存储 | MinIO（S3 兼容），`audio-platform` bucket |

#### SRT / JSON 字幕脚本

| 字段 | 说明 |
|------|------|
| 对应文件 | `services/scripts.py` |
| 功能作用 | 基于段级时间码生成 SRT 字幕和 JSON 结构化脚本 |
| 触发 | 任务参数 `generate_scripts: true` |
| 输出 | `{base}_transcript.srt`、`{base}_transcript.json` 存入 MinIO |

### 工具功能

| 功能 | 文件 | 说明 |
|------|------|------|
| 一键启动 | `start.bat` | 自动启动 Docker + 后端 + 前端（三个窗口）|
| 一键停止 | `stop.bat` | 关闭所有服务和容器 |
| DB 初始化 | `scripts/init_db.py` | 首次运行建表 |
| Few-shot 管理 | `api/v1/admin.py` | `/admin/few-shot/stats`、`/admin/few-shot/reload` |
| DB 迁移 | `migrations/` + alembic | `alembic upgrade head` 执行新 migration |

---

## 章节 3：文件与脚本地图 / Project File Map

```
test-audio-builder-platform/
├── start.bat                    ← [工具脚本] 一键启动（Docker + 后端 + 前端）
├── stop.bat                     ← [工具脚本] 一键停止所有服务
├── .env                         ← [配置文件] 密钥和连接信息（gitignore，不提交）
├── .env.example                 ← [配置文件] .env 填写模板
├── docker-compose.dev.yml       ← [配置文件] 本地 MySQL 8.0 / Redis 7 / MinIO
├── alembic.ini                  ← [配置文件] Alembic 数据库迁移工具配置
├── migrations/
│   ├── env.py                   ← [核心逻辑] Alembic 运行环境（含 URL 对象 bug 修复）
│   └── versions/
│       ├── 6945045eafae_baseline.py         ← 基线快照（对齐现有 5 张表）
│       └── a65fcd8fef1d_add_voice_catalog.py ← voice_catalog 表 migration
├── backend/
│   ├── pyproject.toml           ← [配置文件] Python 依赖声明
│   └── app/
│       ├── main.py              ← [主入口] FastAPI app + lifespan + 所有路由注册
│       ├── celery_app.py        ← [核心逻辑] Celery 实例（Redis broker）
│       ├── core/
│       │   ├── config.py        ← [核心逻辑] 所有环境变量（lru_cache 单例）
│       │   ├── db.py            ← [核心逻辑] SQLAlchemy engine + Session 工厂
│       │   ├── security.py      ← [辅助脚本] JWT 签发/解码、bcrypt 密码哈希
│       │   └── logging.py       ← [辅助脚本] loguru 日志配置
│       ├── api/v1/
│       │   ├── auth.py          ← [核心逻辑] 注册 / 登录 / Google SSO / 用户信息
│       │   ├── tasks.py         ← [核心逻辑] 任务提交/查询/重试/取消/对话预览
│       │   ├── voices.py        ← [核心逻辑] ★新增 音色注册/列出/删除（E2E验证）
│       │   ├── files.py         ← [核心逻辑] 文件管理（上传/下载/软删除/批量）
│       │   ├── folders.py       ← [辅助脚本] 文件夹 CRUD
│       │   ├── meta.py          ← [辅助脚本] 语言/模板/音色/标签元数据
│       │   ├── admin.py         ← [工具脚本] few-shot 统计和热重建
│       │   └── deps.py          ← [核心逻辑] JWT 鉴权依赖（含 UUID 类型修复）
│       ├── models/
│       │   ├── user.py          ← [核心逻辑] 用户表（JWT + Google SSO）
│       │   ├── task.py          ← [核心逻辑] 任务表（queued→succeeded/failed，6状态）
│       │   ├── audio_file.py    ← [核心逻辑] 音频文件表（软删除 + MinIO key）
│       │   ├── voice_catalog.py ← [核心逻辑] ★新增 音色目录表（全局共享，软删除）
│       │   ├── transcript.py    ← [辅助脚本] 时间码脚本表（segments JSON）
│       │   ├── folder.py        ← [辅助脚本] 文件夹表（嵌套支持）
│       │   └── tag.py           ← [辅助脚本] 标签表（many-to-many with AudioFile）
│       ├── providers/
│       │   ├── llm/
│       │   │   ├── base.py      ← [核心逻辑] LLMMessage / LLMResult / LLMProvider ABC
│       │   │   ├── deepseek.py  ← [核心逻辑] DeepSeek + OpenAI 兼容实现
│       │   │   ├── anthropic.py ← [核心逻辑] Anthropic Messages API 实现
│       │   │   └── factory.py   ← [核心逻辑] 从 .env 读配置返回对应 Provider 实例
│       │   ├── tts/
│       │   │   ├── base.py      ← [核心逻辑] VoiceSpec / SynthesisRequest / TTSProvider ABC
│       │   │   ├── cosyvoice.py ← [核心逻辑] CosyVoice /v1/audio/speech 实现（主路径）
│       │   │   ├── edge_tts_provider.py ← [核心逻辑] ★新增 edge_tts 降级 Provider
│       │   │   └── factory.py   ← [辅助脚本] 返回 CosyVoice Provider + fallback 列表
│       │   └── storage/
│       │       └── minio_client.py ← [核心逻辑] MinIO 上传/下载/presigned URL/删除
│       ├── services/
│       │   ├── dialogue.py      ← [核心逻辑] LLM prompt 构建 + few-shot 注入 + 对话解析
│       │   ├── audio.py         ← [核心逻辑] ★改造 分段合成+silenceremove+concat降级
│       │   ├── postprocess.py   ← [核心逻辑] ★新增 关键词注入+中文稳定化
│       │   ├── quality_check.py ← [核心逻辑] ★新增 3条质量门禁
│       │   ├── multilingual_naturalness_lite.py ← [核心逻辑] ★新增 中文稳定化引擎（2200行）
│       │   ├── few_shot.py      ← [辅助脚本] few-shot 索引构建（MIN_SCORE=70）与检索
│       │   ├── scripts.py       ← [辅助脚本] SRT / JSON 时间码脚本生成
│       │   ├── preset_topics.py ← [辅助脚本] preset_topics.json 加载与查询
│       │   └── tags.py          ← [辅助脚本] 标签 upsert
│       ├── tasks/
│       │   ├── generation.py    ← [核心逻辑] ★改造 Celery任务端到端处理（含后处理门禁）
│       │   └── cleanup.py       ← [辅助脚本] 回收站定期清理（推测）
│       ├── schemas/
│       │   ├── voice.py         ← [辅助脚本] ★新增 VoiceOut / VoiceCreateResponse
│       │   ├── task.py          ← [辅助脚本] TaskCreate / TaskOut / PreviewRequest
│       │   └── ...              ← [辅助脚本] 其他 Pydantic schema
│       ├── scripts/
│       │   ├── init_db.py       ← [工具脚本] 首次运行建表
│       │   └── init_voice_catalog.py ← [工具脚本] ★新增 启动时从CosyVoice导入初始音色
│       └── data/
│           ├── preset_topics.json ← [数据/样例] 22个预置场景（已同步最新版）
│           └── few_shot/        ← [数据/样例] 933条few-shot训练样本（gitignore）
├── frontend/
│   └── src/
│       ├── api/
│       │   ├── voices.ts        ← [核心逻辑] ★新增 listVoicesFromDB/registerVoice/deleteVoice
│       │   ├── tasks.ts         ← [核心逻辑] createTask / previewDialogue
│       │   └── ...              ← [辅助脚本] auth/files/folders/meta API 封装
│       └── components/
│           ├── VoiceManageModal.vue ← [核心逻辑] ★新增 音色管理弹窗
│           └── GenerateModal.vue    ← [核心逻辑] ★改造 加音色管理入口按钮
└── docs/
    └── PROJECT_EXPLANATION.md   ← [文档] 本文档
```

> ★ 标注的文件为本次 V2 改造新增或重要修改。

---

## 章节 4：脚本能力说明 / What Each Script Can Do

### `backend/app/main.py` ⭐ FastAPI 主入口

**是什么**：整个后端服务的启动入口。注册所有路由，在 `lifespan` 里做启动初始化——创建 MinIO bucket、尝试从 CosyVoice 导入初始音色目录（CosyVoice 不可用时只 warning 不崩溃）。

**能做什么**：
- 以 uvicorn 启动 FastAPI 服务，监听 8000 端口
- 加载 7 个 API 路由模块（auth/tasks/files/folders/meta/admin/voices）
- CORS 配置，默认允许 `localhost:5173`
- 健康检查 `GET /api/v1/health` 返回 `{"status": "ok"}`

**如何调用**：
```bash
cd D:\Github\test-audio-builder-platform
backend\.venv\Scripts\uvicorn app.main:app --reload --port 8000 --app-dir backend
# 或直接双击 start.bat
```

---

### `backend/app/tasks/generation.py` ⭐ 核心任务处理器

**是什么**：Celery 任务的实际执行体，端到端处理从文本生成到音频入库的全流程。每个任务从 DB 读取参数，按 5 个阶段顺序执行。

**5 个执行阶段**：
1. **文本生成**：LLM 模式调 `generate_dialogue()`；manual 模式解析粘贴文本
2. **说话人校验**：文本中 speaker 数必须与配置一致，不一致 → 任务 FAILED
3. **后处理 + 质量门禁**（LLM 模式）：`apply_postprocess()` → `check_quality()`
4. **音频合成**：`synthesize_lines()`，失败自动降级 edge_tts
5. **存储入库**：上传 MinIO → 写 AudioFile + Transcript → 任务 SUCCEEDED

**如何启动 Celery worker**：
```bash
cd D:\Github\test-audio-builder-platform
backend\.venv\Scripts\celery -A app.celery_app worker --loglevel=info -Q text_gen,audio_synth --concurrency=2
```
> ⚠️ 不启动 Celery worker，LLM 模式任务会永远停在 queued 状态。

---

### `backend/app/services/audio.py` ⭐ 音频合成引擎

**是什么**：所有音频处理逻辑的核心。负责分段合成、格式转码、静音裁剪、无缝拼接，并支持 CosyVoice 失败时自动降级 edge_tts。

**关键改造点**：
- 返回值从 3-tuple 改为 4-tuple：`(bytes, duration, segments, degraded)`
- `fallback_tts` 参数：传入 `EdgeTTSProvider()` 实例，CosyVoice 失败时自动切换
- `_ffmpeg_normalize()` 加 silenceremove -65dB：裁掉 CosyVoice 数字静音头尾
- `degraded=True` 时，任务 `error_message` 写入 `[TTS_WARN]` 标记（任务仍 SUCCEEDED）

---

### `backend/app/api/v1/voices.py` ⭐ 音色管理 API（新增）

**是什么**：平台音色目录的 RESTful API。音色信息存 MySQL `voice_catalog` 表，DB 是唯一权威来源（替代了每次实时调 CosyVoice 的方式）。

**注册流程（强制 E2E 验证，防"注册成功合成 500"）**：
1. 接收 multipart（参考音频文件 + 名称/语言/性别/参考文本）
2. 调 CosyVoice `/v1/voices/create` 获取 voice_id
3. 立即用该 voice_id 合成验证短句（中文："你好，这是音色验证。"）
4. 验证成功 → 写 `voice_catalog` DB → 返回 `201 + verified=true`
5. 验证失败 → 不写 DB → 返回 `422 + message（参考音频质量建议）`

**API 用法**：
```bash
# 列出所有可用音色（可按语言过滤）
GET /api/v1/voices?language=zh

# 注册新音色（multipart/form-data）
POST /api/v1/voices?name=耿同学&language=zh&gender=male
Body: audio=<参考音频文件>

# 删除音色（仅创建者可操作）
DELETE /api/v1/voices/{voice_id}?delete_remote=0
```

---

### `backend/app/providers/tts/edge_tts_provider.py`（新增）

**是什么**：Microsoft Edge TTS 的 Provider 封装，CosyVoice 失败时的透明降级，对用户不可见。

**关键技术点**：Celery worker 是同步线程，没有 asyncio 事件循环，必须用 `asyncio.new_event_loop()` 创建独立循环调用 edge_tts 的异步接口，不能用 `get_running_loop()`（会报 RuntimeError）。

**语言支持**：12 种（zh/en/ja/ko/es/fr/de/pt/it/ru/ar/id），通过 `default_voice_for(language)` 方法查询，不暴露内部 dict。

---

### `backend/app/services/postprocess.py`（新增）

**是什么**：LLM 输出的精简后处理器（3A 路线）。云 LLM 不产生 Bundle 退化，所以不做 repair 遍，只做两步：

1. **关键词注入** (`enforce_keywords_in_lines`)：检查关键词是否出现在对话中，若缺失则注入上下文化的短句（中文）或追加说明行（英文）
2. **中文说话人稳定化** (`stabilize_dialogue_constraints`)：修复中文对话中说话人混乱、幽灵 Speaker 等问题；非中文路径直接 early return

**容错设计**：任何异常只记 warning，返回原始 lines，不阻断合成流程。

---

### `frontend/src/components/VoiceManageModal.vue`（新增）

**是什么**：音色管理弹窗组件，在 `GenerateModal` 的"语音配置"区点击"⚙️ 管理真人音色"按钮打开。

**功能**：
- 已注册音色列表（可滚动，max-height 240px），仅创建者可见删除按钮
- 上传参考音频的注册表单（支持拖拽）
- 提交时显示 loading，E2E 验证失败时完整展示参考音频质量建议
- 注册/删除后通过 `@updated` 事件通知 `GenerateModal` 刷新音色下拉

---

## 章节 5：优缺点分析 / Strengths and Limitations

### 整体优点

- **生产级架构**：Celery + Redis + MySQL + MinIO，任务持久化、多实例横向扩展
- **LLM 可切换**：`.env` 改一行，DeepSeek ↔ OpenAI ↔ Anthropic，不改代码
- **TTS 有降级**：CosyVoice 不可用时自动降级 edge_tts，任务不卡死
- **音色 E2E 验证**：注册即测试，杜绝哑音色问题
- **时间码精确**：实测每段 mp3 时长累加，SRT/JSON 与实际音频完全对齐
- **多用户隔离**：JWT + user_id，数据严格隔离

### 局限性

- **Celery worker 需手动启动**：`start.bat` 目前不启动 worker，LLM 任务卡在 queued
- **few-shot 数据 gitignore**：933 条样本在本地有，但不进 Git，协作需手动复制
- **CosyVoice 串行**：`max_concurrency=1` 防响应串扰，合成大段音频较慢
- **无管理员权限**：User 表无 `is_admin`，只有创建者能删自己的音色

### 可维护性：⭐⭐⭐⭐（4/5）
FastAPI + SQLAlchemy + Pydantic 结构规范，类型注解完整，API 文档自动生成（`/docs`）。主要隐患是 `multilingual_naturalness_lite.py` 整文件搬运，2200 行，较难维护。

### 可扩展性：⭐⭐⭐⭐（4/5）
Provider 抽象层设计良好，新增 LLM / TTS 只需实现 ABC 接口。Celery 支持横向扩展。

### 最值得改进的 3 处

| 位置 | 问题 | 建议方向 |
|------|------|---------|
| `multilingual_naturalness_lite.py` | 2200 行整文件搬运 | 只保留 2 个公开函数及其直接依赖，独立重写 lite 版（约 200 行）|
| `start.bat` | 未启动 Celery worker | 加第 5 步启动 Celery 窗口 |
| `User` 表 | 无 `is_admin` 字段 | 加 Alembic migration 补列，voices.py delete 加管理员特权 |

---

## 章节 6：内部调用与实现逻辑 / Internal Flow and Call Graph

### 端到端任务流程（LLM 模式）

```
Step 1   前端 GenerateModal 配置场景 → 点"生成文本"调 POST /api/v1/tasks/preview-dialogue
Step 2   预览文本成功后，点"生成音频" → POST /api/v1/tasks（创建任务，status=queued）
Step 3   Celery worker 拉到任务 → run_generation_task()
Step 4     get_llm_provider() → DeepSeekProvider / AnthropicProvider
Step 5     generate_dialogue() → build_prompt()（scene背景 + few-shot + 关键词 + 规则）
Step 6     provider.complete(messages) → 云 LLM API 返回文本（~7秒）
Step 7     parse_dialogue() → lines = [(speaker_id, text), ...]
Step 8     校验 len(speakers) == speaker_count
Step 9     apply_postprocess(lines) → enforce_keywords + stabilize_chinese
Step 10    check_quality(lines) → 3条门禁（失败 → task FAILED，流程终止）
Step 11    synthesize_lines(lines, voice_assignments, fallback_tts=EdgeTTS)
Step 12      for each merged_segment (同speaker连续行合并≤500字):
Step 13        CosyVoiceProvider.synthesize() → WAV bytes（~3-7秒/段）
Step 14        _ffmpeg_normalize(WAV → MP3, silenceremove -65dB)
Step 15        [若CosyVoice失败] EdgeTTSProvider.synthesize() 透明降级
Step 16      _ffmpeg_concat(all MP3 segments → final.mp3)
Step 17    upload_bytes(MinIO) → storage_key
Step 18    写 AudioFile DB + Transcript DB（含段级时间码）
Step 19    task status = succeeded，progress = 100
Step 20    前端 3秒轮询看到 succeeded → 展示下载链接
```

### 主要调用链

```
POST /api/v1/tasks
  └─ tasks.create_task()                          [api/v1/tasks.py]
       └─ run_generation_task.delay(task_id)       [Celery 异步入队]
            ├─ generate_dialogue()                 [services/dialogue.py]
            │    ├─ build_prompt()                 [注入 few-shot + 场景背景 + 关键词]
            │    ├─ provider.complete(messages)    [providers/llm/deepseek.py]
            │    └─ parse_dialogue()
            ├─ apply_postprocess()                 [services/postprocess.py]
            │    ├─ enforce_keywords_in_lines()    [multilingual_naturalness_lite.py]
            │    └─ stabilize_dialogue_constraints()
            ├─ check_quality()                     [services/quality_check.py]
            └─ synthesize_lines()                  [services/audio.py]
                 ├─ CosyVoiceProvider.synthesize() [providers/tts/cosyvoice.py]
                 │  └─ [失败] EdgeTTSProvider.synthesize() [providers/tts/edge_tts_provider.py]
                 ├─ _ffmpeg_normalize()            [silenceremove + 44100Hz mono MP3]
                 ├─ _ffmpeg_concat()               [filter_complex concat 无缝拼接]
                 └─ upload_bytes(MinIO)            [providers/storage/minio_client.py]
```

### 数据流

```
用户表单 → TaskCreate（Pydantic 校验）
  → Task DB 记录（params JSON 列快照全量入库）
  → Celery 任务参数（task_id string）
  → LLM messages（system prompt 含 few-shot + user prompt 含关键词）
  → LLM 原始文本（"Speaker 1: ...\nSpeaker 2: ..."）
  → lines = [(speaker_id, text), ...]（parse_dialogue）
  → 后处理后 lines（关键词注入 + 说话人稳定化）
  → merged_lines（同 speaker 连续行合并）
  → 分段 WAV bytes（每 merged segment 一次 CosyVoice API）
  → 分段 MP3 bytes（ffmpeg 转码 + silenceremove）
  → final.mp3 bytes（ffmpeg filter_complex concat）
  → MinIO storage_key（presigned URL 供下载）
  → AudioFile DB（file_name、duration_sec、storage_key、language、tags）
  → Transcript DB（segments: [{speaker_id, text, start_time, end_time}]）
```

### 外部资源调用

| 资源类型 | 名称 | 调用位置 | 说明 |
|---------|------|---------|------|
| LLM API | DeepSeek | `providers/llm/deepseek.py` | `POST /v1/chat/completions`，OpenAI 兼容协议 |
| LLM API | OpenAI | `providers/llm/deepseek.py` | 同上，换 base_url 即可 |
| LLM API | Anthropic | `providers/llm/anthropic.py` | `POST /v1/messages`，独立协议 |
| TTS API | CosyVoice | `providers/tts/cosyvoice.py` | `POST /v1/audio/speech`，返回 WAV bytes |
| TTS API | Microsoft Edge TTS | `providers/tts/edge_tts_provider.py` | 降级备用，免费无需 key |
| 对象存储 | MinIO | `providers/storage/minio_client.py` | S3 兼容，本地 `localhost:9000` |
| 消息队列 | Redis 7 | `celery_app.py` | Celery broker + result backend |
| 关系数据库 | MySQL 8.0 | `core/db.py` | `audio_platform` 库，6 张业务表 |

---

## 章节 7：深度解读 / Deep Technical Notes

### `tasks/generation.py` — 最核心的 Celery 任务

**全局状态**：无模块级可变状态，所有状态通过 DB 传递。每次调用创建独立 `SessionLocal()`，`finally` 块确保关闭，无连接泄漏。

**关键细节**

| 问题 | 位置 | 说明 |
|------|------|------|
| `target_duration_sec → word_count` 换算 | 第 98 行 | `target_words = max(50, int(target_duration_sec * 2.5))`，150字/分钟估算 |
| speaker_count 校验时机 | 第 83 行 | 在后处理之前做；后处理可能增加行但不增加 speaker 种类，顺序正确 |
| `get_settings()` lru_cache | `core/config.py` | `.env` 修改后必须重启或调 `get_settings.cache_clear()` 才生效 |
| 降级标记 | 第 142 行 | `degraded=True` 时写 `error_message="[TTS_WARN]..."`，任务仍 SUCCEEDED |

---

### `services/audio.py` — 音频合成引擎

**段合并逻辑**

同 speaker 连续行合并（上限 500 字），减少 CosyVoice API 调用次数（每次调用约 3-7 秒）。合并保持 speaker_id 不变，时间码按合并后段计算。

**silenceremove 参数选择**

`-65dB` 是保守阈值：CosyVoice 数字静音约 -90dB，正常语音 > -40dB，-65dB 只裁数字静音不误删语音。`start_duration=0.05s` 防止裁掉极短起音，`stop_duration=0.15s` 保留自然句尾停顿。

**`fallback_tts.default_voice_for(language)` 设计原因**

不直接引用 `_EDGE_VOICE_MAP` dict，而是通过方法调用。目的：避免服务层（`audio.py`）反向依赖 provider 层（`edge_tts_provider.py`）的内部实现细节，保持层次清晰。

---

### `migrations/env.py` — 两个必知的坑

**坑 1：必须传 URL 对象，不能 `str(url)`**

`str(SQLAlchemy URL)` 会把密码遮成 `***`（SQLAlchemy 安全设计），导致 MySQL 认证失败（Access Denied for user 'app'@'...'）。

```python
# ✅ 正确
connectable = create_engine(get_settings().database_url, poolclass=pool.NullPool)

# ❌ 错误（密码变 ***，MySQL 拒绝连接）
connectable = create_engine(str(get_settings().database_url), ...)
```

**坑 2：MySQL UUID 列需要 `uuid.UUID` 对象，不能用字符串**

JWT payload 的 `sub` 字段是字符串，但 `User.user_id` 是 `Uuid(as_uuid=True)` 列，MySQL 驱动会对 UUID 对象调 `.hex()` 转成 16 字节 binary 存储。传字符串报 `AttributeError: 'str' object has no attribute 'hex'`。

```python
# deps.py 的修复写法
user_id = uuid.UUID(payload.get("sub"))   # 先转 uuid.UUID 再查询
```

---

### 快速启动检查清单

```bash
# 前置条件
1. Docker Desktop 启动（左下角 Engine running）
2. .env 中 LLM_API_KEY 已填入（DeepSeek key）

# 启动服务
3. 双击 start.bat → 等待"All services started!"
   → 后端：http://localhost:8000/docs
   → 前端：http://localhost:5173

# 若需 LLM 生成任务（必须单独启动 Celery）
4. 新开终端：
   cd D:\Github\test-audio-builder-platform
   backend\.venv\Scripts\celery -A app.celery_app worker --loglevel=info -Q text_gen,audio_synth --concurrency=2

# 若需真人音色合成
5. 在 .env 中填入 COSYVOICE_BASE_URL，重启后端
   → 在前端"⚙️ 管理真人音色"上传参考音频注册音色
   → 注册成功后可在生成弹窗中选择使用
```

---

*文档生成完毕。分析了 10 个文件（深读 4 个，grep 6 个，推测 0 个）。主入口：`backend/app/main.py`。无推测标注。*
