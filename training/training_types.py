from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


DialogueLines = List[Tuple[str, str]]


@dataclass
class TrainingTask:
    task_id: str
    stage: str
    profile: Dict[str, Any]
    scenario: str
    core_content: str
    language: str
    people_count: int
    word_count: int
    seed: int
    meta: Dict[str, Any] = field(default_factory=dict)
    source_format: str = "normalized"


@dataclass
class ValidationFinding:
    code: str
    severity: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoreReport:
    passed: bool
    score: float
    max_score: float
    metrics: Dict[str, Any]
    findings: List[ValidationFinding] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "max_score": self.max_score,
            "metrics": self.metrics,
            "findings": [
                {
                    "code": finding.code,
                    "severity": finding.severity,
                    "message": finding.message,
                    "details": finding.details,
                }
                for finding in self.findings
            ],
        }


@dataclass
class ExecutionResult:
    task: TrainingTask
    lines: DialogueLines
    debug_info: Dict[str, Any]
    score_report: ScoreReport
    output_paths: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None
