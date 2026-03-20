# Architecture

## Layers

1. Entry wrappers
- Root `run.py`, `server.py`, and `app.py` keep legacy startup commands working.
- `scripts/start_server.py` and `scripts/start_server.bat` are operational entry points.
- `scripts/run_pre_release_source_only_check.py` and `.bat` are source-only regression entry points.
- `scripts/run_multilingual_quality_checks.py` and `.bat` are the daily multilingual quality/regression entry points.
- `scripts/enforce_multilingual_quality_gate.py` turns the generated report into a pass/fail gate for CI or scheduled execution.

2. Application package
- `src/demo_app/` holds the application-facing modules.
- `src/demo_app/server.py` is the primary Tornado server implementation.
- `src/demo_app/text_service.py` and `src/demo_app/audio_service.py` own the main text/audio request flows.
- `src/demo_app/text_backends.py` and `src/demo_app/audio_backends.py` select source-first backends with explicit legacy fallback policy.
- `src/demo_app/legacy_runtime_gateway.py` is the only remaining runtime-access gateway used by bundle fallback paths.
- `src/demo_app/runtime_bridge.py` and `src/demo_app/runtime_bootstrap.py` isolate the remaining bundled runtime access.
- `src/demo_app/runtime_patches.py` is deprecated and only preserves legacy import compatibility.
- `src/demo_app/runtime_patches.py` now exposes only a minimal public API surface and hides legacy helper internals.

3. Assets and domain data
- `src/demo_app/assets/` contains `static/`, `audio/`, `template_bank/`, and `template_data_pack/`.
- `src/demo_app/domains/` contains `domain_kb/`, `payment/`, and `quality_upgrade/`.

4. Configuration
- `src/demo_app/configuration.py` loads YAML files from `config/` and ensures runtime directories exist.
- `src/demo_app/rule_loader.py` loads text postprocess and quality rules from YAML so multilingual rule tables are data-driven.

5. Runtime artifacts
- `runtime/logs/`: service and startup logs
- `runtime/cache/`: caches such as `voice_cache`
- `runtime/temp/`: temporary outputs for tests and maintenance tasks
- `output/`: durable generated training corpora and other produced data
- `reports/`: validation/debug reports
- `reports/multilingual_quality_checks/`: fixed JSON/Markdown daily multilingual regression reports

## Server Startup Flow

```text
run.py / server.py / scripts/start_server.py
  -> demo_app.server.main()
  -> demo_app.server.make_app()
  -> text_service.generate_text() / audio_service.generate_audio()
  -> source backends and source engines
  -> runtime_bridge.get_runtime_server() only if a legacy fallback path is needed
  -> Tornado listens on configured port
```

## Path Resolution

- Project-relative paths are centralized in `config/paths.yaml`.
- `src/demo_app/resource_path_utils.py` resolves static assets, ffmpeg, demo output, and config files from the centralized config.
- `sitecustomize.py` keeps legacy absolute-style imports working after the `src/` move.

## Current Technical Debt

- The demo still keeps bundle-backed fallback adapters as a safety net for text/audio generation.
- `src/demo_app/runtime_patches_legacy.py` is retained only for deprecated compatibility paths and should continue to shrink over time.
