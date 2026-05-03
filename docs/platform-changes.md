# 语料生成平台改造说明文档

> **改造范围**：在原有音频合成 Demo 基础上，叠加一套完整的「语料生成平台」，原 Demo 功能完全保留，互不干扰。
>
> **改造周期**：Phase 1–5，共 5 个阶段
>
> **启动方式**：`python server_platform.py`（新平台）或 `python server.py`（原 Demo）

---

## 目录

1. [整体架构](#1-整体架构)
2. [新增文件一览](#2-新增文件一览)
3. [Phase 1 — 后端基础](#3-phase-1--后端基础)
4. [Phase 2 — 前端 SPA](#4-phase-2--前端-spa)
5. [Phase 3 — 统计与搜索增强](#5-phase-3--统计与搜索增强)
6. [Phase 4 — 视觉与交互打磨](#6-phase-4--视觉与交互打磨)
7. [Phase 5 — 高级功能](#7-phase-5--高级功能)
8. [API 接口速查](#8-api-接口速查)
9. [数据库结构](#9-数据库结构)
10. [部署与配置](#10-部署与配置)

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────┐
│                    浏览器 / SPA                       │
│              static/index.html (1505 行)              │
│   全部文件 │ 我的文件 │ 生成任务 │ 回收站 │ 详情页    │
└────────────────────────┬────────────────────────────┘
                         │ HTTP / REST
┌────────────────────────▼────────────────────────────┐
│              server_platform.py (入口)               │
│   make_app() ← 原 Demo 路由全部保留                  │
│   register_platform_routes() ← 注册新平台路由        │
│   start_worker() ← 启动异步任务协程                  │
└──────────┬──────────────────────┬───────────────────┘
           │                      │
┌──────────▼──────────┐  ┌───────▼──────────────────┐
│   webapp/handlers.py │  │   webapp/task_runner.py   │
│   18 个 Handler      │  │   asyncio.Queue 任务队列  │
│   /api/platform/*    │  │   调用原 Bundle Server    │
└──────────┬──────────┘  │   生成文本 + 合成音频     │
           │              └───────────────────────────┘
┌──────────▼──────────┐
│   webapp/db.py       │
│   SQLite platform.db │
│   tasks / audio_files│
│   / folders 三张表   │
└─────────────────────┘
```

### 设计原则

| 原则 | 实现方式 |
|------|---------|
| **零侵入** | 不修改 `server.py` 和 `embedded_server_main.py`，原 Demo 独立运行不受影响 |
| **零依赖** | SQLite（Python 内置）、Tornado（已有）、edge_tts（已有），无需安装新包 |
| **懒加载** | Bundle Server 在首次任务执行时才加载，不拖慢启动速度 |
| **单文件前端** | 整个 SPA 自包含于 `static/index.html`，无构建工具、无框架依赖 |

---

## 2. 新增文件一览

```
audio-synthesis-demo/
├── server_platform.py          ← 平台入口（新增，87 行）
├── platform.db                 ← SQLite 数据库（运行时生成，gitignore）
├── storage/                    ← 音频存储目录（运行时生成，gitignore）
│   ├── generated/              ←   AI 生成的音频（按 task_id 分目录）
│   └── uploaded/               ←   手动上传的音频
├── static/
│   ├── index.html              ← 平台 SPA（修改，1505 行）
│   └── legacy.html             ← 原 Demo 备份（新增，338 行）
└── webapp/                     ← 平台后端（全部新增）
    ├── __init__.py
    ├── db.py                   ← SQLite CRUD（382 行）
    ├── handlers.py             ← Tornado 请求处理器（587 行）
    ├── routes.py               ← 路由注册（63 行）
    └── task_runner.py          ← 异步任务队列（229 行）
```

---

## 3. Phase 1 — 后端基础

### 3.1 数据库（`webapp/db.py`）

三张表，全部幂等初始化（`CREATE TABLE IF NOT EXISTS`）：

#### `tasks` 表 — 生成任务

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | TEXT PK | UUID hex 前 16 位 |
| `status` | TEXT | `queued` → `generating_text` → `synthesizing` → `completed` / `failed` |
| `generation_mode` | TEXT | `llm`（AI 生成）或 `direct`（直接输入） |
| `topic` | TEXT | 文本主题（LLM 模式必填） |
| `language` | TEXT | 合成语言，如 `中文（普通话）` |
| `people_count` | INTEGER | 说话人数（1–10） |
| `word_count` | INTEGER | 目标字数（LLM 模式） |
| `template` | TEXT | 场景模板（meeting/interview/medical/custom） |
| `keywords` | TEXT | JSON 数组，关键词列表 |
| `custom_prompt` | TEXT | 自定义提示词 |
| `input_text` | TEXT | 直接输入的对话文本 |
| `voice_map` | TEXT | JSON 对象，`{"Speaker 1": "zh-CN-XiaoxiaoNeural", ...}` |
| `output_format` | TEXT | `mp3` 或 `wav` |
| `include_scripts` | INTEGER | 是否保存 SRT 字幕（0/1） |
| `error_msg` | TEXT | 失败原因 |
| `file_id` | TEXT | 完成后关联的音频文件 ID |
| `created_at` / `updated_at` / `completed_at` | TEXT | ISO 8601 时间戳 |

#### `audio_files` 表 — 音频文件

| 字段 | 类型 | 说明 |
|------|------|------|
| `file_id` | TEXT PK | UUID hex 前 16 位 |
| `task_id` | TEXT | 关联任务（上传文件为 NULL） |
| `file_name` | TEXT | 文件名 |
| `file_path` | TEXT | 磁盘绝对路径 |
| `source` | TEXT | `generated`（AI 生成）或 `uploaded`（手动上传） |
| `duration` | REAL | 时长（秒） |
| `format` | TEXT | `mp3` / `wav` |
| `file_size` | INTEGER | 字节数 |
| `language` | TEXT | 语言 |
| `speaker_count` | INTEGER | 说话人数 |
| `scene` | TEXT | 场景（meeting/interview/medical/other） |
| `topic` | TEXT | 主题/备注 |
| `transcript_json` | TEXT | 分段字幕 JSON（含 speaker/text/start_time/end_time） |
| `transcript_srt` | TEXT | SRT 格式字幕 |
| `tags` | TEXT | JSON 数组，用户标签 |
| `folder_id` | TEXT | 所属文件夹（NULL 表示根目录） |
| `deleted` | INTEGER | 软删除标志（0/1） |
| `deleted_at` | TEXT | 移入回收站时间 |
| `created_at` | TEXT | 创建时间 |

#### `folders` 表 — 文件夹

| 字段 | 类型 | 说明 |
|------|------|------|
| `folder_id` | TEXT PK | UUID hex 前 16 位 |
| `name` | TEXT | 文件夹名称 |
| `parent_id` | TEXT | 父文件夹 ID（NULL 表示根级） |
| `created_at` | TEXT | 创建时间 |

### 3.2 异步任务队列（`webapp/task_runner.py`）

```
提交任务 → enqueue(task_id)
              ↓
         asyncio.Queue
              ↓
         _worker() 协程（Tornado IOLoop 内）
              ↓
    ┌─────────────────────────┐
    │  Step 1: 生成文本        │  status = generating_text
    │  • llm 模式：调用 Bundle │
    │  • direct 模式：解析输入 │
    └─────────┬───────────────┘
              ↓
    ┌─────────────────────────┐
    │  Step 2: 合成音频        │  status = synthesizing
    │  调用 _synthesize_audio  │
    │  保存到 storage/generated│
    └─────────┬───────────────┘
              ↓
    ┌─────────────────────────┐
    │  Step 3: 落库            │  status = completed
    │  写入 audio_files 表     │
    └─────────────────────────┘
```

**并发控制**：同时最多 3 个活跃任务（`count_active_tasks() >= 3` 时返回 HTTP 429）。

### 3.3 入口文件（`server_platform.py`）

```python
def main():
    init_db()                    # 1. 初始化 SQLite
    app = make_app()             # 2. 构建原 Demo Tornado app
    register_platform_routes(app) # 3. 追加平台路由
    app.listen(port, address=host) # 4. 监听端口
    threading.Thread(target=_ensure_manifest_cache).start()  # 5. 预热缓存
    IOLoop.current().call_later(0.1, start_worker)           # 6. 启动任务协程
    IOLoop.current().start()
```

端口读取优先级：`DEMO_APP_PORT` → `AUTOGATE_PORT` → `8899`

---

## 4. Phase 2 — 前端 SPA

### 4.1 页面结构

```
/                    ← 新平台首页（全部文件）
├── 全部文件（Home）  ← 所有音频，含统计、搜索、筛选、排序
├── 我的文件（My）    ← 带文件夹侧边栏，支持文件夹管理
├── 生成任务（Tasks） ← 任务卡片网格，实时轮询状态
├── 回收站（Trash）   ← 软删除文件，30 天内可还原
└── 详情页（Detail）  ← 音频播放、元数据编辑、字幕查看

/legacy              ← 原 Demo（完整保留，由 LegacyPageHandler 提供）
```

### 4.2 技术选型

| 项目 | 选择 | 理由 |
|------|------|------|
| 框架 | 无（Vanilla JS） | 零依赖，无需构建，单文件交付 |
| 样式 | 内联 CSS + CSS 变量 | 一致性暗色主题，`--primary` 等变量全局复用 |
| API | `fetch` + 轻量 `API` 对象封装 | GET/POST/PUT/DELETE 统一错误处理 |
| 状态管理 | 模块级 `let` 变量 | 单页面无需 Vuex/Redux |

### 4.3 主要 JS 状态变量

```javascript
let _page = 'home'         // 当前页面
let _folderId = undefined  // undefined=全部, null=根目录, string=具体文件夹
let _allFolders = []       // 展平后的文件夹列表（用于选择器）
let _homeFiles = []        // 当前全部文件页的已加载文件（供 CSV 导出）
let _myFiles = []          // 当前我的文件页的已加载文件
let _prevRunningIds = new Set() // 上次轮询时正在运行的任务 ID（用于完成通知）
let _miniAudio = null      // 行内迷你播放器 Audio 对象
let _voiceLang = '中文（普通话）' // 当前音色选择语言
```

### 4.4 核心功能模块

#### 文件表格

- **双表格**：`tbl-home`（全部文件）和 `tbl-my`（我的文件）共用 `renderFileTable(key, files)` 渲染
- **批量操作**：全选/反选 → Bulk Bar 浮出 → 批量下载（ZIP）/ 移动 / 删除
- **行内播放**：点击 ▶ 在该行下方插入迷你播放器行（颜色条 + 进度条 + 时间）

#### 文件夹管理

- 侧边栏显示文件夹树（仅限「我的文件」页）
- 支持创建 / 重命名 / 删除（删除时文件软删入回收站）
- `loadFolders()` 返回树状结构，`flatTree()` 展平用于下拉选择器

#### 生成弹窗（`modal-gen`）

| 模式 | 流程 |
|------|------|
| **LLM 模式** | 填主题 → 选模板/语言/字数/关键词 → 可选预览文本 → 提交生成任务 |
| **直接输入** | 粘贴 `说话人N: 内容` 格式文本 → 选语言/音色 → 提交 |

两种模式共用底部「音色分配」区域（按说话人数动态生成下拉行）。

#### 详情页内联编辑

点击字段旁的「✎」按钮，原地替换为输入框/下拉框，按 Enter 或点「✓」保存，调用 `PUT /api/platform/files/:id`，响应后原地更新显示值，无需刷新页面。

---

## 5. Phase 3 — 统计与搜索增强

### 5.1 统计 API（`GET /api/platform/stats`）

```json
{
  "ok": true,
  "data": {
    "total_files": 42,
    "total_duration": 18720.5,
    "total_size": 524288000,
    "active_tasks": 1,
    "trash_count": 3,
    "by_language": [
      {"language": "中文（普通话）", "cnt": 28},
      {"language": "英语", "cnt": 10}
    ],
    "by_scene": [
      {"scene": "meeting", "cnt": 18},
      {"scene": "interview", "cnt": 12}
    ]
  }
}
```

统计栏 4 张卡片（全部文件 / 总时长 / 总大小 / 进行中任务）在页面加载时及任务完成时自动刷新。

### 5.2 高级筛选面板

点击「▼ 高级筛选」展开，支持：
- 最小/最大时长（秒）
- 说话人数精确匹配
- 创建日期范围（起/止）

筛选逻辑在客户端执行（`applyAdvFilters()`），不增加额外 API 请求。

### 5.3 文件夹树展平修复

`FoldersHandler.get()` 返回嵌套树结构。修复前：`_allFolders = res.data`（只有根级），导致子文件夹在下拉框中不可见。

修复：`flatTree()` 递归展平所有层级：

```javascript
function flatTree(nodes, acc = []) {
    nodes.forEach(n => {
        acc.push(n);
        if (n.children?.length) flatTree(n.children, acc);
    });
    return acc;
}
```

---

## 6. Phase 4 — 视觉与交互打磨

### 6.1 任务流程可视化

替换原来的单一进度条，改为 4 步管道图：

```
[排队中] ──── [生成文本] ──── [合成音频] ──── [完成]
   ○              ●               ○              ○
（已完成=绿色 ✓，当前=蓝色脉冲，待执行=灰色）
```

状态映射：`queued=0, generating_text=1, synthesizing=2, completed=3, failed=不显示管道图`

### 6.2 波形动画播放器

详情页播放器从静态 🎵 emoji 改为 7 条动态波形条：

```css
.waveform-anim.playing .wb {
    animation: waveAnim 1.1s ease-in-out infinite;
}
@keyframes waveAnim { 0%,100% { height: 6px } 50% { height: 36px } }
```

每条设置不同 `animation-delay`（0s ~ 0.36s），形成流动波浪效果。播放/暂停/结束时同步切换 `playing` class。

### 6.3 任务完成通知横幅

后台每 8 秒轮询一次任务状态（`_prevRunningIds` 记录上次正在运行的 ID）。当某个之前在运行的任务变为 `completed`，底部弹出绿色通知：

```
✅ 任务完成：医院随访问诊  [查看任务 →]  [✕]
```

6 秒后自动淡出，支持手动关闭。

### 6.4 语言/场景分布图

统计栏第 5 张卡片内嵌双段迷你柱状图：

- **语言分布**（蓝色条）：top 5 语言，按文件数降序，最高值=100% 宽度
- **场景分布**（绿色条）：会议/访谈/问诊/其他四种场景

### 6.5 其他增强

| 功能 | 说明 |
|------|------|
| 相对时间 | 任务卡片时间显示「5分钟前」，悬停显示精确时间 |
| 复制台本 | 详情页「字幕/台本」区域右上角「📋 复制文本」按钮 |
| CSV 导出 | 全部文件/我的文件页标题栏「📊 导出CSV」，导出当前可见列表（含 UTF-8 BOM，Excel 直接打开无乱码） |

---

## 7. Phase 5 — 高级功能

### 7.1 失败任务重试

**前端**：失败任务卡片底部出现「↺ 重试」按钮。

**后端**：
```
POST /api/platform/tasks/{task_id}
Body: {"action": "retry"}
```

`db.retry_task()` 仅对 `status='failed'` 的任务执行：
- 重置 `status='queued'`
- 清空 `error_msg`、`file_id`、`dialogue_id`
- 重新调用 `enqueue(task_id)`

### 7.2 清空已完成任务

**前端**：生成任务页标题栏「🗑 清空已完成」→ 确认对话框 → 执行。

**后端**：
```
DELETE /api/platform/tasks?status=completed
```

`db.delete_completed_tasks()` 批量删除所有 `status='completed'` 的任务记录（仅删任务行，关联音频文件不受影响）。

### 7.3 列标题点击排序

表格「文件名」「时长」「创建时间」三列标题可点击，替代纯下拉选择：

- **首次点击**：按该列默认方向排序（时长/创建时间默认降序，文件名默认升序）
- **再次点击**：切换升降序方向
- **视觉反馈**：当前排序列标题旁显示 ↑ / ↓，并高亮蓝色

内部实现：点击时同步修改隐藏的 `<select>` 值，`updateSortIndicators()` 读取该值刷新所有指示器图标。

### 7.4 键盘快捷键

| 快捷键 | 功能 | 限制 |
|--------|------|------|
| `/` | 聚焦当前页搜索框 | 在输入框内、弹窗打开时不触发 |
| `n` | 打开「生成语料」弹窗 | 同上 |
| `?` | 显示/关闭快捷键帮助弹窗 | 同上 |
| `Esc` | 关闭当前弹窗/确认框 | 原有功能 |

### 7.5 响应式汉堡菜单

屏幕宽度 ≤ 680px 时：
- 顶部导航按钮组自动隐藏
- 出现「≡」汉堡按钮
- 点击展开移动端下拉菜单（含全部导航项及「生成语料」「上传音频」快捷入口）
- 点击遮罩层或菜单项自动关闭

---

## 8. API 接口速查

### 任务

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/platform/tasks` | 任务列表（`?limit=&offset=`） |
| POST | `/api/platform/tasks` | 创建任务 |
| DELETE | `/api/platform/tasks?status=completed` | 清空已完成任务 |
| GET | `/api/platform/tasks/{id}` | 任务详情 |
| POST | `/api/platform/tasks/{id}` | 重试失败任务（`{"action":"retry"}`） |
| DELETE | `/api/platform/tasks/{id}` | 删除任务记录 |

### 文件

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/platform/files` | 文件列表（支持 `search/language/scene/source/folder_id/limit/offset`） |
| GET | `/api/platform/files/{id}` | 文件详情 |
| PUT | `/api/platform/files/{id}` | 更新元数据（file_name/scene/language/speaker_count/topic/folder_id/tags） |
| DELETE | `/api/platform/files/{id}` | 软删除（移入回收站） |
| GET | `/api/platform/files/{id}/download` | 下载音频文件 |
| GET | `/api/platform/files/{id}/transcript` | 下载字幕（`?type=json\|srt`） |

### 上传

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/platform/upload` | 上传音频（multipart/form-data，字段：file/language/scene/speaker_count/folder_id/topic） |

### 文件夹

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/platform/folders` | 文件夹树（含 children） |
| POST | `/api/platform/folders` | 创建文件夹（`{"name":"..."}`） |
| PUT | `/api/platform/folders/{id}` | 重命名（`{"name":"..."}`） |
| DELETE | `/api/platform/folders/{id}` | 删除文件夹（内部文件软删） |

### 搜索 / 回收站 / 批量 / 统计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/platform/search` | 全文搜索（`?q=&limit=`） |
| GET | `/api/platform/trash` | 回收站列表 |
| POST | `/api/platform/trash/{id}/restore` | 还原文件 |
| DELETE | `/api/platform/trash/{id}` | 永久删除 |
| POST | `/api/platform/batch/move` | 批量移动（`{"file_ids":[...],"folder_id":"..."}`) |
| POST | `/api/platform/batch/delete` | 批量软删除（`{"file_ids":[...]}`) |
| GET | `/api/platform/batch/download` | 批量下载 ZIP（`?ids=id1,id2,...`） |
| GET | `/api/platform/stats` | 统计信息 |

---

## 9. 数据库结构

```
platform.db（SQLite，WAL 模式，位于项目根目录）
│
├── tasks
│   主键: task_id (TEXT)
│   索引: status, created_at
│
├── audio_files
│   主键: file_id (TEXT)
│   外键: task_id → tasks.task_id（逻辑关联，非 FK 约束）
│         folder_id → folders.folder_id（同上）
│   索引: deleted, language, scene, source, created_at
│
└── folders
    主键: folder_id (TEXT)
    外键: parent_id → folders.folder_id（自引用，支持嵌套）
```

> **软删除机制**：`audio_files.deleted=1` + `deleted_at` 记录删除时间，查询时默认过滤 `deleted=0`；回收站查询 `deleted=1`；永久删除执行 `DELETE`。

---

## 10. 部署与配置

### 启动命令

```bash
# 新平台（推荐）
python server_platform.py

# 原 Demo（独立运行，互不影响）
python server.py
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEMO_APP_HOST` | `0.0.0.0` | 监听地址 |
| `DEMO_APP_PORT` | `8899` | 监听端口（也读 `AUTOGATE_PORT`） |

### 访问地址

| 路径 | 内容 |
|------|------|
| `http://HOST:PORT/` | 语料生成平台（新） |
| `http://HOST:PORT/legacy` | 原音频合成 Demo |
| `http://HOST:PORT/api/platform/*` | 平台 REST API |
| `http://HOST:PORT/api/generate_text` | 原 Demo 文本生成 API（保留） |
| `http://HOST:PORT/api/synthesize_audio` | 原 Demo 音频合成 API（保留） |

### 存储目录

```
storage/
├── generated/{task_id}/     ← AI 生成任务的音频及字幕文件
│   ├── {basename}.mp3
│   ├── {basename}_segments.json
│   └── {basename}_transcript.srt
└── uploaded/                ← 手动上传的音频文件
    └── {stem}_{ts}_{hash}{ext}
```

### 注意事项

1. **Bundle Server**：LLM 文本生成依赖 `build/demo_app/SceneDialogueDemo.exe`，缺失时任务会以 `failed` 结束，但平台本身仍可正常运行（上传、文件管理等功能不受影响）。

2. **并发限制**：同时最多 3 个活跃任务。超出时 API 返回 HTTP 429，前端弹出错误 Toast。

3. **数据库位置**：`platform.db` 在项目根目录，已加入 `.gitignore`，不会被提交。

4. **存储目录**：`storage/` 同样在 `.gitignore` 中，生产部署时需另行备份。

---

*文档生成时间：2026-05-03*
*对应 commit：`0568ccd3` (Phase 2-5) + `05e1ce39` (Phase 1)*
