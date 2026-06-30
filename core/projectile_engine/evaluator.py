from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from .cases import SOLVERS, canonical_engine_case, unsupported
from .classifier import classify_projectile_question
from .diagram import normalize_diagram_for_template, validate_diagram_for_template
from .models import EvaluationResult, ManifestEntry
from .planner import build_equation_plan
from .templates import classify_template


def evaluate_manifest_entry(raw_entry: dict) -> EvaluationResult:
    if raw_entry.get("engine_case"):
        raw_entry = {**raw_entry, "engine_case": canonical_engine_case(raw_entry.get("engine_case"))}
    entry = ManifestEntry.from_dict(raw_entry)
    template_match = classify_template(
        question_text=entry.question_text,
        engine_case=entry.engine_case,
        requested_quantity=raw_entry.get("requested_quantity"),
        givens=entry.knowns,
    )
    solver = SOLVERS.get(entry.engine_case)
    if solver is None:
        return _with_template_metadata(unsupported(entry), template_match)
    try:
        result = solver(entry)
        result = replace(result, equation_plan=build_equation_plan(result, entry.knowns))
        return _with_template_metadata(result, template_match)
    except Exception as exc:
        return _with_template_metadata(
            EvaluationResult(
                label=entry.label,
                engine_case=entry.engine_case,
                status="failed",
                expected_option_letter=entry.expected_option_letter,
                expected_answer=entry.expected_answer,
                reason=f"solver error: {type(exc).__name__}: {exc}",
            ),
            template_match,
        )


def solve_ad_hoc_question(
    *,
    question_text: str,
    engine_case: str | None,
    options: list[str],
    givens: list[str],
    requested_quantity: str | None = None,
    diagram: Any = None,
    require_diagram_validation: bool = False,
) -> EvaluationResult:
    classification = classify_projectile_question(
        question_text=question_text,
        suggested_engine_case=engine_case,
        givens=givens,
        requested_quantity=requested_quantity,
    )
    engine_case = canonical_engine_case(classification.engine_case)
    givens = classification.givens
    requested_quantity = classification.requested_quantity or requested_quantity
    intent_reason = classification.unsupported_reason or "; ".join(classification.warnings)
    template_match = None if classification.unsupported else classify_template(
        question_text=question_text,
        engine_case=engine_case,
        requested_quantity=requested_quantity,
        givens=givens,
    )
    diagram_validation = validate_diagram_for_template(
        template_match.template if template_match else None,
        diagram,
    )
    diagram_model = normalize_diagram_for_template(
        template=template_match.template if template_match else None,
        diagram=diagram,
        engine_case=engine_case,
    )
    givens = _merge_diagram_givens(engine_case, givens, diagram_model, diagram_present=diagram is not None)
    text_geometry_is_sufficient = _text_givens_satisfy_template_geometry(engine_case, givens, question_text)
    if text_geometry_is_sufficient and not diagram_validation.valid:
        diagram_validation = replace(diagram_validation, valid=True, warnings=[], missing_entities=[])
        if isinstance(diagram_model, dict):
            diagram_model = {**diagram_model, "validation_warnings": []}
    if (
        require_diagram_validation
        and template_match
        and not diagram_validation.valid
    ):
        missing = ", ".join(diagram_validation.missing_entities)
        return _with_template_metadata(
            replace(
                EvaluationResult(
                    label="ad_hoc",
                    engine_case=engine_case or "unknown",
                    status="needs_review",
                    reason=(
                        "Diagram semantics need review before solving"
                        + (f": missing {missing}" if missing else ".")
                    ),
                ),
                diagram_valid=False,
                diagram_warnings=diagram_validation.warnings,
                diagram_model=diagram_model,
            ),
            template_match,
        )
    if not engine_case:
        return _with_template_metadata(
            EvaluationResult(
                label="ad_hoc",
                engine_case="unknown",
                status="unsupported",
                reason=intent_reason or "No engine case was provided by extraction.",
                template_warnings=classification.warnings,
            ),
            template_match,
        )

    entry = ManifestEntry(
        pdf_id="ad_hoc",
        question_number=0,
        engine_case=engine_case,
        question_text=question_text,
        options=options,
        expected_option_letter=None,
        expected_answer=None,
        knowns=givens,
    )

    solver = SOLVERS.get(engine_case)
    if solver is None:
        result = unsupported(entry)
        return _with_template_metadata(
            EvaluationResult(
                label=result.label,
                engine_case=result.engine_case,
                status=result.status,
                expected_option_letter=result.expected_option_letter,
                predicted_option_letter=result.predicted_option_letter,
                expected_answer=result.expected_answer,
                computed_value=result.computed_value,
                computed_text=result.computed_text,
                reason=f"{intent_reason}. {result.reason}".strip() if intent_reason else result.reason,
                trace=result.trace,
            ),
            template_match,
        )

    try:
        result = solver(entry)
        result = replace(
            result,
            diagram_valid=diagram_validation.valid,
            diagram_warnings=diagram_validation.warnings,
            diagram_model=diagram_model,
            equation_plan=build_equation_plan(result, entry.knowns),
        )
        # Ad-hoc solves do not have an answer key. If the solver computed an answer,
        # surface it as passed; unsupported/solver errors still remain explicit.
        return _with_template_metadata(
            EvaluationResult(
                label=result.label,
                engine_case=result.engine_case,
                status="passed" if result.computed_text or result.computed_value is not None or result.predicted_option_letter else result.status,
                template_id=result.template_id,
                template_confidence=result.template_confidence,
                template_reason=result.template_reason,
                template_warnings=result.template_warnings,
                diagram_valid=result.diagram_valid,
                diagram_warnings=result.diagram_warnings,
                diagram_model=result.diagram_model,
                expected_option_letter=None,
                predicted_option_letter=result.predicted_option_letter,
                computed_value=result.computed_value,
                computed_text=result.computed_text,
                reason="" if result.reason.startswith("expected option None") else result.reason,
                trace=result.trace,
                equation_plan=result.equation_plan,
            ),
            template_match,
        )
    except Exception as exc:
        preview = " ".join(question_text.split())[:240]
        return _with_template_metadata(
            EvaluationResult(
                label=entry.label,
                engine_case=entry.engine_case,
                status="failed",
                reason=f"solver error: {type(exc).__name__}: {exc}. text_preview={preview!r}",
            ),
            template_match,
        )


def _with_template_metadata(result: EvaluationResult, template_match) -> EvaluationResult:
    if template_match is None:
        return result
    combined_warnings = list(template_match.warnings)
    for warning in result.template_warnings:
        if warning not in combined_warnings:
            combined_warnings.append(warning)
    for warning in result.diagram_warnings:
        if warning not in combined_warnings:
            combined_warnings.append(warning)
    return replace(
        result,
        template_id=template_match.template.id,
        template_confidence=template_match.confidence,
        template_reason=template_match.reason,
        template_warnings=combined_warnings,
    )


def _merge_diagram_givens(engine_case: str | None, givens: list[str], diagram_model: Any, *, diagram_present: bool) -> list[str]:
    merged = list(givens)
    if not diagram_present or not isinstance(diagram_model, dict):
        return merged
    existing = {_normalize_given_key(given.split("=", 1)[0]) for given in merged if "=" in given}
    if engine_case in {
        "projectile_collides_with_sliding_particle_on_incline",
        "perpendicular_launch_range_on_incline",
        "max_range_on_incline",
        "horizontal_launch_onto_incline_distance",
        "motion_on_smooth_incline_perpendicular_to_slope",
    } and not {"incline", "incline_angle", "angle"} & existing:
        for surface in diagram_model.get("surfaces") or []:
            if not isinstance(surface, dict):
                continue
            angle = surface.get("angle_to_horizontal_deg")
            if angle is not None:
                try:
                    angle_text = f"{float(angle):g}"
                except (TypeError, ValueError):
                    angle_text = str(angle).strip()
                merged.append(f"incline={angle_text}deg")
                break
    return merged


def _text_givens_satisfy_template_geometry(engine_case: str | None, givens: list[str], question_text: str = "") -> bool:
    keys = {_normalize_given_key(given.split("=", 1)[0]) for given in givens if "=" in given}
    if engine_case in {"wall_height_at_distance", "wall_clearance_condition"}:
        required = {"wall_distance"}
        if engine_case == "wall_clearance_condition":
            required.add("wall_height")
        return required.issubset(keys)
    if engine_case in {"target_launch_angle_fixed_speed", "minimum_speed_to_hit_target"}:
        return "target" in keys
    if engine_case == "projectile_collides_with_sliding_particle_on_incline":
        text = question_text.lower()
        has_p = "particle p" in text or re.search(r"\bp\s+is\s+projected\b", text) is not None
        has_q = "particle q" in text or re.search(r"\bq\s+is\s+released\b", text) is not None
        has_incline = "inclined plane" in text or "incline" in text
        return has_p and has_q and has_incline
    return False


def _normalize_given_key(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")
