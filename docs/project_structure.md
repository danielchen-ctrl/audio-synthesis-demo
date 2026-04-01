# Project Structure

```text
demo_app/
├─ AGENTS.md
├─ README.md
├─ server.py
├─ start_demo.bat
├─ .gitignore
├─ .cleanupignore
├─ config/
│  ├─ app.yaml
│  ├─ logging.yaml
│  ├─ paths.yaml
│  ├─ requirements.txt
│  ├─ project_guard_rules.yaml
│  ├─ runtime.yaml
│  ├─ runtime.pre_release.yaml
│  ├─ text_postprocess_rules.yaml
│  ├─ text_quality_rules.yaml
│  └─ text_naturalness_rules.yaml
├─ .github/
│  ├─ ISSUE_TEMPLATE/
│  └─ workflows/
├─ docs/
│  ├─ architecture.md
│  ├─ project-overview.md
│  ├─ development-workflow.md
│  ├─ release-process.md
│  ├─ project-board-workflow.md
│  ├─ github-project-setup-checklist.md
│  ├─ demo-startup-sharing-guide.md
│  ├─ project_self_healing_system.md
│  └─ project_structure.md
├─ scripts/
│  ├─ start_server.py
│  ├─ start_server.bat
│  ├─ run_pre_release_ci_gate.py
│  ├─ enforce_pre_release_ci_gate.py
│  ├─ run_multilingual_quality_checks.py
│  ├─ run_multilingual_quality_checks.bat
│  ├─ run_multilingual_pre_release_source_only_check.py
│  ├─ run_multilingual_pre_release_source_only_check.bat
│  ├─ run_pre_release_source_only_check.py
│  ├─ run_repo_daily_check.py
│  ├─ run_repo_daily_check.bat
│  ├─ clean_debug_artifacts.bat
│  ├─ release_tag.ps1
│  ├─ release_tag.sh
│  └─ maintenance/
│     ├─ cleanup_tool.py
│     └─ project_guard.py
├─ static/
│  ├─ index.html
│  ├─ app.js
│  └─ styles.css
├─ src/
│  └─ demo_app/
│     ├─ embedded_server_main.py
│     ├─ multilingual_naturalness.py
│     ├─ rule_loader.py
│     ├─ assets/
│     └─ domains/
├─ tests/
├─ tools/
├─ training/
├─ build/
└─ demo/
```

## Notes

- 当前真实可运行服务主实现是 `src/demo_app/embedded_server_main.py`。
- 根目录只保留 `server.py` 作为 Python 启动入口，`start_demo.bat` 作为 Windows 一键启动入口。
- `scripts/run_pre_release_ci_gate.py` 是当前正式的发布前门禁入口。
- `scripts/run_pre_release_source_only_check.py` 已降级为 deprecated wrapper，仅用于兼容旧调用方式。
- `src/demo_app/` 当前承载服务实现、多语言自然度处理、资源和领域数据。
- `runtime/`、`reports/`、`output/` 等运行产物目录只在本地使用时按需生成，默认不作为仓库核心结构保留。
- `demo/` 目录用于运行期样例与对话情景参数，保留其参数资产，历史输出可按需清理。
