from __future__ import annotations

import argparse
import json
import os
import py_compile
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = ROOT / 'reports' / 'pre_release_gate'
MULTILINGUAL_REPORT_DIR = ROOT / 'reports' / 'multilingual_quality_checks'
RUNTIME_TEMP = ROOT / 'runtime' / 'temp' / 'pre_release_gate'

REQUIRED_PATHS = [
    ROOT / 'AGENTS.md',
    ROOT / 'README.md',
    ROOT / 'embedded_server.py',
    ROOT / 'server.py',
    ROOT / 'run.py',
    ROOT / 'start_demo.bat',
    ROOT / 'static' / 'index.html',
    ROOT / 'static' / 'app.js',
    ROOT / 'scripts' / 'start_server.py',
    ROOT / 'scripts' / 'run_repo_daily_check.py',
    ROOT / 'scripts' / 'run_multilingual_quality_checks.py',
    ROOT / '.github' / 'workflows' / 'ci.yml',
    ROOT / '.github' / 'workflows' / 'project-reminder.yml',
    ROOT / '.github' / 'workflows' / 'pre-release-gate.yml',
]

PYTHON_COMPILE_TARGETS = [
    ROOT / 'embedded_server.py',
    ROOT / 'server.py',
    ROOT / 'run.py',
    ROOT / 'scripts' / 'start_server.py',
    ROOT / 'scripts' / 'run_repo_daily_check.py',
    ROOT / 'scripts' / 'run_multilingual_quality_checks.py',
    ROOT / 'scripts' / 'run_multilingual_pre_release_source_only_check.py',
]

YAML_TARGETS = [
    ROOT / 'project_guard_rules.yaml',
    ROOT / '.github' / 'workflows' / 'ci.yml',
    ROOT / '.github' / 'workflows' / 'project-reminder.yml',
    ROOT / '.github' / 'workflows' / 'pre-release-gate.yml',
]

BUNDLE_TARGETS = [
    ROOT / 'build' / 'demo_app' / 'SceneDialogueDemo.exe',
    ROOT / 'build' / 'DialogDemo' / 'DialogDemo.pkg',
]


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding='utf-8',
    )


def _decode_json_stdout(stdout: str) -> dict[str, Any] | None:
    stdout = (stdout or '').strip()
    if not stdout:
        return None
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _find_free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def _check_required_paths() -> dict[str, Any]:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_PATHS if not path.exists()]
    return {
        'status': 'ok' if not missing else 'error',
        'missing': missing,
        'checked': [str(path.relative_to(ROOT)) for path in REQUIRED_PATHS],
    }


def _check_yaml_files() -> dict[str, Any]:
    parsed: list[str] = []
    failures: list[dict[str, str]] = []
    for path in YAML_TARGETS:
        if not path.exists():
            failures.append({'file': str(path.relative_to(ROOT)), 'error': 'file not found'})
            continue
        try:
            with path.open('r', encoding='utf-8') as fh:
                yaml.safe_load(fh)
            parsed.append(str(path.relative_to(ROOT)))
        except Exception as exc:
            failures.append({'file': str(path.relative_to(ROOT)), 'error': str(exc)})
    return {
        'status': 'ok' if not failures else 'error',
        'parsed': parsed,
        'failures': failures,
    }


def _check_python_compile() -> dict[str, Any]:
    compiled: list[str] = []
    failures: list[dict[str, str]] = []
    for path in PYTHON_COMPILE_TARGETS:
        if not path.exists():
            failures.append({'file': str(path.relative_to(ROOT)), 'error': 'file not found'})
            continue
        try:
            py_compile.compile(str(path), doraise=True)
            compiled.append(str(path.relative_to(ROOT)))
        except Exception as exc:
            failures.append({'file': str(path.relative_to(ROOT)), 'error': str(exc)})
    return {
        'status': 'ok' if not failures else 'error',
        'compiled': compiled,
        'failures': failures,
    }


def _run_repo_daily(report_dir: Path) -> dict[str, Any]:
    completed = _run([sys.executable, 'scripts/run_repo_daily_check.py', '--report-dir', str(report_dir)], cwd=ROOT)
    stdout = (completed.stdout or '').strip()
    stderr = (completed.stderr or '').strip()
    payload = _decode_json_stdout(stdout)
    return {
        'status': 'ok' if completed.returncode == 0 else 'error',
        'exit_code': completed.returncode,
        'stdout': stdout,
        'stderr': stderr,
        'payload': payload,
    }


def _run_multilingual_quality(report_dir: Path) -> dict[str, Any]:
    completed = _run([sys.executable, 'scripts/run_multilingual_quality_checks.py', '--report-dir', str(report_dir)], cwd=ROOT)
    stdout = (completed.stdout or '').strip()
    stderr = (completed.stderr or '').strip()
    payload = _decode_json_stdout(stdout)
    return {
        'status': 'ok' if completed.returncode == 0 else 'error',
        'exit_code': completed.returncode,
        'stdout': stdout,
        'stderr': stderr,
        'payload': payload,
    }


def _smoke_payload() -> dict[str, Any]:
    return {
        'title': 'ci_pre_release_smoke',
        'profile': {
            'job_function': '后端开发',
            'work_content': '系统建设',
            'seniority': '资深',
            'use_case': '内部会议',
        },
        'scenario': '内部会议',
        'core_content': '确认下周演示范围，明确负责人、风险项和回滚安排，确保文本可下载。',
        'people_count': 3,
        'word_count': 600,
    }


def _run_embedded_smoke() -> dict[str, Any]:
    bundle_status = {str(path.relative_to(ROOT)): path.exists() for path in BUNDLE_TARGETS}
    if not all(bundle_status.values()):
        return {
            'status': 'skipped',
            'reason': 'build bundles are not present in this checkout; full embedded smoke is skipped',
            'bundles': bundle_status,
        }

    RUNTIME_TEMP.mkdir(parents=True, exist_ok=True)
    port = _find_free_port()
    url = f'http://127.0.0.1:{port}'
    log_path = RUNTIME_TEMP / 'embedded_server_smoke.log'
    env = os.environ.copy()
    env['DEMO_APP_HOST'] = '127.0.0.1'
    env['DEMO_APP_PORT'] = str(port)
    proc = None
    with log_path.open('w', encoding='utf-8') as log_file:
        try:
            session = requests.Session()
            session.trust_env = False
            proc = subprocess.Popen(
                [sys.executable, 'scripts/start_server.py'],
                cwd=ROOT,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
            ready = False
            for _ in range(30):
                try:
                    response = session.get(f'{url}/', timeout=2)
                    if response.status_code == 200:
                        ready = True
                        break
                except Exception:
                    pass
                time.sleep(1)
            if not ready:
                return {
                    'status': 'error',
                    'reason': 'server did not become healthy within timeout',
                    'log_path': str(log_path),
                    'bundles': bundle_status,
                }

            info = session.get(f'{url}/api/server_info', timeout=5)
            info.raise_for_status()
            text_resp = session.post(f'{url}/api/generate_text', json=_smoke_payload(), timeout=120)
            text_resp.raise_for_status()
            text_payload = text_resp.json()
            if not text_payload.get('ok'):
                raise RuntimeError(text_payload.get('error') or 'generate_text returned ok=false')

            return {
                'status': 'ok',
                'bundles': bundle_status,
                'base_url': url + '/',
                'dialogue_id': text_payload.get('dialogue_id'),
                'text_path': text_payload.get('text_path'),
                'text_download_url': text_payload.get('text_download_url'),
                'log_path': str(log_path),
            }
        except Exception as exc:
            return {
                'status': 'error',
                'reason': str(exc),
                'bundles': bundle_status,
                'log_path': str(log_path),
            }
        finally:
            if proc is not None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        '# Pre-release CI Gate Report',
        '',
        f"- Generated at: {payload['generated_at']}",
        f"- Status: `{payload['status']}`",
        '',
        '## Checks',
        '',
        f"- Required paths: `{payload['checks']['required_paths']['status']}`",
        f"- YAML parse: `{payload['checks']['yaml_parse']['status']}`",
        f"- Python compile: `{payload['checks']['python_compile']['status']}`",
        f"- Repo daily check: `{payload['checks']['repo_daily_check']['status']}`",
        f"- Multilingual quality check: `{payload['checks']['multilingual_quality_check']['status']}`",
        f"- Embedded smoke: `{payload['checks']['embedded_demo_smoke']['status']}`",
        '',
    ]
    if payload.get('blocking_failures'):
        lines.extend(['## Blocking Failures', ''])
        for item in payload['blocking_failures']:
            lines.append(f"- {item}")
        lines.append('')
    if payload.get('warnings'):
        lines.extend(['## Warnings', ''])
        for item in payload['warnings']:
            lines.append(f"- {item}")
        lines.append('')

    multilingual = payload['checks']['multilingual_quality_check']
    if multilingual.get('payload'):
        summary = multilingual['payload'].get('summary', {})
        lines.extend([
            '## Multilingual Quality Summary',
            '',
            f"- Overall status: `{multilingual.get('status')}`",
            f"- Errors: `{summary.get('error_count', 0)}`",
            f"- Warnings: `{summary.get('warning_count', 0)}`",
            f"- Scripted languages: `{summary.get('scripted_language_count', 0)}`",
            f"- Source-only text languages: `{summary.get('source_text_language_count', 0)}`",
            f"- Source-only audio languages: `{summary.get('source_audio_language_count', 0)}`",
            '',
        ])

    smoke = payload['checks']['embedded_demo_smoke']
    if smoke.get('status') == 'ok':
        lines.extend([
            '## Embedded Smoke',
            '',
            f"- Base URL: `{smoke.get('base_url')}`",
            f"- Dialogue ID: `{smoke.get('dialogue_id')}`",
            f"- Log path: `{smoke.get('log_path')}`",
            '',
        ])
    elif smoke.get('status') == 'skipped':
        lines.extend([
            '## Embedded Smoke',
            '',
            f"- Skipped reason: `{smoke.get('reason')}`",
            '',
        ])
    return '\n'.join(lines) + '\n'


def _write_reports(payload: dict[str, Any], report_dir: Path) -> dict[str, str]:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = report_dir / f'pre_release_ci_gate_{timestamp}.json'
    md_path = report_dir / f'pre_release_ci_gate_{timestamp}.md'
    latest_json = report_dir / 'latest.json'
    latest_md = report_dir / 'latest.md'
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    md_text = _markdown_report(payload)
    json_path.write_text(json_text, encoding='utf-8')
    md_path.write_text(md_text, encoding='utf-8')
    latest_json.write_text(json_text, encoding='utf-8')
    latest_md.write_text(md_text, encoding='utf-8')
    return {
        'json': str(json_path),
        'markdown': str(md_path),
        'latest_json': str(latest_json),
        'latest_markdown': str(latest_md),
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Run pre-release CI gate aligned to the current embedded demo repository.')
    parser.add_argument('--report-dir', default=str(DEFAULT_REPORT_DIR), help='Directory for gate reports.')
    args = parser.parse_args(argv)

    required_paths = _check_required_paths()
    yaml_parse = _check_yaml_files()
    python_compile = _check_python_compile()
    repo_daily_check = _run_repo_daily(RUNTIME_TEMP / 'repo_daily_checks')
    multilingual_quality_check = _run_multilingual_quality(MULTILINGUAL_REPORT_DIR)
    embedded_demo_smoke = _run_embedded_smoke()

    blocking_failures: list[str] = []
    warnings: list[str] = []

    if required_paths['status'] != 'ok':
        blocking_failures.append(f"missing required paths: {', '.join(required_paths['missing'])}")
    if yaml_parse['status'] != 'ok':
        for item in yaml_parse['failures']:
            blocking_failures.append(f"yaml parse failed for {item['file']}: {item['error']}")
    if python_compile['status'] != 'ok':
        for item in python_compile['failures']:
            blocking_failures.append(f"python compile failed for {item['file']}: {item['error']}")
    if repo_daily_check['status'] != 'ok':
        blocking_failures.append('repo daily check failed')
    if multilingual_quality_check['status'] != 'ok':
        details = multilingual_quality_check.get('payload', {}).get('summary', {}) if multilingual_quality_check.get('payload') else {}
        blocking_failures.append(
            'multilingual quality check failed'
            + (f" (errors={details.get('error_count', 'unknown')}, warnings={details.get('warning_count', 'unknown')})" if details else '')
        )
    if embedded_demo_smoke['status'] == 'error':
        blocking_failures.append(f"embedded smoke failed: {embedded_demo_smoke.get('reason', 'unknown error')}")
    elif embedded_demo_smoke['status'] == 'skipped':
        warnings.append(embedded_demo_smoke.get('reason', 'embedded smoke skipped'))

    payload = {
        'entrypoint': 'run_pre_release_ci_gate',
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'checks': {
            'required_paths': required_paths,
            'yaml_parse': yaml_parse,
            'python_compile': python_compile,
            'repo_daily_check': repo_daily_check,
            'multilingual_quality_check': multilingual_quality_check,
            'embedded_demo_smoke': embedded_demo_smoke,
        },
        'blocking_failures': blocking_failures,
        'warnings': warnings,
        'status': 'ok' if not blocking_failures else 'error',
    }
    payload['report_paths'] = _write_reports(payload, Path(args.report_dir))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
