# Project Structure

```text
demo_app/
├─ AGENTS.md
├─ README.md
├─ app.py
├─ server.py
├─ run.py
├─ embedded_server.py
├─ start_demo.bat
├─ requirements.txt
├─ project_guard.py
├─ project_guard_rules.yaml
├─ .gitignore
├─ .cleanupignore
├─ config/
│  ├─ app.yaml
│  ├─ logging.yaml
│  ├─ paths.yaml
│  ├─ runtime.yaml
│  ├─ runtime.pre_release.yaml
│  ├─ text_postprocess_rules.yaml
│  ├─ text_quality_rules.yaml
│  └─ text_naturalness_rules.yaml
├─ docs/
│  ├─ architecture.md
│  ├─ project-overview.md
│  ├─ development-workflow.md
│  ├─ release-process.md
│  ├─ project-board-workflow.md
│  ├─ github-project-setup-checklist.md
│  ├─ demo-startup-sharing-guide.md
│  ├─ project_self_healing_system.md
│  ├─ project_structure.md
│  └─ archive/
│     ├─ UPGRADE_CHANGELOG.md
│     └─ legacy-runtime-transition.md
├─ .github/
│  ├─ ISSUE_TEMPLATE/
│  └─ workflows/
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
├─ static/
│  ├─ index.html
│  ├─ app.js
│  └─ styles.css
├─ src/
│  └─ demo_app/
│     ├─ multilingual_naturalness.py
│     ├─ rule_loader.py
│     ├─ assets/
│     └─ domains/
├─ tests/
├─ tools/
├─ training/
├─ archive/
│  ├─ deprecated/
│  └─ failed_artifacts/
├─ build/
├─ dist/
├─ runtime/
├─ reports/
├─ output/
└─ demo/
```

## Notes

- 当前真实可运行服务主实现是 `embedded_server.py`。
- `server.py`、`run.py`、`app.py` 都是兼容入口，最终都会转到 `embedded_server.py`。
- `scripts/run_pre_release_ci_gate.py` 是当前正式的发布前门禁入口。
- `scripts/run_pre_release_source_only_check.py` 已降级为 deprecated wrapper，仅用于兼容旧调用方式。
- `src/demo_app/` 当前主要承载规则加载、多语言自然度处理、资源和领域数据；并不是完整服务实现目录。
- `build/`、`dist/`、`runtime/`、`reports/`、`output/`、`demo/` 都属于构建或运行产物目录，默认不应随意纳入版本管理。
- 历史 source-first 运行链说明已移动到 `docs/archive/legacy-runtime-transition.md`。
