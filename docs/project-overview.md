# 项目概览

## 项目用途

本项目用于维护 `demo_app` 的可演示版本，支持：

- 通过 Web 页面生成场景对话文本
- 手动编辑生成结果
- 继续合成音频
- 下载文本、音频、字幕和分段文件
- 进行多语言质量检查与 source-only 回归

## 核心模块

当前仓库的核心模块如下：

- `embedded_server.py`
  - 当前实际服务主实现
  - 提供 Web 接口、文本生成、音频合成和下载能力
- `static/`
  - 当前前端页面与交互逻辑
- `scripts/`
  - 启动脚本、质量检查、项目治理、版本辅助脚本
- `config/`
  - 运行配置与规则配置
- `tests/`
  - 自动化测试与回归检查
- `tools/`
  - 批量生成、验证与辅助工具

## 当前目标

当前阶段目标是：

1. 保持 Demo 可稳定演示
2. 让多人协作、任务管理和版本发布形成规范
3. 让 Codex 进入仓库后能快速理解结构与工作方式
4. 让 GitHub Issues / PR / Project / Release 形成统一流程

## 推荐维护方式

建议按以下方式维护：

1. 任何功能改动先对应一个 Issue
2. 小步开发，小步提交
3. 修改流程、结构或脚本时同步更新文档
4. 日常先运行：
   - `scripts\run_repo_daily_check.bat`
   - `scripts\run_multilingual_quality_checks.bat`
5. 多语言质量报告固定查看：
   - `reports/multilingual_quality_checks/latest.json`
   - `reports/multilingual_quality_checks/latest.md`
6. 如果质量检查失败，优先查看：
   - `failure_summary`
   - `suggested_actions`
7. 发布前确认：
   - Web 可启动
   - 关键脚本可用
   - README 与变更说明同步更新

如果当前工作涉及对外演示或把 Demo 分享给其他人使用，请同步维护：

- `docs/demo-startup-sharing-guide.md`
