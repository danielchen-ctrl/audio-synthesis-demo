# 发布流程

## 从 dev 合并到 main

推荐流程：

1. 在 `dev` 完成集成和回归
2. 确认关键脚本可用
3. 执行发布前门禁检查
4. 确认 README、流程文档、变更说明已更新
5. 从 `dev` 发起到 `main` 的 PR
6. 审核通过后合并到 `main`

建议执行：

```powershell
python scripts/run_pre_release_ci_gate.py
python scripts/enforce_pre_release_ci_gate.py --report reports/pre_release_gate/latest.json
```

## 如何打 tag

推荐采用语义化版本号：

- `v0.1.0`
- `v0.2.0`
- `v1.0.0`

可使用脚本：

- `scripts/release_tag.ps1`
- `scripts/release_tag.sh`

示例：

```powershell
scripts/release_tag.ps1 v0.1.0
```

```bash
./scripts/release_tag.sh v0.1.0
```

## 如何准备 release note

建议至少包含：

1. 本次版本目标
2. 新功能
3. 修复项
4. 风险与已知问题
5. 升级/回滚说明

建议同时引用：

- `reports/pre_release_gate/latest.md`
- `reports/multilingual_quality_checks/latest.md`

其中多语言质量报告建议重点检查：

- `summary`
- `failure_summary`
- `suggested_actions`

这样在 release note 里可以明确说明：

- 哪些语言 / 场景已通过
- 是否存在失败摘要
- 发布前还需要补哪些动作

## 如何回滚到历史版本

推荐方式：

1. 找到目标 tag 或 commit
2. 在本地验证该版本可用
3. 根据情况：
   - 新建修复分支
   - 或将 `main` 回退到某个 tag 后再发布

如果需要改写远程历史，属于高风险操作，应先确认团队影响范围。
