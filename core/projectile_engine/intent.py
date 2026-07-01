from __future__ import annotations

import re


CASE_OUTPUT_QUANTITIES: dict[str, set[str]] = {
    "parametric_initial_speed": {"initial_speed"},
    "velocity_change_interval": {"magnitude_change_in_velocity", "change_in_velocity"},
    "parametric_curve_classification": {"path_shape"},
    "velocity_angle_event_speed": {"speed_when_velocity_angle_matches", "speed"},
    "horizontal_throw_velocity_angle_time": {"time_when_velocity_angle_matches", "time"},
    "velocity_perpendicular_to_initial_event": {"x_coordinate_at_event", "x_coordinate"},
    "same_range_doubled_angle_time_ratio": {"time_of_flight_ratio"},
    "two_projectile_interception_time_ratio": {"time_ratio_squared", "squared_time_ratio", "t1_t2_squared"},
    "two_projectile_same_speed_comparison": {
        "projectile_comparison",
        "time_height_range_comparison",
        "comparison",
        "multiple_quantities",
    },
    "target_angle_from_short_overshoot": {"launch_angle_to_hit_target", "angle_of_elevation"},
    "fielder_catch_before_ground": {"fielder_speed"},
    "average_velocity_to_peak": {"average_velocity_magnitude_to_peak", "average_velocity"},
    "projectile_with_horizontal_acceleration": {"modified_range_and_height"},
    "level_ground_range": {"horizontal_range", "range", "level_ground_range", "maximum_level_ground_range", "maximum_range"},
    "level_ground_time_of_flight": {"time_of_flight", "flight_time", "time_to_land"},
    "level_ground_multi_quantity": {
        "level_ground_multi_quantity",
        "multi_quantity",
        "multiple_quantities",
        "range_and_time",
        "range_and_time_of_flight",
        "horizontal_range_and_time",
        "range_time",
        "range_time_height",
    },
    "level_ground_range_and_time": {"range_and_time", "range_and_time_of_flight", "horizontal_range_and_time", "range_time"},
    "level_ground_time_of_flight_derivation": {"time_of_flight_derivation", "derive_time_of_flight", "derivation_time_of_flight"},
    "level_ground_max_height": {"maximum_height", "max_height", "greatest_height"},
    "projectile_split_at_apex_fragment_time": {"fragment_fall_time", "time_after_splitting", "t_after_splitting"},
    "bounce_restitution_height": {
        "post_bounce_height",
        "rebound_height",
        "height_after_bounce",
        "coefficient_of_restitution",
    },
    "relative_projectile_apex_collision": {
        "vertical_throw_speed_for_apex_collision",
        "collision_condition",
        "speed_of_vertical_projection",
    },
    "piecewise_acceleration_at_apex_range": {
        "range_under_changed_acceleration",
        "new_range_after_apex",
        "range",
    },
    "level_ground_time_to_peak": {"time_to_peak", "time_to_maximum_height", "time_to_highest_point"},
    "level_ground_position_at_time": {"position_at_time", "coordinates_at_time", "position", "coordinates"},
    "level_ground_velocity_at_time": {"velocity_at_time", "speed_at_time", "velocity_after_time", "speed_after_time"},
    "vertical_component_height_times": {"times_at_height", "vertical_component_height_times"},
    "trajectory_equation_from_launch": {"trajectory_equation", "equation_of_trajectory"},
    "monkey_hunter_condition": {"monkey_hunter_condition", "falling_target_condition"},
    "same_height_times_initial_speed": {"initial_speed_from_same_height_times", "speed_of_projection", "initial_speed"},
    "trajectory_equation_max_height": {"maximum_height_from_trajectory", "maximum_height", "greatest_height"},
    "projectile_height_scaling": {"scaled_maximum_height", "new_maximum_height", "maximum_height"},
    "range_angle_scaling": {"scaled_range", "new_range", "range"},
    "range_equals_max_height_angle": {"launch_angle", "angle_of_projection", "angle_for_range_equal_height"},
    "level_ground_launch_angle_from_range": {"launch_angle", "launch_angles", "angle_of_projection", "angle_from_range"},
    "height_launch_time_of_flight": {"time_of_flight_from_height", "height_launch_time_of_flight", "time_of_flight"},
    "height_launch_range": {"height_launch_range", "range_from_height", "horizontal_range_from_height", "horizontal_range"},
    "height_launch_multi_quantity": {
        "height_launch_multi_quantity",
        "height_launch_multiple_quantities",
        "time_range_from_height",
        "time_range_impact_speed_from_height",
        "range_and_time_from_height",
    },
    "height_launch_horizontal_scenario": {"scenario_summary", "horizontal_launch_summary"},
    "max_range_from_height_fixed_speed": {"maximum_ground_range", "maximum_range"},
    "wall_height_at_distance": {"height_at_wall", "projectile_height_at_wall"},
    "wall_clearance_condition": {"clears_wall_condition", "wall_clearance", "clear_wall", "does_it_clear_wall"},
    "air_drag_conceptual_timing": {"correct_qualitative_statement", "effects_of_air_drag"},
    "inclined_plane_impact_time": {"time_to_hit_incline", "impact_time"},
    "inclined_plane_same_point_time_ratio": {"time_of_flight_ratio"},
    "inclined_plane_right_angle_impact_condition": {"condition_for_right_angle_impact"},
    "target_reachability_fixed_speed": {"impossible_target_condition"},
    "staircase_collision": {"step_number_hit", "step_number"},
    "minimum_speed_to_hit_target": {"minimum_launch_speed"},
    "target_launch_angle_fixed_speed": {"launch_angle_to_hit_target", "launch_angles_to_hit_target", "target_launch_angle"},
    "two_projectile_collision_time": {"collision_time", "interception_time", "time_to_collide"},
    "inclined_plane_max_normal_distance_velocity_component": {
        "normal_velocity_component_at_max_distance",
        "y_component_of_velocity",
    },
    "perpendicular_launch_range_on_incline": {"range_on_incline"},
    "max_range_on_incline": {"maximum_range_on_incline"},
    "horizontal_launch_onto_incline_distance": {"distance_along_incline_to_impact"},
    "two_inclines_perpendicular_launch_impact": {
        "impact_speed",
        "velocity_at_impact",
        "impact_velocity",
        "speed_at_impact",
        "velocity_at_q",
        "velocity_strike_ob",
        "velocity_with_which_particle_strikes_ob",
        "speed_strike_ob",
    },
    "projectile_collides_with_sliding_particle_on_incline": {"projection_speed", "speed_of_projection_p"},
    "motion_on_smooth_incline_perpendicular_to_slope": {
        "speed_after_time",
        "speed_after_1_sec",
        "speed_after_1_second",
        "speed_after_one_second",
    },
    "three_dimensional_projectile_line_intersection": {"impact_coordinates_on_horizontal_line"},
}

REQUESTED_QUANTITY_TO_CASE: dict[str, str] = {
    quantity: engine_case
    for engine_case, quantities in CASE_OUTPUT_QUANTITIES.items()
    for quantity in quantities
}


def normalize_quantity(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip().lower()
    text = text.replace("θ", "theta").replace("α", "alpha").replace("β", "beta")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def requested_quantity_case(requested_quantity: str | None, question_text: str = "") -> str | None:
    quantity = normalize_quantity(requested_quantity)
    text = question_text.lower()
    if _is_quantitative_non_ideal_projectile(text) or _is_moving_wedge_projectile(text):
        return None
    if any(marker in text for marker in ("derive", "derivation", "prove", "show that")) and any(
        marker in text for marker in ("time of flight", "flight time")
    ):
        return "level_ground_time_of_flight_derivation"
    priority_text_case = _priority_text_case(text)
    if priority_text_case:
        return priority_text_case
    if ("coordinates are" in text or ("x" in text and "y" in text and "=" in text)) and any(
        marker in text for marker in ("initial horizontal velocity", "initial vertical velocity", "initial speed", "angle of projection")
    ):
        return "level_ground_position_at_time"
    if "passes through" in text and "high after" in text and "horizontal velocity" in text:
        return "level_ground_position_at_time"
    if any(marker in text for marker in ("wall", "barrier", "obstacle")) and any(marker in text for marker in ("clear", "clears", "cross", "crosses")):
        return "wall_clearance_condition"
    elevated_launch = any(marker in text for marker in ("tower", "building", "balcony", "platform", "table", "cart", "cliff", "from a height"))
    if elevated_launch and _requested_level_ground_output_count(text) >= 2:
        return "height_launch_horizontal_scenario" if _is_horizontal_launch(text) else "height_launch_multi_quantity"
    if _requested_level_ground_output_count(text) >= 2:
        return "level_ground_multi_quantity"
    text_target_case = _explicit_single_target_case(text)
    if text_target_case:
        return text_target_case
    if quantity == "maximum_range" and not any(marker in text for marker in ("tower", "height", "cliff", "incline", "inclined")):
        return "level_ground_range"
    if quantity == "time_of_flight" and elevated_launch:
        return "height_launch_time_of_flight"
    if quantity == "time_of_flight" and not elevated_launch:
        return "level_ground_time_of_flight"
    if quantity in {"range", "horizontal_range"} and elevated_launch:
        if _is_horizontal_launch(text):
            return "height_launch_horizontal_scenario"
        return "height_launch_range"
    if quantity in {"range", "horizontal_range"}:
        if _is_piecewise_acceleration_range_context(text):
            return "piecewise_acceleration_at_apex_range"
        if _is_range_angle_scaling_context(text):
            return "range_angle_scaling"
        return "level_ground_range"
    if quantity in {"maximum_height", "max_height", "greatest_height"}:
        if _is_trajectory_equation_context(text):
            return "trajectory_equation_max_height"
        if _is_height_scaling_context(text):
            return "projectile_height_scaling"
        return "level_ground_max_height"
    if quantity in {"launch_angle", "launch_angles", "angle_of_projection"} and "target" in text:
        return "target_launch_angle_fixed_speed"
    if quantity == "launch_angle_to_hit_target" and any(marker in text for marker in ("overshoot", "short")):
        return "target_angle_from_short_overshoot"
    if quantity in {"launch_angle", "launch_angles", "angle_of_projection"} and "range" in text:
        if "maximum height" in text and any(marker in text for marker in ("same", "equal", "equals", "times")):
            return "range_equals_max_height_angle"
        return "level_ground_launch_angle_from_range"
    if quantity in REQUESTED_QUANTITY_TO_CASE:
        return REQUESTED_QUANTITY_TO_CASE[quantity]
    return _infer_case_from_question_target(question_text)


def is_case_quantity_compatible(engine_case: str | None, requested_quantity: str | None) -> bool:
    if not engine_case or not requested_quantity:
        return True
    quantity = normalize_quantity(requested_quantity)
    if not quantity:
        return True
    accepted = CASE_OUTPUT_QUANTITIES.get(engine_case)
    if accepted is None:
        return True
    return quantity in accepted


def choose_engine_case_for_requested_quantity(
    *,
    question_text: str,
    engine_case: str | None,
    requested_quantity: str | None,
) -> tuple[str | None, str]:
    requested_case = requested_quantity_case(requested_quantity, question_text)
    if requested_case and requested_case != engine_case:
        return requested_case, (
            f"requested_quantity={normalize_quantity(requested_quantity) or 'inferred_from_text'} "
            f"requires engine_case={requested_case}; extractor suggested {engine_case or 'none'}"
        )
    if requested_case:
        if engine_case and not is_case_quantity_compatible(engine_case, requested_quantity):
            return engine_case, (
                f"question_text target keeps engine_case={engine_case}; ignoring incompatible "
                f"requested_quantity={normalize_quantity(requested_quantity)}"
            )
        return engine_case, ""
    if engine_case and not is_case_quantity_compatible(engine_case, requested_quantity):
        return None, (
            f"engine_case={engine_case} does not solve requested_quantity="
            f"{normalize_quantity(requested_quantity)}"
        )
    return engine_case, ""


def _infer_case_from_question_target(question_text: str) -> str | None:
    text = question_text.lower()
    if _is_quantitative_non_ideal_projectile(text) or _is_moving_wedge_projectile(text):
        return None
    if any(marker in text for marker in ("derive", "derivation", "prove", "show that")) and any(
        marker in text for marker in ("time of flight", "flight time")
    ):
        return "level_ground_time_of_flight_derivation"
    if _is_height_launch_context(text) and _requested_level_ground_output_count(text) >= 2:
        return "height_launch_horizontal_scenario" if _is_horizontal_launch(text) else "height_launch_multi_quantity"
    if _requested_level_ground_output_count(text) >= 2:
        return "level_ground_multi_quantity"
    if "which step" in text or "to which step" in text or "step will" in text:
        return "staircase_collision"
    if "hit by a stone" in text and ("t1/t2" in text or "t_1/t_2" in text or "t₁/t₂" in text):
        return "two_projectile_interception_time_ratio"
    if "air drag" in text:
        return "air_drag_conceptual_timing"
    if ("splits into" in text or "split into" in text or "splits at" in text or "split at" in text) and (
        "highest point" in text or "apex" in text
    ):
        return "projectile_split_at_apex_fragment_time"
    if any(marker in text for marker in ("changed gravity", "gravity changes", "effective gravity", "enters a region")) and any(
        marker in text for marker in ("highest point", "apex")
    ):
        return "piecewise_acceleration_at_apex_range"
    if "hits the incline at right angle" in text or "hit the incline at right angle" in text:
        return "inclined_plane_right_angle_impact_condition"
    if "velocity at q" in text or "speed at q" in text:
        return "two_inclines_perpendicular_launch_impact"
    if "range of the ball on the inclined plane" in text or "range on the inclined plane" in text:
        return "perpendicular_launch_range_on_incline"
    if ("position after" in text or "coordinates after" in text or "position at" in text) and "incline" not in text:
        return "level_ground_position_at_time"
    if any(marker in text for marker in ("time to reach the maximum height", "time to reach maximum height", "time to highest point", "time to reach highest point")):
        return "level_ground_time_to_peak"
    if "lands on a platform" in text and ("angle" in text or "angles" in text):
        return "target_launch_angle_fixed_speed"
    if ("launch angles" in text or "what launch angles" in text or "what angle" in text) and "range" in text:
        return "level_ground_launch_angle_from_range"
    if _asks_height_launch_time(text):
        return "height_launch_time_of_flight"
    if _asks_height_launch_range(text):
        return "height_launch_range"
    if _is_horizontal_launch(text) and _is_height_launch_context(text):
        return "height_launch_horizontal_scenario"
    if any(marker in text for marker in ("wall", "barrier", "obstacle")) and any(marker in text for marker in ("clear", "clears", "cross", "crosses")):
        return "wall_clearance_condition"
    if any(marker in text for marker in ("wall", "barrier", "obstacle")) and any(
        marker in text for marker in ("height", "at a wall", "at the wall", "at a barrier", "at the barrier", "at an obstacle")
    ):
        return "wall_height_at_distance"
    if ("launch angle" in text or "launch angles" in text) and "target" in text:
        return "target_launch_angle_fixed_speed"
    if "projectile a" in text and "projectile b" in text and ("collide" in text or "collision" in text):
        return "two_projectile_collision_time"
    if _is_level_ground_range_request(text):
        return "level_ground_range"
    if "maximum distance from the incline" in text and "component" in text:
        return "inclined_plane_max_normal_distance_velocity_component"
    if "speed after" in text and "line of greatest slope" in text:
        return "motion_on_smooth_incline_perpendicular_to_slope"
    if "speed of projection" in text and "collide" in text and "inclined plane" in text:
        return "projectile_collides_with_sliding_particle_on_incline"
    return None


def _explicit_single_target_case(text: str) -> str | None:
    if _is_piecewise_acceleration_range_context(text):
        return "piecewise_acceleration_at_apex_range"
    if _is_range_angle_scaling_context(text):
        return "range_angle_scaling"
    if _text_requests_maximum_range(text):
        if "incline" in text or "inclined" in text:
            return "max_range_on_incline"
        if _is_height_launch_context(text):
            return "max_range_from_height_fixed_speed"
        return "level_ground_range"
    if _text_requests_maximum_height(text):
        if _is_trajectory_equation_context(text):
            return "trajectory_equation_max_height"
        if _is_height_scaling_context(text):
            return "projectile_height_scaling"
        return "level_ground_max_height"
    return None


def _priority_text_case(text: str) -> str | None:
    if "hit by a stone" in text and ("t1/t2" in text or "t_1/t_2" in text or "t₁/t₂" in text):
        return "two_projectile_interception_time_ratio"
    if _is_two_projectile_same_speed_comparison(text):
        return "two_projectile_same_speed_comparison"
    if "air drag" in text:
        return "air_drag_conceptual_timing"
    if ("splits into" in text or "split into" in text or "splits at" in text or "split at" in text) and (
        "highest point" in text or "apex" in text
    ):
        return "projectile_split_at_apex_fragment_time"
    if "collides at" in text and "highest point" in text and "thrown vertically" in text:
        return "relative_projectile_apex_collision"
    if _is_piecewise_acceleration_range_context(text):
        return "piecewise_acceleration_at_apex_range"
    if _asks_time_to_peak(text):
        return "level_ground_time_to_peak"
    if _asks_height_launch_time(text):
        return "height_launch_time_of_flight"
    if _asks_height_launch_range(text):
        return "height_launch_range"
    if "range" in text and any(marker in text for marker in ("maximum height", "greatest height")) and any(
        marker in text for marker in ("same", "equal", "equals", "times")
    ):
        return "range_equals_max_height_angle"
    if ("launch angles" in text or "what launch angles" in text or "what angle" in text) and "range" in text:
        return "level_ground_launch_angle_from_range"
    if "maximum distance from the incline" in text and "component" in text:
        return "inclined_plane_max_normal_distance_velocity_component"
    return None


def _text_requests_maximum_range(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "maximum range",
            "max range",
            "maximum horizontal range",
            "greatest range",
            "maximum distance travelled",
            "maximum distance traveled",
        )
    )


def _text_requests_maximum_height(text: str) -> bool:
    if "maximum distance from the incline" in text:
        return False
    if _asks_time_to_peak(text):
        return False
    if any(marker in text for marker in ("air drag", "split", "splits", "collides at")):
        return False
    if "range" in text and any(marker in text for marker in ("same", "equal", "equals", "times")):
        return False
    return any(
        marker in text
        for marker in (
            "maximum height",
            "max height",
            "greatest height",
            "maximum altitude",
        )
    )


def _is_trajectory_equation_context(text: str) -> bool:
    return ("trajectory" in text or "path" in text) and bool(re.search(r"\by\s*=", text))


def _is_height_scaling_context(text: str) -> bool:
    if any(marker in text for marker in ("new maximum height", "new max height", "scaled maximum height", "scaled max height")):
        return True
    return _text_requests_maximum_height(text) and any(
        marker in text
        for marker in (
            "halved",
            "doubled",
            "tripled",
            "same angle",
            "initial velocity is",
            "initial speed is",
            "speed is changed",
            "velocity is changed",
        )
    )


def _asks_time_to_peak(text: str) -> bool:
    return any(marker in text for marker in ("maximum height", "highest point", "top", "peak")) and any(
        marker in text for marker in ("time to", "time taken", "how long", "when")
    )


def _asks_height_launch_time(text: str) -> bool:
    return _is_height_launch_context(text) and any(
        marker in text
        for marker in (
            "time of flight",
            "flight time",
            "hits the ground",
            "reach the ground",
            "to reach the ground",
            "how long",
            "remains in air",
            "take to fall",
            "time to fall",
        )
    )


def _asks_height_launch_range(text: str) -> bool:
    if not _is_height_launch_context(text):
        return False
    if "how far" in text or "where will it land" in text or "where does it land" in text:
        return True
    if "range from" in text or "distance covered" in text or "distance travelled" in text or "distance traveled" in text:
        return True
    return bool(
        re.search(
            r"\bfind (?:the |its )?(?:horizontal )?(?:range|distance|displacement)\b",
            text,
        )
    )


def _is_range_angle_scaling_context(text: str) -> bool:
    if not any(marker in text for marker in ("same velocity", "same speed", "same initial velocity", "same initial speed")):
        return False
    return any(marker in text for marker in ("find the range when", "range when", "new range", "range for"))


def _is_two_projectile_same_speed_comparison(text: str) -> bool:
    if not any(marker in text for marker in ("two projectiles", "two particles", "two bodies")):
        return False
    if not any(marker in text for marker in ("same speed", "same velocity", "same initial speed", "same initial velocity")):
        return False
    if len(re.findall(r"[0-9]+(?:\.[0-9]+)?\s*(?:deg|degree|degrees|°)", text)) < 2:
        return False
    return "compare" in text and all(marker in text for marker in ("time", "height", "range"))


def _is_piecewise_acceleration_range_context(text: str) -> bool:
    return any(marker in text for marker in ("changed gravity", "gravity changes", "effective gravity", "enters a region")) and any(
        marker in text for marker in ("highest point", "apex")
    )


def _requested_level_ground_output_count(text: str) -> int:
    if _is_special_non_composite_context(text):
        return 0
    outputs: list[str] = []
    if any(marker in text for marker in ("initial speed", "speed needed", "speed of projection")):
        outputs.append("initial_speed")
    if any(marker in text for marker in ("angle of projection", "launch angle", "find theta", "find the angle", "angle theta")):
        outputs.append("launch_angle")
    if any(marker in text for marker in ("range", "horizontal distance", "ground distance", "distance covered on ground", "distance on ground", "distance from", "how far")):
        outputs.append("range")
    if any(marker in text for marker in ("time of flight", "flight time", "total time", "time in air", "airtime", "stays in the air", "stays in air")):
        outputs.append("time_of_flight")
    peak_time = any(marker in text for marker in ("maximum height", "highest point", "top", "peak")) and any(
        marker in text for marker in ("time to", "time taken", "how long", "when")
    )
    if peak_time:
        outputs.append("time_to_peak")
    if any(marker in text for marker in ("maximum height", "max height", "greatest height", "maximum altitude", "altitude gained")):
        if not peak_time or any(marker in text for marker in ("and maximum height", "and max height", "height and")):
            outputs.append("maximum_height")
    if any(marker in text for marker in ("components", "component", "u_x", "ux", "uₓ", "u_y", "uy", "uᵧ", "horizontal velocity", "vertical velocity")):
        outputs.append("components")
    return len(set(outputs))


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
    if any(marker in text for marker in ("tower", "height", "cliff", "incline", "inclined")):
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
        )
    )


def _is_horizontal_launch(text: str) -> bool:
    if "no horizontal velocity" in text or "without horizontal velocity" in text:
        return False
    if "initial horizontal velocity" in text and "find" in text:
        return False
    return any(
        marker in text
        for marker in (
            "thrown horizontally",
            "projected horizontally",
            "projected horizontal",
            "launched horizontally",
            "fired horizontally",
            "horizontally from",
            "horizontal speed",
            "horizontal velocity",
            "rolls off",
            "leaves horizontally",
        )
    )


def _is_non_ideal_projectile(text: str) -> bool:
    return any(marker in text for marker in ("air drag", "air resistance", "quadratic drag", "drag force", "magnus"))


def _is_quantitative_non_ideal_projectile(text: str) -> bool:
    if not _is_non_ideal_projectile(text):
        return False
    quantitative_markers = ("find", "calculate", "exact", "range", "deflection", "distance", "height")
    conceptual_markers = ("choose", "correct alternative", "considered")
    return any(marker in text for marker in quantitative_markers) and not any(marker in text for marker in conceptual_markers)


def _is_moving_wedge_projectile(text: str) -> bool:
    return any(marker in text for marker in ("moving wedge", "wedge moving", "moving incline"))
