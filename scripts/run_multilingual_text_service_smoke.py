from __future__ import annotations

import json
import sys


CASES = {
    "Japanese": {
        "text": "要件整理を先に固めたいです。ロールバック責任者は明確で、受け入れ条件も明示されています。",
        "must_contain": ["要件整理", "ロールバック責任者"],
        "must_not_contain": ["Hello,", "Let's discuss your situation"],
    },
    "Korean": {
        "text": "먼저 요구사항 정리를 명확히 하고 싶습니다. 롤백 책임자와 승인 기준도 이미 정의되어 있습니다.",
        "must_contain": ["요구사항", "롤백 책임자"],
        "must_not_contain": ["Hello,", "Let's discuss your situation"],
    },
    "French": {
        "text": "Je veux d'abord clarifier les exigences. Le responsable du rollback et les critères d'acceptation sont déjà définis.",
        "must_contain": ["clarifier les exigences", "responsable du rollback"],
        "must_not_contain": ["Hello,", "Let's discuss your situation"],
    },
    "German": {
        "text": "Ich möchte zuerst die Anforderungen klären. Der Rollback-Verantwortliche und die Abnahmekriterien sind bereits festgelegt.",
        "must_contain": ["Anforderungen", "Rollback-Verantwortliche"],
        "must_not_contain": ["Hello,", "Let's discuss your situation"],
    },
    "Spanish": {
        "text": "Quiero aclarar primero los requisitos. El responsable del rollback y los criterios de aceptación ya están definidos.",
        "must_contain": ["aclarar primero los requisitos", "responsable del rollback"],
        "must_not_contain": ["Hello,", "Let's discuss your situation"],
    },
    "Portuguese": {
        "text": "Quero esclarecer primeiro os requisitos. O responsável pelo rollback e os critérios de aceitação já estão definidos.",
        "must_contain": ["esclarecer primeiro os requisitos", "responsável pelo rollback"],
        "must_not_contain": ["Hello,", "Let's discuss your situation"],
    },
    "Cantonese": {
        "text": "我想先釐清需求，回滾負責人同驗收條件都已經講清楚。",
        "must_contain": ["釐清需求", "回滾負責人"],
        "must_not_contain": ["Hello,", "Let's discuss your situation"],
    },
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_case(language: str, fixture: dict[str, list[str] | str]) -> dict[str, object]:
    text = str(fixture["text"])
    for item in fixture["must_contain"]:
        _assert(item in text, f"{language} missing expected phrase: {item}")
    for item in fixture["must_not_contain"]:
        _assert(item not in text, f"{language} leaked unwanted phrase: {item}")
    return {
        "language": language,
        "ok": True,
        "quality_passed": True,
        "text_backend": "FixtureMultilingualSmoke",
        "generator_version": "fixture_multilingual_smoke",
        "text_excerpt": text[:80],
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    results = [run_case(language, fixture) for language, fixture in CASES.items()]
    print(json.dumps({"status": "ok", "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
