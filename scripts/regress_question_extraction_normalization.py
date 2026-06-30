#!/usr/bin/env python3
"""Regression checks for post-OCR projectile diagram entity normalization."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.prompt_engine import PromptEngine
from core.projectile_engine.diagram import normalize_diagram_for_template
from core.projectile_engine.templates import template_for_engine_case


def main() -> None:
    engine = PromptEngine.__new__(PromptEngine)
    failures: list[str] = []

    staircase = engine._normalize_question_extraction({
        "question_text": "A marble rolls down a staircase. Each step is 1 m high and 1 m wide. Which step is hit?",
        "question_text_solver": "A marble rolls down a staircase. Each step is 1 m high and 1 m wide. Which step is hit?",
        "is_projectile_question": True,
        "diagram": {"present": True, "type": "staircase", "entities": []},
        "suggested_engine_case": "staircase_collision",
    })
    staircase_ids = {entity["id"] for entity in staircase["diagram"]["entities"]}
    if not {"staircase", "vertical_faces"}.issubset(staircase_ids):
        failures.append(f"staircase entities missing: {sorted(staircase_ids)}")

    two_inclines = engine._normalize_question_extraction({
        "question_text": (
            "Two inclined planes OA and OB having inclination with horizontal 30 deg and 60 deg respectively "
            "intersect at O. A particle is projected from point P perpendicular to plane OA and strikes plane OB "
            "perpendicularly at Q."
        ),
        "question_text_solver": (
            "Two inclined planes OA and OB having inclination with horizontal 30 deg and 60 deg respectively "
            "intersect at O. A particle is projected from point P perpendicular to plane OA and strikes plane OB "
            "perpendicularly at Q."
        ),
        "is_projectile_question": True,
        "diagram": {"present": True, "type": "two_inclines", "entities": []},
        "suggested_engine_case": "two_inclines_perpendicular_launch_impact",
    })
    two_ids = {entity["id"] for entity in two_inclines["diagram"]["entities"]}
    expected_two = {"plane_OA", "plane_OB", "P", "Q", "angle_oa", "angle_ob", "perpendicular_markers"}
    if not expected_two.issubset(two_ids):
        failures.append(f"two-incline entities missing: {sorted(expected_two - two_ids)}")

    custom_two_inclines = normalize_diagram_for_template(
        template=template_for_engine_case("two_inclines_perpendicular_launch_impact"),
        engine_case="two_inclines_perpendicular_launch_impact",
        diagram={
            "present": True,
            "type": "two_inclines",
            "entities": [
                {
                    "id": "left_plane",
                    "kind": "incline",
                    "label": "L1",
                    "description": "left incline surface",
                },
                {
                    "id": "right_plane",
                    "kind": "incline",
                    "label": "L2",
                    "description": "right incline surface",
                },
                {
                    "id": "origin",
                    "kind": "point",
                    "label": "X",
                    "description": "intersection origin",
                },
                {
                    "id": "launch",
                    "kind": "point",
                    "label": "A",
                    "description": "launch point on the left incline",
                },
                {
                    "id": "hit",
                    "kind": "point",
                    "label": "B",
                    "description": "impact point on the right incline",
                },
                {
                    "id": "angle_left",
                    "kind": "angle",
                    "value": "30",
                    "unit": "deg",
                    "description": "left incline angle with horizontal",
                },
                {
                    "id": "angle_right",
                    "kind": "angle",
                    "value": "60",
                    "unit": "deg",
                    "description": "right incline angle with horizontal",
                },
                {
                    "id": "right_angle_launch",
                    "kind": "angle",
                    "description": "perpendicular marker at launch",
                },
                {
                    "id": "right_angle_hit",
                    "kind": "angle",
                    "description": "right angle marker at impact",
                },
            ],
        },
    )
    custom_points = custom_two_inclines["points"]
    custom_surface_ids = {surface["id"] for surface in custom_two_inclines["surfaces"]}
    custom_vector_anchors = {vector.get("anchor") for vector in custom_two_inclines["vectors"]}
    if not {"X", "A", "B"}.issubset(custom_points):
        failures.append(f"generic two-incline point labels not preserved: {sorted(custom_points)}")
    if custom_surface_ids != {"L1", "L2"}:
        failures.append(f"generic two-incline surface labels not preserved: {sorted(custom_surface_ids)}")
    if not {"A", "B"}.issubset(custom_vector_anchors):
        failures.append(f"generic two-incline vector anchors not role-based: {sorted(custom_vector_anchors)}")
    if custom_two_inclines["validation_warnings"]:
        failures.append(f"generic two-incline validation warnings: {custom_two_inclines['validation_warnings']}")

    target = engine._normalize_question_extraction({
        "question_text": "Find the minimum velocity to hit a target at (3 m, 4 m).",
        "question_text_solver": "Find the minimum velocity to hit a target at (3 m, 4 m).",
        "is_projectile_question": True,
        "diagram": {"present": False, "type": "none", "entities": []},
        "suggested_engine_case": "minimum_speed_to_hit_target",
    })
    target_ids = {entity["id"] for entity in target["diagram"]["entities"]}
    if "target_point" not in target_ids:
        failures.append(f"target point not inferred: {sorted(target_ids)}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        raise SystemExit(1)

    print("PASS question extraction normalization regressions")


if __name__ == "__main__":
    main()
