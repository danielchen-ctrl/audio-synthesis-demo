from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_app.audio_catalog import audio_locale, voices_for_language
from demo_app.text_postprocess import evaluate_facts_coverage, polish_english_lines, sanitize_generated_lines
from demo_app.text_quality import apply_conflict_budget_boost, apply_persona_boost, pick_conflict_language, run_quality_gate


class TextProcessingRefactorTests(unittest.TestCase):
    def test_sanitize_generated_lines_replaces_pack_section_with_fact_summary(self) -> None:
        lines = [("Speaker 1", "Core Facts:"), ("Speaker 1", "- criteria defined"), ("Speaker 2", "We can proceed.")]
        cleaned, cleanup = sanitize_generated_lines(lines, ["criteria defined", "owner assigned"], "English")
        self.assertTrue(any("Let me anchor on the key facts:" in text for _, text in cleaned))
        self.assertFalse(any(text == "Core Facts:" for _, text in cleaned))
        self.assertTrue(cleanup)

    def test_sanitize_generated_lines_strips_inline_pack_section(self) -> None:
        lines = [("Speaker 1", "Specifically, Core Facts: - criteria defined - owner assigned"), ("Speaker 2", "We can proceed.")]
        cleaned, cleanup = sanitize_generated_lines(lines, ["criteria defined", "owner assigned"], "English")
        self.assertIn("Let me anchor on the key facts:", cleaned[0][1])
        self.assertNotIn("Core Facts:", cleaned[0][1])
        self.assertTrue(any(item["reason"] == "inline_pack_section" for item in cleanup))

    def test_polish_english_lines_removes_chinese_name_and_term_leakage(self) -> None:
        lines = [
            ("Speaker 1", "Hello, I'm 张昊, 项目负责人. Let's discuss your situation regarding meeting."),
            ("Speaker 2", "From the product goal and schedule side, Yes, 张昊. I mainly want to understand 需求澄清."),
        ]
        polished, rewrites = polish_english_lines(lines, "English")
        self.assertEqual(polished[0][1], "Hello, I am the project lead. Let us discuss this meeting.")
        self.assertEqual(polished[1][1], "From the product goal and schedule side, I mainly want to clarify the requirements and scope.")
        self.assertEqual(len(rewrites), 2)

    def test_polish_english_lines_removes_generic_filler_from_substantive_lines(self) -> None:
        lines = [
            ("Speaker 1", "But I cannot sign off yet because the core issue is still open: From the engineering side, the implementation risk and rollback cost are still high. Hello, I am the project lead. Let us discuss this meeting."),
            ("Speaker 2", "However, I still see release risk here, and I cannot approve it before rollback and acceptance evidence are clear: Could you provide more details?"),
            ("Speaker 3", "I hear the plan, but that risk cannot be accepted as-is: What's the specific amount or number?"),
            ("Speaker 4", "Actually, I will not sign off unless the entry gate and fallback actions are explicit: From QA validation, the acceptance gate and no-go criteria are still not explicit. To add, regarding timeline, we need X days. This is confirmed."),
            ("Speaker 5", "Actually, I will not sign off unless the entry gate and fallback actions are explicit: From QA validation, the acceptance gate and no-go criteria are still not explicit. To add, regarding timeline, we need Y items. Already prepared."),
            ("Speaker 6", "Actually, I will not sign off unless the entry gate and fallback actions are explicit: From QA validation, the acceptance gate and no-go criteria are still not explicit. To add, regarding procedures, we need X days. This is confirmed."),
            ("Speaker 7", "I understand the schedule pressure, but I do not agree with moving forward on the current assumption: From the product goal and schedule side, I mainly want to clarify the requirements and scope."),
            ("Speaker 8", "The problem is not closed yet, so I disagree with treating this item as resolved."),
            ("Speaker 9", "Yes. I mainly want to clarify the requirements and scope."),
            ("Speaker 10", "Based on your situation, I recommend this approach. Specifically, Let me anchor on the key facts: criteria defined; owner assigned."),
            ("Speaker 11", "Please note that there are risks involved, including uncertainties."),
            ("Speaker 12", "To add, regarding timeline, we need Y items. I will coordinate."),
        ]
        polished, rewrites = polish_english_lines(lines, "English")
        self.assertEqual(polished[0][1], "I cannot sign off yet because the core issue is still open. From the engineering side, the implementation risk and rollback cost are still high.")
        self.assertEqual(polished[1][1], "I still see release risk here, and I cannot approve it until rollback and acceptance evidence are clear.")
        self.assertEqual(polished[2][1], "I understand the plan, but that risk cannot be accepted as-is. I need the exact threshold and impact.")
        self.assertEqual(polished[3][1], "I am not ready to sign off until the entry gate and fallback actions are explicit. From QA validation, the acceptance gate and no-go criteria are still not explicit. We still need a concrete timeline and named owner.")
        self.assertEqual(polished[4][1], "I cannot approve this until the entry gate and fallback actions are explicit. From QA validation, the acceptance gate and no-go criteria are still not explicit. We still need a concrete timeline and named owner.")
        self.assertEqual(polished[5][1], "I cannot approve this until the entry gate and fallback actions are explicit. From QA validation, the acceptance gate and no-go criteria are still not explicit. We still need a concrete timeline and named owner.")
        self.assertEqual(polished[6][1], "I see the schedule pressure, but I do not think the current assumption is ready to move forward. From the product and schedule side, I mainly want to clarify the requirements and scope.")
        self.assertEqual(polished[7][1], "This issue is still open, so I do not see it as resolved.")
        self.assertEqual(polished[8][1], "I mainly want to clarify the requirements and scope.")
        self.assertEqual(polished[9][1], "Let me anchor on the key facts: criteria defined; owner assigned.")
        self.assertEqual(polished[10][1], "The main risk is still unresolved implementation and rollback exposure.")
        self.assertEqual(polished[11][1], "We still need a concrete timeline and named owner.")
        self.assertGreaterEqual(len(rewrites), 12)

    def test_polish_english_lines_applies_role_aware_tone(self) -> None:
        lines = [
            ("Speaker 1", "I cannot sign off yet because the core issue is still open. From the engineering side, the implementation risk and rollback cost are still high."),
            ("Speaker 2", "I understand the schedule pressure, but I do not think the current assumption is ready to move forward. From the product and schedule side, I mainly want to clarify the requirements and scope."),
            ("Speaker 3", "I cannot sign off until the entry gate and fallback actions are explicit. From QA validation, the acceptance gate and no-go criteria are still not explicit."),
        ]
        polished, _ = polish_english_lines(lines, "English", {"Speaker 1": "Backend", "Speaker 2": "PM", "Speaker 3": "QA"})
        self.assertIn("From an engineering perspective,", polished[0][1])
        self.assertIn("From a product and delivery perspective,", polished[1][1])
        self.assertIn("From a QA standpoint,", polished[2][1])

    def test_polish_japanese_lines_remove_leakage_and_soften_tone(self) -> None:
        lines = [
            ("Speaker 1", "はい。主に確認したいのは需求澄清です。"),
            ("Speaker 2", "実際には、受け入れ条件とフォールバック対応が明確になるまで承認できません：具体的な期限が必要です。"),
            ("Speaker 3", "技術面から見ると、ロールバックリスクが高いです。"),
        ]
        polished, rewrites = polish_english_lines(lines, "Japanese", {"Speaker 3": "Backend"})
        self.assertEqual(polished[0][1], "主に確認したいのは要件整理です。")
        self.assertEqual(polished[1][1], "受け入れ条件とフォールバック対応が明確になるまで承認できません。具体的な期限が必要です。")
        self.assertEqual(polished[2][1], "技術観点では、ロールバックリスクが高いです。")
        self.assertTrue(rewrites)

    def test_polish_korean_lines_remove_leakage_and_soften_tone(self) -> None:
        lines = [
            ("Speaker 1", "네. 제가 주로 확인하고 싶은 것은 需求澄清입니다."),
            ("Speaker 2", "실제로는 진입 기준과 폴백 조치가 명확해지기 전까지 승인할 수 없습니다: 구체적인 일정이 필요합니다."),
            ("Speaker 3", "기술 측면에서 보면, 롤백 리스크가 높습니다."),
        ]
        polished, rewrites = polish_english_lines(lines, "Korean", {"Speaker 3": "Backend"})
        self.assertEqual(polished[0][1], "제가 주로 확인하고 싶은 것은 요건 정리입니다.")
        self.assertEqual(polished[1][1], "진입 기준과 폴백 조치가 명확해지기 전까지는 승인할 수 없습니다. 구체적인 일정이 필요합니다.")
        self.assertEqual(polished[2][1], "기술 관점에서 보면, 롤백 리스크가 높습니다.")
        self.assertTrue(rewrites)

    def test_polish_french_lines_remove_leakage_and_soften_tone(self) -> None:
        lines = [
            ("Speaker 1", "Oui. Je veux surtout clarifier 需求澄清."),
            ("Speaker 2", "Mais je ne peux pas encore valider cela, car le point central n'est pas encore résolu : il manque encore le rollback."),
            ("Speaker 3", "Du point de vue technique, le risque de rollback reste élevé."),
        ]
        polished, rewrites = polish_english_lines(lines, "French", {"Speaker 3": "Backend"})
        self.assertEqual(polished[0][1], "Je veux surtout clarifier clarification des exigences.")
        self.assertEqual(polished[1][1], "Je ne peux pas encore valider cela, car le point central n'est pas encore résolu. il manque encore le rollback.")
        self.assertEqual(polished[2][1], "Sur le plan technique, le risque de rollback reste élevé.")
        self.assertTrue(rewrites)

    def test_polish_german_lines_remove_leakage_and_soften_tone(self) -> None:
        lines = [
            ("Speaker 1", "Ja. Ich möchte vor allem 需求澄清 klären."),
            ("Speaker 2", "Aber ich kann das noch nicht freigeben, weil der Kernpunkt noch offen ist: Der Rollback-Pfad fehlt noch."),
            ("Speaker 3", "Aus technischer Sicht, das Rollback-Risiko bleibt hoch."),
        ]
        polished, rewrites = polish_english_lines(lines, "German", {"Speaker 3": "Backend"})
        self.assertEqual(polished[0][1], "Ich möchte vor allem Anforderungsabstimmung klären.")
        self.assertEqual(polished[1][1], "Ich kann das noch nicht freigeben, weil der Kernpunkt noch offen ist. Der Rollback-Pfad fehlt noch.")
        self.assertEqual(polished[2][1], "Technisch betrachtet, das Rollback-Risiko bleibt hoch.")
        self.assertTrue(rewrites)

    def test_polish_spanish_lines_remove_leakage_and_soften_tone(self) -> None:
        lines = [
            ("Speaker 1", "Sí. Quiero sobre todo aclarar 需求澄清."),
            ("Speaker 2", "Pero no puedo aprobar esto todavía porque el punto central sigue abierto: todavía falta el rollback."),
            ("Speaker 3", "Desde el lado técnico, el riesgo de rollback sigue siendo alto."),
        ]
        polished, rewrites = polish_english_lines(lines, "Spanish", {"Speaker 3": "Backend"})
        self.assertEqual(polished[0][1], "Quiero sobre todo aclarar aclaración de requisitos.")
        self.assertEqual(polished[1][1], "No puedo aprobar esto todavía porque el punto central sigue abierto. todavía falta el rollback.")
        self.assertEqual(polished[2][1], "Desde una perspectiva técnica, el riesgo de rollback sigue siendo alto.")
        self.assertTrue(rewrites)

    def test_polish_portuguese_lines_remove_leakage_and_soften_tone(self) -> None:
        lines = [
            ("Speaker 1", "Sim. Quero principalmente esclarecer 需求澄清."),
            ("Speaker 2", "Mas ainda não posso aprovar isso porque o ponto central continua em aberto: ainda falta o rollback."),
            ("Speaker 3", "Do lado técnico, o risco de rollback continua alto."),
        ]
        polished, rewrites = polish_english_lines(lines, "Portuguese", {"Speaker 3": "Backend"})
        self.assertEqual(polished[0][1], "Quero principalmente esclarecer clareza de requisitos.")
        self.assertEqual(polished[1][1], "Ainda não posso aprovar isso porque o ponto central continua em aberto. ainda falta o rollback.")
        self.assertEqual(polished[2][1], "Sob a perspectiva técnica, o risco de rollback continua alto.")
        self.assertTrue(rewrites)

    def test_polish_cantonese_lines_remove_leakage_and_soften_tone(self) -> None:
        lines = [
            ("Speaker 1", "係。我主要想確認需求澄清。"),
            ("Speaker 2", "實際上，準入條件同 fallback 動作未明確之前我都唔會批：仲需要一個具體時間表。"),
            ("Speaker 3", "由技術角度睇，回滾風險仲係好高。"),
        ]
        polished, rewrites = polish_english_lines(lines, "Cantonese", {"Speaker 3": "Backend"})
        self.assertEqual(polished[0][1], "我主要想確認需求釐清。")
        self.assertEqual(polished[1][1], "準入條件同 fallback 動作未明確之前，我唔會批。仲需要一個具體時間表。")
        self.assertEqual(polished[2][1], "從技術角度睇，回滾風險仲係好高。")
        self.assertTrue(rewrites)

    def test_polish_spanish_and_portuguese_lines_strip_english_residue(self) -> None:
        cases = [
            (
                "Spanish",
                [
                    ("Speaker 1", "Hello, I'm 王睿, responsable del proyecto. Let's discuss your situation regarding meeting."),
                    ("Speaker 2", "Yes, 王睿. I mainly want to understand aclaración de requisitos."),
                    ("Speaker 3", "Please note that there are risks involved, including delays."),
                ],
                [
                    "Hola, soy el responsable del proyecto. Hablemos de esta reunión.",
                    "Quiero sobre todo aclarar aclaración de requisitos.",
                    "El riesgo principal sigue siendo la incertidumbre sobre la implementación y el rollback.",
                ],
            ),
            (
                "Portuguese",
                [
                    ("Speaker 1", "Hello, I'm 刘畅, responsável pelo projeto. Let's discuss your situation regarding review."),
                    ("Speaker 2", "Yes, 刘畅. I mainly want to understand clareza de requisitos."),
                    ("Speaker 3", "Please note that there are risks involved, including delays."),
                ],
                [
                    "Olá, sou o responsável pelo projeto. Vamos discutir esta reunião.",
                    "Quero principalmente esclarecer clareza de requisitos.",
                    "O principal risco continua sendo a incerteza sobre implementação e rollback.",
                ],
            ),
        ]
        for language, lines, expected in cases:
            with self.subTest(language=language):
                polished, rewrites = polish_english_lines(lines, language)
                self.assertEqual([item[1] for item in polished], expected)
                self.assertTrue(rewrites)

    def test_polish_japanese_korean_french_german_lines_strip_english_residue(self) -> None:
        cases = [
            (
                "Japanese",
                [
                    ("Speaker 1", "Hello, I'm 冯浩, プロジェクト責任者. Let's discuss your situation regarding meeting."),
                    ("Speaker 2", "Yes, 冯浩. I mainly want to understand 要件整理."),
                    ("Speaker 3", "Please note that there are risks involved, including complications."),
                ],
                [
                    "こんにちは、私はプロジェクト責任者です。今回の話を整理しましょう。",
                    "主に確認したいのは要件整理です。",
                    "主なリスクは、実装とロールバックの不確実性がまだ残っていることです。",
                ],
            ),
            (
                "Korean",
                [
                    ("Speaker 1", "Hello, I'm 郑越, 프로젝트 책임자. Let's discuss your situation regarding review."),
                    ("Speaker 2", "Yes, 郑越. I mainly want to understand 요건 정리."),
                    ("Speaker 3", "Please note that there are risks involved, including uncertainties."),
                ],
                [
                    "안녕하세요, 저는 프로젝트 책임자입니다. 이번 이야기를 정리해 보겠습니다.",
                    "제가 주로 확인하고 싶은 것은 요건 정리입니다.",
                    "핵심 리스크는 구현과 롤백 불확실성이 아직 남아 있다는 점입니다.",
                ],
            ),
            (
                "French",
                [
                    ("Speaker 1", "Hello, I'm 许言, responsable du projet. Let's discuss your situation regarding meeting."),
                    ("Speaker 2", "Yes, 许言. I mainly want to understand clarification des exigences."),
                    ("Speaker 3", "Please note that there are risks involved, including complications."),
                ],
                [
                    "Bonjour, je suis le responsable du projet. Regardons ce sujet ensemble.",
                    "Je veux surtout clarifier clarification des exigences.",
                    "Le risque principal reste l'incertitude sur l'implémentation et le rollback.",
                ],
            ),
            (
                "German",
                [
                    ("Speaker 1", "Hello, I'm 冯浩, Projektverantwortliche. Let's discuss your situation regarding review."),
                    ("Speaker 2", "Yes, 冯浩. I mainly want to understand Anforderungsabstimmung."),
                    ("Speaker 3", "Please note that there are risks involved, including complications."),
                ],
                [
                    "Hallo, ich bin für das Projekt verantwortlich. Lassen Sie uns dieses Thema durchgehen.",
                    "Ich möchte vor allem Anforderungsabstimmung klären.",
                    "Das Hauptrisiko liegt weiterhin in der Umsetzungs- und Rollback-Unsicherheit.",
                ],
            ),
        ]
        for language, lines, expected in cases:
            with self.subTest(language=language):
                polished, rewrites = polish_english_lines(lines, language)
                self.assertEqual([item[1] for item in polished], expected)
                self.assertTrue(rewrites)

    def test_polish_cantonese_lines_convert_mainland_templates(self) -> None:
        lines = [
            ("Speaker 1", "先对齐这次consultation的目标：我们要在下一个发布窗口前把结论定下来。"),
            ("Speaker 2", "监控和执行路径是：告警阈值和监控看板。回退方案按人工回滾到上一稳定版本处理。"),
        ]
        polished, rewrites = polish_english_lines(lines, "Cantonese")
        self.assertEqual(polished[0][1], "我哋先對齊今次 consultation 嘅目標：要喺下一個發布窗口前定好結論。")
        self.assertEqual(polished[1][1], "監控同執行路徑係：告警閾值同監控看板，因為要及早發現風險，再手動回滾到上一個穩定版本。")
        self.assertTrue(rewrites)

    def test_audio_catalog_supports_new_languages(self) -> None:
        self.assertEqual(audio_locale("Japanese"), "ja-JP")
        self.assertEqual(audio_locale("Korean"), "ko-KR")
        self.assertEqual(audio_locale("French"), "fr-FR")
        self.assertEqual(audio_locale("German"), "de-DE")
        self.assertEqual(audio_locale("Spanish"), "es-ES")
        self.assertEqual(audio_locale("Portuguese"), "pt-BR")
        self.assertEqual(audio_locale("Cantonese"), "zh-HK")
        self.assertTrue(all(voice.startswith("ko-KR") for voice in voices_for_language("Korean")["male"]))
        self.assertTrue(all(voice.startswith("fr-FR") for voice in voices_for_language("French")["female"]))
        self.assertTrue(all(voice.startswith("de-DE") for voice in voices_for_language("German")["female"]))
        self.assertTrue(all(voice.startswith("es-ES") for voice in voices_for_language("Spanish")["male"]))
        self.assertTrue(all(voice.startswith("pt-BR") for voice in voices_for_language("Portuguese")["female"]))
        self.assertTrue(all(voice.startswith("zh-HK") for voice in voices_for_language("Cantonese")["male"]))

    def test_evaluate_facts_coverage_counts_matches(self) -> None:
        coverage = evaluate_facts_coverage([("Speaker 1", "criteria defined and owner assigned")], ["criteria defined", "owner assigned", "rollback ready"])
        self.assertEqual(coverage["covered_count"], 2)
        self.assertEqual(coverage["total_facts"], 3)
        self.assertIn("rollback ready", coverage["missing_facts"])

    def test_apply_conflict_budget_boost_injects_prefixes(self) -> None:
        lines = [
            ("Speaker 1", "Can we ship now?"),
            ("Speaker 2", "I disagree because the rollback path is not ready."),
            ("Speaker 1", "Why are you still blocking this release?"),
            ("Speaker 2", "We can probably move fast."),
            ("Speaker 1", "That assumption still worries me."),
            ("Speaker 2", "Can you clarify the blocking point?"),
        ]
        boosted, boosts = apply_conflict_budget_boost(lines, "English")
        self.assertTrue(boosts)
        self.assertNotEqual(boosted, lines)
        self.assertGreaterEqual(len({item["line_idx"] // 3 for item in boosts}), 2)

    def test_apply_conflict_budget_boost_uses_second_alternating_window_when_first_is_only_scored_window(self) -> None:
        lines = [
            ("Speaker 1", "Hello, I am the project lead. Let us discuss this meeting."),
            ("Speaker 2", "I mainly want to clarify the requirements and scope."),
            ("Speaker 1", "I cannot sign off yet because the core issue is still open."),
            ("Speaker 2", "I understand the schedule pressure, but I do not agree with moving forward on the current assumption."),
            ("Speaker 1", "I still see release risk here, and I cannot approve it until rollback and acceptance evidence are clear."),
            ("Speaker 3", "We still need a concrete timeline and named owner."),
            ("Speaker 1", "Let me anchor on the key facts: criteria defined; owner assigned."),
            ("Speaker 1", "The main risk is still unresolved implementation and rollback exposure."),
            ("Speaker 3", "We still need a concrete timeline and named owner."),
        ]
        boosted, boosts = apply_conflict_budget_boost(lines, "English")
        self.assertTrue(boosts)
        tail = boosted[-3:]
        self.assertEqual(tail[0][0], "Speaker 2")
        self.assertEqual(tail[1][0], "Speaker 1")
        self.assertEqual(tail[2][0], "Speaker 3")
        self.assertIn("The problem is not closed yet", tail[0][1])
        self.assertIn("I hear the plan", tail[1][1])
        self.assertIn("Actually, I will not sign off", tail[2][1])

    def test_apply_persona_boost_adds_missing_role_prefixes(self) -> None:
        lines = [("Speaker 1", "We should move quickly."), ("Speaker 2", "I will coordinate the release."), ("Speaker 3", "We need one more pass.")]
        boosted, boosts = apply_persona_boost(lines, {"Speaker 1": "PM", "Speaker 2": "Backend", "Speaker 3": "QA"}, "English")
        self.assertTrue(boosts)
        self.assertIn("QA validation", boosted[2][1])

    def test_run_quality_gate_detects_two_conflict_windows(self) -> None:
        lines = [
            ("Speaker 1", "But I cannot approve this release yet."),
            ("Speaker 2", "I disagree because the current assumption is still risky."),
            ("Speaker 1", "However, rollback evidence is still missing."),
            ("Speaker 2", "The problem is not closed yet, so I still object."),
            ("Speaker 1", "I hear the proposal, but the risk is not acceptable."),
            ("Speaker 2", "Actually, I will not sign off until the entry gate is explicit."),
        ]
        result = run_quality_gate({}, lines, {"role_table": {"Speaker 1": "Backend", "Speaker 2": "PM"}}, "English")
        self.assertTrue(result["report"]["conflict_budget"]["passed"])

    def test_run_quality_gate_supports_english_persona_keywords(self) -> None:
        lines = [
            ("Speaker 1", "From the engineering side, the implementation risk and rollback cost are still high."),
            ("Speaker 2", "From the product goal and schedule side, the release goal is still valid."),
            ("Speaker 3", "From QA validation, the acceptance gate is still a no-go until the entry criteria are explicit."),
            ("Speaker 1", "However, I still cannot approve the release until rollback is proven."),
            ("Speaker 2", "But the schedule pressure is real, and I still need a clear trade-off."),
            ("Speaker 3", "I must block this until validation evidence is complete."),
        ]
        result = run_quality_gate({}, lines, {"role_table": {"Speaker 1": "Backend", "Speaker 2": "PM", "Speaker 3": "QA"}}, "English")
        self.assertTrue(result["report"]["persona_validator"]["passed"])

    def test_run_quality_gate_corrects_weak_role_table_using_persona_content(self) -> None:
        lines = [
            ("Speaker 1", "From the engineering side, the implementation risk and rollback cost are still high."),
            ("Speaker 2", "From the product goal and schedule side, the release goal is still valid."),
            ("Speaker 3", "From QA validation, the acceptance gate is still a no-go until the entry criteria are explicit. I must block this until validation evidence is complete."),
        ]
        result = run_quality_gate(
            {"job_function": "backend"},
            lines,
            {"role_table": {"Speaker 1": "Backend", "Speaker 2": "PM", "Speaker 3": "PM"}},
            "English",
        )
        self.assertEqual(result["role_mapping"]["Speaker 3"], "QA")

    def test_run_quality_gate_supports_multilingual_persona_and_conflicts(self) -> None:
        cases = [
            (
                "Japanese",
                [
                    ("Speaker 1", "技術観点では、実装コストとロールバックリスクが高いです。"),
                    ("Speaker 2", "スケジュールの圧力は理解していますが、この前提のまま進めることには同意できません。"),
                    ("Speaker 3", "QA観点では、受け入れ条件が明確になるまでNo-Goです。"),
                    ("Speaker 1", "それでも今は承認できません。"),
                    ("Speaker 2", "この問題はまだ未解決です。"),
                    ("Speaker 3", "検証証跡がそろうまでブロックします。"),
                ],
            ),
            (
                "Korean",
                [
                    ("Speaker 1", "기술 관점에서 보면 구현 비용과 롤백 리스크가 높습니다."),
                    ("Speaker 2", "일정 압박은 이해하지만 현재 가정으로 바로 진행하는 데는 동의하기 어렵습니다."),
                    ("Speaker 3", "QA 관점에서는 수용 기준이 명확해질 때까지 no-go입니다."),
                    ("Speaker 1", "그래도 지금은 승인할 수 없습니다."),
                    ("Speaker 2", "이 문제는 아직 열려 있습니다."),
                    ("Speaker 3", "검증 증거가 준비될 때까지 차단합니다."),
                ],
            ),
            (
                "French",
                [
                    ("Speaker 1", "Sur le plan technique, le coût d'implémentation et le risque de rollback restent élevés."),
                    ("Speaker 2", "Je comprends la pression du calendrier, mais je ne suis pas d'accord pour avancer sur cette hypothèse."),
                    ("Speaker 3", "Côté QA, c'est un no-go tant que les critères d'acceptation ne sont pas explicites."),
                    ("Speaker 1", "Je ne peux pas encore valider cela."),
                    ("Speaker 2", "Ce point est encore ouvert."),
                    ("Speaker 3", "Je bloque tant que la preuve de validation n'est pas complète."),
                ],
            ),
            (
                "German",
                [
                    ("Speaker 1", "Technisch betrachtet sind Implementierungskosten und Rollback-Risiko weiterhin hoch."),
                    ("Speaker 2", "Ich verstehe den Zeitdruck, aber ich stimme nicht zu, unter dieser Annahme weiterzugehen."),
                    ("Speaker 3", "Aus QA-Perspektive ist das ein no-go, solange die Abnahmekriterien nicht klar sind."),
                    ("Speaker 1", "Ich kann das noch nicht freigeben."),
                    ("Speaker 2", "Dieser Punkt ist noch offen."),
                    ("Speaker 3", "Ich blockiere das, bis der Validierungsnachweis vollständig ist."),
                ],
            ),
            (
                "Spanish",
                [
                    ("Speaker 1", "Desde una perspectiva técnica, el coste de implementación y el riesgo de rollback siguen siendo altos."),
                    ("Speaker 2", "Entiendo la presión del calendario, pero no estoy de acuerdo con avanzar con esta hipótesis."),
                    ("Speaker 3", "Desde la perspectiva de QA, esto es un no-go hasta que los criterios de aceptación estén claros."),
                    ("Speaker 1", "No puedo aprobar esto todavía."),
                    ("Speaker 2", "Este punto sigue abierto."),
                    ("Speaker 3", "Bloqueo esto hasta que la evidencia de validación esté completa."),
                ],
            ),
            (
                "Portuguese",
                [
                    ("Speaker 1", "Sob a perspectiva técnica, o custo de implementação e o risco de rollback continuam altos."),
                    ("Speaker 2", "Entendo a pressão do cronograma, mas não concordo em avançar com esta hipótese."),
                    ("Speaker 3", "Na perspectiva de QA, isso é um no-go até que os critérios de aceitação estejam claros."),
                    ("Speaker 1", "Ainda não posso aprovar isso."),
                    ("Speaker 2", "Esse ponto ainda está em aberto."),
                    ("Speaker 3", "Eu bloqueio isso até que a evidência de validação esteja completa."),
                ],
            ),
            (
                "Cantonese",
                [
                    ("Speaker 1", "從技術角度睇，實現成本同回滾風險都仲係高。"),
                    ("Speaker 2", "我明白進度壓力，但照而家個假設直接推進我唔同意。"),
                    ("Speaker 3", "從QA角度睇，驗收條件未講清楚之前都係No-Go。"),
                    ("Speaker 1", "我而家未可以批。"),
                    ("Speaker 2", "呢個問題仲未收口。"),
                    ("Speaker 3", "驗證證據未齊之前我會阻擋。"),
                ],
            ),
        ]
        for language, lines in cases:
            with self.subTest(language=language):
                result = run_quality_gate({}, lines, {"role_table": {"Speaker 1": "Backend", "Speaker 2": "PM", "Speaker 3": "QA"}}, language)
                self.assertTrue(result["report"]["persona_validator"]["passed"])
                self.assertTrue(result["report"]["conflict_budget"]["passed"])

    def test_pick_conflict_language_detects_spanish_portuguese_and_cantonese(self) -> None:
        spanish_lines = [("Speaker 1", "Yo no puedo aprobar esto todavía, y el riesgo sigue abierto.")]
        portuguese_lines = [("Speaker 1", "Eu não posso aprovar isso agora, e o risco ainda está em aberto.")]
        cantonese_lines = [("Speaker 1", "我而家未可以批，呢個問題仲未收口。")]
        self.assertEqual(pick_conflict_language("", spanish_lines), "es")
        self.assertEqual(pick_conflict_language("", portuguese_lines), "pt")
        self.assertEqual(pick_conflict_language("", cantonese_lines), "yue")


if __name__ == "__main__":
    unittest.main()
