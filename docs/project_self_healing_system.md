# Project Self-Healing Organization System

## Purpose

`project_guard.py` is a repository hygiene guard for AI coding workflows. It continuously scans the project, classifies clutter, centralizes runtime artifacts, and keeps the directory layout within the expected engineering structure.

## Files

- `project_guard.py`: main guard tool
- `project_guard_rules.yaml`: rule configuration
- `scripts/run_project_guard.py`: Python launcher
- `scripts/run_project_guard.bat`: Windows launcher
- `cleanup_tool.py`: deprecated compatibility wrapper
- `.cleanupignore`: ignore list respected by the guard
- `project_guard_report.md`: generated health and action report

## Supported Modes

### Guard mode

```bash
python project_guard.py --dry-run
python project_guard.py --execute
```

This is the primary interface.

### Dry run

```bash
python project_guard.py --dry-run
```

Scans the repository, creates `project_guard_report.md`, and prints planned changes without mutating files.

### Execute

```bash
python project_guard.py --execute
```

Applies safe moves and deletions:
- moves logs to `runtime/logs/`
- archives suspicious temp/debug scripts
- deletes cache files
- archives failed/corrupted artifacts

Python source files are not deleted by default.

### Report only

```bash
python project_guard.py --report-only
```

Scans and emits the repository health report without planning filesystem mutations beyond the report itself.

### Watch mode

```bash
python project_guard.py --dry-run --watch
python project_guard.py --execute --watch
```

Watch mode polls the repository and reruns the guard after file changes. This is intended for long AI-assisted editing sessions where temporary scripts, logs, and cache artifacts accumulate quickly.

### Cleanup compatibility mode

```bash
python project_guard.py cleanup-compat --dry-run
python cleanup_tool.py --dry-run
```

Compatibility mode keeps the legacy cleanup-tool behavior:
- defaults the report to `cleanup_report.md`
- uses narrower default temp-script rules
- still runs on top of the unified `project_guard.py` implementation
- supports `--aggressive` to widen detection

`cleanup_tool.py` should no longer be used for new workflows. It remains only to avoid breaking existing commands and should be treated as deprecated.

## Rules

Rules are loaded from `project_guard_rules.yaml`.

Key sections:
- `target_directories`
- `targets`
- `suspicious_scripts`
- `failed_artifact_patterns`
- `cache_patterns`
- `protected`
- `root_whitelist`
- `watch`

## Ignore Handling

`.cleanupignore` works like a safety override:
- ignored files are skipped during classification and planning
- use it to protect project-specific wrappers or experimental areas

## Safety Model

- archive instead of delete when uncertain
- never delete `.py` source files by default
- keep the tool idempotent by skipping already-organized files
- create missing target directories automatically
- write a report on every run

## Current Expected Structure

```text
src/demo_app/
config/
runtime/
scripts/
tools/debug/
docs/archive/
archive/deprecated/
archive/failed_artifacts/
reports/
output/
```

## Typical AI Workflow

1. Run `python project_guard.py --dry-run` before a major refactor.
2. Run `python project_guard.py --execute` after temporary probes and logs accumulate.
3. Use `python project_guard.py --dry-run --watch` during long autonomous coding sessions.
4. Review `project_guard_report.md` for root clutter and suspicious script findings.
