# GitHub Project 任务流建议

## 推荐字段

建议至少配置以下字段：

- `Status`
- `Priority`
- `Type`
- `Iteration`
- `Target Version`

## 推荐列

推荐使用以下看板列：

- `Backlog`
- `Todo`
- `In Progress`
- `Review`
- `Done`

## 推荐标签

- `feature`
- `bug`
- `task`
- `priority:high`
- `priority:medium`
- `priority:low`
- `blocked`

## 推荐里程碑

- `v0.1 demo`
- `v0.2 demo`
- `v1.0 release`

## 推荐流转方式

1. 新需求、新缺陷、新任务先建 Issue
2. 给 Issue 加类型标签与优先级标签
3. 将 Issue 加入 GitHub Project
4. 根据实际阶段移动状态：
   - `Backlog` -> `Todo` -> `In Progress` -> `Review` -> `Done`
5. 开发时从 Issue 创建分支或手动关联分支
6. PR 中关联 Issue
7. PR 合并后把 Project 卡片移到 `Done`
8. 本地正式目录通过 `git pull origin main` 同步 GitHub 最新代码

## Issue、PR、Project Card 的关联方式

建议做法：

1. Issue 是任务入口
2. Project Card 反映当前状态
3. PR 通过 `Closes #123` 或 `Refs #123` 关联 Issue
4. 发布时用 Milestone 统一归类版本范围
5. 推荐让团队日常只盯 4 个入口：
   - `Projects`：看进度
   - `Issues`：看任务说明
   - `Pull requests`：看变更和合并情况
   - `Code / Actions`：看代码现状和检查结果

## 适合当前仓库的建议

当前仓库包含：

- Demo 迭代
- 多语言质量检查
- GitHub 工作流
- 仓库治理脚本

因此建议 Project 中至少区分三类任务：

- 产品功能任务
- 质量与回归任务
- 仓库治理/自动化任务
