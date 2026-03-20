from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_app.rule_loader import clear_rule_cache, load_text_postprocess_rules, load_text_quality_rules


def main() -> int:
    clear_rule_cache()
    postprocess = load_text_postprocess_rules()
    quality = load_text_quality_rules()
    payload = {
        "status": "ok",
        "validated": {
            "text_postprocess_rules": {
                "languages": sorted((postprocess.get("language_term_rewrites") or {}).keys()),
                "english_opening_variants": len(postprocess.get("english_opening_variants") or []),
            },
            "text_quality_rules": {
                "persona_roles": sorted((quality.get("persona_rules") or {}).keys()),
                "conflict_locales": sorted((quality.get("conflict_keywords_by_locale") or {}).keys()),
            },
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
