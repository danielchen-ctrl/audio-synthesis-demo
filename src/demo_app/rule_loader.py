from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"


def clear_rule_cache() -> None:
    load_text_postprocess_rules.cache_clear()
    load_text_quality_rules.cache_clear()
    load_text_naturalness_rules.cache_clear()


def _load_yaml_mapping(filename: str) -> dict[str, Any]:
    path = CONFIG_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing rule file: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Rule file must contain a top-level mapping: {path}")
    return payload


@lru_cache(maxsize=1)
def load_text_postprocess_rules() -> dict[str, Any]:
    payload = _load_yaml_mapping("text_postprocess_rules.yaml")
    if not isinstance(payload.get("language_term_rewrites"), dict):
        raise ValueError("text_postprocess_rules.yaml: language_term_rewrites must be a mapping")
    return payload


@lru_cache(maxsize=1)
def load_text_quality_rules() -> dict[str, Any]:
    payload = _load_yaml_mapping("text_quality_rules.yaml")
    if not isinstance(payload.get("persona_rules"), dict):
        raise ValueError("text_quality_rules.yaml: persona_rules must be a mapping")
    return payload


@lru_cache(maxsize=1)
def load_text_naturalness_rules() -> dict[str, Any]:
    payload = _load_yaml_mapping("text_naturalness_rules.yaml")
    if not isinstance(payload.get("languages"), dict):
        raise ValueError("text_naturalness_rules.yaml: languages must be a mapping")
    return payload
