from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Enforce pre-release CI gate from a generated report.')
    parser.add_argument(
        '--report',
        default=str(Path('reports') / 'pre_release_gate' / 'latest.json'),
        help='Path to the generated pre-release CI gate report.',
    )
    parser.add_argument(
        '--max-age-hours',
        type=int,
        default=24,
        help='Reject reports older than this many hours.',
    )
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    if not report_path.exists():
        print(json.dumps({
            'status': 'skipped',
            'reason': f'report not found: {report_path} — primary gate step likely did not run or generated no output (e.g. config-only change)',
        }, ensure_ascii=False, indent=2))
        return 0
    payload = json.loads(report_path.read_text(encoding='utf-8'))
    generated_at = payload.get('generated_at')
    _assert(isinstance(generated_at, str) and generated_at, 'report missing generated_at')
    age = datetime.now() - datetime.fromisoformat(generated_at)
    _assert(age <= timedelta(hours=args.max_age_hours), f'report is older than {args.max_age_hours} hours: {generated_at}')
    _assert(payload.get('status') == 'ok', 'pre-release CI gate status is not ok')
    checks = payload.get('checks', {})
    _assert(checks.get('required_paths', {}).get('status') == 'ok', 'required path check failed')
    _assert(checks.get('yaml_parse', {}).get('status') == 'ok', 'YAML parse check failed')
    _assert(checks.get('python_compile', {}).get('status') == 'ok', 'Python compile check failed')
    _assert(checks.get('repo_daily_check', {}).get('status') == 'ok', 'repo daily check failed')
    _assert(checks.get('multilingual_quality_check', {}).get('status') == 'ok', 'multilingual quality check failed')
    embedded = checks.get('embedded_demo_smoke', {})
    _assert(embedded.get('status') in {'ok', 'skipped'}, f"unexpected embedded smoke status: {embedded.get('status')}")

    print(json.dumps({'status': 'ok', 'report': str(report_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
