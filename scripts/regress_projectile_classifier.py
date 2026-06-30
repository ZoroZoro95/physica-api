#!/usr/bin/env python3
"""Regression checks for projectile engine-case classification."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.projectile_engine.classifier import (  # noqa: E402
    classify_projectile_question,
    llm_engine_case_registry,
    validate_llm_classification,
)


def main() -> None:
    failures: list[str] = []

    registry = llm_engine_case_registry()
    engine_cases = {row["engine_case"] for row in registry}
    if "level_ground_range" not in engine_cases:
        failures.append("registry missing level_ground_range")
    if "perpendicular_launch_range_on_incline" not in engine_cases:
        failures.append("registry missing perpendicular_launch_range_on_incline")

    os.environ["PROJECTILE_CLASSIFIER"] = "rules"
    rules = classify_projectile_question(
        question_text="A projectile is fired with speed 25 m/s at 45 degrees. Calculate the distance covered on ground.",
        suggested_engine_case=None,
        givens=[],
        requested_quantity=None,
    )
    if rules.engine_case != "level_ground_range":
        failures.append(f"rules classifier engine_case={rules.engine_case}, expected level_ground_range")
    if "v0=25 m/s" not in rules.givens:
        failures.append(f"rules classifier missing v0 in givens: {rules.givens}")

    accepted = validate_llm_classification(
        {
            "engine_case": "level_ground_range",
            "requested_quantity": "horizontal_range",
            "givens": ["v0=25 m/s", "angle=45 deg"],
            "evidence": ["25 m/s", "45 degrees", "distance covered on ground"],
            "unsupported": False,
            "unsupported_reason": None,
        },
        original_givens=[],
        requested_quantity=None,
    )
    if accepted.classification is None:
        failures.append(f"valid LLM classification was rejected: {accepted.warnings}")
    elif accepted.classification.engine_case != "level_ground_range":
        failures.append(f"valid LLM classification engine_case={accepted.classification.engine_case}")

    invented = validate_llm_classification(
        {
            "engine_case": "made_up_projectile_case",
            "requested_quantity": "range",
            "givens": ["v0=25 m/s"],
            "evidence": ["range"],
            "unsupported": False,
        },
        original_givens=[],
        requested_quantity=None,
    )
    if invented.classification is not None:
        failures.append("invented LLM engine case was accepted")

    unsupported = validate_llm_classification(
        {
            "engine_case": None,
            "requested_quantity": "range",
            "givens": ["v0=40 m/s", "angle=30 deg"],
            "evidence": ["quadratic drag force", "exact horizontal range"],
            "unsupported": True,
            "unsupported_reason": "Quantitative quadratic drag is outside the registered cases.",
        },
        original_givens=[],
        requested_quantity=None,
    )
    if unsupported.classification is None or not unsupported.classification.unsupported:
        failures.append("unsupported LLM classification was not preserved")

    os.environ["PROJECTILE_CLASSIFIER"] = "hybrid"
    os.environ.pop("GROQ_API_KEY", None)
    os.environ.pop("GOOGLE_API_KEY", None)
    os.environ.pop("GEMINI_API_KEY", None)
    hybrid_no_key = classify_projectile_question(
        question_text="A projectile is fired with speed 25 m/s at 45 degrees. Calculate the horizontal range.",
        suggested_engine_case=None,
        givens=[],
        requested_quantity=None,
    )
    if hybrid_no_key.engine_case != "level_ground_range":
        failures.append(f"hybrid without provider did not fall back to rules: {hybrid_no_key.engine_case}")

    os.environ.pop("PROJECTILE_CLASSIFIER", None)
    os.environ["ENVIRONMENT"] = "production"
    production_default = classify_projectile_question(
        question_text="A projectile is fired with speed 25 m/s at 45 degrees. Calculate the horizontal range.",
        suggested_engine_case=None,
        givens=[],
        requested_quantity=None,
    )
    if production_default.engine_case != "level_ground_range":
        failures.append(f"production default classifier did not produce a valid mapping: {production_default.engine_case}")
    if not any("llm_classifier_unavailable" in warning for warning in production_default.warnings):
        failures.append(f"production default did not attempt hybrid fallback without provider: {production_default.warnings}")

    os.environ["PROJECTILE_CLASSIFIER"] = "rules"

    if failures:
        print("FAIL projectile classifier regressions")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print("PASS projectile classifier regressions")


if __name__ == "__main__":
    main()
