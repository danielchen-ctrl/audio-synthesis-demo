# GitHub Project 设置清单

## 1. Project 名称建议

建议名称：

- `demo_app delivery board`

如果想分阶段，也可以：

- `demo_app v0.x board`
- `demo_app release board`

## 2. 视图建议

建议至少创建两个视图：

1. `Table`
   - 适合批量筛选、补字段、看版本范围
2. `Board`
   - 按 `Status` 分列，适合日常推进

## 3. 字段建议

建议配置以下字段：

- `Status`
- `Priority`
- `Type`
- `Iteration`
- `Target Version`

## 4. 自动化建议

建议先从轻量自动化开始：

1. 新建 Item 默认进入 `Backlog`
2. PR 进入 Review 时，手动把对应卡片移动到 `Review`
3. PR 合并后，将卡片移到 `Done`

后续可以逐步加：

- 根据标签自动设置优先级
- 根据里程碑自动填版本
- 根据 PR 合并自动更新状态

## 5. 里程碑建议

- `v0.1 demo`
- `v0.2 demo`
- `v1.0 release`

## 6. 标签建议

- `feature`
- `bug`
- `task`
- `priority:high`
- `priority:medium`
- `priority:low`
- `blocked`

## 7. 推荐流转

1. 建立 Issue
2. 加标签、里程碑和 Project 字段
3. 放入 Project 对应列
4. 创建分支开发
5. 发起 PR 并关联 Issue
6. 合并后更新状态与里程碑
7. 发布时按 Milestone 汇总 release note
