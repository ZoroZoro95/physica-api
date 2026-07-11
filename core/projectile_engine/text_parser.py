from __future__ import annotations

import re
import math

from .mapper import map_projectile_problem


def infer_engine_case_and_givens(
    *,
    question_text: str,
    suggested_engine_case: str | None,
    givens: list[str],
) -> tuple[str | None, list[str]]:
    """Infer a supported engine case and missing givens from reviewed OCR/text."""
    text = _normalize(question_text)
    engine_case = suggested_engine_case
    inferred = list(givens)
    spec = map_projectile_problem(question_text)

    if not engine_case:
        engine_case = spec.engine_case or _infer_engine_case(text)

    inferred.extend(_infer_common_givens(text))
    inferred.extend(spec.givens)

    if engine_case == "velocity_change_interval":
        _append_if_missing(inferred, "dt", _infer_time_interval(text))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "velocity_angle_event_speed":
        _append_if_missing(inferred, "v0", _infer_first_number_after(text, ["speed", "velocity"]))
        _append_if_missing(inferred, "launch_angle", _infer_angle_after(text, ["projected at an angle", "angle of"]))
        _append_if_missing(inferred, "velocity_angle", _infer_angle_after(text, ["velocity makes an angle", "direction of its velocity"]))

    elif engine_case == "horizontal_throw_velocity_angle_time":
        _append_if_missing(inferred, "vx", _infer_velocity_value(text))
        _append_if_missing(inferred, "velocity_angle", _infer_angle_after(text, ["angle"]))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "minimum_speed_to_hit_target":
        target = _infer_point(text)
        if target:
            _append_if_missing(inferred, "target", target)
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "inclined_plane_impact_time":
        _append_if_missing(inferred, "incline", _infer_angle_after(text, ["inclination", "inclined plane of inclination"]))
        _append_if_missing(inferred, "launch_angle_horizontal", _infer_angle_after(text, ["angle of", "thrown at an angle"]))
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "max_range_from_height_fixed_speed":
        _append_if_missing(inferred, "height", _infer_first_number_after(text, ["height", "tower"]))
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case in {"height_launch_time_of_flight", "height_launch_range", "height_launch_multi_quantity"}:
        _append_if_missing(inferred, "height", _infer_launch_height(text))
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        explicit_angle = _infer_angle_after(text, ["angle", "at"])
        angle = "0deg" if _is_horizontal_launch(text) else explicit_angle or ("90deg" if _is_vertical_upward_launch(text) else None)
        _append_if_missing(inferred, "angle", angle)
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case in {"level_ground_range", "level_ground_range_and_time", "level_ground_multi_quantity"}:
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        _append_if_missing(inferred, "angle", _infer_angle_after(text, ["angle", "at"]))
        _append_if_missing(inferred, "time", _infer_time_value(text))
        _append_if_missing(inferred, "range", _infer_range_value(text))
        _append_if_missing(inferred, "max_height", _infer_known_max_height(text))
        _append_if_missing(inferred, "ux", _infer_horizontal_component(text) or _infer_peak_horizontal_component(text))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "projectile_split_at_apex_fragment_time":
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        _append_if_missing(inferred, "angle", _infer_angle_after(text, ["angle", "at"]))
        _append_if_missing(inferred, "g", _infer_gravity(text))
        _append_if_missing(inferred, "frag1_fall_time", _infer_fragment_fall_time(text))

    elif engine_case == "bounce_restitution_height":
        _append_if_missing(inferred, "height", _infer_bounce_reference_height(text) or _infer_launch_height(text) or _infer_known_max_height(text))
        _append_if_missing(inferred, "e", _infer_restitution(text))
        _append_if_missing(inferred, "post_bounce_height", _infer_post_bounce_height(text))
        _append_if_missing(inferred, "energy_retained_fraction", _infer_energy_retained_fraction(text))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "relative_projectile_apex_collision":
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        _append_if_missing(inferred, "angle", _infer_angle_after(text, ["angle", "at"]))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "piecewise_acceleration_at_apex_range":
        _append_if_missing(inferred, "range", _infer_range_value(text))
        _append_if_missing(inferred, "g1", _infer_gravity(text))
        _append_if_missing(inferred, "g2", _infer_changed_gravity(text))
        _append_if_missing(inferred, "acceleration_ratio", _infer_acceleration_ratio(text))

    elif engine_case in {"level_ground_time_of_flight", "level_ground_max_height", "level_ground_time_to_peak"}:
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        angle = "90deg" if _is_vertical_upward_launch(text) else _infer_angle_after(text, ["angle", "at"])
        _append_if_missing(inferred, "angle", angle)
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "height_launch_horizontal_scenario":
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        _append_if_missing(inferred, "vx", _infer_horizontal_component(text))
        _append_if_missing(inferred, "angle", "0deg")
        _append_if_missing(inferred, "height", _infer_launch_height(text))
        _append_if_missing(inferred, "time", _infer_time_value(text))
        _append_if_missing(inferred, "range", _infer_range_value(text))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "level_ground_position_at_time":
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        _append_if_missing(inferred, "ux", _infer_horizontal_component(text))
        _append_if_missing(inferred, "angle", _infer_angle_after(text, ["angle", "at"]))
        _append_if_missing(inferred, "time", _infer_time_value(text))
        point = _infer_coordinate_values(text)
        _append_if_missing(inferred, "x", point.get("x") or _infer_horizontal_position_value(text))
        _append_if_missing(inferred, "y", point.get("y") or _infer_height_point_value(text))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "level_ground_velocity_at_time":
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        _append_if_missing(inferred, "angle", _infer_angle_after(text, ["angle", "at"]))
        _append_if_missing(inferred, "time", _infer_time_value(text))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "same_height_times_initial_speed":
        _append_if_missing(inferred, "angle", _infer_angle_after(text, ["angle", "at"]))
        times = _infer_same_height_times(text)
        _append_if_missing(inferred, "t1", times.get("t1"))
        _append_if_missing(inferred, "t2", times.get("t2"))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "trajectory_equation_max_height":
        trajectory = _infer_trajectory_coefficients(text)
        _append_if_missing(inferred, "trajectory_a", trajectory.get("a"))
        _append_if_missing(inferred, "trajectory_b", trajectory.get("b"))

    elif engine_case == "projectile_height_scaling":
        _append_if_missing(inferred, "height", _infer_known_max_height(text))
        _append_if_missing(inferred, "speed_scale", _infer_speed_scale(text))

    elif engine_case == "range_angle_scaling":
        _append_if_missing(inferred, "range", _infer_range_value(text))
        angles = _infer_range_scaling_angles(text)
        _append_if_missing(inferred, "angle1", angles.get("angle1"))
        _append_if_missing(inferred, "angle2", angles.get("angle2"))

    elif engine_case == "two_projectile_same_speed_comparison":
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        angles = _infer_range_scaling_angles(text)
        _append_if_missing(inferred, "angle1", angles.get("angle1"))
        _append_if_missing(inferred, "angle2", angles.get("angle2"))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "range_equals_max_height_angle":
        pass

    elif engine_case == "level_ground_launch_angle_from_range":
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        _append_if_missing(inferred, "range", _infer_range_value(text))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case in {"wall_height_at_distance", "wall_clearance_condition"}:
        wall = _infer_wall_values(text)
        two_wall = _infer_two_wall_values(text)
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        _append_if_missing(inferred, "angle", _infer_angle_after(text, ["angle", "at"]))
        _append_if_missing(inferred, "wall_distance", wall.get("distance"))
        _append_if_missing(inferred, "wall_height", wall.get("height"))
        _append_if_missing(inferred, "wall_x1", two_wall.get("x1"))
        _append_if_missing(inferred, "wall_x2", two_wall.get("x2"))
        _append_if_missing(inferred, "wall_height", two_wall.get("height"))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "target_launch_angle_fixed_speed":
        target = _infer_point(text) or _infer_platform_target(text)
        if target:
            _append_if_missing(inferred, "target", target)
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "vertical_component_height_times":
        _append_if_missing(inferred, "uy", _infer_vertical_component(text))
        _append_if_missing(inferred, "height", _infer_height_point_value(text))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "trajectory_equation_from_launch":
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        _append_if_missing(inferred, "angle", _infer_angle_after(text, ["angle", "at"]))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "monkey_hunter_condition":
        _append_if_missing(inferred, "v0", _infer_velocity_value(text))
        _append_if_missing(inferred, "height", _infer_height_point_value(text))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "two_projectile_collision_time":
        for given in _infer_two_projectile_components(text):
            if "=" in given:
                key, value = given.split("=", 1)
                _append_if_missing(inferred, key, value)

    elif engine_case == "staircase_collision":
        dimensions = _infer_staircase_dimensions(text)
        _append_if_missing(inferred, "vx", _infer_velocity_value(text))
        _append_if_missing(inferred, "step_height", dimensions.get("height"))
        _append_if_missing(inferred, "step_width", dimensions.get("width"))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    elif engine_case == "projectile_collides_with_sliding_particle_on_incline":
        _append_if_missing(inferred, "collision_time", _infer_time_value(text))
        _append_if_missing(inferred, "incline", _infer_angle_after(text, ["incline", "inclined plane", "smooth inclined plane"]))
        _append_if_missing(inferred, "g", _infer_gravity(text))

    return engine_case, _dedupe_givens(inferred)


def _infer_engine_case(text: str) -> str | None:
    if _is_quantitative_non_ideal_projectile(text) or _is_moving_wedge_projectile(text):
        return None
    if ("derive" in text or "derivation" in text or "prove" in text or "show that" in text) and (
        "time of flight" in text or "flight time" in text
    ):
        return "level_ground_time_of_flight_derivation"
    if "change in velocity" in text and "time interval" in text:
        return "velocity_change_interval"
    if "trajectory" in text and ("equation" in text or "in terms of x and y" in text):
        return "trajectory_equation_from_launch"
    if "monkey" in text and "hunter" in text:
        return "monkey_hunter_condition"
    if _is_two_projectile_same_speed_comparison(text):
        return "two_projectile_same_speed_comparison"
    if "vertical component" in text and "height" in text and ("two times" in text or "times at which" in text):
        return "vertical_component_height_times"
    if ("required initial speed" in text or "initial speed" in text) and ("lands" in text or "range" in text):
        return "level_ground_multi_quantity"
    if _contains_any(text, ["wall", "barrier", "obstacle"]) and _contains_any(text, ["clear", "clears", "cross", "crosses"]):
        return "wall_clearance_condition"
    if ("coordinates are" in text or ("x" in text and "y" in text and "=" in text)) and any(
        marker in text for marker in ("initial horizontal velocity", "initial vertical velocity", "initial speed", "angle of projection")
    ):
        return "level_ground_position_at_time"
    if "passes through" in text and "high after" in text and "horizontal velocity" in text:
        return "level_ground_position_at_time"
    if _is_height_launch_context(text) and _asks_impact_velocity(text):
        return "height_launch_horizontal_scenario" if _is_horizontal_launch(text) else "height_launch_multi_quantity"
    if _is_height_launch_context(text) and len(_requested_level_ground_outputs(text)) >= 2:
        return "height_launch_horizontal_scenario" if _is_horizontal_launch(text) else "height_launch_multi_quantity"
    if len(_requested_level_ground_outputs(text)) >= 2:
        return "level_ground_multi_quantity"
    if "component" in text and _infer_velocity_value(text) and _infer_angle_after(text, ["angle", "at"]):
        return "level_ground_multi_quantity"
    if ("possible angles" in text or "possible angle" in text or "angles of projection" in text) and (
        "range" in text or "lands" in text or "target" in text
    ):
        return "level_ground_launch_angle_from_range"
    if _asks_time_to_peak(text):
        return "level_ground_time_to_peak"
    if (
        "hit by a stone" in text
        and "same time" in text
        and ("t1/t2" in text or "t_1/t_2" in text or "t₁/t₂" in text)
    ):
        return "two_projectile_interception_time_ratio"
    if ("splits into" in text or "split into" in text or "splits at" in text or "split at" in text) and (
        "highest point" in text or "apex" in text
    ):
        return "projectile_split_at_apex_fragment_time"
    if "coefficient of restitution" in text or "bounce" in text or "bounces" in text or "rebound" in text:
        return "bounce_restitution_height"
    if ("highest point" in text or "apex" in text) and ("gravity changes" in text or "effective gravity" in text or "enters a region" in text):
        return "piecewise_acceleration_at_apex_range"
    if ("highest point" in text or "apex" in text) and ("collides" in text or "collision" in text) and "vertically" in text:
        return "relative_projectile_apex_collision"
    if "initial speed" in text and "x=" in text and "y=" in text:
        return "parametric_initial_speed"
    if "direction of its velocity" in text and "angle" in text and "speed" in text:
        return "velocity_angle_event_speed"
    if _is_horizontal_launch(text):
        if _is_height_launch_context(text):
            return "height_launch_horizontal_scenario"
        if "angle" in text:
            return "horizontal_throw_velocity_angle_time"
        if "inclined" in text or "incline" in text:
            return "horizontal_launch_onto_incline_distance"
    if "perpendicular to the velocity of projection" in text:
        return "velocity_perpendicular_to_initial_event"
    if "minimum velocity" in text and "target" in text:
        return "minimum_speed_to_hit_target"
    if "lands on a platform" in text and ("angle" in text or "angles" in text):
        return "target_launch_angle_fixed_speed"
    if ("launch angle" in text or "launch angles" in text or "what angle" in text) and "target" in text:
        return "target_launch_angle_fixed_speed"
    if "impossible to hit the target" in text:
        return "target_reachability_fixed_speed"
    if "inclined plane" in text and "time" in text and ("hit" in text or "strike" in text):
        return "inclined_plane_impact_time"
    if "maximum possible range" in text and "tower" in text:
        return "max_range_from_height_fixed_speed"
    if "fielder" in text and "catch" in text:
        return "fielder_catch_before_ground"
    if "average velocity" in text and "highest point" in text:
        return "average_velocity_to_peak"
    if "horizontal acceleration" in text or "due to wind" in text:
        return "projectile_with_horizontal_acceleration"
    if ("position after" in text or "coordinates after" in text or "position at" in text or "position and velocity" in text or "displacement" in text) and "inclined" not in text:
        return "level_ground_position_at_time"
    if any(marker in text for marker in ("height of the projectile when", "height of the ball when", "height when", "height and vertical velocity when")) and any(
        marker in text for marker in ("covered", "travelled", "traveled", "away", "horizontal range")
    ):
        return "level_ground_position_at_time"
    if (
        "velocity after" in text
        or "velocity at" in text
        or "velocity one" in text
        or "speed after" in text
        or "speed at" in text
    ) and "inclined" not in text:
        return "level_ground_velocity_at_time"
    if "same height" in text and ("two times" in text or " at " in text):
        return "same_height_times_initial_speed"
    if "trajectory" in text and "y=" in text and ("maximum height" in text or "greatest height" in text):
        return "trajectory_equation_max_height"
    if ("velocity is halved" in text or "speed is halved" in text or "initial velocity is halved" in text) and "maximum height" in text:
        return "projectile_height_scaling"
    if "range" in text and ("maximum height" in text or "greatest height" in text) and (
        "same" in text or "equal" in text or "equals" in text or "times" in text
    ):
        return "range_equals_max_height_angle"
    if "same velocity" in text and "range" in text and "angle" in text:
        return "range_angle_scaling"
    if ("launch angles" in text or "what launch angles" in text or "what angle" in text) and "range" in text:
        return "level_ground_launch_angle_from_range"
    if _contains_any(text, ["wall", "barrier", "obstacle"]) and _contains_any(text, ["clear", "clears", "cross", "crosses"]):
        return "wall_clearance_condition"
    if _contains_any(text, ["wall", "barrier", "obstacle"]) and _contains_any(text, ["height", "at a wall", "at the wall", "at a barrier", "at the barrier", "at an obstacle"]):
        return "wall_height_at_distance"
    if (
        "time of flight" in text
        or "flight time" in text
        or "time in air" in text
        or "airtime" in text
        or "duration" in text
        or "hits the ground" in text
        or "how long" in text
        or "take to fall" in text
        or "time to fall" in text
    ) and _is_height_launch_context(text):
        return "height_launch_time_of_flight"
    if _is_horizontal_launch(text) and _is_height_launch_context(text):
        return "height_launch_horizontal_scenario"
    if ("horizontal range" in text or "horizontal distance" in text or "lands" in text) and _is_height_launch_context(text):
        return "height_launch_range"
    if _is_level_ground_range_request(text):
        return "level_ground_range"
    if "projectile a" in text and "projectile b" in text and ("collide" in text or "collision" in text):
        return "two_projectile_collision_time"
    if "maximum possible range" in text and "inclined" in text:
        return "max_range_on_incline"
    return None


def _infer_common_givens(text: str) -> list[str]:
    givens: list[str] = []
    g = _infer_gravity(text)
    if g:
        givens.append(f"g={g}")
    direction = _horizontal_direction_sign(text)
    if direction < 0:
        givens.append("x_direction=-1")
    return givens


def _infer_gravity(text: str) -> str | None:
    match = re.search(r"\bg\s*=\s*([0-9]+(?:\.[0-9]+)?)", text)
    return f"{match.group(1)} m/s^2" if match else None


def _infer_time_interval(text: str) -> str | None:
    compact = text.replace(" ", "")
    patterns = [
        r"t=([0-9]+(?:\.[0-9]+)?)(?:s)?(?:to|-|until)t?=([0-9]+(?:\.[0-9]+)?)",
        r"from([0-9]+(?:\.[0-9]+)?)(?:s)?(?:to|-|until)([0-9]+(?:\.[0-9]+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, compact)
        if match:
            dt = abs(float(match.group(2)) - float(match.group(1)))
            return f"{dt:g}s"
    match = re.search(r"timeinterval.*?([0-9]+(?:\.[0-9]+)?)s", compact)
    return f"{match.group(1)}s" if match else None


def _infer_velocity_value(text: str) -> str | None:
    match = re.search(r"(?<![\w.])([+-]?[0-9]+(?:\.[0-9]+)?)\s*i\s*m/s\b", text)
    if match:
        return f"{abs(float(match.group(1))):g} m/s"
    match = re.search(r"(?:velocity|speed)\s+(?:of\s+)?([0-9]+(?:\.[0-9]+)?(?:\s*(?:sqrt|root|√)\(?[0-9]+\)?)?)\s*m/s", text)
    if match:
        return f"{_normalize_radical(match.group(1))} m/s"
    match = re.search(r"([0-9]+(?:\.[0-9]+)?(?:\s*(?:sqrt|root|√)\(?[0-9]+\)?)?)\s*m/s", text)
    return f"{_normalize_radical(match.group(1))} m/s" if match else None


def _infer_first_number_after(text: str, markers: list[str]) -> str | None:
    for marker in markers:
        index = text.find(marker)
        if index < 0:
            continue
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text[index:])
        if match:
            return match.group(1)
    return None


def _infer_launch_height(text: str) -> str | None:
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


def _is_horizontal_launch(text: str) -> bool:
    if "no horizontal velocity" in text or "without horizontal velocity" in text:
        return False
    if "initial horizontal velocity" in text and "find" in text:
        return False
    if re.search(r"\bu[_\s]*y\s*=\s*0\b", text) or re.search(r"\buy\s*=\s*0\b", text):
        return True
    if re.search(r"(?<![\w.])[+-]?[0-9]+(?:\.[0-9]+)?\s*i\s*m/s\b", text):
        return True
    if re.search(r"\b0\s*(?:deg|degree|degrees)\s+(?:from|above|with)\s+(?:the\s+)?horizontal\b", text):
        return True
    return (
        "thrown horizontally" in text
        or "projected horizontally" in text
        or "projected horizontal" in text
        or "launched horizontally" in text
        or "fired horizontally" in text
        or "horizontally" in text
        or "parallel to the ground" in text
        or "parallel to ground" in text
        or "x direction" in text
        or "sideways" in text
        or "horizontal speed" in text
        or "horizontal velocity" in text
        or "rolls off" in text
        or "leaves a cliff horizontally" in text
        or "leaves horizontally" in text
    )


def _is_height_launch_context(text: str) -> bool:
    launch_markers = (
        "cliff",
        "tower",
        "building",
        "balcony",
        "roof",
        "platform",
        "table",
        "cart",
        "from a height",
        "from height",
        "from the top",
        "from the edge",
        "above the ground",
        "above ground",
    )
    return any(marker in text for marker in launch_markers) or re.search(
        r"(?:fall|falls|fell|drop|drops|dropped)\s+[0-9]+(?:\.[0-9]+)?\s*m\s+(?:to|before|until)\s+(?:the\s+)?ground",
        text,
    ) is not None


def _asks_time_to_peak(text: str) -> bool:
    peak_markers = [
        "maximum height",
        "max height",
        "highest point",
        "highest height",
        "topmost point",
        "top of its path",
        "top of the path",
        "top of trajectory",
        "top of the trajectory",
        "peak",
        "apex",
    ]
    time_markers = ["time to", "time taken", "how long", "when"]
    return any(marker in text for marker in peak_markers) and any(marker in text for marker in time_markers)


def _asks_range_and_time(text: str) -> bool:
    range_markers = ["range", "horizontal distance", "ground distance", "distance covered on ground", "distance on ground", "how far"]
    time_markers = ["time of flight", "flight time", "time taken", "time in air", "airtime", "how long"]
    return any(marker in text for marker in range_markers) and any(marker in text for marker in time_markers)


def _requested_level_ground_outputs(text: str) -> list[str]:
    if _is_special_non_composite_context(text):
        return []
    output_tokens = set(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())
    outputs: list[str] = []
    if any(marker in text for marker in ("initial speed", "speed needed", "speed of projection")):
        outputs.append("initial_speed")
    if any(marker in text for marker in ("angle of projection", "launch angle", "find theta", "find the angle", "angle theta")):
        outputs.append("launch_angle")
    if any(marker in text for marker in ("range", "horizontal distance", "ground distance", "distance covered", "distance travelled", "distance traveled", "distance covered on ground", "distance on ground", "distance from", "how far")) or "r" in output_tokens:
        outputs.append("range")
    if any(marker in text for marker in (
        "time of flight",
        "flight time",
        "flight duration",
        "duration of flight",
        "total time",
        "time in air",
        "total time in air",
        "airtime",
        "stays in the air",
        "stays in air",
        "time taken",
        "reach the ground",
        "to reach the ground",
        "hits the ground",
        "hit the ground",
    )) or "t" in output_tokens:
        outputs.append("time_of_flight")
    if _asks_time_to_peak(text):
        outputs.append("time_to_peak")
    if any(marker in text for marker in ("maximum height", "max height", "greatest height", "peak height", "highest height", "maximum altitude", "altitude gained")) or "h" in output_tokens:
        if not _asks_time_to_peak(text) or any(marker in text for marker in ("and maximum height", "and max height", "height and")):
            outputs.append("maximum_height")
    if _asks_impact_speed(text):
        outputs.append("impact_speed")
    if _asks_impact_angle(text):
        outputs.append("impact_angle")
    if any(marker in text for marker in ("components", "component", "u_x", "ux", "uₓ", "u_y", "uy", "uᵧ", "horizontal velocity", "vertical velocity")):
        outputs.append("components")
    return list(dict.fromkeys(outputs))


def _asks_impact_velocity(text: str) -> bool:
    return _asks_impact_speed(text) or _asks_impact_angle(text)


def _asks_impact_speed(text: str) -> bool:
    return any(marker in text for marker in (
        "impact speed",
        "speed at ground impact",
        "speed and direction",
        "speed just before",
        "speed before impact",
        "speed before hitting",
        "speed with which it hits",
        "speed with which it hit",
        "final speed",
        "magnitude of the velocity",
        "magnitude and direction",
        "resultant velocity",
        "velocity vector",
        "impact velocity",
        "velocity at impact",
        "velocity just before",
        "velocity when it reaches",
        "velocity when it reaches the ground",
        "velocity when it hits",
        "velocity when it hits the ground",
        "just before impact",
        "just before striking",
        "just before hitting",
        "just before it lands",
        "just before reaching the ground",
        "ground impact",
    ))


def _asks_impact_angle(text: str) -> bool:
    return any(marker in text for marker in (
        "impact angle",
        "angle made by the velocity",
        "angle with the horizontal",
        "angle its velocity makes",
        "angle the velocity makes",
        "angle below the horizontal",
        "angle of descent",
        "speed and direction",
        "direction of its velocity",
        "direction of the velocity",
        "magnitude and direction",
        "direction just before",
        "direction at impact",
        "velocity when it reaches",
        "velocity when it reaches the ground",
        "velocity when it hits",
        "velocity when it hits the ground",
        "just before it lands",
        "velocity vector",
        "impact velocity",
    ))


def _is_special_non_composite_context(text: str) -> bool:
    if _is_non_ideal_projectile(text) or _is_moving_wedge_projectile(text):
        return True
    if any(marker in text for marker in ("changed gravity", "gravity changes", "effective gravity", "enters a region")):
        return True
    if "range" in text and any(marker in text for marker in ("maximum height", "greatest height")) and any(
        marker in text for marker in ("same", "equal", "equals", "times")
    ):
        return True
    return False


def _is_level_ground_range_request(text: str) -> bool:
    if any(marker in text for marker in ("inclined", "incline", "tower", "height", "cliff")):
        return False
    return any(
        marker in text
        for marker in (
            "range",
            "horizontal distance",
            "ground distance",
            "distance covered on ground",
            "distance on ground",
            "where does it land",
        )
    )


def _is_non_ideal_projectile(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "air drag",
            "air resistance",
            "quadratic drag",
            "drag force",
            "magnus",
        )
    )


def _is_quantitative_non_ideal_projectile(text: str) -> bool:
    if not _is_non_ideal_projectile(text):
        return False
    quantitative_markers = ("find", "calculate", "exact", "range", "deflection", "distance", "height")
    conceptual_markers = ("choose", "correct alternative", "considered")
    return any(marker in text for marker in quantitative_markers) and not any(marker in text for marker in conceptual_markers)


def _is_moving_wedge_projectile(text: str) -> bool:
    return any(marker in text for marker in ("moving wedge", "wedge moving", "moving incline"))


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _is_vertical_upward_launch(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "thrown upward",
            "thrown upwards",
            "projected upward",
            "projected upwards",
            "vertically upward",
            "vertically upwards",
            "straight up",
        )
    )


def _infer_time_value(text: str) -> str | None:
    match = re.search(r"(?:after|at)\s+([0-9]+(?:\.[0-9]+)?)\s*(?:s|sec|second|seconds)\b", text)
    if match:
        return f"{match.group(1)}s"
    patterns = [
        r"(?:takes|take|taken)\s+([0-9]+(?:\.[0-9]+)?)\s*(?:s|sec|second|seconds)\b",
        r"(?:returns? to (?:the )?same level|returns? to (?:the )?ground)\s+after\s+([0-9]+(?:\.[0-9]+)?)\s*(?:s|sec|second|seconds)\b",
        r"(?:time of flight|total time of flight|flight time|time in air)\s*(?:is|=|of)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:s|sec|second|seconds)\b",
        r"(?:strikes|hits)\s+(?:the\s+)?ground\s+after\s+([0-9]+(?:\.[0-9]+)?)\s*(?:s|sec|second|seconds)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return f"{match.group(1)}s"
    word_match = re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:s|sec|second|seconds)\s+later\b", text)
    if word_match:
        return f"{_number_word_value(word_match.group(1)):g}s"
    match = re.search(r"\bt\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*(?:s|sec|second|seconds)?\b", text)
    return f"{match.group(1)}s" if match else None


def _infer_same_height_times(text: str) -> dict[str, str]:
    matches = re.findall(r"(?:t\s*=\s*)?([0-9]+(?:\.[0-9]+)?)\s*(?:s|sec|second|seconds)\b", text)
    if len(matches) >= 2:
        return {"t1": f"{matches[0]}s", "t2": f"{matches[1]}s"}
    matches = re.findall(r"\b([0-9]+(?:\.[0-9]+)?)\s*(?:s|sec|second|seconds)\b", text)
    if len(matches) >= 2:
        return {"t1": f"{matches[0]}s", "t2": f"{matches[1]}s"}
    return {}


def _infer_trajectory_coefficients(text: str) -> dict[str, str]:
    compact = text.replace(" ", "")
    match = re.search(
        r"y=([+-]?(?:[0-9]+(?:\.[0-9]+)?|\([^)]*\)|sqrt\(?[0-9]+\)?))\*?x([+-])x\^2/([0-9]+(?:\.[0-9]+)?)",
        compact,
    )
    if match:
        a = _normalize_radical(match.group(1).strip("()"))
        sign = -1.0 if match.group(2) == "-" else 1.0
        b = sign / float(match.group(3))
        return {"a": a, "b": f"{b:g}"}
    match = re.search(
        r"y=([+-]?[0-9]+(?:\.[0-9]+)?)\*?x([+-])([0-9]+(?:\.[0-9]+)?)\*?x\^2",
        compact,
    )
    if match:
        b = float(match.group(3)) * (-1 if match.group(2) == "-" else 1)
        return {"a": match.group(1), "b": f"{b:g}"}
    return {}


def _infer_known_max_height(text: str) -> str | None:
    patterns = [
        r"maximum height(?: reached)?(?: by a projectile)?\s*(?:is|=)?\s*([0-9]+(?:\.[0-9]+)?)\s*m",
        r"([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:maximum height|high)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return f"{match.group(1)}m"
    return None


def _infer_post_bounce_height(text: str) -> str | None:
    patterns = [
        r"(?:post-bounce|post bounce|after bounce|after rebounding|after rebound).*?(?:maximum height|height)\s*(?:is|=|of)?\s*([0-9]+(?:\.[0-9]+)?)\s*m",
        r"(?:rises|rebounds).*?(?:to|height of)\s*([0-9]+(?:\.[0-9]+)?)\s*m",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return f"{match.group(1)}m"
    return None


def _infer_bounce_reference_height(text: str) -> str | None:
    patterns = [
        r"(?:pre-bounce|pre bounce|before bounce|drop)\s+(?:vertical\s+)?height\s*(?:is|=)?\s*([0-9]+(?:\.[0-9]+)?)\s*m",
        r"(?:falls|dropped|drops)\s+from\s+(?:a\s+)?height\s*(?:of)?\s*([0-9]+(?:\.[0-9]+)?)\s*m",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return f"{match.group(1)}m"
    return None


def _infer_restitution(text: str) -> str | None:
    patterns = [
        r"(?:coefficient of restitution|restitution coefficient|e)\s*(?:is|=)?\s*([0-9]+(?:\.[0-9]+)?)",
        r"\be\s*=\s*([0-9]+(?:\.[0-9]+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def _infer_energy_retained_fraction(text: str) -> str | None:
    lost = re.search(r"los(?:es|t)\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*(?:of\s*)?(?:kinetic energy|energy)", text)
    if lost:
        return f"{1 - float(lost.group(1)) / 100:g}"
    retained = re.search(r"(?:retains|keeps)\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*(?:of\s*)?(?:kinetic energy|energy)", text)
    if retained:
        return f"{float(retained.group(1)) / 100:g}"
    return None


def _infer_changed_gravity(text: str) -> str | None:
    match = re.search(r"(?:changed|changes|becomes|effective gravity is|new gravity is)\s*(?:to\s*)?([0-9]+(?:\.[0-9]+)?)\s*m/s\^?2", text)
    if match:
        return f"{match.group(1)} m/s^2"
    return None


def _infer_acceleration_ratio(text: str) -> str | None:
    compact = text.replace(" ", "")
    match = re.search(r"(?:g'|g2|newgravity|effectivegravity|gravity)(?:becomes|=|is)?g/([0-9]+(?:\.[0-9]+)?)", compact)
    if match:
        return f"1/{match.group(1)}"
    match = re.search(r"(?:g'|g2|newgravity|effectivegravity|gravity)(?:becomes|=|is)?([0-9]+(?:\.[0-9]+)?)g", compact)
    if match:
        return match.group(1)
    return None


def _infer_speed_scale(text: str) -> str | None:
    if "halved" in text or "half" in text:
        return "0.5"
    match = re.search(r"(?:speed|velocity).*?(?:becomes|changed to)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:times|x)", text)
    return match.group(1) if match else None


def _infer_range_scaling_angles(text: str) -> dict[str, str]:
    angles = re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*(?:deg|degree|degrees)", text)
    if len(angles) >= 2:
        return {"angle1": f"{angles[0]}deg", "angle2": f"{angles[1]}deg"}
    return {}


def _is_two_projectile_same_speed_comparison(text: str) -> bool:
    if not _contains_any(text, ["two projectiles", "two particles", "two bodies"]):
        return False
    if not _contains_any(text, ["same speed", "same velocity", "same initial speed", "same initial velocity"]):
        return False
    if len(re.findall(r"[0-9]+(?:\.[0-9]+)?\s*(?:deg|degree|degrees|°)", text)) < 2:
        return False
    return "compare" in text and all(marker in text for marker in ("time", "height", "range"))


def _infer_fragment_fall_time(text: str) -> str | None:
    match = re.search(
        r"one\s+part\s+falls\s+vertically\s+down\s+to\s+the\s+ground,\s*([0-9]+(?:\.[0-9]+)?)\s*(?:s|sec|second|seconds)\s+after\s+the\s+splitting",
        text,
    )
    return f"{match.group(1)}s" if match else None


def _infer_range_value(text: str) -> str | None:
    patterns = [
        r"(?:range|horizontal range)\s*(?:of|=|is|equal to|equals|give|gives)?\s*([0-9]+(?:\.[0-9]+)?)\s*m",
        r"(?:range|horizontal range)\b[^.?\n]*?\b(?:is|=|equals|equal to)\s*([0-9]+(?:\.[0-9]+)?)\s*m",
        r"([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:range|horizontal range)",
        r"lands?\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:away|from)",
        r"lands?\s+[^.?\n]*?\b([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:away|from)",
        r"(?:horizontal distance|distance)\s+(?:of\s+)?([0-9]+(?:\.[0-9]+)?)\s*m",
        r"([0-9]+(?:\.[0-9]+)?)\s*m\s+(?:from the base|from the foot|away from the base)",
        r"target\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+away",
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
        rf"{obstacle}s?\s+of\s+equal\s+height\s+([0-9]+(?:\.[0-9]+)?)\s*m",
    ]
    for pattern in height_patterns:
        match = re.search(pattern, text)
        if match:
            values["height"] = f"{match.group(1)}m"
            break
    return values


def _infer_two_wall_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    height_match = re.search(r"walls?\s+of\s+equal\s+height\s+([0-9]+(?:\.[0-9]+)?)\s*m", text)
    distances_match = re.search(
        r"distances?\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+and\s+([0-9]+(?:\.[0-9]+)?)\s*m",
        text,
    )
    if height_match:
        values["height"] = f"{height_match.group(1)}m"
    if distances_match:
        values["x1"] = f"{distances_match.group(1)}m"
        values["x2"] = f"{distances_match.group(2)}m"
    return values


def _infer_two_projectile_components(text: str) -> list[str]:
    compact = " ".join(text.split())
    givens: list[str] = []
    a_match = re.search(
        r"projectile a.*?(?:x\s*=\s*)?([-+]?[0-9]+(?:\.[0-9]+)?)\s*m?.*?velocity components\s*\(\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*,\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*\)",
        compact,
    )
    b_match = re.search(
        r"projectile b.*?(?:x\s*=\s*)?([-+]?[0-9]+(?:\.[0-9]+)?)\s*m?.*?velocity components\s*\(\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*,\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*\)",
        compact,
    )
    if a_match:
        givens.extend([f"p1_x0={a_match.group(1)}m", "p1_y0=0m", f"p1_vx={a_match.group(2)}m/s", f"p1_vy={a_match.group(3)}m/s"])
    if b_match:
        givens.extend([f"p2_x0={b_match.group(1)}m", "p2_y0=0m", f"p2_vx={b_match.group(2)}m/s", f"p2_vy={b_match.group(3)}m/s"])
    return givens


def _infer_angle_after(text: str, markers: list[str]) -> str | None:
    for marker in markers:
        index = text.find(marker)
        if index < 0:
            continue
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:deg|degree|degrees|°)", text[index:])
        if match:
            window = text[index : index + match.end() + 40]
            sign = "-" if "below" in window or "downward" in window else ""
            return f"{sign}{match.group(1)}deg"
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:deg|degree|degrees|°)", text)
    if not match:
        return None
    window = text[max(0, match.start() - 40) : match.end() + 40]
    sign = "-" if "below" in window or "downward" in window else ""
    return f"{sign}{match.group(1)}deg"


def _infer_horizontal_component(text: str) -> str | None:
    vector_match = re.search(r"(?<![\w.])([+-]?[0-9]+(?:\.[0-9]+)?)\s*i\s*m/s\b", text)
    if vector_match:
        return f"{float(vector_match.group(1)):g} m/s"
    patterns = [
        r"(?:horizontal component|horizontal speed|horizontal velocity|u_x|ux|v_x|vx)\s*(?:of\s+velocity\s*)?(?:is|=|of)?\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s*m/s",
        r"([+-]?[0-9]+(?:\.[0-9]+)?)\s*m/s\s+(?:horizontally|horizontal)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return f"{match.group(1)} m/s"
    if _is_horizontal_launch(text):
        speed = _infer_velocity_value(text)
        if speed:
            sign = _horizontal_direction_sign(text)
            return f"{'-' if sign < 0 else ''}{speed}"
    return None


def _horizontal_direction_sign(text: str) -> int:
    if re.search(
        r"(?:\b(?:to\s+the\s+left|towards\s+the\s+left|leftward|westward|to\s+the\s+west|towards\s+the\s+west|negative\s+x|negative\s+x-axis|negative\s+x\s+axis)\b|-\s*x\s+(?:axis|direction))",
        text,
    ):
        return -1
    return 1


def _infer_vertical_component(text: str) -> str | None:
    patterns = [
        r"(?:vertical component|vertical speed|vertical velocity|u_y|uy|v_y|vy)\s*(?:of\s+(?:the\s+)?initial\s+velocity\s*)?(?:is|=|of)?\s*([0-9]+(?:\.[0-9]+)?)\s*m/s",
        r"(?:vertical component|vertical speed|vertical velocity)\b.*?(?:is|=)\s*([0-9]+(?:\.[0-9]+)?)\s*m/s",
        r"([0-9]+(?:\.[0-9]+)?)\s*m/s\s+vertical",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return f"{match.group(1)} m/s"
    return None


def _infer_peak_horizontal_component(text: str) -> str | None:
    match = re.search(
        r"(?:velocity|speed)\s+at\s+(?:the\s+)?(?:highest point|apex)\s+(?:is|=)?\s*([0-9]+(?:\.[0-9]+)?)\s*m/s",
        text,
    )
    return f"{match.group(1)} m/s" if match else None


def _infer_point(text: str) -> str | None:
    match = re.search(r"\(([0-9]+(?:\.[0-9]+)?)\s*m?\s*,\s*([0-9]+(?:\.[0-9]+)?)\s*m?\)", text)
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


def _infer_coordinate_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    x_match = re.search(r"\bx\s*=\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*m?", text)
    y_match = re.search(r"\by\s*=\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*m?", text)
    if x_match:
        values["x"] = f"{x_match.group(1)}m"
    if y_match:
        values["y"] = f"{y_match.group(1)}m"
    return values


def _infer_horizontal_position_value(text: str) -> str | None:
    half_range = re.search(r"half\s+of\s+its\s+horizontal\s+range", text)
    if half_range:
        v0 = _parse_float_from_value(_infer_velocity_value(text))
        angle = _parse_float_from_value(_infer_angle_after(text, ["angle", "at"]))
        g = _parse_float_from_value(_infer_gravity(text)) or 10.0
        if v0 is not None and angle is not None:
            range_value = v0 * v0 * math.sin(math.radians(2 * angle)) / g
            return f"{range_value / 2:g}m"
    patterns = [
        r"(?:travelled|traveled|covered)\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+horizontally",
        r"(?:travelled|traveled|covered)\s+([0-9]+(?:\.[0-9]+)?)\s*m",
        r"fielder\s+is\s+standing\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+away",
        r"reaches\s+(?:the\s+)?fielder.*?([0-9]+(?:\.[0-9]+)?)\s*m",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return f"{match.group(1)}m"
    return None


def _infer_height_point_value(text: str) -> str | None:
    patterns = [
        r"point\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+high",
        r"height\s+of\s+([0-9]+(?:\.[0-9]+)?)\s*m",
        r"height\s+([0-9]+(?:\.[0-9]+)?)\s*m\s+above",
        r"([0-9]+(?:\.[0-9]+)?)\s*m\s+above\s+(?:the\s+)?point\s+of\s+projection",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return f"{match.group(1)}m"
    return None


def _parse_float_from_value(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.search(r"[-+]?[0-9]+(?:\.[0-9]+)?", value)
    return float(match.group(0)) if match else None


def _infer_staircase_dimensions(text: str) -> dict[str, str]:
    compact = " ".join(text.split())
    patterns = [
        r"each (?:step|stair) is\s*([0-9]+(?:\.[0-9]+)?)\s*m(?:eter|etre|eters|etres)?\s*high\s*and\s*([0-9]+(?:\.[0-9]+)?)\s*m(?:eter|etre|eters|etres)?\s*wide",
        r"each (?:step|stair) is\s*y\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*m(?:eter|etre|eters|etres)?\s*high\s*and\s*x\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*m(?:eter|etre|eters|etres)?\s*wide",
        r"y\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*m(?:eter|etre|eters|etres)?\s*high\s*and\s*x\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*m(?:eter|etre|eters|etres)?\s*wide",
    ]
    for pattern in patterns:
        match = re.search(pattern, compact)
        if match:
            return {"height": f"{match.group(1)}m", "width": f"{match.group(2)}m"}
    return {}


def _append_if_missing(givens: list[str], key: str, value: str | None) -> None:
    if value is None:
        return
    prefix = f"{key}="
    replacement = f"{key}={value}"
    for index, given in enumerate(givens):
        if given.startswith(prefix):
            givens[index] = replacement
            return
    givens.append(replacement)


def _number_word_value(value: str) -> float:
    numbers = {
        "one": 1.0,
        "two": 2.0,
        "three": 3.0,
        "four": 4.0,
        "five": 5.0,
        "six": 6.0,
        "seven": 7.0,
        "eight": 8.0,
        "nine": 9.0,
        "ten": 10.0,
    }
    return numbers[value]


def _dedupe_givens(givens: list[str]) -> list[str]:
    deduped: dict[str, str] = {}
    passthrough: list[str] = []
    for given in givens:
        if "=" not in given:
            passthrough.append(given)
            continue
        key = given.split("=", 1)[0].strip()
        deduped[key] = given
    return list(deduped.values()) + passthrough


def _normalize_radical(value: str) -> str:
    cleaned = value.replace("root", "sqrt").replace("√", "sqrt").replace(" ", "")
    cleaned = re.sub(r"sqrt(\d+)", r"sqrt(\1)", cleaned)
    return cleaned


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
