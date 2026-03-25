# 开发流程

## 本地开发步骤

1. 阅读：
   - `README.md`
   - `AGENTS.md`
   - `docs/project-overview.md`
   - `docs/architecture.md`
2. 创建或切换分支
3. 开发与自测
4. 运行仓库检查脚本
5. 提交代码
6. 发起 PR

推荐在提 PR 前至少执行：

- `scripts\run_repo_daily_check.bat`
- `python scripts/run_pre_release_ci_gate.py`

## 本地启动

推荐入口：

- `start_demo.bat`

服务启动后访问：

- `http://127.0.0.1:8899/`

## 分支使用方式

- `main`
  - 保持可演示、可发布
  - 不直接开发，所有改动通过 PR 合并进入
- `dev`
  - 日常集成分支
- `docs/*`
  - 文档与说明调整
- `feature/*`
  - 新功能开发
- `fix/*`
  - 问题修复
- `ci/*`
  - CI、门禁、自动化脚本调整
- `chore/*`
  - 仓库治理与杂项维护
- `release/*`
  - 发布准备（如需要）

## 提交与 PR 流程

1. 从 Issue 开始
2. 创建独立分支，分支前缀使用：
   - `docs/`
   - `feature/`
   - `fix/`
   - `ci/`
   - `chore/`
   - 若由 Codex 自动创建，分支会带工具前缀，例如 `codex/docs/...`
3. 在对应分支开发
4. 自测通过后提交
5. 推送并发起 PR
6. 在 PR 中说明：
   - 变更目的
   - 主要改动
   - 测试情况
   - 风险与回滚
   - 关联 Issue
7. PR 合并到 `main` 后，在本地正式目录执行：
   - `git pull origin main`

## Codex 接入方式

Codex 进入仓库后建议顺序：

1. 先读 `AGENTS.md`
2. 再读 `README.md`
3. 再读 `docs/` 相关文档
4. 修改前先确认当前任务对应的 Issue / PR / 文档

## 如何从 Issue 开始一个任务

1. 新建或领取一个 Issue
2. 补齐标签：
   - `feature`
   - `bug`
   - `task`
3. 如果使用 GitHub Project，将 Issue 加入看板
4. 创建分支，例如：
   - `docs/startup-sharing-guide`
   - `feature/share-download`
   - `fix/audio-fallback`
   - `ci/pre-release-gate`
   - `chore/repo-cleanup`
5. 开发完成后提交 PR 并关联 Issue

## 发布前门禁

当前仓库的正式发布前门禁入口是：

- `python scripts/run_pre_release_ci_gate.py`
- `python scripts/enforce_pre_release_ci_gate.py --report reports/pre_release_gate/latest.json`

对应 GitHub Actions 工作流：

- `.github/workflows/pre-release-gate.yml`

说明：

- 该门禁基于当前仓库的真实可运行结构（`embedded_server.py` + `scripts/start_server.py`）
- 如果当前 checkout 缺少本地 build bundle，embedded smoke 会被标记为 `skipped`
- 其余仓库级检查（关键文件、YAML、Python 编译、repo daily check）仍会继续执行
