#!/usr/bin/env python3
"""Attach engine-case classifications to the projectile DPP manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def c(
    engine_case: str,
    projectile_subtype: str,
    requested_quantity: str,
    constraints: list[str],
    *,
    knowns: list[str] | None = None,
    unknowns: list[str] | None = None,
    needs_symbolic_solver: bool = False,
    needs_diagram_geometry: bool = False,
    current_engine_status: str = "unsupported",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "engine_case": engine_case,
        "projectile_subtype": projectile_subtype,
        "requested_quantity": requested_quantity,
        "knowns": knowns or [],
        "unknowns": unknowns or [],
        "constraints": constraints,
        "needs_symbolic_solver": needs_symbolic_solver,
        "needs_diagram_geometry": needs_diagram_geometry,
        "current_engine_status": current_engine_status,
        "notes": notes,
    }


CLASSIFICATIONS: dict[tuple[str, int], dict[str, Any]] = {
    ("projectilenorm", 1): c(
        "parametric_initial_speed",
        "projectile_parametric",
        "initial_speed",
        ["given x(t)", "given y(t)", "differentiate position or read velocity components"],
        knowns=["x(t)=6t", "y(t)=8t-5t^2"],
        unknowns=["v0"],
        current_engine_status="unsupported",
    ),
    ("projectilenorm", 2): c(
        "velocity_change_interval",
        "projectile_basic",
        "magnitude_change_in_velocity",
        ["constant acceleration", "delta_v = g * delta_t"],
        knowns=["v0=20 m/s", "angle=30deg", "g=10 m/s^2", "dt=0.5s"],
        unknowns=["|delta_v|"],
        current_engine_status="partial",
    ),
    ("projectilenorm", 3): c(
        "parametric_curve_classification",
        "kinematics_parametric_non_projectile",
        "path_shape",
        ["integrate dx/dt", "integrate dy/dt", "eliminate time"],
        knowns=["dx/dt=8pi sin(2pi t)", "dy/dt=5pi cos(2pi t)", "x(0)=8", "y(0)=0"],
        unknowns=["curve_type"],
        needs_symbolic_solver=True,
        current_engine_status="unsupported",
        notes="Not standard projectile motion; keep in suite because DPP includes it.",
    ),
    ("projectilenorm", 4): c(
        "velocity_angle_event_speed",
        "projectile_basic",
        "speed_when_velocity_angle_matches",
        ["vx constant", "tan(phi)=vy/vx"],
        knowns=["v0=10 m/s", "launch_angle=60deg", "velocity_angle=30deg"],
        unknowns=["speed_at_event"],
        current_engine_status="unsupported",
    ),
    ("projectilenorm", 5): c(
        "horizontal_throw_velocity_angle_time",
        "projectile_horizontal_throw",
        "time_when_velocity_angle_matches",
        ["vx constant", "vy=gt", "tan(phi)=vy/vx"],
        knowns=["height=100m", "vx=10m/s", "velocity_angle=45deg"],
        unknowns=["time"],
        current_engine_status="unsupported",
    ),
    ("projectilenorm", 6): c(
        "velocity_perpendicular_to_initial_event",
        "projectile_basic",
        "x_coordinate_at_event",
        ["v(t) dot v0 = 0", "x=vx*t"],
        knowns=["v0=20m/s", "angle=30deg"],
        unknowns=["x_event"],
        current_engine_status="unsupported",
    ),
    ("projectilenorm", 7): c(
        "same_range_doubled_angle_time_ratio",
        "projectile_angle_pair",
        "time_of_flight_ratio",
        ["same range", "second angle is double first", "sin(2theta)=sin(4theta)"],
        unknowns=["T1/T2"],
        needs_symbolic_solver=True,
        current_engine_status="partial",
    ),
    ("projectilenorm", 8): c(
        "target_angle_from_short_overshoot",
        "projectile_target_angle",
        "launch_angle_to_hit_target",
        ["same speed", "range at 30deg is target-6", "range at 45deg is target+9"],
        knowns=["undershoot=6m at 30deg", "overshoot=9m at 45deg"],
        unknowns=["hit_angle"],
        needs_symbolic_solver=True,
        current_engine_status="unsupported",
    ),
    ("projectilenorm", 9): c(
        "fielder_catch_before_ground",
        "projectile_moving_observer",
        "fielder_speed",
        ["range of ball", "time of flight", "fielder covers remaining distance"],
        knowns=["v0=15m/s", "angle=30deg", "fielder_distance=70m"],
        unknowns=["fielder_speed"],
        current_engine_status="unsupported",
    ),
    ("projectilenorm", 10): c(
        "average_velocity_to_peak",
        "projectile_basic_symbolic",
        "average_velocity_magnitude_to_peak",
        ["displacement to highest point", "time to highest point", "average velocity = displacement/time"],
        knowns=["v0=v", "angle=theta"],
        unknowns=["|v_avg|"],
        needs_symbolic_solver=True,
        current_engine_status="unsupported",
    ),
    ("projectilenorm", 11): c(
        "projectile_with_horizontal_acceleration",
        "projectile_with_wind_acceleration",
        "modified_range_and_height",
        ["ax=g/4", "vertical motion unchanged", "horizontal displacement gains 0.5*a*T^2"],
        knowns=["original_range=R", "original_max_height=H", "ax=g/4"],
        unknowns=["new_range", "new_height"],
        needs_symbolic_solver=True,
        current_engine_status="unsupported",
    ),
    ("projectilenorm", 12): c(
        "air_drag_conceptual_timing",
        "projectile_with_drag_conceptual",
        "correct_qualitative_statement",
        ["air drag changes ascent/descent timing and range"],
        unknowns=["qualitative_effect"],
        current_engine_status="unsupported",
        notes="Conceptual drag question; not solvable by no-drag deterministic projectile equations.",
    ),
    ("projectilenorm", 13): c(
        "max_range_from_height_fixed_speed",
        "projectile_launch_from_height",
        "maximum_ground_range",
        ["optimize range over launch angle", "landing y=0"],
        knowns=["height=10m", "v0=10m/s"],
        unknowns=["max_range"],
        needs_symbolic_solver=True,
        current_engine_status="partial",
    ),
    ("projectileinc", 1): c(
        "inclined_plane_impact_time",
        "projectile_inclined",
        "time_to_hit_incline",
        ["trajectory intersects y=x*tan(alpha)"],
        knowns=["incline=30deg", "launch_angle_horizontal=60deg", "v0=10sqrt3m/s", "g=10m/s^2"],
        unknowns=["time"],
        current_engine_status="partial",
    ),
    ("projectileinc", 2): c(
        "inclined_plane_same_point_time_ratio",
        "projectile_inclined_symbolic",
        "time_of_flight_ratio",
        ["same launch speed", "same impact point on inclined plane"],
        knowns=["incline_angle=beta", "first_launch_angle=alpha"],
        unknowns=["T1/T2"],
        needs_symbolic_solver=True,
        current_engine_status="unsupported",
    ),
    ("projectileinc", 3): c(
        "inclined_plane_right_angle_impact_condition",
        "projectile_inclined_symbolic",
        "condition_for_right_angle_impact",
        ["impact velocity perpendicular to incline"],
        knowns=["incline_angle=alpha", "launch_angle_to_incline=theta"],
        unknowns=["relation_between_theta_alpha"],
        needs_symbolic_solver=True,
        needs_diagram_geometry=True,
        current_engine_status="unsupported",
    ),
    ("projectileinc", 4): c(
        "target_reachability_fixed_speed",
        "projectile_target_reachability",
        "impossible_target_condition",
        ["trajectory through (alpha,beta)", "fixed speed sqrt(2g alpha)", "real launch angle condition"],
        knowns=["target=(alpha,beta)", "v0=sqrt(2g alpha)"],
        unknowns=["reachability_condition"],
        needs_symbolic_solver=True,
        current_engine_status="unsupported",
    ),
    ("projectileinc", 5): c(
        "staircase_collision",
        "projectile_staircase",
        "step_number_hit",
        ["horizontal throw", "stair tread/riser geometry", "first collision with step boundary"],
        knowns=["vx=10m/s", "step_height=1m", "step_width=1m", "g=9.8m/s^2"],
        unknowns=["step_number"],
        needs_diagram_geometry=True,
        current_engine_status="unsupported",
    ),
    ("projectileinc", 6): c(
        "minimum_speed_to_hit_target",
        "projectile_target_min_speed",
        "minimum_launch_speed",
        ["target point", "optimize over angle"],
        knowns=["target=(40m,30m)", "g=10m/s^2"],
        unknowns=["min_v0"],
        needs_symbolic_solver=True,
        current_engine_status="unsupported",
    ),
    ("projectileinc", 7): c(
        "inclined_plane_max_normal_distance_velocity_component",
        "projectile_inclined_components",
        "normal_velocity_component_at_max_distance",
        ["maximum perpendicular distance from incline", "normal velocity component is zero"],
        knowns=["speed=u", "launch_angle_to_incline=theta", "incline_angle=beta"],
        unknowns=["y_component_velocity"],
        needs_diagram_geometry=True,
        current_engine_status="unsupported",
    ),
    ("projectileinc", 8): c(
        "perpendicular_launch_range_on_incline",
        "projectile_inclined",
        "range_on_incline",
        ["launch perpendicular to incline", "impact with incline"],
        knowns=["v0=10m/s", "launch perpendicular to plane"],
        unknowns=["range_on_incline"],
        needs_diagram_geometry=True,
        current_engine_status="partial",
    ),
    ("projectileinc", 9): c(
        "max_range_on_incline",
        "projectile_inclined_symbolic",
        "maximum_range_on_incline",
        ["optimize incline range over launch angle"],
        knowns=["incline_angle=theta", "v0=v"],
        unknowns=["max_range"],
        needs_symbolic_solver=True,
        current_engine_status="partial",
    ),
    ("projectileinc", 10): c(
        "horizontal_launch_onto_incline_distance",
        "projectile_inclined",
        "distance_along_incline_to_impact",
        ["horizontal launch from top", "intersect falling trajectory with 45deg incline"],
        knowns=["vx=v", "incline_angle=45deg"],
        unknowns=["impact_distance_along_plane"],
        needs_symbolic_solver=True,
        current_engine_status="unsupported",
    ),
    ("projectileinc", 11): c(
        "two_inclines_perpendicular_launch_impact",
        "projectile_inclined_multi_surface",
        "impact_speed",
        ["launch perpendicular to first plane", "impact perpendicular to second plane"],
        knowns=["plane_OA=30deg", "plane_OB=60deg", "u=10sqrt3m/s"],
        unknowns=["impact_speed"],
        needs_diagram_geometry=True,
        current_engine_status="unsupported",
    ),
    ("projectileinc", 12): c(
        "projectile_collides_with_sliding_particle_on_incline",
        "projectile_inclined_relative_motion",
        "projection_speed",
        ["projectile P", "particle Q slides on smooth incline", "collision after 4s"],
        knowns=["collision_time=4s", "incline geometry from diagram"],
        unknowns=["projection_speed"],
        needs_diagram_geometry=True,
        current_engine_status="unsupported",
    ),
    ("projectileinc", 13): c(
        "motion_on_smooth_incline_perpendicular_to_slope",
        "inclined_plane_kinematics",
        "speed_after_time",
        ["initial velocity perpendicular to line of greatest slope", "acceleration down incline"],
        knowns=["initial_speed=8m/s", "time=1s"],
        unknowns=["speed_after_1s"],
        needs_diagram_geometry=True,
        current_engine_status="unsupported",
    ),
    ("projectileinc", 14): c(
        "three_dimensional_projectile_line_intersection",
        "projectile_3d",
        "impact_coordinates_on_horizontal_line",
        ["3D launch plane contains horizontal line PQ", "intersect projectile with y=0 horizontal line direction"],
        knowns=["P=(2,0,0)m", "v0=10m/s", "launch_angle=45deg", "line_angle=37deg", "g=10m/s^2"],
        unknowns=["impact_coordinates"],
        needs_diagram_geometry=True,
        current_engine_status="unsupported",
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=Path("questions/manifest/projectile_dpp_manifest.json"),
    )
    args = parser.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    for entry in data:
        key = (entry["pdf_id"], entry["question_number"])
        classification = CLASSIFICATIONS.get(key)
        if classification is None:
            raise SystemExit(f"missing classification for {key}")
        entry.update(classification)

    args.manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Classified {len(data)} questions in {args.manifest}")


if __name__ == "__main__":
    main()
