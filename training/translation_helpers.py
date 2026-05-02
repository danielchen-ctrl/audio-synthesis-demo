from __future__ import annotations

import importlib
import re
from typing import Callable, Dict, Tuple


TranslatorFn = Callable[[str, str], Tuple[str, bool]]


LANGUAGE_CODE_MAP: Dict[str, str] = {
    "中文": "zh",
    "英语": "en",
    "日语": "ja",
    "韩语": "ko",
    "法语": "fr",
    "德语": "de",
    "西班牙语": "es",
    "葡萄牙语": "pt",
    "粤语": "yue",
}

LANGUAGE_DISPLAY_MAP: Dict[str, Dict[str, str]] = {
    "英语": {
        "scenario": "Scenario: A professional business discussion conducted in English. Keep the conversation practical, decision-oriented, and easy to follow.",
        "core": "Core requirements: include concrete facts, assigned actions, open risks, dependencies, and a clear next-step summary in English.",
    },
    "日语": {
        "scenario": "シナリオ：日本語で進行する業務対話。実務的で、意思決定と次のアクションが明確な会話にすること。",
        "core": "必須要件：具体的な事実、担当アクション、未解決リスク、依存関係、次の進め方を日本語で明確に含めること。",
    },
    "韩语": {
        "scenario": "시나리오: 한국어로 진행되는 업무 대화입니다. 실무적이고 의사결정과 다음 행동이 분명해야 합니다.",
        "core": "핵심 요구사항: 구체적인 사실, 담당 액션, 남은 리스크, 의존 관계, 다음 단계 요약을 한국어로 포함하세요.",
    },
    "法语": {
        "scenario": "Scenario: une discussion professionnelle en francais, concrete et orientee vers les decisions et les prochaines actions.",
        "core": "Exigences essentielles: inclure des faits concrets, des actions assignees, des risques ouverts, des dependances et un resume clair des prochaines etapes en francais.",
    },
    "德语": {
        "scenario": "Szenario: ein berufliches Gesprach auf Deutsch, praxisnah und klar auf Entscheidungen sowie nachste Schritte ausgerichtet.",
        "core": "Kernanforderungen: konkrete Fakten, zugewiesene Aktionen, offene Risiken, Abhangigkeiten und eine klare Zusammenfassung der nachsten Schritte auf Deutsch.",
    },
    "西班牙语": {
        "scenario": "Escenario: una conversacion profesional en espanol, practica y enfocada en decisiones y siguientes pasos.",
        "core": "Requisitos clave: incluir hechos concretos, acciones asignadas, riesgos abiertos, dependencias y un resumen claro de los siguientes pasos en espanol.",
    },
    "葡萄牙语": {
        "scenario": "Cenario: uma conversa profissional em portugues, pratica e orientada para decisoes e proximos passos.",
        "core": "Requisitos centrais: incluir fatos concretos, acoes atribuidas, riscos em aberto, dependencias e um resumo claro dos proximos passos em portugues.",
    },
    "粤语": {
        "scenario": "情景：用廣東話進行嘅業務對話，要實際、清晰，重點放喺決策同下一步安排。",
        "core": "核心要求：用廣東話講清楚具體事實、責任分工、未解決風險、依賴關係，同埋下一步總結。",
    },
}

PROFESSION_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "英语": {
        "医疗健康": "Healthcare",
        "人力资源与招聘": "HR and Recruitment",
        "娱乐/媒体": "Entertainment and Media",
        "建筑与工程行业": "Construction and Engineering",
        "汽车行业": "Automotive",
        "咨询/专业服务": "Consulting and Professional Services",
        "法律服务": "Legal Services",
        "金融/投资": "Finance and Investment",
        "零售行业": "Retail",
        "保险行业": "Insurance",
        "房地产": "Real Estate",
        "人工智能/科技": "AI and Technology",
        "制造业": "Manufacturing",
        "医疗服务供应商": "Healthcare Services",
        "招聘与人才获取": "Talent Acquisition",
        "内容制作": "Content Production",
        "工程规划与施工": "Engineering Planning and Delivery",
        "整车制造": "Vehicle Manufacturing",
        "管理咨询": "Management Consulting",
        "法务/合规": "Legal and Compliance",
        "投资银行": "Investment Banking",
        "零售运营": "Retail Operations",
        "保险销售与理赔": "Insurance Sales and Claims",
        "房地产开发": "Real Estate Development",
        "产品研发": "Product Development",
        "生产运营": "Production Operations",
        "综合管理": "General Management",
        "高级职员": "Senior Staff",
        "经理": "Manager",
        "主管": "Supervisor",
        "总监": "Director",
        "C层/创始人": "Founder or C-Level",
        "客户洽谈": "Client Discussion",
    },
    "日语": {
        "医疗健康": "医療・ヘルスケア",
        "人力资源与招聘": "人事・採用",
        "娱乐/媒体": "エンタメ・メディア",
        "建筑与工程行业": "建設・エンジニアリング",
        "汽车行业": "自動車",
        "咨询/专业服务": "コンサルティング・専門サービス",
        "法律服务": "法務サービス",
        "金融/投资": "金融・投資",
        "零售行业": "小売",
        "保险行业": "保険",
        "房地产": "不動産",
        "人工智能/科技": "AI・テクノロジー",
        "制造业": "製造業",
        "医疗服务供应商": "医療サービス",
        "招聘与人才获取": "採用・人材獲得",
        "内容制作": "コンテンツ制作",
        "工程规划与施工": "計画・施工",
        "整车制造": "完成車製造",
        "管理咨询": "経営コンサルティング",
        "法务/合规": "法務・コンプライアンス",
        "投资银行": "投資銀行",
        "零售运营": "小売運営",
        "保险销售与理赔": "保険営業・保険金対応",
        "房地产开发": "不動産開発",
        "产品研发": "製品開発",
        "生产运营": "生産運営",
        "综合管理": "総合管理",
        "高级职员": "シニアスタッフ",
        "经理": "マネージャー",
        "主管": "スーパーバイザー",
        "总监": "ディレクター",
        "C层/创始人": "経営層・創業者",
        "客户洽谈": "顧客折衝",
    },
}


def _count_chinese_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def chinese_ratio(text: str) -> float:
    stripped = "".join(ch for ch in text if not ch.isspace())
    if not stripped:
        return 0.0
    return _count_chinese_chars(stripped) / len(stripped)


def _is_translation_usable(source_text: str, translated_text: str, target_language: str) -> bool:
    normalized = translated_text.strip()
    if not normalized or normalized == source_text.strip():
        return False
    if target_language != "中文" and chinese_ratio(normalized) > 0.35:
        return False
    return True


def _runtime_translate_fn() -> Callable[[str, str, bool], Tuple[str, object]] | None:
    candidates = (
        ("server", "translate_text"),
        ("demo_app.embedded_server_main", "translate_text"),
    )
    for module_name, attr in candidates:
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        translate_fn = getattr(module, attr, None)
        if callable(translate_fn):
            return translate_fn
    return None


def _fallback_language_text(original_text: str, target_language: str, field: str) -> str:
    if target_language == "中文":
        return original_text
    localized = LANGUAGE_DISPLAY_MAP.get(target_language) or LANGUAGE_DISPLAY_MAP["英语"]
    prompt = localized["scenario" if field == "scenario" else "core"]
    return prompt


def translate_text_best_effort(text: str, target_language: str, field: str) -> Tuple[str, bool]:
    if target_language == "中文":
        return text, False

    translate_fn = _runtime_translate_fn()
    if translate_fn is not None:
        try:
            translated_text, _ = translate_fn(text, target_language, protect_tags=False)
            if _is_translation_usable(text, translated_text, target_language):
                return translated_text, False
        except Exception:
            pass

    return _fallback_language_text(text, target_language, field), True


def translate_scenario_and_core(text_scenario: str, text_core: str, target_language: str) -> Tuple[str, str, bool]:
    translated_scenario, scenario_fallback = translate_text_best_effort(text_scenario, target_language, "scenario")
    translated_core, core_fallback = translate_text_best_effort(text_core, target_language, "core")
    return translated_scenario, translated_core, scenario_fallback or core_fallback


def localize_profile_value(value: str, target_language: str) -> str:
    if target_language == "中文":
        return value
    translated = PROFESSION_TRANSLATIONS.get(target_language, {}).get(value)
    if translated:
        return translated
    english = PROFESSION_TRANSLATIONS["英语"].get(value)
    return english or value
