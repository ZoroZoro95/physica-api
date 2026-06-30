from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


CoverageStatus = Literal["solved", "partial", "missing"]


@dataclass(frozen=True)
class CoverageRow:
    world: str
    unknown: str
    constraints: tuple[str, ...] = ()
    engine_case: str | None = None
    status: CoverageStatus = "missing"
    source: tuple[str, ...] = ("syllabus",)
    needs_diagram: bool = False
    notes: str = ""

    @property
    def key(self) -> tuple[str, str, tuple[str, ...]]:
        return self.world, self.unknown, tuple(sorted(self.constraints))

    def to_dict(self) -> dict:
        return asdict(self)


BASE_COVERAGE_ROWS: tuple[CoverageRow, ...] = (
    CoverageRow(
        world="level_ground",
        unknown="range",
        constraints=("same_height_landing",),
        engine_case="level_ground_range",
        status="solved",
        source=("syllabus", "engine"),
        notes="R = u^2 sin(2theta)/g.",
    ),
    CoverageRow(
        world="level_ground",
        unknown="maximum_range",
        constraints=("same_height_landing", "optimize"),
        engine_case="level_ground_range",
        status="solved",
        source=("syllabus", "engine"),
        notes="Same solver; theta=45deg gives maximum for fixed speed.",
    ),
    CoverageRow(
        world="level_ground",
        unknown="time_of_flight",
        constraints=("same_height_landing",),
        engine_case="level_ground_time_of_flight",
        status="solved",
        source=("syllabus", "engine"),
    ),
    CoverageRow(
        world="level_ground",
        unknown="maximum_height",
        constraints=("peak",),
        engine_case="level_ground_max_height",
        status="solved",
        source=("syllabus", "engine"),
    ),
    CoverageRow(
        world="level_ground",
        unknown="speed_at_velocity_angle",
        constraints=("velocity_angle_event",),
        engine_case="velocity_angle_event_speed",
        status="solved",
        source=("syllabus", "engine"),
    ),
    CoverageRow(
        world="level_ground",
        unknown="time_when_velocity_angle",
        constraints=("horizontal_launch", "velocity_angle_event"),
        engine_case="horizontal_throw_velocity_angle_time",
        status="solved",
        source=("syllabus", "engine"),
    ),
    CoverageRow(
        world="level_ground",
        unknown="change_in_velocity",
        constraints=("constant_gravity", "time_interval"),
        engine_case="velocity_change_interval",
        status="solved",
        source=("syllabus", "engine"),
    ),
    CoverageRow(
        world="level_ground",
        unknown="position_at_time",
        constraints=("same_height_landing",),
        engine_case="level_ground_position_at_time",
        status="solved",
        source=("syllabus", "engine"),
        notes="General x(t), y(t) primitive for fixed time.",
    ),
    CoverageRow(
        world="level_ground",
        unknown="launch_angle",
        constraints=("given_range", "same_height_landing"),
        engine_case="level_ground_launch_angle_from_range",
        status="solved",
        source=("syllabus", "engine"),
        notes="Solve sin(2theta)=gR/u^2; may return two angles.",
    ),
    CoverageRow(
        world="height_launch",
        unknown="maximum_range",
        constraints=("fixed_speed", "optimize"),
        engine_case="max_range_from_height_fixed_speed",
        status="solved",
        source=("syllabus", "engine"),
    ),
    CoverageRow(
        world="height_launch",
        unknown="time_of_flight",
        constraints=("initial_height",),
        engine_case="height_launch_time_of_flight",
        status="solved",
        source=("syllabus", "engine"),
        notes="Quadratic y(t)=0 from nonzero height.",
    ),
    CoverageRow(
        world="height_launch",
        unknown="range",
        constraints=("initial_height",),
        engine_case="height_launch_range",
        status="solved",
        source=("syllabus", "engine"),
        notes="Use height-launch time root then x=u_x t.",
    ),
    CoverageRow(
        world="target",
        unknown="minimum_speed",
        constraints=("fixed_target", "optimize"),
        engine_case="minimum_speed_to_hit_target",
        status="solved",
        source=("syllabus", "engine"),
        needs_diagram=True,
    ),
    CoverageRow(
        world="target",
        unknown="launch_angle",
        constraints=("fixed_speed", "fixed_target"),
        engine_case="target_launch_angle_fixed_speed",
        status="solved",
        source=("syllabus", "engine"),
        needs_diagram=True,
        notes="General target-angle solver; DPP-specific overshoot case remains separate.",
    ),
    CoverageRow(
        world="target",
        unknown="reachability_condition",
        constraints=("fixed_speed", "fixed_target"),
        engine_case="target_reachability_fixed_speed",
        status="solved",
        source=("syllabus", "engine"),
        needs_diagram=True,
    ),
    CoverageRow(
        world="wall",
        unknown="height_at_wall",
        constraints=("fixed_horizontal_distance",),
        engine_case="wall_height_at_distance",
        status="solved",
        source=("syllabus", "engine"),
        needs_diagram=True,
        notes="Use trajectory equation at x=wall_x.",
    ),
    CoverageRow(
        world="wall",
        unknown="clears_wall_condition",
        constraints=("fixed_horizontal_distance", "obstacle_height"),
        engine_case="wall_clearance_condition",
        status="solved",
        source=("syllabus", "engine"),
        needs_diagram=True,
    ),
    CoverageRow(
        world="incline",
        unknown="impact_time",
        constraints=("surface_intersection",),
        engine_case="inclined_plane_impact_time",
        status="solved",
        source=("syllabus", "engine"),
        needs_diagram=True,
    ),
    CoverageRow(
        world="incline",
        unknown="condition_for_perpendicular_impact",
        constraints=("surface_intersection", "perpendicular_impact"),
        engine_case="inclined_plane_right_angle_impact_condition",
        status="solved",
        source=("syllabus", "engine"),
        needs_diagram=True,
    ),
    CoverageRow(
        world="incline",
        unknown="range_on_incline",
        constraints=("perpendicular_launch",),
        engine_case="perpendicular_launch_range_on_incline",
        status="solved",
        source=("syllabus", "engine"),
        needs_diagram=True,
    ),
    CoverageRow(
        world="incline",
        unknown="maximum_range_on_incline",
        constraints=("optimize",),
        engine_case="max_range_on_incline",
        status="solved",
        source=("syllabus", "engine"),
        needs_diagram=True,
    ),
    CoverageRow(
        world="incline",
        unknown="range_ratio_or_time_ratio",
        constraints=("same_point", "two_launch_angles"),
        engine_case="inclined_plane_same_point_time_ratio",
        status="solved",
        source=("syllabus", "engine"),
        needs_diagram=True,
    ),
    CoverageRow(
        world="staircase",
        unknown="step_number",
        constraints=("piecewise_vertical_faces",),
        engine_case="staircase_collision",
        status="solved",
        source=("syllabus", "engine"),
        needs_diagram=True,
    ),
    CoverageRow(
        world="bounce",
        unknown="post_bounce_height_or_restitution",
        constraints=("coefficient_of_restitution",),
        engine_case="bounce_restitution_height",
        status="solved",
        source=("advanced", "engine"),
        needs_diagram=True,
        notes="Solves vertical bounce height/restitution relation. More complex angled rebound variants still need explicit givens.",
    ),
    CoverageRow(
        world="level_ground",
        unknown="range_under_changed_acceleration",
        constraints=("apex_boundary", "piecewise_acceleration"),
        engine_case="piecewise_acceleration_at_apex_range",
        status="solved",
        source=("advanced", "engine"),
        notes="Splits path at apex and scales descent time by sqrt(g1/g2).",
    ),
    CoverageRow(
        world="multi_projectile",
        unknown="vertical_throw_speed_for_apex_collision",
        constraints=("apex_collision", "vertical_throw"),
        engine_case="relative_projectile_apex_collision",
        status="solved",
        source=("advanced", "engine"),
        notes="Uses apex time/height and vertical throw kinematics.",
    ),
    CoverageRow(
        world="two_inclines",
        unknown="impact_speed",
        constraints=("perpendicular_launch", "perpendicular_impact"),
        engine_case="two_inclines_perpendicular_launch_impact",
        status="solved",
        source=("dpp", "engine"),
        needs_diagram=True,
    ),
    CoverageRow(
        world="multi_projectile",
        unknown="time_ratio_squared",
        constraints=("simultaneous_launch", "interception"),
        engine_case="two_projectile_interception_time_ratio",
        status="solved",
        source=("syllabus", "engine"),
    ),
    CoverageRow(
        world="multi_projectile",
        unknown="collision_time",
        constraints=("simultaneous_launch", "interception"),
        engine_case="two_projectile_collision_time",
        status="partial",
        source=("syllabus", "engine"),
        notes="Solved for explicit component-form text; general angle/speed relative launch parsing still needs expansion.",
    ),
    CoverageRow(
        world="relative_motion",
        unknown="projection_speed",
        constraints=("inclined_motion", "collision"),
        engine_case="projectile_collides_with_sliding_particle_on_incline",
        status="solved",
        source=("dpp", "engine"),
        needs_diagram=True,
    ),
    CoverageRow(
        world="drag",
        unknown="drag_effects",
        constraints=("qualitative",),
        engine_case="air_drag_conceptual_timing",
        status="partial",
        source=("syllabus", "engine"),
        needs_diagram=True,
        notes="Qualitative rule exists for current DPP family; not a numeric drag solver.",
    ),
    CoverageRow(
        world="3d",
        unknown="impact_coordinates",
        constraints=("line_constraint",),
        engine_case="three_dimensional_projectile_line_intersection",
        status="solved",
        source=("dpp", "engine"),
        needs_diagram=True,
    ),
)


def merge_coverage_rows(rows: list[CoverageRow]) -> list[CoverageRow]:
    merged: dict[tuple[str, str, tuple[str, ...]], CoverageRow] = {}
    for row in rows:
        existing = merged.get(row.key)
        if existing is None or _status_rank(row.status) > _status_rank(existing.status):
            merged[row.key] = row
            continue
        if existing and row.source:
            merged[row.key] = CoverageRow(
                world=existing.world,
                unknown=existing.unknown,
                constraints=existing.constraints,
                engine_case=existing.engine_case or row.engine_case,
                status=existing.status,
                source=tuple(sorted(set(existing.source).union(row.source))),
                needs_diagram=existing.needs_diagram or row.needs_diagram,
                notes=existing.notes or row.notes,
            )
    return sorted(merged.values(), key=lambda item: (item.world, item.unknown, item.constraints))


def _status_rank(status: CoverageStatus) -> int:
    return {"missing": 0, "partial": 1, "solved": 2}[status]
