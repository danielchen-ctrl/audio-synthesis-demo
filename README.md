# demo_app

## 项目简介

`demo_app` 是一个可演示的场景对话 Demo，当前支持：

- 通过 Web 页面生成场景对话文本
- 在 Web 端手动修改生成文本
- 基于当前文本继续合成音频
- 下载文本、音频、字幕与分段文件
- 运行多语言质量检查与 source-only 回归

## 目录结构说明

当前仓库以“可演示版本 + 脚本化治理 + GitHub 协作流程”为主，核心目录如下：

- `embedded_server.py`
  - 当前实际服务主实现
- `static/`
  - Web 前端页面
- `config/`
  - 配置文件与规则文件
- `docs/`
  - 项目说明、架构、开发流程、发布流程和 Project 规则
- `scripts/`
  - 启动、治理、回归和发布辅助脚本
- `tests/`
  - 自动化测试
- `tools/`
  - 生成、验证和辅助工具
- `training/`
  - 训练与数据构建脚本
- `src/demo_app/`
  - 当前主要存放资源与领域数据，业务源码结构待补充

## 快速开始

### 一键启动 Demo

直接双击：

- `start_demo.bat`

或命令行执行：

```bat
start_demo.bat
```

启动后访问：

- `http://127.0.0.1:8899/`
- `http://localhost:8899/`

如果需要分享给其他电脑使用，请查看：

- `docs/demo-startup-sharing-guide.md`

### 日常检查

仓库日常检查：

- `scripts\run_repo_daily_check.bat`

多语言质量检查：

- `scripts\run_multilingual_quality_checks.bat`

执行后会固定产出：

- `reports/multilingual_quality_checks/latest.json`
- `reports/multilingual_quality_checks/latest.md`

报告中包含：

- 总体状态与检查摘要
- 失败摘要（按语言 / 场景 / 组件拆分）
- 建议动作（便于人工排查和后续自动化消费）

发布前门禁检查：

- `python scripts/run_pre_release_ci_gate.py`
- `python scripts/enforce_pre_release_ci_gate.py --report reports/pre_release_gate/latest.json`

GitHub Actions 中对应的工作流：

- `.github/workflows/pre-release-gate.yml`

### 调试垃圾清理

- `scripts\clean_debug_artifacts.bat`

## Demo 启动、分享与排障

如果你要把 Demo 分享给别人使用，推荐优先阅读：

- `docs/demo-startup-sharing-guide.md`

这份文档覆盖：

- 一键启动方式
- 局域网分享方式
- 文本编辑后继续合成音频
- 文本/音频下载
- 防火墙、端口占用、构建包缺失等常见问题排查

## 开发流程

建议按以下顺序工作：

1. 先阅读：
   - `AGENTS.md`
   - `README.md`
   - `docs/project-overview.md`
   - `docs/architecture.md`
2. 从 GitHub Issue 开始任务
3. 建立分支开发
4. 本地自测与脚本检查
5. 提交代码并发起 PR

建议在提交前至少执行一次：

- `scripts\run_repo_daily_check.bat`
- `python scripts/run_pre_release_ci_gate.py`

更详细说明见：

- `docs/development-workflow.md`

## 分支策略

- `main`：始终保持可演示、可发布
- `dev`：日常集成
- `feature/*`：单功能开发
- `fix/*`：缺陷修复
- `release/*`：发布准备（如需要）

## 版本发布方式

版本标签建议采用：

- `v0.1.0`
- `v0.2.0`
- `v1.0.0`

辅助脚本：

- `scripts/release_tag.ps1`
- `scripts/release_tag.sh`

详细流程见：

- `docs/release-process.md`

## GitHub Project / Issues / PR 协作方式

推荐方式：

1. 每项工作优先对应一个 Issue
2. Issue 带类型标签：
   - `feature`
   - `bug`
   - `task`
3. Issue 加入 GitHub Project
4. PR 关联 Issue
5. 任务状态按 `Backlog / Todo / In Progress / Review / Done` 流转

详细说明见：

- `docs/project-board-workflow.md`
- `docs/github-project-setup-checklist.md`

## 与 Codex 的协作方式

Codex 进入仓库后，默认应先阅读：

1. `AGENTS.md`
2. `README.md`
3. `docs/` 下相关文档

请在开始修改前先理解：

- 当前任务目标
- 当前分支策略
- 当前工作是否有对应 Issue / Task

如果涉及高风险操作，例如大规模删除、改 Git 历史、改核心发布流程，需要先确认。
