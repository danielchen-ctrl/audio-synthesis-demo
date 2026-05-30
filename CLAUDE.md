# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 🖥 项目概览（V2 平台）

**架构**：FastAPI + Vue 3 + MySQL + Redis + MinIO + Celery  
**本地工作目录**：`D:\Github\test-audio-builder-platform`  
**GitHub 分支**：`danielchen-ctrl/audio-synthesis-demo` → `V2`  
**状态**：Phase 1 改造完成（P0~P3），含真人音色管理、edge_tts 降级、LLM 后处理、few-shot 检索

---

## 启动方式

```bash
# 1. 依赖服务（MySQL / Redis / MinIO）
docker compose -f docker-compose.dev.yml up -d

# 2. 后端 API
backend\.venv\Scripts\uvicorn app.main:app --reload --app-dir backend
# 访问: http://localhost:8000/docs

# 3. 前端
cd frontend && npm run dev
# 访问: http://localhost:5173
```

---

## 环境变量（.env，gitignored）

关键字段：

| 字段 | 说明 |
|------|------|
| `LLM_API_KEY` | DeepSeek / OpenAI key |
| `LLM_PROVIDER` | `deepseek` / `openai` / `anthropic` |
| `COSYVOICE_BASE_URL` | CosyVoice 服务地址 |
| `EDGE_TTS_FALLBACK_ON_FAILURE` | `true` = CosyVoice 失败时自动降级 edge_tts |
| `LLM_POSTPROCESS_ENABLED` | `true` = 开启关键词注入 + 中文稳定化 |

---

## 数据库 Migration

```bash
# 当前版本
alembic current

# 新建 migration（改完 ORM 后）
alembic revision --autogenerate -m "描述"

# 执行
alembic upgrade head
```

> ⚠️ `create_engine` 必须传 `URL` 对象而非 `str(url)`，`str()` 会把密码遮成 `***`。见 `migrations/env.py`。

---

## 架构概览

```
backend/
  app/
    api/v1/
      auth.py          ← 注册 / 登录 / JWT
      tasks.py         ← 任务提交 / 列表 / 重试 / 取消
      voices.py        ← 音色注册(E2E验证) / 删除 / 列表  ← P2 新增
      files.py         ← 文件列表 / 详情 / 下载
      folders.py       ← 文件夹管理
      meta.py          ← 语言 / 模板 / 音色元数据
      admin.py         ← few-shot stats / reload
    models/
      voice_catalog.py ← 音色目录表（全局共享，软删除）← P2 新增
    providers/tts/
      cosyvoice.py     ← 主 TTS（/v1/audio/speech）
      edge_tts_provider.py ← 降级 TTS（Celery-safe）← P1 新增
    services/
      audio.py         ← synthesize_lines（4-tuple + fallback_tts + silenceremove）← P1 改
      dialogue.py      ← LLM prompt 构建 + few-shot 注入
      few_shot.py      ← v3 训练样本检索（MIN_SCORE=70，933条）
      multilingual_naturalness_lite.py ← 移植自 V1，中文稳定化 + 关键词注入 ← P3 新增
      postprocess.py   ← apply_postprocess()（3A 精简路线）← P3 新增
      quality_check.py ← 3条质量门禁 ← P3 新增
    tasks/
      generation.py    ← Celery 任务：文本生成→后处理→门禁→合成→存 MinIO
frontend/
  src/
    components/
      GenerateModal.vue    ← 生成弹窗（含⚙️管理真人音色按钮）← P2 改
      VoiceManageModal.vue ← 音色管理弹窗 ← P2 新增
    api/
      voices.ts        ← 音色 API 客户端 ← P2 新增
migrations/
  versions/
    6945045eafae_baseline.py     ← 基线（5张原有表）
    a65fcd8fef1d_add_voice_catalog_table.py ← P2 新增
backend/app/data/
  few_shot/     ← 1967条训练样本（gitignored，本地存在）
  preset_topics.json ← 22个预置场景
```

---

## 关键设计说明

### 音色目录（P2）
- `voice_catalog` 表是唯一权威来源，替代 CosyVoice 动态拉取
- 注册流程：调 `/v1/voices/create` → **立即 E2E 合成验证** → 写 DB（验证失败不写 DB）
- 全局共享：所有用户可用；仅创建者可删除

### 音频合成（P1）
- `synthesize_lines()` 返回 `(bytes, float, list[dict], bool)` — 第 4 项 `degraded`
- CosyVoice 失败 → `EdgeTTSProvider`（`asyncio.new_event_loop()`，Celery 安全）
- 降级时 `task.error_message = "[TTS_WARN] 部分片段降级为 edge_tts"`

### LLM 后处理（P3）
- `repair` 遍不迁移（云 LLM 不产生 Bundle 退化）
- `apply_postprocess()` = `enforce_keywords_in_lines` + `stabilize_chinese`（非中文 no-op）
- 质量门禁阈值 30%（对应 `target_duration_sec * 2.5` 换算字数）

### Alembic URL Bug（已修复）
- `str(SQLAlchemy_URL)` 会把密码遮成 `***` → 认证失败
- `migrations/env.py` 必须传 `URL` 对象：`create_engine(get_settings().database_url)`

### MySQL UUID（已修复）
- `deps.py` 中 JWT `sub` 是字符串，MySQL `Uuid` 列需要 `uuid.UUID` 对象
- 修复：`user_id = uuid.UUID(user_id_str)`

---

## 常用命令

```bash
# 语法检查
backend\.venv\Scripts\python -m py_compile backend/app/tasks/generation.py

# few-shot stats
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/admin/few-shot/stats

# 查看 Alembic 历史
alembic history

# 重启后端（修改代码后）
# uvicorn --reload 会自动重启，无需手动操作
```
