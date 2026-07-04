from __future__ import annotations

import re
from typing import Any

from ..models import EvaluationResult


FORBIDDEN_TEXT_PATTERNS: dict[str, tuple[str, ...]] = {
    "theta_arc": (r"\btheta\b", r"θ"),
    "u_cos_theta": (r"u[_ₓx]?\s*=\s*u\s*cos", r"u\s*cos\s*θ", r"uₓ\s*=\s*u\s*cos"),
    "u_sin_theta": (r"u[_ᵧy]?\s*=\s*u\s*sin", r"u\s*sin\s*θ", r"uᵧ\s*=\s*u\s*sin"),
    "angled_launch_vector": (r"launch angle", r"angle of projection", r"angled launch"),
}


def dedupe_strings(items: list[Any] | tuple[Any, ...]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))


def dedupe_labels(labels: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in labels:
        if not isinstance(raw, dict):
            continue
        label = dict(raw)
        target = str(label.get("target_id") or "")
        text = str(label.get("text") or label.get("math") or "")
        if not target or not text:
            continue
        key = (target, text)
        if key in seen:
            continue
        seen.add(key)
        out.append(label)
    return out


def normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(spec)
    normalized["must_show"] = dedupe_strings(list(normalized.get("must_show") or []))
    normalized["must_not_show"] = dedupe_strings(list(normalized.get("must_not_show") or []))
    normalized["labels"] = dedupe_labels(list(normalized.get("labels") or []))
    normalized["checks"] = [dict(item) for item in normalized.get("checks") or [] if isinstance(item, dict)]
    normalized["renderer_hints"] = dict(normalized.get("renderer_hints") or {})
    normalized["render_primitives"] = [dict(item) for item in normalized.get("render_primitives") or [] if isinstance(item, dict)]
    return normalized


def quantity_number(result: EvaluationResult, *keys: str) -> float | None:
    candidates: list[str] = []
    plan = result.equation_plan or {}
    candidates.extend(str(item) for item in plan.get("givens") or [])
    candidates.extend(str(item) for item in plan.get("knowns") or [])
    candidates.extend(str(item) for item in result.trace or [])
    text = "\n".join(candidates)
    for key in keys:
        escaped = re.escape(str(key))
        patterns = [
            rf"\b{escaped}\b\s*=\s*([-+]?[0-9]+(?:\.[0-9]+)?)",
            rf"\b{escaped}\b[^0-9+\-]{{0,24}}([-+]?[0-9]+(?:\.[0-9]+)?)\s*(?:m/s|m|s|deg|degree)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return float(match.group(1))
    return None


def format_number(value: float) -> str:
    if abs(value) >= 100:
        return f"{value:.0f}"
    return f"{round(value, 3):g}"
