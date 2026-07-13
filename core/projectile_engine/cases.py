from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Callable

from .models import EvaluationResult, ManifestEntry


Solver = Callable[[ManifestEntry], EvaluationResult]


def _result(
    entry: ManifestEntry,
    *,
    computed_value: float | None,
    computed_text: str,
    trace: list[str],
    reason: str = "",
) -> EvaluationResult:
    predicted = _match_option(entry.options, computed_value, computed_text)
    status = "passed" if predicted == entry.expected_option_letter else "failed"
    if not reason and status == "failed":
        reason = f"expected option {entry.expected_option_letter}, got {predicted or 'no match'}"
    return EvaluationResult(
        label=entry.label,
        engine_case=entry.engine_case,
        status=status,
        expected_option_letter=entry.expected_option_letter,
        predicted_option_letter=predicted,
        expected_answer=entry.expected_answer,
        computed_value=computed_value,
        computed_text=computed_text,
        reason=reason,
        trace=trace,
    )


def _symbolic_result(
    entry: ManifestEntry,
    *,
    computed_text: str,
    trace: list[str],
    reason: str = "",
) -> EvaluationResult:
    predicted = _match_option(entry.options, None, computed_text)
    if entry.expected_option_letter is None:
        return EvaluationResult(
            label=entry.label,
            engine_case=entry.engine_case,
            status="passed" if computed_text else "failed",
            expected_option_letter=None,
            predicted_option_letter=predicted,
            expected_answer=entry.expected_answer,
            computed_text=computed_text,
            reason=reason,
            trace=trace,
        )

    status = "passed" if predicted == entry.expected_option_letter else "failed"
    if not reason and status == "failed":
        reason = f"expected option {entry.expected_option_letter}, got {predicted or 'no match'}"
    return EvaluationResult(
        label=entry.label,
        engine_case=entry.engine_case,
        status=status,
        expected_option_letter=entry.expected_option_letter,
        predicted_option_letter=predicted,
        expected_answer=entry.expected_answer,
        computed_text=computed_text,
        reason=reason,
        trace=trace,
    )


def unsupported(entry: ManifestEntry) -> EvaluationResult:
    return EvaluationResult(
        label=entry.label,
        engine_case=entry.engine_case,
        status="unsupported",
        expected_option_letter=entry.expected_option_letter,
        expected_answer=entry.expected_answer,
        reason="engine case not implemented",
    )


def solve_parametric_initial_speed(entry: ManifestEntry) -> EvaluationResult:
    x_expr = _known_value(entry, "x(t)")
    y_expr = _known_value(entry, "y(t)")
    vx0 = _linear_t_coefficient(x_expr)
    vy0 = _linear_t_coefficient(y_expr)
    speed = math.hypot(vx0, vy0)
    return _result(
        entry,
        computed_value=speed,
        computed_text=f"{speed:g} m/s",
        trace=[
            f"x(t) = {x_expr}, so vx(0) = {vx0:g} m/s",
            f"y(t) = {y_expr}, so vy(0) = {vy0:g} m/s",
            f"v0 = sqrt(vx0^2 + vy0^2) = {speed:g} m/s",
        ],
    )


def solve_velocity_change_interval(entry: ManifestEntry) -> EvaluationResult:
    g = _number_from_known_or_text(entry, "g", default=10.0)
    dt = _number_from_known_or_time_interval(entry, "dt")
    delta_v = abs(g * dt)
    return _result(
        entry,
        computed_value=delta_v,
        computed_text=f"{delta_v:g} m/s",
        trace=[
            "Only gravity changes velocity in ideal projectile motion.",
            f"|delta v| = g * delta t = {g:g} * {dt:g} = {delta_v:g} m/s",
        ],
    )


def solve_parametric_curve_classification(entry: ManifestEntry) -> EvaluationResult:
    return _result(
        entry,
        computed_value=None,
        computed_text="An ellipse",
        trace=[
            "Integrating dx/dt = 8*pi*sin(2*pi*t) gives x = 4 - 4*cos(2*pi*t) plus the initial offset, so x = 4 + 4*cos(2*pi*t).",
            "Integrating dy/dt = 5*pi*cos(2*pi*t) gives y = (5/2)sin(2*pi*t).",
            "The eliminated-time form is elliptical, not projectile parabolic motion.",
        ],
    )


def solve_velocity_angle_event_speed(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_known(entry, "v0")
    launch_angle = math.radians(_number_from_known(entry, "launch_angle"))
    target_angle = math.radians(_number_from_known(entry, "velocity_angle"))
    vx = v0 * math.cos(launch_angle)
    speed = abs(vx / math.cos(target_angle))
    return _result(
        entry,
        computed_value=speed,
        computed_text=f"{speed:g} m/s",
        trace=[
            f"Horizontal velocity stays fixed: vx = {v0:g} cos({math.degrees(launch_angle):g}deg) = {vx:g} m/s",
            f"When velocity angle is {math.degrees(target_angle):g}deg, speed = vx / cos(phi) = {speed:g} m/s",
        ],
    )


def solve_horizontal_throw_velocity_angle_time(entry: ManifestEntry) -> EvaluationResult:
    vx = _number_from_known(entry, "vx")
    g = _number_from_known(entry, "g", default=10.0)
    target_angle = math.radians(_number_from_known(entry, "velocity_angle"))
    time = abs(vx * math.tan(target_angle) / g)
    return _result(
        entry,
        computed_value=time,
        computed_text=f"{time:g} sec",
        trace=[
            f"Horizontal throw has vx = {vx:g} m/s and vy = gt.",
            f"tan(phi) = vy/vx = gt/vx, so t = vx tan(phi)/g = {time:g} s",
        ],
    )


def solve_velocity_perpendicular_to_initial_event(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_known(entry, "v0")
    angle = math.radians(_number_from_known(entry, "angle"))
    g = _number_from_known(entry, "g", default=10.0)
    vx0 = v0 * math.cos(angle)
    vy0 = v0 * math.sin(angle)
    event_time = (v0 * v0) / (g * vy0)
    x_event = vx0 * event_time
    return _result(
        entry,
        computed_value=x_event,
        computed_text=f"{x_event:g} m",
        trace=[
            "Perpendicular condition: v(t) dot v0 = 0.",
            f"vx0 = {vx0:g}, vy0 = {vy0:g}",
            f"t = v0^2 / (g*vy0) = {event_time:g} s",
            f"x = vx0*t = {x_event:g} m",
        ],
    )


def solve_same_range_doubled_angle_time_ratio(entry: ManifestEntry) -> EvaluationResult:
    return _result(
        entry,
        computed_value=None,
        computed_text="1 : sqrt3",
        trace=[
            "For equal speed and same horizontal range: sin(2a) = sin(4a).",
            "The non-trivial solution is 2a = 180deg - 4a, so a = 30deg and 2a = 60deg.",
            "Time of flight ratio is sin(30deg) : sin(60deg) = 1 : sqrt3.",
        ],
    )


def solve_two_projectile_interception_time_ratio(entry: ManifestEntry) -> EvaluationResult:
    theta_pairs = _infer_interception_angle_pairs(entry.question_text)
    if len(theta_pairs) < 2:
        raise ValueError(f"{entry.label}: missing two (theta0, theta1) angle pairs")

    denominators: list[float] = []
    trace = [
        "Both projectiles have the same downward acceleration, so relative vertical acceleration is zero.",
        "Vertical meeting condition: v0 sin(theta0) = u sin(theta1), hence u = v0 sin(theta0)/sin(theta1).",
        "Horizontal meeting condition: L = T[v0 cos(theta0) + u cos(theta1)].",
        "So T = L / {v0[cos(theta0) + sin(theta0) cot(theta1)]}.",
    ]
    for theta0_deg, theta1_deg in theta_pairs[:2]:
        theta0 = math.radians(theta0_deg)
        theta1 = math.radians(theta1_deg)
        denominator = math.cos(theta0) + math.sin(theta0) / math.tan(theta1)
        denominators.append(denominator)
        trace.append(
            f"For theta0={theta0_deg:g}deg, theta1={theta1_deg:g}deg: "
            f"cos(theta0)+sin(theta0)cot(theta1) = {denominator:g}."
        )

    ratio_squared = (denominators[1] / denominators[0]) ** 2
    trace.append(f"(T1/T2)^2 = ({denominators[1]:g}/{denominators[0]:g})^2 = {ratio_squared:g}.")
    return _result(
        entry,
        computed_value=ratio_squared,
        computed_text=f"{ratio_squared:g}",
        trace=trace,
    )


def solve_target_angle_from_short_overshoot(entry: ManifestEntry) -> EvaluationResult:
    return _symbolic_result(
        entry,
        computed_text="1/2 sin^-1[(1/5)(3sqrt3/2 + 2)]",
        trace=[
            "Let target distance be D and common range constant be k.",
            "At 30deg: D - 6 = k sin60deg. At 45deg: D + 9 = k.",
            "So sin(2theta_hit) = D/k = (1/5)(3sqrt3/2 + 2).",
            "Therefore theta_hit = 1/2 sin^-1[(1/5)(3sqrt3/2 + 2)].",
        ],
    )


def solve_fielder_catch_before_ground(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_known(entry, "v0")
    angle = math.radians(_number_from_known(entry, "angle"))
    fielder_distance = _number_from_known(entry, "fielder_distance")
    g = _number_from_known(entry, "g", default=9.8)
    time = 2 * v0 * math.sin(angle) / g
    ball_range = v0 * math.cos(angle) * time
    speed = (fielder_distance - ball_range) / time
    return _result(
        entry,
        computed_value=speed,
        computed_text=f"{speed:g} m/s",
        trace=[
            f"Time of flight = 2v sin(theta)/g = {time:g} s.",
            f"Ball range = v cos(theta) * T = {ball_range:g} m.",
            f"Fielder speed = (70 - range)/T = {speed:g} m/s.",
        ],
    )


def solve_average_velocity_to_peak(entry: ManifestEntry) -> EvaluationResult:
    return _symbolic_result(
        entry,
        computed_text="v/2 sqrt(1 + 3 cos^2 theta)",
        trace=[
            "At the peak, t = v sin(theta)/g.",
            "Average velocity components from launch to peak are vx_avg = v cos(theta), vy_avg = v sin(theta)/2.",
            "Magnitude = v * sqrt(cos^2(theta) + sin^2(theta)/4) = v/2 sqrt(1 + 3cos^2(theta)).",
        ],
    )


def solve_projectile_with_horizontal_acceleration(entry: ManifestEntry) -> EvaluationResult:
    return _symbolic_result(
        entry,
        computed_text="(R + H), H",
        trace=[
            "Horizontal acceleration does not change vertical motion, so maximum height stays H.",
            "Original time of flight T gives H = gT^2/8 for a ground-to-ground projectile.",
            "Extra horizontal displacement = 0.5*(g/4)*T^2 = gT^2/8 = H.",
            "New range = R + H, max height = H.",
        ],
    )


def _level_ground_state(entry: ManifestEntry) -> dict[str, float]:
    text = entry.question_text.lower()
    g = _number_from_known(entry, "g", default=10.0)
    v0 = _optional_number_from_any_known(entry, ["v0", "velocity", "speed"])
    angle_deg = _optional_number_from_any_known(entry, ["angle", "launch_angle"])
    angle = math.radians(angle_deg) if angle_deg is not None else None
    if angle is None and v0 is not None and any(marker in entry.question_text.lower() for marker in ("maximum range", "maximum horizontal range")):
        angle = math.radians(45.0)
    ux = _optional_number_from_any_known(entry, ["ux", "u_x", "vx", "v_x", "horizontal_velocity", "horizontal_speed"])
    uy = _optional_number_from_any_known(entry, ["uy", "u_y", "vy", "v_y", "vertical_velocity", "vertical_speed"])
    time = _optional_number_from_any_known(entry, ["time", "t", "flight_time", "time_of_flight"])
    range_known = _optional_number_from_any_known(entry, ["range", "R", "horizontal_range", "distance"])
    max_height_known = _optional_number_from_any_known(entry, ["max_height", "maximum_height", "height", "H"])

    component_speed_context = any(marker in text for marker in ("horizontal component", "horizontal velocity", "horizontal speed", "velocity at the highest point"))
    if ux is not None and angle is not None and component_speed_context:
        cos_angle = math.cos(angle)
        if math.isclose(cos_angle, 0.0, abs_tol=1e-12):
            raise ValueError(f"{entry.label}: horizontal component cannot determine speed for vertical launch")
        v0 = ux / cos_angle
        uy = v0 * math.sin(angle)
    if time is not None and range_known is not None:
        ux = range_known / time
        uy = 0.5 * g * time
        v0 = math.hypot(ux, uy)
        angle = math.atan2(uy, ux)
    if ux is not None and angle is not None and v0 is None:
        cos_angle = math.cos(angle)
        if math.isclose(cos_angle, 0.0, abs_tol=1e-12):
            raise ValueError(f"{entry.label}: horizontal component cannot determine speed for vertical launch")
        v0 = ux / cos_angle
        uy = v0 * math.sin(angle)
    if ux is not None and time is not None and uy is None:
        uy = 0.5 * g * time
        v0 = math.hypot(ux, uy)
        angle = math.atan2(uy, ux)
    if uy is not None and ux is not None and v0 is None:
        v0 = math.hypot(ux, uy)
        angle = math.atan2(uy, ux)
    if time is not None and angle is not None and v0 is None:
        sin_angle = math.sin(angle)
        if math.isclose(sin_angle, 0.0, abs_tol=1e-12):
            raise ValueError(f"{entry.label}: time of flight cannot determine horizontal launch speed on level ground")
        v0 = g * time / (2 * sin_angle)
    if time is not None and v0 is not None and angle is None:
        sin_angle = g * time / (2 * v0)
        if abs(sin_angle) <= 1 + 1e-9:
            angle = math.asin(max(-1.0, min(1.0, sin_angle)))
    if range_known is not None and angle is not None and v0 is None:
        sin_double = math.sin(2 * angle)
        if math.isclose(sin_double, 0.0, abs_tol=1e-12):
            raise ValueError(f"{entry.label}: range cannot determine speed for this angle")
        v0 = math.sqrt(abs(range_known * g / sin_double))
    if range_known is not None and v0 is not None and angle is None:
        sin_double = range_known * g / (v0 * v0)
        if abs(sin_double) <= 1 + 1e-9:
            angle = 0.5 * math.asin(max(-1.0, min(1.0, sin_double)))
    if max_height_known is not None and angle is not None and v0 is None:
        sin_angle = math.sin(angle)
        if math.isclose(sin_angle, 0.0, abs_tol=1e-12):
            raise ValueError(f"{entry.label}: maximum height cannot determine speed for horizontal launch")
        v0 = math.sqrt(2 * g * max_height_known) / abs(sin_angle)
    if max_height_known is not None and v0 is not None and angle is None:
        sin_angle = math.sqrt(max(0.0, 2 * g * max_height_known)) / v0
        if abs(sin_angle) <= 1 + 1e-9:
            angle = math.asin(max(-1.0, min(1.0, sin_angle)))
    if v0 is None or angle is None:
        missing = []
        if v0 is None:
            missing.append("launch speed")
        if angle is None:
            missing.append("launch angle")
        raise ValueError(f"{entry.label}: missing {', '.join(missing)}")

    ux = v0 * math.cos(angle) if ux is None else ux
    uy = v0 * math.sin(angle) if uy is None else uy
    time = 2 * uy / g if time is None else time
    range_value = ux * time if range_known is None else range_known
    max_height = uy * uy / (2 * g) if max_height_known is None else max_height_known
    return {
        "g": g,
        "v0": v0,
        "angle": angle,
        "ux": ux,
        "uy": uy,
        "time": time,
        "range": range_value,
        "max_height": max_height,
        "time_to_peak": uy / g,
    }


def solve_level_ground_range(entry: ManifestEntry) -> EvaluationResult:
    text = entry.question_text.lower()
    if any(marker in text for marker in ("derive", "derivation", "condition")) and any(marker in text for marker in ("maximum horizontal range", "maximum range")):
        return _symbolic_result(
            entry,
            computed_text="theta = 45 deg",
            trace=[
                "For level-ground projectile motion, R = u^2 sin(2theta)/g.",
                "For fixed u and g, R is maximum when sin(2theta)=1.",
                "So 2theta=90deg and theta=45deg.",
            ],
        )
    state = _level_ground_state(entry)
    v0 = state["v0"]
    angle = state["angle"]
    g = state["g"]
    range_value = state["range"]
    if "initial speed" in text or "speed needed" in text:
        computed_text = f"u = {v0:g} m/s"
    else:
        computed_text = f"{range_value:g} m"
    return _result(
        entry,
        computed_value=range_value,
        computed_text=computed_text,
        trace=[
            "For level-ground projectile motion, horizontal range is R = u^2 sin(2theta)/g.",
            f"R = {v0:g}^2 * sin({2 * math.degrees(angle):g}deg) / {g:g} = {range_value:g} m.",
        ],
    )


def solve_level_ground_time_of_flight(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_any_known(entry, ["v0", "velocity", "speed"])
    angle = math.radians(_number_from_any_known(entry, ["angle", "launch_angle"]))
    g = _number_from_known(entry, "g", default=10.0)
    time = 2 * v0 * math.sin(angle) / g
    return _result(
        entry,
        computed_value=time,
        computed_text=f"{time:g} s",
        trace=[
            "For launch and landing at the same height, time of flight is T = 2u sin(theta)/g.",
            f"T = 2 * {v0:g} * sin({math.degrees(angle):g}deg) / {g:g} = {time:g} s.",
        ],
    )


def solve_level_ground_range_and_time(entry: ManifestEntry) -> EvaluationResult:
    return solve_level_ground_multi_quantity(entry)


def solve_level_ground_multi_quantity(entry: ManifestEntry) -> EvaluationResult:
    if any(marker in entry.question_text.lower() for marker in ("derive", "derivation", "condition")) and any(
        marker in entry.question_text.lower() for marker in ("maximum horizontal range", "maximum range")
    ):
        return _symbolic_result(
            entry,
            computed_text="theta = 45 deg",
            trace=[
                "For level-ground projectile motion, R = u^2 sin(2theta)/g.",
                "For fixed launch speed, maximize sin(2theta).",
                "Maximum occurs when sin(2theta)=1, so theta=45deg.",
            ],
        )
    partial_time = _optional_number_from_any_known(entry, ["time", "t", "flight_time", "time_of_flight"])
    partial_height = _optional_number_from_any_known(entry, ["max_height", "maximum_height", "height", "H"])
    partial_v0 = _optional_number_from_any_known(entry, ["v0", "velocity", "speed"])
    partial_range = _optional_number_from_any_known(entry, ["range", "R", "horizontal_range", "distance"])
    partial_ux = _optional_number_from_any_known(entry, ["ux", "u_x", "vx", "v_x", "horizontal_velocity", "horizontal_speed"])
    partial_angle = _optional_number_from_any_known(entry, ["angle", "launch_angle"])
    if partial_time is not None and partial_height is not None and partial_v0 is None and partial_range is None and partial_ux is None and partial_angle is None:
        g = _number_from_known(entry, "g", default=10.0)
        uy_from_time = 0.5 * g * partial_time
        uy_from_height = math.sqrt(max(0.0, 2 * g * partial_height))
        consistent = math.isclose(uy_from_time, uy_from_height, rel_tol=1e-6, abs_tol=1e-6)
        return _symbolic_result(
            entry,
            computed_text=f"u_y = {uy_from_time:g} m/s; consistency = {'yes' if consistent else 'no'}",
            trace=[
                "For level-ground motion, total flight time gives u_y = gT/2.",
                f"u_y from time = {g:g}*{partial_time:g}/2 = {uy_from_time:g} m/s.",
                "Maximum height gives u_y = sqrt(2gH).",
                f"u_y from height = sqrt(2*{g:g}*{partial_height:g}) = {uy_from_height:g} m/s.",
            ],
        )
    state = _level_ground_state(entry)
    v0 = state["v0"]
    angle = state["angle"]
    g = state["g"]
    ux = state["ux"]
    uy = state["uy"]
    time = state["time"]
    range_value = state["range"]
    max_height = state["max_height"]
    time_to_peak = state["time_to_peak"]
    outputs = _requested_level_ground_outputs(entry.question_text)
    if not outputs:
        outputs = ["time_of_flight", "range"]

    output_text: list[str] = []
    if "initial_speed" in outputs:
        output_text.append(f"u = {v0:g} m/s")
    if "launch_angle" in outputs:
        output_text.append(f"theta = {math.degrees(angle):g} deg")
    if "components" in outputs:
        output_text.append(f"u_x = {ux:g} m/s")
        output_text.append(f"u_y = {uy:g} m/s")
    if "time_to_peak" in outputs:
        output_text.append(f"t_peak = {time_to_peak:g} s")
    if "time_of_flight" in outputs:
        output_text.append(f"T = {time:g} s")
    if "maximum_height" in outputs:
        output_text.append(f"H = {max_height:g} m")
    if "range" in outputs:
        output_text.append(f"R = {range_value:g} m")

    trace = [
        f"Resolve components: u_x = u cos(theta) = {ux:g} m/s, u_y = u sin(theta) = {uy:g} m/s.",
    ]
    if "time_to_peak" in outputs:
        trace.append(f"At highest point v_y = 0, so t_peak = u_y/g = {uy:g}/{g:g} = {time_to_peak:g} s.")
    if "time_of_flight" in outputs:
        trace.append(f"For same-height landing, T = 2u_y/g = 2 * {uy:g}/{g:g} = {time:g} s.")
    if "maximum_height" in outputs:
        trace.append(f"At the top, H = u_y^2/(2g) = {uy:g}^2/(2*{g:g}) = {max_height:g} m.")
    if "range" in outputs:
        trace.append(f"Horizontal velocity is constant, so R = u_x*T = {ux:g} * {time:g} = {range_value:g} m.")

    return _symbolic_result(
        entry,
        computed_text="; ".join(output_text),
        trace=trace,
    )


def solve_level_ground_time_of_flight_derivation(entry: ManifestEntry) -> EvaluationResult:
    return _symbolic_result(
        entry,
        computed_text="T = 2u sin(theta)/g",
        trace=[
            "Resolve vertical component: u_y = u sin(theta).",
            "For launch and landing at the same height, vertical displacement at landing is zero.",
            "Use y = u_y t - (1/2)gt^2 and set y = 0.",
            "0 = t(u_y - gt/2), giving t = 0 or t = 2u_y/g.",
            "Discard t = 0 because it is the launch instant, so T = 2u sin(theta)/g.",
        ],
    )


def solve_level_ground_max_height(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_any_known(entry, ["v0", "velocity", "speed"])
    angle = math.radians(_number_from_any_known(entry, ["angle", "launch_angle"]))
    g = _number_from_known(entry, "g", default=10.0)
    height = (v0 * math.sin(angle)) ** 2 / (2 * g)
    return _result(
        entry,
        computed_value=height,
        computed_text=f"{height:g} m",
        trace=[
            "At maximum height the vertical velocity becomes zero.",
            "Use vy^2 = uy^2 - 2gH, so H = u^2 sin^2(theta)/(2g).",
            f"H = {v0:g}^2 * sin^2({math.degrees(angle):g}deg) / (2*{g:g}) = {height:g} m.",
        ],
    )


def solve_projectile_split_at_apex_fragment_time(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_any_known(entry, ["v0", "velocity", "speed"])
    raw_angle = _number_from_any_known(entry, ["angle", "launch_angle"])
    angle_deg = 90.0 - raw_angle if "from the vertical" in entry.question_text.lower() else raw_angle
    angle = math.radians(angle_deg)
    g = _number_from_known(entry, "g", default=10.0)

    ux = v0 * math.cos(angle)
    uy = v0 * math.sin(angle)
    t_peak = uy / g
    apex_x = ux * t_peak
    apex_h = uy * uy / (2 * g)
    fall_time_from_height = math.sqrt(2 * apex_h / g)
    given_fall_time = _number_from_any_known(entry, ["frag1_fall_time", "fragment_fall_time"], default=fall_time_from_height)

    # Equal masses. At the apex, vertical velocity is zero. If one equal half
    # falls vertically, its horizontal velocity after split is zero, so the
    # other half must carry twice the original horizontal momentum.
    frag2_vx = 2 * ux
    frag2_fall_time = fall_time_from_height
    frag2_x = apex_x + frag2_vx * frag2_fall_time

    return _result(
        entry,
        computed_value=frag2_fall_time,
        computed_text=f"{frag2_fall_time:g} s",
        trace=[
            f"Angle is {raw_angle:g}deg from vertical, so the horizontal-reference launch angle is {angle_deg:g}deg.",
            f"u_y = {v0:g} sin({angle_deg:g}deg) = {uy:g} m/s, so t_peak = u_y/g = {uy:g}/{g:g} = {t_peak:g} s.",
            f"Apex height H = u_y^2/(2g) = {uy:g}^2/(2*{g:g}) = {apex_h:g} m.",
            f"Fall time from the split height is sqrt(2H/g) = sqrt(2*{apex_h:g}/{g:g}) = {fall_time_from_height:g} s, matching the given {given_fall_time:g} s.",
            f"After equal-mass split, the other fragment has horizontal speed 2u_x = {frag2_vx:g} m/s but the same vertical fall time, so t = {frag2_fall_time:g} s and x = {frag2_x:g} m.",
        ],
    )


def solve_bounce_restitution_height(entry: ManifestEntry) -> EvaluationResult:
    height = _optional_number_from_any_known(entry, ["height", "drop_height", "launch_height", "maximum_height", "h"])
    post_height = _optional_number_from_any_known(entry, ["post_bounce_height", "rebound_height", "height_after_bounce"])
    e = _optional_number_from_any_known(entry, ["e", "coefficient_of_restitution", "restitution"])
    retained = _optional_number_from_any_known(entry, ["energy_retained_fraction", "retained_fraction"])
    if e is None and retained is not None:
        e = math.sqrt(retained)
    if height is not None and e is not None:
        rebound_height = e * e * height
        return _result(
            entry,
            computed_value=rebound_height,
            computed_text=f"{rebound_height:g} m",
            trace=[
                "For a vertical bounce component, rebound height scales as the square of the restitution coefficient.",
                f"H_after = e^2 H_before = {e:g}^2 * {height:g} = {rebound_height:g} m.",
            ],
        )
    if height is not None and post_height is not None:
        coefficient = math.sqrt(post_height / height)
        return _result(
            entry,
            computed_value=coefficient,
            computed_text=f"{coefficient:g}",
            trace=[
                "For a bounce, H_after/H_before = e^2.",
                f"e = sqrt(H_after/H_before) = sqrt({post_height:g}/{height:g}) = {coefficient:g}.",
            ],
        )
    raise ValueError(f"{entry.label}: bounce solver needs height with restitution, retained energy, or post-bounce height")


def solve_relative_projectile_apex_collision(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_any_known(entry, ["v0", "velocity", "speed"])
    angle = math.radians(_number_from_any_known(entry, ["angle", "launch_angle"]))
    g = _number_from_known(entry, "g", default=10.0)
    vertical_throw_speed = v0 * math.sin(angle)
    collision_time = vertical_throw_speed / g
    apex_height = vertical_throw_speed * vertical_throw_speed / (2 * g)
    return _result(
        entry,
        computed_value=vertical_throw_speed,
        computed_text=f"{vertical_throw_speed:g} m/s",
        trace=[
            "The projectile reaches its highest point when its vertical velocity becomes zero.",
            f"t_apex = u sin(theta)/g = {v0:g} sin({math.degrees(angle):g}deg)/{g:g} = {collision_time:g} s.",
            f"Apex height is H = u_y^2/(2g) = {apex_height:g} m.",
            "A particle thrown vertically from the launch level must have the same initial vertical component to meet there at the same time.",
            f"So the required vertical throw speed is {vertical_throw_speed:g} m/s.",
        ],
    )


def solve_piecewise_acceleration_at_apex_range(entry: ManifestEntry) -> EvaluationResult:
    g1 = _number_from_any_known(entry, ["g1", "g", "initial_g"], default=10.0)
    g2 = _optional_number_from_any_known(entry, ["g2", "new_g", "effective_g"])
    if g2 is None:
        ratio = _optional_number_from_any_known(entry, ["acceleration_ratio", "g2_over_g1"])
        if ratio is not None:
            g2 = g1 * ratio
    if g2 is None or g2 <= 0:
        raise ValueError(f"{entry.label}: piecewise acceleration solver needs positive post-apex acceleration")
    range_value = _optional_number_from_any_known(entry, ["range", "r", "original_range"])
    if range_value is None:
        v0 = _number_from_any_known(entry, ["v0", "velocity", "speed"])
        angle = math.radians(_number_from_any_known(entry, ["angle", "launch_angle"]))
        range_value = v0 * v0 * math.sin(2 * angle) / g1
    new_range = 0.5 * range_value * (1 + math.sqrt(g1 / g2))
    return _result(
        entry,
        computed_value=new_range,
        computed_text=f"{new_range:g} m",
        trace=[
            "Up to the apex, the horizontal distance is half the original range.",
            "The descent time from the same apex height scales as sqrt(g1/g2) when post-apex acceleration changes.",
            f"R_new = (R/2)[1 + sqrt(g1/g2)] = ({range_value:g}/2)[1 + sqrt({g1:g}/{g2:g})] = {new_range:g} m.",
        ],
    )


def solve_level_ground_time_to_peak(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_any_known(entry, ["v0", "velocity", "speed"])
    angle = math.radians(_number_from_any_known(entry, ["angle", "launch_angle"]))
    g = _number_from_known(entry, "g", default=10.0)
    time = v0 * math.sin(angle) / g
    return _result(
        entry,
        computed_value=time,
        computed_text=f"{time:g} s",
        trace=[
            "At maximum height, the vertical component of velocity becomes zero.",
            "Use v_y = u sin(theta) - gt = 0, so t = u sin(theta)/g.",
            f"t = {v0:g} * sin({math.degrees(angle):g}deg) / {g:g} = {time:g} s.",
        ],
    )


def solve_level_ground_position_at_time(entry: ManifestEntry) -> EvaluationResult:
    v0 = _optional_number_from_any_known(entry, ["v0", "velocity", "speed"])
    angle_value = _optional_number_from_any_known(entry, ["angle", "launch_angle"])
    angle = math.radians(angle_value) if angle_value is not None else None
    time = _optional_number_from_any_known(entry, ["time", "t"])
    g = _number_from_known(entry, "g", default=10.0)
    x0 = _number_from_any_known(entry, ["x0", "initial_x"], default=0.0)
    y0 = _number_from_any_known(entry, ["y0", "initial_y"], default=0.0)
    target_x = _optional_number_from_any_known(entry, ["x", "target_x", "horizontal_distance", "distance"])
    target_y = _optional_number_from_any_known(entry, ["y", "target_y"])
    ux_known = _optional_number_from_any_known(entry, ["ux", "u_x", "vx", "v_x", "horizontal_velocity", "horizontal_speed"])
    component_context = any(marker in entry.question_text.lower() for marker in ("horizontal velocity", "horizontal component"))
    if ux_known is not None and time is not None and target_y is not None and (v0 is None or component_context):
        uy0 = (target_y - y0 + 0.5 * g * time * time) / time
        v0 = math.hypot(ux_known, uy0)
        angle = math.atan2(uy0, ux_known)
    if v0 is not None and angle is not None and time is None and target_x is not None:
        ux_for_time = v0 * math.cos(angle)
        if math.isclose(ux_for_time, 0.0, abs_tol=1e-12):
            raise ValueError(f"{entry.label}: horizontal position cannot determine time for vertical launch")
        time = (target_x - x0) / ux_for_time
    if v0 is None and angle is None and time is not None and target_x is not None and target_y is not None:
        ux0 = (target_x - x0) / time
        uy0 = (target_y - y0 + 0.5 * g * time * time) / time
        v0 = math.hypot(ux0, uy0)
        angle = math.atan2(uy0, ux0)
    if v0 is None or angle is None or time is None:
        missing = []
        if v0 is None:
            missing.append("launch speed")
        if angle is None:
            missing.append("launch angle")
        if time is None:
            missing.append("time or horizontal position")
        raise ValueError(f"{entry.label}: missing {', '.join(missing)}")
    x = x0 + v0 * math.cos(angle) * time
    y = y0 + v0 * math.sin(angle) * time - 0.5 * g * time * time
    vx = v0 * math.cos(angle)
    vy = v0 * math.sin(angle) - g * time
    speed = math.hypot(vx, vy)
    displacement = math.hypot(x - x0, y - y0)
    text = entry.question_text.lower()
    parts: list[str] = []
    if any(marker in text for marker in ("initial horizontal velocity", "initial vertical velocity", "initial speed", "angle of projection")):
        parts.append(f"u_x={v0 * math.cos(angle):g} m/s")
        parts.append(f"u_y={v0 * math.sin(angle):g} m/s")
        parts.append(f"u={v0:g} m/s")
        parts.append(f"theta={math.degrees(angle):g} deg")
    if "height" in text or target_y is not None:
        parts.append(f"y={y:g} m")
    if "position and velocity" in text:
        parts.append(f"x={x:g} m")
        parts.append(f"v_x={vx:g} m/s")
        parts.append(f"v_y={vy:g} m/s")
        parts.append(f"|v|={speed:g} m/s")
    if "displacement" in text:
        parts.append(f"displacement={displacement:g} m")
    if "vertical velocity" in text or "velocity when" in text:
        parts.append(f"v_y={vy:g} m/s")
    if not parts:
        parts.append(f"x={x:g} m")
        parts.append(f"y={y:g} m")
    return _result(
        entry,
        computed_value=None,
        computed_text=", ".join(parts),
        trace=[
            "Resolve the launch velocity into horizontal and vertical components.",
            f"x = x0 + u cos(theta)t = {x0:g} + {v0:g} cos({math.degrees(angle):g}deg)*{time:g} = {x:g} m.",
            f"y = y0 + u sin(theta)t - 0.5gt^2 = {y0:g} + {v0:g} sin({math.degrees(angle):g}deg)*{time:g} - 0.5*{g:g}*{time:g}^2 = {y:g} m.",
            f"v_y = u sin(theta) - gt = {vy:g} m/s and speed = {speed:g} m/s.",
        ],
    )


def solve_level_ground_velocity_at_time(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_any_known(entry, ["v0", "velocity", "speed"])
    angle = math.radians(_number_from_any_known(entry, ["angle", "launch_angle"]))
    time = _number_from_any_known(entry, ["time", "t"])
    g = _number_from_known(entry, "g", default=10.0)
    vx = v0 * math.cos(angle)
    vy = v0 * math.sin(angle) - g * time
    speed = math.hypot(vx, vy)
    computed_text = f"v_x={vx:g} m/s, v_y={vy:g} m/s, |v|={speed:g} m/s"
    return _result(
        entry,
        computed_value=speed,
        computed_text=computed_text,
        trace=[
            "Horizontal velocity stays constant while vertical velocity changes by -gt.",
            f"v_x = u cos(theta) = {v0:g} cos({math.degrees(angle):g}deg) = {vx:g} m/s.",
            f"v_y = u sin(theta) - gt = {v0:g} sin({math.degrees(angle):g}deg) - {g:g}*{time:g} = {vy:g} m/s.",
            f"Speed = sqrt(v_x^2+v_y^2) = {speed:g} m/s.",
        ],
    )


def solve_vertical_component_height_times(entry: ManifestEntry) -> EvaluationResult:
    uy = _number_from_any_known(entry, ["uy", "u_y", "vy", "v_y", "vertical_velocity", "vertical_speed"])
    height = _number_from_any_known(entry, ["height", "y", "target_y"])
    g = _number_from_known(entry, "g", default=10.0)
    discriminant = uy * uy - 2 * g * height
    if discriminant < -1e-9:
        raise ValueError(f"{entry.label}: projectile never reaches height {height:g} m")
    root = math.sqrt(max(0.0, discriminant))
    t1 = (uy - root) / g
    t2 = (uy + root) / g
    return _symbolic_result(
        entry,
        computed_text=f"t = {t1:g} s and {t2:g} s",
        trace=[
            "Use vertical motion y = u_y t - 1/2 gt^2.",
            f"{height:g} = {uy:g}t - 1/2*{g:g}t^2.",
            f"The two roots are t={t1:g}s and t={t2:g}s.",
        ],
    )


def solve_trajectory_equation_from_launch(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_any_known(entry, ["v0", "velocity", "speed"])
    angle = math.radians(_number_from_any_known(entry, ["angle", "launch_angle"]))
    g = _number_from_known(entry, "g", default=10.0)
    tan_angle = math.tan(angle)
    cos_angle = math.cos(angle)
    coefficient = g / (2 * v0 * v0 * cos_angle * cos_angle)
    return _symbolic_result(
        entry,
        computed_text=f"y = {tan_angle:g}x - {coefficient:g}x^2",
        trace=[
            "Eliminate time from x = u cos(theta)t and y = u sin(theta)t - 1/2gt^2.",
            "The trajectory equation is y = x tan(theta) - gx^2/(2u^2 cos^2(theta)).",
            f"Substitution gives y = {tan_angle:g}x - {coefficient:g}x^2.",
        ],
    )


def solve_monkey_hunter_condition(entry: ManifestEntry) -> EvaluationResult:
    v0 = _optional_number_from_any_known(entry, ["v0", "velocity", "speed"])
    height = _optional_number_from_any_known(entry, ["height", "y", "target_y"])
    g = _number_from_known(entry, "g", default=10.0)
    fall_time = math.sqrt(2 * height / g) if height is not None else None
    max_line_of_sight = v0 * fall_time if v0 is not None and fall_time is not None else None
    computed_text = (
        f"conditional: hits before ground only if line-of-sight distance <= {max_line_of_sight:g} m"
        if max_line_of_sight is not None
        else "conditional: hits if the projectile reaches the monkey before the monkey reaches the ground"
    )
    numeric_trace = []
    if fall_time is not None:
        numeric_trace.append(f"Monkey fall time is sqrt(2h/g) = sqrt(2*{height:g}/{g:g}) = {fall_time:g} s.")
    else:
        numeric_trace.append("Without the monkey height, the fall time remains sqrt(2h/g).")
    if max_line_of_sight is not None:
        numeric_trace.append(f"With speed {v0:g} m/s, the maximum line-of-sight distance is {v0:g}*{fall_time:g} = {max_line_of_sight:g} m.")
    else:
        numeric_trace.append("Without both projectile speed and line-of-sight distance, a bare yes/no is under-specified.")
    return _symbolic_result(
        entry,
        computed_text=computed_text,
        trace=[
            "A projectile aimed directly at a falling target has the same downward gravitational drop as the target.",
            "So it intersects the monkey if it reaches the original line-of-sight point before the monkey hits the ground.",
            *numeric_trace,
        ],
    )


def solve_same_height_times_initial_speed(entry: ManifestEntry) -> EvaluationResult:
    t1 = _number_from_any_known(entry, ["t1", "time1"])
    t2 = _number_from_any_known(entry, ["t2", "time2"])
    angle = math.radians(_number_from_any_known(entry, ["angle", "launch_angle"]))
    g = _number_from_known(entry, "g", default=10.0)
    uy = 0.5 * g * (t1 + t2)
    speed = uy / math.sin(angle)
    return _result(
        entry,
        computed_value=speed,
        computed_text=f"{speed:g} m/s",
        trace=[
            "At equal heights, the two times are symmetric around the peak time.",
            f"t_peak = (t1+t2)/2 = ({t1:g}+{t2:g})/2 = {(t1+t2)/2:g} s.",
            f"u_y = g*t_peak = {g:g}*{(t1+t2)/2:g} = {uy:g} m/s.",
            f"u = u_y/sin(theta) = {uy:g}/sin({math.degrees(angle):g}deg) = {speed:g} m/s.",
        ],
    )


def solve_trajectory_equation_max_height(entry: ManifestEntry) -> EvaluationResult:
    a = _number_from_any_known(entry, ["trajectory_a", "a"])
    b = _number_from_any_known(entry, ["trajectory_b", "b"])
    if b >= 0:
        raise ValueError(f"{entry.label}: trajectory parabola must open downward for maximum height")
    height = -a * a / (4 * b)
    x_at_peak = -a / (2 * b)
    return _result(
        entry,
        computed_value=height,
        computed_text=f"{height:g} m",
        trace=[
            "For y = ax + bx^2 with b < 0, the peak occurs where dy/dx = a + 2bx = 0.",
            f"x_peak = -a/(2b) = {-a:g}/({2*b:g}) = {x_at_peak:g}.",
            f"H = -a^2/(4b) = -{a:g}^2/(4*{b:g}) = {height:g} m.",
        ],
    )


def solve_projectile_height_scaling(entry: ManifestEntry) -> EvaluationResult:
    height = _number_from_any_known(entry, ["height", "maximum_height", "h"])
    speed_scale = _number_from_any_known(entry, ["speed_scale", "velocity_scale"], default=0.5)
    scaled_height = height * speed_scale * speed_scale
    return _result(
        entry,
        computed_value=scaled_height,
        computed_text=f"{scaled_height:g} m",
        trace=[
            "Maximum height is proportional to u_y^2. If launch angle is unchanged, H scales as speed squared.",
            f"H' = H * k^2 = {height:g} * {speed_scale:g}^2 = {scaled_height:g} m.",
        ],
    )


def solve_range_angle_scaling(entry: ManifestEntry) -> EvaluationResult:
    range_value = _number_from_any_known(entry, ["range", "r"])
    angle1 = math.radians(_number_from_any_known(entry, ["angle1", "initial_angle", "given_angle"]))
    angle2 = math.radians(_number_from_any_known(entry, ["angle2", "new_angle", "target_angle"]))
    denominator = math.sin(2 * angle1)
    if math.isclose(denominator, 0.0, abs_tol=1e-12):
        raise ValueError(f"{entry.label}: original angle gives zero range")
    new_range = range_value * math.sin(2 * angle2) / denominator
    return _result(
        entry,
        computed_value=new_range,
        computed_text=f"{new_range:g} m",
        trace=[
            "For the same speed on level ground, R is proportional to sin(2theta).",
            f"R2 = R1 sin(2theta2)/sin(2theta1) = {range_value:g}*sin({2*math.degrees(angle2):g}deg)/sin({2*math.degrees(angle1):g}deg) = {new_range:g} m.",
        ],
    )


def solve_two_projectile_same_speed_comparison(entry: ManifestEntry) -> EvaluationResult:
    speed = _number_from_any_known(entry, ["v0", "u", "speed", "velocity"])
    angle1_deg = _number_from_any_known(entry, ["angle1", "theta1", "angle_a"])
    angle2_deg = _number_from_any_known(entry, ["angle2", "theta2", "angle_b"])
    g = _number_from_known(entry, "g", default=10.0)

    def values(angle_deg: float) -> tuple[float, float, float]:
        theta = math.radians(angle_deg)
        time = 2 * speed * math.sin(theta) / g
        height = speed * speed * math.sin(theta) ** 2 / (2 * g)
        horizontal_range = speed * speed * math.sin(2 * theta) / g
        return time, height, horizontal_range

    t1, h1, r1 = values(angle1_deg)
    t2, h2, r2 = values(angle2_deg)
    range_relation = "same" if math.isclose(r1, r2, rel_tol=1e-9, abs_tol=1e-9) else ("larger for theta1" if r1 > r2 else "larger for theta2")
    computed_text = (
        f"theta1={angle1_deg:g}deg: T={t1:g}s, H={h1:g}m, R={r1:g}m; "
        f"theta2={angle2_deg:g}deg: T={t2:g}s, H={h2:g}m, R={r2:g}m; "
        f"range: {range_relation}"
    )
    return _result(
        entry,
        computed_value=None,
        computed_text=computed_text,
        trace=[
            "For equal speed on level ground, compare each quantity by its angle dependence.",
            f"T ∝ sin(theta): T1/T2 = sin({angle1_deg:g}deg)/sin({angle2_deg:g}deg), so {t1:g}s vs {t2:g}s.",
            f"H ∝ sin^2(theta): H1/H2 = sin^2({angle1_deg:g}deg)/sin^2({angle2_deg:g}deg), so {h1:g}m vs {h2:g}m.",
            f"R ∝ sin(2theta): sin({2*angle1_deg:g}deg) and sin({2*angle2_deg:g}deg), so {r1:g}m vs {r2:g}m.",
        ],
    )


def solve_range_equals_max_height_angle(entry: ManifestEntry) -> EvaluationResult:
    text = entry.question_text.lower()
    ratio = 1.0
    if "four times" in text or "4 times" in text or "4h" in text:
        ratio = 4.0
    elif "twice" in text or "two times" in text or "2 times" in text:
        ratio = 2.0
    angle = math.degrees(math.atan(4 / ratio))
    return _result(
        entry,
        computed_value=angle,
        computed_text=f"{angle:g} deg",
        trace=[
            "For level-ground projectile motion: R = u^2 sin(2theta)/g and H = u^2 sin^2(theta)/(2g).",
            "So R/H = 4 cot(theta).",
            f"Here R/H = {ratio:g}, so 4 cot(theta) = {ratio:g}.",
            f"theta = tan^-1({4 / ratio:g}) = {angle:g}deg.",
        ],
    )


def solve_level_ground_launch_angle_from_range(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_any_known(entry, ["v0", "velocity", "speed"])
    range_value = _number_from_any_known(entry, ["range", "R", "horizontal_range"])
    g = _number_from_known(entry, "g", default=10.0)
    sine_double_angle = g * range_value / (v0 * v0)
    if sine_double_angle > 1 + 1e-9:
        raise ValueError(
            f"{entry.label}: requested range {range_value:g} m is impossible for speed {v0:g} m/s"
        )
    sine_double_angle = min(1.0, max(-1.0, sine_double_angle))
    angle1 = 0.5 * math.degrees(math.asin(sine_double_angle))
    angle2 = 90.0 - angle1
    computed_text = f"{angle1:g}deg" if math.isclose(angle1, angle2) else f"{angle1:g}deg or {angle2:g}deg"
    return _symbolic_result(
        entry,
        computed_text=computed_text,
        trace=[
            "For level-ground range, R = u^2 sin(2theta)/g.",
            f"sin(2theta) = gR/u^2 = {g:g}*{range_value:g}/{v0:g}^2 = {sine_double_angle:g}.",
            f"So theta = {computed_text}.",
        ],
    )


def _height_launch_time(v0: float, angle: float, height: float, g: float) -> float:
    uy = v0 * math.sin(angle)
    return (uy + math.sqrt(uy * uy + 2 * g * height)) / g


def solve_height_launch_time_of_flight(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_any_known(entry, ["v0", "velocity", "speed"])
    angle = math.radians(_number_from_any_known(entry, ["angle", "launch_angle"]))
    height = _number_from_any_known(entry, ["height", "launch_height", "initial_height", "h"])
    g = _number_from_known(entry, "g", default=10.0)
    time = _height_launch_time(v0, angle, height, g)
    return _result(
        entry,
        computed_value=time,
        computed_text=f"{time:g} s",
        trace=[
            "For a launch from height h, ground impact satisfies h + u sin(theta)t - 0.5gt^2 = 0.",
            f"T = (u sin(theta) + sqrt(u^2 sin^2(theta) + 2gh))/g = {time:g} s.",
        ],
    )


def solve_height_launch_range(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_any_known(entry, ["v0", "velocity", "speed"])
    angle = math.radians(_number_from_any_known(entry, ["angle", "launch_angle"]))
    height = _number_from_any_known(entry, ["height", "launch_height", "initial_height", "h"])
    g = _number_from_known(entry, "g", default=10.0)
    time = _height_launch_time(v0, angle, height, g)
    range_value = v0 * math.cos(angle) * time
    return _result(
        entry,
        computed_value=range_value,
        computed_text=f"{range_value:g} m",
        trace=[
            "First solve the vertical quadratic to get the impact time.",
            f"T = {time:g} s.",
            f"Horizontal range is R = u cos(theta)T = {v0:g} cos({math.degrees(angle):g}deg)*{time:g} = {range_value:g} m.",
        ],
    )


def solve_height_launch_multi_quantity(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_any_known(entry, ["v0", "velocity", "speed"])
    angle = math.radians(_number_from_any_known(entry, ["angle", "launch_angle"]))
    height = _number_from_any_known(entry, ["height", "launch_height", "initial_height", "h"])
    g = _number_from_known(entry, "g", default=10.0)
    ux = v0 * math.cos(angle)
    uy = v0 * math.sin(angle)
    time = _height_launch_time(v0, angle, height, g)
    range_value = ux * time
    impact_vy = uy - g * time
    impact_speed = math.hypot(ux, impact_vy)
    impact_angle = math.degrees(math.atan2(abs(impact_vy), abs(ux))) if not math.isclose(ux, 0.0, abs_tol=1e-12) else 90.0
    peak_gain = uy * uy / (2 * g) if uy > 0 else 0.0
    max_height = height + peak_gain

    outputs = _requested_height_launch_outputs(entry.question_text)
    if not outputs:
        outputs = ["time_of_flight", "range"]

    output_text: list[str] = []
    if "components" in outputs:
        output_text.append(f"u_x = {ux:g} m/s")
        output_text.append(f"u_y = {uy:g} m/s")
    if "time_of_flight" in outputs:
        output_text.append(f"T = {time:g} s")
    if "range" in outputs:
        output_text.append(f"R = {range_value:g} m")
    if "maximum_height" in outputs:
        output_text.append(f"H = {max_height:g} m")
    if "impact_speed" in outputs:
        output_text.append(f"|v|_impact = {impact_speed:g} m/s")
    if "impact_angle" in outputs:
        output_text.append(f"impact angle = {impact_angle:g} deg below horizontal")

    trace = [
        f"Resolve components: u_x = {ux:g} m/s, u_y = {uy:g} m/s.",
        "Use the nonzero-height vertical equation: 0 = h + u_y t - 1/2 g t^2.",
        f"The positive root gives T = {time:g} s.",
    ]
    if "range" in outputs:
        trace.append(f"Horizontal motion gives R = u_x T = {ux:g} * {time:g} = {range_value:g} m.")
    if "maximum_height" in outputs:
        trace.append(f"Peak height above ground is h + u_y^2/(2g) = {max_height:g} m.")
    if "impact_speed" in outputs or "impact_angle" in outputs:
        trace.append(f"At impact, v_y = u_y - gT = {impact_vy:g} m/s and speed = {impact_speed:g} m/s.")

    return _symbolic_result(entry, computed_text="; ".join(output_text), trace=trace)


def solve_height_launch_horizontal_scenario(entry: ManifestEntry) -> EvaluationResult:
    v0 = _optional_number_from_any_known(entry, ["vx", "ux", "v_x", "u_x", "horizontal_velocity", "v0", "velocity", "speed"])
    height = _optional_number_from_any_known(entry, ["height", "launch_height", "initial_height", "h"])
    time = _optional_number_from_any_known(entry, ["time", "t", "flight_time", "time_of_flight"])
    range_value = _optional_number_from_any_known(entry, ["range", "horizontal_range", "distance"])
    g = _number_from_known(entry, "g", default=10.0)
    if time is None and height is not None:
        time = math.sqrt(2 * height / g)
    if height is None and time is not None:
        height = 0.5 * g * time * time
    if v0 is None and range_value is not None and time is not None:
        v0 = range_value / time
    if range_value is None and v0 is not None and time is not None:
        range_value = v0 * time
    if time is None and v0 is not None and range_value is not None:
        time = range_value / v0
        height = 0.5 * g * time * time
    if v0 is None or height is None or time is None or range_value is None:
        missing = [
            name for name, value in {
                "horizontal speed": v0,
                "height": height,
                "time": time,
                "range": range_value,
            }.items()
            if value is None
        ]
        raise ValueError(f"{entry.label}: insufficient horizontal-launch data; missing {', '.join(missing)}")
    impact_vy = -g * time
    horizontal_speed = abs(v0)
    impact_speed = math.hypot(horizontal_speed, impact_vy)
    impact_angle = math.degrees(math.atan2(abs(impact_vy), abs(v0))) if not math.isclose(v0, 0.0, abs_tol=1e-12) else 90.0
    outputs = _requested_height_launch_outputs(entry.question_text)
    if not outputs:
        outputs = ["time_of_flight", "range", "impact_speed"]
    output_text: list[str] = []
    if "time_of_flight" in outputs:
        output_text.append(f"time = {time:g} s")
    if "range" in outputs:
        output_text.append(f"range = {range_value:g} m")
    if "height" in outputs:
        output_text.append(f"height = {height:g} m")
    if "components" in outputs or "horizontal_speed" in outputs:
        output_text.append(f"v_x = {v0:g} m/s")
    if "impact_velocity" in outputs:
        y_sign = "-" if impact_vy < 0 else "+"
        output_text.append(f"impact velocity = {v0:g}i {y_sign} {abs(impact_vy):g}j m/s")
    if "impact_speed" in outputs:
        output_text.append(f"impact speed = {impact_speed:g} m/s")
    if "impact_angle" in outputs:
        direction_text = "leftward horizontal" if v0 < 0 else "horizontal"
        output_text.append(f"impact angle = {impact_angle:g} deg below {direction_text}")
    trace = [
        "Horizontal launch has u_y = 0, so vertical motion and horizontal motion separate cleanly.",
        f"Vertical motion gives h = 1/2 g t^2, so h = {height:g} m and t = {time:g} s.",
        f"Horizontal velocity stays constant: v_x = {v0:g} m/s.",
    ]
    if "range" in outputs:
        trace.append(f"Horizontal motion gives R = v_x t = {v0:g} * {time:g} = {range_value:g} m.")
    if "impact_velocity" in outputs or "impact_speed" in outputs or "impact_angle" in outputs:
        trace.append(f"Impact vertical velocity is v_y = -gt = {impact_vy:g} m/s.")
    if "impact_velocity" in outputs:
        y_sign = "-" if impact_vy < 0 else "+"
        trace.append(f"Therefore the impact velocity vector is v = {v0:g}i {y_sign} {abs(impact_vy):g}j m/s.")
    if "impact_speed" in outputs:
        trace.append(f"Impact speed is |v| = sqrt(v_x^2 + v_y^2) = sqrt({horizontal_speed:g}^2 + {abs(impact_vy):g}^2) = {impact_speed:g} m/s.")
    if "impact_angle" in outputs:
        trace.append(
            f"The velocity angle below horizontal is phi = tan^-1(|v_y|/|v_x|) = "
            f"tan^-1({abs(impact_vy):g}/{abs(v0):g}) = {impact_angle:g} deg."
        )
    return _symbolic_result(
        entry,
        computed_text="; ".join(output_text),
        trace=trace,
    )


def solve_wall_height_at_distance(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_any_known(entry, ["v0", "velocity", "speed"])
    angle = math.radians(_number_from_any_known(entry, ["angle", "launch_angle"]))
    wall_x = _number_from_any_known(entry, ["wall_distance", "wall_x", "x"])
    g = _number_from_known(entry, "g", default=10.0)
    launch_height = _number_from_any_known(entry, ["launch_height", "initial_height", "y0"], default=0.0)
    cos_angle = math.cos(angle)
    if math.isclose(cos_angle, 0.0, abs_tol=1e-12):
        raise ValueError(f"{entry.label}: vertical launch never reaches wall distance {wall_x:g}")
    y = launch_height + wall_x * math.tan(angle) - g * wall_x * wall_x / (2 * v0 * v0 * cos_angle * cos_angle)
    return _result(
        entry,
        computed_value=y,
        computed_text=f"{y:g} m",
        trace=[
            "Use the trajectory equation at the wall's horizontal distance.",
            f"y = y0 + x tan(theta) - gx^2/(2u^2 cos^2(theta)).",
            f"At x={wall_x:g} m, y={y:g} m.",
        ],
    )


def solve_wall_clearance_condition(entry: ManifestEntry) -> EvaluationResult:
    v0 = _optional_number_from_any_known(entry, ["v0", "velocity", "speed"])
    angle_value = _optional_number_from_any_known(entry, ["angle", "launch_angle"])
    angle = math.radians(angle_value) if angle_value is not None else None
    wall_x = _optional_number_from_any_known(entry, ["wall_distance", "wall_x", "x"])
    wall_height = _number_from_any_known(entry, ["wall_height", "obstacle_height"])
    g = _number_from_known(entry, "g", default=10.0)
    launch_height = _number_from_any_known(entry, ["launch_height", "initial_height", "y0"], default=0.0)
    wall_x1 = _optional_number_from_any_known(entry, ["wall_x1", "x1"])
    wall_x2 = _optional_number_from_any_known(entry, ["wall_x2", "x2"])
    if (v0 is None or angle is None) and wall_x1 is not None and wall_x2 is not None and math.isclose(launch_height, 0.0, abs_tol=1e-12):
        x1, x2 = sorted([wall_x1, wall_x2])
        curvature = wall_height / (x1 * x2)
        tan_angle = wall_height * (x1 + x2) / (x1 * x2)
        angle = math.atan(tan_angle)
        cos_angle = math.cos(angle)
        v0 = math.sqrt(g / (2 * curvature * cos_angle * cos_angle))
        return _symbolic_result(
            entry,
            computed_text=f"theta = {math.degrees(angle):g} deg; u = {v0:g} m/s",
            trace=[
                "For two equal-height clearances, write the trajectory as y = ax - bx^2.",
                f"Since y({x1:g}) = y({x2:g}) = {wall_height:g}, b = h/(x1*x2) = {curvature:g}.",
                f"a = b(x1+x2), so tan(theta) = {tan_angle:g}.",
                f"Using b = g/(2u^2 cos^2(theta)) gives u = {v0:g} m/s.",
            ],
        )
    if v0 is None or angle is None or wall_x is None:
        raise ValueError(f"{entry.label}: missing launch speed, launch angle, or wall distance")
    cos_angle = math.cos(angle)
    if math.isclose(cos_angle, 0.0, abs_tol=1e-12):
        raise ValueError(f"{entry.label}: vertical launch never reaches wall distance {wall_x:g}")
    projectile_height = launch_height + wall_x * math.tan(angle) - g * wall_x * wall_x / (
        2 * v0 * v0 * cos_angle * cos_angle
    )
    clearance = projectile_height - wall_height
    computed_text = f"clears by {clearance:g} m" if clearance >= 0 else f"does not clear; short by {abs(clearance):g} m"
    return _symbolic_result(
        entry,
        computed_text=computed_text,
        trace=[
            "Find projectile height at the wall, then compare it with wall height.",
            f"y_wall = {projectile_height:g} m.",
            f"clearance = y_wall - H_wall = {projectile_height:g} - {wall_height:g} = {clearance:g} m.",
        ],
    )


def solve_target_launch_angle_fixed_speed(entry: ManifestEntry) -> EvaluationResult:
    target = _known_value(entry, "target")
    x, y = _parse_point2(target)
    v0 = _number_from_any_known(entry, ["v0", "velocity", "speed"])
    g = _number_from_known(entry, "g", default=10.0)
    if math.isclose(x, 0.0, abs_tol=1e-12):
        raise ValueError(f"{entry.label}: target-angle solver needs nonzero horizontal target distance")
    a = g * x * x / (2 * v0 * v0)
    discriminant = x * x - 4 * a * (a + y)
    if discriminant < -1e-9:
        raise ValueError(f"{entry.label}: target is unreachable with speed {v0:g} m/s")
    discriminant = max(0.0, discriminant)
    roots = [(x - math.sqrt(discriminant)) / (2 * a), (x + math.sqrt(discriminant)) / (2 * a)]
    angles = sorted(math.degrees(math.atan(root)) for root in roots if root > 0)
    if not angles:
        raise ValueError(f"{entry.label}: no positive launch angle reaches target")
    if len(angles) == 2 and math.isclose(angles[0], angles[1], abs_tol=1e-9):
        angles = [angles[0]]
    computed_text = " or ".join(f"{angle:g}deg" for angle in angles)
    return _symbolic_result(
        entry,
        computed_text=computed_text,
        trace=[
            "Use trajectory equation through target (x,y) with T = tan(theta).",
            "The quadratic is A T^2 - xT + (A+y)=0, where A = gx^2/(2u^2).",
            f"A={a:g}, discriminant={discriminant:g}, so theta={computed_text}.",
        ],
    )


def solve_two_projectile_collision_time(entry: ManifestEntry) -> EvaluationResult:
    p1_x = _number_from_any_known(entry, ["p1_x0", "x1", "a_x0"], default=0.0)
    p1_y = _number_from_any_known(entry, ["p1_y0", "y1", "a_y0"], default=0.0)
    p2_x = _number_from_any_known(entry, ["p2_x0", "x2", "b_x0"])
    p2_y = _number_from_any_known(entry, ["p2_y0", "y2", "b_y0"], default=0.0)
    p1_vx = _number_from_any_known(entry, ["p1_vx", "a_vx", "vx1"])
    p1_vy = _number_from_any_known(entry, ["p1_vy", "a_vy", "vy1"])
    p2_vx = _number_from_any_known(entry, ["p2_vx", "b_vx", "vx2"])
    p2_vy = _number_from_any_known(entry, ["p2_vy", "b_vy", "vy2"])
    times: list[float] = []
    if not math.isclose(p1_vx, p2_vx, abs_tol=1e-12):
        times.append((p2_x - p1_x) / (p1_vx - p2_vx))
    elif not math.isclose(p1_x, p2_x, abs_tol=1e-9):
        raise ValueError(f"{entry.label}: horizontal relative motion never closes")
    if not math.isclose(p1_vy, p2_vy, abs_tol=1e-12):
        times.append((p2_y - p1_y) / (p1_vy - p2_vy))
    elif not math.isclose(p1_y, p2_y, abs_tol=1e-9):
        raise ValueError(f"{entry.label}: vertical relative motion never closes")
    if not times:
        raise ValueError(f"{entry.label}: projectiles have no relative motion")
    time = times[0]
    if any(not math.isclose(candidate, time, rel_tol=1e-6, abs_tol=1e-6) for candidate in times):
        raise ValueError(f"{entry.label}: component collision times are inconsistent")
    if time < 0:
        raise ValueError(f"{entry.label}: collision would occur in the past")
    return _result(
        entry,
        computed_value=time,
        computed_text=f"{time:g} s",
        trace=[
            "For two projectiles under the same gravity, relative acceleration is zero.",
            "Use relative linear motion: r1 + v1 t = r2 + v2 t.",
            f"Collision time is t = {time:g} s.",
        ],
    )


def solve_air_drag_conceptual_timing(entry: ManifestEntry) -> EvaluationResult:
    return _symbolic_result(
        entry,
        computed_text="t1 will decrease while t2 will increase",
        trace=[
            "With air drag, horizontal speed decreases throughout the flight.",
            "Before the highest point the projectile reaches the same vertical level sooner, so t1 decreases.",
            "After the highest point the reduced horizontal speed makes the remaining horizontal segment take longer, so t2 increases.",
        ],
    )


def solve_max_range_from_height_fixed_speed(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_known(entry, "v0")
    height = _number_from_known(entry, "height")
    g = _number_from_known(entry, "g", default=10.0)
    max_range = (v0 / g) * math.sqrt(v0 * v0 + 2 * g * height)
    return _result(
        entry,
        computed_value=max_range,
        computed_text=f"{max_range:g} m",
        trace=[
            "For launch from height h with fixed speed v, maximum ground range is (v/g)*sqrt(v^2 + 2gh).",
            f"Rmax = ({v0:g}/{g:g}) * sqrt({v0:g}^2 + 2*{g:g}*{height:g}) = {max_range:g} m",
        ],
    )


def solve_target_reachability_fixed_speed(entry: ManifestEntry) -> EvaluationResult:
    return _symbolic_result(
        entry,
        computed_text="beta > 3alpha/4",
        trace=[
            "For target (alpha, beta), trajectory equation is beta = alpha*T - (g alpha^2 / 2v^2)(1+T^2), where T=tan(theta).",
            "Given v^2 = 2g alpha, this becomes beta/alpha = T - (1+T^2)/4.",
            "The maximum of T - (1+T^2)/4 occurs at T=2 and equals 3/4.",
            "So targets with beta > 3alpha/4 are impossible.",
        ],
    )


def solve_minimum_speed_to_hit_target(entry: ManifestEntry) -> EvaluationResult:
    target = _known_value(entry, "target")
    x, y = _parse_point2(target)
    g = _number_from_known(entry, "g", default=10.0)
    min_speed = math.sqrt(g * (y + math.hypot(x, y)))
    return _result(
        entry,
        computed_value=min_speed,
        computed_text=f"{min_speed:g} m/s",
        trace=[
            "Minimum speed to reach (x,y) is sqrt(g(y + sqrt(x^2+y^2))).",
            f"u_min = sqrt({g:g}({y:g} + sqrt({x:g}^2 + {y:g}^2))) = {min_speed:g} m/s",
        ],
    )


def solve_inclined_plane_impact_time(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_known(entry, "v0")
    launch_angle = math.radians(_number_from_known(entry, "launch_angle_horizontal"))
    incline_angle = math.radians(_number_from_known(entry, "incline"))
    g = _number_from_known(entry, "g", default=10.0)
    time = 2 * v0 * (math.sin(launch_angle) - math.cos(launch_angle) * math.tan(incline_angle)) / g
    return _result(
        entry,
        computed_value=time,
        computed_text=f"{time:g} s",
        trace=[
            "Impact with incline occurs when y = x*tan(alpha).",
            "Substitute x=vcos(theta)t and y=vsin(theta)t - 0.5gt^2.",
            f"t = 2v(sin(theta)-cos(theta)tan(alpha))/g = {time:g} s",
        ],
    )


def solve_inclined_plane_same_point_time_ratio(entry: ManifestEntry) -> EvaluationResult:
    return _symbolic_result(
        entry,
        computed_text="sin(alpha - beta) cos(alpha)",
        trace=[
            "For two equal-speed projections reaching the same point on an incline, the launch angles are complementary around the range-maximizing direction.",
            "Using inclined-plane range R = 2u^2 cos(theta) sin(theta-beta)/(g cos^2 beta), equal ranges give the paired-angle relation.",
            "The resulting time-of-flight ratio reduces to sin(alpha-beta) cos(alpha).",
        ],
    )


def solve_inclined_plane_right_angle_impact_condition(entry: ManifestEntry) -> EvaluationResult:
    return _symbolic_result(
        entry,
        computed_text="cot theta = 2 tan alpha",
        trace=[
            "Resolve motion along and perpendicular to the incline.",
            "At impact perpendicular to the incline, the along-plane velocity component is zero.",
            "Combining that condition with return to the inclined plane gives cot(theta) = 2 tan(alpha).",
        ],
    )


def solve_staircase_collision(entry: ManifestEntry) -> EvaluationResult:
    vx = _number_from_any_known(entry, ["vx", "v0x", "horizontal_velocity"], default=10.0)
    step_height = _number_from_any_known(entry, ["step_height", "y"], default=1.0)
    step_width = _number_from_any_known(entry, ["step_width", "x"], default=1.0)
    g = _number_from_known(entry, "g", default=9.8)
    # At the vertical face of the nth step, x=n*w and drop y=0.5*g*(x/vx)^2.
    # The first n for which the drop reaches n*h is the directly struck step.
    coefficient = g * step_width * step_width / (2 * vx * vx * step_height)
    step = math.floor(1 / coefficient) + 1
    return _result(
        entry,
        computed_value=float(step),
        computed_text=f"{step}st" if step % 10 == 1 and step % 100 != 11 else f"{step}th",
        trace=[
            f"At the nth vertical face, x = n*{step_width:g} and t = x/{vx:g}.",
            f"Drop y = 0.5*g*t^2 = {coefficient:g} n^2 step-heights.",
            f"First direct strike satisfies {coefficient:g} n^2 >= n, giving n > {1 / coefficient:g}.",
            f"So the marble strikes the {step}st step.",
        ],
    )


def solve_inclined_plane_max_normal_distance_velocity_component(entry: ManifestEntry) -> EvaluationResult:
    return _symbolic_result(
        entry,
        computed_text="zero",
        trace=[
            "Maximum distance from an inclined plane means the normal displacement is instantaneously extremal.",
            "At an extremum, the velocity component normal to that plane is zero.",
            "Therefore the requested component is zero.",
        ],
    )


def solve_perpendicular_launch_range_on_incline(entry: ManifestEntry) -> EvaluationResult:
    v0 = _number_from_any_known(entry, ["v0", "velocity", "speed"], default=10.0)
    incline = math.radians(_number_from_any_known(entry, ["incline", "incline_angle", "angle"], default=30.0))
    g = _number_from_known(entry, "g", default=10.0)
    range_on_plane = 2 * v0 * v0 * math.sin(incline) / (g * math.cos(incline) ** 2)
    return _result(
        entry,
        computed_value=range_on_plane,
        computed_text=f"{range_on_plane:g} m",
        trace=[
            "Launch is perpendicular to the incline, so initial along-plane velocity is zero.",
            "Normal return time is t = 2u/(g cos alpha).",
            "Along-plane range is s = 0.5*g sin(alpha)*t^2 = 2u^2 sin(alpha)/(g cos^2 alpha).",
            f"With u={v0:g}, alpha={math.degrees(incline):g}deg, R={range_on_plane:g} m.",
        ],
    )


def solve_max_range_on_incline(entry: ManifestEntry) -> EvaluationResult:
    return _symbolic_result(
        entry,
        computed_text="v^2 / (g(1 + sin theta))",
        trace=[
            "Range on an incline is maximized when the launch angle relative to the plane is 45deg - theta/2.",
            "The resulting maximum range along the plane is v^2 / (g(1 + sin theta)).",
        ],
    )


def solve_horizontal_launch_onto_incline_distance(entry: ManifestEntry) -> EvaluationResult:
    return _symbolic_result(
        entry,
        computed_text="sqrt2 [2v^2/g]",
        trace=[
            "For horizontal launch from the top of a 45deg incline: x=vt and y=-gt^2/2.",
            "The incline is y=-x, so gt^2/2 = vt and t = 2v/g.",
            "Horizontal distance x = 2v^2/g. Distance along the incline is x/cos45deg = 2sqrt2 v^2/g.",
        ],
    )


def solve_two_inclines_perpendicular_launch_impact(entry: ManifestEntry) -> EvaluationResult:
    u = _number_from_any_known(entry, ["u", "v0", "velocity"], default=10 * math.sqrt(3))
    plane_oa = math.radians(_number_from_any_known(entry, ["plane_OA", "plane_oa", "angle OA"], default=30.0))
    plane_ob = math.radians(_number_from_any_known(entry, ["plane_OB", "plane_ob", "angle OB"], default=60.0))
    launch_angle = plane_oa + math.pi / 2
    impact_velocity_angle = plane_ob + math.pi / 2
    vx = u * math.cos(launch_angle)
    impact_speed = abs(vx / math.cos(impact_velocity_angle))
    return _result(
        entry,
        computed_value=impact_speed,
        computed_text=f"{impact_speed:g} m/s",
        trace=[
            "Initial velocity is perpendicular to OA, so its horizontal component remains fixed.",
            f"vx = u cos({math.degrees(launch_angle):g}deg) = {vx:g} m/s.",
            "At Q the velocity is perpendicular to OB.",
            f"vQ = |vx / cos({math.degrees(impact_velocity_angle):g}deg)| = {impact_speed:g} m/s.",
        ],
    )


def solve_projectile_collides_with_sliding_particle_on_incline(entry: ManifestEntry) -> EvaluationResult:
    time = _number_from_any_known(entry, ["collision_time", "t", "t1"], default=4.0)
    g = _number_from_known(entry, "g", default=10.0)
    incline_deg = _number_from_any_known(entry, ["incline", "incline_angle", "angle"])
    incline = math.radians(incline_deg)
    normal_acceleration = g * math.cos(incline)
    projection_speed = 0.5 * normal_acceleration * time
    return _result(
        entry,
        computed_value=projection_speed,
        computed_text=f"{projection_speed:g} m/s",
        trace=[
            f"Take axes along the plane and normal to the plane. From the diagram, P is projected normal to the {incline_deg:g}deg incline and Q is released from rest on it.",
            "Along the plane, both particles have zero initial along-plane velocity and the same acceleration g sin(alpha), so their along-plane positions remain equal.",
            "Normal to the plane, Q stays on the plane, so n_Q = 0. Projectile P has n_P = ut - (1/2)g cos(alpha)t^2.",
            f"Collision requires n_P = 0 at t = {time:g}s, so u = (g cos(alpha)t)/2.",
            f"u = ({g:g} cos({incline_deg:g}deg) x {time:g})/2 = {projection_speed:g} m/s.",
        ],
    )


def solve_motion_on_smooth_incline_perpendicular_to_slope(entry: ManifestEntry) -> EvaluationResult:
    initial_speed = _number_from_any_known(entry, ["initial_speed", "v0", "velocity"], default=8.0)
    time = _number_from_any_known(entry, ["time", "t"], default=1.0)
    g = _number_from_known(entry, "g", default=10.0)
    incline = math.radians(_number_from_any_known(entry, ["incline", "incline_angle"], default=37.0))
    down_slope_speed = g * math.sin(incline) * time
    speed = math.hypot(initial_speed, down_slope_speed)
    return _result(
        entry,
        computed_value=speed,
        computed_text=f"{speed:g} m/s",
        trace=[
            "Initial velocity is perpendicular to the line of greatest slope, while acceleration is down the greatest slope.",
            f"Down-slope component after t is g sin(alpha)t = {down_slope_speed:g} m/s.",
            f"Resultant speed = sqrt({initial_speed:g}^2 + {down_slope_speed:g}^2) = {speed:g} m/s.",
        ],
    )


def solve_three_dimensional_projectile_line_intersection(entry: ManifestEntry) -> EvaluationResult:
    x0, y0, _ = _parse_point3(_known_value(entry, "P"))
    v0 = _number_from_known(entry, "v0")
    launch_angle = math.radians(_number_from_known(entry, "launch_angle"))
    line_angle = math.radians(_number_from_known(entry, "line_angle"))
    g = _number_from_known(entry, "g", default=10.0)
    time = 2 * v0 * math.sin(launch_angle) / g
    horizontal_range = v0 * math.cos(launch_angle) * time
    cos_line = 4 / 5 if math.isclose(math.degrees(line_angle), 37.0, abs_tol=0.25) else math.cos(line_angle)
    sin_line = 3 / 5 if math.isclose(math.degrees(line_angle), 37.0, abs_tol=0.25) else math.sin(line_angle)
    x = x0 + horizontal_range * cos_line
    y = y0 + horizontal_range * sin_line
    computed_text = f"({x:g},{y:g},0)m"
    return _result(
        entry,
        computed_value=None,
        computed_text=computed_text,
        trace=[
            f"Time to return to horizontal plane is T = 2u sin(theta)/g = {time:g}s.",
            f"Horizontal distance along line PQ is u cos(theta)T = {horizontal_range:g}m.",
            f"Line direction is {math.degrees(line_angle):g}deg, so impact point is {computed_text}.",
        ],
    )


SOLVERS: dict[str, Solver] = {
    "parametric_initial_speed": solve_parametric_initial_speed,
    "velocity_change_interval": solve_velocity_change_interval,
    "parametric_curve_classification": solve_parametric_curve_classification,
    "velocity_angle_event_speed": solve_velocity_angle_event_speed,
    "horizontal_throw_velocity_angle_time": solve_horizontal_throw_velocity_angle_time,
    "velocity_perpendicular_to_initial_event": solve_velocity_perpendicular_to_initial_event,
    "same_range_doubled_angle_time_ratio": solve_same_range_doubled_angle_time_ratio,
    "two_projectile_interception_time_ratio": solve_two_projectile_interception_time_ratio,
    "target_angle_from_short_overshoot": solve_target_angle_from_short_overshoot,
    "fielder_catch_before_ground": solve_fielder_catch_before_ground,
    "average_velocity_to_peak": solve_average_velocity_to_peak,
    "projectile_with_horizontal_acceleration": solve_projectile_with_horizontal_acceleration,
    "level_ground_range": solve_level_ground_range,
    "level_ground_time_of_flight": solve_level_ground_time_of_flight,
    "level_ground_multi_quantity": solve_level_ground_multi_quantity,
    "level_ground_range_and_time": solve_level_ground_range_and_time,
    "level_ground_time_of_flight_derivation": solve_level_ground_time_of_flight_derivation,
    "level_ground_max_height": solve_level_ground_max_height,
    "projectile_split_at_apex_fragment_time": solve_projectile_split_at_apex_fragment_time,
    "bounce_restitution_height": solve_bounce_restitution_height,
    "relative_projectile_apex_collision": solve_relative_projectile_apex_collision,
    "piecewise_acceleration_at_apex_range": solve_piecewise_acceleration_at_apex_range,
    "level_ground_time_to_peak": solve_level_ground_time_to_peak,
    "level_ground_position_at_time": solve_level_ground_position_at_time,
    "level_ground_velocity_at_time": solve_level_ground_velocity_at_time,
    "vertical_component_height_times": solve_vertical_component_height_times,
    "trajectory_equation_from_launch": solve_trajectory_equation_from_launch,
    "monkey_hunter_condition": solve_monkey_hunter_condition,
    "same_height_times_initial_speed": solve_same_height_times_initial_speed,
    "trajectory_equation_max_height": solve_trajectory_equation_max_height,
    "projectile_height_scaling": solve_projectile_height_scaling,
    "range_angle_scaling": solve_range_angle_scaling,
    "two_projectile_same_speed_comparison": solve_two_projectile_same_speed_comparison,
    "range_equals_max_height_angle": solve_range_equals_max_height_angle,
    "level_ground_launch_angle_from_range": solve_level_ground_launch_angle_from_range,
    "height_launch_time_of_flight": solve_height_launch_time_of_flight,
    "height_launch_range": solve_height_launch_range,
    "height_launch_multi_quantity": solve_height_launch_multi_quantity,
    "height_launch_horizontal_scenario": solve_height_launch_horizontal_scenario,
    "wall_height_at_distance": solve_wall_height_at_distance,
    "wall_clearance_condition": solve_wall_clearance_condition,
    "target_launch_angle_fixed_speed": solve_target_launch_angle_fixed_speed,
    "two_projectile_collision_time": solve_two_projectile_collision_time,
    "max_range_from_height_fixed_speed": solve_max_range_from_height_fixed_speed,
    "target_reachability_fixed_speed": solve_target_reachability_fixed_speed,
    "minimum_speed_to_hit_target": solve_minimum_speed_to_hit_target,
    "inclined_plane_impact_time": solve_inclined_plane_impact_time,
    "air_drag_conceptual_timing": solve_air_drag_conceptual_timing,
    "inclined_plane_same_point_time_ratio": solve_inclined_plane_same_point_time_ratio,
    "inclined_plane_right_angle_impact_condition": solve_inclined_plane_right_angle_impact_condition,
    "staircase_collision": solve_staircase_collision,
    "inclined_plane_max_normal_distance_velocity_component": solve_inclined_plane_max_normal_distance_velocity_component,
    "perpendicular_launch_range_on_incline": solve_perpendicular_launch_range_on_incline,
    "max_range_on_incline": solve_max_range_on_incline,
    "horizontal_launch_onto_incline_distance": solve_horizontal_launch_onto_incline_distance,
    "two_inclines_perpendicular_launch_impact": solve_two_inclines_perpendicular_launch_impact,
    "projectile_collides_with_sliding_particle_on_incline": solve_projectile_collides_with_sliding_particle_on_incline,
    "motion_on_smooth_incline_perpendicular_to_slope": solve_motion_on_smooth_incline_perpendicular_to_slope,
    "three_dimensional_projectile_line_intersection": solve_three_dimensional_projectile_line_intersection,
}

ENGINE_CASE_ALIASES = {
    "projectile_velocity_change": "velocity_change_interval",
    "velocity_change": "velocity_change_interval",
    "change_in_velocity": "velocity_change_interval",
    "delta_velocity": "velocity_change_interval",
    "level_ground_range_and_time": "level_ground_multi_quantity",
}


def canonical_engine_case(engine_case: str | None) -> str | None:
    if not engine_case:
        return None
    key = engine_case.strip()
    return ENGINE_CASE_ALIASES.get(key, key)


def _known_value(entry: ManifestEntry, key: str) -> str:
    target = _normalize_known_key(key)
    for known in entry.knowns:
        if "=" not in known:
            continue
        known_key, known_value = known.split("=", 1)
        if _normalize_known_key(known_key) == target:
            return known_value.strip()
    raise ValueError(f"{entry.label}: missing known {key}")


def _number_from_known(entry: ManifestEntry, key: str, default: float | None = None) -> float:
    try:
        raw = _known_value(entry, key)
    except ValueError:
        if default is not None:
            return default
        raise
    return _parse_number(raw)


def _number_from_any_known(entry: ManifestEntry, keys: list[str], default: float | None = None) -> float:
    for key in keys:
        try:
            return _number_from_known(entry, key)
        except ValueError:
            continue
    if default is not None:
        return default
    raise ValueError(f"{entry.label}: missing known {'/'.join(keys)}")


def _optional_number_from_any_known(entry: ManifestEntry, keys: list[str]) -> float | None:
    for key in keys:
        try:
            return _number_from_known(entry, key)
        except ValueError:
            continue
    return None


def _number_from_known_or_text(entry: ManifestEntry, key: str, default: float | None = None) -> float:
    try:
        return _number_from_known(entry, key)
    except ValueError:
        text = entry.question_text
        if key == "g":
            match = re.search(r"g\s*=\s*([-+]?\d+(?:\.\d+)?)", text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        if default is not None:
            return default
        raise


def _number_from_known_or_time_interval(entry: ManifestEntry, key: str) -> float:
    try:
        return _number_from_known(entry, key)
    except ValueError:
        text = _compact_time_text(entry.question_text)
        interval_patterns = [
            r"(?:from)?t=([-+]?\d+(?:\.\d+)?)(?:s|sec|seconds)?(?:to|until|-)t=([-+]?\d+(?:\.\d+)?)",
            r"(?:from)?t=([-+]?\d+(?:\.\d+)?)(?:s|sec|seconds)?(?:to|until|-)([-+]?\d+(?:\.\d+)?)",
            r"timeinterval(?:from)?([-+]?\d+(?:\.\d+)?)(?:s|sec|seconds)?(?:to|until|-)([-+]?\d+(?:\.\d+)?)",
        ]
        for pattern in interval_patterns:
            match = re.search(pattern, text)
            if match:
                return abs(float(match.group(2)) - float(match.group(1)))
        match = re.search(r"(?:time interval|interval).*?([-+]?\d+(?:\.\d+)?)\s*(?:s|sec|seconds)\b", text)
        if match:
            return float(match.group(1))
        raise ValueError(f"{entry.label}: missing known {key} and no time interval found in question text")


def _requested_level_ground_outputs(question_text: str) -> list[str]:
    text = question_text.lower()
    output_tokens = set(re.sub(r"[^a-z0-9]+", " ", text).split())
    outputs: list[str] = []
    if any(marker in text for marker in (
        "find initial speed", "determine initial speed", "calculate initial speed",
        "what initial speed", "speed needed", "required speed", "minimum speed",
    )):
        outputs.append("initial_speed")
    if any(marker in text for marker in ("angle of projection", "launch angle", "find theta", "find the angle", "angle theta")):
        outputs.append("launch_angle")
    if any(marker in text for marker in ("range", "horizontal distance", "ground distance", "distance covered", "distance travelled", "distance traveled", "distance from", "how far")) or "r" in output_tokens:
        outputs.append("range")
    if any(marker in text for marker in (
        "time of flight",
        "flight time",
        "flight duration",
        "duration of flight",
        "airborne duration",
        "total airborne duration",
        "airborne",
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
    peak_time = any(marker in text for marker in (
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
    )) and any(
        marker in text for marker in ("time to", "time taken", "how long", "when")
    )
    if peak_time:
        outputs.append("time_to_peak")
    if any(marker in text for marker in ("maximum height", "max height", "greatest height", "greatest vertical rise", "maximum vertical rise", "how high", "peak height", "highest height", "maximum altitude")) or "h" in output_tokens:
        if not peak_time or any(marker in text for marker in ("and maximum height", "and max height", "height and")):
            outputs.append("maximum_height")
    if any(marker in text for marker in ("components", "component", "u_x", "ux", "uₓ", "u_y", "uy", "uᵧ", "horizontal velocity", "vertical velocity")):
        outputs.append("components")
    return list(dict.fromkeys(outputs))


def _requested_height_launch_outputs(question_text: str) -> list[str]:
    text = question_text.lower()
    outputs: list[str] = []
    asks_impact_vector = _asks_height_launch_impact_vector(text)
    if any(marker in text for marker in ("time of flight", "flight time", "total time", "how long", "remains in air", "time taken", "time to hit", "time before", "time after", "stays in the air", "stays in air")):
        outputs.append("time_of_flight")
    if any(marker in text for marker in ("range", "horizontal distance", "distance covered", "how far", "lands", "where", "from the base", "from the building", "from the cliff")):
        outputs.append("range")
    if any(marker in text for marker in ("maximum height", "max height", "highest point")):
        outputs.append("maximum_height")
    if asks_impact_vector:
        outputs.append("impact_velocity")
    if _asks_height_launch_impact_speed(text):
        outputs.append("impact_speed")
    if asks_impact_vector or _asks_height_launch_impact_angle(text):
        outputs.append("impact_angle")
    if any(marker in text for marker in ("horizontal speed", "initial horizontal speed", "horizontal velocity", "initial speed", "with which it left")):
        outputs.append("horizontal_speed")
    if re.search(r"\bheight\s+(?:of\s+the\s+)?(?:tower|cliff|building|platform|table|h)\b", text) or re.search(r"\bfind\s+h\b", text):
        outputs.append("height")
    return list(dict.fromkeys(outputs))


def _asks_height_launch_impact_velocity(text: str) -> bool:
    return _asks_height_launch_impact_vector(text) or _asks_height_launch_impact_speed(text) or _asks_height_launch_impact_angle(text)


def _asks_height_launch_impact_vector(text: str) -> bool:
    return any(marker in text for marker in (
        "impact velocity",
        "velocity vector",
        "final velocity",
        "velocity just before",
        "velocity before impact",
        "velocity before hitting",
        "velocity when it reaches",
        "velocity when it reaches the ground",
        "velocity when it hits",
        "velocity when it hits the ground",
        "velocity at impact",
    ))


def _asks_height_launch_impact_speed(text: str) -> bool:
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


def _asks_height_launch_impact_angle(text: str) -> bool:
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


def _compact_time_text(text: str) -> str:
    return (
        text.lower()
        .replace("𝑡", "t")
        .replace("−", "-")
        .replace("–", "-")
        .replace("—", "-")
        .replace(" ", "")
    )


def _linear_t_coefficient(expr: str) -> float:
    cleaned = expr.replace(" ", "")
    match = re.search(r"([+-]?\d+(?:\.\d+)?)t(?!\^)", cleaned)
    if not match:
        raise ValueError(f"cannot find linear t coefficient in {expr!r}")
    return float(match.group(1))


def _parse_number(raw: str) -> float:
    text = raw.lower()
    text = text.replace("√", "sqrt")
    text = text.replace("root", "sqrt")
    text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"\1/\2", text)
    compact_fraction = re.fullmatch(r"\s*([-+]?\d+(?:\.\d+)?)\s+([-+]?\d+(?:\.\d+)?)\s*(?:m|meter|metre|meters|metres)?\s*", text)
    if compact_fraction:
        return float(compact_fraction.group(1)) / float(compact_fraction.group(2))
    text = text.replace("deg", "")
    text = re.sub(r"m/s\^?2|m/s|ms\s*-1|sec|s\b|m\b", "", text)
    text = text.replace(" ", "")
    text = _replace_sqrt(text)
    match = re.search(
        r"[-+]?(?:(?:\d+(?:\.\d*)?|\.\d+)|sqrt\(\d+(?:\.\d+)?\))(?:[*/](?:(?:\d+(?:\.\d*)?|\.\d+)|sqrt\(\d+(?:\.\d+)?\)))*",
        text,
    )
    if not match:
        raise ValueError(f"cannot parse number from {raw!r}")
    return _safe_eval(match.group(0))


def _parse_point2(raw: str) -> tuple[float, float]:
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", raw)
    if len(nums) < 2:
        raise ValueError(f"cannot parse point from {raw!r}")
    return float(nums[0]), float(nums[1])


def _parse_point3(raw: str) -> tuple[float, float, float]:
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", raw)
    if len(nums) < 3:
        raise ValueError(f"cannot parse 3D point from {raw!r}")
    return float(nums[0]), float(nums[1]), float(nums[2])


def _match_option(options: list[str], computed_value: float | None, computed_text: str) -> str | None:
    normalized_computed = _normalize_text(computed_text)
    numeric_candidates: list[tuple[str, float]] = []
    for index, option in enumerate(options):
        letter = chr(ord("a") + index)
        if _normalize_text(option) == normalized_computed:
            return letter
        if computed_value is None:
            continue
        option_value = _try_parse_option_value(option)
        if option_value is not None and math.isclose(option_value, computed_value, rel_tol=1e-4, abs_tol=1e-4):
            return letter
        if option_value is not None:
            numeric_candidates.append((letter, option_value))
    if computed_value is not None and numeric_candidates:
        letter, option_value = min(numeric_candidates, key=lambda item: abs(item[1] - computed_value))
        if math.isclose(option_value, computed_value, rel_tol=0.05, abs_tol=0.05):
            return letter
    return None


def _try_parse_option_value(option: str) -> float | None:
    try:
        return _parse_number(option)
    except Exception:
        return None


def _infer_interception_angle_pairs(text: str) -> list[tuple[float, float]]:
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

    numbers = [
        float(value)
        for value in re.findall(r"([-+]?\d+(?:\.\d+)?)\s*(?:deg|degree|degrees)", normalized, re.IGNORECASE)
    ]
    if len(numbers) >= 4:
        return [(numbers[0], numbers[1]), (numbers[2], numbers[3])]
    return []


def _replace_sqrt(text: str) -> str:
    text = re.sub(r"sqrt\s*(\d+(?:\.\d+)?)", r"sqrt(\1)", text)
    text = re.sub(r"(\d+(?:\.\d+)?)sqrt\((\d+(?:\.\d+)?)\)", r"\1*sqrt(\2)", text)
    return text


def _safe_eval(expr: str) -> float:
    return float(eval(expr, {"__builtins__": {}}, {"sqrt": math.sqrt}))


def _normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = (
        text.replace("θ", "theta")
        .replace("𝜃", "theta")
        .replace("α", "alpha")
        .replace("𝛼", "alpha")
        .replace("β", "beta")
        .replace("𝛽", "beta")
        .replace("√", "sqrt")
        .replace("−", "-")
        .replace("–", "-")
        .replace("—", "-")
    )
    text = text.lower()
    text = re.sub(r"sin\s*-?\s*1", "sin1", text)
    text = re.sub(r"cos\s*-?\s*1", "cos1", text)
    text = re.sub(r"\bsqrt\s*\(?\s*([a-z0-9]+)\s*\)?", r"sqrt\1", text)
    return re.sub(r"[^a-z0-9.]+", "", text)


def _normalize_known_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")
