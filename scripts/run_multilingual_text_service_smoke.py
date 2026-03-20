from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_app.app_state import AppState
from demo_app.backend_common import GeneratedDialogue
from demo_app.text_service import generate_text


CASES = {
    "Japanese": {
        "lines": [
            ("Speaker 2", "はい。主に確認したいのは需求澄清です。"),
            ("Speaker 1", "技術面から見ると、ロールバックリスクが高いです。"),
            ("Speaker 3", "QA検証の観点では、受け入れ条件が明確になるまでNo-Goです。"),
            ("Speaker 1", "今は承認できません。"),
            ("Speaker 2", "スケジュールの圧力は理解していますが、この前提のまま進めることには同意できません。"),
            ("Speaker 3", "検証証跡がそろうまでブロックします。"),
        ],
        "must_contain": ["主に確認したいのは要件整理です。", "技術観点では、ロールバックリスクが高いです。"],
        "must_not_contain": ["需求澄清", "QA検証の観点では、"],
    },
    "Korean": {
        "lines": [
            ("Speaker 2", "네. 제가 주로 확인하고 싶은 것은 需求澄清입니다."),
            ("Speaker 1", "기술 측면에서 보면, 롤백 리스크가 높습니다."),
            ("Speaker 3", "QA 검증 관점에서 보면, 수용 기준이 명확해질 때까지 no-go입니다."),
            ("Speaker 1", "지금은 승인할 수 없습니다."),
            ("Speaker 2", "일정 압박은 이해하지만 현재 가정으로 바로 진행하는 데는 동의하기 어렵습니다."),
            ("Speaker 3", "검증 증거가 준비될 때까지 차단합니다."),
        ],
        "must_contain": ["제가 주로 확인하고 싶은 것은 요건 정리입니다.", "기술 관점에서 보면, 롤백 리스크가 높습니다."],
        "must_not_contain": ["需求澄清", "QA 검증 관점에서 보면,"],
    },
    "French": {
        "lines": [
            ("Speaker 2", "Oui. Je veux surtout clarifier 需求澄清."),
            ("Speaker 1", "Du point de vue technique, le risque de rollback reste élevé."),
            ("Speaker 3", "Du point de vue QA, c'est un no-go tant que les critères d'acceptation ne sont pas explicites."),
            ("Speaker 1", "Je ne peux pas encore valider cela."),
            ("Speaker 2", "Je comprends la pression du calendrier, mais je ne suis pas d'accord pour avancer sur cette hypothèse."),
            ("Speaker 3", "Je bloque tant que la preuve de validation n'est pas complète."),
        ],
        "must_contain": ["Je veux surtout clarifier clarification des exigences.", "Sur le plan technique, le risque de rollback reste élevé."],
        "must_not_contain": ["需求澄清", "Du point de vue QA,"],
    },
    "German": {
        "lines": [
            ("Speaker 2", "Ja. Ich möchte vor allem 需求澄清 klären."),
            ("Speaker 1", "Aus technischer Sicht, das Rollback-Risiko bleibt hoch."),
            ("Speaker 3", "Aus QA-Sicht, ist das ein no-go, solange die Abnahmekriterien nicht klar sind."),
            ("Speaker 1", "Ich kann das noch nicht freigeben."),
            ("Speaker 2", "Ich verstehe den Zeitdruck, aber ich stimme nicht zu, unter dieser Annahme weiterzugehen."),
            ("Speaker 3", "Ich blockiere das, bis der Validierungsnachweis vollständig ist."),
        ],
        "must_contain": ["Ich möchte vor allem Anforderungsabstimmung klären.", "Technisch betrachtet, das Rollback-Risiko bleibt hoch."],
        "must_not_contain": ["需求澄清", "Aus QA-Sicht,"],
    },
    "Spanish": {
        "lines": [
            ("Speaker 2", "Sí. Quiero sobre todo aclarar 需求澄清."),
            ("Speaker 1", "Desde el lado técnico, el riesgo de rollback sigue siendo alto."),
            ("Speaker 3", "Desde QA, esto es un no-go hasta que los criterios de aceptación estén claros."),
            ("Speaker 1", "No puedo aprobar esto todavía."),
            ("Speaker 2", "Entiendo la presión del calendario, pero no estoy de acuerdo con avanzar con esta hipótesis."),
            ("Speaker 3", "Bloqueo esto hasta que la evidencia de validación esté completa."),
        ],
        "must_contain": ["Quiero sobre todo aclarar aclaración de requisitos.", "Desde una perspectiva técnica, el riesgo de rollback sigue siendo alto."],
        "must_not_contain": ["需求澄清", "Desde QA,"],
    },
    "Portuguese": {
        "lines": [
            ("Speaker 2", "Sim. Quero principalmente esclarecer 需求澄清."),
            ("Speaker 1", "Do lado técnico, o risco de rollback continua alto."),
            ("Speaker 3", "Do lado de QA, isso é um no-go até que os critérios de aceitação estejam claros."),
            ("Speaker 1", "Ainda não posso aprovar isso."),
            ("Speaker 2", "Entendo a pressão do cronograma, mas não concordo em avançar com esta hipótese."),
            ("Speaker 3", "Eu bloqueio isso até que a evidência de validação esteja completa."),
        ],
        "must_contain": ["Quero principalmente esclarecer clareza de requisitos.", "Sob a perspectiva técnica, o risco de rollback continua alto."],
        "must_not_contain": ["需求澄清", "Do lado de QA,"],
    },
    "Cantonese": {
        "lines": [
            ("Speaker 2", "係。我主要想確認需求澄清。"),
            ("Speaker 1", "由技術角度睇，回滾風險仲係好高。"),
            ("Speaker 3", "由 QA 角度睇，驗收條件未講清楚之前都係No-Go。"),
            ("Speaker 1", "我而家未可以批。"),
            ("Speaker 2", "我明白進度壓力，但照而家個假設直接推進我唔同意。"),
            ("Speaker 3", "驗證證據未齊之前我會阻擋。"),
        ],
        "must_contain": ["我主要想確認需求釐清。", "從技術角度睇，回滾風險仲係好高。"],
        "must_not_contain": ["需求澄清", "由 QA 角度睇，"],
    },
}


class ScriptedMultilingualBackend:
    def __init__(self, language: str) -> None:
        self.language = language

    def validate_payload(self, payload):
        return dict(payload)

    def get_generation_config(self):
        return {"prefer_v2_for_scenes": ["meeting"]}

    def classify_scene_type(self, scenario, profile):
        return "meeting"

    def generate_v2(self, profile, scenario, core, people, target_len, language):
        return GeneratedDialogue(
            lines=list(CASES[self.language]["lines"]),
            debug_info={
                "from_v2": True,
                "is_from_v2": True,
                "generator_version": f"scripted_multilingual_{self.language.lower()}",
                "role_table": {"Speaker 1": "Backend", "Speaker 2": "PM", "Speaker 3": "QA"},
            },
        )

    def generate_fallback(self, profile, scenario, core, people, target_len, language):
        raise AssertionError("fallback should not be used in multilingual service smoke")

    def save_manifest(self, save_dir, dialogue_id, timestamp, basename, text_path, language, profile):
        return None


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_case(language: str, state: AppState) -> dict:
    payload = {
        "profile": {"job_function": "backend", "seniority": "senior"},
        "scenario": "meeting",
        "title": f"multilingual_smoke_{language.lower()}",
        "language": language,
        "audio_language": language,
        "people_count": 3,
        "word_count": 700,
        "core_content": "requirements clarification; rollback owner assigned; acceptance gate explicit; action items mapped to owners",
    }
    response = generate_text(payload, state, generator=ScriptedMultilingualBackend(language))
    debug = response.get("debug") or {}
    joined = " ".join(item["text"] for item in response.get("lines") or [])
    _assert(bool(response.get("ok")), f"text generation failed for {language}")
    _assert(debug.get("quality_gate", {}).get("passed") is True, f"quality gate failed for {language}")
    _assert(debug.get("from_v2") is True, f"from_v2 should be true for {language}")
    _assert(debug.get("text_backend") == "ScriptedMultilingualBackend", f"unexpected backend for {language}: {debug.get('text_backend')}")
    _assert(response.get("language") == language, f"language canonicalization mismatch for {language}: {response.get('language')}")
    for text in CASES[language]["must_contain"]:
        _assert(text in joined, f"missing expected text for {language}: {text}")
    for text in CASES[language]["must_not_contain"]:
        _assert(text not in joined, f"unexpected leakage for {language}: {text}")
    return {
        "language": language,
        "ok": True,
        "quality_passed": True,
        "basename": response.get("basename"),
        "text_backend": debug.get("text_backend"),
        "generator_version": debug.get("generator_version"),
    }


def main() -> int:
    state = AppState()
    results = [run_case(language, state) for language in CASES]
    print(json.dumps({"status": "ok", "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
