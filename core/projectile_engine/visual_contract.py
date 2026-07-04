from __future__ import annotations

import re
from typing import Any

from .models import EvaluationResult
from .visual_director import default_visual_director
from .visuals.types import SCHEMA_VERSION
from .visuals.utils import (
    FORBIDDEN_TEXT_PATTERNS,
    dedupe_labels,
    format_number,
    normalize_spec,
    quantity_number,
)


def build_beat_visual_spec(
    *,
    result: EvaluationResult,
    step_id: str,
    title: str = "",
    text: str = "",
    visual_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return default_visual_director().build_beat_visual_spec(
        result=result,
        step_id=step_id,
        title=title,
        text=text,
        visual_plan=visual_plan,
    )


def attach_beat_visual_spec(
    *,
    result: EvaluationResult,
    step_id: str,
    title: str,
    text: str,
    visual_plan: dict[str, Any],
) -> dict[str, Any]:
    return default_visual_director().apply_to_plan(
        result=result,
        step_id=step_id,
        title=title,
        text=text,
        visual_plan=visual_plan,
    )


def contract_visible_vectors(existing: list[Any], spec: dict[str, Any]) -> list[str]:
    return default_visual_director().visible_vectors(existing, spec)


def contract_visible_ids(existing: list[Any], spec: dict[str, Any]) -> list[str]:
    return default_visual_director().visible_ids(existing, spec)


def contract_visual_action(existing: str, spec: dict[str, Any]) -> str:
    return default_visual_director().visual_action(existing, spec)


def merge_contract_labels(existing: list[Any], contract_labels: list[Any]) -> list[dict[str, Any]]:
    return default_visual_director().merge_labels(existing, contract_labels)


def validate_beat_visual_spec(spec: dict[str, Any], *, text: str = "") -> list[str]:
    errors: list[str] = []
    if not isinstance(spec, dict) or int(spec.get("schema_version") or 0) < SCHEMA_VERSION:
        return ["beat_visual_spec schema_version is required"]
    for key in ("family", "beat", "must_show", "must_not_show", "labels", "renderer_hints"):
        if key not in spec:
            errors.append(f"beat_visual_spec.{key} is required")
    labels = spec.get("labels") or []
    if not isinstance(labels, list):
        errors.append("beat_visual_spec.labels must be a list")
    for forbidden in spec.get("must_not_show") or []:
        for pattern in FORBIDDEN_TEXT_PATTERNS.get(str(forbidden), ()):
            if text and re.search(pattern, text, re.I):
                errors.append(f"beat_visual_spec forbids {forbidden}, but text contains {pattern}")
    if spec.get("family") == "horizontal_launch" and spec.get("beat") == "initial_components":
        label_text = " ".join(str(label.get("text") or "") for label in labels if isinstance(label, dict)).lower()
        if "u_y = 0" not in label_text and "uᵧ = 0" not in label_text:
            errors.append("horizontal_launch initial_components must label u_y = 0")
    return errors


def normalize_beat_visual_spec(spec: dict[str, Any]) -> dict[str, Any]:
    return normalize_spec(spec)


def _dedupe_labels(labels: list[Any]) -> list[dict[str, Any]]:
    return dedupe_labels(labels)


def _visual_state_for_contract_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return default_visual_director().visual_state_for_plan(plan)


__all__ = [
    "FORBIDDEN_TEXT_PATTERNS",
    "SCHEMA_VERSION",
    "attach_beat_visual_spec",
    "build_beat_visual_spec",
    "contract_visible_ids",
    "contract_visible_vectors",
    "contract_visual_action",
    "format_number",
    "merge_contract_labels",
    "normalize_beat_visual_spec",
    "quantity_number",
    "validate_beat_visual_spec",
]
