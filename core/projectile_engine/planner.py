from __future__ import annotations

import math
import re
from dataclasses import asdict

from .models import EquationPlan, EquationStep, EvaluationResult
from .templates import TEMPLATE_BY_ENGINE_CASE


VELOCITY_EVENT_CASES = {
    "velocity_change_interval",
    "velocity_angle_event_speed",
    "horizontal_throw_velocity_angle_time",
    "velocity_perpendicular_to_initial_event",
}


def build_equation_plan(result: EvaluationResult, givens: list[str]) -> dict:
    has_answer = bool(result.computed_text) or result.computed_value is not None or bool(result.predicted_option_letter)
    custom_builders = {
        "projectile_collides_with_sliding_particle_on_incline": _projectile_slider_incline_collision_plan,
    }
    if has_answer and result.engine_case in custom_builders:
        return asdict(custom_builders[result.engine_case](result, givens))
    if result.engine_case not in VELOCITY_EVENT_CASES or not has_answer:
        if not has_answer or result.engine_case not in PLAN_BLUEPRINTS:
            return {}
        return asdict(_blueprint_plan(result, givens))
    builders = {
        "velocity_change_interval": _velocity_change_interval_plan,
        "velocity_angle_event_speed": _velocity_angle_event_speed_plan,
        "horizontal_throw_velocity_angle_time": _horizontal_throw_angle_time_plan,
        "velocity_perpendicular_to_initial_event": _velocity_perpendicular_plan,
    }
    plan = builders[result.engine_case](result, givens)
    return asdict(plan)


def _velocity_change_interval_plan(result: EvaluationResult, givens: list[str]) -> EquationPlan:
    return EquationPlan(
        template_id="constant_acceleration_velocity_event",
        engine_case=result.engine_case,
        goal="Find the magnitude of change in velocity during a time interval.",
        givens=givens,
        unknown="|Delta v|",
        invariant="In ideal projectile motion, acceleration is only vertical, so horizontal velocity does not affect Delta v.",
        steps=[
            EquationStep(
                id="model",
                title="Decide what changes",
                equation="a = -g j",
                explanation="Gravity changes only the vertical velocity component. The horizontal component remains constant.",
                focus_ids=["v_x", "v_y"],
            ),
            EquationStep(
                id="delta_v",
                title="Use acceleration over time",
                equation="|Delta v| = g Delta t",
                substitution=_trace(result, 1),
                explanation="Velocity change from constant acceleration is acceleration multiplied by elapsed time.",
                focus_ids=["v_y"],
            ),
            EquationStep(
                id="answer",
                title="State the magnitude",
                equation=result.computed_text or "",
                explanation=f"The required magnitude is {result.computed_text}.",
                focus_ids=["answer"],
            ),
        ],
        final_answer=result.computed_text or "",
        exam_takeaway="For velocity change over time in projectile motion, ignore launch angle unless non-gravity acceleration is present.",
    )


def _velocity_angle_event_speed_plan(result: EvaluationResult, givens: list[str]) -> EquationPlan:
    return EquationPlan(
        template_id="constant_acceleration_velocity_event",
        engine_case=result.engine_case,
        goal="Find speed when the velocity vector makes a given angle with the horizontal.",
        givens=givens,
        unknown="speed at the velocity-angle event",
        invariant="The horizontal component of velocity remains constant throughout ideal projectile motion.",
        steps=[
            EquationStep(
                id="constant_vx",
                title="Lock the horizontal component",
                equation="v_x = u cos(theta)",
                substitution=_trace(result, 0),
                explanation="Whatever happens vertically, the horizontal component stays equal to its launch value.",
                focus_ids=["v_x"],
            ),
            EquationStep(
                id="angle_relation",
                title="Use the new velocity direction",
                equation="cos(phi) = v_x / v",
                substitution=_trace(result, 1),
                explanation="At the event, the velocity direction is known, so speed is fixed by its horizontal projection.",
                focus_ids=["velocity_angle", "v_x"],
            ),
            EquationStep(
                id="answer",
                title="Compute the speed",
                equation="v = v_x / cos(phi)",
                substitution=result.computed_text or "",
                explanation=f"The particle speed at that instant is {result.computed_text}.",
                focus_ids=["answer"],
            ),
        ],
        final_answer=result.computed_text or "",
        exam_takeaway="When velocity angle is given, use the unchanged horizontal component to recover the full speed.",
    )


def _horizontal_throw_angle_time_plan(result: EvaluationResult, givens: list[str]) -> EquationPlan:
    return EquationPlan(
        template_id="constant_acceleration_velocity_event",
        engine_case=result.engine_case,
        goal="Find when a horizontal projection reaches a given velocity angle.",
        givens=givens,
        unknown="time at velocity-angle event",
        invariant="For horizontal projection, v_x is constant and v_y grows as gt.",
        steps=[
            EquationStep(
                id="components",
                title="Write velocity components",
                equation="v_x = u,  v_y = gt",
                substitution=_trace(result, 0),
                explanation="A horizontal launch starts with zero vertical velocity, then gravity builds vertical speed.",
                focus_ids=["v_x", "v_y"],
            ),
            EquationStep(
                id="angle_condition",
                title="Convert angle to component ratio",
                equation="tan(phi) = v_y / v_x = gt / u",
                substitution=_trace(result, 1),
                explanation="The direction of velocity is controlled by the ratio of vertical to horizontal components.",
                focus_ids=["velocity_angle"],
            ),
            EquationStep(
                id="answer",
                title="Solve for time",
                equation="t = u tan(phi) / g",
                substitution=result.computed_text or "",
                explanation=f"The time is {result.computed_text}.",
                focus_ids=["answer"],
            ),
        ],
        final_answer=result.computed_text or "",
        exam_takeaway="For horizontal projection, angle questions usually reduce to tan(phi)=gt/u.",
    )


def _velocity_perpendicular_plan(result: EvaluationResult, givens: list[str]) -> EquationPlan:
    return EquationPlan(
        template_id="constant_acceleration_velocity_event",
        engine_case=result.engine_case,
        goal="Find the event where velocity becomes perpendicular to the initial velocity.",
        givens=givens,
        unknown="x-coordinate at perpendicular-velocity event",
        invariant="The perpendicular event is defined by a zero dot product between current and initial velocity.",
        steps=[
            EquationStep(
                id="condition",
                title="Translate perpendicular into algebra",
                equation="v(t) dot u = 0",
                substitution=_trace(result, 0),
                explanation="Perpendicular vectors have zero dot product, so this condition gives the event time.",
                focus_ids=["v_initial", "v_current"],
            ),
            EquationStep(
                id="time",
                title="Find the event time",
                equation="t = u^2 / (g u_y)",
                substitution=_trace(result, 2),
                explanation="Substitute velocity components into the dot-product condition and solve for time.",
                focus_ids=["time"],
            ),
            EquationStep(
                id="position",
                title="Convert time into horizontal position",
                equation="x = u_x t",
                substitution=_trace(result, 3),
                explanation=f"The required x-coordinate is {result.computed_text}.",
                focus_ids=["answer"],
            ),
        ],
        final_answer=result.computed_text or "",
        exam_takeaway="Perpendicular velocity events are dot-product problems, not range or height problems.",
    )


def _projectile_slider_incline_collision_plan(result: EvaluationResult, givens: list[str]) -> EquationPlan:
    time = _given_number(givens, ["collision_time", "time", "t", "t1"])
    incline = _given_number(givens, ["incline", "incline_angle", "angle"])
    g = _given_number(givens, ["g"])
    if time is None:
        time = _number_from_text(" ".join(result.trace), r"t\s*=\s*([0-9.]+)")
    if incline is None:
        incline = _number_from_text(" ".join(result.trace), r"([0-9.]+)\s*deg\s+incline")
    if g is None:
        g = _number_from_text(" ".join(result.trace), r"g\s*=\s*([0-9.]+)")
    time = time if time is not None else 4.0
    incline = incline if incline is not None else 60.0
    g = g if g is not None else 10.0
    cos_alpha = math.cos(math.radians(incline))
    answer = result.computed_text or f"{0.5 * g * cos_alpha * time:g} m/s"
    givens_out = list(givens)
    if not any(item.split("=", 1)[0].strip() in {"collision_time", "time", "t"} for item in givens_out if "=" in item):
        givens_out.append(f"collision_time={time:g}s")
    if not any(item.split("=", 1)[0].strip() in {"incline", "incline_angle", "angle"} for item in givens_out if "=" in item):
        givens_out.append(f"incline={incline:g}deg")
    if not any(item.split("=", 1)[0].strip() == "g" for item in givens_out if "=" in item):
        givens_out.append(f"g={g:g}m/s^2")
    return EquationPlan(
        template_id="relative_motion_on_incline",
        engine_case=result.engine_case,
        goal="Find the speed with which P must be projected so that it collides with Q on the smooth incline.",
        givens=givens_out,
        unknown="projection speed of P",
        invariant="Resolve motion along the incline and normal to the incline. Collision requires both along-plane and normal separation to be zero at the same time.",
        steps=[
            EquationStep(
                id="read_diagram",
                title="Read the diagram condition",
                equation="P is projected normal to the incline; Q is released on the incline",
                explanation=(
                    "The missing physics is in the figure: P starts perpendicular to the plane, while Q starts from rest and remains constrained to the smooth plane."
                ),
                focus_ids=["point:launch", "surface:inclined_plane", "incline:normal_axis", "actor:projectile_p", "actor:slider_q"],
            ),
            EquationStep(
                id="along_plane",
                title="Check motion along the plane",
                equation="s_P = 1/2 g sin(alpha)t^2,  s_Q = 1/2 g sin(alpha)t^2",
                substitution=f"Both particles start with zero along-plane velocity, so after {time:g}s their along-plane displacement is identical.",
                explanation=(
                    "Along the incline, P and Q have the same acceleration component g sin(alpha). This direction does not determine u; it only confirms they stay aligned along the plane."
                ),
                focus_ids=["surface:inclined_plane", "incline:tangent_axis", "trajectory:p", "trajectory:q"],
            ),
            EquationStep(
                id="normal_plane",
                title="Write normal separation",
                equation="n_P = ut - 1/2 g cos(alpha)t^2,  n_Q = 0",
                substitution="Q stays on the plane, so only P's normal displacement must be brought back to zero.",
                explanation=(
                    "Normal to the incline, P first moves away from the plane with speed u, while gravity pulls it back with component g cos(alpha)."
                ),
                focus_ids=["incline:normal_axis", "actor:projectile_p", "trajectory:p", "point:collision"],
            ),
            EquationStep(
                id="collision_condition",
                title="Apply collision condition",
                equation="0 = ut - 1/2 g cos(alpha)t^2",
                substitution="At collision, P is back on the plane at the same point as Q.",
                explanation="Set normal separation to zero. The root t = 0 is the launch instant; the given nonzero collision time gives u.",
                focus_ids=["point:collision", "event:collision", "trajectory:p", "trajectory:q"],
            ),
            EquationStep(
                id="solve_u",
                title="Solve for projection speed",
                equation="u = g cos(alpha)t / 2",
                substitution=f"u = {g:g} cos({incline:g}deg) * {time:g} / 2 = {g:g} * {cos_alpha:g} * {time:g} / 2",
                explanation="Now substitute the incline angle and collision time.",
                focus_ids=["quantity:u", "point:collision", "event:collision"],
            ),
            EquationStep(
                id="answer",
                title="State the answer",
                equation=f"u = {answer}",
                explanation=f"The speed of projection of P is {answer}.",
                focus_ids=["answer", "quantity:u", "actor:projectile_p"],
            ),
        ],
        final_answer=answer,
        exam_takeaway="For this setup, the along-plane motion is already synchronized; the speed is fixed by the normal-to-plane return condition.",
    )


def _trace(result: EvaluationResult, index: int) -> str:
    return result.trace[index] if 0 <= index < len(result.trace) else ""


def _given_number(givens: list[str], keys: list[str]) -> float | None:
    wanted = {key.lower() for key in keys}
    for given in givens:
        if "=" not in given:
            continue
        key, value = given.split("=", 1)
        if key.strip().lower() not in wanted:
            continue
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if match:
            return float(match.group(0))
    return None


def _number_from_text(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1))


PLAN_BLUEPRINTS: dict[str, dict[str, object]] = {
    "parametric_initial_speed": {
        "goal": "Find initial speed from parametric position equations.",
        "unknown": "initial speed",
        "invariant": "Velocity components are derivatives of position components.",
        "equations": ["v_x = dx/dt", "v_y = dy/dt", "v_0 = sqrt(v_x^2 + v_y^2)"],
        "takeaway": "For x(t), y(t) questions, read velocity from derivatives before using projectile formulas.",
    },
    "parametric_curve_classification": {
        "goal": "Classify the curve by eliminating time from component motion.",
        "unknown": "path shape",
        "invariant": "Parametric component equations define the path; projectile motion is not assumed.",
        "equations": ["integrate dx/dt and dy/dt", "eliminate t", "identify the conic"],
        "takeaway": "Not every x-y motion question in a projectile DPP is actually parabolic projectile motion.",
    },
    "same_range_doubled_angle_time_ratio": {
        "goal": "Find time-of-flight ratio for two equal-range projections.",
        "unknown": "time ratio",
        "invariant": "For same speed and same level, range is proportional to sin(2theta).",
        "equations": ["R = u^2 sin(2theta)/g", "sin(2a) = sin(4a)", "T ∝ sin(theta)"],
        "takeaway": "Equal range usually means paired launch angles; time ratio comes from vertical component.",
    },
    "two_projectile_interception_time_ratio": {
        "goal": "Find the squared ratio of interception times for two simultaneous projectile launches.",
        "unknown": "(T1/T2)^2",
        "invariant": "Both bodies have the same vertical acceleration, so relative vertical acceleration is zero.",
        "equations": [
            "v0 sin(theta0) = u sin(theta1)",
            "L = T[v0 cos(theta0) + u cos(theta1)]",
            "T = L / {v0[cos(theta0) + sin(theta0)cot(theta1)]}",
        ],
        "takeaway": "For two projectiles launched together under gravity, use relative motion; gravity cancels between them.",
    },
    "two_projectile_same_speed_comparison": {
        "goal": "Compare time of flight, maximum height, and range for two equal-speed launches.",
        "unknown": "time-height-range comparison",
        "invariant": "Both projectiles have the same speed and land on the same level; only launch angle changes the component formulas.",
        "equations": ["T = 2u sin(theta)/g", "H = u^2 sin^2(theta)/(2g)", "R = u^2 sin(2theta)/g"],
        "takeaway": "Complementary launch angles have the same range, but the steeper angle stays longer and reaches higher.",
    },
    "target_angle_from_short_overshoot": {
        "goal": "Infer the launch angle that exactly hits the target from two miss distances.",
        "unknown": "launch angle",
        "invariant": "For fixed speed on level ground, range is proportional to sin(2theta).",
        "equations": ["D - 6 = k sin60deg", "D + 9 = k", "sin(2theta) = D/k"],
        "takeaway": "Overshoot and undershoot encode the true range indirectly.",
    },
    "fielder_catch_before_ground": {
        "goal": "Find the fielder speed needed to catch the projectile before it lands.",
        "unknown": "fielder speed",
        "invariant": "The ball and fielder share the same available flight time.",
        "equations": ["T = 2u sin(theta)/g", "R = u cos(theta) T", "v_f = remaining distance / T"],
        "takeaway": "First compute the ball's time window, then assign the remaining horizontal distance to the fielder.",
    },
    "average_velocity_to_peak": {
        "goal": "Find average velocity magnitude from launch to highest point.",
        "unknown": "average velocity magnitude",
        "invariant": "Average velocity equals displacement divided by time, component by component.",
        "equations": ["v_x,avg = u cos(theta)", "v_y,avg = u sin(theta)/2", "|v_avg| = sqrt(v_x,avg^2 + v_y,avg^2)"],
        "takeaway": "To the peak, horizontal average remains unchanged while vertical average is half the initial vertical component.",
    },
    "projectile_with_horizontal_acceleration": {
        "goal": "Find how added horizontal acceleration changes range and height.",
        "unknown": "new range and maximum height",
        "invariant": "Horizontal acceleration does not affect vertical motion.",
        "equations": ["H unchanged", "extra x = (1/2)a_x T^2", "new range = R + extra x"],
        "takeaway": "Separate horizontal and vertical motion; only the horizontal answer changes here.",
    },
    "level_ground_range": {
        "goal": "Find horizontal range for level-ground projectile motion.",
        "unknown": "range",
        "invariant": "For launch and landing at the same height, derive range from vertical flight time and constant horizontal velocity.",
        "equations": [
            "u_x = u cos(theta), u_y = u sin(theta)",
            "0 = u_y T - (1/2)gT^2",
            "T = 2u_y/g = 2u sin(theta)/g",
            "R = u_x T",
            "R = u^2 sin(2theta)/g",
        ],
        "takeaway": "At 45deg on level ground, sin(2theta)=1, so the range is maximized for a fixed speed.",
    },
    "level_ground_time_of_flight": {
        "goal": "Find time of flight for level-ground projectile motion.",
        "unknown": "time of flight",
        "invariant": "The projectile lands when vertical displacement returns to zero.",
        "equations": ["y = u sin(theta)t - (1/2)gt^2", "set y=0", "T = 2u sin(theta)/g"],
        "takeaway": "For same-height landing, time is controlled only by the initial vertical component.",
    },
    "level_ground_multi_quantity": {
        "goal": "Find all requested level-ground projectile quantities from one shared motion model.",
        "unknown": "requested projectile quantities",
        "invariant": "Resolve velocity once; vertical motion controls time and height while horizontal uniform motion controls range.",
        "equations": [
            "u_x = u cos(theta), u_y = u sin(theta)",
            "t_peak = u_y/g",
            "0 = u_y T - (1/2)gT^2",
            "T = 2u_y/g = 2u sin(theta)/g",
            "H = u_y^2/(2g)",
            "R = u_x T",
            "R = u^2 sin(2theta)/g",
        ],
        "takeaway": "When multiple quantities are asked, compute the shared components once and report every requested output.",
    },
    "level_ground_time_of_flight_derivation": {
        "goal": "Derive the time-of-flight formula for a level-ground projectile.",
        "unknown": "time-of-flight formula",
        "invariant": "Vertical motion alone decides when the projectile returns to launch height.",
        "equations": [
            "u_x = u cos(theta), u_y = u sin(theta)",
            "y(t) = u_y t - (1/2)gt^2",
            "0 = t(u_y - gt/2)",
            "T = 2u_y/g",
            "T = 2u sin(theta)/g",
        ],
        "takeaway": "The nonzero root gives landing time; the zero root is only the launch instant.",
    },
    "level_ground_time_to_peak": {
        "goal": "Find time taken to reach the highest point.",
        "unknown": "time to peak",
        "invariant": "At the highest point, the vertical velocity component becomes zero.",
        "equations": [
            "u_y = u sin(theta)",
            "v_y = u_y - gt",
            "0 = u_y - gt_peak",
            "t_peak = u_y/g = u sin(theta)/g",
        ],
        "takeaway": "Time to peak depends only on the initial vertical component.",
    },
    "level_ground_max_height": {
        "goal": "Find maximum height for level-ground projectile motion.",
        "unknown": "maximum height",
        "invariant": "At the top, vertical velocity is zero.",
        "equations": ["v_y^2 = u_y^2 - 2gH", "0 = u^2 sin^2(theta) - 2gH", "H = u^2 sin^2(theta)/(2g)"],
        "takeaway": "Maximum height comes from vertical motion only; horizontal velocity is irrelevant.",
    },
    "monkey_hunter_condition": {
        "goal": "Explain the falling-target hit condition.",
        "unknown": "falling target hit condition",
        "invariant": "The dart and monkey have the same downward gravitational displacement after release.",
        "equations": [
            "aim line: hunter points directly at the monkey",
            "projectile drop = (1/2)gt^2",
            "monkey drop = (1/2)gt^2",
            "hit if line-of-sight arrival time is before monkey ground time",
        ],
        "takeaway": "The shot hits the falling monkey if the projectile reaches the original line of sight before the monkey reaches the ground.",
    },
    "projectile_split_at_apex_fragment_time": {
        "goal": "Find the landing time of the second equal fragment after the projectile splits at the apex.",
        "unknown": "time after splitting",
        "invariant": "At the apex, vertical velocity is zero; the split changes horizontal momentum distribution, not the fall time from the same height.",
        "equations": [
            "u_y = u sin(theta)",
            "H = u_y^2/(2g)",
            "t_fall = sqrt(2H/g)",
            "m u_x = (m/2)0 + (m/2)v_2x",
        ],
        "takeaway": "For an apex split, vertical fall time comes from height; equal-mass momentum only affects where the other fragment lands.",
    },
    "level_ground_position_at_time": {
        "goal": "Find projectile coordinates at a specified time.",
        "unknown": "position at time t",
        "invariant": "Horizontal motion is uniform; vertical motion has constant downward acceleration.",
        "equations": ["x = x0 + u cos(theta)t", "y = y0 + u sin(theta)t - (1/2)gt^2"],
        "takeaway": "Position-at-time questions need component equations, not range formulas.",
    },
    "level_ground_launch_angle_from_range": {
        "goal": "Find launch angle or angles that give a specified level-ground range.",
        "unknown": "launch angle",
        "invariant": "For same-height landing, R = u^2 sin(2theta)/g.",
        "equations": ["sin(2theta)=gR/u^2", "theta = (1/2)sin^-1(gR/u^2)", "paired angle = 90deg - theta"],
        "takeaway": "A valid non-maximum range usually has two complementary launch angles.",
    },
    "height_launch_time_of_flight": {
        "goal": "Find time of flight for launch from a nonzero height.",
        "unknown": "time of flight",
        "invariant": "Ground impact is the positive root of the vertical displacement equation.",
        "equations": ["0 = h + u sin(theta)t - (1/2)gt^2", "T = (u sin(theta)+sqrt(u^2 sin^2(theta)+2gh))/g"],
        "takeaway": "Do not use same-height time of flight when launch height is nonzero.",
    },
    "height_launch_range": {
        "goal": "Find horizontal range for launch from a nonzero height.",
        "unknown": "horizontal range",
        "invariant": "Vertical motion fixes flight time; horizontal motion then gives range.",
        "equations": ["0 = h + u sin(theta)t - (1/2)gt^2", "R = u cos(theta)T"],
        "takeaway": "For launch from height, solve time first; level-ground range formula is wrong.",
    },
    "height_launch_multi_quantity": {
        "goal": "Find all requested projectile quantities for a launch from nonzero height.",
        "unknown": "requested nonzero-height projectile quantities",
        "invariant": "Resolve velocity once; impact time comes from the nonzero-height vertical quadratic, then horizontal motion and impact velocity follow.",
        "equations": [
            "u_x = u cos(theta), u_y = u sin(theta)",
            "0 = h + u_yT - (1/2)gT^2",
            "T = (u_y + sqrt(u_y^2 + 2gh))/g",
            "R = u_xT",
            "H_max = h + max(u_y,0)^2/(2g)",
        ],
        "takeaway": "Do not reuse same-level formulas when launch height is nonzero; the positive root of the height equation controls the rest.",
    },
    "air_drag_conceptual_timing": {
        "goal": "Choose the qualitative effect of air drag.",
        "unknown": "correct qualitative statement",
        "invariant": "Drag opposes velocity and reduces horizontal speed throughout motion.",
        "equations": ["v_x decreases", "pre-peak segment changes", "post-peak horizontal segment takes longer"],
        "takeaway": "Air-drag questions are constraint reasoning problems; do not use ideal projectile symmetry blindly.",
    },
    "max_range_from_height_fixed_speed": {
        "goal": "Find maximum horizontal range from a height with fixed launch speed.",
        "unknown": "maximum range",
        "invariant": "The optimum balances horizontal speed with extra fall time from height.",
        "equations": ["R = u cos(theta) t", "0 = h + u sin(theta)t - (1/2)gt^2", "R_max = (u/g)sqrt(u^2 + 2gh)"],
        "takeaway": "Launch from height has a different maximum-range formula than level-ground projection.",
    },
    "target_reachability_fixed_speed": {
        "goal": "Decide whether a target point is reachable with fixed speed.",
        "unknown": "impossible-target condition",
        "invariant": "A target is reachable only if the trajectory equation has a real launch-angle solution.",
        "equations": ["y = xT - gx^2(1+T^2)/(2u^2)", "substitute u^2 = 2g alpha", "maximize over T"],
        "takeaway": "Reachability is a discriminant/maximum-value question, not a single-angle substitution.",
    },
    "minimum_speed_to_hit_target": {
        "goal": "Find the minimum speed needed to hit a target point.",
        "unknown": "minimum launch speed",
        "invariant": "At minimum speed, the trajectory just becomes tangent to the family of reachable parabolas.",
        "equations": ["u_min = sqrt(g(y + sqrt(x^2 + y^2)))"],
        "takeaway": "For a point target, minimum speed depends on both height and straight-line distance to the target.",
    },
    "target_launch_angle_fixed_speed": {
        "goal": "Find launch angle or angles that hit a target point with fixed speed.",
        "unknown": "launch angle",
        "invariant": "The target must satisfy the projectile trajectory equation for a real tan(theta).",
        "equations": ["y = xT - gx^2(1+T^2)/(2u^2)", "A T^2 - xT + (A+y)=0", "theta = atan(T)"],
        "takeaway": "Target-angle questions are quadratic in tan(theta); there can be two arcs or none.",
    },
    "wall_height_at_distance": {
        "goal": "Find projectile height at a wall.",
        "unknown": "height at wall",
        "invariant": "The wall gives x; substitute that x into the trajectory equation.",
        "equations": ["y = y0 + x tan(theta) - gx^2/(2u^2 cos^2(theta))"],
        "takeaway": "Obstacle questions use the trajectory equation at a fixed horizontal distance.",
    },
    "wall_clearance_condition": {
        "goal": "Decide whether the projectile clears a wall.",
        "unknown": "clearance above wall",
        "invariant": "Clearance equals projectile height at the wall minus wall height.",
        "equations": ["y_wall = y0 + x tan(theta) - gx^2/(2u^2 cos^2(theta))", "clearance = y_wall - H_wall"],
        "takeaway": "Compute height at the obstacle first; only then compare with obstacle height.",
    },
    "inclined_plane_impact_time": {
        "goal": "Find when the projectile strikes an inclined plane.",
        "unknown": "impact time",
        "invariant": "Impact occurs where projectile coordinates satisfy the incline line equation.",
        "equations": ["x = u cos(theta)t", "y = u sin(theta)t - (1/2)gt^2", "y = x tan(alpha)"],
        "takeaway": "Inclined-plane impact time comes from intersecting the trajectory with the plane, not from level-ground flight time.",
    },
    "inclined_plane_same_point_time_ratio": {
        "goal": "Find the time ratio for two projections hitting the same point on an incline.",
        "unknown": "time-of-flight ratio",
        "invariant": "Equal range along an incline creates a paired-angle relation.",
        "equations": ["R = 2u^2 cos(theta) sin(theta-beta)/(g cos^2 beta)", "set ranges equal", "take time ratio"],
        "takeaway": "On an incline, paired angles are relative to the plane geometry, not just complementary to 90deg.",
    },
    "inclined_plane_right_angle_impact_condition": {
        "goal": "Find the condition for right-angle impact with an incline.",
        "unknown": "condition on launch/incline angles",
        "invariant": "Right-angle impact means final velocity has zero along-plane component.",
        "equations": ["resolve along plane", "set v_parallel at impact = 0", "combine with return-to-plane condition"],
        "takeaway": "Perpendicular impact on an incline is easiest in axes parallel and normal to the plane.",
    },
    "staircase_collision": {
        "goal": "Find the first staircase step directly struck by the projectile.",
        "unknown": "step number",
        "invariant": "At each vertical face, horizontal motion fixes time and free fall fixes drop.",
        "equations": ["x_n = n w,  t_n = x_n / v_x", "y_n = (1/2)g t_n^2", "y_n >= n h"],
        "takeaway": "Staircase collision is a first-integer inequality problem.",
    },
    "inclined_plane_max_normal_distance_velocity_component": {
        "goal": "Find the velocity component at maximum normal distance from an incline.",
        "unknown": "normal velocity component",
        "invariant": "At maximum normal displacement, the normal component of velocity is zero.",
        "equations": ["d(normal distance)/dt = v_normal", "at maximum: v_normal = 0"],
        "takeaway": "Extremum of distance means the velocity component in that direction vanishes.",
    },
    "perpendicular_launch_range_on_incline": {
        "goal": "Find range along an incline for launch perpendicular to the plane.",
        "unknown": "range on incline",
        "invariant": "Use axes normal and parallel to the incline.",
        "equations": ["t_return = 2u/(g cos alpha)", "s = (1/2)g sin(alpha)t^2", "s = 2u^2 sin(alpha)/(g cos^2 alpha)"],
        "takeaway": "Perpendicular launch means zero initial along-plane velocity; range comes from down-plane acceleration.",
    },
    "max_range_on_incline": {
        "goal": "Find maximum range along an inclined plane.",
        "unknown": "maximum range on incline",
        "invariant": "Range on an incline is optimized over launch angle relative to the plane.",
        "equations": ["R = 2u^2 cos(theta) sin(theta-alpha)/(g cos^2 alpha)", "optimize theta", "R_max = u^2/(g(1+sin alpha))"],
        "takeaway": "The optimum angle on an incline is not 45deg from horizontal.",
    },
    "horizontal_launch_onto_incline_distance": {
        "goal": "Find distance along an incline hit by a horizontal launch.",
        "unknown": "distance along incline",
        "invariant": "The impact point satisfies both the projectile path and the incline line.",
        "equations": ["x = vt", "y = -(1/2)gt^2", "incline line gives t, then distance = x/cos alpha"],
        "takeaway": "For horizontal launch onto an incline, solve intersection first, then convert to distance along the plane.",
    },
    "two_inclines_perpendicular_launch_impact": {
        "goal": "Find impact speed between two inclined planes with perpendicular launch and impact.",
        "unknown": "impact speed",
        "invariant": "Horizontal velocity is constant between launch and impact.",
        "equations": ["v_x = u cos(launch direction)", "v_x = v_Q cos(impact direction)", "solve for v_Q"],
        "takeaway": "The diagram fixes the two velocity directions; horizontal component conservation gives the speed.",
    },
    "projectile_collides_with_sliding_particle_on_incline": {
        "goal": "Find projection speed for collision with a sliding particle on an incline.",
        "unknown": "projection speed",
        "invariant": "Collision means both particles occupy the same point at the same time.",
        "equations": ["write relative motion along incline", "apply same-time collision condition", "solve for projection speed"],
        "takeaway": "Mixed projectile/incline collision questions are relative-motion problems once geometry is fixed.",
    },
    "two_projectile_collision_time": {
        "goal": "Find when two projectiles collide.",
        "unknown": "collision time",
        "invariant": "If both projectiles have the same gravitational acceleration, relative acceleration is zero.",
        "equations": ["r1 + v1 t = r2 + v2 t", "t = (x2-x1)/(vx1-vx2)", "check y component consistency"],
        "takeaway": "For simultaneous projectile collision under the same gravity, use relative motion and let gravity cancel.",
    },
    "motion_on_smooth_incline_perpendicular_to_slope": {
        "goal": "Find speed on a smooth incline when initial velocity is perpendicular to greatest slope.",
        "unknown": "speed after time",
        "invariant": "Initial perpendicular component and gained down-slope component are perpendicular velocity components.",
        "equations": ["v_down = g sin(alpha)t", "v = sqrt(v_0^2 + v_down^2)"],
        "takeaway": "On a smooth incline, acceleration is down the greatest slope, so combine perpendicular velocity components.",
    },
    "three_dimensional_projectile_line_intersection": {
        "goal": "Find where a projectile intersects a horizontal line in 3D.",
        "unknown": "impact coordinates",
        "invariant": "Vertical motion fixes flight time; horizontal range is then projected along the given line.",
        "equations": ["T = 2u sin(theta)/g", "horizontal range = u cos(theta)T", "resolve range along line direction"],
        "takeaway": "For 3D projectile constraints, solve time vertically first, then distribute horizontal displacement by direction.",
    },
}


def _blueprint_plan(result: EvaluationResult, givens: list[str]) -> EquationPlan:
    spec = PLAN_BLUEPRINTS[result.engine_case]
    template = TEMPLATE_BY_ENGINE_CASE.get(result.engine_case)
    equations = list(spec.get("equations") or [])
    steps: list[EquationStep] = []
    trace_items = result.trace or []
    step_count = max(len(equations), len(trace_items), 1)
    for index in range(step_count):
        equation = str(equations[index]) if index < len(equations) else ""
        trace_index = index - max(step_count - len(trace_items), 0)
        raw_substitution = trace_items[trace_index] if 0 <= trace_index < len(trace_items) else ""
        substitution = _blueprint_substitution(equation, raw_substitution)
        steps.append(
            EquationStep(
                id=f"solve_{index + 1}",
                title=_blueprint_step_title(result.engine_case, index, step_count, equation),
                equation=equation,
                substitution=substitution,
                explanation=_blueprint_step_explanation(result.engine_case, index, step_count, equation, substitution, spec),
                focus_ids=_blueprint_focus_ids(result.engine_case, index, step_count, equation),
            )
        )
    return EquationPlan(
        template_id=template.id if template else "",
        engine_case=result.engine_case,
        goal=str(spec.get("goal") or f"Solve {result.engine_case}."),
        givens=givens,
        unknown=str(spec.get("unknown") or "requested quantity"),
        invariant=str(spec.get("invariant") or (template.solve_strategy if template else "")),
        steps=steps,
        final_answer=result.computed_text or "",
        exam_takeaway=str(spec.get("takeaway") or "Match the requested quantity exactly before choosing equations."),
    )


def _step_title(index: int, step_count: int) -> str:
    if index == 0:
        return "Set up the model"
    if index == step_count - 1:
        return "Get the answer"
    return f"Use relation {index + 1}"


def _blueprint_step_title(engine_case: str, index: int, step_count: int, equation: str) -> str:
    lowered = equation.lower()
    compact = lowered.replace(" ", "")
    if engine_case == "target_launch_angle_fixed_speed":
        if lowered.startswith("y = xt") or "1+t^2" in compact:
            return "Write the target trajectory equation"
        if "a t^2" in lowered or "a+y" in compact:
            return "Solve the tan(theta) quadratic"
        if "atan" in lowered and "theta" in lowered:
            return "Convert roots into launch angles"
    if engine_case == "minimum_speed_to_hit_target" and "u_min" in lowered:
        return "Use the limiting-trajectory relation"
    if engine_case == "motion_on_smooth_incline_perpendicular_to_slope":
        if compact.startswith("v_down=") or compact.startswith("vdown="):
            return "Find down-slope speed gained"
        if lowered.startswith("v = sqrt") or "v_0^2" in lowered:
            return "Combine perpendicular velocity components"
    if engine_case == "monkey_hunter_condition":
        if "aim line" in lowered:
            return "Read the direct aim line"
        if "projectile drop" in lowered:
            return "Track the projectile drop"
        if "monkey drop" in lowered:
            return "Track the monkey drop"
        if "arrival time" in lowered:
            return "Check arrival before the monkey lands"
    if _is_indexed_face_time_equation(lowered):
        return "Set up the nth step face"
    if _is_indexed_drop_equation(lowered):
        return "Find the drop at that face"
    if _is_indexed_hit_inequality(lowered):
        return "Pick the first direct-hit step"
    if "u_x" in lowered and "u_y" in lowered:
        return "Resolve the launch velocity"
    if lowered.startswith("u_y"):
        return "Resolve the vertical component"
    if lowered.startswith("v_y"):
        return "Write vertical velocity"
    if lowered.startswith("0 = u_y") and ("t^2" in lowered or " t" in lowered):
        return "Apply the landing condition"
    if lowered.startswith("0 = u_y"):
        return "Apply the highest-point condition"
    if "t_peak" in lowered:
        return "Find time to peak"
    if lowered.startswith("y(t)") or lowered.startswith("y ="):
        return "Write vertical position"
    if lowered.startswith("0 = t") or "t(" in lowered:
        return "Factor the landing condition"
    if "2u_y/g" in lowered:
        return "Choose the nonzero root"
    if "2u sin" in lowered:
        return "State the final formula"
    if "0 =" in lowered and "h +" in lowered and "gt^2" in lowered:
        return "Apply the ground-impact condition"
    if "0 =" in lowered and "gT^2".lower() in lowered:
        return "Use zero vertical displacement"
    if compact.startswith("t_return=") or compact.startswith("treturn="):
        return "Find when the projectile returns to the incline"
    if compact.startswith("s=(1/2)gsin") or compact.startswith("s=0.5gsin"):
        return "Find displacement along the incline"
    if compact.startswith("s=2u^2") and "cos^2" in compact:
        return "Combine the return time with along-plane motion"
    if lowered.startswith("t") or " t =" in lowered or "flight time" in lowered:
        return "Find the flight time"
    if "r =" in lowered and " t" in lowered:
        return "Convert time into range"
    if index == 0:
        return "Choose the controlling relation"
    if index == step_count - 1:
        return "Compute the requested answer"
    if "component" in lowered or "cos" in lowered or "sin" in lowered:
        return "Resolve the motion into useful parts"
    if "set" in lowered or "=0" in lowered:
        return "Apply the event condition"
    return "Connect the equation to the diagram"


def _blueprint_step_explanation(engine_case: str, index: int, step_count: int, equation: str, substitution: str, spec: dict[str, object]) -> str:
    lowered = equation.lower()
    compact = lowered.replace(" ", "")
    if engine_case == "target_launch_angle_fixed_speed":
        if lowered.startswith("y = xt") or "1+t^2" in compact:
            return "Use the trajectory equation at the target point and set T = tan(theta), so the unknown angle becomes an algebraic variable."
        if "a t^2" in lowered or "a+y" in compact:
            return "This quadratic gives the admissible values of T = tan(theta). Two real roots mean two possible launch arcs."
        if "atan" in lowered and "theta" in lowered:
            return "Convert each real T root back to theta. Report both launch angles that pass through the target."
    if engine_case == "minimum_speed_to_hit_target" and "u_min" in lowered:
        return "At minimum speed, the target lies on the limiting reachable parabola. Substitute target x and y into the minimum-speed formula."
    if engine_case == "motion_on_smooth_incline_perpendicular_to_slope":
        if compact.startswith("v_down=") or compact.startswith("vdown="):
            return "Gravity accelerates the particle only down the line of greatest slope, so the gained component is g sin(alpha)t."
        if lowered.startswith("v = sqrt") or "v_0^2" in lowered:
            return "The initial sideways speed and gained down-slope speed are perpendicular, so the final speed is their Pythagorean resultant."
    if engine_case == "monkey_hunter_condition":
        if "aim line" in lowered:
            return "The gun is initially aimed along the straight line from the hunter to the monkey's starting position."
        if "projectile drop" in lowered:
            return "After firing, the projectile falls below the original aim line by exactly (1/2)gt^2."
        if "monkey drop" in lowered:
            return "The monkey starts from rest vertically, so in the same time it also drops by (1/2)gt^2."
        if "arrival time" in lowered:
            return "Because the two drops match, the only remaining condition is whether the projectile arrives before the monkey reaches the ground."
    if _is_indexed_face_time_equation(lowered):
        return "Let n be the step number. The nth vertical face is n step-widths away, so horizontal motion gives the time to reach that face."
    if _is_indexed_drop_equation(lowered):
        return "During that same time, the marble falls vertically from rest under gravity. This gives the drop by the time it reaches the nth face."
    if _is_indexed_hit_inequality(lowered):
        return "The nth step is n step-heights below the top. A direct strike starts when the vertical drop reaches at least that much."
    if "u_x" in lowered and "u_y" in lowered:
        return "Resolve the launch velocity into horizontal and vertical components. Horizontal motion decides range, while vertical motion decides flight time."
    if lowered.startswith("u_y"):
        return "Only the vertical component controls upward slowing, so use u_y = u sin(theta)."
    if lowered.startswith("v_y"):
        return "Gravity reduces vertical velocity linearly with time: v_y = u_y - gt."
    if lowered.startswith("0 = u_y") and ("t^2" in lowered or " t" in lowered):
        return "At landing, vertical displacement is zero again. Use the nonzero root for total flight time."
    if lowered.startswith("0 = u_y"):
        return "At the highest point, vertical velocity is zero. Set v_y = 0 to find the time."
    if "t_peak" in lowered:
        return "Solve for t_peak and substitute the vertical component. For a straight-up throw, theta = 90deg."
    if lowered.startswith("y(t)") or lowered.startswith("y ="):
        return "Measure vertical position from the launch level. The upward term is u_y t and the downward gravitational term is (1/2)gt^2."
    if lowered.startswith("0 = t") or "t(" in lowered:
        return "At landing the vertical position is back to zero. Factoring separates the launch instant from the later landing instant."
    if "2u_y/g" in lowered:
        return "The root t = 0 is the launch instant. The physical flight time is the later root, T = 2u_y/g."
    if "2u sin" in lowered:
        return "Replace u_y with u sin(theta). This gives the symbolic time-of-flight formula for same-height projectile motion."
    if "0 =" in lowered and "h +" in lowered and "gt^2" in lowered:
        return "At the ground, y = 0 while the launch point is h above ground. Use y = h + u sin(theta)t - (1/2)gt^2 and set it equal to zero."
    if "0 =" in lowered and "gt^2" in lowered:
        return "Launch and landing are on the same horizontal level, so the net vertical displacement is zero. Use the vertical displacement equation at landing."
    if "sqrt" in lowered and "2gh" in lowered:
        return "Solve the quadratic in t and keep the positive root, because negative time is not physically valid."
    if compact.startswith("t_return=") or compact.startswith("treturn="):
        return "Use the axis normal to the incline. The projectile starts away from the plane with speed u and comes back because gravity has a normal component g cos(alpha)."
    if compact.startswith("s=(1/2)gsin") or compact.startswith("s=0.5gsin"):
        return "Now use the axis along the incline. There is no initial along-plane velocity, so the along-plane distance is produced only by g sin(alpha)."
    if compact.startswith("s=2u^2") and "cos^2" in compact:
        return "Substitute the normal-return time into the along-plane displacement equation to get the range measured on the incline."
    if lowered.startswith("t") or " t =" in lowered or "flight time" in lowered:
        return "Factor the previous equation: T(u_y - gT/2)=0. The nonzero root gives the total flight time."
    if "r =" in lowered and " t" in lowered:
        return "Horizontal acceleration is zero, so horizontal range equals constant horizontal velocity multiplied by flight time."
    if index == 0:
        return str(spec.get("invariant") or "Start from the physical condition that stays true for this problem.")
    if index == step_count - 1:
        return "Now substitute the known values and report only the requested quantity."
    if equation:
        return f"This equation is used because it links the highlighted geometry to {spec.get('unknown') or 'the unknown'}."
    return substitution or "Use the previous relation to move one step closer to the requested quantity."


def _blueprint_focus_ids(engine_case: str, index: int, step_count: int, equation: str) -> list[str]:
    lowered = equation.lower()
    case = engine_case.lower()
    if case == "monkey_hunter_condition":
        if index == step_count - 1:
            return ["actor:hunter", "actor:monkey", "point:hit", "event:hit", "answer"]
        if "aim line" in lowered:
            return ["actor:hunter", "actor:monkey", "line:aim", "point:monkey_start"]
        if "projectile drop" in lowered:
            return ["actor:projectile", "trajectory:path", "line:aim", "quantity:drop_projectile"]
        if "monkey drop" in lowered:
            return ["actor:monkey", "trajectory:monkey_drop", "quantity:drop_monkey"]
        return ["actor:hunter", "actor:monkey", "trajectory:path", "trajectory:monkey_drop"]
    if "staircase" in case:
        if _is_indexed_hit_inequality(lowered) or index == step_count - 1:
            return ["staircase", "vertical_faces", "nth_step", "point:impact", "answer"]
        if _is_indexed_drop_equation(lowered):
            return ["staircase", "vertical_faces", "trajectory:path", "quantity:drop"]
        return ["staircase", "vertical_faces", "nth_step", "trajectory:path"]
    incline_range_cases = {
        "perpendicular_launch_range_on_incline",
        "max_range_on_incline",
        "horizontal_launch_onto_incline_distance",
    }
    if "time_to_peak" in case:
        if index == step_count - 1:
            return ["quantity:t_peak", "event:apex", "quantity:H", "trajectory:path"]
        if any(token in lowered for token in ("u_y", "v_y", "t_peak", "highest")):
            return ["vector:u", "vector:vy", "quantity:uy", "event:apex", "trajectory:path"]
    if index == step_count - 1:
        return ["answer", "quantity:R", "quantity:T", "quantity:H", "point:landing", "point:impact", "point:collision"]
    if "wall" in lowered or "clearance" in lowered or "wall" in case:
        return ["obstacle:wall", "point:wall_top", "trajectory:path"]
    if "target" in lowered or "target" in case:
        return ["point:target", "trajectory:path"]
    if engine_case in incline_range_cases and any(token in lowered for token in ("s =", "r =", "range", "distance")):
        return ["quantity:R", "point:impact", "surface:inclined_plane", "trajectory:path"]
    if "incline" in lowered or "plane" in lowered or "incline" in case:
        return ["surface:inclined_plane", "incline:tangent_axis", "incline:normal_axis", "trajectory:path"]
    if "u_x" in lowered and "u_y" in lowered:
        return ["vector:u", "vector:vx", "vector:vy", "quantity:ux", "quantity:uy"]
    if "0 =" in lowered and "gt^2" in lowered:
        return ["point:launch", "point:landing", "quantity:delta_y", "trajectory:path"]
    if lowered.startswith("t") or " t =" in lowered:
        return ["quantity:T", "point:launch", "point:landing", "event:apex", "trajectory:path"]
    if "r =" in lowered or any(token in lowered for token in ("range", " r", "distance")):
        return ["quantity:R", "point:landing", "trajectory:path"]
    if any(token in lowered for token in ("u_x", "u cos", "v_x", "horizontal", "component")):
        return ["vector:u", "vector:vx", "quantity:ux", "trajectory:path"]
    if any(token in lowered for token in ("u_y", "u sin", "v_y", "vertical")):
        return ["vector:u", "vector:vy", "quantity:uy", "event:apex", "trajectory:path"]
    if any(token in lowered for token in ("h =", "height", "apex", "t_peak")):
        return ["event:apex", "quantity:H", "vector:vy", "trajectory:path"]
    if any(token in lowered for token in ("t_", "time", " t", "sqrt(2h", "sqrt(2H".lower())):
        return ["quantity:T", "event:landing", "event:impact", "event:collision", "trajectory:path"]
    if any(token in lowered for token in (" x",)):
        return ["quantity:R", "point:landing", "point:impact", "trajectory:path"]
    return ["vector:u", "quantity:u", "quantity:theta", "trajectory:path"]


def _is_indexed_face_time_equation(lowered_equation: str) -> bool:
    return "x_n" in lowered_equation and "n w" in lowered_equation and "t_n" in lowered_equation


def _is_indexed_drop_equation(lowered_equation: str) -> bool:
    return "y_n" in lowered_equation and "t_n^2" in lowered_equation


def _is_indexed_hit_inequality(lowered_equation: str) -> bool:
    return "y_n" in lowered_equation and "n h" in lowered_equation and (">=" in lowered_equation or ">" in lowered_equation)


def _blueprint_substitution(equation: str, substitution: str) -> str:
    cleaned = substitution.strip()
    if not cleaned:
        return ""
    if equation and cleaned.lower().startswith(("for ", "since ", "because ")):
        return ""
    return cleaned
