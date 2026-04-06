# scripts 目录说明

当前 `scripts/` 分成两类：

- 根目录脚本
  - 启动、门禁、检查、GitHub CLI 辅助、发布辅助
- `maintenance/`
  - 维护与清理类脚本

## 常用入口

- `start_server.py`
  - Python 启动入口
- `run_pre_release_ci_gate.py`
  - 发布前检查主入口
- `run_repo_daily_check.py`
  - 仓库日常检查
- `maintenance/project_guard.py`
  - 项目结构守卫

如果后续再加脚本：

- 面向开发/检查/发布的，放 `scripts/`
- 面向清理/治理/维护的，放 `scripts/maintenance/`
