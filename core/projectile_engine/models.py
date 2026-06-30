from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


EvalStatus = Literal["passed", "failed", "unsupported", "needs_review"]


@dataclass(frozen=True)
class ManifestEntry:
    pdf_id: str
    question_number: int
    engine_case: str
    question_text: str
    options: list[str]
    expected_option_letter: str | None
    expected_answer: str | None
    knowns: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ManifestEntry":
        return cls(
            pdf_id=raw.get("pdf_id", "ad_hoc"),
            question_number=int(raw.get("question_number", 0)),
            engine_case=raw["engine_case"],
            question_text=raw["question_text"],
            options=list(raw.get("options") or []),
            expected_option_letter=raw.get("expected_option_letter"),
            expected_answer=raw.get("expected_answer"),
            knowns=list(raw.get("knowns") or []),
        )

    @property
    def label(self) -> str:
        return f"{self.pdf_id} Q{self.question_number:02d}"


@dataclass(frozen=True)
class EvaluationResult:
    label: str
    engine_case: str
    status: EvalStatus
    template_id: str | None = None
    template_confidence: float | None = None
    template_reason: str = ""
    template_warnings: list[str] = field(default_factory=list)
    diagram_valid: bool | None = None
    diagram_warnings: list[str] = field(default_factory=list)
    diagram_model: dict[str, Any] = field(default_factory=dict)
    expected_option_letter: str | None = None
    predicted_option_letter: str | None = None
    expected_answer: str | None = None
    computed_value: float | None = None
    computed_text: str | None = None
    reason: str = ""
    trace: list[str] = field(default_factory=list)
    equation_plan: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "passed"


@dataclass(frozen=True)
class ProblemTemplate:
    id: str
    title: str
    family: str
    engine_cases: set[str]
    accepted_quantities: set[str]
    required_known_keys: set[str] = field(default_factory=set)
    optional_known_keys: set[str] = field(default_factory=set)
    required_diagram_entities: set[str] = field(default_factory=set)
    diagram_kind: str = "none"
    solve_strategy: str = ""
    animation_requirements: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class TemplateMatch:
    template: ProblemTemplate
    confidence: float
    reason: str
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EquationStep:
    id: str
    title: str
    equation: str = ""
    substitution: str = ""
    explanation: str = ""
    focus_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EquationPlan:
    template_id: str
    engine_case: str
    goal: str
    givens: list[str] = field(default_factory=list)
    unknown: str = ""
    invariant: str = ""
    steps: list[EquationStep] = field(default_factory=list)
    final_answer: str = ""
    exam_takeaway: str = ""
