# 音频语料生成平台 v2

> 基于 FastAPI + Vue 3 + MySQL + Redis + MinIO + Celery 的内部音频语料生成平台。
> 配套技术设计文档见 `../音频语料生成平台_技术设计文档.md`。

---

## 当前阶段

**Phase 1: 核心骨架 MVP**

✅ 已实现：
- 用户注册 / 登录 / JWT 鉴权
- 任务提交 → Celery 异步处理
- LLM Provider 抽象层 + DeepSeek 实现（**配置文件可切换其他 LLM**）
- CosyVoice TTS Provider
- 文件存储到 MinIO
- 文件列表 / 详情 / 软删除
- Vue 3 + Naive UI 前端

⏳ 待实现（结构已留好）：
- 文件夹 / 标签 / 全局搜索 6 维 filter
- 用户上传音频
- 三遍后处理 + 质量门禁迁移
- few-shot 检索
- JSON / SRT 脚本输出
- 回收站自动清理
- WebSocket 实时推送（当前用 3 秒轮询）

---

## 目录结构

```
audio-platform-v2/
├── backend/                  # FastAPI + Celery
│   ├── app/
│   │   ├── core/             # 配置、DB、安全
│   │   ├── models/           # SQLAlchemy ORM
│   │   ├── schemas/          # Pydantic I/O 模型
│   │   ├── api/v1/           # REST 路由
│   │   ├── providers/        # LLM / TTS / Storage 抽象
│   │   ├── services/         # 业务逻辑
│   │   └── tasks/            # Celery 任务
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                 # Vue 3 + Vite + Naive UI
│   ├── src/
│   │   ├── api/              # API 客户端
│   │   ├── stores/           # Pinia
│   │   ├── pages/            # 页面
│   │   └── components/
│   └── package.json
├── deploy/                   # 生产部署
│   ├── docker-compose.prod.yml
│   └── nginx.conf
├── docker-compose.dev.yml    # 本地依赖（PG/Redis/MinIO）
├── .env.example
└── README.md
```

---

## 本地开发（Mac）

### 0. 前置条件

```bash
# Mac 上要装：
brew install python@3.11 node ffmpeg
# Docker Desktop 或 OrbStack（推荐）
brew install --cask orbstack
```

### 1. 起依赖服务

```bash
cd test-audio-builder-platform
cp .env.example .env
# 编辑 .env，至少填：JWT_SECRET、MYSQL_PASSWORD、LLM_API_KEY、COSYVOICE_BASE_URL
docker compose -f docker-compose.dev.yml up -d
```

确认服务起来：
```bash
docker compose -f docker-compose.dev.yml ps
# 应该看到 mysql / redis / minio 都是 healthy
```

MinIO 控制台：http://localhost:9001（账号 minioadmin / minioadmin）

### 2. 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .

# 初始化 DB（首次运行）
python -m app.scripts.init_db

# 起 API
uvicorn app.main:app --reload --port 8000

# 另开终端起 Celery worker（文本生成 + 音频合成）
celery -A app.celery_app worker --loglevel=info -Q text_gen,audio_synth --concurrency=2
```

API 文档：http://localhost:8000/docs

### 3. 启动前端

```bash
cd frontend
npm install      # 或 pnpm install
npm run dev
```

浏览器打开 http://localhost:5173

---

## 连接 staging 数据库（MySQL on RDS）

数据库使用托管的 **MySQL（AWS RDS）**，不在公网开放，需经 VPC 内主机访问。

- **本地开发**：先开 bastion SSH 隧道，再让 `.env` 指向 `127.0.0.1:13306`
  ```bash
  ssh -fN -i ~/.ssh/<你的key> \
    -L 13306:<rds-endpoint>:3306 ubuntu@<跳板机>
  # .env: MYSQL_HOST=127.0.0.1  MYSQL_PORT=13306
  ```
- **VPC 内服务器**：直连，无需隧道
  ```
  MYSQL_HOST=<rds-endpoint>   MYSQL_PORT=3306
  ```

> 🔒 `.env` 含真实密钥（DB 密码 / LLM key / JWT），**已被 `.gitignore` 排除、绝不提交**。
> 密钥通过 1Password / Slack 私下传递，或用 `scp` 直传到服务器，切勿走 git。

---

## 生产/服务器部署（Linux 服务器，VPC 内）

```bash
# 1. 拉代码（仓库不含 .env）
git clone git@github.com:Plaud-AI/test-audio-builder-platform.git
cd test-audio-builder-platform

# 2. 放置 .env（不要 git pull，单独传）
#    方式 A：从本地 scp 一份服务器版（MySQL 直连 RDS）过来
#    方式 B：cp .env.example .env 后手动填密钥
#    关键：服务器版用 MYSQL_HOST=<rds-endpoint> / MYSQL_PORT=3306（直连，不走隧道）
mv ~/audio-builder.env ./.env    # 若已用 scp 传到 ~ 下

# 3. 一键启动
docker compose -f deploy/docker-compose.prod.yml up -d --build

# 4. 初始化 DB（首次，建表 + 可选建管理员）
docker compose -f deploy/docker-compose.prod.yml exec api python -m app.scripts.init_db
```

平台访问：https://your-domain.com

---

## 切换 LLM Provider

**只需改 `.env`**，无需改代码：

```bash
# DeepSeek（默认）
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# 换 OpenAI
LLM_PROVIDER=openai
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# 换 Anthropic Claude
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-xxx
LLM_BASE_URL=https://api.anthropic.com
LLM_MODEL=claude-opus-4-7

# 换公司内部网关（兼容 OpenAI 协议）
LLM_PROVIDER=openai
LLM_API_KEY=internal-token
LLM_BASE_URL=https://llm-gateway.company.com/v1
LLM_MODEL=your-model-name
```

重启 API 和 Celery worker 生效。

---

## 关键架构决策

| 决策 | 理由 |
|---|---|
| FastAPI 而非 Tornado | 类型注解 + 自动 OpenAPI 文档 + 现代 async |
| MySQL 而非 SQLite | 多 worker 共享、托管 RDS、备份成熟 |
| Celery 而非 Python 线程 | 任务持久化、自动重试、可横向扩展 |
| MinIO 而非本地文件 | S3 兼容，未来切云对象存储零改动 |
| Provider 抽象层 | LLM/TTS 切换零代码改动 |
| Docker Compose | Mac 本地和 Linux 生产同一份配置 |

详见 `../音频语料生成平台_技术设计文档.md`。

---

## 常见问题

**Q: 没有 CosyVoice 服务怎么开发？**
A: 配置一个假地址，TTS 调用会失败但其他流程能跑。后续会加 MockTTSProvider 用于开发。

**Q: 端口冲突？**
A: 改 `.env` 里的 `APP_PORT`，以及 `docker-compose.dev.yml` 里的端口映射。

**Q: Mac 上 ffmpeg 找不到？**
A: `brew install ffmpeg`。生产 Docker 镜像里已内置。

**Q: 怎么看 Celery 任务？**
A: 开发时启动 `celery -A app.celery_app flower` 访问 http://localhost:5555。
