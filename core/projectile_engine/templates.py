from __future__ import annotations

import re

from .intent import CASE_OUTPUT_QUANTITIES, normalize_quantity
from .models import ProblemTemplate, TemplateMatch


PROJECTILE_TEMPLATES: tuple[ProblemTemplate, ...] = (
    ProblemTemplate(
        id="parametric_kinematics",
        title="Parametric motion from x(t), y(t), or velocity functions",
        family="coordinate_kinematics",
        engine_cases={"parametric_initial_speed", "parametric_curve_classification"},
        accepted_quantities={"initial_speed", "path_shape"},
        required_known_keys={"x(t)|dx/dt", "y(t)|dy/dt"},
        solve_strategy="Read or integrate components, then combine or eliminate time.",
        animation_requirements=["coordinate axes", "component arrows", "path curve"],
    ),
    ProblemTemplate(
        id="constant_acceleration_velocity_event",
        title="Velocity change or velocity direction event",
        family="basic_projectile",
        engine_cases={
            "velocity_change_interval",
            "velocity_angle_event_speed",
            "horizontal_throw_velocity_angle_time",
            "velocity_perpendicular_to_initial_event",
        },
        accepted_quantities={
            "magnitude_change_in_velocity",
            "change_in_velocity",
            "speed_when_velocity_angle_matches",
            "speed",
            "time_when_velocity_angle_matches",
            "time",
            "x_coordinate_at_event",
            "x_coordinate",
        },
        optional_known_keys={"v0", "angle", "launch_angle", "velocity_angle", "dt", "vx", "g"},
        solve_strategy="Use vx constant and vy changing linearly under gravity; impose the velocity-angle condition.",
        animation_requirements=["launch velocity", "vx component", "vy component", "event highlight"],
    ),
    ProblemTemplate(
        id="range_peak_and_average_quantities",
        title="Range, height, time ratio, and average velocity",
        family="basic_projectile",
        engine_cases={
            "same_range_doubled_angle_time_ratio",
            "two_projectile_interception_time_ratio",
            "two_projectile_same_speed_comparison",
            "fielder_catch_before_ground",
            "average_velocity_to_peak",
            "projectile_with_horizontal_acceleration",
            "level_ground_range",
            "level_ground_time_of_flight",
            "level_ground_multi_quantity",
            "level_ground_range_and_time",
            "level_ground_time_of_flight_derivation",
            "level_ground_max_height",
            "level_ground_time_to_peak",
            "level_ground_position_at_time",
            "level_ground_velocity_at_time",
            "vertical_component_height_times",
            "trajectory_equation_from_launch",
            "monkey_hunter_condition",
            "same_height_times_initial_speed",
            "trajectory_equation_max_height",
            "projectile_height_scaling",
            "range_angle_scaling",
            "range_equals_max_height_angle",
            "level_ground_launch_angle_from_range",
            "height_launch_time_of_flight",
            "height_launch_range",
            "height_launch_multi_quantity",
            "height_launch_horizontal_scenario",
            "max_range_from_height_fixed_speed",
        },
        accepted_quantities={
            "time_of_flight_ratio",
            "time_ratio_squared",
            "squared_time_ratio",
            "t1_t2_squared",
            "projectile_comparison",
            "time_height_range_comparison",
            "comparison",
            "fielder_speed",
            "average_velocity_magnitude_to_peak",
            "average_velocity",
            "modified_range_and_height",
            "horizontal_range",
            "range",
            "level_ground_range",
            "maximum_level_ground_range",
            "maximum_range",
            "time_of_flight",
            "range_and_time",
            "range_and_time_of_flight",
            "horizontal_range_and_time",
            "range_time",
            "range_time_height",
            "multi_quantity",
            "level_ground_multi_quantity",
            "multiple_quantities",
            "time_of_flight_derivation",
            "derive_time_of_flight",
            "derivation_time_of_flight",
            "flight_time",
            "time_to_land",
            "maximum_height",
            "max_height",
            "greatest_height",
            "time_to_peak",
            "time_to_maximum_height",
            "time_to_highest_point",
            "position_at_time",
            "coordinates_at_time",
            "position",
            "coordinates",
            "velocity_at_time",
            "speed_at_time",
            "velocity_after_time",
            "speed_after_time",
            "times_at_height",
            "vertical_component_height_times",
            "trajectory_equation",
            "equation_of_trajectory",
            "monkey_hunter_condition",
            "falling_target_condition",
            "initial_speed_from_same_height_times",
            "speed_of_projection",
            "maximum_height_from_trajectory",
            "scaled_maximum_height",
            "new_maximum_height",
            "scaled_range",
            "new_range",
            "angle_for_range_equal_height",
            "launch_angle",
            "launch_angles",
            "angle_of_projection",
            "angle_from_range",
            "time_of_flight_from_height",
            "height_launch_time_of_flight",
            "height_launch_range",
            "height_launch_multi_quantity",
            "height_launch_multiple_quantities",
            "time_range_from_height",
            "time_range_impact_speed_from_height",
            "range_and_time_from_height",
            "range_from_height",
            "horizontal_range_from_height",
            "horizontal_range",
            "scenario_summary",
            "horizontal_launch_summary",
            "maximum_ground_range",
        },
        optional_known_keys={"v0", "angle", "height", "time", "range", "fielder_distance", "trajectory_a", "trajectory_b", "t1", "t2", "speed_scale", "angle1", "angle2", "g"},
        solve_strategy="Apply standard time-of-flight, peak, range, or external-horizontal-acceleration relations.",
        animation_requirements=["trajectory", "range marker", "peak marker", "time marker", "velocity components"],
    ),
    ProblemTemplate(
        id="target_reachability",
        title="Target point reachability and minimum launch speed",
        family="target_projectile",
        engine_cases={
            "target_angle_from_short_overshoot",
            "target_reachability_fixed_speed",
            "minimum_speed_to_hit_target",
            "target_launch_angle_fixed_speed",
        },
        accepted_quantities={
            "launch_angle_to_hit_target",
            "angle_of_elevation",
            "launch_angles_to_hit_target",
            "target_launch_angle",
            "impossible_target_condition",
            "minimum_launch_speed",
        },
        optional_known_keys={"target", "v0", "g"},
        required_diagram_entities={"target_point"},
        diagram_kind="target_point",
        solve_strategy="Use trajectory equation through a target point, then optimize or solve for launch angle.",
        animation_requirements=["origin", "target point", "family of possible trajectories"],
    ),
    ProblemTemplate(
        id="wall_clearance",
        title="Projectile height and clearance at a wall",
        family="obstacle_projectile",
        engine_cases={"wall_height_at_distance", "wall_clearance_condition"},
        accepted_quantities={
            "height_at_wall",
            "projectile_height_at_wall",
            "clears_wall_condition",
            "wall_clearance",
            "clear_wall",
            "does_it_clear_wall",
        },
        optional_known_keys={"v0", "angle", "wall_distance", "wall_height", "g"},
        required_diagram_entities={"wall"},
        diagram_kind="wall",
        solve_strategy="Evaluate the trajectory at the wall's x-coordinate, then compare with wall height if needed.",
        animation_requirements=["trajectory", "wall", "height marker", "clearance marker"],
    ),
    ProblemTemplate(
        id="inclined_plane_impact",
        title="Projectile striking an inclined plane",
        family="inclined_projectile",
        engine_cases={"inclined_plane_impact_time", "inclined_plane_right_angle_impact_condition"},
        accepted_quantities={"time_to_hit_incline", "impact_time", "condition_for_right_angle_impact"},
        optional_known_keys={"v0", "launch_angle_horizontal", "incline", "g"},
        required_diagram_entities={"inclined_surface", "impact_point"},
        diagram_kind="single_incline",
        solve_strategy="Resolve trajectory against the line y = x tan(alpha), then apply impact condition if needed.",
        animation_requirements=["incline orientation", "trajectory", "impact point", "impact velocity"],
    ),
    ProblemTemplate(
        id="inclined_plane_range",
        title="Range measured on an inclined plane",
        family="inclined_projectile",
        engine_cases={
            "inclined_plane_same_point_time_ratio",
            "perpendicular_launch_range_on_incline",
            "max_range_on_incline",
            "horizontal_launch_onto_incline_distance",
            "inclined_plane_max_normal_distance_velocity_component",
        },
        accepted_quantities={
            "time_of_flight_ratio",
            "range_on_incline",
            "maximum_range_on_incline",
            "distance_along_incline_to_impact",
            "normal_velocity_component_at_max_distance",
            "y_component_of_velocity",
        },
        optional_known_keys={"v0", "velocity", "speed", "incline", "angle", "g"},
        required_diagram_entities={"inclined_surface"},
        diagram_kind="single_incline",
        solve_strategy="Use axes parallel and normal to the incline; derive return/range/extremum condition.",
        animation_requirements=["incline frame", "normal axis", "parallel axis", "range along plane"],
    ),
    ProblemTemplate(
        id="staircase_collision",
        title="Projectile collision with staircase geometry",
        family="piecewise_geometry",
        engine_cases={"staircase_collision"},
        accepted_quantities={"step_number_hit", "step_number"},
        optional_known_keys={"vx", "step_height", "step_width", "g"},
        required_diagram_entities={"staircase", "vertical_faces"},
        diagram_kind="staircase",
        solve_strategy="Evaluate projectile drop at successive vertical faces and choose the first face reached.",
        animation_requirements=["stair geometry", "candidate faces", "first collision highlight"],
    ),
    ProblemTemplate(
        id="bounce_restitution",
        title="Projectile bounce with restitution or retained energy",
        family="bounce_projectile",
        engine_cases={"bounce_restitution_height"},
        accepted_quantities={
            "post_bounce_height",
            "rebound_height",
            "height_after_bounce",
            "coefficient_of_restitution",
        },
        optional_known_keys={"height", "drop_height", "launch_height", "post_bounce_height", "e", "energy_retained_fraction", "g"},
        required_diagram_entities={"bounce_surface"},
        diagram_kind="bounce_surface",
        solve_strategy="Use vertical impact/rebound energy: post-bounce height scales as e^2 times pre-bounce drop height.",
        animation_requirements=["pre-bounce trajectory", "impact point", "rebound trajectory", "velocity before and after bounce"],
    ),
    ProblemTemplate(
        id="piecewise_acceleration_at_apex",
        title="Projectile range when acceleration changes at the apex",
        family="piecewise_acceleration_projectile",
        engine_cases={"piecewise_acceleration_at_apex_range"},
        accepted_quantities={"range_under_changed_acceleration", "new_range_after_apex", "range"},
        optional_known_keys={"range", "v0", "angle", "g1", "g2", "acceleration_ratio"},
        solve_strategy="Split the trajectory at the apex; keep the first half unchanged and scale descent time by sqrt(g1/g2).",
        animation_requirements=["pre-apex trajectory", "apex boundary", "post-apex trajectory with changed acceleration"],
    ),
    ProblemTemplate(
        id="relative_apex_collision",
        title="Projectile collides at apex with a vertically thrown particle",
        family="relative_motion_projectile",
        engine_cases={"relative_projectile_apex_collision"},
        accepted_quantities={
            "vertical_throw_speed_for_apex_collision",
            "collision_condition",
            "speed_of_vertical_projection",
        },
        optional_known_keys={"v0", "angle", "g"},
        solve_strategy="At the projectile apex, the vertical throw must share the same vertical launch component to arrive at the same height/time.",
        animation_requirements=["projectile path", "vertical throw path", "apex collision marker"],
    ),
    ProblemTemplate(
        id="two_incline_perpendicular_transfer",
        title="Projectile between two inclined planes with perpendicular launch/impact",
        family="multi_surface_projectile",
        engine_cases={"two_inclines_perpendicular_launch_impact"},
        accepted_quantities={
            "impact_speed",
            "velocity_at_impact",
            "impact_velocity",
            "speed_at_impact",
            "velocity_at_q",
            "velocity_strike_ob",
            "velocity_with_which_particle_strikes_ob",
            "speed_strike_ob",
        },
        optional_known_keys={"u", "v0", "plane_OA", "plane_OB", "g"},
        required_diagram_entities={"left_incline", "right_incline", "launch_point", "impact_point", "perpendicular_markers"},
        diagram_kind="two_inclines",
        solve_strategy="Use diagram orientation to set launch and impact velocity directions, then conserve horizontal component.",
        animation_requirements=["two incline orientations", "perpendicular launch", "perpendicular impact", "constant vx"],
    ),
    ProblemTemplate(
        id="relative_motion_on_incline",
        title="Projectile and another particle constrained by an incline",
        family="relative_motion_projectile",
        engine_cases={"projectile_collides_with_sliding_particle_on_incline"},
        accepted_quantities={"projection_speed", "speed_of_projection_p"},
        optional_known_keys={"collision_time", "t", "g"},
        required_diagram_entities={"inclined_surface", "particle_p", "particle_q"},
        diagram_kind="incline_relative_motion",
        solve_strategy="Write relative motion along the relevant inclined direction and impose collision at the same point/time.",
        animation_requirements=["both particles", "relative displacement", "collision point"],
    ),
    ProblemTemplate(
        id="two_projectile_collision",
        title="Two projectile collision with same gravity",
        family="relative_motion_projectile",
        engine_cases={"two_projectile_collision_time"},
        accepted_quantities={"collision_time", "interception_time", "time_to_collide"},
        optional_known_keys={"p1_x0", "p1_y0", "p1_vx", "p1_vy", "p2_x0", "p2_y0", "p2_vx", "p2_vy"},
        solve_strategy="Because both bodies share gravity, solve collision using relative linear motion.",
        animation_requirements=["two particles", "relative motion", "collision point"],
    ),
    ProblemTemplate(
        id="projectile_split_at_apex",
        title="Projectile splits into equal fragments at the apex",
        family="momentum_projectile",
        engine_cases={"projectile_split_at_apex_fragment_time"},
        accepted_quantities={"fragment_fall_time", "time_after_splitting", "t_after_splitting"},
        optional_known_keys={"v0", "angle", "g", "frag1_fall_time"},
        solve_strategy="Use apex kinematics to get split height, then conserve momentum between equal fragments at the split.",
        animation_requirements=["pre-split trajectory", "apex split", "vertical fragment", "second fragment", "momentum relation"],
    ),
    ProblemTemplate(
        id="smooth_incline_vector_composition",
        title="Motion on smooth incline with perpendicular initial velocity",
        family="inclined_dynamics_projectile",
        engine_cases={"motion_on_smooth_incline_perpendicular_to_slope"},
        accepted_quantities={
            "speed_after_time",
            "speed_after_1_sec",
            "speed_after_1_second",
            "speed_after_one_second",
        },
        optional_known_keys={"initial_speed", "v0", "time", "t", "incline", "g"},
        required_diagram_entities={"inclined_surface", "line_of_greatest_slope", "perpendicular_velocity"},
        diagram_kind="smooth_incline_3d",
        solve_strategy="Resolve velocity into perpendicular-to-slope and down-slope components, then combine vectorially.",
        animation_requirements=["inclined plane", "line of greatest slope", "perpendicular component", "down-slope component"],
    ),
    ProblemTemplate(
        id="air_drag_conceptual",
        title="Qualitative projectile with air drag",
        family="non_ideal_projectile",
        engine_cases={"air_drag_conceptual_timing"},
        accepted_quantities={"correct_qualitative_statement", "effects_of_air_drag"},
        solve_strategy="Reason qualitatively from reduced horizontal speed and drag-opposed motion.",
        animation_requirements=["ideal path", "drag path", "speed reduction"],
    ),
    ProblemTemplate(
        id="three_dimensional_projectile",
        title="Projectile constrained by a 3D line or plane",
        family="3d_projectile",
        engine_cases={"three_dimensional_projectile_line_intersection"},
        accepted_quantities={"impact_coordinates_on_horizontal_line"},
        optional_known_keys={"P", "v0", "launch_angle", "line_angle", "g"},
        required_diagram_entities={"3d_axes", "line_constraint"},
        diagram_kind="3d_line",
        solve_strategy="Solve vertical flight time, then project horizontal range along the line direction.",
        animation_requirements=["3d axes", "line constraint", "projected range", "impact point"],
    ),
)

TEMPLATES_BY_ID = {template.id: template for template in PROJECTILE_TEMPLATES}
TEMPLATE_BY_ENGINE_CASE = {
    engine_case: template
    for template in PROJECTILE_TEMPLATES
    for engine_case in template.engine_cases
}


def classify_template(
    *,
    question_text: str,
    engine_case: str | None,
    requested_quantity: str | None,
    givens: list[str],
) -> TemplateMatch | None:
    if engine_case and engine_case in TEMPLATE_BY_ENGINE_CASE:
        template = TEMPLATE_BY_ENGINE_CASE[engine_case]
        return TemplateMatch(
            template=template,
            confidence=0.98,
            reason=f"matched by engine_case={engine_case}",
            warnings=_template_warnings(template, givens),
        )

    quantity = normalize_quantity(requested_quantity)
    if quantity:
        candidates = [template for template in PROJECTILE_TEMPLATES if quantity in template.accepted_quantities]
        if len(candidates) == 1:
            template = candidates[0]
            return TemplateMatch(
                template=template,
                confidence=0.82,
                reason=f"matched by requested_quantity={quantity}",
                warnings=_template_warnings(template, givens),
            )

    text = _normalize_text(question_text)
    keyword_match = _classify_from_keywords(text)
    if keyword_match:
        return TemplateMatch(
            template=keyword_match,
            confidence=0.62,
            reason="matched by projectile template keywords",
            warnings=_template_warnings(keyword_match, givens),
        )
    return None


def template_for_engine_case(engine_case: str | None) -> ProblemTemplate | None:
    return TEMPLATE_BY_ENGINE_CASE.get(engine_case or "")


def all_engine_cases_covered(engine_cases: set[str]) -> tuple[bool, set[str]]:
    covered = set(TEMPLATE_BY_ENGINE_CASE)
    missing = engine_cases - covered
    return not missing, missing


def _template_warnings(template: ProblemTemplate, givens: list[str]) -> list[str]:
    known_keys = {_normalize_key(given.split("=", 1)[0]) for given in givens if "=" in given}
    warnings: list[str] = []
    for requirement in sorted(template.required_known_keys):
        alternatives = {_normalize_key(part) for part in requirement.split("|")}
        if alternatives and known_keys.isdisjoint(alternatives):
            warnings.append(f"missing required known: {requirement}")
    return warnings


def _classify_from_keywords(text: str) -> ProblemTemplate | None:
    if "air drag" in text:
        return TEMPLATES_BY_ID["air_drag_conceptual"]
    if "hit by a stone" in text and ("t1/t2" in text or "t_1/t_2" in text or "t₁/t₂" in text):
        return TEMPLATES_BY_ID["range_peak_and_average_quantities"]
    if "stair" in text or "step" in text:
        return TEMPLATES_BY_ID["staircase_collision"]
    if "line of greatest slope" in text:
        return TEMPLATES_BY_ID["smooth_incline_vector_composition"]
    if "plane oa" in text and "plane ob" in text:
        return TEMPLATES_BY_ID["two_incline_perpendicular_transfer"]
    if "collide" in text and "inclined" in text:
        return TEMPLATES_BY_ID["relative_motion_on_incline"]
    if "inclined" in text or "incline" in text:
        if "range" in text or "distance along" in text or "maximum distance from" in text:
            return TEMPLATES_BY_ID["inclined_plane_range"]
        return TEMPLATES_BY_ID["inclined_plane_impact"]
    if "target" in text or _has_coordinate_pair(text):
        return TEMPLATES_BY_ID["target_reachability"]
    if "x =" in text and "y =" in text:
        return TEMPLATES_BY_ID["parametric_kinematics"]
    if "velocity" in text and ("angle" in text or "change" in text):
        return TEMPLATES_BY_ID["constant_acceleration_velocity_event"]
    return None


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9()]+", "_", value.lower()).strip("_")


def _normalize_text(value: str) -> str:
    return value.lower().replace("°", "deg").replace("−", "-").replace("–", "-").replace("—", "-")


def _has_coordinate_pair(text: str) -> bool:
    return bool(
        re.search(
            r"\(\s*[-+]?\d+(?:\.\d+)?\s*(?:m|metre|meter)?\s*,\s*[-+]?\d+(?:\.\d+)?\s*(?:m|metre|meter)?\s*\)",
            text,
        )
    )


def _assert_quantity_mapping_is_registered() -> None:
    template_quantities = set().union(*(template.accepted_quantities for template in PROJECTILE_TEMPLATES))
    mapped_quantities = set().union(*CASE_OUTPUT_QUANTITIES.values())
    missing = mapped_quantities - template_quantities
    if missing:
        raise RuntimeError(f"Projectile templates missing requested quantities: {sorted(missing)}")


_assert_quantity_mapping_is_registered()
