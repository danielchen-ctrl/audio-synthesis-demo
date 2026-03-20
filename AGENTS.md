# AGENTS

## 仓库目标

本仓库用于维护 `demo_app` 的可演示版本、迭代开发、任务管理和发布。

目标包括：

- 保持 `main` 分支始终可演示、可交付
- 支持日常功能迭代、缺陷修复和版本发布
- 让 Codex、GitHub Issues、PR、Project 和发布流程协同工作

## Codex 工作原则

1. 进入仓库后优先阅读：
   - `README.md`
   - `AGENTS.md`
   - `docs/` 下相关文档
2. 先理解后修改，避免直接大改核心文件。
3. 优先小步提交，单次提交只解决一类问题。
4. 不随意改动以下生成目录：
   - `build/`
   - `dist/`
   - `output/`
   - `reports/`
   - `runtime/`
   - `demo/`
5. 修改前先检查是否已有对应 Issue / Task。
6. 高风险改动需要先提示确认，例如：
   - 删除大量文件
   - 改核心配置
   - 改发布流程
   - 改 Git 历史
7. 变更完成后，如涉及流程、结构或使用方式，必须同步更新文档。

## 分支策略

- `main`：始终保持可演示、可发布
- `dev`：日常集成
- `feature/*`：单功能开发
- `fix/*`：缺陷修复
- `release/*`：发布准备（如需要）

## 提交规范

建议使用以下前缀：

- `feat:` 新功能
- `fix:` 缺陷修复
- `docs:` 文档更新
- `chore:` 杂项维护
- `refactor:` 重构
- `test:` 测试相关

## PR 规则

PR 必须至少说明：

1. 变更目的
2. 影响范围
3. 测试结果
4. 回滚方式

如果代码改动影响流程、结构、脚本或协作方式，必须同步更新 `docs/`。

## GitHub Project 任务规则

1. 每项开发工作优先对应一个 Issue。
2. Issue 必须带类型标签：
   - `feature`
   - `bug`
   - `task`
3. PR 必须关联 Issue。
4. Project 推荐状态：
   - `Backlog`
   - `Todo`
   - `In Progress`
   - `Review`
   - `Done`

## 发布规则

1. 只在 `main` 上打 tag。
2. tag 采用语义化格式，例如：
   - `v0.1.0`
   - `v0.2.3`
3. 发布前至少确认：
   - `README.md` 已更新
   - 变更说明已准备
   - 关键启动脚本可用
   - 关键检查脚本可运行

## 当前仓库的真实结构说明

当前仓库的可运行主链以以下文件为主：

- `embedded_server.py`：当前实际服务主实现
- `server.py` / `run.py` / `app.py`：兼容入口
- `static/`：Web 前端资源
- `scripts/`：启动、检查、治理和自动化脚本
- `config/`：项目配置
- `tests/`：自动化测试

`src/demo_app/` 当前主要承载资源和领域数据，业务源码结构仍可继续演进，文档中会持续以“当前真实状态”为准。
