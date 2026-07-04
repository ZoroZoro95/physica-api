from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..models import EvaluationResult


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class BeatContext:
    result: EvaluationResult
    step_id: str
    title: str = ""
    text: str = ""
    visual_plan: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VisualSelection:
    family: str
    source: str
    beat: str | None = None
    confidence: float = 1.0
    warnings: tuple[str, ...] = ()


class VisualFamilyPack(Protocol):
    family: str
    engine_cases: tuple[str, ...]
    forbidden_global: tuple[str, ...]

    def describe(self) -> dict[str, Any]:
        ...

    def matches(self, result: EvaluationResult) -> bool:
        ...

    def build_spec(self, context: BeatContext) -> dict[str, Any]:
        ...

    def visible_vectors(self, existing: list[Any], spec: dict[str, Any]) -> list[str]:
        ...

    def visible_ids(self, existing: list[Any], spec: dict[str, Any]) -> list[str]:
        ...

    def visual_action(self, existing: str, spec: dict[str, Any]) -> str:
        ...
