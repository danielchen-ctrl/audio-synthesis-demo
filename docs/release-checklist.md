# 发布核对清单

> 用途：在 `main` 分支准备打版本前，按顺序核对一次，避免“只打 tag、没核对可演示性和文档”的情况。

## 一、版本前提

- [ ] 当前发布目标和范围已经明确
- [ ] 对应 Issue / PR / Milestone 已经收口
- [ ] `main` 分支处于可演示状态
- [ ] 工作区干净：`git status` 无未提交改动
- [ ] 准备发布的版本号已确认，例如 `v0.2.0`

## 二、代码与运行检查

- [ ] 一键启动可用：`start_demo.bat`
- [ ] Web 首页可打开：`http://127.0.0.1:8899/`
- [ ] 文本生成可用
- [ ] 文本编辑后可继续生成音频
- [ ] 文本 / 音频下载可用
- [ ] `scripts/run_repo_daily_check.bat` 通过
- [ ] `python scripts/run_pre_release_ci_gate.py` 通过
- [ ] `python scripts/enforce_pre_release_ci_gate.py --report reports/pre_release_gate/latest.json` 通过

## 三、质量与报告检查

- [ ] 查看 `reports/pre_release_gate/latest.md`
- [ ] 查看 `reports/multilingual_quality_checks/latest.md`
- [ ] 若存在失败摘要，已明确是否阻塞发布
- [ ] 已确认当前已知问题和风险说明

## 四、文档与版本信息

- [ ] `README.md` 已更新到当前真实状态
- [ ] `docs/demo-startup-sharing-guide.md` 与当前启动方式一致
- [ ] 本次改动的说明已整理为 release note
- [ ] 版本号、目标里程碑、关键功能点一致

## 五、Git 与发布动作

- [ ] 当前分支为 `main`
- [ ] 已拉取最新远程：`git pull --ff-only origin main`
- [ ] 版本号符合规范：`v主版本.次版本.修订号`
- [ ] 使用打 tag 脚本或等价命令创建 tag
- [ ] tag 已推送到远程

## 六、发布后确认

- [ ] 在 GitHub 上确认 tag 已存在
- [ ] Release Note 已归档或发布
- [ ] 若需要对外演示，已验证分享地址和下载能力
- [ ] 若需要回滚，已记录可回退 tag / commit
