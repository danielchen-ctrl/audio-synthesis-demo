# Project Structure

```text
demo_app/
├─ README.md
├─ requirements.txt
├─ run.py
├─ app.py
├─ server.py
├─ sitecustomize.py
├─ config/
│  ├─ app.yaml
│  ├─ logging.yaml
│  ├─ paths.yaml
│  ├─ runtime.yaml
│  ├─ text_postprocess_rules.yaml
│  └─ text_quality_rules.yaml
├─ docs/
│  ├─ architecture.md
│  ├─ project_structure.md
│  └─ archive/
│     └─ UPGRADE_CHANGELOG.md
├─ scripts/
│  ├─ run_multilingual_pre_release_source_only_check.bat
│  ├─ run_multilingual_pre_release_source_only_check.py
│  ├─ run_multilingual_quality_checks.bat
│  ├─ run_multilingual_quality_checks.py
│  ├─ run_multilingual_text_service_smoke.bat
│  ├─ run_multilingual_text_service_smoke.py
│  ├─ run_pre_release_source_only_check.bat
│  ├─ run_pre_release_source_only_check.py
│  ├─ start_server.bat
│  ├─ start_server.py
│  └─ maintenance/
│     ├─ clean_logs.py
│     └─ cleanup_workspace.py
├─ runtime/
│  ├─ cache/
│  │  └─ voice_cache/
│  ├─ logs/
│  └─ temp/
├─ src/
│  └─ demo_app/
│     ├─ __init__.py
│     ├─ app.py
│     ├─ server.py
│     ├─ app_state.py
│     ├─ backend_common.py
│     ├─ bundle_loader.py
│     ├─ configuration.py
│     ├─ language_utils.py
│     ├─ rule_loader.py
│     ├─ runtime_bootstrap.py
│     ├─ runtime_bridge.py
│     ├─ runtime_patches.py
│     ├─ runtime_patches_legacy.py
│     ├─ legacy_fallback_policy.py
│     ├─ legacy_runtime_gateway.py
│     ├─ legacy_runtime_adapters.py
│     ├─ resource_path_utils.py
│     ├─ pack_adapter.py
│     ├─ template_retriever.py
│     ├─ ssml_builder.py
│     ├─ audio_alignment.py
│     ├─ audio_catalog.py
│     ├─ audio_engine.py
│     ├─ audio_backends.py
│     ├─ audio_service.py
│     ├─ core_content_normalizer.py
│     ├─ dialogue_rules.py
│     ├─ fallback_text_generator.py
│     ├─ text_backends.py
│     ├─ text_postprocess.py
│     ├─ text_quality.py
│     ├─ text_runtime_policy.py
│     ├─ text_service.py
│     ├─ v2_compat.py
│     ├─ dialogue_*.py
│     ├─ assets/
│     │  ├─ audio/
│     │  ├─ static/
│     │  ├─ template_bank/
│     │  └─ template_data_pack/
│     └─ domains/
│        ├─ domain_kb/
│        ├─ payment/
│        └─ quality_upgrade/
├─ output/
│  └─ training/
│     ├─ full/
│     ├─ mvp/
│     └─ smoke/
├─ reports/
├─ demo/
├─ archive/
│  ├─ deprecated/
│  │  ├─ debug_scripts/
│  │  └─ legacy_code/
│  └─ failed_artifacts/
├─ tests/
├─ tools/
├─ training/
├─ build/
├─ dist/
└─ bin/
```

## Notes

- Root entry points are retained for compatibility.
- Core code now lives under `src/demo_app/`.
- `src/demo_app/server.py` is now the main Tornado server implementation, not just a wrapper.
- `src/demo_app/runtime_patches.py` is deprecated and only preserved as a lazy compatibility import.
- multilingual text quality rules now live in `config/text_postprocess_rules.yaml` and `config/text_quality_rules.yaml`.
- `src/demo_app/legacy_runtime_gateway.py` is the remaining runtime-access choke point for bundle fallback.
- `scripts/run_multilingual_quality_checks.py` is the main daily multilingual quality entry point.
- Logs and cache are centralized under `runtime/`.
- Durable generated training data moved from root `training_outputs_*` to `output/training/*`.
- Historical and broken server artifacts were archived under `archive/deprecated/legacy_code/`.
