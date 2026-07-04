from __future__ import annotations

import math
import json
import re
from typing import Any

from .mapper import map_projectile_problem
from .models import EvaluationResult
from .scene_contract import validate_animation_scene_spec
from .walkthrough import build_solution_walkthrough
from .visual_contract import (
    build_beat_visual_spec,
    contract_visible_ids,
    contract_visible_vectors,
    contract_visual_action,
    merge_contract_labels,
)


def build_animation_scene_spec(
    *,
    result: EvaluationResult,
    question_text: str,
    givens: list[str],
) -> dict[str, Any] | None:
    if result.status != "passed":
        return None
    spec = map_projectile_problem(question_text)
    plan_givens = list((result.equation_plan or {}).get("givens") or [])
    merged_givens = _merge_givens(spec.givens + givens + plan_givens)

    def finalize(scene: dict[str, Any]) -> dict[str, Any]:
        scene = _attach_storyboard_contract(scene, result=result)
        scene["contract_errors"] = validate_animation_scene_spec(scene)
        return scene

    if result.engine_case == "two_inclines_perpendicular_launch_impact":
        two_incline_scene = _build_two_incline_transfer_scene(result=result, question_text=question_text, givens=merged_givens)
        if two_incline_scene is not None:
            return finalize(two_incline_scene)
    if result.engine_case == "two_projectile_interception_time_ratio":
        ratio_scene = _build_interception_ratio_scene(result=result, question_text=question_text, givens=merged_givens)
        if ratio_scene is not None:
            return finalize(ratio_scene)
    if result.engine_case == "two_projectile_same_speed_comparison":
        comparison_scene = _build_two_projectile_same_speed_comparison_scene(result=result, givens=merged_givens)
        if comparison_scene is not None:
            return finalize(comparison_scene)
    if result.engine_case == "staircase_collision":
        staircase_scene = _build_staircase_scene(result=result, question_text=question_text, givens=merged_givens)
        if staircase_scene is not None:
            return finalize(staircase_scene)
    if result.engine_case == "projectile_split_at_apex_fragment_time":
        split_scene = _build_split_at_apex_scene(result=result, question_text=question_text, givens=merged_givens)
        if split_scene is not None:
            return finalize(split_scene)
    if result.engine_case in {
        "inclined_plane_impact_time",
        "inclined_plane_right_angle_impact_condition",
        "inclined_plane_same_point_time_ratio",
        "inclined_plane_max_normal_distance_velocity_component",
        "perpendicular_launch_range_on_incline",
        "max_range_on_incline",
        "horizontal_launch_onto_incline_distance",
        "projectile_collides_with_sliding_particle_on_incline",
        "motion_on_smooth_incline_perpendicular_to_slope",
    }:
        if result.engine_case == "projectile_collides_with_sliding_particle_on_incline":
            incline_collision_scene = _build_projectile_slider_incline_collision_scene(result=result, question_text=question_text, givens=merged_givens)
            if incline_collision_scene is not None:
                return finalize(incline_collision_scene)
        incline_scene = _build_single_incline_scene(result=result, question_text=question_text, givens=merged_givens)
        if incline_scene is not None:
            return finalize(incline_scene)
    if result.engine_case == "two_projectile_collision_time":
        multi_scene = _build_two_projectile_collision_scene(result=result, spec_world=spec.world, givens=merged_givens)
        if multi_scene is not None:
            return finalize(multi_scene)
    if result.engine_case == "monkey_hunter_condition":
        monkey_scene = _build_monkey_hunter_scene(result=result, givens=merged_givens)
        if monkey_scene is not None:
            return finalize(monkey_scene)

    target = _point_from_givens(merged_givens, ["target"])
    u = _number_from_givens(merged_givens, ["v0", "u", "speed", "velocity"])
    if result.engine_case == "minimum_speed_to_hit_target" and result.computed_value is not None:
        u = result.computed_value
    theta_deg = _number_from_givens(merged_givens, ["angle", "theta", "launch_angle"])
    if theta_deg is None and result.engine_case == "minimum_speed_to_hit_target" and target is not None:
        theta_deg = _minimum_speed_target_angle_deg(target)
    if theta_deg is None and "horizontal" in spec.constraints:
        theta_deg = 0.0
    if u is None and theta_deg == 0.0:
        u = _number_from_givens(merged_givens, ["vx", "ux", "v_x", "u_x"])
    if theta_deg is None and _unknown_for_case(result.engine_case, question_text) in {"launch_angle", "target_launch_angle"}:
        theta_deg = _first_angle_from_text(result.computed_text or "")
    representative_scene = result.engine_case == "level_ground_time_of_flight_derivation"
    if representative_scene:
        u = u if u is not None else 20.0
        theta_deg = theta_deg if theta_deg is not None else 45.0
    if u is None or theta_deg is None:
        fallback_scene = _build_representative_scene_for_passed_case(
            result=result,
            question_text=question_text,
            givens=merged_givens,
        )
        return finalize(fallback_scene) if fallback_scene is not None else None

    g = _number_from_givens(merged_givens, ["g"]) or 10.0
    launch_height = _number_from_givens(merged_givens, ["height", "launch_height", "initial_height", "h", "y0"]) or 0.0

    theta = math.radians(theta_deg)
    ux = u * math.cos(theta)
    uy = u * math.sin(theta)
    full_time = _positive_ground_time(y0=launch_height, uy=uy, g=g)
    full_range = ux * full_time
    peak_gain = (uy * uy) / (2 * g) if g else 0
    max_height = launch_height + peak_gain
    t_peak = max(0.0, uy / g) if g else 0

    unknown = _unknown_for_case(result.engine_case, question_text)
    wall_x = _number_from_givens(merged_givens, ["wall_distance", "wall_x", "x"])
    wall_height = _number_from_givens(merged_givens, ["wall_height", "obstacle_height"])
    position_time = _number_from_givens(merged_givens, ["time", "t"])

    if unknown in {"time_of_flight", "time_to_land"} and result.computed_value is not None:
        display_time = result.computed_value
        display_range = ux * display_time
    elif wall_x is not None:
        display_time = max((wall_x or full_range) / ux, 0.001) if ux else full_time
        display_range = max(wall_x or full_range, full_range)
    elif unknown == "position_at_time" and position_time is not None:
        display_time = _number_from_givens(merged_givens, ["time", "t"]) or full_time
        display_range = max(ux * display_time, full_range)
    elif target:
        display_time = (target[0] / ux) if target and ux else full_time
        display_range = max(target[0] if target else full_range, full_range)
    else:
        display_time = full_time
        display_range = (
            result.computed_value
            if unknown in {"range", "maximum_range"}
            and result.computed_value is not None
            else full_range
        )

    display_height = (
        result.computed_value
        if unknown == "maximum_height" and result.computed_value is not None
        else max_height
    )
    apex_x = ux * t_peak
    position_point = None
    if unknown == "position_at_time" and position_time is not None:
        position_point = {
            "x": ux * position_time,
            "y": launch_height + uy * position_time - 0.5 * g * position_time * position_time,
            "label": f"t={position_time:g}s",
        }

    points = {
        "launch": {"x": 0.0, "y": launch_height, "label": "O"},
        "landing": {"x": display_range, "y": 0.0, "label": "landing"},
        "apex": {"x": apex_x, "y": display_height, "label": "apex"},
    }
    if target:
        points["target"] = {"x": target[0], "y": target[1], "label": "target"}
    if wall_x is not None:
        points["wall_top"] = {"x": wall_x, "y": wall_height or 0.0, "label": "wall"}
    if position_point:
        points["position_at_t"] = position_point

    sampled = _sample_projectile_path(y0=launch_height, ux=ux, uy=uy, g=g, duration=max(display_time, 0.001), count=32)
    if wall_x is not None and ux:
        wall_time = wall_x / ux
        if wall_time > display_time:
            sampled = _sample_projectile_path(y0=launch_height, ux=ux, uy=uy, g=g, duration=wall_time, count=32)
    steps = _scene_steps(result)
    world = _scene_world(spec.world, target=target, wall_x=wall_x, launch_height=launch_height)
    scene_constraints = set(spec.constraints)
    if world == "level_ground":
        scene_constraints.add("same_height_landing")
    if world == "height_launch":
        scene_constraints.add("initial_height")
    if world == "wall":
        scene_constraints.add("fixed_horizontal_distance")
    obstacles = []
    if wall_x is not None:
        obstacles.append({"id": "wall", "type": "vertical_wall", "x": wall_x, "height": wall_height or 0.0})
    warnings = []
    if unknown in {"launch_angle", "target_launch_angle"} and " or " in (result.computed_text or ""):
        warnings.append("Multiple valid launch angles exist; scene shows the lower-angle trajectory.")
    if representative_scene:
        warnings.append("Symbolic derivation is visualized with representative values u=20 m/s, theta=45deg, g=10 m/s^2.")

    surfaces = [{"id": "ground", "type": "line", "from_xy": [0.0, 0.0], "to_xy": [display_range, 0.0], "label": "ground"}]
    if launch_height > 0:
        points["drop_base"] = {"x": 0.0, "y": 0.0, "label": "base"}
        surfaces.append({
            "id": "cliff_face",
            "type": "vertical_drop",
            "from_xy": [0.0, 0.0],
            "to_xy": [0.0, launch_height],
            "label": f"h = {launch_height:g} m",
        })

    return finalize({
        "schema_version": 1,
        "problem": {
            "world": world,
            "unknown": unknown,
            "constraints": sorted(scene_constraints),
            "engine_case": result.engine_case,
        },
        "units": {"length": "m", "time": "s", "angle": "deg", "velocity": "m/s"},
        "coordinate_frame": {"x": "horizontal", "y": "vertical", "origin": "launch"},
        "geometry": {
            "points": points,
            "surfaces": surfaces,
            "obstacles": obstacles,
            "axes": [
                {"id": "x_axis", "direction": "horizontal"},
                {"id": "y_axis", "direction": "vertical"},
            ],
        },
        "actors": [{"id": "projectile", "type": "particle", "label": "projectile"}],
        "trajectories": [
            {
                "id": "trajectory:path",
                "actor": "projectile",
                "equation": "y = x tan(theta) - gx^2/(2u^2cos^2(theta))",
                "sampled_points": sampled,
            }
        ],
        "motion": {
            "kind": "constant_gravity_projectile",
            "initial": {"x": 0.0, "y": launch_height, "vx": ux, "vy": uy},
            "acceleration": {"x": 0.0, "y": -g},
            "duration": display_time,
        },
        "motions": [
            {
                "actor": "projectile",
                "kind": "constant_gravity_projectile",
                "initial": {"x": 0.0, "y": launch_height, "vx": ux, "vy": uy},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": display_time,
            }
        ],
        "quantities": {
            "u": {"value": u, "unit": "m/s", "label": "u"},
            "theta": {"value": theta_deg, "unit": "deg", "label": "theta"},
            "g": {"value": g, "unit": "m/s^2", "label": "g"},
            "ux": {"value": ux, "unit": "m/s", "label": "u_x"},
            "uy": {"value": uy, "unit": "m/s", "label": "u_y"},
            "T": {"value": display_time, "unit": "s", "label": "T"},
            "t_peak": {"value": t_peak, "unit": "s", "label": "t_peak"},
            "R": {"value": display_range, "unit": "m", "label": "R"},
            "H": {"value": display_height, "unit": "m", "label": "H"},
            "launch_height": {"value": launch_height, "unit": "m", "label": "h"},
            "h": {"value": launch_height, "unit": "m", "label": "h"},
            **({"formula_T": {"value": display_time, "unit": "s", "label": "T = 2u sin(theta)/g"}} if representative_scene else {}),
        },
        "events": [
            {"id": "event:launch", "time": 0.0, "point": "launch", "label": "launch"},
            {"id": "event:apex", "time": t_peak, "point": "apex", "label": "v_y = 0"},
            {"id": "event:landing", "time": display_time, "point": "landing", "label": "landing"},
        ],
        "steps": steps,
        "warnings": warnings,
    })


def _build_representative_scene_for_passed_case(
    *,
    result: EvaluationResult,
    question_text: str,
    givens: dict[str, str],
) -> dict[str, Any] | None:
    if result.engine_case == "parametric_initial_speed":
        return _build_parametric_initial_speed_scene(result=result, givens=givens)
    if result.engine_case == "parametric_curve_classification":
        return _build_parametric_curve_classification_scene(result=result)
    if result.engine_case == "air_drag_conceptual_timing":
        return _build_air_drag_concept_scene(result=result)
    return _build_representative_projectile_scene(result=result, question_text=question_text, givens=givens)


def _build_monkey_hunter_scene(*, result: EvaluationResult, givens: dict[str, str]) -> dict[str, Any]:
    g = _number_from_givens(givens, ["g"]) or 10.0
    height = _number_from_givens(givens, ["height", "h", "target_y", "y"]) or 45.0
    speed = _number_from_givens(givens, ["v0", "u", "speed", "velocity"]) or 30.0
    theta_from_given = _number_from_givens(givens, ["angle", "theta", "launch_angle"])
    horizontal_distance = _number_from_givens(givens, ["horizontal_distance", "target_x", "x"])
    line_of_sight = _number_from_givens(givens, ["line_of_sight", "los", "distance"])

    fall_time = math.sqrt(max(0.0, 2 * height / g)) if g else 1.0
    max_line_of_sight = speed * fall_time
    if horizontal_distance is None and theta_from_given is not None:
        tangent = math.tan(math.radians(theta_from_given))
        if not math.isclose(tangent, 0.0, abs_tol=1e-9):
            horizontal_distance = abs(height / tangent)
    if horizontal_distance is None and line_of_sight is not None and line_of_sight > height:
        horizontal_distance = math.sqrt(max(1.0, line_of_sight * line_of_sight - height * height))
    if horizontal_distance is None:
        representative_line = max(height * 1.42, min(max_line_of_sight * 0.72, height * 1.75))
        horizontal_distance = math.sqrt(max(height, representative_line * representative_line - height * height))
    if line_of_sight is None:
        line_of_sight = math.hypot(horizontal_distance, height)

    theta_deg = math.degrees(math.atan2(height, horizontal_distance))
    ux = speed * horizontal_distance / max(line_of_sight, 1e-9)
    uy = speed * height / max(line_of_sight, 1e-9)
    arrival_time = line_of_sight / speed if speed > 0 else fall_time
    hit_before_ground = arrival_time <= fall_time + 1e-9
    duration = max(0.35, min(arrival_time, fall_time))

    projectile_sampled = _sample_projectile_path(
        y0=0.0,
        ux=ux,
        uy=uy,
        g=g,
        duration=duration,
        count=36,
        clamp_to_ground=True,
    )
    monkey_sampled = [
        {"x": horizontal_distance, "y": max(0.0, height - 0.5 * g * point["t"] * point["t"]), "t": point["t"]}
        for point in projectile_sampled
    ]
    current_monkey_y = monkey_sampled[-1]["y"] if monkey_sampled else height
    hit_point = {
        "x": horizontal_distance if hit_before_ground else projectile_sampled[-1]["x"],
        "y": current_monkey_y if hit_before_ground else 0.0,
        "label": "hit" if hit_before_ground else "ground first",
    }
    same_drop = max(0.0, height - current_monkey_y)

    return {
        "schema_version": 1,
        "problem": {
            "world": "monkey_hunter",
            "unknown": _unknown_for_case(result.engine_case, ""),
            "constraints": ["falling_target", "direct_aim", "same_gravity"],
            "engine_case": result.engine_case,
        },
        "units": {"length": "m", "time": "s", "angle": "deg", "velocity": "m/s"},
        "coordinate_frame": {"x": "horizontal", "y": "vertical", "origin": "hunter"},
        "geometry": {
            "points": {
                "launch": {"x": 0.0, "y": 0.0, "label": "gun"},
                "hunter": {"x": -2.0, "y": 0.0, "label": "hunter"},
                "monkey_start": {"x": horizontal_distance, "y": height, "label": "monkey"},
                "monkey_current": {"x": horizontal_distance, "y": current_monkey_y, "label": "monkey"},
                "hit": hit_point,
                "monkey_ground": {"x": horizontal_distance, "y": 0.0, "label": "ground"},
            },
            "surfaces": [
                {"id": "ground", "type": "line", "from_xy": [-4.0, 0.0], "to_xy": [horizontal_distance + 8.0, 0.0], "label": "ground"},
                {"id": "tree_trunk", "type": "tree", "from_xy": [horizontal_distance + 3.0, 0.0], "to_xy": [horizontal_distance + 3.0, height + 4.0], "label": "tree"},
                {"id": "branch", "type": "branch", "from_xy": [horizontal_distance - 8.0, height], "to_xy": [horizontal_distance + 6.0, height], "label": "branch"},
                {"id": "aim_line", "type": "aim_line", "from_xy": [0.0, 0.0], "to_xy": [horizontal_distance, height], "label": "direct aim line"},
            ],
            "obstacles": [{"id": "tree", "type": "tree", "x": horizontal_distance + 3.0, "height": height + 4.0}],
            "axes": [
                {"id": "x_axis", "direction": "horizontal"},
                {"id": "y_axis", "direction": "vertical"},
            ],
        },
        "actors": [
            {"id": "hunter", "type": "person", "label": "hunter"},
            {"id": "monkey", "type": "falling_target", "label": "monkey"},
            {"id": "projectile", "type": "projectile", "label": "projectile"},
        ],
        "trajectories": [
            {
                "id": "trajectory:path",
                "actor": "projectile",
                "equation": "projectile follows the original aim line minus 1/2gt^2 drop",
                "sampled_points": projectile_sampled,
            },
            {
                "id": "trajectory:monkey_drop",
                "actor": "monkey",
                "equation": "monkey drop = 1/2gt^2",
                "sampled_points": monkey_sampled,
            },
        ],
        "motion": {
            "actor": "projectile",
            "kind": "constant_gravity_projectile",
            "initial": {"x": 0.0, "y": 0.0, "vx": ux, "vy": uy},
            "acceleration": {"x": 0.0, "y": -g},
            "duration": duration,
        },
        "motions": [
            {
                "actor": "projectile",
                "kind": "constant_gravity_projectile",
                "initial": {"x": 0.0, "y": 0.0, "vx": ux, "vy": uy},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": duration,
            },
            {
                "actor": "monkey",
                "kind": "vertical_free_fall",
                "initial": {"x": horizontal_distance, "y": height, "vx": 0.0, "vy": 0.0},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": duration,
            },
        ],
        "quantities": {
            "u": {"value": speed, "unit": "m/s", "label": "u"},
            "theta": {"value": theta_deg, "unit": "deg", "label": "theta"},
            "g": {"value": g, "unit": "m/s^2", "label": "g"},
            "H": {"value": height, "unit": "m", "label": "monkey height"},
            "T": {"value": duration, "unit": "s", "label": "arrival time"},
            "T_fall": {"value": fall_time, "unit": "s", "label": "monkey fall time"},
            "line_of_sight": {"value": line_of_sight, "unit": "m", "label": "line of sight"},
            "drop_projectile": {"value": same_drop, "unit": "m", "label": "projectile drop"},
            "drop_monkey": {"value": same_drop, "unit": "m", "label": "monkey drop"},
        },
        "events": [
            {"id": "event:launch", "time": 0.0, "point": "launch", "label": "fire"},
            {"id": "event:monkey_drop", "time": 0.0, "point": "monkey_start", "label": "monkey drops"},
            {"id": "event:hit", "time": duration, "point": "hit", "label": "same drop"},
            {"id": "event:monkey_ground", "time": fall_time, "point": "monkey_ground", "label": "monkey reaches ground"},
        ],
        "steps": _scene_steps(result),
        "warnings": [] if hit_before_ground else ["Line-of-sight arrival is after monkey ground time; the diagram shows the limiting condition."],
    }


def _build_parametric_initial_speed_scene(*, result: EvaluationResult, givens: dict[str, str]) -> dict[str, Any]:
    ux = _number_from_givens(givens, ["ux", "vx"]) or _coefficient_of_t(givens.get("x_t") or givens.get("x") or "") or 6.0
    y_equation = givens.get("y_t") or givens.get("y") or ""
    uy = _linear_coefficient_of_t(y_equation) or 8.0
    g = _quadratic_gravity_from_y_t(y_equation) or 10.0
    duration = max(_positive_ground_time(y0=0.0, uy=uy, g=g), 0.8)
    sampled = _sample_projectile_path(y0=0.0, ux=ux, uy=uy, g=g, duration=duration, count=36)
    apex = max(sampled, key=lambda point: point["y"])
    landing = sampled[-1]
    return _representative_projectile_scene(
        result=result,
        world="level_ground",
        unknown="initial_speed",
        u=math.hypot(ux, uy),
        theta_deg=math.degrees(math.atan2(uy, ux)),
        g=g,
        launch_height=0.0,
        duration=duration,
        sampled=sampled,
        points={
            "launch": {"x": 0.0, "y": 0.0, "label": "O"},
            "landing": {"x": landing["x"], "y": 0.0, "label": "landing"},
            "apex": {"x": apex["x"], "y": apex["y"], "label": "apex"},
        },
        warnings=["Scene is built directly from the parametric equations x(t) and y(t)."],
    )


def _build_parametric_curve_classification_scene(*, result: EvaluationResult) -> dict[str, Any]:
    sampled = []
    for index in range(64):
        tau = index / 63
        angle = 2 * math.pi * tau
        sampled.append({"x": 12.0 - 4.0 * math.cos(angle), "y": 2.5 * math.sin(angle), "t": tau})
    top = max(sampled, key=lambda point: point["y"])
    right = max(sampled, key=lambda point: point["x"])
    return {
        "schema_version": 1,
        "problem": {
            "world": "parametric_curve",
            "unknown": "path_shape",
            "constraints": ["parametric_velocity", "representative_curve"],
            "engine_case": result.engine_case,
        },
        "units": {"length": "m", "time": "s", "angle": "deg", "velocity": "m/s"},
        "coordinate_frame": {"x": "horizontal", "y": "vertical", "origin": "given coordinate axes"},
        "geometry": {
            "points": {
                "launch": {"x": sampled[0]["x"], "y": sampled[0]["y"], "label": "t=0"},
                "apex": {"x": top["x"], "y": top["y"], "label": "top"},
                "landing": {"x": sampled[-1]["x"], "y": sampled[-1]["y"], "label": ""},
                "curve_right": {"x": right["x"], "y": right["y"], "label": "ellipse"},
            },
            "surfaces": [],
            "obstacles": [],
            "axes": [
                {"id": "x_axis", "direction": "horizontal"},
                {"id": "y_axis", "direction": "vertical"},
            ],
        },
        "actors": [{"id": "projectile", "type": "particle", "label": "particle"}],
        "trajectories": [{"id": "trajectory:path", "actor": "projectile", "equation": "parametric ellipse", "sampled_points": sampled}],
        "motion": {
            "kind": "parametric_curve",
            "initial": {"x": sampled[0]["x"], "y": sampled[0]["y"], "vx": 0.0, "vy": 5.0 * math.pi},
            "acceleration": {"x": 1.0, "y": 0.0},
            "duration": 1.0,
        },
        "motions": [
            {
                "actor": "projectile",
                "kind": "parametric_curve",
                "initial": {"x": sampled[0]["x"], "y": sampled[0]["y"], "vx": 0.0, "vy": 5.0 * math.pi},
                "acceleration": {"x": 1.0, "y": 0.0},
                "duration": 1.0,
            }
        ],
        "quantities": {
            "R": {"value": 8.0, "unit": "m", "label": "major span"},
            "H": {"value": 2.5, "unit": "m", "label": "minor semi-axis"},
            "T": {"value": 1.0, "unit": "s", "label": "period"},
        },
        "events": [
            {"id": "event:launch", "time": 0.0, "point": "launch", "label": "given t=0 point"},
            {"id": "event:landing", "time": 1.0, "point": "landing", "label": "one full cycle"},
        ],
        "steps": _scene_steps(result),
        "warnings": ["This is a parametric-curve visualization, not projectile motion."],
    }


def _build_air_drag_concept_scene(*, result: EvaluationResult) -> dict[str, Any]:
    u = 20.0
    theta = math.radians(45.0)
    g = 10.0
    ux = u * math.cos(theta)
    uy = u * math.sin(theta)
    duration = _positive_ground_time(y0=0.0, uy=uy, g=g)
    no_drag = _sample_projectile_path(y0=0.0, ux=ux, uy=uy, g=g, duration=duration, count=40)
    drag = [
        {
            "x": point["x"] * (0.82 - 0.18 * (index / 39)),
            "y": max(0.0, point["y"] * (0.92 - 0.12 * (index / 39))),
            "t": point["t"],
        }
        for index, point in enumerate(no_drag)
    ]
    apex = max(no_drag, key=lambda point: point["y"])
    landing = no_drag[-1]
    scene = _representative_projectile_scene(
        result=result,
        world="drag_concept",
        unknown="qualitative_drag_effect",
        u=u,
        theta_deg=45.0,
        g=g,
        launch_height=0.0,
        duration=duration,
        sampled=no_drag,
        points={
            "launch": {"x": 0.0, "y": 0.0, "label": "O"},
            "landing": {"x": landing["x"], "y": 0.0, "label": "no-drag landing"},
            "apex": {"x": apex["x"], "y": apex["y"], "label": "apex"},
        },
        warnings=["Representative comparison: drag path is schematic, not a solved drag differential equation."],
    )
    scene["actors"].append({"id": "projectile_drag", "type": "particle", "label": "with drag"})
    scene["trajectories"].append({"id": "trajectory:drag", "actor": "projectile_drag", "equation": "schematic drag path", "sampled_points": drag})
    scene["motions"].append({
        "actor": "projectile_drag",
        "kind": "schematic_drag_projectile",
        "initial": {"x": 0.0, "y": 0.0, "vx": ux * 0.88, "vy": uy * 0.92},
        "acceleration": {"x": -1.0, "y": -g},
        "duration": duration,
    })
    return scene


def _build_representative_projectile_scene(
    *,
    result: EvaluationResult,
    question_text: str,
    givens: dict[str, str],
) -> dict[str, Any]:
    g = _number_from_givens(givens, ["g"]) or 10.0
    launch_height = _number_from_givens(givens, ["height", "launch_height", "initial_height", "h", "y0"]) or 0.0
    horizontal_speed = _number_from_givens(givens, ["vx", "ux", "v_x", "u_x"])
    u = _number_from_givens(givens, ["v0", "u", "speed", "velocity"]) or _first_speed_from_text(question_text)
    theta_deg = _number_from_givens(givens, ["angle", "theta", "launch_angle"])
    if result.engine_case == "horizontal_throw_velocity_angle_time" or ("horizontal" in question_text.lower() and horizontal_speed is not None):
        u = horizontal_speed or u or 10.0
        theta_deg = 0.0
        launch_height = launch_height or 10.0
    else:
        u = u or 20.0
        theta_deg = theta_deg if theta_deg is not None else (_first_angle_from_text(question_text) or 45.0)

    if result.engine_case in {"same_range_doubled_angle_time_ratio", "target_angle_from_short_overshoot", "target_reachability_fixed_speed"}:
        theta_deg = 45.0
    if result.engine_case == "max_range_from_height_fixed_speed":
        theta_deg = 35.0

    theta = math.radians(theta_deg)
    ux = u * math.cos(theta)
    uy = u * math.sin(theta)
    duration = _positive_ground_time(y0=launch_height, uy=uy, g=g)
    if duration <= 0:
        duration = max(_first_time_from_text(question_text) or 2.0, 0.5)
    sampled = _sample_projectile_path(y0=launch_height, ux=ux, uy=uy, g=g, duration=duration, count=40)
    apex = max(sampled, key=lambda point: point["y"])
    landing = sampled[-1]
    target = _point_from_givens(givens, ["target"]) or ((40.0, 30.0) if "target" in question_text.lower() else None)
    points = {
        "launch": {"x": 0.0, "y": launch_height, "label": "O"},
        "landing": {"x": landing["x"], "y": 0.0, "label": "landing"},
        "apex": {"x": apex["x"], "y": apex["y"], "label": "apex"},
    }
    if target is not None:
        points["target"] = {"x": target[0], "y": target[1], "label": "target"}
    return _representative_projectile_scene(
        result=result,
        world=_scene_world("target" if target is not None else "height_launch" if launch_height > 0 else "level_ground", target=target, wall_x=None, launch_height=launch_height),
        unknown=_unknown_for_case(result.engine_case, question_text),
        u=u,
        theta_deg=theta_deg,
        g=g,
        launch_height=launch_height,
        duration=duration,
        sampled=sampled,
        points=points,
        warnings=["Representative geometry for a symbolic or conceptual solved case; equations and final answer remain authoritative."],
    )


def _representative_projectile_scene(
    *,
    result: EvaluationResult,
    world: str,
    unknown: str,
    u: float,
    theta_deg: float,
    g: float,
    launch_height: float,
    duration: float,
    sampled: list[dict[str, float]],
    points: dict[str, dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    ux = u * math.cos(math.radians(theta_deg))
    uy = u * math.sin(math.radians(theta_deg))
    landing_x = float(points.get("landing", {}).get("x") or (sampled[-1]["x"] if sampled else 0.0))
    max_height = max((point["y"] for point in sampled), default=launch_height)
    surfaces = [{"id": "ground", "type": "line", "from_xy": [min(0.0, landing_x), 0.0], "to_xy": [max(landing_x, 1.0), 0.0], "label": "ground"}]
    if launch_height > 0:
        points.setdefault("drop_base", {"x": 0.0, "y": 0.0, "label": "base"})
        surfaces.append({"id": "cliff_face", "type": "vertical_drop", "from_xy": [0.0, 0.0], "to_xy": [0.0, launch_height], "label": f"h = {launch_height:g} m"})
    return {
        "schema_version": 1,
        "problem": {
            "world": world,
            "unknown": unknown,
            "constraints": ["representative_scene"],
            "engine_case": result.engine_case,
        },
        "units": {"length": "m", "time": "s", "angle": "deg", "velocity": "m/s"},
        "coordinate_frame": {"x": "horizontal", "y": "vertical", "origin": "launch"},
        "geometry": {
            "points": points,
            "surfaces": surfaces,
            "obstacles": [],
            "axes": [
                {"id": "x_axis", "direction": "horizontal"},
                {"id": "y_axis", "direction": "vertical"},
            ],
        },
        "actors": [{"id": "projectile", "type": "particle", "label": "projectile"}],
        "trajectories": [{"id": "trajectory:path", "actor": "projectile", "equation": "representative projectile path", "sampled_points": sampled}],
        "motion": {
            "kind": "representative_projectile",
            "initial": {"x": 0.0, "y": launch_height, "vx": ux, "vy": uy},
            "acceleration": {"x": 0.0, "y": -g},
            "duration": duration,
        },
        "motions": [
            {
                "actor": "projectile",
                "kind": "representative_projectile",
                "initial": {"x": 0.0, "y": launch_height, "vx": ux, "vy": uy},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": duration,
            }
        ],
        "quantities": {
            "u": {"value": u, "unit": "m/s", "label": "u"},
            "theta": {"value": theta_deg, "unit": "deg", "label": "theta"},
            "g": {"value": g, "unit": "m/s^2", "label": "g"},
            "ux": {"value": ux, "unit": "m/s", "label": "u_x"},
            "uy": {"value": uy, "unit": "m/s", "label": "u_y"},
            "T": {"value": duration, "unit": "s", "label": "T"},
            "R": {"value": landing_x, "unit": "m", "label": "R"},
            "H": {"value": max_height, "unit": "m", "label": "H"},
            "launch_height": {"value": launch_height, "unit": "m", "label": "h"},
            "h": {"value": launch_height, "unit": "m", "label": "h"},
        },
        "events": [
            {"id": "event:launch", "time": 0.0, "point": "launch", "label": "launch"},
            {"id": "event:apex", "time": max((point.get("t", 0.0) for point in sampled if point["y"] == max_height), default=duration / 2), "point": "apex", "label": "apex"},
            {"id": "event:landing", "time": duration, "point": "landing", "label": "landing"},
        ],
        "steps": _scene_steps(result),
        "warnings": warnings,
    }


def _coefficient_of_t(equation: str) -> float | None:
    match = re.search(r"=\s*([-+]?\d+(?:\.\d+)?)\s*t\b", equation.replace(" ", ""), re.IGNORECASE)
    return float(match.group(1)) if match else None


def _linear_coefficient_of_t(equation: str) -> float | None:
    match = re.search(r"=\s*([-+]?\d+(?:\.\d+)?)\s*t", equation.replace(" ", ""), re.IGNORECASE)
    return float(match.group(1)) if match else None


def _quadratic_gravity_from_y_t(equation: str) -> float | None:
    compact = equation.replace(" ", "").lower()
    match = re.search(r"([-+])(\d+(?:\.\d+)?)t\^?2", compact)
    if not match:
        return None
    sign, coeff = match.groups()
    value = float(coeff)
    return 2 * value if sign == "-" else None


def _build_projectile_slider_incline_collision_scene(
    *,
    result: EvaluationResult,
    question_text: str,
    givens: dict[str, str],
) -> dict[str, Any] | None:
    duration = _number_from_givens(givens, ["t", "time", "collision_time"]) or _first_time_from_text(question_text) or 4.0
    g = _number_from_givens(givens, ["g"]) or 10.0
    angles = _angle_numbers_from_text(question_text)
    incline_deg = _number_from_givens(givens, ["incline", "incline_angle", "alpha", "angle"]) or (angles[0] if angles else 60.0)
    alpha = math.radians(incline_deg)
    launch_speed = result.computed_value or g * duration / 4
    launch_x = 0.0
    launch_y = max(2.0, 0.55 * g * math.sin(alpha) * duration * duration)
    slider_s = 0.5 * g * math.sin(alpha) * duration * duration
    collision_x = launch_x + slider_s * math.cos(alpha)
    collision_y = launch_y - slider_s * math.sin(alpha)
    projectile_vx = (collision_x - launch_x) / duration
    projectile_vy = (collision_y - launch_y + 0.5 * g * duration * duration) / duration
    projectile_speed = math.hypot(projectile_vx, projectile_vy)
    if result.computed_value and projectile_speed > 1e-9:
        scale = launch_speed / projectile_speed
        projectile_vx *= scale
        projectile_vy *= scale
    projectile_path = _sample_projectile_path(y0=launch_y, ux=projectile_vx, uy=projectile_vy, g=g, duration=duration, count=48, x0=launch_x, clamp_to_ground=False)
    slider_path = _sample_slider_path(
        x0=launch_x,
        y0=launch_y,
        angle_rad=-alpha,
        acceleration=g * math.sin(alpha),
        duration=duration,
        count=48,
    )
    collision = slider_path[-1]
    apex = max(projectile_path, key=lambda point: point["y"])
    plane_length = max(slider_s * 1.25, 8.0)
    plane_to = [launch_x + plane_length * math.cos(alpha), launch_y - plane_length * math.sin(alpha)]
    return {
        "schema_version": 1,
        "problem": {
            "world": "incline_collision",
            "unknown": "projection_speed",
            "constraints": ["smooth_incline", "simultaneous_release", "same_start_point"],
            "engine_case": result.engine_case,
        },
        "units": {"length": "m", "time": "s", "angle": "deg", "velocity": "m/s"},
        "coordinate_frame": {"x": "horizontal", "y": "vertical", "origin": "launch"},
        "geometry": {
            "points": {
                "launch": {"x": launch_x, "y": launch_y, "label": "P,Q"},
                "collision": {"x": collision["x"], "y": collision["y"], "label": "collision"},
                "apex": {"x": apex["x"], "y": apex["y"], "label": "apex"},
                "landing": {"x": plane_to[0], "y": 0.0, "label": "reference"},
            },
            "surfaces": [
                {
                    "id": "smooth_inclined_plane",
                    "type": "inclined_plane",
                    "from_xy": [launch_x - 1.5 * math.cos(alpha), launch_y + 1.5 * math.sin(alpha)],
                    "to_xy": plane_to,
                    "label": f"smooth incline {incline_deg:g}deg",
                    "angle_deg": incline_deg,
                }
            ],
            "obstacles": [],
            "axes": [
                {"id": "x_axis", "direction": "horizontal"},
                {"id": "y_axis", "direction": "vertical"},
            ],
        },
        "actors": [
            {"id": "projectile_p", "type": "particle", "label": "P"},
            {"id": "slider_q", "type": "particle", "label": "Q"},
        ],
        "trajectories": [
            {"id": "trajectory:p", "actor": "projectile_p", "equation": "projectile under gravity", "sampled_points": projectile_path},
            {"id": "trajectory:q", "actor": "slider_q", "equation": "sliding motion along smooth incline", "sampled_points": slider_path},
        ],
        "motion": {
            "kind": "constant_gravity_projectile",
            "initial": {"x": launch_x, "y": launch_y, "vx": projectile_vx, "vy": projectile_vy},
            "acceleration": {"x": 0.0, "y": -g},
            "duration": duration,
        },
        "motions": [
            {
                "actor": "projectile_p",
                "kind": "constant_gravity_projectile",
                "initial": {"x": launch_x, "y": launch_y, "vx": projectile_vx, "vy": projectile_vy},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": duration,
            },
            {
                "actor": "slider_q",
                "kind": "constant_acceleration_slider",
                "initial": {"x": launch_x, "y": launch_y, "vx": 0.0, "vy": 0.0},
                "acceleration": {"x": g * math.sin(alpha) * math.cos(alpha), "y": -g * math.sin(alpha) * math.sin(alpha)},
                "duration": duration,
            }
        ],
        "quantities": {
            "u": {"value": launch_speed, "unit": "m/s", "label": "u_P"},
            "theta": {"value": math.degrees(math.atan2(projectile_vy, projectile_vx)), "unit": "deg", "label": "theta"},
            "alpha": {"value": incline_deg, "unit": "deg", "label": "alpha"},
            "g": {"value": g, "unit": "m/s^2", "label": "g"},
            "ux": {"value": projectile_vx, "unit": "m/s", "label": "u_x"},
            "uy": {"value": projectile_vy, "unit": "m/s", "label": "u_y"},
            "T": {"value": duration, "unit": "s", "label": "t"},
            "R": {"value": slider_s, "unit": "m", "label": "s_Q"},
            "H": {"value": apex["y"], "unit": "m", "label": "H"},
        },
        "events": [
            {"id": "event:launch", "time": 0.0, "point": "launch", "label": "P projected, Q released"},
            {"id": "event:apex", "time": max(0.0, projectile_vy / g), "point": "apex", "label": "P apex"},
            {"id": "event:collision", "time": duration, "point": "collision", "label": "P and Q collide"},
        ],
        "steps": _scene_steps(result),
        "warnings": [],
    }


def _build_staircase_scene(
    *,
    result: EvaluationResult,
    question_text: str,
    givens: dict[str, str],
) -> dict[str, Any] | None:
    vx = _number_from_givens(givens, ["vx", "v0x", "horizontal_velocity", "v0"]) or _first_speed_from_text(question_text) or 10.0
    step_height = _number_from_givens(givens, ["step_height", "y"]) or _stair_dimension_from_text(question_text, "height") or 1.0
    step_width = _number_from_givens(givens, ["step_width", "x"]) or _stair_dimension_from_text(question_text, "width") or 1.0
    g = _number_from_givens(givens, ["g"]) or 9.8
    struck_step = max(1, int(round(result.computed_value or 1)))
    visible_steps = max(struck_step + 2, 8)
    launch_height = visible_steps * step_height
    contact_drop = max(0.0, (struck_step - 1) * step_height)
    contact_time = math.sqrt(max(0.0, 2 * contact_drop / max(g, 0.001)))
    contact_x = vx * contact_time
    lower_x = (struck_step - 1) * step_width
    upper_x = struck_step * step_width
    if contact_x < lower_x or contact_x > upper_x:
        # Keep the visual honest even when OCR/default dimensions make the
        # textbook step-number condition slightly inconsistent.
        contact_x = min(max(contact_x, lower_x + 0.08 * step_width), upper_x - 0.08 * step_width)
        contact_time = contact_x / max(vx, 0.001)
        contact_drop = 0.5 * g * contact_time * contact_time
    duration = max(contact_time, 0.001)
    sampled = _sample_projectile_path(y0=launch_height, ux=vx, uy=0.0, g=g, duration=duration, count=48)
    impact_y = launch_height - contact_drop
    impact = {"x": contact_x, "y": impact_y}
    if sampled:
        sampled[-1] = impact

    surfaces: list[dict[str, Any]] = []
    for index in range(visible_steps):
        x0 = index * step_width
        x1 = (index + 1) * step_width
        y_top = launch_height - index * step_height
        y_next = launch_height - (index + 1) * step_height
        surfaces.append({
            "id": f"step_{index + 1}_tread",
            "type": "stair_tread",
            "from_xy": [x0, y_top],
            "to_xy": [x1, y_top],
            "label": "",
        })
        surfaces.append({
            "id": f"step_{index + 1}_riser",
            "type": "stair_riser",
            "from_xy": [x1, y_top],
            "to_xy": [x1, y_next],
            "label": str(index + 1) if index + 1 == struck_step else "",
        })

    return {
        "schema_version": 1,
        "problem": {
            "world": "staircase",
            "unknown": "step_number",
            "constraints": ["horizontal_launch", "vertical_faces"],
            "engine_case": result.engine_case,
        },
        "units": {"length": "m", "time": "s", "angle": "deg", "velocity": "m/s"},
        "coordinate_frame": {"x": "horizontal", "y": "vertical", "origin": "top_step"},
        "geometry": {
            "points": {
                "launch": {"x": 0.0, "y": launch_height, "label": "launch"},
                "impact": {"x": impact["x"], "y": impact["y"], "label": f"step {struck_step}"},
                "apex": {"x": 0.0, "y": launch_height, "label": "launch level"},
                "landing": {"x": visible_steps * step_width, "y": 0.0, "label": "reference"},
            },
            "surfaces": surfaces,
            "obstacles": [],
            "axes": [
                {"id": "x_axis", "direction": "horizontal"},
                {"id": "y_axis", "direction": "vertical"},
            ],
        },
        "actors": [{"id": "projectile", "type": "particle", "label": "marble"}],
        "trajectories": [
            {"id": "trajectory:path", "actor": "projectile", "equation": "x=vx t, y=y0-0.5gt^2", "sampled_points": sampled}
        ],
        "motion": {
            "kind": "constant_gravity_projectile",
            "initial": {"x": 0.0, "y": launch_height, "vx": vx, "vy": 0.0},
            "acceleration": {"x": 0.0, "y": -g},
            "duration": duration,
        },
        "motions": [
            {
                "actor": "projectile",
                "kind": "constant_gravity_projectile",
                "initial": {"x": 0.0, "y": launch_height, "vx": vx, "vy": 0.0},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": duration,
            }
        ],
        "quantities": {
            "vx": {"value": vx, "unit": "m/s", "label": "v_x"},
            "u": {"value": vx, "unit": "m/s", "label": "u"},
            "theta": {"value": 0.0, "unit": "deg", "label": "theta"},
            "g": {"value": g, "unit": "m/s^2", "label": "g"},
            "T": {"value": duration, "unit": "s", "label": "T"},
            "R": {"value": impact["x"], "unit": "m", "label": "x"},
            "H": {"value": launch_height, "unit": "m", "label": "height"},
            "step": {"value": float(struck_step), "unit": "", "label": "step"},
        },
        "events": [
            {"id": "event:launch", "time": 0.0, "point": "launch", "label": "horizontal launch"},
            {"id": "event:impact", "time": duration, "point": "impact", "label": f"strikes step {struck_step}"},
        ],
        "steps": _scene_steps(result),
        "warnings": [],
    }


def _build_split_at_apex_scene(
    *,
    result: EvaluationResult,
    question_text: str,
    givens: dict[str, str],
) -> dict[str, Any] | None:
    u = _number_from_givens(givens, ["v0", "u", "speed", "velocity"]) or _first_speed_from_text(question_text) or 5 * math.sqrt(2)
    raw_angle = _number_from_givens(givens, ["angle", "theta", "launch_angle"]) or 45.0
    theta_deg = 90.0 - raw_angle if "from the vertical" in question_text.lower() else raw_angle
    g = _number_from_givens(givens, ["g"]) or 10.0
    theta = math.radians(theta_deg)
    ux = u * math.cos(theta)
    uy = u * math.sin(theta)
    t_peak = max(uy / g, 0.001)
    apex_x = ux * t_peak
    apex_y = uy * uy / (2 * g)
    t_fall = result.computed_value or math.sqrt(2 * apex_y / g)
    frag2_vx = 2 * ux
    frag1_path = _sample_projectile_path(y0=apex_y, ux=0.0, uy=0.0, g=g, duration=t_fall, count=32, x0=apex_x)
    frag2_path = _sample_projectile_path(y0=apex_y, ux=frag2_vx, uy=0.0, g=g, duration=t_fall, count=32, x0=apex_x)
    phase1_path = _sample_projectile_path(y0=0.0, ux=ux, uy=uy, g=g, duration=t_peak, count=32)
    frag1_landing = frag1_path[-1]
    frag2_landing = frag2_path[-1]
    return {
        "schema_version": 1,
        "problem": {
            "world": "split_at_apex",
            "unknown": "fragment_fall_time",
            "constraints": ["same_height_landing", "equal_fragments", "split_at_apex"],
            "engine_case": result.engine_case,
        },
        "units": {"length": "m", "time": "s", "angle": "deg", "velocity": "m/s"},
        "coordinate_frame": {"x": "horizontal", "y": "vertical", "origin": "O"},
        "geometry": {
            "points": {
                "launch": {"x": 0.0, "y": 0.0, "label": "O"},
                "apex": {"x": apex_x, "y": apex_y, "label": "split"},
                "split": {"x": apex_x, "y": apex_y, "label": "split"},
                "fragment_1_landing": {"x": frag1_landing["x"], "y": 0.0, "label": "part 1"},
                "fragment_2_landing": {"x": frag2_landing["x"], "y": 0.0, "label": "part 2"},
                "landing": {"x": frag2_landing["x"], "y": 0.0, "label": "x"},
            },
            "surfaces": [{"id": "ground", "type": "line", "from_xy": [0.0, 0.0], "to_xy": [frag2_landing["x"] * 1.08, 0.0], "label": "ground"}],
            "obstacles": [],
            "axes": [
                {"id": "x_axis", "direction": "horizontal"},
                {"id": "y_axis", "direction": "vertical"},
            ],
        },
        "actors": [
            {"id": "projectile", "type": "particle", "label": "projectile"},
            {"id": "fragment_1", "type": "particle", "label": "part 1"},
            {"id": "fragment_2", "type": "particle", "label": "part 2"},
        ],
        "trajectories": [
            {
                "id": "trajectory:before_split",
                "actor": "projectile",
                "equation": "projectile reaches apex",
                "sampled_points": phase1_path,
                "time_window": {"start": 0.0, "end": t_peak},
            },
            {
                "id": "trajectory:fragment_1",
                "actor": "fragment_1",
                "equation": "vertical fall from apex",
                "sampled_points": frag1_path,
                "time_window": {"start": t_peak, "end": t_peak + t_fall},
            },
            {
                "id": "trajectory:fragment_2",
                "actor": "fragment_2",
                "equation": "horizontal momentum carried by second fragment",
                "sampled_points": frag2_path,
                "time_window": {"start": t_peak, "end": t_peak + t_fall},
            },
        ],
        "motion": {
            "kind": "constant_gravity_projectile",
            "initial": {"x": 0.0, "y": 0.0, "vx": ux, "vy": uy},
            "acceleration": {"x": 0.0, "y": -g},
            "duration": t_peak,
        },
        "motions": [
            {
                "actor": "projectile",
                "kind": "constant_gravity_projectile",
                "initial": {"x": 0.0, "y": 0.0, "vx": ux, "vy": uy},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": t_peak,
                "time_window": {"start": 0.0, "end": t_peak},
            },
            {
                "actor": "fragment_1",
                "kind": "constant_gravity_projectile",
                "initial": {"x": apex_x, "y": apex_y, "vx": 0.0, "vy": 0.0},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": t_fall,
                "time_window": {"start": t_peak, "end": t_peak + t_fall},
            },
            {
                "actor": "fragment_2",
                "kind": "constant_gravity_projectile",
                "initial": {"x": apex_x, "y": apex_y, "vx": frag2_vx, "vy": 0.0},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": t_fall,
                "time_window": {"start": t_peak, "end": t_peak + t_fall},
            },
        ],
        "quantities": {
            "u": {"value": u, "unit": "m/s", "label": "u"},
            "theta": {"value": theta_deg, "unit": "deg", "label": "theta"},
            "g": {"value": g, "unit": "m/s^2", "label": "g"},
            "ux": {"value": ux, "unit": "m/s", "label": "u_x"},
            "uy": {"value": uy, "unit": "m/s", "label": "u_y"},
            "T": {"value": t_fall, "unit": "s", "label": "t"},
            "t_peak": {"value": t_peak, "unit": "s", "label": "t_peak"},
            "R": {"value": frag2_landing["x"], "unit": "m", "label": "x"},
            "H": {"value": apex_y, "unit": "m", "label": "H"},
            "v_fragment_2": {"value": frag2_vx, "unit": "m/s", "label": "v_2x"},
        },
        "events": [
            {"id": "event:launch", "time": 0.0, "point": "launch", "label": "launch"},
            {"id": "event:apex", "time": t_peak, "point": "apex", "label": "split at apex"},
            {"id": "event:landing", "time": t_peak + t_fall, "point": "fragment_2_landing", "label": "fragment lands"},
        ],
        "steps": _scene_steps(result),
        "warnings": [],
    }


def _build_single_incline_scene(
    *,
    result: EvaluationResult,
    question_text: str,
    givens: dict[str, str],
) -> dict[str, Any] | None:
    g = _number_from_givens(givens, ["g"]) or 10.0
    angles = _angle_numbers_from_text(question_text)
    incline_keys = ["incline", "incline_angle", "alpha", "beta"]
    if result.engine_case == "perpendicular_launch_range_on_incline":
        incline_keys.append("angle")
    default_incline_deg = 37.0 if result.engine_case == "motion_on_smooth_incline_perpendicular_to_slope" else 30.0
    incline_deg = _number_from_givens(givens, incline_keys) or (angles[0] if angles else default_incline_deg)
    u = _number_from_givens(givens, ["v0", "u", "speed", "velocity"]) or _first_speed_from_text(question_text) or 10.0
    warning = ""
    if not angles and not _number_from_givens(givens, incline_keys):
        warning = f"Symbolic incline angles are visualized with alpha={default_incline_deg:g}deg as a representative case."

    alpha = math.radians(incline_deg)
    if result.engine_case == "horizontal_launch_onto_incline_distance":
        launch_angle = 0.0
        launch_height = max(4.0, (result.computed_value or 4.0) / math.sqrt(2))
        duration = 2 * u / g
        x0 = 0.0
        y0 = launch_height
        plane_from = [0.0, launch_height]
        plane_to = [launch_height / math.tan(alpha or math.radians(45)), 0.0] if not math.isclose(math.tan(alpha), 0.0) else [launch_height, 0.0]
    else:
        if result.engine_case == "perpendicular_launch_range_on_incline":
            # The standard DPP diagram is a plane descending to the right, with
            # launch perpendicular to the plane. Use that orientation so the
            # simulated projectile moves toward the impact point instead of
            # producing a backwards, near-infinite scene.
            launch_angle = math.pi / 2 - alpha
        elif result.engine_case == "max_range_on_incline":
            launch_angle = alpha + math.radians(45.0) - alpha / 2
            if not warning and not result.computed_value:
                warning = "Symbolic maximum-range result is visualized with representative speed/angle values."
        elif result.engine_case == "inclined_plane_right_angle_impact_condition":
            launch_angle = math.atan(1 / (2 * math.tan(alpha))) if not math.isclose(math.tan(alpha), 0.0) else math.radians(60)
        else:
            launch_angle = math.radians(_number_from_givens(givens, ["launch_angle_horizontal", "launch_angle", "theta", "angle"]) or (angles[1] if len(angles) > 1 else incline_deg + 45.0))
        x0 = 0.0
        y0 = 0.0
        duration = result.computed_value if result.engine_case == "inclined_plane_impact_time" and result.computed_value else None
        if duration is None:
            denominator = g * math.cos(launch_angle) * math.cos(launch_angle)
            if result.engine_case == "perpendicular_launch_range_on_incline" and result.computed_value:
                range_along = max(result.computed_value, 0.5)
                impact_x = range_along * math.cos(alpha)
                duration = impact_x / max(abs(u * math.cos(launch_angle)), 0.001)
            elif result.engine_case in {"max_range_on_incline"} and result.computed_value:
                range_along = max(result.computed_value, 0.5)
                impact_x = range_along * math.cos(alpha)
                duration = impact_x / max(u * math.cos(launch_angle), 0.001)
            else:
                duration = max(2 * u * max(math.sin(launch_angle - alpha), 0.25) / max(g * math.cos(alpha), 0.001), 0.8)
        if result.engine_case == "perpendicular_launch_range_on_incline":
            visible_length = max((result.computed_value or 4.0) * 1.25, 5.0)
            plane_from = [-0.18 * visible_length * math.cos(alpha), 0.18 * visible_length * math.sin(alpha)]
            plane_to = [visible_length * math.cos(alpha), -visible_length * math.sin(alpha)]
        else:
            plane_from = [0.0, 0.0]
            end_x = max(u * math.cos(launch_angle) * duration * 1.2, 5.0)
            plane_to = [end_x, math.tan(alpha) * end_x]

    ux = u * math.cos(launch_angle)
    uy = u * math.sin(launch_angle)
    duration = max(float(duration), 0.001)
    sampled = _sample_projectile_path(
        y0=y0,
        ux=ux,
        uy=uy,
        g=g,
        duration=duration,
        count=48,
        x0=x0,
        clamp_to_ground=result.engine_case not in {
            "perpendicular_launch_range_on_incline",
            "horizontal_launch_onto_incline_distance",
            "projectile_collides_with_sliding_particle_on_incline",
        },
    )
    impact = sampled[-1]
    apex = max(sampled, key=lambda point: point["y"])
    range_on_surface = math.hypot(impact["x"] - x0, impact["y"] - y0)
    if result.engine_case in {
        "perpendicular_launch_range_on_incline",
        "max_range_on_incline",
        "horizontal_launch_onto_incline_distance",
    } and result.computed_value:
        range_on_surface = abs(float(result.computed_value))
    warnings = [warning] if warning else []
    if result.engine_case == "inclined_plane_max_normal_distance_velocity_component":
        warnings.append("Symbolic theta/beta scene uses representative geometry; the zero normal-velocity conclusion is invariant.")

    return {
        "schema_version": 1,
        "problem": {
            "world": "incline",
            "unknown": _unknown_for_case(result.engine_case, question_text),
            "constraints": ["inclined_plane"],
            "engine_case": result.engine_case,
        },
        "units": {"length": "m", "time": "s", "angle": "deg", "velocity": "m/s"},
        "coordinate_frame": {"x": "horizontal", "y": "vertical", "origin": "launch"},
        "geometry": {
            "points": {
                "launch": {"x": x0, "y": y0, "label": "launch"},
                "impact": {"x": impact["x"], "y": impact["y"], "label": "impact"},
                "apex": {"x": apex["x"], "y": apex["y"], "label": "apex"},
                "landing": {"x": max(impact["x"], plane_to[0]), "y": 0.0, "label": "reference"},
            },
            "surfaces": [
                {
                    "id": "inclined_plane",
                    "type": "inclined_plane",
                    "from_xy": plane_from,
                    "to_xy": plane_to,
                    "label": f"incline {incline_deg:g}deg",
                    "angle_deg": incline_deg,
                }
            ],
            "obstacles": [],
            "axes": [
                {"id": "x_axis", "direction": "horizontal"},
                {"id": "y_axis", "direction": "vertical"},
            ],
        },
        "actors": [{"id": "projectile", "type": "particle", "label": "projectile"}],
        "trajectories": [
            {"id": "trajectory:path", "actor": "projectile", "equation": "constant gravity relative to an inclined plane", "sampled_points": sampled}
        ],
        "motion": {
            "kind": "constant_gravity_projectile",
            "initial": {"x": x0, "y": y0, "vx": ux, "vy": uy},
            "acceleration": {"x": 0.0, "y": -g},
            "duration": duration,
        },
        "motions": [
            {
                "actor": "projectile",
                "kind": "constant_gravity_projectile",
                "initial": {"x": x0, "y": y0, "vx": ux, "vy": uy},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": duration,
            }
        ],
        "quantities": {
            "u": {"value": u, "unit": "m/s", "label": "u"},
            "theta": {"value": math.degrees(launch_angle), "unit": "deg", "label": "theta"},
            "alpha": {"value": incline_deg, "unit": "deg", "label": "alpha"},
            "g": {"value": g, "unit": "m/s^2", "label": "g"},
            "ux": {"value": ux, "unit": "m/s", "label": "u_x"},
            "uy": {"value": uy, "unit": "m/s", "label": "u_y"},
            "T": {"value": duration, "unit": "s", "label": "T"},
            "R": {"value": range_on_surface, "unit": "m", "label": "range on incline"},
            "H": {"value": apex["y"], "unit": "m", "label": "H"},
        },
        "events": [
            {"id": "event:launch", "time": 0.0, "point": "launch", "label": "launch"},
            {"id": "event:apex", "time": max(0.0, uy / g), "point": "apex", "label": "apex"},
            {"id": "event:impact", "time": duration, "point": "impact", "label": "incline event"},
        ],
        "steps": _scene_steps(result),
        "warnings": warnings,
    }


def _build_two_incline_transfer_scene(
    *,
    result: EvaluationResult,
    question_text: str,
    givens: dict[str, str],
) -> dict[str, Any] | None:
    u = _number_from_givens(givens, ["u", "v0", "velocity"]) or _first_speed_from_text(question_text) or 10 * math.sqrt(3)
    angles = _angle_numbers_from_text(question_text)
    left_incline_deg = angles[0] if angles else 30.0
    right_incline_deg = angles[1] if len(angles) > 1 else 60.0
    g = _number_from_givens(givens, ["g"]) or 10.0
    impact_speed = result.computed_value or 10.0

    left_line_angle = -math.radians(left_incline_deg)
    right_line_angle = math.radians(right_incline_deg)
    launch_angle = left_line_angle + math.pi / 2
    impact_velocity_angle = right_line_angle - math.pi / 2
    ux = u * math.cos(launch_angle)
    uy = u * math.sin(launch_angle)
    final_vy = impact_speed * math.sin(impact_velocity_angle)
    duration = max((uy - final_vy) / g, 0.001)

    tan_left = math.tan(left_line_angle)
    tan_right = math.tan(right_line_angle)
    denominator = tan_left - tan_right
    if math.isclose(denominator, 0.0, abs_tol=1e-9):
        return None
    p_x = (tan_right * ux * duration - uy * duration + 0.5 * g * duration * duration) / denominator
    p_y = tan_left * p_x
    q_x = p_x + ux * duration
    q_y = p_y + uy * duration - 0.5 * g * duration * duration
    sampled = _sample_projectile_path(y0=p_y, ux=ux, uy=uy, g=g, duration=duration, count=40, x0=p_x)
    apex = max(sampled, key=lambda point: point["y"])

    plane_left_x = min(p_x * 1.35, p_x - 2)
    plane_right_x = max(q_x * 1.25, q_x + 2)
    return {
        "schema_version": 1,
        "problem": {
            "world": "two_inclines",
            "unknown": "impact_speed",
            "constraints": ["launch_perpendicular_to_OA", "impact_perpendicular_to_OB"],
            "engine_case": result.engine_case,
        },
        "units": {"length": "m", "time": "s", "angle": "deg", "velocity": "m/s"},
        "coordinate_frame": {"x": "horizontal", "y": "vertical", "origin": "O"},
        "geometry": {
            "points": {
                "O": {"x": 0.0, "y": 0.0, "label": "O"},
                "launch": {"x": p_x, "y": p_y, "label": "P"},
                "P": {"x": p_x, "y": p_y, "label": "P"},
                "Q": {"x": q_x, "y": q_y, "label": "Q"},
                "impact": {"x": q_x, "y": q_y, "label": "Q"},
                "apex": {"x": apex["x"], "y": apex["y"], "label": "apex"},
                "landing": {"x": q_x, "y": 0.0, "label": "reference"},
            },
            "surfaces": [
                {
                    "id": "plane_OA",
                    "type": "inclined_plane",
                    "from_xy": [plane_left_x, tan_left * plane_left_x],
                    "to_xy": [0.0, 0.0],
                    "label": "OA",
                    "angle_deg": left_incline_deg,
                },
                {
                    "id": "plane_OB",
                    "type": "inclined_plane",
                    "from_xy": [0.0, 0.0],
                    "to_xy": [plane_right_x, tan_right * plane_right_x],
                    "label": "OB",
                    "angle_deg": right_incline_deg,
                },
            ],
            "obstacles": [],
            "axes": [
                {"id": "x_axis", "direction": "horizontal"},
                {"id": "y_axis", "direction": "vertical"},
            ],
        },
        "actors": [{"id": "projectile", "type": "particle", "label": "projectile"}],
        "trajectories": [
            {"id": "trajectory:path", "actor": "projectile", "equation": "constant gravity between inclined planes", "sampled_points": sampled}
        ],
        "motion": {
            "kind": "constant_gravity_projectile",
            "initial": {"x": p_x, "y": p_y, "vx": ux, "vy": uy},
            "acceleration": {"x": 0.0, "y": -g},
            "duration": duration,
        },
        "motions": [
            {
                "actor": "projectile",
                "kind": "constant_gravity_projectile",
                "initial": {"x": p_x, "y": p_y, "vx": ux, "vy": uy},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": duration,
            }
        ],
        "quantities": {
            "u": {"value": u, "unit": "m/s", "label": "u"},
            "theta": {"value": math.degrees(launch_angle), "unit": "deg", "label": "launch angle"},
            "g": {"value": g, "unit": "m/s^2", "label": "g"},
            "ux": {"value": ux, "unit": "m/s", "label": "u_x"},
            "uy": {"value": uy, "unit": "m/s", "label": "u_y"},
            "T": {"value": duration, "unit": "s", "label": "T"},
            "H": {"value": apex["y"], "unit": "m", "label": "H"},
            "R": {"value": q_x - p_x, "unit": "m", "label": "horizontal span"},
            "v_impact": {"value": impact_speed, "unit": "m/s", "label": "v_Q"},
        },
        "events": [
            {"id": "event:launch", "time": 0.0, "point": "P", "label": "normal launch from OA"},
            {"id": "event:apex", "time": max(0.0, uy / g), "point": "apex", "label": "apex"},
            {"id": "event:impact", "time": duration, "point": "Q", "label": "normal impact on OB"},
        ],
        "steps": _scene_steps(result),
        "warnings": [],
    }


def _build_interception_ratio_scene(
    *,
    result: EvaluationResult,
    question_text: str,
    givens: dict[str, str],
) -> dict[str, Any] | None:
    pairs = _interception_angle_pairs(question_text)
    if len(pairs) < 2:
        return None
    v0 = _number_from_givens(givens, ["v0", "u", "speed", "velocity"]) or 20.0
    g = _number_from_givens(givens, ["g"]) or 10.0
    base_l = _number_from_givens(givens, ["L", "distance"]) or 100.0
    x_gap = base_l * 1.42
    trajectories = []
    motions = []
    points: dict[str, dict[str, Any]] = {}
    quantities: dict[str, dict[str, Any]] = {
        "g": {"value": g, "unit": "m/s^2", "label": "g"},
        "ratio_squared": {"value": result.computed_value or 0.0, "unit": "", "label": "(T1/T2)^2"},
    }
    max_height = 0.0
    for index, (theta0_deg, theta1_deg) in enumerate(pairs[:2], start=1):
        theta0 = math.radians(theta0_deg)
        theta1 = math.radians(theta1_deg)
        stone_speed = v0 * math.sin(theta0) / math.sin(theta1)
        denom = math.cos(theta0) + math.sin(theta0) / math.tan(theta1)
        duration = base_l / (v0 * denom)
        offset = (index - 1) * x_gap
        ball_vx = v0 * math.cos(theta0)
        ball_vy = v0 * math.sin(theta0)
        stone_vx = -stone_speed * math.cos(theta1)
        stone_vy = stone_speed * math.sin(theta1)
        ball_path = _sample_projectile_path(y0=0.0, ux=ball_vx, uy=ball_vy, g=g, duration=duration, count=32, x0=offset)
        stone_path = _sample_projectile_path(y0=0.0, ux=stone_vx, uy=stone_vy, g=g, duration=duration, count=32, x0=offset + base_l)
        collision = ball_path[-1]
        max_height = max(max_height, *(point["y"] for point in ball_path + stone_path))
        points[f"launch_ball_{index}"] = {"x": offset, "y": 0.0, "label": f"B{index}"}
        points[f"launch_stone_{index}"] = {"x": offset + base_l, "y": 0.0, "label": f"S{index}"}
        points[f"collision_{index}"] = {"x": collision["x"], "y": collision["y"], "label": f"T{index}"}
        trajectories.extend([
            {"id": f"trajectory:ball:{index}", "actor": f"ball_{index}", "equation": "ball scenario", "sampled_points": ball_path},
            {"id": f"trajectory:stone:{index}", "actor": f"stone_{index}", "equation": "stone scenario", "sampled_points": stone_path},
        ])
        motions.extend([
            {
                "actor": f"ball_{index}",
                "kind": "constant_gravity_projectile",
                "initial": {"x": offset, "y": 0.0, "vx": ball_vx, "vy": ball_vy},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": duration,
            },
            {
                "actor": f"stone_{index}",
                "kind": "constant_gravity_projectile",
                "initial": {"x": offset + base_l, "y": 0.0, "vx": stone_vx, "vy": stone_vy},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": duration,
            },
        ])
        quantities[f"T{index}"] = {"value": duration, "unit": "s", "label": f"T{index}"}
        quantities[f"theta0_{index}"] = {"value": theta0_deg, "unit": "deg", "label": f"theta0_{index}"}
        quantities[f"theta1_{index}"] = {"value": theta1_deg, "unit": "deg", "label": f"theta1_{index}"}

    points["launch"] = points["launch_ball_1"]
    points["landing"] = {"x": x_gap + base_l, "y": 0.0, "label": "reference"}
    points["collision"] = points["collision_1"]
    points["apex"] = {"x": base_l * 0.35, "y": max_height, "label": "comparison apex"}
    return {
        "schema_version": 1,
        "problem": {
            "world": "multi_projectile",
            "unknown": "time_ratio_squared",
            "constraints": ["simultaneous_launch", "same_gravity", "side_by_side_comparison"],
            "engine_case": result.engine_case,
        },
        "units": {"length": "m", "time": "s", "angle": "deg", "velocity": "m/s"},
        "coordinate_frame": {"x": "horizontal", "y": "vertical", "origin": "scenario_1_ball"},
        "geometry": {
            "points": points,
            "surfaces": [{"id": "ground", "type": "line", "from": "launch", "to": "landing"}],
            "obstacles": [],
            "axes": [
                {"id": "x_axis", "direction": "horizontal"},
                {"id": "y_axis", "direction": "vertical"},
            ],
        },
        "actors": [{"id": motion["actor"], "type": "particle", "label": str(motion["actor"])} for motion in motions],
        "trajectories": trajectories,
        "motions": motions,
        "motion": motions[0],
        "quantities": quantities,
        "events": [
            {"id": "event:launch", "time": 0.0, "point": "launch", "label": "simultaneous launches"},
            {"id": "event:collision", "time": quantities["T1"]["value"], "point": "collision_1", "label": "scenario 1 intercept"},
            {"id": "event:collision_2", "time": quantities["T2"]["value"], "point": "collision_2", "label": "scenario 2 intercept"},
        ],
        "steps": _scene_steps(result),
        "warnings": ["Comparison view uses side-by-side scenarios with the same L and v0 scale."],
    }


def _build_two_projectile_collision_scene(
    *,
    result: EvaluationResult,
    spec_world: str,
    givens: dict[str, str],
) -> dict[str, Any] | None:
    duration = result.computed_value
    if duration is None:
        return None
    p1_x = _number_from_givens(givens, ["p1_x0", "x1", "a_x0"]) or 0.0
    p1_y = _number_from_givens(givens, ["p1_y0", "y1", "a_y0"]) or 0.0
    p2_x = _number_from_givens(givens, ["p2_x0", "x2", "b_x0"])
    p2_y = _number_from_givens(givens, ["p2_y0", "y2", "b_y0"]) or 0.0
    p1_vx = _number_from_givens(givens, ["p1_vx", "a_vx", "vx1"])
    p1_vy = _number_from_givens(givens, ["p1_vy", "a_vy", "vy1"])
    p2_vx = _number_from_givens(givens, ["p2_vx", "b_vx", "vx2"])
    p2_vy = _number_from_givens(givens, ["p2_vy", "b_vy", "vy2"])
    if None in {p2_x, p1_vx, p1_vy, p2_vx, p2_vy}:
        return None

    g = _number_from_givens(givens, ["g"]) or 10.0
    p2_x = float(p2_x)
    p1_vx = float(p1_vx)
    p1_vy = float(p1_vy)
    p2_vx = float(p2_vx)
    p2_vy = float(p2_vy)
    duration = max(duration, 0.001)
    p1_path = _sample_projectile_path(y0=p1_y, ux=p1_vx, uy=p1_vy, g=g, duration=duration, count=32, x0=p1_x)
    p2_path = _sample_projectile_path(y0=p2_y, ux=p2_vx, uy=p2_vy, g=g, duration=duration, count=32, x0=p2_x)
    collision = p1_path[-1]
    max_y = max(point["y"] for point in p1_path + p2_path)
    min_x = min(point["x"] for point in p1_path + p2_path)
    max_x = max(point["x"] for point in p1_path + p2_path)
    return {
        "schema_version": 1,
        "problem": {
            "world": "multi_projectile",
            "unknown": "collision_time",
            "constraints": ["simultaneous_launch", "same_gravity"],
            "engine_case": result.engine_case,
        },
        "units": {"length": "m", "time": "s", "angle": "deg", "velocity": "m/s"},
        "coordinate_frame": {"x": "horizontal", "y": "vertical", "origin": "world"},
        "geometry": {
            "points": {
                "launch": {"x": p1_x, "y": p1_y, "label": "A"},
                "launch_a": {"x": p1_x, "y": p1_y, "label": "A"},
                "launch_b": {"x": p2_x, "y": p2_y, "label": "B"},
                "collision": {"x": collision["x"], "y": collision["y"], "label": "collision"},
                "landing": {"x": max_x, "y": 0.0, "label": "ground reference"},
            },
            "surfaces": [{"id": "ground", "type": "line", "from": "launch_a", "to": "landing"}],
            "obstacles": [],
            "axes": [
                {"id": "x_axis", "direction": "horizontal"},
                {"id": "y_axis", "direction": "vertical"},
            ],
        },
        "actors": [
            {"id": "projectile_a", "type": "particle", "label": "projectile A"},
            {"id": "projectile_b", "type": "particle", "label": "projectile B"},
        ],
        "trajectories": [
            {"id": "trajectory:a", "actor": "projectile_a", "equation": "r_a = r_a0 + v_a t + 0.5gt^2", "sampled_points": p1_path},
            {"id": "trajectory:b", "actor": "projectile_b", "equation": "r_b = r_b0 + v_b t + 0.5gt^2", "sampled_points": p2_path},
        ],
        "motions": [
            {
                "actor": "projectile_a",
                "kind": "constant_gravity_projectile",
                "initial": {"x": p1_x, "y": p1_y, "vx": p1_vx, "vy": p1_vy},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": duration,
            },
            {
                "actor": "projectile_b",
                "kind": "constant_gravity_projectile",
                "initial": {"x": p2_x, "y": p2_y, "vx": p2_vx, "vy": p2_vy},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": duration,
            },
        ],
        "motion": {
            "kind": "constant_gravity_projectile",
            "initial": {"x": p1_x, "y": p1_y, "vx": p1_vx, "vy": p1_vy},
            "acceleration": {"x": 0.0, "y": -g},
            "duration": duration,
        },
        "quantities": {
            "T": {"value": duration, "unit": "s", "label": "T"},
            "g": {"value": g, "unit": "m/s^2", "label": "g"},
            "A_vx": {"value": p1_vx, "unit": "m/s", "label": "A v_x"},
            "A_vy": {"value": p1_vy, "unit": "m/s", "label": "A v_y"},
            "B_vx": {"value": p2_vx, "unit": "m/s", "label": "B v_x"},
            "B_vy": {"value": p2_vy, "unit": "m/s", "label": "B v_y"},
            "H": {"value": max_y, "unit": "m", "label": "H"},
            "R": {"value": max_x - min_x, "unit": "m", "label": "span"},
        },
        "events": [
            {"id": "event:launch", "time": 0.0, "point": "launch_a", "label": "simultaneous launch"},
            {"id": "event:collision", "time": duration, "point": "collision", "label": "collision"},
        ],
        "steps": _scene_steps(result),
        "warnings": [],
    }


def _build_two_projectile_same_speed_comparison_scene(
    *,
    result: EvaluationResult,
    givens: dict[str, str],
) -> dict[str, Any] | None:
    u = _number_from_givens(givens, ["v0", "u", "speed", "velocity"])
    angle1 = _number_from_givens(givens, ["angle1", "theta1", "angle_a"])
    angle2 = _number_from_givens(givens, ["angle2", "theta2", "angle_b"])
    if None in {u, angle1, angle2}:
        return None
    u = float(u)
    angle1 = float(angle1)
    angle2 = float(angle2)
    g = _number_from_givens(givens, ["g"]) or 10.0

    def components(angle_deg: float) -> tuple[float, float, float, float, float]:
        theta = math.radians(angle_deg)
        ux = u * math.cos(theta)
        uy = u * math.sin(theta)
        duration = max(0.001, 2 * uy / g)
        horizontal_range = ux * duration
        height = uy * uy / (2 * g)
        return ux, uy, duration, horizontal_range, height

    ux1, uy1, t1, r1, h1 = components(angle1)
    ux2, uy2, t2, r2, h2 = components(angle2)
    path1 = _sample_projectile_path(y0=0.0, ux=ux1, uy=uy1, g=g, duration=t1, count=34, x0=0.0)
    path2 = _sample_projectile_path(y0=0.0, ux=ux2, uy=uy2, g=g, duration=t2, count=34, x0=0.0)
    landing_x = max(r1, r2)
    return {
        "schema_version": 1,
        "problem": {
            "world": "multi_projectile",
            "unknown": "time_height_range_comparison",
            "constraints": ["same_speed", "same_height_landing", "compare_angles"],
            "engine_case": result.engine_case,
        },
        "units": {"length": "m", "time": "s", "angle": "deg", "velocity": "m/s"},
        "coordinate_frame": {"x": "horizontal", "y": "vertical", "origin": "launch"},
        "geometry": {
            "points": {
                "launch": {"x": 0.0, "y": 0.0, "label": "O"},
                "landing": {"x": landing_x, "y": 0.0, "label": "same range"},
                "apex_a": {"x": ux1 * t1 / 2, "y": h1, "label": f"H({angle1:g}deg)"},
                "apex_b": {"x": ux2 * t2 / 2, "y": h2, "label": f"H({angle2:g}deg)"},
            },
            "surfaces": [{"id": "ground", "type": "line", "from": "launch", "to": "landing"}],
            "obstacles": [],
            "axes": [
                {"id": "x_axis", "direction": "horizontal"},
                {"id": "y_axis", "direction": "vertical"},
            ],
        },
        "actors": [
            {"id": "projectile_a", "type": "particle", "label": f"{angle1:g}deg projectile"},
            {"id": "projectile_b", "type": "particle", "label": f"{angle2:g}deg projectile"},
        ],
        "trajectories": [
            {"id": "trajectory:a", "actor": "projectile_a", "equation": "R = u^2 sin(2theta)/g", "sampled_points": path1},
            {"id": "trajectory:b", "actor": "projectile_b", "equation": "R = u^2 sin(2theta)/g", "sampled_points": path2},
        ],
        "motions": [
            {
                "actor": "projectile_a",
                "kind": "constant_gravity_projectile",
                "initial": {"x": 0.0, "y": 0.0, "vx": ux1, "vy": uy1},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": t1,
            },
            {
                "actor": "projectile_b",
                "kind": "constant_gravity_projectile",
                "initial": {"x": 0.0, "y": 0.0, "vx": ux2, "vy": uy2},
                "acceleration": {"x": 0.0, "y": -g},
                "duration": t2,
            },
        ],
        "motion": {
            "actor": "projectile_a",
            "kind": "constant_gravity_projectile",
            "initial": {"x": 0.0, "y": 0.0, "vx": ux1, "vy": uy1},
            "acceleration": {"x": 0.0, "y": -g},
            "duration": max(t1, t2),
        },
        "quantities": {
            "u": {"value": u, "unit": "m/s"},
            "angle1": {"value": angle1, "unit": "deg"},
            "angle2": {"value": angle2, "unit": "deg"},
            "T1": {"value": t1, "unit": "s"},
            "T2": {"value": t2, "unit": "s"},
            "H1": {"value": h1, "unit": "m"},
            "H2": {"value": h2, "unit": "m"},
            "R1": {"value": r1, "unit": "m"},
            "R2": {"value": r2, "unit": "m"},
            "g": {"value": g, "unit": "m/s^2"},
        },
        "events": [
            {"id": "event:launch", "time": 0.0, "point": "launch", "label": "same speed launch"},
            {"id": "event:landing_a", "time": t1, "point": "landing", "label": f"{angle1:g}deg lands"},
            {"id": "event:landing_b", "time": t2, "point": "landing", "label": f"{angle2:g}deg lands"},
        ],
        "steps": _scene_steps(result),
        "warnings": ["Comparison view overlays the two same-speed trajectories from a common launch point."],
    }


def _scene_steps(result: EvaluationResult) -> list[dict[str, Any]]:
    plan_steps = (result.equation_plan or {}).get("steps") or []
    plan = result.equation_plan or {}
    if not plan_steps and not plan.get("invariant"):
        return []
    scene_steps: list[dict[str, Any]] = []
    if plan.get("invariant"):
        focus = _scene_invariant_focus(result)
        visual_action = _scene_visual_action("invariant", "Given and what to find", "", focus)
        scene_steps.append({
            "id": "invariant",
            "title": "Given and what to find",
            "equation_step_id": "invariant",
            "student_goal": _scene_student_goal({"title": "Given and what to find"}, result),
            "concept_used": _scene_concept({"id": "invariant"}, result),
            "equation": "",
            "substitution": "",
            "visual_action": visual_action,
            "focus_ids": focus,
            "reveal_ids": focus,
            "highlight_ids": focus,
            "camera_target_ids": _camera_targets_for_visual_action(visual_action, focus),
            "overlays": _overlays_for_step("invariant", focus, visual_action),
        })
    for step in plan_steps:
        step_id = str(step.get("id", "step"))
        focus = list(step.get("focus_ids") or _focus_for_step(step_id))
        title = str(step.get("title", step_id))
        equation = str(step.get("equation", ""))
        visual_action = _scene_visual_action(step_id, title, equation, focus)
        scene_steps.append(
            {
                "id": step_id,
                "title": title,
                "equation_step_id": step_id,
                "student_goal": _scene_student_goal(step, result),
                "concept_used": _scene_concept(step, result),
                "equation": equation,
                "substitution": step.get("substitution", ""),
                "visual_action": visual_action,
                "focus_ids": focus,
                "reveal_ids": focus,
                "highlight_ids": focus,
                "camera_target_ids": _camera_targets_for_visual_action(visual_action, focus),
                "overlays": _overlays_for_step(step_id, focus, visual_action),
            }
        )
    return scene_steps


def _attach_storyboard_contract(scene: dict[str, Any], *, result: EvaluationResult) -> dict[str, Any]:
    steps = scene.get("steps") or _scene_steps(result)
    scene["steps"] = steps
    scene["live_vectors"] = _live_vectors_for_scene(scene)
    scene["camera_bookmarks"] = _camera_bookmarks_for_scene(scene)
    scene["beat_visual_plans"] = _beat_visual_plans(result)
    scene["storyboard"] = _storyboard_for_scene(scene, result=result)
    scene["schema_version"] = max(int(scene.get("schema_version") or 1), 2)
    return scene


def _beat_visual_plans(result: EvaluationResult) -> dict[str, dict[str, Any]]:
    try:
        walkthrough = build_solution_walkthrough(result)
    except Exception:
        return {}
    plans: dict[str, dict[str, Any]] = {}
    for beat in walkthrough.get("explainer_beats") or []:
        step_id = str(beat.get("step_id") or beat.get("id") or "")
        visual_plan = beat.get("visual_plan") or {}
        if step_id and isinstance(visual_plan, dict):
            plans[step_id] = visual_plan
    return plans


def _live_vectors_for_scene(scene: dict[str, Any]) -> list[dict[str, Any]]:
    motions = scene.get("motions") or []
    if not motions and scene.get("motion"):
        motions = [{"actor": "projectile", **scene["motion"]}]
    vectors: list[dict[str, Any]] = []
    for motion in motions:
        actor = str(motion.get("actor") or "projectile")
        actor_prefix = actor.replace("projectile_", "").replace("ball_", "B").replace("stone_", "S")
        vectors.extend([
            {
                "id": f"{actor}:v",
                "actor": actor,
                "kind": "velocity",
                "component": "velocity",
                "anchor": "current_position",
                "label": f"{actor_prefix} v(t)",
                "role": "instantaneous velocity tangent to trajectory",
            },
            {
                "id": f"{actor}:vx",
                "actor": actor,
                "kind": "component",
                "component": "x_velocity",
                "anchor": "current_position",
                "label": "v_x",
                "role": "horizontal velocity component",
            },
            {
                "id": f"{actor}:vy",
                "actor": actor,
                "kind": "component",
                "component": "y_velocity",
                "anchor": "current_position",
                "label": "v_y",
                "role": "vertical velocity component",
            },
            {
                "id": f"{actor}:a",
                "actor": actor,
                "kind": "acceleration",
                "component": "acceleration",
                "anchor": "current_position",
                "label": "g",
                "role": "constant gravitational acceleration",
            },
        ])
    axis_ids = {
        str(axis.get("id") or "")
        for axis in (scene.get("geometry", {}).get("axes") or [])
        if axis.get("id")
    }
    if "x_axis" in axis_ids:
        vectors.append({
            "id": "x_axis",
            "actor": str((motions[0] if motions else {}).get("actor") or "projectile"),
            "kind": "axis",
            "component": "horizontal_axis",
            "anchor": "launch",
            "label": "x-axis",
            "role": "horizontal reference axis",
        })
    if "y_axis" in axis_ids:
        vectors.append({
            "id": "y_axis",
            "actor": str((motions[0] if motions else {}).get("actor") or "projectile"),
            "kind": "axis",
            "component": "vertical_axis",
            "anchor": "launch",
            "label": "y-axis",
            "role": "vertical reference axis",
        })
    if any(surface.get("type") == "inclined_plane" for surface in scene.get("geometry", {}).get("surfaces", [])):
        primary_motion = motions[0] if motions else {}
        primary_actor = str(primary_motion.get("actor") or (scene.get("actors") or [{}])[0].get("id") or "projectile")
        vectors.extend([
            {
                "id": "incline:tangent_axis",
                "actor": "projectile",
                "kind": "axis",
                "component": "incline_tangent",
                "anchor": "launch",
                "label": "along plane",
                "role": "axis parallel to the incline",
            },
            {
                "id": "incline:normal_axis",
                "actor": "projectile",
                "kind": "axis",
                "component": "incline_normal",
                "anchor": "launch",
                "label": "normal",
                "role": "axis perpendicular to the incline",
            },
            {
                "id": "gravity:tangent_component",
                "actor": primary_actor,
                "kind": "component",
                "component": "gravity_tangent",
                "anchor": "launch",
                "label": "g sin alpha",
                "role": "gravity component along the incline",
            },
            {
                "id": "gravity:normal_component",
                "actor": primary_actor,
                "kind": "component",
                "component": "gravity_normal",
                "anchor": "launch",
                "label": "g cos alpha",
                "role": "gravity component normal to the incline",
            },
            {
                "id": "velocity:tangent_component",
                "actor": primary_actor,
                "kind": "component",
                "component": "velocity_tangent",
                "anchor": "current_position",
                "label": "v_parallel",
                "role": "velocity component along the incline",
            },
            {
                "id": "velocity:normal_component",
                "actor": primary_actor,
                "kind": "component",
                "component": "velocity_normal",
                "anchor": "current_position",
                "label": "v_n",
                "role": "velocity component normal to the incline",
            },
        ])
        for motion in motions:
            actor = str(motion.get("actor") or "")
            if not actor:
                continue
            vectors.extend([
                {
                    "id": f"{actor}:gravity_tangent_component",
                    "actor": actor,
                    "kind": "component",
                    "component": "gravity_tangent",
                    "anchor": "launch",
                    "label": "g sin alpha",
                    "role": f"gravity component along the incline for {actor}",
                },
                {
                    "id": f"{actor}:gravity_normal_component",
                    "actor": actor,
                    "kind": "component",
                    "component": "gravity_normal",
                    "anchor": "launch",
                    "label": "g cos alpha",
                    "role": f"gravity component normal to the incline for {actor}",
                },
            ])
    return vectors


def _camera_bookmarks_for_scene(scene: dict[str, Any]) -> list[dict[str, Any]]:
    points = scene.get("geometry", {}).get("points", {})
    bookmarks = [
        {"id": "full_scene", "label": "Full scene", "target": "scene", "zoom": 1.0},
        {"id": "setup", "label": "Launch setup", "target": "launch", "zoom": 2.15},
    ]
    if "apex" in points:
        bookmarks.append({"id": "apex", "label": "Apex", "target": "apex", "zoom": 2.0})
    for point_id in ("impact", "collision", "landing", "target", "wall_top"):
        if point_id in points:
            bookmarks.append({"id": point_id, "label": point_id.replace("_", " ").title(), "target": point_id, "zoom": 1.9})
    return bookmarks


def _storyboard_for_scene(scene: dict[str, Any], *, result: EvaluationResult) -> list[dict[str, Any]]:
    steps = scene.get("steps") or []
    plan_steps = {str(step.get("id")): step for step in (result.equation_plan or {}).get("steps", [])}
    beat_visual_plans = scene.get("beat_visual_plans") or {}
    camera_ids = {str(camera.get("id")) for camera in scene.get("camera_bookmarks") or [] if camera.get("id")}
    storyboard: list[dict[str, Any]] = []
    used_visual_plans: set[str] = set()
    for step in steps:
        step_id = str(step.get("id") or "step")
        plan_step = plan_steps.get(step_id, {})
        visual_plan = beat_visual_plans.get(step_id) if isinstance(beat_visual_plans, dict) else None
        visual_action = str((visual_plan or {}).get("visual_action") or step.get("visual_action") or _scene_visual_action(
            step_id,
            str(step.get("title") or ""),
            str(step.get("equation") or ""),
            list(step.get("focus_ids") or []),
        ))
        visual_action = _semantic_visual_action_override(result, step_id, step, visual_action)
        camera = _camera_for_visual_plan(visual_plan, step_id, step)
        if camera not in camera_ids:
            camera = "full_scene"
        visible_vectors = _vectors_for_visual_plan(visual_plan) or _visible_vectors_for_step(step_id, step, scene)
        contract_text = " ".join(
            str(item or "")
            for item in (
                step_id,
                step.get("title"),
                step.get("equation"),
                step.get("substitution"),
                plan_step.get("title"),
                plan_step.get("explanation"),
                plan_step.get("equation"),
                plan_step.get("substitution"),
            )
        )
        beat_visual_spec = (visual_plan or {}).get("beat_visual_spec") if isinstance(visual_plan, dict) else None
        if not isinstance(beat_visual_spec, dict) or not beat_visual_spec:
            beat_visual_spec = build_beat_visual_spec(
                result=result,
                step_id=step_id,
                title=str(step.get("title") or plan_step.get("title") or ""),
                text=contract_text,
                visual_plan=visual_plan or {},
            )
        visual_action = contract_visual_action(visual_action, beat_visual_spec)
        contract_camera = str((beat_visual_spec.get("renderer_hints") or {}).get("camera") or "")
        if contract_camera:
            camera = contract_camera
        if camera not in camera_ids:
            camera = "full_scene"
        visible_vectors = contract_visible_vectors(visible_vectors, beat_visual_spec)
        overlays = _overlays_for_visual_plan(visual_plan) or step.get("overlays") or _overlays_for_step(step_id, step.get("focus_ids") or [], visual_action)
        visual_focus = contract_visible_ids(_show_ids_for_visual_plan(visual_plan) or step.get("focus_ids") or [], beat_visual_spec)
        highlight_ids = contract_visible_ids(_highlight_ids_for_visual_plan(visual_plan) or step.get("highlight_ids") or step.get("focus_ids") or [], beat_visual_spec)
        labels = merge_contract_labels((visual_plan or {}).get("labels") or [], beat_visual_spec.get("labels") or [])
        used_visual_plans.add(step_id)
        storyboard.append({
            "step_id": step_id,
            "beat_visual_spec": beat_visual_spec,
            "visual_action": visual_action,
            "camera": camera,
            "visible_vectors": visible_vectors,
            "overlays": overlays,
            "visual_focus": visual_focus,
            "highlight_ids": highlight_ids,
            "camera_target_ids": step.get("camera_target_ids") or (visual_plan or {}).get("show_ids") or [],
            "labels": labels,
            "motion": (visual_plan or {}).get("motion") or {},
            "visual_state": _visual_state_for_visual_plan(visual_plan, visible_vectors, visual_focus, highlight_ids),
            "visual_plan": visual_plan or {},
            "why": plan_step.get("explanation") or _why_for_step(step_id, result),
            "student_goal": step.get("student_goal") or "",
            "equation": plan_step.get("equation") or step.get("equation") or "",
            "substitution": plan_step.get("substitution") or step.get("substitution") or "",
        })
    for step_id, visual_plan in (beat_visual_plans.items() if isinstance(beat_visual_plans, dict) else []):
        if step_id in used_visual_plans:
            continue
        visual_action = str(visual_plan.get("visual_action") or "highlight_final_answer")
        beat_visual_spec = visual_plan.get("beat_visual_spec") if isinstance(visual_plan.get("beat_visual_spec"), dict) else build_beat_visual_spec(
            result=result,
            step_id=step_id,
            title="",
            text=json.dumps(visual_plan, ensure_ascii=False),
            visual_plan=visual_plan,
        )
        visual_action = contract_visual_action(visual_action, beat_visual_spec)
        visible_vectors = contract_visible_vectors(_vectors_for_visual_plan(visual_plan) or ["__none__"], beat_visual_spec)
        visual_focus = contract_visible_ids(_show_ids_for_visual_plan(visual_plan) or ["answer"], beat_visual_spec)
        highlight_ids = contract_visible_ids(_highlight_ids_for_visual_plan(visual_plan) or ["answer"], beat_visual_spec)
        labels = merge_contract_labels(visual_plan.get("labels") or [], beat_visual_spec.get("labels") or [])
        storyboard.append({
            "step_id": step_id,
            "beat_visual_spec": beat_visual_spec,
            "visual_action": visual_action,
            "camera": "full_scene",
            "visible_vectors": visible_vectors,
            "overlays": _overlays_for_visual_plan(visual_plan) or ["show_final_answer"],
            "visual_focus": visual_focus,
            "highlight_ids": highlight_ids,
            "camera_target_ids": visual_plan.get("show_ids") or ["answer"],
            "labels": labels,
            "motion": visual_plan.get("motion") or {},
            "visual_state": _visual_state_for_visual_plan(
                visual_plan,
                visible_vectors,
                visual_focus,
                highlight_ids,
            ),
            "visual_plan": visual_plan,
            "why": "Close the walkthrough with the final result.",
            "student_goal": "Lock the final answer to the exact quantity asked.",
            "equation": "",
            "substitution": "",
        })
    if not storyboard:
        beat_visual_spec = build_beat_visual_spec(
            result=result,
            step_id="full",
            title="Full motion",
            text="Show the full solved projectile motion.",
            visual_plan={"visual_action": "show_full_scene"},
        )
        storyboard.append({
            "step_id": "full",
            "beat_visual_spec": beat_visual_spec,
            "visual_action": "show_full_scene",
            "camera": "full_scene",
            "visible_vectors": ["__none__"],
            "overlays": ["show_trajectory"],
            "visual_focus": ["trajectory:path"],
            "highlight_ids": ["trajectory:path"],
            "camera_target_ids": ["full_scene"],
            "why": "Show the motion implied by the solved projectile model.",
            "visual_state": {
                "visible_ids": ["trajectory:path"],
                "visible_vectors": ["__none__"],
                "highlight_ids": ["trajectory:path"],
                "label_ids": [],
                "dimmed_ids": [],
                "persist_until": "next_beat",
            },
        })
    return [_normalize_storyboard_step_for_scene(step, scene) for step in storyboard]


def _semantic_visual_action_override(
    result: EvaluationResult,
    step_id: str,
    step: dict[str, Any],
    visual_action: str,
) -> str:
    if result.engine_case == "monkey_hunter_condition":
        focus = " ".join(str(item).lower() for item in step.get("focus_ids") or [])
        if step_id.endswith("4") or "point:hit" in focus or "event:hit" in focus:
            return "highlight_collision"
    if result.engine_case.startswith("height_launch"):
        focus = " ".join(str(item).lower() for item in step.get("focus_ids") or [])
        if "event:impact" in focus or "quantity:launch_height" in focus:
            if visual_action == "highlight_same_height":
                return "highlight_vertical_motion"
    return visual_action


def _normalize_storyboard_step_for_scene(step: dict[str, Any], scene: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(step)
    point_ids = set((scene.get("geometry", {}).get("points") or {}).keys())
    point_aliases = _point_aliases_for_scene(scene, point_ids)
    surface_ids = {
        str(surface.get("id") or "")
        for surface in (scene.get("geometry", {}).get("surfaces") or [])
        if surface.get("id")
    }
    surface_aliases = _surface_aliases_for_scene(scene, surface_ids)

    def normalize_id(raw: Any) -> list[str]:
        scene_id = str(raw or "")
        if scene_id.startswith("point:"):
            point_id = scene_id.split(":", 1)[1]
            if point_id in point_ids:
                return [scene_id]
            alias = point_aliases.get(point_id, "")
            return [alias] if alias else []
        if scene_id.startswith("surface:"):
            surface_id = scene_id.split(":", 1)[1]
            if surface_id in surface_ids:
                return [scene_id]
            return surface_aliases.get(surface_id, [])
        return [scene_id] if scene_id else []

    for key in ("visual_focus", "highlight_ids", "camera_target_ids"):
        normalized[key] = _deduped_ids(alias for item in normalized.get(key) or [] for alias in normalize_id(item))

    visual_state = dict(normalized.get("visual_state") or {})
    for key in ("visible_ids", "highlight_ids", "dimmed_ids"):
        visual_state[key] = _deduped_ids(alias for item in visual_state.get(key) or [] for alias in normalize_id(item))
    visual_state["label_ids"] = _deduped_ids(alias for item in visual_state.get("label_ids") or [] for alias in normalize_id(item))
    normalized["visual_state"] = visual_state
    return normalized


def _point_aliases_for_scene(scene: dict[str, Any], point_ids: set[str]) -> dict[str, str]:
    event_points: dict[str, str] = {}
    for event in scene.get("events") or []:
        event_id = str(event.get("id") or "").split(":", 1)[-1]
        point_id = str(event.get("point") or "")
        if event_id and point_id in point_ids:
            event_points[event_id] = f"point:{point_id}"

    aliases: dict[str, str] = {}
    for event_id in ("impact", "collision", "landing"):
        if event_id not in point_ids and event_id in event_points:
            aliases[event_id] = event_points[event_id]
    if "impact" not in point_ids and "landing" in point_ids:
        aliases.setdefault("impact", "point:landing")
    if "collision" not in point_ids and "landing" in point_ids:
        aliases.setdefault("collision", "point:landing")
    return aliases


def _surface_aliases_for_scene(scene: dict[str, Any], surface_ids: set[str]) -> dict[str, list[str]]:
    inclined = [
        f"surface:{surface_id}"
        for surface in (scene.get("geometry", {}).get("surfaces") or [])
        for surface_id in [str(surface.get("id") or "")]
        if surface_id and (surface.get("type") == "inclined_plane" or "incline" in surface_id.lower() or "plane" in surface_id.lower())
    ]
    aliases: dict[str, list[str]] = {}
    if "inclined_plane" not in surface_ids and inclined:
        aliases["inclined_plane"] = inclined
    if "plane" not in surface_ids and inclined:
        aliases["plane"] = inclined
    return aliases


def _deduped_ids(items: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item or "")
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _visual_state_for_visual_plan(
    visual_plan: dict[str, Any] | None,
    visible_vectors: list[str],
    visual_focus: list[str],
    highlight_ids: list[str],
) -> dict[str, Any]:
    if isinstance(visual_plan, dict) and isinstance(visual_plan.get("visual_state"), dict):
        state = dict(visual_plan.get("visual_state") or {})
    else:
        state = {}
    labels = (visual_plan or {}).get("labels") if isinstance(visual_plan, dict) else []
    label_ids = [
        str(label.get("target_id"))
        for label in labels or []
        if isinstance(label, dict) and str(label.get("target_id") or "")
    ]
    return {
        "visible_ids": _string_list(state.get("visible_ids") or visual_focus),
        "visible_vectors": _string_list(state.get("visible_vectors") or visible_vectors),
        "highlight_ids": _string_list(state.get("highlight_ids") or highlight_ids),
        "label_ids": _string_list(state.get("label_ids") or label_ids),
        "dimmed_ids": _string_list(state.get("dimmed_ids") or []),
        "persist_until": str(state.get("persist_until") or "next_beat"),
    }


def _string_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item) for item in items if str(item)]


def _vectors_for_visual_plan(visual_plan: dict[str, Any] | None) -> list[str]:
    if not isinstance(visual_plan, dict):
        return []
    vectors = visual_plan.get("visible_vectors") or []
    return [str(item) for item in vectors if str(item)]


def _overlays_for_visual_plan(visual_plan: dict[str, Any] | None) -> list[str]:
    if not isinstance(visual_plan, dict):
        return []
    overlays = visual_plan.get("overlays") or []
    return [str(item) for item in overlays if str(item)]


def _show_ids_for_visual_plan(visual_plan: dict[str, Any] | None) -> list[str]:
    if not isinstance(visual_plan, dict):
        return []
    ids = visual_plan.get("show_ids") or []
    return [str(item) for item in ids if str(item)]


def _highlight_ids_for_visual_plan(visual_plan: dict[str, Any] | None) -> list[str]:
    if not isinstance(visual_plan, dict):
        return []
    ids = visual_plan.get("highlight_ids") or []
    return [str(item) for item in ids if str(item)]


def _camera_for_visual_plan(visual_plan: dict[str, Any] | None, step_id: str, step: dict[str, Any]) -> str:
    if isinstance(visual_plan, dict) and visual_plan.get("camera"):
        return str(visual_plan.get("camera"))
    return _camera_for_step(step_id, step)


def _camera_for_step(step_id: str, step: dict[str, Any]) -> str:
    visual_action = str(step.get("visual_action") or "")
    if visual_action == "show_full_scene":
        return "full_scene"
    if visual_action == "highlight_final_answer":
        focus_ids = " ".join(str(item).lower() for item in step.get("focus_ids", []))
        if "quantity:u" in focus_ids or "actor:projectile_p" in focus_ids:
            return "setup"
        if "collision" in focus_ids:
            return "collision"
        return "full_scene"
    if visual_action in {"show_incline_axes", "compare_incline_motion"}:
        return "full_scene"
    if visual_action in {"show_normal_return", "highlight_collision"}:
        return "collision"
    if visual_action == "zoom_launch_vector":
        return "setup"
    if visual_action in {"highlight_vertical_motion", "highlight_apex"}:
        focus_ids = " ".join(str(item).lower() for item in step.get("focus_ids", []))
        is_peak_time = "peak" in focus_ids or "highest" in focus_ids or "t_peak" in focus_ids or "t_peak" in step_id.lower()
        if visual_action == "highlight_vertical_motion" and not is_peak_time and ("landing" in focus_ids or "flight" in step_id.lower()):
            return "landing"
        if "apex" in focus_ids or is_peak_time:
            return "apex"
        if "apex" in focus_ids or "peak" in focus_ids or "quantity:h" in focus_ids:
            return "apex"
        if "landing" in focus_ids or "quantity:t" in focus_ids or "time" in step_id.lower():
            return "landing"
        return "apex"
    if visual_action == "highlight_range":
        focus_ids = " ".join(str(item).lower() for item in step.get("focus_ids", []))
        return "impact" if "impact" in focus_ids and "landing" not in focus_ids else "landing"
    if visual_action == "show_impact_velocity_triangle":
        focus_ids = " ".join(str(item).lower() for item in step.get("focus_ids", []))
        if "collision" in focus_ids:
            return "collision"
        if "impact" in focus_ids:
            return "impact"
        return "landing"
    lowered = step_id.lower()
    focus_ids = " ".join(str(item).lower() for item in step.get("focus_ids", []))
    if "quantity:r" in focus_ids or "range" in lowered:
        return "full_scene"
    if "apex" in lowered or "height" in lowered or "peak" in lowered:
        return "apex"
    if "point:impact" in focus_ids or "event:impact" in focus_ids:
        return "impact"
    if "point:collision" in focus_ids or "event:collision" in focus_ids:
        return "collision"
    if "point:landing" in focus_ids or "event:landing" in focus_ids:
        return "landing"
    if "point:target" in focus_ids:
        return "target"
    if "point:wall_top" in focus_ids or "obstacle:wall" in focus_ids:
        return "wall_top"
    if "event:apex" in focus_ids or "quantity:h" in focus_ids:
        return "apex"
    if "impact" in lowered or "collision" in lowered or "answer" in lowered:
        return "impact" if "point:impact" in focus_ids or "impact" in focus_ids else "collision" if "collision" in focus_ids else "landing"
    if "target" in lowered or "wall" in lowered:
        return "target" if "target" in focus_ids else "wall_top"
    if "component" in lowered or "model" in lowered or "setup" in lowered or "invariant" in lowered:
        return "setup"
    return "full_scene"


def _visible_vectors_for_step(step_id: str, step: dict[str, Any], scene: dict[str, Any]) -> list[str]:
    lowered = " ".join(
        [
            step_id.lower(),
            str(step.get("title") or "").lower(),
            str(step.get("concept_used") or "").lower(),
            str(step.get("equation") or "").lower(),
            " ".join(str(item).lower() for item in step.get("focus_ids", [])),
        ]
    )
    visual_action = str(step.get("visual_action") or "")
    has_incline = any(surface.get("type") == "inclined_plane" for surface in scene.get("geometry", {}).get("surfaces", []))
    if visual_action == "show_full_scene" and ("vector:u" in lowered or "quantity:u" in lowered):
        vectors = ["*:v"]
    elif visual_action == "show_full_scene" and _mentions_component_resolution(lowered):
        vectors = ["x_axis", "y_axis", "*:v", "*:vx", "*:vy"]
    elif visual_action == "show_full_scene":
        vectors = ["__none__"]
    elif visual_action == "show_incline_axes":
        vectors = ["incline:tangent_axis", "incline:normal_axis"]
    elif visual_action == "compare_incline_motion":
        vectors = ["*:a", "incline:tangent_axis"]
    elif visual_action in {"show_normal_return", "highlight_collision"}:
        vectors = ["incline:normal_axis"]
        if "gravity" in lowered or "normal" in lowered:
            vectors.append("*:gravity_normal_component")
        if "velocity" in lowered or "quantity:u" in lowered or "vector:u" in lowered:
            vectors.append("*:v")
    elif visual_action == "zoom_launch_vector":
        vectors = ["*:v"]
    elif visual_action == "show_impact_velocity_triangle":
        vectors = ["*:v", "*:velocity_tangent_component", "*:velocity_normal_component"]
    elif (
        "vector:vx" in lowered
        or "vector:vy" in lowered
        or "quantity:ux" in lowered
        or "quantity:uy" in lowered
        or "resolve" in lowered
        or "velocity component" in lowered
    ):
        vectors = ["*:v"]
        if "vector:vx" in lowered or "quantity:ux" in lowered or "velocity component" in lowered or "resolve" in lowered:
            vectors.append("*:vx")
        if "vector:vy" in lowered or "quantity:uy" in lowered or "velocity component" in lowered or "resolve" in lowered:
            vectors.append("*:vy")
    elif "quantity:u" in lowered or "vector:u" in lowered or "launch" in lowered:
        vectors = ["*:v"]
    elif visual_action == "highlight_range" or "quantity:r" in lowered or "point:landing" in lowered or "answer" in lowered or "range" in lowered:
        vectors = ["__none__"]
    elif visual_action in {"highlight_vertical_motion", "highlight_apex"} or "time" in lowered or "height" in lowered or "apex" in lowered or "peak" in lowered:
        vectors = ["*:vy", "*:a"]
    else:
        vectors = ["*:v", "*:a"]
    if vectors != ["__none__"] and has_incline and ("incline" in lowered or "model" in lowered or "setup" in lowered or "invariant" in lowered):
        vectors.extend(["incline:tangent_axis", "incline:normal_axis"])
    return list(dict.fromkeys(vectors))


def _mentions_component_resolution(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "resolve",
            "component",
            "horizontal motion",
            "vertical motion",
            "u_x",
            "u_y",
            "v_x",
            "v_y",
        )
    )


def _why_for_step(step_id: str, result: EvaluationResult) -> str:
    if step_id == "invariant":
        return str((result.equation_plan or {}).get("invariant") or "Identify the physical invariant before calculating.")
    return "Use the highlighted diagram quantity to justify the equation used in this step."


def _scene_student_goal(step: dict[str, Any], result: EvaluationResult) -> str:
    title = str(step.get("title") or "").lower()
    unknown = str((result.equation_plan or {}).get("unknown") or "the requested quantity")
    if "answer" in title or "compute" in title:
        return f"Compute {unknown} and check the final form."
    if "relation" in title or "model" in title or "setup" in title:
        return f"Connect the diagram to the relation needed for {unknown}."
    return f"Use this visual focus to solve for {unknown}."


def _scene_concept(step: dict[str, Any], result: EvaluationResult) -> str:
    equation = str(step.get("equation") or "").lower()
    if "sin" in equation or "cos" in equation or "tan" in equation:
        return "component trigonometry"
    if "x =" in equation or "y =" in equation:
        return "2D kinematics"
    if "dot" in equation:
        return "vector direction condition"
    if step.get("id") == "invariant":
        return str((result.equation_plan or {}).get("invariant") or "physical invariant")
    return "projectile model"


def _scene_invariant_focus(result: EvaluationResult) -> list[str]:
    plan = result.equation_plan or {}
    unknown = str(plan.get("unknown") or "").lower()
    text = f"{unknown} {plan.get('goal') or ''}".lower()
    if result.engine_case == "projectile_collides_with_sliding_particle_on_incline":
        return ["point:launch", "surface:inclined_plane", "incline:normal_axis", "incline:tangent_axis", "actor:projectile_p", "actor:slider_q", "quantity:u", "vector:u"]
    if result.engine_case == "inclined_plane_max_normal_distance_velocity_component":
        return ["surface:inclined_plane", "incline:normal_axis", "velocity:normal_component", "trajectory:path", "answer"]
    if result.engine_case == "motion_on_smooth_incline_perpendicular_to_slope":
        return ["surface:inclined_plane", "incline:tangent_axis", "incline:normal_axis", "vector:u", "quantity:u", "answer"]
    if result.engine_case == "inclined_plane_right_angle_impact_condition":
        return ["surface:inclined_plane", "incline:tangent_axis", "point:impact", "velocity:tangent_component", "answer"]
    if result.engine_case == "two_inclines_perpendicular_launch_impact":
        return ["plane_OA", "plane_OB", "point:P", "point:Q", "vector:u", "quantity:u"]
    if result.engine_case in {
        "perpendicular_launch_range_on_incline",
        "max_range_on_incline",
        "horizontal_launch_onto_incline_distance",
    }:
        return ["quantity:R", "point:impact", "surface:inclined_plane", "trajectory:path"]
    if "peak" in unknown or "highest" in unknown or result.engine_case == "level_ground_time_to_peak":
        return ["event:apex", "quantity:t_peak", "quantity:H", "trajectory:path"]
    if "time" in unknown:
        return ["quantity:T", "event:landing", "trajectory:path"]
    if "velocity" in text or "speed" in text:
        return ["vector:u", "vector:vx", "vector:vy"]
    if "range" in text or "distance" in text:
        return ["quantity:R", "point:landing", "trajectory:path"]
    if "height" in text or "apex" in text or "peak" in text:
        return ["event:apex", "quantity:H", "trajectory:path"]
    if "time" in text:
        return ["quantity:T", "event:landing", "trajectory:path"]
    return ["setup", "trajectory:path"]


def _focus_for_step(step_id: str) -> list[str]:
    lowered = step_id.lower()
    if "answer" in lowered:
        return ["quantity:R", "quantity:T", "quantity:H", "point:landing", "point:target", "obstacle:wall"]
    if "wall" in lowered or "clear" in lowered:
        return ["obstacle:wall", "point:wall_top", "trajectory:path"]
    if "target" in lowered:
        return ["point:target", "trajectory:path"]
    if "position" in lowered or "coordinate" in lowered:
        return ["point:position_at_t", "trajectory:path"]
    if "height" in lowered or "peak" in lowered:
        return ["event:apex", "quantity:H", "trajectory:path"]
    if "time" in lowered:
        return ["event:landing", "quantity:T", "trajectory:path"]
    if "range" in lowered:
        return ["quantity:R", "point:landing", "trajectory:path"]
    return ["vector:u", "quantity:u", "quantity:theta", "trajectory:path"]


def _scene_visual_action(step_id: str, title: str, equation: str, focus_ids: list[Any] | None = None) -> str:
    lowered = " ".join([step_id, title, equation, " ".join(str(item) for item in (focus_ids or []))]).lower()
    if (step_id == "invariant" or "given and what to find" in lowered) and ("quantity:r" in lowered or "range" in lowered):
        return "highlight_range"
    if step_id == "invariant" or "given and what to find" in lowered:
        return "show_full_scene"
    if "projection speed" in lowered or ("quantity:u" in lowered and ("solve" in lowered or "answer" in lowered or "state" in lowered)):
        return "zoom_launch_vector"
    if "incline:normal_axis" in lowered and ("read_diagram" in lowered or "normal to the incline" in lowered or "projected normal" in lowered):
        return "show_incline_axes"
    if "incline:tangent_axis" in lowered and "trajectory:q" in lowered:
        return "compare_incline_motion"
    if "n_p" in lowered or "normal separation" in lowered or ("incline:normal_axis" in lowered and "point:collision" in lowered):
        return "show_normal_return"
    if "actor:monkey" in lowered and ("point:hit" in lowered or "event:hit" in lowered or "arrival" in lowered):
        return "highlight_collision"
    if "event:collision" in lowered or "point:collision" in lowered:
        return "highlight_collision"
    if "range" in lowered or "quantity:r" in lowered or "distance" in lowered:
        return "highlight_range"
    if "event:impact" in lowered or "ground-impact" in lowered or "quantity:launch_height" in lowered:
        return "highlight_vertical_motion"
    if "same height" in lowered or "delta y" in lowered or "delta_y" in lowered:
        return "highlight_same_height"
    if "sqrt(2h" in lowered or "quantity:h" in lowered or " h/" in lowered or " h)" in lowered:
        return "highlight_apex"
    if "time" in lowered or "quantity:t" in lowered:
        return "highlight_vertical_motion"
    if "height" in lowered or "apex" in lowered or "peak" in lowered or "quantity:h" in lowered:
        return "highlight_apex"
    if (
        "component" in lowered
        or "resolve" in lowered
        or "vector:vx" in lowered
        or "vector:vy" in lowered
        or "quantity:ux" in lowered
        or "quantity:uy" in lowered
        or "u_x" in lowered
        or "u_y" in lowered
        or "v_x" in lowered
        or "v_y" in lowered
    ):
        return "zoom_launch_vector"
    if "time" in lowered or "vertical" in lowered or "y =" in lowered:
        return "highlight_vertical_motion"
    if "impact" in lowered or "resultant" in lowered or "speed" in lowered or "velocity" in lowered:
        return "show_impact_velocity_triangle"
    if "answer" in lowered or "takeaway" in lowered:
        return "highlight_final_answer"
    if step_id == "invariant" or "given" in lowered or "setup" in lowered or "model" in lowered:
        return "show_full_scene"
    return "focus_relevant_step"


def _camera_targets_for_visual_action(visual_action: str, focus_ids: list[Any] | None = None) -> list[str]:
    focus = [str(item) for item in (focus_ids or [])]
    if visual_action == "show_full_scene":
        return ["full_scene"]
    if visual_action == "show_incline_axes":
        return ["setup", "surface:inclined_plane", "incline:normal_axis", "incline:tangent_axis"]
    if visual_action == "compare_incline_motion":
        return ["surface:inclined_plane", "incline:tangent_axis", "trajectory:p", "trajectory:q"]
    if visual_action == "show_normal_return":
        return ["incline:normal_axis", "trajectory:p", "point:collision"]
    if visual_action == "highlight_collision":
        return ["point:collision", "event:collision"]
    if visual_action == "zoom_launch_vector":
        return ["setup", "point:launch", "vector:u"]
    if visual_action in {"highlight_vertical_motion", "highlight_apex"}:
        return ["event:apex", "quantity:H", "quantity:T"]
    if visual_action == "highlight_same_height":
        return ["point:launch", "point:landing"]
    if visual_action == "highlight_range":
        return ["quantity:R", "point:landing", "point:impact"]
    if visual_action == "show_impact_velocity_triangle":
        return ["point:impact", "point:landing", "vector:v"]
    return focus[:3] or ["full_scene"]


def _overlays_for_step(step_id: str, focus_ids: list[Any] | None = None, visual_action: str = "") -> list[str]:
    lowered = step_id.lower() + " " + " ".join(str(item).lower() for item in (focus_ids or []))
    static_actions = {"show_incline_axes", "compare_incline_motion", "zoom_launch_vector"}
    overlays = [] if visual_action in static_actions else ["show_trajectory"]
    if visual_action in {"show_incline_axes", "compare_incline_motion"}:
        overlays.append("show_perpendicular_marker")
    if visual_action in {"show_normal_return", "highlight_collision"}:
        overlays.append("show_timer")
        if visual_action == "show_normal_return":
            overlays.append("show_motion_progress")
        if visual_action == "highlight_collision":
            overlays.append("show_collision_marker")
    if visual_action == "zoom_launch_vector":
        overlays.extend(["show_velocity_components", "show_perpendicular_marker"])
    if visual_action == "highlight_vertical_motion":
        overlays.extend(["show_height_marker", "show_timer", "show_motion_progress"])
    if visual_action == "highlight_same_height":
        overlays.append("show_same_height")
    if visual_action == "highlight_range":
        overlays.append("show_range_marker")
    if visual_action == "highlight_apex":
        overlays.extend(["show_height_marker", "show_motion_progress"])
    if visual_action == "show_impact_velocity_triangle":
        overlays.extend(["show_final_velocity_components", "show_motion_progress"])
    if visual_action == "show_full_scene":
        return list(dict.fromkeys(overlays))
    if "range" in lowered or "quantity:r" in lowered:
        overlays.append("show_range_marker")
    if "point:launch" in lowered and "point:landing" in lowered:
        overlays.append("show_same_height")
    if "height" in lowered or "peak" in lowered or "event:apex" in lowered:
        overlays.append("show_height_marker")
        overlays.append("show_motion_progress")
    if "time" in lowered:
        overlays.append("show_timer")
        overlays.append("show_motion_progress")
    if "component" in lowered or "model" in lowered:
        overlays.append("show_velocity_components")
    if "vector:vx" in lowered or "vector:vy" in lowered or "quantity:ux" in lowered or "quantity:uy" in lowered:
        overlays.append("show_velocity_components")
    if "wall" in lowered or "clear" in lowered:
        overlays.append("show_wall")
    if "target" in lowered:
        overlays.append("show_target")
    if "trajectory:path" in lowered and visual_action not in {"show_incline_axes", "compare_incline_motion"} and not any(marker in lowered for marker in ("quantity:r", "point:landing", "vector:vx", "vector:vy", "quantity:ux", "quantity:uy")):
        overlays.append("show_motion_progress")
    return list(dict.fromkeys(overlays))


def _sample_projectile_path(
    *,
    y0: float,
    ux: float,
    uy: float,
    g: float,
    duration: float,
    count: int,
    x0: float = 0.0,
    clamp_to_ground: bool = True,
) -> list[dict[str, float]]:
    points: list[dict[str, float]] = []
    for index in range(count):
        t = duration * index / max(count - 1, 1)
        y = y0 + uy * t - 0.5 * g * t * t
        points.append({"x": x0 + ux * t, "y": max(0.0, y) if clamp_to_ground else y, "t": t})
    return points


def _sample_slider_path(
    *,
    x0: float,
    y0: float,
    angle_rad: float,
    acceleration: float,
    duration: float,
    count: int,
) -> list[dict[str, float]]:
    points: list[dict[str, float]] = []
    for index in range(count):
        t = duration * index / max(count - 1, 1)
        distance = 0.5 * acceleration * t * t
        points.append({
            "x": x0 + distance * math.cos(angle_rad),
            "y": max(0.0, y0 + distance * math.sin(angle_rad)),
            "t": t,
        })
    return points


def _positive_ground_time(*, y0: float, uy: float, g: float) -> float:
    if not g:
        return 0.0
    discriminant = uy * uy + 2 * g * y0
    if discriminant < 0:
        return 0.0
    return (uy + math.sqrt(discriminant)) / g


def _unknown_for_case(engine_case: str, question_text: str) -> str:
    return {
        "level_ground_range": "maximum_range" if "maximum" in question_text.lower() else "range",
        "level_ground_time_of_flight": "time_of_flight",
        "level_ground_multi_quantity": "level_ground_multi_quantity",
        "level_ground_range_and_time": "range_and_time_of_flight",
        "level_ground_time_of_flight_derivation": "time_of_flight_derivation",
        "level_ground_max_height": "maximum_height",
        "projectile_split_at_apex_fragment_time": "fragment_fall_time",
        "level_ground_time_to_peak": "time_to_peak",
        "level_ground_position_at_time": "position_at_time",
        "level_ground_launch_angle_from_range": "launch_angle",
        "two_projectile_same_speed_comparison": "time_height_range_comparison",
        "monkey_hunter_condition": "falling_target_condition",
        "height_launch_time_of_flight": "time_of_flight",
        "height_launch_range": "range",
        "height_launch_multi_quantity": "height_launch_multi_quantity",
        "height_launch_horizontal_scenario": "scenario_summary",
        "minimum_speed_to_hit_target": "minimum_speed",
        "perpendicular_launch_range_on_incline": "range_on_incline",
        "max_range_on_incline": "maximum_range_on_incline",
        "horizontal_launch_onto_incline_distance": "distance_along_incline",
        "inclined_plane_impact_time": "impact_time",
        "inclined_plane_right_angle_impact_condition": "right_angle_impact_condition",
        "inclined_plane_same_point_time_ratio": "time_ratio",
        "inclined_plane_max_normal_distance_velocity_component": "normal_velocity_component",
        "wall_height_at_distance": "height_at_wall",
        "wall_clearance_condition": "wall_clearance",
        "target_launch_angle_fixed_speed": "launch_angle",
    }.get(engine_case, "unknown")


def _scene_world(
    spec_world: str,
    *,
    target: tuple[float, float] | None,
    wall_x: float | None,
    launch_height: float,
) -> str:
    if wall_x is not None:
        return "wall"
    if target is not None:
        return "target"
    if launch_height > 0:
        return "height_launch"
    if spec_world in {"level_ground", "height_launch", "wall", "target"}:
        return spec_world
    return "level_ground"


def _merge_givens(givens: list[str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for given in givens:
        if "=" not in given:
            continue
        key, value = given.split("=", 1)
        merged[_normalize_key(key)] = value.strip()
    return merged


def _number_from_givens(givens: dict[str, str], keys: list[str]) -> float | None:
    for key in keys:
        value = givens.get(_normalize_key(key))
        if value is None:
            continue
        parsed = _parse_number(value)
        if parsed is not None:
            return parsed
    return None


def _point_from_givens(givens: dict[str, str], keys: list[str]) -> tuple[float, float] | None:
    for key in keys:
        value = givens.get(_normalize_key(key))
        if value is None:
            continue
        nums = re.findall(r"[-+]?\d+(?:\.\d+)?", value)
        if len(nums) >= 2:
            return float(nums[0]), float(nums[1])
    return None


def _first_angle_from_text(text: str) -> float | None:
    match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*deg", text)
    return float(match.group(1)) if match else None


def _minimum_speed_target_angle_deg(target: tuple[float, float]) -> float | None:
    x, y = target
    if math.isclose(x, 0.0, abs_tol=1e-12):
        return 90.0
    return math.degrees(math.atan2(y + math.hypot(x, y), x))


def _first_speed_from_text(text: str) -> float | None:
    match = re.search(
        r"([-+]?\d+(?:\.\d+)?(?:\s*\*?\s*(?:sqrt|root)\(?\d+(?:\.\d+)?\)?)?)\s*m/s",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    return _parse_number(match.group(1))


def _first_time_from_text(text: str) -> float | None:
    match = re.search(r"(?:t\s*=\s*)?([-+]?\d+(?:\.\d+)?)\s*(?:s|sec|second|seconds)", text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def _angle_numbers_from_text(text: str) -> list[float]:
    return [
        float(value)
        for value in re.findall(r"([-+]?\d+(?:\.\d+)?)\s*(?:deg|degree|degrees|°)", text, re.IGNORECASE)
    ]


def _interception_angle_pairs(text: str) -> list[tuple[float, float]]:
    normalized = text.replace("°", "deg")
    pairs: list[tuple[float, float]] = []
    for match in re.finditer(
        r"\(\s*theta0\s*,\s*theta1\s*\)\s*=\s*\(\s*([-+]?\d+(?:\.\d+)?)\s*(?:deg|degree|degrees)?\s*,\s*([-+]?\d+(?:\.\d+)?)\s*(?:deg|degree|degrees)?\s*\)",
        normalized,
        re.IGNORECASE,
    ):
        pairs.append((float(match.group(1)), float(match.group(2))))
    if pairs:
        return pairs
    numbers = _angle_numbers_from_text(normalized)
    if len(numbers) >= 4:
        return [(numbers[0], numbers[1]), (numbers[2], numbers[3])]
    return []


def _stair_dimension_from_text(text: str, kind: str) -> float | None:
    compact = " ".join(text.lower().split())
    if kind == "height":
        patterns = [
            r"step\s+is\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+high",
            r"each\s+step\s+is\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+high",
            r"y\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*m",
        ]
    else:
        patterns = [
            r"and\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+wide",
            r"step\s+is\s+[0-9]+(?:\.[0-9]+)?\s*m\s+high\s+and\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+wide",
            r"x\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*m",
        ]
    for pattern in patterns:
        match = re.search(pattern, compact)
        if match:
            return float(match.group(1))
    return None


def _parse_number(raw: str) -> float | None:
    text = raw.lower().replace("°", "").replace("deg", "").replace("root", "sqrt").replace("√", "sqrt")
    text = re.sub(r"m/s\^?2|m/s|meter|metre|meters|metres|sec|s\b|m\b", "", text)
    text = text.replace(" ", "")
    text = re.sub(r"(\d+(?:\.\d+)?)sqrt\(?(\d+(?:\.\d+)?)\)?", r"\1*sqrt(\2)", text)
    text = re.sub(r"sqrt(\d+(?:\.\d+)?)", r"sqrt(\1)", text)
    match = re.search(r"[-+]?(?:(?:\d+(?:\.\d*)?|\.\d+)|sqrt\(\d+(?:\.\d+)?\))(?:[*/](?:(?:\d+(?:\.\d*)?|\.\d+)|sqrt\(\d+(?:\.\d+)?\)))*", text)
    if not match:
        return None
    return float(eval(match.group(0), {"__builtins__": {}}, {"sqrt": math.sqrt}))


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
