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

- `main`：始终保持可演示、可发布，只接受通过 PR 合并的改动
- `dev`：日常集成
- `feature/*`：单功能开发
- `fix/*`：缺陷修复
- `docs/*`：文档与说明调整
- `ci/*`：工作流、门禁、自动化脚本调整
- `chore/*`：仓库治理、脚本清理、杂项维护
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

补充约束：

1. 不直接在 `main` 上开发和提交
2. 每个 Issue / 任务都使用独立分支
3. 分支命名优先使用：
   - `docs/*`
   - `feature/*`
   - `fix/*`
   - `ci/*`
   - `chore/*`
   - 若由 Codex 自动创建分支，实际会体现为 `codex/docs/*`、`codex/feature/*` 等形式
4. 改动完成后先创建 PR，再合并到 `main`
5. PR 合并后，本地正式目录使用 `git pull origin main` 同步最新代码

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

- `src/demo_app/embedded_server_main.py`：当前实际服务主实现
- `server.py`：根目录唯一服务入口
- `static/`：Web 前端资源
- `scripts/`：启动、检查、治理和自动化脚本
- `config/`：项目配置
- `tests/`：自动化测试

`src/demo_app/` 当前承载服务实现、多语言文本处理和领域数据，文档中会持续以“当前真实状态”为准。
