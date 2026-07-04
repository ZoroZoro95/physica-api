#!/usr/bin/env python3
"""Regression checks for ad-hoc projectile text/image-OCR solves."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.projectile_engine import solve_ad_hoc_question


@dataclass(frozen=True)
class Case:
    name: str
    question: str
    options: list[str]
    expected_engine_case: str
    expected_option: str | None = None
    expected_value: float | None = None
    expected_text_contains: list[str] | None = None
    expected_trace_contains: list[str] | None = None
    requested_quantity: str | None = None
    suggested_engine_case: str | None = None
    givens: list[str] | None = None
    diagram: dict[str, Any] | None = None
    require_diagram_validation: bool = False
    expected_diagram_kind: str | None = None
    expected_status: str = "passed"
    tolerance: float = 1e-6


CASES = [
    Case(
        name="velocity change interval from OCR text",
        question=(
            "A particle is projected from the ground with an initial velocity of 20 m/s "
            "at an angle of 30deg with horizontal. The magnitude of change in velocity "
            "in a time interval from t = 0 to t = 0.5 s is: (g = 10 m/s^2)"
        ),
        options=["5 m/s", "2.5 m/s", "2 m/s", "4 m/s"],
        expected_engine_case="velocity_change_interval",
        expected_option="a",
        expected_value=5.0,
        requested_quantity="magnitude_change_in_velocity",
    ),
    Case(
        name="speed when velocity direction changes",
        question=(
            "A particle is projected at an angle of 60deg above the horizontal with "
            "a speed of 10 m/s. After some time the direction of its velocity makes "
            "an angle of 30deg above the horizontal. The speed of the particle is:"
        ),
        options=["10 m/s", "5 m/s", "5 sqrt(3) m/s", "10/sqrt(3) m/s"],
        expected_engine_case="velocity_angle_event_speed",
        expected_option="d",
        expected_value=10 / math.sqrt(3),
        requested_quantity="speed_when_velocity_angle_matches",
    ),
    Case(
        name="velocity angle mcq options do not look like target coordinates",
        question=(
            "A particle is projected at an angle of 60deg above the horizontal with a speed of 10 m/s. "
            "After some time the direction of its velocity makes an angle of 30deg above the horizontal. "
            "The speed of the particle at this instant is:\n"
            "(a) 10 m/s\n(b) 5 m/s\n(c) 5sqrt(3) m/s\n(d) 10/sqrt(3) m/s"
        ),
        options=["10 m/s", "5 m/s", "5sqrt(3) m/s", "10/sqrt(3) m/s"],
        expected_engine_case="velocity_angle_event_speed",
        expected_option="d",
        expected_value=10 / math.sqrt(3),
    ),
    Case(
        name="two projectile interception squared time ratio",
        question=(
            "A ball is thrown from the location (x0, y0) = (0, 0) of a horizontal playground "
            "with an initial speed v0 at an angle theta0 from the +x-direction. The ball is "
            "to be hit by a stone, which is thrown at the same time from the location "
            "(x1, y1) = (L, 0). The stone is thrown at an angle (180 - theta1) from the "
            "+x-direction with a suitable initial speed. For a fixed v0, when "
            "(theta0, theta1) = (45deg, 45deg), the stone hits the ball after time T1, "
            "and when (theta0, theta1) = (60deg, 30deg), it hits the ball after time T2. "
            "In such a case, (T1/T2)^2 is _______."
        ),
        options=[],
        expected_engine_case="two_projectile_interception_time_ratio",
        expected_value=2.0,
        requested_quantity="time_ratio_squared",
    ),
    Case(
        name="horizontal throw angle time",
        question=(
            "A stone is projected horizontally with speed 10 m/s. Find the time when "
            "the velocity makes an angle of 45deg with the horizontal. Take g = 10 m/s^2."
        ),
        options=["1 sec", "2 sec", "0.5 sec", "4 sec"],
        expected_engine_case="horizontal_throw_velocity_angle_time",
        expected_option="a",
        expected_value=1.0,
        requested_quantity="time_when_velocity_angle_matches",
    ),
    Case(
        name="projectile split at apex equal fragments",
        question=(
            "A projectile is thrown from a point O on the ground at an angle 45deg from the vertical "
            "and with a speed of 5sqrt(2) m/s. The projectile at the highest point of its trajectory "
            "splits into two equal parts. One part falls vertically down to the ground, 0.5 s after "
            "the splitting. The other part, t seconds after the splitting, falls to the ground at a "
            "distance x meters from the point O. The acceleration due to gravity g = 10 m/s^2."
        ),
        options=[],
        expected_engine_case="projectile_split_at_apex_fragment_time",
        expected_value=0.5,
        requested_quantity="time_after_splitting",
    ),
    Case(
        name="bounce restitution gives rebound height",
        question=(
            "A ball has pre-bounce vertical drop height 20 m and bounces from the ground "
            "with coefficient of restitution e = 0.5. Find the post-bounce height."
        ),
        options=[],
        expected_engine_case="bounce_restitution_height",
        expected_value=5.0,
        requested_quantity="post_bounce_height",
    ),
    Case(
        name="relative vertical throw collides at projectile apex",
        question=(
            "A projectile is fired at 30deg with speed 20 m/s. It collides at its highest point "
            "with an identical particle thrown vertically from the launch level. Find the speed "
            "of vertical projection. Take g = 10 m/s^2."
        ),
        options=[],
        expected_engine_case="relative_projectile_apex_collision",
        expected_value=10.0,
        requested_quantity="speed_of_vertical_projection",
    ),
    Case(
        name="piecewise acceleration changes range after apex",
        question=(
            "A projectile has horizontal range 100 m when gravity is g = 10 m/s^2. "
            "At the highest point the effective gravity becomes 40 m/s^2. Find the new range."
        ),
        options=[],
        expected_engine_case="piecewise_acceleration_at_apex_range",
        expected_value=75.0,
        requested_quantity="new_range_after_apex",
    ),
    Case(
        name="piecewise acceleration infers without requested quantity",
        question=(
            "A projectile has horizontal range 100 m when gravity is g = 10 m/s^2. "
            "At the highest point the effective gravity becomes 40 m/s^2. Find the new range."
        ),
        options=[],
        expected_engine_case="piecewise_acceleration_at_apex_range",
        expected_value=75.0,
    ),
    Case(
        name="basic level-ground maximum range",
        question="Projectile launched at 45deg with 25 m/s. Find the maximum range.",
        options=[],
        expected_engine_case="level_ground_range",
        expected_value=62.5,
        requested_quantity="maximum_range",
    ),
    Case(
        name="maximum range text overrides bad height metadata",
        question="Projectile at 45deg with 25 m/s. Find the maximum range.",
        options=[],
        expected_engine_case="level_ground_range",
        expected_value=62.5,
        requested_quantity="maximum_height",
    ),
    Case(
        name="plain maximum height does not use scaling solver",
        question="Projectile launched at 30deg with 20 m/s. Find the maximum height.",
        options=[],
        expected_engine_case="level_ground_max_height",
        expected_value=5.0,
        requested_quantity="maximum_height",
    ),
    Case(
        name="monkey hunter conceptual wording without full numeric data",
        question=(
            "A monkey hangs from a branch. A hunter aims directly at the monkey and fires. "
            "At the instant of firing, the monkey drops. Explain whether the projectile hits the monkey."
        ),
        options=[],
        expected_engine_case="monkey_hunter_condition",
        expected_text_contains=["projectile reaches the monkey before the monkey reaches the ground"],
    ),
    Case(
        name="level-ground range and time requested together",
        question="A ball is thrown at u=16 m/s at 53 deg. Find range and time of flight.",
        options=[],
        expected_engine_case="level_ground_multi_quantity",
        expected_text_contains=["T =", "R =", "s", "m"],
        requested_quantity="range_and_time_of_flight",
    ),
    Case(
        name="level-ground four requested quantities",
        question=(
            "A projectile is launched at 20 m/s at 30deg. Find range, time of flight, "
            "maximum height, and velocity components. Take g = 10 m/s^2."
        ),
        options=[],
        expected_engine_case="level_ground_multi_quantity",
        expected_text_contains=["u_x =", "u_y =", "T =", "H =", "R ="],
        requested_quantity="multiple_quantities",
    ),
    Case(
        name="level-ground position after time",
        question=(
            "A projectile is launched from level ground with speed 20 m/s at 30deg. "
            "Find its position after 1 s. Take g = 10 m/s^2."
        ),
        options=[],
        expected_engine_case="level_ground_position_at_time",
        requested_quantity="position_at_time",
    ),
    Case(
        name="level-ground velocity after time",
        question=(
            "A projectile is projected at 30deg with speed 20 m/s. "
            "Find its velocity after 1 s. Take g = 10 m/s^2."
        ),
        options=[],
        expected_engine_case="level_ground_velocity_at_time",
        expected_value=10 * math.sqrt(3),
        requested_quantity="velocity_at_time",
    ),
    Case(
        name="same height two times gives initial speed",
        question=(
            "A projectile fired at 30deg is observed at the same height at t = 1 s and t = 3 s. "
            "Find the speed of projection. Take g = 10 m/s^2."
        ),
        options=[],
        expected_engine_case="same_height_times_initial_speed",
        expected_value=40.0,
        requested_quantity="initial_speed_from_same_height_times",
    ),
    Case(
        name="trajectory equation maximum height",
        question="The trajectory of a projectile is y = 2x - x^2/20. Find the maximum height.",
        options=[],
        expected_engine_case="trajectory_equation_max_height",
        expected_value=20.0,
        requested_quantity="maximum_height_from_trajectory",
    ),
    Case(
        name="maximum height scales with speed squared",
        question=(
            "The maximum height reached by a projectile is 64 m. "
            "If the initial velocity is halved, find the new maximum height."
        ),
        options=[],
        expected_engine_case="projectile_height_scaling",
        expected_value=16.0,
        requested_quantity="new_maximum_height",
    ),
    Case(
        name="range angle scaling for same speed",
        question=(
            "The range of a projectile projected at an angle of 15deg is 50 m. "
            "For the same velocity, find the range when projected at 45deg."
        ),
        options=[],
        expected_engine_case="range_angle_scaling",
        expected_value=100.0,
        requested_quantity="new_range",
    ),
    Case(
        name="two projectile same speed compare time height range",
        question=(
            "Two projectiles are launched with the same speed of 40 m/s, one at 30 degrees "
            "and the other at 60 degrees. Compare their time of flight, maximum height, and range."
        ),
        options=[],
        expected_engine_case="two_projectile_same_speed_comparison",
        expected_text_contains=["T=4s", "T=6.9282", "H=20m", "H=60m", "range: same"],
    ),
    Case(
        name="angle when range equals maximum height",
        question="Find the angle of projection for a projectile to have horizontal range equal to maximum height.",
        options=[],
        expected_engine_case="range_equals_max_height_angle",
        expected_value=math.degrees(math.atan(4)),
        requested_quantity="angle_for_range_equal_height",
    ),
    Case(
        name="level-ground launch angles from range",
        question=(
            "A projectile is launched on level ground with speed 20 m/s. "
            "What launch angles give a horizontal range of 20 m? Take g = 10 m/s^2."
        ),
        options=[],
        expected_engine_case="level_ground_launch_angle_from_range",
        requested_quantity="launch_angles",
    ),
    Case(
        name="paraphrased level-ground time of flight",
        question=(
            "A body leaves the origin with speed 20 m/s making an angle of 30deg with the x-axis. "
            "Find the time after which its vertical coordinate again becomes zero. Take g = 10 m/s^2."
        ),
        options=[],
        expected_engine_case="level_ground_time_of_flight",
        expected_value=2.0,
    ),
    Case(
        name="derive level-ground time of flight formula",
        question="Derive the equation for time of flight for a projectile launched at angle theta with initial speed u",
        options=[],
        expected_engine_case="level_ground_time_of_flight_derivation",
        requested_quantity="time_of_flight_derivation",
    ),
    Case(
        name="paraphrased level-ground maximum height",
        question="A ball is fired at 30deg with speed 20 m/s. Find the greatest height reached. Take g = 10 m/s^2.",
        options=[],
        expected_engine_case="level_ground_max_height",
        expected_value=5.0,
    ),
    Case(
        name="split degree symbol time to peak",
        question="A ball is thrown at 15 m/s at an angle of 37 \n∘\n . Calculate time to reach the maximum height.",
        options=[],
        expected_engine_case="level_ground_time_to_peak",
        expected_value=15 * math.sin(math.radians(37)) / 10,
    ),
    Case(
        name="vertical upward time to highest point",
        question="If a ball is thrown upward at 8 m/s, how long to reach the highest point?",
        options=[],
        expected_engine_case="level_ground_time_to_peak",
        expected_value=0.8,
        requested_quantity="time_to_peak",
    ),
    Case(
        name="horizontal cliff scenario summary",
        question="Ball thrown horizontally at 15 m/s from a 45 m cliff.",
        options=[],
        expected_engine_case="height_launch_horizontal_scenario",
    ),
    Case(
        name="horizontal tower impact speed and angle",
        question=(
            "A ball is thrown from a 100 m tall tower with speed 20 m/s horizontally. "
            "Find its impact speed and the angle made by the velocity with the horizontal just before impact."
        ),
        options=[],
        expected_engine_case="height_launch_horizontal_scenario",
        expected_text_contains=["impact speed = 48.9898 m/s", "impact angle = 65.9052 deg below horizontal"],
        expected_trace_contains=["Impact vertical velocity", "Impact speed is", "tan^-1"],
    ),
    Case(
        name="horizontal cliff fall distance asks time",
        question=(
            "Question 3: If a stone is thrown horizontally from a cliff with a velocity of 10 m/s, "
            "how long will it take to fall 45 m to the ground?"
        ),
        options=[],
        expected_engine_case="height_launch_time_of_flight",
        expected_value=3.0,
        requested_quantity="time_of_flight",
    ),
    Case(
        name="horizontal tower height after noun asks time",
        question="A stone is thrown horizontally from a tower 80 m high at 5 m/s. How long to reach the ground?",
        options=[],
        expected_engine_case="height_launch_time_of_flight",
        expected_value=4.0,
        requested_quantity="time_of_flight",
    ),
    Case(
        name="height launch time of flight",
        question=(
            "A projectile is fired from a 45 m high cliff with speed 20 m/s at 30deg above horizontal. "
            "Find the time of flight until it hits the ground. Take g = 10 m/s^2."
        ),
        options=[],
        expected_engine_case="height_launch_time_of_flight",
        expected_value=1 + math.sqrt(10),
        requested_quantity="time_of_flight",
        tolerance=1e-5,
    ),
    Case(
        name="height launch horizontal range",
        question=(
            "A projectile is fired from a 45 m high cliff with speed 20 m/s at 30deg above horizontal. "
            "Find the horizontal range. Take g = 10 m/s^2."
        ),
        options=[],
        expected_engine_case="height_launch_range",
        expected_value=10 * math.sqrt(3) * (1 + math.sqrt(10)),
        requested_quantity="horizontal_range",
        tolerance=1e-5,
    ),
    Case(
        name="height launch from building asks ground time and base distance",
        question=(
            "A ball is thrown from the top of a 60 m building with speed 20 m/s at 30 degrees above the horizontal. "
            "Find the time taken to reach the ground and the horizontal distance from the base of the building."
        ),
        options=[],
        expected_engine_case="height_launch_multi_quantity",
        expected_text_contains=["T = 4.60555 s", "R = 79.7705 m"],
        expected_trace_contains=["positive root gives T", "Horizontal motion gives R"],
    ),
    Case(
        name="minimum speed to target point",
        question=(
            "Find the minimum velocity with which a projectile should be fired to hit "
            "a target at (3 m, 4 m). Take g = 10 m/s^2."
        ),
        options=["10 m/s", "5 m/s", "3sqrt(10) m/s", "8 m/s"],
        expected_engine_case="minimum_speed_to_hit_target",
        expected_option="c",
        expected_value=math.sqrt(90),
        requested_quantity="minimum_launch_speed",
        tolerance=1e-5,
    ),
    Case(
        name="target launch angles fixed speed",
        question=(
            "A projectile is fired with speed 20 m/s to hit a target at (20 m, 10 m). "
            "Find all launch angles. Take g = 10 m/s^2."
        ),
        options=[],
        expected_engine_case="target_launch_angle_fixed_speed",
        requested_quantity="launch_angles_to_hit_target",
    ),
    Case(
        name="wall height at distance",
        question=(
            "A projectile is launched at 20 m/s at 45deg. What is its height when it reaches "
            "a wall 20 m away? Take g = 10 m/s^2."
        ),
        options=[],
        expected_engine_case="wall_height_at_distance",
        expected_value=10.0,
        requested_quantity="height_at_wall",
    ),
    Case(
        name="wall clearance condition",
        question=(
            "A projectile is launched at 20 m/s at 45deg toward a wall 20 m away and 8 m high. "
            "Does it clear the wall? Take g = 10 m/s^2."
        ),
        options=[],
        expected_engine_case="wall_clearance_condition",
        requested_quantity="wall_clearance",
    ),
    Case(
        name="text wall values bypass missing diagram entity",
        question=(
            "A projectile is launched at 20 m/s at 45deg toward a wall 20 m away and 8 m high. "
            "Does it clear the wall? Take g = 10 m/s^2."
        ),
        options=[],
        diagram={"present": True, "type": "wall", "entities": []},
        require_diagram_validation=True,
        expected_engine_case="wall_clearance_condition",
        requested_quantity="wall_clearance",
    ),
    Case(
        name="two projectile component collision time",
        question=(
            "Projectile A is launched from x=0 with velocity components (20, 30) m/s. "
            "Projectile B is launched simultaneously from x=100 m with velocity components (-10, 30) m/s. "
            "Both have the same gravity. When do they collide?"
        ),
        options=[],
        expected_engine_case="two_projectile_collision_time",
        expected_value=10 / 3,
        requested_quantity="collision_time",
        tolerance=1e-5,
    ),
    Case(
        name="text target coordinates bypass missing diagram entity",
        question=(
            "A projectile is fired with speed 20 m/s to hit a target at (20 m, 10 m). "
            "Find all launch angles. Take g = 10 m/s^2."
        ),
        options=[],
        diagram={"present": True, "type": "target", "entities": []},
        require_diagram_validation=True,
        expected_engine_case="target_launch_angle_fixed_speed",
        requested_quantity="launch_angles_to_hit_target",
    ),
    Case(
        name="route velocity at Q away from impact-time solve",
        question=(
            "Two inclined planes OA and OB with inclinations 30 deg and 60 deg intersect at O. "
            "A particle is projected from P with velocity u = 10*sqrt(3) m/s perpendicular to plane OA. "
            "If it strikes plane OB perpendicularly at Q, find the velocity at Q."
        ),
        options=["10 m/s", "10sqrt(3) m/s", "sqrt(3) m/s", "5sqrt(3) m/s"],
        suggested_engine_case="inclined_plane_impact_time",
        requested_quantity="velocity_at_Q",
        expected_engine_case="two_inclines_perpendicular_launch_impact",
        expected_status="passed",
        expected_option="a",
        expected_value=10.0,
    ),
    Case(
        name="accept generic velocity at impact alias for two-incline solve",
        question=(
            "Two inclined planes OA and OB with inclinations 30 deg and 60 deg intersect at O. "
            "A particle is projected from P with velocity u = 10*sqrt(3) m/s perpendicular to plane OA. "
            "If it strikes plane OB perpendicularly at Q, find the velocity at impact."
        ),
        options=["10 m/s", "10sqrt(3) m/s", "sqrt(3) m/s", "5sqrt(3) m/s"],
        suggested_engine_case="two_inclines_perpendicular_launch_impact",
        requested_quantity="velocity_at_impact",
        expected_engine_case="two_inclines_perpendicular_launch_impact",
        expected_status="passed",
        expected_option="a",
        expected_value=10.0,
    ),
    Case(
        name="route staircase away from fielder catch",
        question=(
            "A marble rolls down from top of a staircase with constant horizontal velocity 10 m/s. "
            "If each step is 1 m high and 1 m wide. To which step will the marble strike directly?"
        ),
        options=["21st", "8th", "10th", "18th"],
        suggested_engine_case="fielder_catch_before_ground",
        requested_quantity="step_number",
        givens=["vx=10 m/s", "step_height=1m", "step_width=1m", "g=9.8 m/s^2"],
        expected_engine_case="staircase_collision",
        expected_status="passed",
        expected_option="a",
        expected_value=21.0,
    ),
    Case(
        name="edited staircase height overrides stale extraction givens",
        question=(
            "A marble rolls down from top of a staircase with constant horizontal velocity 10 m/s. "
            "If each step is 2 m high and 1 m wide. To which step will the marble strike directly?\n\n"
            "A marble rolls down from top of a staircase with constant horizontal velocity 10 m/s. "
            "If each step is 1 m high and 1 m wide. To which step will the marble strike directly?"
        ),
        options=["21st", "8th", "10th", "18th"],
        suggested_engine_case="staircase_collision",
        requested_quantity="step_number",
        expected_engine_case="staircase_collision",
        expected_status="passed",
        expected_value=41.0,
    ),
    Case(
        name="route air drag away from horizontal acceleration",
        question=(
            "In a projectile motion let tOA = t1 and tAB = t2. The horizontal displacement "
            "from O to A is R1 and from A to B is R2. If air drag is considered, choose the correct alternatives."
        ),
        options=[
            "t1 will decrease while t2 will increase",
            "H will increase",
            "R1 will decrease while R2 will increase",
            "None of these",
        ],
        suggested_engine_case="projectile_with_horizontal_acceleration",
        requested_quantity="effects of air drag",
        expected_engine_case="air_drag_conceptual_timing",
        expected_status="passed",
        expected_option="a",
    ),
    Case(
        name="air drag image without options does not invent option letter",
        question=(
            "In a projectile motion let tOA = t1 and tAB = t2. The horizontal displacement "
            "from O to A is R1 and from A to B is R2. Maximum height is H and time of flight is T. "
            "If air drag is to be considered, then choose the correct alternative(s)."
        ),
        options=[],
        suggested_engine_case="air_drag_conceptual_timing",
        requested_quantity="effects of air drag",
        expected_engine_case="air_drag_conceptual_timing",
        expected_status="passed",
        expected_option=None,
    ),
    Case(
        name="image two-incline pauses when required geometry is missing",
        question=(
            "Two inclined planes OA and OB with inclinations 30 deg and 60 deg intersect at O. "
            "A particle is projected from P perpendicular to plane OA and strikes plane OB perpendicularly at Q. "
            "Find the velocity at Q."
        ),
        options=["10 m/s", "10sqrt(3) m/s", "sqrt(3) m/s", "5sqrt(3) m/s"],
        suggested_engine_case="two_inclines_perpendicular_launch_impact",
        requested_quantity="impact_speed",
        givens=["u=10sqrt(3) m/s"],
        diagram={"present": True, "type": "two_inclines", "entities": []},
        require_diagram_validation=True,
        expected_engine_case="two_inclines_perpendicular_launch_impact",
        expected_status="needs_review",
        expected_diagram_kind="two_inclines",
    ),
    Case(
        name="image two-incline normalizes valid geometry",
        question=(
            "Two inclined planes OA and OB with inclinations 30 deg and 60 deg intersect at O. "
            "A particle is projected from P perpendicular to plane OA and strikes plane OB perpendicularly at Q. "
            "Find the velocity at Q."
        ),
        options=["10 m/s", "10sqrt(3) m/s", "sqrt(3) m/s", "5sqrt(3) m/s"],
        suggested_engine_case="two_inclines_perpendicular_launch_impact",
        requested_quantity="impact_speed",
        givens=["u=10sqrt(3) m/s"],
        diagram={
            "present": True,
            "type": "two_inclines",
            "entities": [
                {"id": "P", "kind": "point", "label": "P", "description": "launch point P"},
                {"id": "Q", "kind": "point", "label": "Q", "description": "impact point Q"},
                {"id": "angle_oa", "kind": "angle", "value": "30", "unit": "deg", "description": "plane OA angle"},
                {"id": "angle_ob", "kind": "angle", "value": "60", "unit": "deg", "description": "plane OB angle"},
                {"id": "right_angle_p", "kind": "angle", "description": "perpendicular marker at P"},
                {"id": "right_angle_q", "kind": "angle", "description": "right angle marker at Q"},
            ],
        },
        require_diagram_validation=True,
        expected_engine_case="two_inclines_perpendicular_launch_impact",
        expected_status="passed",
        expected_option="a",
        expected_value=10.0,
        expected_diagram_kind="two_inclines",
    ),
]


def main() -> None:
    failures: list[str] = []

    for case in CASES:
        result = solve_ad_hoc_question(
            question_text=case.question,
            engine_case=case.suggested_engine_case,
            options=case.options,
            givens=case.givens or [],
            requested_quantity=case.requested_quantity,
            diagram=case.diagram,
            require_diagram_validation=case.require_diagram_validation,
        )
        if result.status != case.expected_status:
            failures.append(f"{case.name}: status={result.status}, expected={case.expected_status} reason={result.reason}")
            continue
        if result.engine_case != case.expected_engine_case:
            failures.append(f"{case.name}: engine={result.engine_case}, expected={case.expected_engine_case}")
        if case.expected_diagram_kind and result.diagram_model.get("kind") != case.expected_diagram_kind:
            failures.append(
                f"{case.name}: diagram_kind={result.diagram_model.get('kind')}, expected={case.expected_diagram_kind}"
            )
        if case.expected_option and result.predicted_option_letter != case.expected_option:
            failures.append(
                f"{case.name}: option={result.predicted_option_letter}, expected={case.expected_option}"
            )
        if not case.options and result.predicted_option_letter is not None:
            failures.append(f"{case.name}: invented option={result.predicted_option_letter} with no input options")
        if case.expected_value is not None:
            if result.computed_value is None:
                failures.append(f"{case.name}: missing computed value")
            elif abs(result.computed_value - case.expected_value) > case.tolerance:
                failures.append(
                    f"{case.name}: value={result.computed_value:g}, expected={case.expected_value:g}"
                )
        if case.expected_text_contains:
            text = result.computed_text or ""
            missing = [item for item in case.expected_text_contains if item not in text]
            if missing:
                failures.append(f"{case.name}: answer missing {missing}; answer={text!r}")
        if case.expected_trace_contains:
            trace_text = "\n".join(result.trace or [])
            missing = [item for item in case.expected_trace_contains if item not in trace_text]
            if missing:
                failures.append(f"{case.name}: trace missing {missing}; trace={trace_text!r}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        raise SystemExit(1)

    print(f"PASS {len(CASES)} ad-hoc projectile regressions")


if __name__ == "__main__":
    main()
