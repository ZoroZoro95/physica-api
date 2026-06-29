from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .models import ProblemTemplate


@dataclass(frozen=True)
class DiagramValidation:
    valid: bool
    present: bool
    missing_entities: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_diagram_for_template(template: ProblemTemplate | None, diagram: Any) -> DiagramValidation:
    if template is None or not template.required_diagram_entities:
        return DiagramValidation(valid=True, present=_diagram_present(diagram))

    present = _diagram_present(diagram)
    if not present:
        missing = sorted(template.required_diagram_entities)
        return DiagramValidation(
            valid=False,
            present=False,
            missing_entities=missing,
            warnings=[f"template requires diagram semantics: {', '.join(missing)}"],
        )

    missing = [
        requirement
        for requirement in sorted(template.required_diagram_entities)
        if not _has_required_entity(diagram, requirement)
    ]
    warnings = [f"missing diagram entity: {name}" for name in missing]
    return DiagramValidation(
        valid=not missing,
        present=True,
        missing_entities=missing,
        warnings=warnings,
    )


def normalize_diagram_for_template(
    *,
    template: ProblemTemplate | None,
    diagram: Any,
    engine_case: str | None = None,
) -> dict[str, Any]:
    if template is None:
        return {"kind": "none"}

    kind = template.diagram_kind or _diagram_type(diagram)
    validation = validate_diagram_for_template(template, diagram)
    warnings = list(validation.warnings)
    entities = _diagram_entities(diagram)

    if kind == "two_inclines":
        return _two_incline_model(entities, warnings)
    if kind == "single_incline":
        return _single_incline_model(entities, warnings, engine_case)
    if kind == "target_point":
        return _target_point_model(entities, warnings)
    if kind == "staircase":
        return _staircase_model(entities, warnings)
    if kind == "3d_line":
        return _line_3d_model(entities, warnings)
    if kind == "incline_relative_motion":
        model = _single_incline_model(entities, warnings, engine_case)
        model["kind"] = "incline_relative_motion"
        model["points"].setdefault("P", {"role": "particle", "label": "P"})
        model["points"].setdefault("Q", {"role": "particle", "label": "Q"})
        return model
    if kind == "smooth_incline_3d":
        model = _single_incline_model(entities, warnings, engine_case)
        model["kind"] = "smooth_incline_3d"
        model["vectors"].append({
            "id": "v0_perp_slope",
            "kind": "initial_velocity",
            "constraint": "perpendicular_to_line_of_greatest_slope",
        })
        model["constraints"].append("initial velocity is perpendicular to the line of greatest slope")
        return model
    return {
        "kind": kind if validation.present else "none",
        "coordinate_frame": _default_frame(),
        "points": _points_from_entities(entities),
        "surfaces": [],
        "vectors": _vectors_from_entities(entities),
        "constraints": [],
        "validation_warnings": warnings,
    }


def _diagram_present(diagram: Any) -> bool:
    if diagram is None:
        return False
    if isinstance(diagram, dict):
        return bool(diagram.get("present"))
    return bool(getattr(diagram, "present", False))


def _diagram_type(diagram: Any) -> str:
    if isinstance(diagram, dict):
        return str(diagram.get("type") or "none")
    return str(getattr(diagram, "type", "none") or "none")


def _diagram_entities(diagram: Any) -> list[Any]:
    if isinstance(diagram, dict):
        entities = diagram.get("entities") or []
    else:
        entities = getattr(diagram, "entities", []) or []
    return entities if isinstance(entities, list) else []


def _entity_field(entity: Any, field: str) -> str:
    if isinstance(entity, dict):
        return str(entity.get(field) or "")
    return str(getattr(entity, field, "") or "")


def _entity_text(entity: Any) -> str:
    fields = [
        _entity_field(entity, "id"),
        _entity_field(entity, "kind"),
        _entity_field(entity, "label"),
        _entity_field(entity, "label_solver"),
        _entity_field(entity, "description"),
        _entity_field(entity, "value"),
        _entity_field(entity, "unit"),
    ]
    return " ".join(fields).lower().replace("_", " ")


def _has_required_entity(diagram: Any, requirement: str) -> bool:
    diagram_type = _diagram_type(diagram)
    entities = _diagram_entities(diagram)
    entity_texts = [_entity_text(entity) for entity in entities]

    if requirement == "inclined_surface":
        return diagram_type in {"incline", "two_inclines"} or _has_kind(entities, {"incline", "surface"})
    if requirement == "impact_point":
        return _has_words(entity_texts, ["impact", "hit", "strike", "point q"])
    if requirement == "target_point":
        return diagram_type == "target" or _has_kind(entities, {"target"}) or _has_words(entity_texts, ["target"])
    if requirement == "bounce_surface":
        return diagram_type in {"bounce_surface", "ground", "surface"} or _has_kind(entities, {"surface", "ground"}) or _has_words(entity_texts, ["bounce", "rebound", "ground", "surface"])
    if requirement == "staircase":
        return diagram_type == "staircase" or _has_kind(entities, {"staircase"})
    if requirement == "vertical_faces":
        return diagram_type == "staircase" or _has_words(entity_texts, ["vertical face", "riser"])
    if requirement == "left_incline":
        return diagram_type == "two_inclines" or _has_words(entity_texts, ["left incline", "left plane", "oa", "plane oa"])
    if requirement == "right_incline":
        return diagram_type == "two_inclines" or _has_words(entity_texts, ["right incline", "right plane", "ob", "plane ob"])
    if requirement == "launch_point":
        return _has_words(entity_texts, ["launch", "projected", "point p"]) or _has_point_label(entity_texts, "p")
    if requirement == "impact_point":
        return _has_words(entity_texts, ["impact", "hit", "strike", "strikes", "point q"]) or _has_point_label(entity_texts, "q")
    if requirement == "plane_OA":
        return diagram_type == "two_inclines" or _has_words(entity_texts, ["oa", "plane oa"])
    if requirement == "plane_OB":
        return diagram_type == "two_inclines" or _has_words(entity_texts, ["ob", "plane ob"])
    if requirement == "point_P":
        return _has_point_label(entity_texts, "p")
    if requirement == "point_Q":
        return _has_point_label(entity_texts, "q")
    if requirement == "perpendicular_markers":
        return _has_words(entity_texts, ["perpendicular", "normal", "right angle"])
    if requirement == "particle_p":
        return _has_words(entity_texts, ["particle p", "point p", " p "])
    if requirement == "particle_q":
        return _has_words(entity_texts, ["particle q", "point q", " q "])
    if requirement == "line_of_greatest_slope":
        return _has_words(entity_texts, ["greatest slope"])
    if requirement == "perpendicular_velocity":
        return _has_words(entity_texts, ["perpendicular velocity", "velocity perpendicular", "normal velocity"])
    if requirement == "3d_axes":
        return diagram_type == "3d_axes" or _has_words(entity_texts, ["3d", "x axis", "y axis", "z axis"])
    if requirement == "line_constraint":
        return _has_kind(entities, {"line"}) or _has_words(entity_texts, ["line", "constraint"])
    return _has_words(entity_texts, [requirement.replace("_", " ")])


def _has_kind(entities: list[Any], kinds: set[str]) -> bool:
    return any(_entity_field(entity, "kind").lower() in kinds for entity in entities)


def _has_words(entity_texts: list[str], needles: list[str]) -> bool:
    return any(needle in text for text in entity_texts for needle in needles)


def _has_point_label(entity_texts: list[str], label: str) -> bool:
    return any(
        f"point {label}" in text
        or f"label {label}" in text
        or text.split().count(label) > 0
        for text in entity_texts
    )


def _default_frame() -> dict[str, Any]:
    return {
        "x_axis": "right",
        "y_axis": "up",
        "origin": "O",
        "angle_reference": "positive x axis",
    }


def _two_incline_model(entities: list[Any], warnings: list[str]) -> dict[str, Any]:
    left_surface = _surface_label_for(entities, ["oa", "left", "30"], "OA")
    right_surface = _surface_label_for(entities, ["ob", "right", "60"], "OB")
    origin = _point_label_for_role(entities, ["intersection", "origin", "point o"], "O")
    launch_point = _point_label_for_role(entities, ["launch", "projected", "point p"], "P")
    impact_point = _point_label_for_role(entities, ["impact", "strike", "strikes", "point q"], "Q")
    oa_angle = _angle_for_label(entities, [left_surface.lower(), "left", "30"]) or 30.0
    ob_angle = _angle_for_label(entities, [right_surface.lower(), "right", "60"]) or 60.0
    oa_ray = 180.0 - abs(oa_angle)
    ob_ray = abs(ob_angle)
    return {
        "kind": "two_inclines",
        "coordinate_frame": _default_frame(),
        "points": {
            origin: {"role": "intersection", "position": [0, 0, 0], "label": origin},
            f"{left_surface}_end": {"role": "point_on_surface", "surface_id": left_surface, "ray_parameter": 1.0},
            f"{right_surface}_end": {"role": "point_on_surface", "surface_id": right_surface, "ray_parameter": 1.0},
            launch_point: {"role": "launch_point", "surface_id": left_surface, "ray_parameter": 0.45, "label": launch_point},
            impact_point: {"role": "impact_point", "surface_id": right_surface, "ray_parameter": 0.62, "label": impact_point},
        },
        "surfaces": [
            {
                "id": left_surface,
                "kind": "incline",
                "passes_through": origin,
                "side": "left",
                "angle_to_horizontal_deg": oa_angle,
                "ray_direction_deg": oa_ray,
            },
            {
                "id": right_surface,
                "kind": "incline",
                "passes_through": origin,
                "side": "right",
                "angle_to_horizontal_deg": ob_angle,
                "ray_direction_deg": ob_ray,
            },
        ],
        "vectors": [
            {
                "id": "u",
                "kind": "initial_velocity",
                "anchor": launch_point,
                "constraint": "perpendicular_to",
                "target": left_surface,
                "direction_deg": _wrap_degrees(oa_ray - 90),
            },
            {
                "id": "vQ",
                "kind": "impact_velocity",
                "anchor": impact_point,
                "constraint": "perpendicular_to",
                "target": right_surface,
                "direction_deg": _wrap_degrees(ob_ray - 90),
            },
            {"id": "vx", "kind": "component", "anchor": launch_point, "direction_deg": 0},
        ],
        "constraints": [
            f"{launch_point} lies on {left_surface}",
            f"{impact_point} lies on {right_surface}",
            f"initial velocity is perpendicular to {left_surface}",
            f"impact velocity is perpendicular to {right_surface}",
        ],
        "validation_warnings": warnings,
    }


def _single_incline_model(entities: list[Any], warnings: list[str], engine_case: str | None) -> dict[str, Any]:
    angle = _angle_for_label(entities, ["incline", "plane", "surface", "slope"]) or _first_angle(entities)
    side = "right"
    ray_direction = angle if angle is not None else 30.0
    if engine_case == "horizontal_launch_onto_incline_distance":
        side = "right_down"
        ray_direction = -(angle if angle is not None else 45.0)
    surface = {
        "id": "incline",
        "kind": "incline",
        "passes_through": "O",
        "side": side,
        "angle_to_horizontal_deg": abs(ray_direction),
        "ray_direction_deg": ray_direction,
    }
    constraints = ["projectile interacts with inclined surface"]
    if engine_case == "perpendicular_launch_range_on_incline":
        constraints.append("initial velocity is perpendicular to incline")
    if engine_case == "inclined_plane_right_angle_impact_condition":
        constraints.append("impact velocity is perpendicular to incline")
    return {
        "kind": "single_incline",
        "coordinate_frame": _default_frame(),
        "points": _points_from_entities(entities) or {
            "O": {"role": "reference_origin", "position": [0, 0, 0]},
            "Q": {"role": "impact_point", "surface_id": "incline"},
        },
        "surfaces": [surface],
        "vectors": _vectors_from_entities(entities),
        "constraints": constraints,
        "validation_warnings": warnings,
    }


def _target_point_model(entities: list[Any], warnings: list[str]) -> dict[str, Any]:
    points = _points_from_entities(entities)
    points.setdefault("O", {"role": "launch_point", "position": [0, 0, 0]})
    points.setdefault("target", {"role": "target_point"})
    return {
        "kind": "target_point",
        "coordinate_frame": _default_frame(),
        "points": points,
        "surfaces": [],
        "vectors": _vectors_from_entities(entities),
        "constraints": ["trajectory must pass through target point"],
        "validation_warnings": warnings,
    }


def _staircase_model(entities: list[Any], warnings: list[str]) -> dict[str, Any]:
    return {
        "kind": "staircase",
        "coordinate_frame": _default_frame(),
        "points": {"O": {"role": "launch_point", "position": [0, 0, 0]}},
        "surfaces": [{
            "id": "staircase",
            "kind": "staircase",
            "step_height": _distance_for_label(entities, ["height", "high", "y"]),
            "step_width": _distance_for_label(entities, ["width", "wide", "x"]),
        }],
        "vectors": _vectors_from_entities(entities),
        "constraints": ["first collision occurs with a vertical stair face"],
        "validation_warnings": warnings,
    }


def _line_3d_model(entities: list[Any], warnings: list[str]) -> dict[str, Any]:
    return {
        "kind": "3d_line",
        "coordinate_frame": {
            "x_axis": "right",
            "y_axis": "forward",
            "z_axis": "up",
            "origin": "O",
        },
        "points": _points_from_entities(entities),
        "surfaces": [],
        "vectors": _vectors_from_entities(entities),
        "constraints": ["projectile impact point lies on the given horizontal line"],
        "validation_warnings": warnings,
    }


def _points_from_entities(entities: list[Any]) -> dict[str, dict[str, Any]]:
    points: dict[str, dict[str, Any]] = {}
    for entity in entities:
        kind = _entity_field(entity, "kind").lower()
        label = _entity_field(entity, "label_solver") or _entity_field(entity, "label") or _entity_field(entity, "id")
        if kind not in {"point", "target", "projectile"} or not label:
            continue
        key = label.strip().replace(" ", "_")
        points[key] = {
            "role": "target_point" if kind == "target" else "point",
            "label": label,
            "description": _entity_field(entity, "description"),
        }
    return points


def _surface_label_for(entities: list[Any], needles: list[str], default: str) -> str:
    for entity in entities:
        if _entity_field(entity, "kind").lower() not in {"line", "incline", "surface"}:
            continue
        text = _entity_text(entity)
        if any(needle in text for needle in needles):
            label = _entity_field(entity, "label_solver") or _entity_field(entity, "label") or _entity_field(entity, "id")
            if label:
                return label.strip().replace(" ", "_")
    return default


def _point_label_for_role(entities: list[Any], needles: list[str], default: str) -> str:
    for entity in entities:
        if _entity_field(entity, "kind").lower() not in {"point", "target", "projectile"}:
            continue
        text = _entity_text(entity)
        if any(needle in text for needle in needles):
            label = _entity_field(entity, "label_solver") or _entity_field(entity, "label") or _entity_field(entity, "id")
            if label:
                return label.strip().replace(" ", "_")
    return default


def _vectors_from_entities(entities: list[Any]) -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = []
    for entity in entities:
        if _entity_field(entity, "kind").lower() != "velocity_arrow":
            continue
        label = _entity_field(entity, "label_solver") or _entity_field(entity, "label") or _entity_field(entity, "id") or "v"
        vectors.append({
            "id": label,
            "kind": "velocity",
            "magnitude": _entity_field(entity, "value"),
            "unit": _entity_field(entity, "unit"),
            "description": _entity_field(entity, "description"),
        })
    return vectors


def _angle_for_label(entities: list[Any], needles: list[str]) -> float | None:
    for entity in entities:
        text = _entity_text(entity)
        if _entity_field(entity, "kind").lower() != "angle":
            continue
        if any(needle in text for needle in needles):
            value = _number_from_entity(entity)
            if value is not None:
                return value
    return None


def _first_angle(entities: list[Any]) -> float | None:
    for entity in entities:
        if _entity_field(entity, "kind").lower() == "angle":
            value = _number_from_entity(entity)
            if value is not None:
                return value
    return None


def _distance_for_label(entities: list[Any], needles: list[str]) -> float | None:
    for entity in entities:
        text = _entity_text(entity)
        if _entity_field(entity, "kind").lower() not in {"distance", "height"}:
            continue
        if any(needle in text for needle in needles):
            return _number_from_entity(entity)
    return None


def _number_from_entity(entity: Any) -> float | None:
    for field in ("value", "description", "label", "label_solver"):
        text = _entity_field(entity, field)
        match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
        if match:
            return float(match.group(0))
    return None


def _wrap_degrees(value: float) -> float:
    while value > 180:
        value -= 360
    while value <= -180:
        value += 360
    return value
