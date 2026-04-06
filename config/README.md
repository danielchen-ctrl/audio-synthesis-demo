# config 目录说明

当前 `config/` 只保留运行 demo 仍然有价值的配置：

- `online_audio_ui.json`
  - 在线生成音频弹窗的预置主题、模板、目录与前端展示配置
- `project_guard_rules.yaml`
  - 仓库结构和关键文件门禁规则
- `requirements.txt`
  - 运行和检查脚本依赖
- `runtime*.yaml`
  - 运行环境相关配置
- `text_*_rules.yaml`
  - 文本自然度、后处理、质量规则
- `app.yaml` / `logging.yaml` / `paths.yaml`
  - 基础应用、日志与路径配置

如果后续新增配置，优先继续放进这里，不再散落到根目录。
