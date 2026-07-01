from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProjectileProblemSpec:
    world: str = "unknown"
    unknown: str = "unknown"
    constraints: set[str] = field(default_factory=set)
    givens: list[str] = field(default_factory=list)
    engine_case: str | None = None


def map_projectile_problem(question_text: str) -> ProjectileProblemSpec:
    text = _normalize(question_text)
    world = _infer_world(text)
    unknown = _infer_unknown(text)
    constraints = _infer_constraints(text)
    givens = _infer_givens(text)
    engine_case = _engine_from_spec(world, unknown, constraints)
    return ProjectileProblemSpec(
        world=world,
        unknown=unknown,
        constraints=constraints,
        givens=givens,
        engine_case=engine_case,
    )


def _infer_world(text: str) -> str:
    if _contains_any(text, ["air drag", "air resistance", "quadratic drag", "drag force", "magnus"]):
        return "drag"
    if _contains_any(text, ["moving wedge", "wedge moving", "moving incline"]):
        return "moving_wedge"
    if _contains_any(text, ["splits into", "split into", "splits at", "split at"]) and _contains_any(text, ["highest point", "apex"]):
        return "split_at_apex"
    if _contains_any(text, ["bounce", "bounces", "rebound", "rebounds", "coefficient of restitution"]):
        return "bounce"
    if _contains_any(text, ["changed gravity", "gravity changes", "effective gravity", "enters a region"]) and _contains_any(text, ["highest point", "apex"]):
        return "piecewise_acceleration"
    if "stair" in text or "step" in text:
        return "staircase"
    if "plane oa" in text and "plane ob" in text:
        return "two_inclines"
    if _is_two_projectile_same_speed_comparison(text):
        return "multi_projectile"
    if "wall" in text or "obstacle" in text or "barrier" in text:
        return "wall"
    if "inclined" in text or "incline" in text:
        return "incline"
    if "stone" in text and "same time" in text:
        return "multi_projectile"
    if _contains_any(text, ["collides", "collision"]) and _contains_any(text, ["highest point", "apex"]) and "vertically" in text:
        return "multi_projectile"
    if "projectile a" in text and "projectile b" in text and _contains_any(text, ["collide", "collision"]):
        return "multi_projectile"
    if "lands on a platform" in text or "target" in text or _has_coordinate_pair(text):
        return "target"
    if _is_height_launch_context(text):
        return "height_launch"
    return "level_ground"


def _infer_unknown(text: str) -> str:
    if _is_two_projectile_same_speed_comparison(text):
        return "same_speed_comparison"
    if _contains_any(text, ["derive", "derivation", "prove", "show that"]) and _contains_any(text, ["time of flight", "flight time"]):
        return "time_of_flight_derivation"
    if _contains_any(text, ["wall", "barrier", "obstacle"]) and _contains_any(text, ["clear", "clears", "cross", "crosses"]):
        return "clears_wall_condition"
    if ("coordinates are" in text or ("x" in text and "y" in text and "=" in text)) and _contains_any(
        text,
        ["initial horizontal velocity", "initial vertical velocity", "initial speed", "angle of projection"],
    ):
        return "position_at_time"
    if "passes through" in text and "high after" in text and "horizontal velocity" in text:
        return "position_at_time"
    if len(_requested_level_ground_outputs(text)) >= 2:
        return "level_ground_multi_quantities"
    if _contains_any(text, ["splits into", "split into", "splits at", "split at"]) and _contains_any(text, ["highest point", "apex"]):
        if re.search(r"\bt\s+seconds?\s+after\s+the\s+splitting", text):
            return "fragment_fall_time"
        return "fragment_motion"
    if _is_quantitative_non_ideal_projectile(text):
        return "non_ideal_quantitative"
    if _is_non_ideal_projectile(text):
        return "drag_effects"
    if _contains_any(text, ["bounce", "bounces", "rebound", "rebounds", "coefficient of restitution"]):
        if _contains_any(text, ["coefficient of restitution", "restitution"]):
            return "coefficient_of_restitution_or_post_bounce_height"
        return "post_bounce_height_or_range"
    if _contains_any(text, ["changed gravity", "gravity changes", "effective gravity", "enters a region"]) and _contains_any(text, ["range", "distance"]):
        return "range_under_changed_acceleration"
    if _contains_any(text, ["which step", "to which step", "step will", "which stair", "stair does it hit", "hit first"]):
        return "step_number"
    if _contains_any(text, ["change in velocity", "delta velocity"]):
        return "change_in_velocity"
    if _contains_any(text, ["position after", "coordinates after", "position at", "coordinates at"]):
        return "position_at_time"
    if _contains_any(text, ["height of the projectile when", "height of the ball when", "height when", "height and vertical velocity when"]) and _contains_any(
        text,
        ["covered", "travelled", "traveled", "away", "horizontal range"],
    ):
        return "position_at_time"
    if _contains_any(text, ["velocity after", "velocity at", "velocity one", "speed after", "speed at"]) and _contains_any(text, ["after", "later", "t =", "time", "second"]):
        return "velocity_at_time"
    if _contains_any(text, ["same height", "same vertical height"]) and _contains_any(text, ["two times", "at times", "observed at"]):
        return "initial_speed_from_same_height_times"
    if "trajectory" in text and re.search(r"\by\s*=", text) and _contains_any(text, ["maximum height", "greatest height"]):
        return "maximum_height_from_trajectory_equation"
    if _contains_any(text, ["initial velocity is halved", "velocity is halved", "speed is halved"]):
        return "scaled_projectile_quantity"
    if "range" in text and _contains_any(text, ["maximum height", "greatest height"]) and _contains_any(text, ["same", "equal", "equals", "times"]):
        return "launch_angle_from_range_height_relation"
    if "same velocity" in text and "range" in text and _contains_any(text, ["another angle", "angle of", "projected at"]):
        return "range_angle_scaling"
    if "direction of" in text and "velocity" in text and "speed" in text:
        return "speed_at_velocity_angle"
    if "velocity" in text and "angle" in text and _contains_any(text, ["when", "time"]):
        return "time_when_velocity_angle"
    if _asks_time_to_peak(text):
        return "time_to_peak"
    if "lands on a platform" in text and _contains_any(text, ["angle", "angles"]):
        return "launch_angle"
    if _contains_any(text, ["launch angle", "launch angles", "angle of projection", "what angle"]) and (
        "range" in text or "target" in text or _has_coordinate_pair(text)
    ):
        return "launch_angle"
    if _contains_any(text, ["wall", "barrier", "obstacle"]) and _contains_any(text, ["clear", "clears", "cross", "crosses"]):
        return "clears_wall_condition"
    if _contains_any(text, ["wall", "barrier", "obstacle"]) and _contains_any(text, ["height when", "height at", "at a wall", "at the wall", "at a barrier", "at the barrier", "at an obstacle"]):
        return "height_at_wall"
    if _contains_any(text, ["time of flight", "flight time", "time after", "time in air", "airtime", "duration", "when", "again becomes zero", "returns to ground", "how long", "take to fall", "time to fall"]):
        return "time_of_flight"
    if _contains_any(text, ["maximum height", "max height", "greatest height", "highest point", "maximum altitude", "altitude gained"]):
        if "average velocity" in text:
            return "average_velocity_to_peak"
        return "maximum_height"
    if "minimum" in text and _contains_any(text, ["velocity", "speed"]):
        return "minimum_speed"
    if "range" in text or _contains_any(text, ["how far", "horizontal distance", "ground distance", "distance covered on ground", "distance on ground", "distance along the plane", "distance along plane", "distance on the plane", "where does it land"]):
        if "maximum" in text or "max" in text:
            return "maximum_range"
        return "range"
    if _contains_any(text, ["velocity at q", "speed at q", "velocity at impact", "strikes plane ob"]):
        return "impact_speed"
    if "t1/t2" in text or "t_1/t_2" in text or "t₁/t₂" in text:
        return "time_ratio_squared"
    if _contains_any(text, ["collides", "collision"]) and _contains_any(text, ["highest point", "apex"]) and "vertically" in text:
        return "vertical_throw_speed_for_apex_collision"
    if _contains_any(text, ["when do they collide", "collision time", "when will they collide"]):
        return "collision_time"
    return "unknown"


def _infer_constraints(text: str) -> set[str]:
    constraints: set[str] = set()
    if _contains_any(text, ["same level", "ground", "playground", "horizontal plane", "vertical coordinate again becomes zero"]):
        constraints.add("same_height_landing")
    if "perpendicular" in text:
        constraints.add("perpendicular")
    if "same time" in text:
        constraints.add("simultaneous_launch")
    if _contains_any(text, ["air drag", "air resistance", "quadratic drag", "drag force", "magnus"]):
        constraints.add("air_drag")
    if _contains_any(text, ["wall", "barrier", "obstacle"]):
        constraints.add("fixed_horizontal_distance")
    if (
        "no horizontal velocity" not in text
        and "without horizontal velocity" not in text
        and not ("initial horizontal velocity" in text and "find" in text)
        and _contains_any(text, ["thrown horizontally", "projected horizontally", "projected horizontal", "launched horizontally", "fired horizontally", "horizontally", "leaves a cliff horizontally", "leaves horizontally", "horizontal speed", "horizontal velocity", "rolls off"])
    ):
        constraints.add("horizontal")
    if _is_height_launch_context(text):
        constraints.add("initial_height")
    if "range" in text and ("angle" in text or "angles" in text):
        constraints.add("given_range")
    if "overshoot" in text or "short" in text:
        constraints.add("miss_distance")
    return constraints


def _infer_givens(text: str) -> list[str]:
    givens: list[str] = []
    _append_if_value(givens, "v0", _infer_velocity_value(text))
    _append_if_value(givens, "angle", _infer_launch_angle(text))
    _append_if_value(givens, "g", _infer_gravity(text))
    _append_if_value(givens, "target", _infer_point(text))
    _append_if_value(givens, "target", _infer_platform_target(text))
    _append_if_value(givens, "height", _infer_height(text))
    _append_if_value(givens, "time", _infer_time_value(text))
    _append_if_value(givens, "range", _infer_range_value(text))
    wall_values = _infer_wall_values(text)
    _append_if_value(givens, "wall_distance", wall_values.get("distance"))
    _append_if_value(givens, "wall_height", wall_values.get("height"))
    if _is_two_projectile_same_speed_comparison(text):
        angles = _infer_two_angle_values(text)
        _append_if_value(givens, "angle1", angles.get("angle1"))
        _append_if_value(givens, "angle2", angles.get("angle2"))
    givens.extend(_infer_two_projectile_components(text))
    return givens


def _engine_from_spec(world: str, unknown: str, constraints: set[str]) -> str | None:
    if world == "multi_projectile" and unknown == "same_speed_comparison":
        return "two_projectile_same_speed_comparison"
    if world == "level_ground":
        if unknown == "level_ground_multi_quantities":
            return "level_ground_multi_quantity"
        if unknown == "range_and_time_of_flight":
            return "level_ground_range_and_time"
        if unknown == "time_of_flight_derivation":
            return "level_ground_time_of_flight_derivation"
        if unknown == "time_to_peak":
            return "level_ground_time_to_peak"
        if unknown in {"range", "maximum_range"}:
            return "level_ground_range"
        if unknown == "time_of_flight":
            return "level_ground_time_of_flight"
        if unknown == "maximum_height":
            return "level_ground_max_height"
        if unknown == "position_at_time":
            return "level_ground_position_at_time"
        if unknown == "velocity_at_time":
            return "level_ground_velocity_at_time"
        if unknown == "initial_speed_from_same_height_times":
            return "same_height_times_initial_speed"
        if unknown == "maximum_height_from_trajectory_equation":
            return "trajectory_equation_max_height"
        if unknown == "scaled_projectile_quantity":
            return "projectile_height_scaling"
        if unknown == "launch_angle_from_range_height_relation":
            return "range_equals_max_height_angle"
        if unknown == "range_angle_scaling":
            return "range_angle_scaling"
        if unknown == "launch_angle":
            return "level_ground_launch_angle_from_range"
    if world == "split_at_apex":
        return "projectile_split_at_apex_fragment_time"
    if world == "bounce":
        return "bounce_restitution_height"
    if world == "piecewise_acceleration":
        return "piecewise_acceleration_at_apex_range"
    if world == "drag":
        return "air_drag_conceptual_timing" if unknown == "drag_effects" else None
    if world == "moving_wedge":
        return None
    if world == "height_launch":
        if unknown == "level_ground_multi_quantities":
            return "height_launch_horizontal_scenario" if "horizontal" in constraints else "height_launch_multi_quantity"
        if unknown == "unknown" and "horizontal" in constraints:
            return "height_launch_horizontal_scenario"
        if unknown == "time_of_flight":
            return "height_launch_time_of_flight"
        if unknown == "range":
            return "height_launch_range"
        if unknown == "maximum_range":
            return "max_range_from_height_fixed_speed"
    if world == "wall":
        if unknown == "height_at_wall":
            return "wall_height_at_distance"
        if unknown == "clears_wall_condition":
            return "wall_clearance_condition"
    if world == "target" and unknown == "minimum_speed":
        return "minimum_speed_to_hit_target"
    if world == "target" and unknown == "launch_angle":
        if "miss_distance" in constraints:
            return "target_angle_from_short_overshoot"
        return "target_launch_angle_fixed_speed"
    if unknown == "time_when_velocity_angle":
        return "horizontal_throw_velocity_angle_time"
    if world == "staircase" and unknown == "step_number":
        return "staircase_collision"
    if world == "multi_projectile" and unknown == "time_ratio_squared":
        return "two_projectile_interception_time_ratio"
    if world == "multi_projectile" and unknown == "vertical_throw_speed_for_apex_collision":
        return "relative_projectile_apex_collision"
    if world == "multi_projectile" and unknown == "collision_time":
        return "two_projectile_collision_time"
    if world == "two_inclines" and unknown == "impact_speed":
        return "two_inclines_perpendicular_launch_impact"
    if world == "incline" and unknown in {"range", "maximum_range"}:
        return "max_range_on_incline" if unknown == "maximum_range" else "perpendicular_launch_range_on_incline"
    return None


def _infer_velocity_value(text: str) -> str | None:
    patterns = [
        r"(?:speed|velocity|initial speed|initial velocity)\s*(?:of\s*)?=\s*([0-9]+(?:\.[0-9]+)?(?:\s*(?:sqrt|root|√)\(?[0-9]+\)?)?)\s*m/s",
        r"(?:speed|velocity|initial speed|initial velocity)\s*(?:of\s*)?([0-9]+(?:\.[0-9]+)?(?:\s*(?:sqrt|root|√)\(?[0-9]+\)?)?)\s*m/s",
        r"([0-9]+(?:\.[0-9]+)?(?:\s*(?:sqrt|root|√)\(?[0-9]+\)?)?)\s*m/s",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return f"{_normalize_radical(match.group(1))} m/s"
    return None


def _infer_launch_angle(text: str) -> str | None:
    if (
        "no horizontal velocity" not in text
        and "without horizontal velocity" not in text
        and not ("initial horizontal velocity" in text and "find" in text)
        and _contains_any(text, ["thrown horizontally", "projected horizontally", "projected horizontal", "launched horizontally", "fired horizontally", "horizontally", "horizontal speed", "horizontal velocity", "rolls off"])
    ):
        return "0deg"
    patterns = [
        r"(?:angle|at|making an angle of|inclination)\s*(?:of\s*)?([0-9]+(?:\.[0-9]+)?)\s*(?:deg|degree|degrees)",
        r"([0-9]+(?:\.[0-9]+)?)\s*(?:deg|degree|degrees)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            window = text[max(0, match.start() - 40) : match.end() + 40]
            sign = "-" if "below" in window or "downward" in window else ""
            return f"{sign}{match.group(1)}deg"
    if _is_vertical_upward_launch(text):
        return "90deg"
    return None


def _infer_two_angle_values(text: str) -> dict[str, str]:
    angles = re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*(?:deg|degree|degrees|°)", text)
    if len(angles) < 2:
        return {}
    return {"angle1": f"{angles[0]}deg", "angle2": f"{angles[1]}deg"}


def _is_two_projectile_same_speed_comparison(text: str) -> bool:
    if not _contains_any(text, ["two projectiles", "two particles", "two bodies"]):
        return False
    if not _contains_any(text, ["same speed", "same velocity", "same initial speed", "same initial velocity"]):
        return False
    if len(re.findall(r"[0-9]+(?:\.[0-9]+)?\s*(?:deg|degree|degrees|°)", text)) < 2:
        return False
    return "compare" in text and all(marker in text for marker in ("time", "height", "range"))


def _asks_time_to_peak(text: str) -> bool:
    peak_markers = ["maximum height", "highest point", "top", "peak"]
    time_markers = ["time to", "time taken", "how long", "when"]
    return _contains_any(text, peak_markers) and _contains_any(text, time_markers)


def _asks_range_and_time(text: str) -> bool:
    range_markers = ["range", "horizontal distance", "how far"]
    time_markers = ["time of flight", "flight time", "time taken", "how long"]
    return _contains_any(text, range_markers) and _contains_any(text, time_markers)


def _requested_level_ground_outputs(text: str) -> list[str]:
    if _is_special_non_composite_context(text):
        return []
    outputs: list[str] = []
    if _contains_any(text, ["initial speed", "speed needed", "speed of projection"]):
        outputs.append("initial_speed")
    if _contains_any(text, ["angle of projection", "launch angle", "find theta", "find the angle", "angle theta"]):
        outputs.append("launch_angle")
    if _contains_any(text, ["range", "horizontal distance", "distance from", "how far"]):
        outputs.append("range")
    if _contains_any(text, ["time of flight", "flight time", "total time"]):
        outputs.append("time_of_flight")
    if _asks_time_to_peak(text):
        outputs.append("time_to_peak")
    if _contains_any(text, ["maximum height", "max height", "greatest height"]):
        if not _asks_time_to_peak(text) or _contains_any(text, ["and maximum height", "and max height", "height and"]):
            outputs.append("maximum_height")
    if _contains_any(text, ["components", "component", "u_x", "ux", "uₓ", "u_y", "uy", "uᵧ", "horizontal velocity", "vertical velocity"]):
        outputs.append("components")
    return list(dict.fromkeys(outputs))


def _is_special_non_composite_context(text: str) -> bool:
    if "air drag" in text:
        return True
    if any(marker in text for marker in ("changed gravity", "gravity changes", "effective gravity", "enters a region")):
        return True
    if "range" in text and any(marker in text for marker in ("maximum height", "greatest height")) and any(
        marker in text for marker in ("same", "equal", "equals", "times")
    ):
        return True
    return False


def _is_height_launch_context(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "cliff",
            "tower",
            "building",
            "balcony",
            "platform",
            "table",
            "cart",
            "from a height",
            "from the top",
            "from the edge",
            "above the ground",
        )
    ) or re.search(
        r"(?:fall|falls|fell|drop|drops|dropped)\s+[0-9]+(?:\.[0-9]+)?\s*m\s+(?:to|before|until)\s+(?:the\s+)?ground",
        text,
    ) is not None


def _is_vertical_upward_launch(text: str) -> bool:
    return _contains_any(text, [
        "thrown upward",
        "thrown upwards",
        "projected upward",
        "projected upwards",
        "vertically upward",
        "vertically upwards",
        "straight up",
    ])


def _infer_gravity(text: str) -> str | None:
    match = re.search(r"\bg\s*=\s*([0-9]+(?:\.[0-9]+)?)", text)
    return f"{match.group(1)} m/s^2" if match else None


def _infer_height(text: str) -> str | None:
    patterns = [
        r"(?:from|on)\s+a\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:high|tall)\s+(?:cliff|tower|building|platform|table|balcony|cart)",
        r"([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:high|tall)\s+(?:cliff|tower|building|platform|table|balcony|cart)",
        r"(?:cliff|tower|building|platform|table|balcony|cart)\s+(?:is\s+)?([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:high|tall)",
        r"(?:from\s+a\s+)?([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:cliff|tower|building|platform|table|balcony|cart)",
        r"(?:height|height of|from a height of)\s*([0-9]+(?:\.[0-9]+)?)\s*m",
        r"(?:table|platform|balcony|cart)\s+of\s+height\s+([0-9]+(?:\.[0-9]+)?)\s*m",
        r"(?:balcony|platform|table|cart)\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+above\s+(?:the\s+)?ground",
        r"([0-9]+(?:\.[0-9]+)?)\s*m\s+above\s+(?:the\s+)?ground",
        r"(?:fall|falls|fell|drop|drops|dropped)\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:to|before|until)\s+(?:the\s+)?ground",
        r"([0-9]+(?:\.[0-9]+)?)\s*m\s+to\s+(?:the\s+)?ground",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return f"{match.group(1)}m"
    return None


def _infer_time_value(text: str) -> str | None:
    match = re.search(r"(?:after|at)\s+([0-9]+(?:\.[0-9]+)?)\s*(?:s|sec|second|seconds)\b", text)
    if match:
        return f"{match.group(1)}s"
    match = re.search(r"\bt\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*(?:s|sec|second|seconds)?\b", text)
    return f"{match.group(1)}s" if match else None


def _infer_range_value(text: str) -> str | None:
    patterns = [
        r"(?:range|horizontal range)\s*(?:of|=|is|equal to|equals|give|gives)?\s*([0-9]+(?:\.[0-9]+)?)\s*m",
        r"([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:range|horizontal range)",
        r"lands?\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:away|from)",
        r"lands?\s+[^.?\n]*?\b([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:away|from)",
        r"(?:horizontal distance|distance)\s+(?:of\s+)?([0-9]+(?:\.[0-9]+)?)\s*m",
        r"([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:from the base|from the foot|away from the base)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return f"{match.group(1)}m"
    return None


def _infer_wall_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    obstacle = r"(?:wall|barrier|obstacle)"
    distance_patterns = [
        rf"{obstacle}\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+away",
        rf"{obstacle}\s+is\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+away",
        rf"{obstacle}\s+is\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+from\s+(?:the\s+)?(?:point|projector|projection|launch)",
        rf"at\s+a\s+{obstacle}\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+away",
        rf"{obstacle}\s+at\s+([0-9]+(?:\.[0-9]+)?)\s*m",
    ]
    for pattern in distance_patterns:
        match = re.search(pattern, text)
        if match:
            values["distance"] = f"{match.group(1)}m"
            break
    height_patterns = [
        rf"{obstacle}\s+[0-9]+(?:\.[0-9]+)?\s*m\s+away\s+and\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:high|tall)",
        rf"{obstacle}\s+is\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:high|tall)",
        rf"([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:high|tall)\s+{obstacle}",
    ]
    for pattern in height_patterns:
        match = re.search(pattern, text)
        if match:
            values["height"] = f"{match.group(1)}m"
            break
    return values


def _infer_two_projectile_components(text: str) -> list[str]:
    compact = " ".join(text.split())
    givens: list[str] = []
    a_match = re.search(
        r"projectile a.*?x\s*=\s*([-+]?[0-9]+(?:\.[0-9]+)?) .*?velocity components\s*\(\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*,\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*\)",
        compact,
    )
    b_match = re.search(
        r"projectile b.*?x\s*=\s*([-+]?[0-9]+(?:\.[0-9]+)?) .*?velocity components\s*\(\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*,\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*\)",
        compact,
    )
    if a_match:
        givens.extend([f"p1_x0={a_match.group(1)}m", "p1_y0=0m", f"p1_vx={a_match.group(2)}m/s", f"p1_vy={a_match.group(3)}m/s"])
    if b_match:
        givens.extend([f"p2_x0={b_match.group(1)}m", "p2_y0=0m", f"p2_vx={b_match.group(2)}m/s", f"p2_vy={b_match.group(3)}m/s"])
    return givens


def _infer_point(text: str) -> str | None:
    match = re.search(r"\(\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*m?\s*,\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*m?\)", text)
    return f"({match.group(1)}m,{match.group(2)}m)" if match else None


def _infer_platform_target(text: str) -> str | None:
    match = re.search(
        r"platform\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+high\s+and\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+away",
        text,
    )
    if match:
        return f"({match.group(2)}m,{match.group(1)}m)"
    match = re.search(
        r"platform\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+high.*?([0-9]+(?:\.[0-9]+)?)\s*m\s+away",
        text,
    )
    return f"({match.group(2)}m,{match.group(1)}m)" if match else None


def _has_coordinate_pair(text: str) -> bool:
    return _infer_point(text) is not None


def _append_if_value(givens: list[str], key: str, value: str | None) -> None:
    if value:
        givens.append(f"{key}={value}")


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _is_non_ideal_projectile(text: str) -> bool:
    return _contains_any(text, ["air drag", "air resistance", "quadratic drag", "drag force", "magnus"])


def _is_quantitative_non_ideal_projectile(text: str) -> bool:
    if not _is_non_ideal_projectile(text):
        return False
    quantitative_markers = ["find", "calculate", "exact", "range", "deflection", "distance", "height"]
    conceptual_markers = ["choose", "correct alternative", "considered"]
    return _contains_any(text, quantitative_markers) and not _contains_any(text, conceptual_markers)


def _normalize_radical(value: str) -> str:
    cleaned = value.replace("root", "sqrt").replace("√", "sqrt").replace(" ", "")
    return re.sub(r"sqrt(\d+)", r"sqrt(\1)", cleaned)


def _normalize(text: str) -> str:
    return (
        text.lower()
        .replace("°", "deg")
        .replace("∘", "deg")
        .replace("𝑠", "s")
        .replace("𝑡", "t")
        .replace("−", "-")
        .replace("–", "-")
        .replace("—", "-")
    )
