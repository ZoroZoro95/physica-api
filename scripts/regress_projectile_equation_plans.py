#!/usr/bin/env python3
"""Regression checks for structured projectile equation plans."""

from __future__ import annotations

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.projectile_engine import build_solution_walkthrough, solve_ad_hoc_question
from core.projectile_engine import evaluate_manifest_entry


def main() -> None:
    cases = [
        (
            "velocity_change_interval",
            "A particle is projected with speed 20 m/s. Find magnitude of change in velocity from t=0 to t=0.5s. g=10 m/s^2.",
            "magnitude_change_in_velocity",
            [],
        ),
        (
            "velocity_angle_event_speed",
            "A particle is projected at 60 deg with speed 10 m/s. Later its velocity is at 30 deg. Find speed.",
            "speed_when_velocity_angle_matches",
            [],
        ),
        (
            "horizontal_throw_velocity_angle_time",
            "A stone is projected horizontally at 10 m/s. When does velocity make 45 deg with horizontal? g=10 m/s^2.",
            "time_when_velocity_angle_matches",
            [],
        ),
        (
            "velocity_perpendicular_to_initial_event",
            "A projectile has speed 40 m/s at angle 60 deg. Find x-coordinate when velocity is perpendicular to initial velocity. g=10 m/s^2.",
            "x_coordinate_at_event",
            ["v0=40 m/s", "angle=60deg", "g=10 m/s^2"],
        ),
    ]
    failures: list[str] = []
    for engine_case, question, requested_quantity, givens in cases:
        result = solve_ad_hoc_question(
            question_text=question,
            engine_case=engine_case,
            options=[],
            givens=givens,
            requested_quantity=requested_quantity,
        )
        if result.status != "passed":
            failures.append(f"{engine_case}: status={result.status} reason={result.reason}")
            continue
        if result.equation_plan.get("template_id") != "constant_acceleration_velocity_event":
            failures.append(f"{engine_case}: missing equation plan")
            continue
        if len(result.equation_plan.get("steps") or []) < 3:
            failures.append(f"{engine_case}: too few planned steps")
        walkthrough = build_solution_walkthrough(result)
        if not walkthrough["steps"] or walkthrough["steps"][0]["id"] != "invariant":
            failures.append(f"{engine_case}: walkthrough did not use equation plan")
            continue
        required_step_fields = {
            "student_goal",
            "teaching_goal",
            "visual_action",
            "concept_used",
            "equation",
            "trap_note",
            "camera_target_ids",
            "highlight_ids",
            "animation_focus",
            "objects_to_highlight",
            "known_values",
            "next_known_values",
            "voiceover_text",
        }
        for step in walkthrough["steps"]:
            missing = sorted(required_step_fields - set(step))
            if missing:
                failures.append(f"{engine_case} {step.get('id')}: missing walkthrough fields {missing}")
            if not step.get("student_goal"):
                failures.append(f"{engine_case} {step.get('id')}: empty student_goal")
            if not step.get("teaching_goal"):
                failures.append(f"{engine_case} {step.get('id')}: empty teaching_goal")
            if not step.get("visual_action"):
                failures.append(f"{engine_case} {step.get('id')}: empty visual_action")
            if not step.get("camera_target_ids"):
                failures.append(f"{engine_case} {step.get('id')}: empty camera_target_ids")
            if not step.get("highlight_ids"):
                failures.append(f"{engine_case} {step.get('id')}: empty highlight_ids")
            if not step.get("voiceover_text"):
                failures.append(f"{engine_case} {step.get('id')}: empty voiceover_text")

    height_question = (
        "Question 3: If a stone is thrown horizontally from a cliff with a velocity of 10 m/s, "
        "how long will it take to fall 45 m to the ground?"
    )
    height_result = solve_ad_hoc_question(
        question_text=height_question,
        engine_case=None,
        options=[],
        givens=[],
        requested_quantity="time_of_flight",
    )
    height_walkthrough = build_solution_walkthrough(height_result)
    height_text = " ".join(
        str(step.get(key) or "")
        for step in height_walkthrough.get("steps", [])
        for key in ("title", "concept_used", "explanation", "voiceover_text")
    ).lower()
    if height_result.status != "passed":
        failures.append(f"height_launch_time_of_flight: status={height_result.status} reason={height_result.reason}")
    if "same horizontal level" in height_text or "same height" in height_text:
        failures.append("height_launch_time_of_flight: walkthrough incorrectly claims same-height landing")

    derivation_question = "Derive the equation for time of flight for a projectile launched at angle theta with initial speed u"
    derivation_result = solve_ad_hoc_question(
        question_text=derivation_question,
        engine_case=None,
        options=[],
        givens=[],
        requested_quantity="time_of_flight_derivation",
    )
    derivation_plan = derivation_result.equation_plan or {}
    if derivation_result.status != "passed":
        failures.append(f"level_ground_time_of_flight_derivation: status={derivation_result.status} reason={derivation_result.reason}")
    if derivation_result.engine_case != "level_ground_time_of_flight_derivation":
        failures.append(f"level_ground_time_of_flight_derivation: engine={derivation_result.engine_case}")
    if "2u sin(theta)/g" not in (derivation_plan.get("final_answer") or ""):
        failures.append("level_ground_time_of_flight_derivation: missing symbolic final answer")
    if len(derivation_plan.get("steps") or []) < 4:
        failures.append("level_ground_time_of_flight_derivation: derivation plan has too few steps")
    derivation_walkthrough = build_solution_walkthrough(derivation_result)
    derivation_reveal_text = " ".join(
        " ".join(str(line) for line in reveal.get("formula_lines", [])) + " " + str(reveal.get("text") or "")
        for beat in derivation_walkthrough.get("explainer_beats", [])
        for reveal in beat.get("sub_reveals", [])
    )
    if "0 = T(u_y - gT/2)" not in derivation_reveal_text:
        failures.append("level_ground_time_of_flight_derivation: explainer skipped factoring the landing equation")
    if "u_y = gT/2" not in derivation_reveal_text or "T = 2u_y/g" not in derivation_reveal_text:
        failures.append("level_ground_time_of_flight_derivation: explainer skipped algebra from factor to time")
    if "not a square-root operation" not in derivation_reveal_text:
        failures.append("level_ground_time_of_flight_derivation: explainer does not clarify root meaning")

    staircase_question = (
        "A marble rolls down from top of a staircase with constant horizontal velocity 10 m/s. "
        "If each step is y = 1 meter high and x = 1 meter wide. To which step the marble will strike directly? "
        "(g = 9.8 m/s^2)"
    )
    staircase_result = solve_ad_hoc_question(
        question_text=staircase_question,
        engine_case=None,
        options=[],
        givens=[],
        requested_quantity=None,
    )
    staircase_walkthrough = build_solution_walkthrough(staircase_result)
    staircase_reveal_text = " ".join(
        " ".join(str(line) for line in reveal.get("formula_lines", [])) + " " + str(reveal.get("text") or "")
        for beat in staircase_walkthrough.get("explainer_beats", [])
        for reveal in beat.get("sub_reveals", [])
    )
    staircase_titles = [str(beat.get("title") or "") for beat in staircase_walkthrough.get("explainer_beats", [])]
    if staircase_result.engine_case != "staircase_collision":
        failures.append(f"staircase_collision: engine={staircase_result.engine_case}")
    staircase_givens = set(staircase_result.equation_plan.get("givens") or [])
    if "step_height=1m" not in staircase_givens or "step_width=1m" not in staircase_givens:
        failures.append(f"staircase_collision: missing staircase dimensions in givens {sorted(staircase_givens)!r}")
    if "Find the flight time" in staircase_titles:
        failures.append("staircase_collision: incorrectly labels t_n as total flight time")
    if "T(u_y - gT/2)" in staircase_reveal_text:
        failures.append("staircase_collision: leaked level-ground root explanation into staircase walkthrough")
    for expected in ("Let n be the step number", "t_n = n w / v_x", "y_n = 1/2 g t_n^2", "direct hit condition: y_n >= n h", "first whole number"):
        if expected not in staircase_reveal_text:
            failures.append(f"staircase_collision: missing explainer phrase {expected!r}")

    combined_question = "A ball is thrown at u=16 m/s at 53 deg. Find range and time of flight."
    combined_result = solve_ad_hoc_question(
        question_text=combined_question,
        engine_case=None,
        options=[],
        givens=[],
        requested_quantity=None,
    )
    combined_plan = combined_result.equation_plan or {}
    if combined_result.engine_case != "level_ground_multi_quantity":
        failures.append(f"level_ground_range_and_time: engine={combined_result.engine_case}")
    if "T =" not in (combined_result.computed_text or "") or "R =" not in (combined_result.computed_text or ""):
        failures.append(f"level_ground_range_and_time: incomplete answer={combined_result.computed_text!r}")
    if len(combined_plan.get("steps") or []) < 5:
        failures.append("level_ground_range_and_time: plan has too few steps")

    four_quantity_question = (
        "A projectile is launched at 20 m/s at 30deg. Find range, time of flight, "
        "maximum height, and velocity components. Take g = 10 m/s^2."
    )
    four_quantity_result = solve_ad_hoc_question(
        question_text=four_quantity_question,
        engine_case=None,
        options=[],
        givens=[],
        requested_quantity=None,
    )
    if four_quantity_result.engine_case != "level_ground_multi_quantity":
        failures.append(f"level_ground_multi_quantity: engine={four_quantity_result.engine_case}")
    for expected in ("u_x =", "u_y =", "T =", "H =", "R ="):
        if expected not in (four_quantity_result.computed_text or ""):
            failures.append(f"level_ground_multi_quantity: missing {expected} in {four_quantity_result.computed_text!r}")

    manifest = json.loads((ROOT / "questions/manifest/projectile_dpp_manifest.json").read_text(encoding="utf-8"))
    for entry in manifest:
        result = evaluate_manifest_entry(entry)
        if result.status != "passed":
            failures.append(f"{result.label}: manifest case no longer passes")
            continue
        if not result.equation_plan:
            failures.append(f"{result.label} {result.engine_case}: missing equation plan")
            continue
        if result.equation_plan.get("engine_case") != result.engine_case:
            failures.append(f"{result.label}: plan engine mismatch")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        raise SystemExit(1)
    print("PASS projectile equation plan regressions")


if __name__ == "__main__":
    main()
