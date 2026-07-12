from __future__ import annotations

import re

from .models import EvaluationResult
from .visual_contract import attach_beat_visual_spec


def build_solution_walkthrough(result: EvaluationResult) -> dict:
    if result.equation_plan:
        steps = _equation_plan_walkthrough(result)
    else:
        builders = {
            "velocity_change_interval": _velocity_change_interval,
            "staircase_collision": _staircase_collision,
            "two_inclines_perpendicular_launch_impact": _two_inclines,
            "motion_on_smooth_incline_perpendicular_to_slope": _smooth_incline_speed,
        }
        builder = builders.get(result.engine_case, _generic_walkthrough)
        steps = builder(result)
    return {
        "engine_case": result.engine_case,
        "answer": result.computed_text,
        "matched_option": result.predicted_option_letter,
        "diagram_model": _diagram_model(result),
        "steps": steps,
        "explainer_beats": _build_explainer_beats(result, steps),
    }


def _step(
    *,
    id: str,
    title: str,
    formula: str,
    explanation: str,
    animation_intent: str,
    focus_ids: list[str] | None = None,
    student_goal: str = "",
    teaching_goal: str = "",
    visual_action: str = "",
    concept_used: str = "",
    equation: str = "",
    substitution: str = "",
    calculation: str = "",
    result: str = "",
    trap_note: str = "",
    camera_target_ids: list[str] | None = None,
    highlight_ids: list[str] | None = None,
    known_values: list[str] | None = None,
    next_known_values: list[str] | None = None,
    animation_focus: str = "",
    objects_to_highlight: list[str] | None = None,
    voiceover_text: str = "",
) -> dict:
    focus = focus_ids or []
    action = visual_action or _visual_action(id=id, title=title, formula=formula, focus_ids=focus, animation_intent=animation_intent)
    highlights = highlight_ids or objects_to_highlight or focus
    camera_targets = camera_target_ids or _camera_targets_for_action(action, focus)
    spoken = voiceover_text or _voiceover(title=title, explanation=explanation, formula=formula, result=result)
    return {
        "id": id,
        "title": title,
        "student_goal": student_goal or _default_student_goal(title),
        "teaching_goal": teaching_goal or student_goal or _default_student_goal(title),
        "visual_action": action,
        "concept_used": concept_used or _concept_from_formula(formula),
        "formula": formula,
        "equation": equation or formula,
        "substitution": substitution,
        "calculation": calculation,
        "result": result,
        "explanation": explanation,
        "trap_note": trap_note or _trap_note(id=id, title=title, formula=formula, explanation=explanation, focus_ids=focus),
        "animation_intent": animation_intent,
        "focus_ids": focus,
        "camera_target_ids": camera_targets,
        "highlight_ids": highlights,
        "animation_focus": animation_focus or _animation_focus(animation_intent, focus),
        "objects_to_highlight": highlights,
        "known_values": known_values or [],
        "next_known_values": next_known_values or [],
        "voiceover_text": spoken,
    }


def _velocity_change_interval(result: EvaluationResult) -> list[dict]:
    return [
        _step(
            id="setup",
            title="Separate what can change",
            formula="v_x = constant, v_y changes under gravity",
            explanation="In ideal projectile motion, gravity is the only acceleration. It changes only the vertical component of velocity.",
            animation_intent="show_projectile_velocity_components",
            focus_ids=["ball", "v_x", "v_y"],
        ),
        _step(
            id="delta_v",
            title="Use acceleration over time",
            formula="|Delta v| = g Delta t",
            explanation=_trace_or(result, 1, "Multiply gravity by the given time interval to get the magnitude of velocity change."),
            animation_intent="show_vertical_velocity_change_interval",
            focus_ids=["v_y"],
        ),
        _step(
            id="answer",
            title="Match the option",
            formula=result.computed_text or "",
            explanation=f"The required magnitude is {result.computed_text}.",
            animation_intent="highlight_final_answer",
            focus_ids=["answer"],
        ),
    ]


def _equation_plan_walkthrough(result: EvaluationResult) -> list[dict]:
    plan = result.equation_plan
    steps: list[dict] = []
    known_values = list(plan.get("givens") or [])
    if plan.get("invariant"):
        invariant_focus = _invariant_focus_ids(plan)
        invariant_explanation = _invariant_explanation(plan)
        steps.append(
            _step(
                id="invariant",
                title="Given and what to find",
                formula="",
                explanation=invariant_explanation,
                animation_intent="show_key_projectile_invariant",
                focus_ids=invariant_focus,
                student_goal=_invariant_student_goal(plan),
                concept_used=_invariant_concept(plan),
                equation="",
                result="",
                animation_focus=_focus_sentence(invariant_focus),
                objects_to_highlight=invariant_focus,
                known_values=[],
                next_known_values=known_values,
            )
        )
    for item in plan.get("steps", []):
        formula = str(item.get("equation") or "")
        substitution = str(item.get("substitution") or "")
        explanation = str(item.get("explanation") or "")
        calculation = _calculation_from_substitution(substitution, result)
        result_text = _result_for_step(item, result)
        next_known_values = _append_known_value(known_values, result_text)
        steps.append(
            _step(
                id=str(item.get("id") or f"step_{len(steps) + 1}"),
                title=str(item.get("title") or "Solve step"),
                formula=formula,
                explanation=explanation,
                animation_intent=f"equation_plan_{item.get('id') or 'step'}",
                focus_ids=list(item.get("focus_ids") or ["solution"]),
                student_goal=_student_goal_for_plan_step(item, plan),
                teaching_goal=_teaching_goal_for_plan_step(item, plan),
                concept_used=_concept_from_formula(formula) or str(plan.get("invariant") or ""),
                equation=formula,
                substitution=substitution,
                calculation=calculation,
                result=result_text,
                animation_focus=_focus_sentence(list(item.get("focus_ids") or ["solution"])),
                objects_to_highlight=list(item.get("focus_ids") or ["solution"]),
                known_values=known_values,
                next_known_values=next_known_values,
            )
        )
        known_values = next_known_values
    if plan.get("exam_takeaway"):
        steps.append(
            _step(
                id="takeaway",
                title="Exam takeaway",
                formula=str(plan.get("final_answer") or result.computed_text or ""),
                explanation=str(plan.get("exam_takeaway")),
                animation_intent="highlight_final_answer",
                focus_ids=["answer"],
                student_goal="Lock the final answer to the exact quantity asked.",
                concept_used="Answer check",
                equation=str(plan.get("final_answer") or result.computed_text or ""),
                result=str(plan.get("final_answer") or result.computed_text or ""),
                animation_focus="Highlight the final measured or computed quantity.",
                objects_to_highlight=["answer"],
                known_values=known_values,
                next_known_values=_append_known_value(known_values, str(plan.get("final_answer") or result.computed_text or "")),
            )
        )
    return steps or _generic_walkthrough(result)


def _default_student_goal(title: str) -> str:
    lowered = title.lower()
    if "answer" in lowered or "option" in lowered:
        return "Match the calculation to the requested answer."
    if "identify" in lowered or "model" in lowered or "setup" in lowered:
        return "Turn the word problem into a physics model."
    if "compute" in lowered or "solve" in lowered:
        return "Substitute known values and simplify carefully."
    return "Move one clear step closer to the requested quantity."


def _concept_from_formula(formula: str) -> str:
    lowered = formula.lower()
    if not formula:
        return ""
    if "projected normal to the incline" in lowered or "normal to the incline" in lowered:
        return "Use incline axes: tangent to the plane and normal to the plane."
    if "s_p" in lowered and "s_q" in lowered:
        return "Compare the two particles along the inclined plane."
    if "n_p" in lowered or "normal separation" in lowered or lowered.startswith("0 = ut"):
        return "Use normal-to-plane motion for the collision condition."
    if lowered.startswith("0 =") and "h +" in lowered and "gt^2" in lowered:
        return "Use vertical position measured from the ground."
    if lowered.startswith("0 =") and "gt^2" in lowered:
        return "Use vertical displacement with launch and landing at the same height."
    if "sqrt" in lowered and "2gh" in lowered:
        return "Use the positive root of the vertical-motion quadratic."
    if lowered.startswith("t =") or " t =" in lowered:
        return "Use vertical motion to find the flight time."
    if lowered.startswith("r =") or " r =" in lowered:
        return "Use horizontal displacement to find range."
    if "delta v" in lowered or "a =" in lowered:
        return "Constant acceleration changes velocity linearly with time."
    if "sin" in lowered or "cos" in lowered or "tan" in lowered:
        return "Resolve vectors into components using trigonometry."
    if "dot" in lowered or "perpendicular" in lowered:
        return "Use vector geometry to convert a direction condition into algebra."
    if "x =" in lowered or "y =" in lowered:
        return "Use independent horizontal and vertical motion equations."
    if "sqrt" in lowered or "^2" in lowered or "v^2" in lowered:
        return "Use energy-like or squared kinematic relations to remove time."
    return "Apply the equation that connects the diagram to the unknown."


def _invariant_focus_ids(plan: dict) -> list[str]:
    engine_case = str(plan.get("engine_case") or "")
    if engine_case == "projectile_collides_with_sliding_particle_on_incline":
        return ["point:launch", "surface:inclined_plane", "incline:normal_axis", "incline:tangent_axis", "actor:projectile_p", "actor:slider_q", "quantity:u", "vector:u"]
    if engine_case == "inclined_plane_max_normal_distance_velocity_component":
        return ["surface:inclined_plane", "incline:normal_axis", "velocity:normal_component", "trajectory:path", "answer"]
    if engine_case == "motion_on_smooth_incline_perpendicular_to_slope":
        return ["surface:inclined_plane", "incline:tangent_axis", "incline:normal_axis", "vector:u", "quantity:u", "answer"]
    if engine_case == "inclined_plane_right_angle_impact_condition":
        return ["surface:inclined_plane", "incline:tangent_axis", "point:impact", "velocity:tangent_component", "answer"]
    if engine_case == "two_inclines_perpendicular_launch_impact":
        return ["plane_OA", "plane_OB", "point:P", "point:Q", "vector:u", "quantity:u"]
    if engine_case.startswith("height_launch"):
        return ["point:launch", "point:impact", "event:impact", "quantity:launch_height", "trajectory:path"]
    unknown = str(plan.get("unknown") or "").lower()
    goal = str(plan.get("goal") or "").lower()
    text = f"{unknown} {goal}"
    if "velocity" in text or "speed" in text:
        return ["vector:u", "vector:vx", "vector:vy"]
    if "range" in text or "distance" in text:
        return ["quantity:R", "point:landing", "trajectory:path"]
    if "height" in text or "peak" in text or "apex" in text:
        return ["event:apex", "quantity:H", "trajectory:path"]
    if "time" in text:
        return ["quantity:T", "event:landing", "trajectory:path"]
    return ["setup", "trajectory:path"]


def _invariant_concept(plan: dict) -> str:
    if plan.get("engine_case") == "projectile_collides_with_sliding_particle_on_incline":
        return "Resolve motion along and normal to the inclined plane."
    unknown = str(plan.get("unknown") or "").lower()
    if "range" in unknown:
        return "Range is the horizontal displacement from launch to landing."
    if "height" in unknown:
        return "Maximum height is found where vertical velocity becomes zero."
    if "time" in unknown:
        return "Flight time is fixed by vertical motion."
    if "velocity" in unknown or "speed" in unknown:
        return "Velocity is resolved into horizontal and vertical components."
    return "Identify the quantity asked before choosing equations."


def _invariant_student_goal(plan: dict) -> str:
    engine_case = str(plan.get("engine_case") or "")
    unknown = str(plan.get("unknown") or "the requested quantity").strip().replace("_", " ")
    if engine_case.startswith("height_launch"):
        return "Separate the horizontal motion from the vertical fall before solving the requested quantities."
    if engine_case == "projectile_collides_with_sliding_particle_on_incline":
        return "Set up both particles on the same incline axes before comparing their positions."
    if engine_case == "two_inclines_perpendicular_launch_impact":
        return "Mark both inclined planes and the perpendicular launch/impact directions before resolving velocity."
    if "range" in unknown.lower():
        return "Identify the launch and landing points before using the range relation."
    if "height" in unknown.lower():
        return "Locate the apex condition before calculating maximum height."
    if "time" in unknown.lower():
        return "Use vertical motion to decide the flight time before horizontal distance."
    if "velocity" in unknown.lower() or "speed" in unknown.lower():
        return "Resolve velocity into components before calculating the requested speed or angle."
    return f"Identify the givens and the target quantity: {unknown}."


def _invariant_explanation(plan: dict) -> str:
    invariant = str(plan.get("invariant") or "").strip()
    goal = str(plan.get("goal") or "Identify the physics relation that controls the event.").strip()
    if invariant and invariant != goal:
        return f"{goal} {invariant}"
    return goal


def _animation_focus(animation_intent: str, focus_ids: list[str]) -> str:
    if focus_ids:
        return _focus_sentence(focus_ids)
    return animation_intent.replace("_", " ") if animation_intent else "Show the relevant part of the setup."


def _focus_sentence(focus_ids: list[str]) -> str:
    labels = [str(item).replace("_", " ").replace(":", " ") for item in focus_ids[:4]]
    if not labels:
        return "Keep the full setup visible."
    return f"Focus the animation on {', '.join(labels)}."


def _visual_action(*, id: str, title: str, formula: str, focus_ids: list[str], animation_intent: str) -> str:
    lowered = " ".join([id, title, formula, animation_intent, " ".join(focus_ids)]).lower()
    physics_text = " ".join([id, title, formula, " ".join(focus_ids)]).lower()
    if (id == "invariant" or "given and what to find" in lowered) and ("quantity:r" in physics_text or "range" in lowered):
        return "highlight_range"
    if id == "invariant" or "given and what to find" in lowered:
        return "show_full_scene"
    if "projection speed" in lowered or ("quantity:u" in physics_text and ("solve" in lowered or "answer" in lowered or "state" in lowered)):
        return "zoom_launch_vector"
    if "incline:normal_axis" in physics_text and ("read_diagram" in physics_text or "normal to the incline" in physics_text or "projected normal" in physics_text):
        return "show_incline_axes"
    if "incline:tangent_axis" in physics_text and "trajectory:q" in physics_text:
        return "compare_incline_motion"
    if "n_p" in physics_text or "normal separation" in physics_text or ("incline:normal_axis" in physics_text and "point:collision" in physics_text):
        return "show_normal_return"
    if "event:collision" in physics_text or "point:collision" in physics_text:
        return "highlight_collision"
    if "range" in lowered or "quantity:r" in lowered or "distance" in lowered:
        return "highlight_range"
    if "event:impact" in physics_text or "ground-impact" in lowered or "quantity:launch_height" in physics_text:
        return "highlight_vertical_motion"
    if "same height" in lowered or "delta y" in lowered or "delta_y" in lowered or "vertical displacement" in lowered:
        return "highlight_same_height"
    if "sqrt(2h" in lowered or "quantity:h" in lowered or " h/" in lowered or " h)" in lowered:
        return "highlight_apex"
    if "time" in lowered or "flight" in lowered or "quantity:t" in lowered:
        return "highlight_vertical_motion"
    if "height" in lowered or "apex" in lowered or "peak" in lowered or "quantity:h" in lowered:
        return "highlight_apex"
    if (
        "component" in lowered
        or "resolve" in lowered
        or "vector:vx" in lowered
        or "vector:vy" in lowered
        or "quantity:ux" in lowered
        or "quantity:uy" in lowered
        or "v_x" in lowered
        or "v_y" in lowered
        or "u_x" in lowered
        or "u_y" in lowered
    ):
        return "zoom_launch_vector"
    if "time" in lowered or "flight" in lowered or "vertical" in lowered or "y =" in lowered or "v_y" in lowered:
        return "highlight_vertical_motion"
    if "impact" in lowered or "final velocity" in lowered or "resultant" in lowered or "speed" in lowered:
        return "show_impact_velocity_triangle"
    if "answer" in lowered or "takeaway" in lowered:
        return "highlight_final_answer"
    if id in {"invariant", "identify", "setup", "model"} or "given" in lowered or "setup" in lowered:
        return "show_full_scene"
    return "focus_relevant_step"


def _camera_targets_for_action(action: str, focus_ids: list[str]) -> list[str]:
    if action == "show_full_scene":
        return ["full_scene"]
    if action == "show_incline_axes":
        return ["setup", "surface:inclined_plane", "incline:normal_axis", "incline:tangent_axis"]
    if action == "compare_incline_motion":
        return ["surface:inclined_plane", "incline:tangent_axis", "trajectory:p", "trajectory:q"]
    if action == "show_normal_return":
        return ["incline:normal_axis", "trajectory:p", "point:collision"]
    if action == "highlight_collision":
        return ["point:collision", "event:collision"]
    if action == "zoom_launch_vector":
        return ["setup", "point:launch", "vector:u"]
    if action == "highlight_vertical_motion":
        return ["event:apex", "event:landing", "quantity:T"]
    if action == "highlight_same_height":
        return ["point:launch", "point:landing"]
    if action == "highlight_range":
        return ["quantity:R", "point:landing", "point:impact"]
    if action == "highlight_apex":
        return ["event:apex", "quantity:H"]
    if action == "show_impact_velocity_triangle":
        return ["point:impact", "point:landing", "vector:v"]
    if action == "highlight_final_answer":
        return ["answer", *focus_ids[:2]]
    return focus_ids[:3] or ["full_scene"]


def _trap_note(*, id: str, title: str, formula: str, explanation: str, focus_ids: list[str]) -> str:
    lowered = " ".join([id, title, formula, explanation, " ".join(focus_ids)]).lower()
    if "vertical" in lowered and ("time" in lowered or "flight" in lowered):
        return "Time of flight is decided by vertical motion; horizontal motion is used after time is known."
    if "horizontal launch" in lowered or ("leaves horizontally" in lowered and ("u_y" in lowered or "uy" in lowered)):
        return "Horizontal launch means the initial vertical component is zero; do not introduce an angle decomposition."
    if ("horizontal velocity" in lowered or "v_x" in lowered or "u_x" in lowered) and ("constant" in lowered or "no horizontal force" in lowered):
        return "Horizontal velocity stays constant because horizontal acceleration is zero."
    if "u_x" in lowered or "u_y" in lowered or "v_x" in lowered or "v_y" in lowered:
        return "Check whether the angle is measured from horizontal or vertical before choosing sin/cos."
    if "same height" in lowered or "delta y" in lowered:
        return "Launch and landing at the same height means vertical displacement is zero, not height is zero."
    if "incline" in lowered and ("range" in lowered or "distance" in lowered):
        return "Range on an incline is measured along the inclined surface, not horizontally."
    if "relative" in lowered or "train" in lowered:
        return "Use one frame consistently; mixing ground and train-frame quantities breaks the equation."
    if "velocity" in lowered and ("resultant" in lowered or "speed" in lowered):
        return "If the question asks speed or velocity magnitude, combine components; do not report only v_y."
    return ""


def _voiceover(*, title: str, explanation: str, formula: str, result: str) -> str:
    parts = [title.strip()]
    if explanation:
        parts.append(explanation.strip().split("\n")[0])
    if formula:
        parts.append(f"We use {formula}.")
    if result:
        parts.append(f"This gives {result}.")
    return " ".join(part for part in parts if part)


def _calculation_from_substitution(substitution: str, result: EvaluationResult) -> str:
    if not substitution:
        return ""
    if result.computed_text and result.computed_text in substitution:
        return substitution
    return substitution


def _result_for_step(item: dict, result: EvaluationResult) -> str:
    step_id = str(item.get("id") or "").lower()
    title = str(item.get("title") or "").lower()
    if "answer" in step_id or "answer" in title or "compute" in title or "state" in title:
        return result.computed_text or ""
    return ""


def _student_goal_for_plan_step(item: dict, plan: dict) -> str:
    title = str(item.get("title") or "").lower()
    unknown = str(plan.get("unknown") or "the requested quantity")
    if "choose" in title or "relation" in title:
        return f"Choose the relation that can lead to {unknown}."
    if "resolve" in title or "component" in title:
        return "Break the motion into components so each direction becomes simple."
    if "condition" in title:
        return "Translate the event described in words into an equation."
    if "compute" in title or "answer" in title:
        return f"Compute {unknown} and keep units/options consistent."
    return f"Use this step to move toward {unknown}."


def _teaching_goal_for_plan_step(item: dict, plan: dict) -> str:
    if plan.get("engine_case") == "projectile_collides_with_sliding_particle_on_incline":
        step_id = str(item.get("id") or "").lower()
        if step_id == "read_diagram":
            return "Extract the hidden condition from the diagram: P is launched normal to the plane and Q stays on the plane."
        if step_id == "along_plane":
            return "Show why the along-plane motion of P and Q stays synchronized."
        if step_id in {"normal_plane", "collision_condition"}:
            return "Use normal separation to turn the collision event into an equation for u."
        if step_id == "solve_u":
            return "Substitute the collision time and incline angle without skipping the algebra."
        if step_id == "answer":
            return "Report the required projection speed of P."
    title = str(item.get("title") or "").lower()
    equation = str(item.get("equation") or "").lower()
    focus = " ".join(str(item) for item in (item.get("focus_ids") or [])).lower()
    unknown = str(plan.get("unknown") or "the requested quantity")
    if "same height" in title or "delta_y" in focus:
        return "Use the diagram condition that launch and landing have the same vertical level."
    if "range" in title or "r =" in equation or "quantity:r" in focus:
        return "Connect the horizontal displacement in the diagram to the requested range."
    if "time" in title or equation.startswith("t") or " t" in equation or "quantity:t" in focus:
        return "Use vertical motion to find the time variable before using horizontal motion."
    if "height" in title or "peak" in title or "apex" in title or "quantity:h" in focus:
        return "Use the highest-point condition to locate the peak of the motion."
    if "resolve" in title or "component" in title or "sin" in equation or "cos" in equation:
        return "Show why the initial velocity must be split before applying one-dimensional equations."
    if "answer" in title or "compute" in title:
        return f"Substitute cleanly and report {unknown} with the correct units."
    return f"Make the next algebra step toward {unknown} explicit."


def _append_known_value(known_values: list[str], value: str) -> list[str]:
    cleaned = value.strip()
    if not cleaned:
        return list(known_values)
    existing = {item.strip().lower() for item in known_values}
    if cleaned.lower() in existing:
        return list(known_values)
    return [*known_values, cleaned]


def _staircase_collision(result: EvaluationResult) -> list[dict]:
    return [
        _step(
            id="model",
            title="Model the nth step face",
            formula="x_n = n w,  t_n = x_n / v_x",
            explanation="The marble leaves horizontally, so horizontal motion is uniform. At the nth vertical face, the horizontal distance is n step widths.",
            animation_intent="show_staircase_with_nth_vertical_face",
            focus_ids=["staircase", "marble", "nth_step"],
        ),
        _step(
            id="drop",
            title="Compute the vertical drop",
            formula="y_n = (1/2) g t_n^2",
            explanation=_trace_or(result, 1, "Substitute the time at the nth face into vertical free fall."),
            animation_intent="animate_parabolic_drop_against_steps",
            focus_ids=["trajectory"],
        ),
        _step(
            id="first_hit",
            title="Choose the first integer step",
            formula="0.049 n^2 >= n",
            explanation=_trace_or(result, 3, f"The first direct strike is {result.computed_text}."),
            animation_intent="highlight_first_hit_step",
            focus_ids=["step_21", "answer"],
        ),
    ]


def _two_inclines(result: EvaluationResult) -> list[dict]:
    return [
        _step(
            id="geometry",
            title="Fix the diagram orientation",
            formula="OA direction = 150 deg, OB direction = 60 deg",
            explanation="The 30 deg plane is OA on the left, so its ray from O points up-left at 150 deg from +x. OB points up-right at 60 deg. This orientation is part of the problem, not a decorative detail.",
            animation_intent="show_two_inclines_and_perpendicular_velocity_arrows",
            focus_ids=["plane_OA", "plane_OB", "v_initial"],
        ),
        _step(
            id="horizontal_component",
            title="Keep horizontal velocity fixed",
            formula="v_x = u cos(60 deg)",
            explanation="The launch is perpendicular to OA, so its direction is 60 deg above +x. The horizontal component remains constant during the flight.",
            animation_intent="show_constant_horizontal_component",
            focus_ids=["v_x"],
        ),
        _step(
            id="impact_speed",
            title="Resolve final velocity",
            formula="v_Q = |v_x / cos(30 deg)|",
            explanation="At Q the velocity is perpendicular to OB, so it points 30 deg below +x. Match its horizontal component to the constant v_x to get the impact speed.",
            animation_intent="show_final_velocity_perpendicular_to_OB",
            focus_ids=["v_final", "answer"],
        ),
    ]


def _diagram_model(result: EvaluationResult) -> dict:
    if result.diagram_model and result.diagram_model.get("kind") not in {None, "", "none"}:
        model = dict(result.diagram_model)
        if result.engine_case == "two_inclines_perpendicular_launch_impact":
            for vector in model.get("vectors", []):
                if vector.get("id") == "vQ" and result.computed_text:
                    vector["magnitude"] = result.computed_text
        return model
    if result.engine_case == "two_inclines_perpendicular_launch_impact":
        return {
            "kind": "two_inclines",
            "coordinate_frame": {
                "x_axis": "right",
                "y_axis": "up",
                "origin": "O",
                "angle_reference": "positive x axis",
            },
            "points": {
                "O": {"role": "intersection", "position": [0, 0, 0]},
                "A": {"role": "point_on_surface", "surface_id": "OA", "ray_parameter": 1.0},
                "B": {"role": "point_on_surface", "surface_id": "OB", "ray_parameter": 1.0},
                "P": {"role": "launch_point", "surface_id": "OA", "ray_parameter": 0.45},
                "Q": {"role": "impact_point", "surface_id": "OB", "ray_parameter": 0.62},
            },
            "surfaces": [
                {
                    "id": "OA",
                    "kind": "incline",
                    "passes_through": "O",
                    "side": "left",
                    "angle_to_horizontal_deg": 30,
                    "ray_direction_deg": 150,
                },
                {
                    "id": "OB",
                    "kind": "incline",
                    "passes_through": "O",
                    "side": "right",
                    "angle_to_horizontal_deg": 60,
                    "ray_direction_deg": 60,
                },
            ],
            "vectors": [
                {
                    "id": "u",
                    "kind": "initial_velocity",
                    "anchor": "P",
                    "constraint": "perpendicular_to",
                    "target": "OA",
                    "direction_deg": 60,
                    "magnitude": "10sqrt(3) m/s",
                },
                {
                    "id": "vQ",
                    "kind": "impact_velocity",
                    "anchor": "Q",
                    "constraint": "perpendicular_to",
                    "target": "OB",
                    "direction_deg": -30,
                    "magnitude": result.computed_text,
                },
                {
                    "id": "vx",
                    "kind": "component",
                    "anchor": "P",
                    "direction_deg": 0,
                    "description": "constant horizontal component",
                },
            ],
            "constraints": [
                "P lies on OA",
                "Q lies on OB",
                "initial velocity is perpendicular to OA",
                "impact velocity is perpendicular to OB",
            ],
            "validation_warnings": [],
        }
    return {"kind": "none"}


def _build_explainer_beats(result: EvaluationResult, steps: list[dict]) -> list[dict]:
    conceptual = _conceptual_explainer_beats(result)
    if conceptual:
        return [_attach_conceptual_beat_visual_spec(result, beat) for beat in conceptual]
    compact_steps = _compact_explainer_steps(result, steps)
    return [_generic_explainer_beat(result, step, index) for index, step in enumerate(compact_steps)]


def _conceptual_explainer_beats(result: EvaluationResult) -> list[dict]:
    if result.engine_case == "height_launch_horizontal_scenario":
        return _horizontal_launch_scenario_conceptual_beats(result)
    if result.engine_case == "projectile_collides_with_sliding_particle_on_incline":
        return _incline_collision_conceptual_beats(result)
    return []


def _horizontal_launch_scenario_conceptual_beats(result: EvaluationResult) -> list[dict]:
    plan = result.equation_plan or {}
    givens = _givens_map(plan.get("givens") or [])
    speed = givens.get("vx") or givens.get("v0") or givens.get("u") or "u"
    height = givens.get("height") or givens.get("h") or "h"
    time_line = _strip_terminal_period(
        _trace_line_containing(result, "Vertical motion gives")
        or f"h = 1/2 gT^2, so T comes from h = {height}"
    )
    vy_line = _strip_terminal_period(
        _trace_line_containing(result, "Impact vertical velocity")
        or "v_y = -gT"
    )
    speed_line = _strip_terminal_period(
        _trace_line_containing(result, "Impact speed")
        or "|v| = sqrt(v_x^2 + v_y^2)"
    )
    angle_line = _strip_terminal_period(
        _trace_line_containing(result, "velocity angle")
        or "theta = tan^-1(|v_y|/v_x)"
    )
    return [
        _conceptual_beat(
            step_id="horizontal_launch_setup",
            title="Recognize this as a horizontal launch",
            learner_message=(
                f"The ball leaves the tower horizontally with speed {speed}. The useful picture is a tower height, "
                "a horizontal launch velocity, and gravity downward."
            ),
            sub_reveals=[
                _sub_reveal(
                    "givens",
                    "Mark the launch speed, tower height, and gravity direction.",
                    "Show the tower, horizontal velocity, height marker, and downward gravity.",
                    [f"u = {speed}", f"h = {height}"],
                    ["point:launch", "quantity:launch_height", "velocity:x_component", "vector:g"],
                    ["velocity:x_component", "quantity:launch_height", "vector:g"],
                ),
            ],
            visual_action="show_launch_setup",
            visual_focus=["point:launch", "quantity:launch_height", "velocity:x_component", "vector:g"],
            visible_vectors=["*:vx", "*:a"],
            overlays=["show_height_marker"],
            motion={"mode": "static"},
            why_it_matters="Horizontal launch means the vertical fall starts from rest vertically, while horizontal velocity is already known.",
            visual_director_beat="setup",
            hide_live_values=True,
        ),
        _conceptual_beat(
            step_id="horizontal_launch_time",
            title="Use vertical motion to find time of fall",
            learner_message="The fall time is decided by the vertical drop, not by the horizontal speed.",
            sub_reveals=[
                _sub_reveal(
                    "vertical_relation",
                    "Use the tower height as the vertical displacement.",
                    "Highlight the drop height and gravity.",
                    ["h = 1/2 gT^2", time_line],
                    ["quantity:launch_height", "vector:g", "quantity:T"],
                    ["quantity:launch_height", "vector:g"],
                ),
            ],
            visual_action="highlight_vertical_motion",
            visual_focus=["quantity:launch_height", "vector:g", "quantity:T"],
            visible_vectors=["*:a"],
            overlays=["show_height_marker", "show_timer"],
            motion={"mode": "static"},
            why_it_matters="This prevents mixing horizontal distance into a vertical free-fall time calculation.",
            visual_director_beat="time_of_flight",
            hide_live_values=True,
        ),
        _conceptual_beat(
            step_id="horizontal_launch_impact_vy",
            title="Find vertical impact velocity",
            learner_message="As the ball moves, horizontal velocity stays constant while gravity grows the downward velocity.",
            sub_reveals=[
                _sub_reveal(
                    "fall_motion",
                    "Watch the ball follow the path while the downward component grows.",
                    "Animate the trajectory and show the changing velocity components.",
                    ["v_y = gt", vy_line],
                    ["trajectory:path", "point:landing", "event:impact", "velocity:impact_y_component", "velocity:x_component"],
                    ["velocity:impact_y_component", "velocity:x_component"],
                ),
            ],
            visual_action="show_impact_vertical_velocity",
            visual_focus=["trajectory:path", "point:landing", "event:impact", "velocity:impact_y_component", "velocity:x_component"],
            visible_vectors=["*:vx", "*:vy"],
            overlays=["show_trajectory", "show_motion_progress", "show_velocity_components"],
            motion={"mode": "partial", "event": "impact"},
            why_it_matters="The vertical impact component is not present at launch; it is built by gravity during the fall.",
            visual_director_beat="impact_vertical_velocity",
            hide_live_values=True,
        ),
        _conceptual_beat(
            step_id="horizontal_launch_impact_speed",
            title="Combine velocity components at impact",
            learner_message="Just before impact, the velocity is a right triangle: horizontal component, vertical component, and resultant.",
            sub_reveals=[
                _sub_reveal(
                    "velocity_triangle",
                    "Freeze at impact and combine the two perpendicular velocity components.",
                    "Show the velocity triangle at impact.",
                    ["v_x = u", "v_y = gt", "|v| = sqrt(v_x^2 + v_y^2)", speed_line],
                    ["point:landing", "event:impact", "velocity:impact", "velocity:impact_x_component", "velocity:impact_y_component"],
                    ["velocity:impact", "velocity:impact_x_component", "velocity:impact_y_component"],
                ),
            ],
            visual_action="show_impact_velocity_triangle",
            visual_focus=["point:landing", "event:impact", "velocity:impact", "velocity:impact_x_component", "velocity:impact_y_component"],
            visible_vectors=["*:vx", "*:vy", "*:v"],
            overlays=["show_trajectory", "show_velocity_components"],
            motion={"mode": "freeze", "event": "impact"},
            why_it_matters="The speed is the length of the resultant vector, not just the vertical component.",
            visual_director_beat="impact_speed",
            hide_live_values=True,
        ),
        _conceptual_beat(
            step_id="horizontal_launch_impact_angle",
            title="Find the impact angle with the horizontal",
            learner_message="Use the same impact triangle to read the direction below the horizontal.",
            sub_reveals=[
                _sub_reveal(
                    "angle",
                    "The angle is measured at impact between the horizontal component and the resultant velocity.",
                    "Add the impact angle arc to the velocity triangle.",
                    ["tan theta = v_y / v_x", angle_line],
                    ["point:landing", "event:impact", "quantity:impact_angle", "velocity:impact", "velocity:impact_x_component", "velocity:impact_y_component"],
                    ["quantity:impact_angle", "velocity:impact"],
                ),
            ],
            visual_action="show_impact_angle",
            visual_focus=["point:landing", "event:impact", "quantity:impact_angle", "velocity:impact", "velocity:impact_x_component", "velocity:impact_y_component"],
            visible_vectors=["*:vx", "*:vy", "*:v"],
            overlays=["show_trajectory", "show_velocity_components"],
            motion={"mode": "freeze", "event": "impact"},
            why_it_matters="The answer needs both magnitude and direction, so the angle must be tied to the impact triangle.",
            visual_director_beat="impact_angle",
            hide_live_values=True,
        ),
    ]


def _incline_collision_conceptual_beats(result: EvaluationResult) -> list[dict]:
    plan = result.equation_plan or {}
    givens = _givens_map(plan.get("givens") or [])
    alpha = givens.get("incline", "alpha")
    time = givens.get("time", "t")
    gravity = givens.get("g", "g")
    answer = str(plan.get("final_answer") or result.computed_text or "u")
    numeric_line = (
        _trace_line_containing_all(result, ["u =", "cos(", answer])
        or f"u = {gravity} cos({alpha}) * {time} / 2 = {answer}"
    )
    numeric_line = _strip_terminal_period(numeric_line)
    return [
        _conceptual_beat(
            step_id="hook_setup",
            title="Set up the puzzle",
            learner_message=(
                f"Two particles start from the same point. P launches off the smooth incline, Q only slides on it, "
                f"and they meet after {time}. The real question is: how fast must P leave the surface?"
            ),
            sub_reveals=[
                _sub_reveal(
                    "story",
                    "First, do not rush to equations. Let us watch the situation: one body can leave the plane, the other cannot.",
                    "Show the incline with P and Q at the same starting point.",
                    [],
                    ["point:launch", "surface:inclined_plane", "actor:projectile_p", "actor:slider_q"],
                    ["point:launch", "actor:projectile_p", "actor:slider_q"],
                ),
                _sub_reveal(
                    "question",
                    "So the unknown is the launch speed of P, not the distance along the plane.",
                    "Highlight the launch direction and the requested speed.",
                    ["to find: u"],
                    ["quantity:u", "vector:u", "actor:projectile_p"],
                    ["quantity:u", "vector:u"],
                ),
            ],
            visual_action="show_full_scene",
            visual_focus=["point:launch", "surface:inclined_plane", "actor:projectile_p", "actor:slider_q", "quantity:u"],
            visible_vectors=["incline:tangent_axis", "incline:normal_axis"],
            overlays=["show_scene"],
            motion={"mode": "static"},
            why_it_matters="A good solution starts by identifying the event: both particles must be at the same point at the same time.",
        ),
        _conceptual_beat(
            step_id="diagram_insight",
            title="Read the diagram trick",
            learner_message=(
                "Look at P's arrow. It is not along the slope; it is perpendicular to the plane. That one detail changes the problem: "
                "P leaves the surface and comes back, while Q stays on the surface."
            ),
            sub_reveals=[
                _sub_reveal(
                    "launch_arrow",
                    "Let us mark the direction of P's initial velocity. It points normal to the incline.",
                    "Reveal the normal axis and P's launch vector.",
                    ["u is normal to the incline"],
                    ["incline:normal_axis", "vector:u", "quantity:u", "surface:inclined_plane"],
                    ["incline:normal_axis", "vector:u", "quantity:u"],
                ),
                _sub_reveal(
                    "constraint",
                    "Q is different. It is released on the smooth plane, so it remains constrained to the incline.",
                    "Keep Q on the surface and highlight the incline constraint.",
                    ["Q stays on the plane"],
                    ["actor:slider_q", "surface:inclined_plane", "incline:tangent_axis"],
                    ["actor:slider_q", "surface:inclined_plane"],
                ),
            ],
            visual_action="show_incline_axes",
            visual_focus=["surface:inclined_plane", "incline:normal_axis", "vector:u", "actor:slider_q"],
            visible_vectors=["incline:normal_axis", "incline:tangent_axis", "*:v"],
            overlays=["show_velocity_components", "show_perpendicular_marker"],
            labels=[{"target_id": "incline:normal_axis", "text": "normal", "placement": "above_arrow", "priority": 1}],
            motion={"mode": "static"},
            why_it_matters="The diagram is not decoration here; it tells us which direction can decide the collision.",
        ),
        _conceptual_beat(
            step_id="along_plane_cancels",
            title="See why along-plane motion cancels",
            learner_message=(
                f"Here is the elegant part. Along the slope, both particles start with zero along-plane velocity and both feel "
                f"the same acceleration, g sin({alpha}). So their along-plane motion stays identical. We can ignore this direction for finding u."
            ),
            sub_reveals=[
                _sub_reveal(
                    "along_axis",
                    "Let us look only along the plane.",
                    "Highlight the along-plane axis.",
                    [],
                    ["incline:tangent_axis", "surface:inclined_plane"],
                    ["incline:tangent_axis"],
                ),
                _sub_reveal(
                    "same_acceleration",
                    "Both particles have the same down-slope acceleration.",
                    "Show equal down-plane gravity components for the shared direction.",
                    [f"a_parallel = g sin({alpha})"],
                    ["projectile_p:gravity_tangent_component", "slider_q:gravity_tangent_component", "incline:tangent_axis", "actor:projectile_p", "actor:slider_q"],
                    ["projectile_p:gravity_tangent_component", "slider_q:gravity_tangent_component", "incline:tangent_axis"],
                ),
                _sub_reveal(
                    "cancel_direction",
                    "Same start, same acceleration, same time. That means this direction cannot determine the launch speed.",
                    "Grey out the along-plane direction and keep the normal direction bright.",
                    [f"s_P = 1/2 g sin({alpha}) t^2", f"s_Q = 1/2 g sin({alpha}) t^2"],
                    ["projectile_p:gravity_tangent_component", "slider_q:gravity_tangent_component", "incline:tangent_axis", "incline:normal_axis", "trajectory:p", "trajectory:q"],
                    ["incline:normal_axis"],
                ),
            ],
            visual_action="compare_incline_motion",
            visual_focus=["surface:inclined_plane", "incline:tangent_axis", "incline:normal_axis", "trajectory:p", "trajectory:q"],
            visible_vectors=["incline:tangent_axis", "incline:normal_axis", "projectile_p:gravity_tangent_component", "slider_q:gravity_tangent_component"],
            overlays=["show_velocity_components", "show_perpendicular_marker"],
            labels=[
                {"target_id": "projectile_p:gravity_tangent_component", "text": f"g sin({alpha})", "placement": "above_arrow", "priority": 1},
                {"target_id": "slider_q:gravity_tangent_component", "text": f"g sin({alpha})", "placement": "above_arrow", "priority": 1},
            ],
            motion={"mode": "static"},
            why_it_matters="This is the satisfying cancellation: one whole direction becomes irrelevant.",
        ),
        _conceptual_beat(
            step_id="normal_direction_controls",
            title="Watch the controlling direction",
            learner_message=(
                f"Now watch P normal to the plane. It shoots away with speed u, and gravity's normal component, "
                f"g cos({alpha}), pulls it back. So the collision time is decided by when P returns to the surface."
            ),
            sub_reveals=[
                _sub_reveal(
                    "normal_axis",
                    "Now switch attention to the normal direction only.",
                    "Highlight the normal axis.",
                    [],
                    ["incline:normal_axis", "surface:inclined_plane"],
                    ["incline:normal_axis"],
                ),
                _sub_reveal(
                    "normal_gravity",
                    f"The vertical gravity vector contributes a component into the plane: g cos({alpha}).",
                    "Reveal the normal component of gravity.",
                    [f"g_normal = g cos({alpha})"],
                    ["projectile_p:gravity_normal_component", "incline:normal_axis", "vector:g"],
                    ["projectile_p:gravity_normal_component", "incline:normal_axis"],
                ),
                _sub_reveal(
                    "return_arc",
                    "P leaves the surface, slows in this normal direction, and comes back to the plane.",
                    "Animate P leaving and returning to the incline while Q moves along the plane.",
                    [],
                    ["trajectory:p", "trajectory:q", "point:collision", "incline:normal_axis"],
                    ["trajectory:p", "point:collision", "incline:normal_axis"],
                ),
            ],
            visual_action="show_normal_return",
            visual_focus=["incline:normal_axis", "trajectory:p", "trajectory:q", "point:collision"],
            visible_vectors=["incline:normal_axis", "projectile_p:gravity_normal_component"],
            overlays=["show_trajectory", "show_motion_progress", "show_velocity_components", "show_perpendicular_marker", "show_timer"],
            labels=[{"target_id": "projectile_p:gravity_normal_component", "text": f"g cos({alpha})", "placement": "above_arrow", "priority": 1}],
            motion={"mode": "partial", "event": "impact"},
            why_it_matters="The unknown speed is fixed by the off-surface motion, not by the sliding direction.",
        ),
        _conceptual_beat(
            step_id="collision_equation",
            title="Turn the return into an equation",
            learner_message=(
                "Collision means P is back on the surface. So normal displacement is zero. Now the equation is no longer memorized; "
                "it is just the motion we watched."
            ),
            sub_reveals=[
                _sub_reveal(
                    "condition",
                    "At collision, normal displacement is zero.",
                    "Freeze at collision and highlight the contact point.",
                    ["n_P = 0"],
                    ["point:collision", "event:collision", "incline:normal_axis"],
                    ["point:collision", "event:collision"],
                ),
                _sub_reveal(
                    "write_equation",
                    "Start from displacement along one axis: s = ut + 1/2 at^2. Along the normal axis, acceleration is -g cos(alpha).",
                    "Place the equation beside the normal return path.",
                    ["s = ut + 1/2 at^2", f"0 = ut - 1/2 g cos({alpha}) t^2"],
                    ["incline:normal_axis", "trajectory:p", "point:collision"],
                    ["incline:normal_axis", "point:collision"],
                ),
                _sub_reveal(
                    "factor",
                    "Factor out t. The first solution, t = 0, is only the launch instant. The other solution gives u.",
                    "Show the algebra while keeping the collision point highlighted.",
                    [f"0 = t(u - 1/2 g cos({alpha}) t)", f"u = g cos({alpha}) t / 2"],
                    ["quantity:u", "point:collision", "event:collision"],
                    ["quantity:u", "point:collision"],
                ),
            ],
            visual_action="highlight_collision",
            visual_focus=["point:collision", "event:collision", "quantity:u", "incline:normal_axis"],
            visible_vectors=["incline:normal_axis", "projectile_p:gravity_normal_component"],
            overlays=["show_trajectory", "show_motion_progress", "show_collision_marker", "show_timer", "show_velocity_components", "show_perpendicular_marker"],
            labels=[{"target_id": "projectile_p:gravity_normal_component", "text": f"g cos({alpha})", "placement": "above_arrow", "priority": 1}],
            motion={"mode": "partial", "event": "impact"},
            why_it_matters="The algebra is the payoff of the visual event: return to the plane means normal displacement is zero.",
        ),
        _conceptual_beat(
            step_id="answer_sanity",
            title="Calculate and sanity-check",
            learner_message=(
                f"Now substitute the numbers: {numeric_line}. So the required projection speed is {answer}. "
                "The result also makes sense: a smaller normal gravity component would need less launch speed for the same return time."
            ),
            sub_reveals=[
                _sub_reveal(
                    "substitute",
                    "Now we only replace symbols with the given values.",
                    "Highlight the launch speed while the arithmetic appears.",
                    [f"u = g cos({alpha}) t / 2", numeric_line],
                    ["quantity:u", "vector:u", "actor:projectile_p"],
                    ["quantity:u", "vector:u"],
                ),
                _sub_reveal(
                    "answer",
                    f"So P must be projected with speed {answer}.",
                    "Show the answer and replay the completed meeting.",
                    [f"u = {answer}"],
                    ["answer", "quantity:u", "point:collision", "trajectory:p", "trajectory:q"],
                    ["answer", "quantity:u", "point:collision"],
                ),
            ],
            visual_action="zoom_launch_vector",
            visual_focus=["quantity:u", "vector:u", "point:collision"],
            visible_vectors=["*:v", "incline:normal_axis"],
            overlays=["show_velocity_components", "show_perpendicular_marker", "show_final_answer"],
            motion={"mode": "freeze", "event": "answer"},
            why_it_matters="A final answer should close the loop: number, unit, and a quick physical check.",
        ),
    ]


def _conceptual_beat(
    *,
    step_id: str,
    title: str,
    learner_message: str,
    sub_reveals: list[dict],
    visual_action: str,
    visual_focus: list[str],
    visible_vectors: list[str],
    overlays: list[str],
    motion: dict,
    why_it_matters: str,
    labels: list[dict] | None = None,
    visual_director_beat: str = "",
    hide_live_values: bool = False,
) -> dict:
    highlight_ids = list(dict.fromkeys([item for reveal in sub_reveals for item in reveal.get("highlight_ids", [])] or visual_focus))
    reveal_ids = list(dict.fromkeys(visual_focus + [item for reveal in sub_reveals for item in reveal.get("reveal_ids", [])]))
    visual_plan = {
        "type": "scene",
        "visual_action": visual_action,
        "scene_phase": _scene_phase_from_text(" ".join([step_id, title, learner_message]).lower(), visual_action),
        "show_ids": reveal_ids,
        "hide_ids": [],
        "highlight_ids": highlight_ids,
        "visible_vectors": list(dict.fromkeys(visible_vectors)),
        "overlays": list(dict.fromkeys(overlays)),
        "labels": labels or [],
        "motion": motion,
        "camera": "full_scene",
    }
    if visual_director_beat:
        visual_plan["_visual_director_beat"] = visual_director_beat
    if hide_live_values:
        visual_plan["hide_live_values"] = True
    visual_plan["visual_state"] = _visual_state_for_plan(visual_plan)
    return {
        "id": f"beat_{step_id}",
        "step_id": step_id,
        "title": title,
        "learner_message": learner_message,
        "visual_instruction": visual_action.replace("_", " "),
        "animation_phase": visual_action,
        "formula_lines": [],
        "sub_reveals": sub_reveals,
        "reveal_ids": reveal_ids,
        "highlight_ids": highlight_ids,
        "why_it_matters": why_it_matters,
        "visual_plan": visual_plan,
    }


def _attach_conceptual_beat_visual_spec(result: EvaluationResult, beat: dict) -> dict:
    visual_plan = dict(beat.get("visual_plan") or {})
    if visual_plan.get("type") == "text_only":
        return beat
    step_id = str(beat.get("step_id") or beat.get("id") or "")
    text = _conceptual_beat_text_blob(beat)
    visual_plan = attach_beat_visual_spec(
        result=result,
        step_id=step_id,
        title=str(beat.get("title") or ""),
        text=text,
        visual_plan=visual_plan,
    )
    updated = dict(beat)
    updated["visual_plan"] = visual_plan
    updated["beat_visual_spec"] = visual_plan.get("beat_visual_spec") or {}
    return updated


def _conceptual_beat_text_blob(beat: dict) -> str:
    parts = [
        beat.get("step_id") or "",
        beat.get("title") or "",
        beat.get("learner_message") or "",
        beat.get("visual_instruction") or "",
        beat.get("why_it_matters") or "",
    ]
    for reveal in beat.get("sub_reveals") or []:
        parts.append(reveal.get("id") or "")
        parts.append(reveal.get("text") or "")
        parts.append(reveal.get("visual_instruction") or "")
        parts.extend(reveal.get("formula_lines") or [])
    return " ".join(str(part) for part in parts).lower()


def _givens_map(givens: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for given in givens:
        text = str(given or "").strip()
        if "=" not in text:
            continue
        key, value = text.split("=", 1)
        out[key.strip().lower()] = value.strip()
    return out


def _trace_line_containing(result: EvaluationResult, token: str) -> str:
    lowered_token = token.lower()
    for line in result.trace or []:
        if lowered_token in str(line).lower():
            return str(line).replace(" x ", " * ")
    return ""


def _trace_line_containing_all(result: EvaluationResult, tokens: list[str]) -> str:
    lowered_tokens = [token.lower() for token in tokens]
    for line in result.trace or []:
        lowered = str(line).lower()
        if all(token in lowered for token in lowered_tokens):
            return str(line).replace(" x ", " * ")
    return ""


def _strip_terminal_period(text: str) -> str:
    return str(text or "").strip().rstrip(".")


def _compact_explainer_steps(result: EvaluationResult, steps: list[dict]) -> list[dict]:
    compact: list[dict] = []
    for raw_step in steps:
        step = dict(raw_step)
        step_id = str(step.get("id") or "").lower()
        title = str(step.get("title") or "").lower()
        if step_id == "takeaway" or "exam takeaway" in title:
            continue
        if compact and not str(step.get("equation") or step.get("formula") or "").strip() and str(step.get("substitution") or "").strip():
            previous = dict(compact[-1])
            previous["substitution"] = str(step.get("substitution") or "").strip()
            answer = str(step.get("result") or result.computed_text or "").strip()
            if answer:
                previous["result"] = answer
            if "calculate" not in str(previous.get("title") or "").lower() and ("compute" in title or "answer" in title):
                previous["title"] = f"{previous.get('title') or 'Solve'} and calculate"
            previous["focus_ids"] = list(dict.fromkeys(list(previous.get("focus_ids") or []) + list(step.get("focus_ids") or [])))
            previous["highlight_ids"] = list(dict.fromkeys(list(previous.get("highlight_ids") or previous.get("focus_ids") or []) + list(step.get("highlight_ids") or step.get("focus_ids") or [])))
            compact[-1] = previous
            continue
        is_final_answer = step_id == "answer" or "state the answer" in title or title.strip() == "answer"
        if is_final_answer and compact:
            previous = dict(compact[-1])
            answer = str(step.get("result") or step.get("equation") or result.computed_text or "").strip()
            if answer:
                previous["result"] = answer
                if "answer" not in str(previous.get("title") or "").lower():
                    previous["title"] = f"{previous.get('title') or 'Solve'} and state the answer"
                previous["focus_ids"] = list(dict.fromkeys(list(previous.get("focus_ids") or []) + ["answer", "quantity:u"]))
                previous["highlight_ids"] = list(dict.fromkeys(list(previous.get("highlight_ids") or previous.get("focus_ids") or []) + ["answer", "quantity:u"]))
                compact[-1] = previous
                continue
        compact.append(step)
    return compact


def _generic_explainer_beat(result: EvaluationResult, step: dict, index: int) -> dict:
    step_id = str(step.get("id") or f"step_{index + 1}")
    title = str(step.get("title") or "Explain the next move")
    title = _student_facing_title(title, result)
    equation = str(step.get("equation") or step.get("formula") or "")
    substitution = str(step.get("substitution") or "")
    explanation = str(step.get("explanation") or "")
    focus_ids = list(step.get("focus_ids") or step.get("highlight_ids") or [])
    unknown = str((result.equation_plan or {}).get("unknown") or "the requested quantity")
    if _is_generic_answer_focus(focus_ids):
        focus_ids = _target_highlight_ids(unknown, _invariant_focus_ids(result.equation_plan or {}))
    formula_lines = _formula_lines(equation, substitution, str(step.get("calculation") or ""), str(step.get("result") or ""))
    sub_reveals = _generic_sub_reveals(
        step_id=step_id,
        title=title,
        equation=equation,
        substitution=substitution,
        explanation=explanation,
        focus_ids=focus_ids,
        result=str(step.get("result") or ""),
        known_values=list(step.get("next_known_values") or step.get("known_values") or []),
        unknown=unknown,
    )
    visual_plan = _visual_plan_for_beat(step, sub_reveals, result)
    return {
        "id": f"beat_{step_id}",
        "step_id": step_id,
        "title": title,
        "learner_message": _learner_message_for_step(step, result),
        "visual_instruction": _visual_instruction_for_step(step),
        "animation_phase": str(step.get("visual_action") or step.get("animation_intent") or ""),
        "formula_lines": formula_lines,
        "sub_reveals": sub_reveals,
        "reveal_ids": list(dict.fromkeys(focus_ids + list(step.get("objects_to_highlight") or []))),
        "highlight_ids": list(step.get("highlight_ids") or step.get("objects_to_highlight") or focus_ids),
        "why_it_matters": str(step.get("teaching_goal") or step.get("student_goal") or explanation),
        "visual_plan": visual_plan,
    }


def _generic_sub_reveals(
    *,
    step_id: str,
    title: str,
    equation: str,
    substitution: str,
    explanation: str,
    focus_ids: list[str],
    result: str,
    known_values: list[str],
    unknown: str,
) -> list[dict]:
    lowered = " ".join([step_id, title, equation, explanation, " ".join(focus_ids)]).lower()
    if step_id == "invariant" or title.strip().lower().startswith("given"):
        return _setup_sub_reveals(known_values, unknown, focus_ids)
    if step_id == "takeaway" or "exam takeaway" in title.lower():
        return [_sub_reveal(
            "takeaway",
            explanation or "Keep this idea as the quick check for similar problems.",
            "Highlight the final result and the main scene relation.",
            [result] if result else [],
            ["answer", *focus_ids[:2]],
            ["answer", *focus_ids[:2]],
        )]
    if _is_diagram_condition_step(step_id, equation, focus_ids):
        return _diagram_condition_sub_reveals(equation, explanation, focus_ids)
    if _is_same_axis_motion_step(step_id, equation):
        return _same_axis_motion_sub_reveals(equation, focus_ids)
    if _is_normal_return_step(step_id, equation):
        return _normal_return_sub_reveals(equation, focus_ids)
    if _is_incline_return_time_equation(equation):
        return _incline_return_time_sub_reveals(equation, substitution, result, focus_ids)
    if _is_incline_along_displacement_equation(equation):
        return _incline_along_displacement_sub_reveals(equation, substitution, result, focus_ids)
    if _is_incline_range_formula_equation(equation):
        return _incline_range_formula_sub_reveals(equation, substitution, result, focus_ids)
    if _is_indexed_collision_equation(equation):
        return _indexed_collision_sub_reveals(equation, substitution, result, focus_ids)
    if _is_horizontal_zero_component_step(title=title, equation=equation, explanation=explanation, focus_ids=focus_ids):
        return _horizontal_zero_component_sub_reveals(focus_ids)
    if _is_vector_resolution_text(step_id=step_id, title=title, equation=equation, focus_ids=focus_ids):
        return _vector_resolution_sub_reveals(equation, focus_ids)
    if equation:
        return _formula_sub_reveals(equation, substitution, result, focus_ids)
    if substitution:
        reveals = [_sub_reveal(
            "substitution",
            _final_substitution_text(substitution, result),
            "Keep the final quantity highlighted while the arithmetic is shown.",
            [substitution],
            focus_ids,
            focus_ids,
        )]
        if result and result not in substitution:
            reveals.append(_sub_reveal(
                "result",
                f"This final simplification gives {result}.",
                "Highlight the final answer and the scene object it belongs to.",
                [result],
                ["answer", *focus_ids[:2]],
                ["answer", *focus_ids[:2]],
            ))
        return reveals
    if result:
        return [_sub_reveal(
            "result",
            f"The substitution is complete in the previous line. The active relation has already isolated the requested quantity, so we write the result as {result}.",
            "Highlight the final answer and the scene object it belongs to.",
            [result],
            ["answer", *focus_ids[:2]],
            ["answer", *focus_ids[:2]],
        )]
    reveals = [_sub_reveal("look", explanation or "Look at the highlighted part of the scene.", _focus_sentence(focus_ids), [], focus_ids, focus_ids)]
    return reveals


def _setup_sub_reveals(known_values: list[str], unknown: str, focus_ids: list[str]) -> list[dict]:
    reveals = []
    display_values = _display_known_values(known_values)
    target_ids = _target_highlight_ids(unknown, focus_ids)
    if display_values:
        reveals.append(_sub_reveal(
            "givens",
            "Let's mark the values the question gives us.",
            "Highlight the known values and the matching scene objects.",
            display_values[:6],
            ["emphasis:given", *focus_ids],
            ["emphasis:given", *focus_ids],
        ))
    reveals.append(_sub_reveal(
        "target",
        f"We need to find {unknown}.",
        "Highlight the requested quantity in the scene if it exists.",
        [],
        ["emphasis:target", *target_ids],
        ["emphasis:target", *target_ids],
    ))
    return reveals


def _student_facing_title(title: str, result: EvaluationResult) -> str:
    lowered = title.strip().lower()
    if lowered in {"compute the requested answer", "state the answer", "answer"}:
        unknown = str((result.equation_plan or {}).get("unknown") or "").strip()
        if unknown:
            return f"Calculate {unknown}"
        return "Calculate the final value"
    return title


def _final_substitution_text(substitution: str, result: str) -> str:
    if "=" in substitution:
        return "Now we evaluate the expression we just built. No new physics is being added here; we are only replacing the symbols with the known values."
    if result:
        return f"The substitution is complete, and the requested quantity is isolated. This last line gives {result}."
    return "Now we finish the arithmetic from the relation above."


def _target_highlight_ids(unknown: str, focus_ids: list[str]) -> list[str]:
    lowered = unknown.lower()
    if "normal velocity" in lowered or "normal component" in lowered:
        return ["velocity:normal_component", "incline:normal_axis", *focus_ids]
    if "condition" in lowered and ("angle" in lowered or "incline" in lowered):
        return ["velocity:tangent_component", "incline:tangent_axis", "point:impact", *focus_ids]
    if "speed" in lowered or "velocity" in lowered or "projection" in lowered:
        return ["quantity:u", "vector:u", "actor:projectile_p", *focus_ids]
    if "range" in lowered or "distance" in lowered:
        return ["quantity:R", "point:impact", "point:landing", *focus_ids]
    if "time" in lowered:
        return ["quantity:T", "event:landing", "event:collision", *focus_ids]
    if "height" in lowered:
        return ["quantity:H", "event:apex", *focus_ids]
    return focus_ids


def _is_generic_answer_focus(focus_ids: list[str]) -> bool:
    if not focus_ids:
        return False
    generic = {"answer", "quantity:R", "quantity:T", "quantity:H", "point:landing", "point:impact", "point:collision"}
    return set(focus_ids).issubset(generic)


def _display_known_values(known_values: list[str]) -> list[str]:
    unique: list[str] = []
    seen = set()
    for value in known_values:
        cleaned = str(value or "").strip()
        if "=" not in cleaned and ":" in cleaned:
            left, right = cleaned.split(":", 1)
            cleaned = f"{left.strip()} = {right.strip()}"
        key = cleaned.lower().replace(" ", "")
        if not cleaned or key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)

    parsed: dict[str, tuple[int, float]] = {}
    for index, value in enumerate(unique):
        if "=" not in value:
            continue
        key, raw = value.split("=", 1)
        match = re.search(r"-?\d+(?:\.\d+)?", raw)
        if match:
            parsed[key.strip().lower().replace("_", "")] = (index, float(match.group(0)))

    remove_indexes: set[int] = set()
    vx = parsed.get("vx") or parsed.get("v0x")
    v0 = parsed.get("v0")
    if vx and v0 and abs(vx[1] - v0[1]) < 1e-9:
        remove_indexes.add(v0[0])
    u = parsed.get("u")
    if u and v0 and abs(u[1] - v0[1]) < 1e-9:
        remove_indexes.add(v0[0])
    if parsed.get("vx") and parsed.get("v0x") and abs(parsed["vx"][1] - parsed["v0x"][1]) < 1e-9:
        remove_indexes.add(parsed["v0x"][0])

    return [value for index, value in enumerate(unique) if index not in remove_indexes]


def _diagram_condition_sub_reveals(equation: str, explanation: str, focus_ids: list[str]) -> list[dict]:
    diagram_line = equation if "=" in equation else f"diagram condition = {equation}"
    return [
        _sub_reveal(
            "read_diagram",
            "Let's read the diagram as physics, not decoration. The diagram tells us where the bodies start and which directions are constrained.",
            "Show the diagram constraints.",
            [diagram_line] if equation else [],
            focus_ids,
            focus_ids,
        ),
        _sub_reveal(
            "extract_constraint",
            explanation or "Together, we convert the visible arrows and surfaces into constraints for the equations.",
            "Highlight the relevant surface, launch point, and direction constraints.",
            [],
            focus_ids,
            focus_ids,
        ),
    ]


def _same_axis_motion_sub_reveals(equation: str, focus_ids: list[str]) -> list[dict]:
    axis_ids = _axis_ids_from_focus(focus_ids, fallback=["incline:tangent_axis"])
    motion_ids = [item for item in focus_ids if "trajectory" in item or "actor" in item] or focus_ids
    return [
        _sub_reveal(
            "axis",
            "Now let's look only along this axis. If two bodies have the same initial component and the same acceleration on this axis, their positions stay matched here.",
            "Highlight the shared axis.",
            [],
            axis_ids,
            axis_ids,
        ),
        _sub_reveal(
            "parent_equation",
            "We use the displacement equation on that single axis.",
            "Show the axis while the parent equation appears.",
            ["s = ut + 1/2 at^2"],
            axis_ids,
            axis_ids,
        ),
        _sub_reveal(
            "compare_terms",
            "Together, we compare the terms for both bodies. Matching terms mean this axis does not decide the unknown.",
            "Highlight both motions on the same axis.",
            [equation],
            motion_ids,
            motion_ids,
        ),
    ]


def _normal_return_sub_reveals(equation: str, focus_ids: list[str]) -> list[dict]:
    normal_ids = _axis_ids_from_focus(focus_ids, fallback=["incline:normal_axis"])
    return [
        _sub_reveal(
            "normal_axis",
            "Now let's switch to the direction normal to the surface. This is where the body moves away and then returns.",
            "Highlight the normal axis.",
            [],
            normal_ids,
            normal_ids,
        ),
        _sub_reveal(
            "parent_equation",
            "We again start from the original displacement equation, but now along the normal direction.",
            "Show the parent equation beside the normal axis.",
            ["s = ut + 1/2 at^2"],
            normal_ids,
            normal_ids,
        ),
        _sub_reveal(
            "normal_terms",
            "The initial normal velocity carries the body away; the acceleration component brings it back.",
            "Highlight the normal velocity and acceleration terms.",
            [equation],
            focus_ids,
            focus_ids,
        ),
    ]


def _incline_return_time_sub_reveals(equation: str, substitution: str, result: str, focus_ids: list[str]) -> list[dict]:
    normal_ids = _axis_ids_from_focus(focus_ids, fallback=["incline:normal_axis"])
    reveals = [
        _sub_reveal(
            "choose_normal_axis",
            "Let us solve perpendicular to the incline first. In this direction, the projectile leaves the plane with speed u.",
            "Highlight the normal axis and the launch velocity.",
            ["normal axis: away from the incline"],
            list(dict.fromkeys([*normal_ids, "vector:u", "quantity:u"])),
            list(dict.fromkeys([*normal_ids, "vector:u", "quantity:u"])),
        ),
        _sub_reveal(
            "resolve_gravity_normal",
            "Gravity points vertically downward. Its component that pulls the projectile back toward the plane is g cos(alpha).",
            "Show the gravity vector split into normal and along-plane parts.",
            ["g_normal = g cos(alpha)"],
            list(dict.fromkeys([*normal_ids, "vector:g", "gravity:normal_component"])),
            list(dict.fromkeys(["gravity:normal_component", *normal_ids])),
        ),
        _sub_reveal(
            "normal_return_equation",
            "At return, normal displacement is zero again. So we use s = ut + 1/2 at^2 on the normal axis.",
            "Animate the projectile leaving the plane and returning to it.",
            ["0 = u t - 1/2 g cos(alpha) t^2"],
            list(dict.fromkeys([*normal_ids, "trajectory:path", "point:impact"])),
            list(dict.fromkeys([*normal_ids, "point:impact"])),
        ),
        _sub_reveal(
            "return_time",
            "The solution t = 0 is the launch instant. The later return time is the useful one.",
            "Keep the impact point highlighted.",
            [equation],
            list(dict.fromkeys([*normal_ids, "quantity:T", "point:impact"])),
            list(dict.fromkeys(["quantity:T", "point:impact", *normal_ids])),
        ),
    ]
    if substitution:
        reveals.append(_sub_reveal(
            "condition",
            substitution,
            "Keep the normal-axis condition visible.",
            [],
            normal_ids,
            normal_ids,
        ))
    if result:
        reveals.append(_sub_reveal(
            "result",
            f"This gives {result}.",
            "Highlight the computed time.",
            [result],
            ["answer", *normal_ids],
            ["answer", *normal_ids],
        ))
    return reveals


def _incline_along_displacement_sub_reveals(equation: str, substitution: str, result: str, focus_ids: list[str]) -> list[dict]:
    tangent_ids = _axis_ids_from_focus(focus_ids, fallback=["incline:tangent_axis"])
    reveals = [
        _sub_reveal(
            "choose_along_axis",
            "Now look along the incline. The launch is perpendicular to the plane, so the initial along-plane velocity is zero.",
            "Highlight the along-plane axis.",
            ["u_parallel = 0"],
            list(dict.fromkeys([*tangent_ids, "surface:inclined_plane"])),
            tangent_ids,
        ),
        _sub_reveal(
            "resolve_gravity_parallel",
            "The component of gravity along the incline is g sin(alpha). That is what pulls the projectile down the plane.",
            "Highlight the down-plane gravity component.",
            ["g_parallel = g sin(alpha)"],
            list(dict.fromkeys([*tangent_ids, "vector:g", "gravity:tangent_component"])),
            list(dict.fromkeys(["gravity:tangent_component", *tangent_ids])),
        ),
        _sub_reveal(
            "along_displacement",
            "Since u_parallel is zero, the along-plane displacement comes only from the acceleration term.",
            "Highlight the range measured along the incline.",
            [equation],
            list(dict.fromkeys([*focus_ids, "quantity:R", "point:impact"])),
            list(dict.fromkeys(["quantity:R", "point:impact", *tangent_ids])),
        ),
    ]
    if substitution:
        reveals.append(_sub_reveal(
            "insert_return_time",
            "Now put the return time from the normal-axis motion into this along-plane displacement.",
            "Keep the range and return point highlighted.",
            [substitution],
            list(dict.fromkeys([*focus_ids, "quantity:R", "point:impact"])),
            list(dict.fromkeys(["quantity:R", "point:impact"])),
        ))
    if result:
        reveals.append(_sub_reveal(
            "result",
            f"This gives {result}.",
            "Highlight the range on the incline.",
            [result],
            ["answer", "quantity:R", "point:impact"],
            ["answer", "quantity:R", "point:impact"],
        ))
    return reveals


def _incline_range_formula_sub_reveals(equation: str, substitution: str, result: str, focus_ids: list[str]) -> list[dict]:
    reveals = [
        _sub_reveal(
            "combine",
            "Now combine the two pieces: normal motion gave the return time, and along-plane motion gives the range.",
            "Show the impact point and the range segment on the incline.",
            ["t_return = 2u/(g cos(alpha))", "s = 1/2 g sin(alpha) t_return^2"],
            list(dict.fromkeys([*focus_ids, "quantity:R", "point:impact"])),
            list(dict.fromkeys(["quantity:R", "point:impact"])),
        ),
        _sub_reveal(
            "simplify",
            "After substituting t_return, the range on the incline becomes this expression.",
            "Keep the incline range highlighted.",
            [equation],
            list(dict.fromkeys([*focus_ids, "quantity:R", "point:impact"])),
            list(dict.fromkeys(["quantity:R", "point:impact"])),
        ),
    ]
    if substitution:
        reveals.append(_sub_reveal(
            "numeric_substitution",
            "Now substitute the given speed and incline angle.",
            "Replace u and alpha with the given values.",
            [substitution],
            list(dict.fromkeys([*focus_ids, "answer", "quantity:R"])),
            list(dict.fromkeys(["answer", "quantity:R"])),
        ))
    if result:
        reveals.append(_sub_reveal(
            "result",
            f"So the range along the incline is {result}.",
            "Highlight the final range.",
            [result],
            ["answer", "quantity:R", "point:impact"],
            ["answer", "quantity:R", "point:impact"],
        ))
    return reveals


def _vector_resolution_sub_reveals(equation: str, focus_ids: list[str]) -> list[dict]:
    angle = _angle_symbol_from_text(equation)
    components = _component_lines_for(equation, angle)
    original_ids, adjacent_ids, opposite_ids = _component_reveal_ids_for(equation, focus_ids)
    return [
        _sub_reveal(
            "original_vector",
            "Let's start with the original velocity vector. It points in the launch direction, but we can solve more cleanly after splitting it into independent directions.",
            "Show only the original vector.",
            [],
            original_ids,
            original_ids,
        ),
        _sub_reveal(
            "axes",
            "Now we choose the useful axes together. On level ground, we use horizontal and vertical axes; on an incline, we use along-plane and normal-to-plane axes.",
            "Reveal the useful axes.",
            [],
            list(dict.fromkeys(original_ids + adjacent_ids + opposite_ids)),
            list(dict.fromkeys(adjacent_ids + opposite_ids)),
        ),
        _sub_reveal(
            "adjacent_component",
            f"The component next to the angle uses cos({angle}). So together, we project the original vector onto that axis.",
            "Reveal the adjacent component arrow and label.",
            [components[0]],
            list(dict.fromkeys(original_ids + adjacent_ids)),
            adjacent_ids,
        ),
        _sub_reveal(
            "opposite_component",
            f"The component opposite the angle uses sin({angle}). That gives us the perpendicular part of the same vector.",
            "Reveal the opposite component arrow and label.",
            [components[1]],
            list(dict.fromkeys(original_ids + adjacent_ids + opposite_ids)),
            opposite_ids,
        ),
    ]


def _is_horizontal_zero_component_step(*, title: str, equation: str, explanation: str, focus_ids: list[str]) -> bool:
    lowered = " ".join([title, equation, explanation, " ".join(focus_ids)]).lower().replace(" ", "")
    if "u_y=0" in lowered or "uy=0" in lowered or "uᵧ=0" in lowered:
        return True
    return "horizontallaunch" in lowered and ("verticalcomponent" in lowered or "initialvertical" in lowered)


def _horizontal_zero_component_sub_reveals(focus_ids: list[str]) -> list[dict]:
    launch_ids = list(dict.fromkeys(["point:launch", "velocity:x_component", "velocity:y_component", *focus_ids]))
    return [
        _sub_reveal(
            "horizontal_launch_direction",
            "The launch arrow is horizontal, so the initial velocity has no upward or downward part.",
            "Show the horizontal launch arrow only.",
            ["u_x = u"],
            launch_ids,
            ["velocity:x_component"],
        ),
        _sub_reveal(
            "zero_vertical_component",
            "Because the launch has no vertical part, the vertical component starts at zero.",
            "Mark the vertical component as zero at the launch point.",
            ["u_y = 0"],
            launch_ids,
            ["velocity:y_component"],
        ),
    ]


def _formula_sub_reveals(equation: str, substitution: str, result: str, focus_ids: list[str]) -> list[dict]:
    if _is_zero_vertical_event_equation(equation):
        return _zero_vertical_event_sub_reveals(equation, substitution, result, focus_ids)
    if _is_height_launch_positive_root_equation(equation):
        return _height_launch_positive_root_sub_reveals(equation, substitution, result, focus_ids)
    if _is_nonzero_time_root_equation(equation):
        return _nonzero_time_root_sub_reveals(equation, substitution, result, focus_ids)
    if _is_vertical_component_time_substitution(equation):
        return _vertical_component_time_sub_reveals(focus_ids)
    if _is_horizontal_range_equation(equation):
        return _horizontal_range_sub_reveals(focus_ids)
    parent = _parent_equation_for(equation)
    reveals: list[dict] = []
    if parent:
        reveals.append(_sub_reveal(
            "parent_equation",
            f"We start from {parent}.",
            "Show the physical direction or event where this equation applies.",
            [parent],
            focus_ids,
            focus_ids,
        ))
    reveals.append(_sub_reveal(
        "chosen_relation",
        _relation_reason(equation),
        "Highlight the scene quantity that this relation describes.",
        [equation],
        focus_ids,
        focus_ids,
    ))
    if substitution:
        reveals.append(_sub_reveal(
            "substitution",
            "Now substitute the known values.",
            "Keep the same visual focus while numbers replace symbols.",
            [substitution],
            focus_ids,
            focus_ids,
        ))
    if result:
        reveals.append(_sub_reveal(
            "result",
            f"This gives {result}.",
            "Highlight the computed quantity.",
            [result],
            ["answer", *focus_ids[:2]],
            ["answer", *focus_ids[:2]],
        ))
    return reveals


def _indexed_collision_sub_reveals(equation: str, substitution: str, result: str, focus_ids: list[str]) -> list[dict]:
    lowered = equation.lower()
    if _is_indexed_face_time_equation(lowered):
        reveals = [
            _sub_reveal(
                "name_index",
                "We do not test every step one by one. Let n be the step number, so the nth vertical face is n step-widths from the start.",
                "Highlight the repeated step width and the nth vertical face.",
                ["step number = n", "distance to nth face = n w", "x_n = n w"],
                focus_ids,
                focus_ids,
            ),
            _sub_reveal(
                "horizontal_time",
                "The marble leaves horizontally, so horizontal speed stays constant. Time to reach that face is distance divided by horizontal speed.",
                "Highlight horizontal motion from launch to the nth face.",
                ["t_n = x_n / v_x", "t_n = n w / v_x"],
                focus_ids,
                focus_ids,
            ),
        ]
        if substitution:
            reveals.append(_sub_reveal(
                "substitute_dimensions",
                "Now put in the step width and horizontal speed from the question.",
                "Replace w and v_x with the given values.",
                [substitution],
                focus_ids,
                focus_ids,
            ))
        return reveals
    if _is_indexed_drop_equation(lowered):
        reveals = [
            _sub_reveal(
                "vertical_free_fall",
                "During that same time, vertical motion is just free fall. The marble starts with no vertical velocity, so the drop is 1/2 g t_n^2.",
                "Highlight the vertical drop while keeping the nth face visible.",
                ["initial vertical velocity = 0", "y_n = 1/2 g t_n^2"],
                focus_ids,
                focus_ids,
            ),
            _sub_reveal(
                "drop_grows_quadratically",
                "Because t_n is proportional to n, the drop is proportional to n^2. That is the main idea of the staircase problem.",
                "Show the trajectory dropping faster as n increases.",
                [substitution or "y_n is proportional to n^2"],
                focus_ids,
                focus_ids,
            ),
        ]
        return reveals
    if _is_indexed_hit_inequality(lowered):
        reveals = [
            _sub_reveal(
                "hit_condition",
                "The nth vertical face begins n step-heights below the top. The marble directly strikes that face when its drop has reached at least n h.",
                "Highlight the nth face height and the projectile drop at that face.",
                ["required drop to reach nth face = n h", "direct hit condition: y_n >= n h"],
                focus_ids,
                focus_ids,
            ),
            _sub_reveal(
                "first_integer",
                "Now solve the inequality. Since n is a step number, the answer is the first whole number after the cutoff.",
                "Highlight the first step satisfying the inequality.",
                [substitution] if substitution else [equation],
                focus_ids,
                focus_ids,
            ),
        ]
        if result:
            reveals.append(_sub_reveal(
                "result",
                f"So the marble directly strikes the {result} step.",
                "Highlight the impact step.",
                [result],
                ["answer", *focus_ids[:2]],
                ["answer", *focus_ids[:2]],
            ))
        return reveals
    return _formula_sub_reveals(equation, substitution, result, focus_ids)


def _zero_vertical_event_sub_reveals(equation: str, substitution: str, result: str, focus_ids: list[str]) -> list[dict]:
    lowered = equation.lower().replace(" ", "")
    has_launch_height = "h+" in lowered
    if has_launch_height:
        condition_text = (
            "Let's set the vertical position at the landing event. The projectile starts at height h and reaches the ground, "
            "so the final vertical position is zero."
        )
        condition_lines = ["y(T) = 0", "y(T) = h + u_y T - 1/2 gT^2"]
    else:
        condition_text = (
            "Let's set the landing condition carefully. Launch and landing are at the same level, so the vertical displacement "
            "from launch to landing is zero."
        )
        condition_lines = ["s_y = 0", "u = u_y", "a = -g", "t = T"]
    reveals = [
        _sub_reveal(
            "parent_equation",
            "We start from the original displacement equation on one axis: s = ut + 1/2 at^2.",
            "Highlight the vertical direction where gravity acts.",
            ["s = ut + 1/2 at^2"],
            focus_ids,
            focus_ids,
        ),
        _sub_reveal(
            "event_condition",
            condition_text,
            "Highlight the launch and landing levels.",
            condition_lines,
            focus_ids,
            focus_ids,
        ),
        _sub_reveal(
            "substitute_axis_terms",
            "Now substitute the vertical-axis terms into the parent equation. The minus sign appears because gravity acts downward while we take upward as positive.",
            "Keep the vertical motion highlighted while the equation is formed.",
            [equation],
            focus_ids,
            focus_ids,
        ),
    ]
    if substitution and substitution != equation:
        reveals.append(_sub_reveal(
            "numeric_substitution",
            "If numbers are already known, we substitute them only after the event equation is clear.",
            "Replace symbols with known values.",
            [substitution],
            focus_ids,
            focus_ids,
        ))
    if result:
        reveals.append(_sub_reveal(
            "result",
            f"This gives {result}.",
            "Highlight the computed quantity.",
            [result],
            ["answer", *focus_ids[:2]],
            ["answer", *focus_ids[:2]],
        ))
    return reveals


def _nonzero_time_root_sub_reveals(equation: str, substitution: str, result: str, focus_ids: list[str]) -> list[dict]:
    canonical = _canonical_zero_time_equation(equation)
    final_lines = _time_root_final_lines(equation)
    reveals = [
        _sub_reveal(
            "start_from_previous_equation",
            "Now we solve the landing equation from the previous step, instead of jumping to the time formula.",
            "Keep the landing condition highlighted.",
            [canonical],
            focus_ids,
            focus_ids,
        ),
        _sub_reveal(
            "factor_time",
            "Both terms contain T, so we factor T out. Here, root means a solution of the factored equation, not a square-root operation.",
            "Show the time factor and the remaining bracket.",
            [canonical, "0 = T(u_y - gT/2)"],
            focus_ids,
            focus_ids,
        ),
        _sub_reveal(
            "discard_launch_instant",
            "The first solution is T = 0, which is only the launch instant. We need the later landing time, so we use the other factor.",
            "Fade the launch instant and keep the landing event highlighted.",
            ["T = 0", "u_y - gT/2 = 0"],
            focus_ids,
            focus_ids,
        ),
        _sub_reveal(
            "solve_remaining_factor",
            "Now solve the remaining linear equation step by step: move gT/2 to the other side, then multiply by 2/g.",
            "Highlight the algebra that produces the flight time.",
            ["u_y = gT/2", "2u_y = gT", "T = 2u_y/g"],
            focus_ids,
            focus_ids,
        ),
    ]
    if final_lines and "sin" in _compact_equation(equation):
        reveals.append(_sub_reveal(
            "replace_vertical_component",
            "If the launch angle is measured from the horizontal, the vertical component is u_y = u sin(theta). Now we replace u_y with that component.",
            "Highlight the vertical component of the launch velocity.",
            final_lines,
            list(dict.fromkeys([*focus_ids, "vector:uy", "quantity:uy"])),
            list(dict.fromkeys(["vector:uy", "quantity:uy", *focus_ids[:2]])),
        ))
    if substitution:
        reveals.append(_sub_reveal(
            "numeric_substitution",
            "Now substitute the known values into this derived relation.",
            "Replace symbols with known values.",
            [substitution],
            focus_ids,
            focus_ids,
        ))
    if result:
        reveals.append(_sub_reveal(
            "result",
            f"This gives {result}.",
            "Highlight the computed quantity.",
            [result],
            ["answer", *focus_ids[:2]],
            ["answer", *focus_ids[:2]],
        ))
    return reveals


def _vertical_component_time_sub_reveals(focus_ids: list[str]) -> list[dict]:
    component_ids = list(dict.fromkeys([*focus_ids, "velocity:launch", "vector:uy", "quantity:uy", "quantity:theta"]))
    return [
        _sub_reveal(
            "recall_vertical_component",
            "From the earlier vector-resolution beat, the component opposite theta is u_y = u sin(theta).",
            "Show the launch vector and its vertical projection only.",
            ["u_y = u sin(theta)"],
            component_ids,
            ["vector:uy", "quantity:uy"],
        ),
        _sub_reveal(
            "substitute_vertical_component",
            "Substitute that component into T = 2u_y/g. This converts the component form into the launch-speed form.",
            "Keep the vertical component visible while the symbolic formula changes.",
            ["T = 2u_y/g", "T = 2u sin(theta)/g"],
            component_ids,
            ["equation:flight_time_substitution", "quantity:T"],
        ),
    ]


def _horizontal_range_sub_reveals(focus_ids: list[str]) -> list[dict]:
    range_ids = list(dict.fromkeys([*focus_ids, "vector:ux", "quantity:ux", "quantity:R", "point:landing"]))
    return [
        _sub_reveal(
            "zero_horizontal_acceleration",
            "Gravity has no horizontal component, so a_x = 0 and the horizontal velocity does not change.",
            "Keep the horizontal velocity arrow unchanged along the path.",
            ["a_x = 0", "v_x(t) = u_x"],
            range_ids,
            ["vector:ux", "quantity:ux"],
        ),
        _sub_reveal(
            "constant_speed_distance",
            "Horizontal displacement equals constant horizontal speed multiplied by the total flight time. Therefore the landing displacement is R = u_x T.",
            "Connect the unchanged horizontal velocity to the launch-to-landing range marker.",
            ["R = v_x T", "v_x = u_x", "R = u_x T"],
            range_ids,
            ["quantity:R", "point:landing"],
        ),
    ]


def _height_launch_positive_root_sub_reveals(equation: str, substitution: str, result: str, focus_ids: list[str]) -> list[dict]:
    reveals = [
        _sub_reveal(
            "start_from_ground_equation",
            "Start from the ground-impact equation. Since launch height is nonzero, the equation does not factor into T times a linear term.",
            "Highlight the height from launch level to the ground-impact point.",
            ["0 = h + u_yT - 1/2 gT^2"],
            focus_ids,
            focus_ids,
        ),
        _sub_reveal(
            "choose_positive_root",
            "Solving the quadratic gives two mathematical roots. The negative root is before launch, so the physical impact time is the positive root.",
            "Keep only the later impact event on the trajectory.",
            [equation],
            focus_ids,
            focus_ids,
        ),
    ]
    if substitution:
        reveals.append(_sub_reveal(
            "numeric_substitution",
            "Now substitute the known values into the positive-root expression.",
            "Replace symbols with known values.",
            [substitution],
            focus_ids,
            focus_ids,
        ))
    if result:
        reveals.append(_sub_reveal(
            "result",
            f"This gives {result}.",
            "Highlight the computed impact time.",
            [result],
            ["answer", *focus_ids[:2]],
            ["answer", *focus_ids[:2]],
        ))
    return reveals


def _compact_equation(equation: str) -> str:
    return equation.lower().replace(" ", "").replace("−", "-")


def _is_zero_vertical_event_equation(equation: str) -> bool:
    lowered = _compact_equation(equation)
    if not lowered.startswith("0="):
        return False
    if "gt^2" not in lowered and "g*t^2" not in lowered:
        return False
    return any(token in lowered for token in ["u_y", "uy", "usin", "h+"])


def _is_nonzero_time_root_equation(equation: str) -> bool:
    lowered = _compact_equation(equation)
    if not lowered.startswith("t="):
        return False
    return any(token in lowered for token in ["2u_y/g", "2uy/g", "2usin", "2u*sin"])


def _is_vertical_component_time_substitution(equation: str) -> bool:
    lowered = _compact_equation(equation)
    return lowered.startswith(("u_y=", "uy=", "uᵧ=")) and "sin" in lowered and "t=" in lowered


def _is_horizontal_range_equation(equation: str) -> bool:
    lowered = _compact_equation(equation)
    return lowered.startswith("r=") and any(token in lowered for token in ("u_xt", "uₓt", "uxt"))


def _is_height_launch_positive_root_equation(equation: str) -> bool:
    lowered = _compact_equation(equation)
    return lowered.startswith("t=") and "sqrt" in lowered and "2gh" in lowered


def _is_incline_return_time_equation(equation: str) -> bool:
    lowered = _compact_equation(equation)
    return (lowered.startswith("t_return=") or lowered.startswith("treturn=")) and "gcos" in lowered


def _is_incline_along_displacement_equation(equation: str) -> bool:
    lowered = _compact_equation(equation)
    return lowered.startswith("s=") and ("1/2" in lowered or "0.5" in lowered) and "gsin" in lowered and "t^2" in lowered


def _is_incline_range_formula_equation(equation: str) -> bool:
    lowered = _compact_equation(equation)
    return lowered.startswith("s=2u^2") and "sin" in lowered and "cos^2" in lowered


def _canonical_zero_time_equation(equation: str) -> str:
    lowered = _compact_equation(equation)
    if "h+" in lowered:
        return "0 = h + u_y T - 1/2 gT^2"
    return "0 = u_y T - 1/2 gT^2"


def _time_root_final_lines(equation: str) -> list[str]:
    lowered = _compact_equation(equation)
    if "sin" in lowered or "u_y" in lowered or "uy" in lowered:
        lines = ["T = 2u_y/g"]
        if "sin" in lowered:
            lines.extend(["u_y = u sin(theta)", equation])
        return lines
    return [equation] if equation else []


def _is_indexed_collision_equation(equation: str) -> bool:
    lowered = equation.lower()
    return _is_indexed_face_time_equation(lowered) or _is_indexed_drop_equation(lowered) or _is_indexed_hit_inequality(lowered)


def _is_indexed_face_time_equation(lowered_equation: str) -> bool:
    return "x_n" in lowered_equation and "n w" in lowered_equation and "t_n" in lowered_equation


def _is_indexed_drop_equation(lowered_equation: str) -> bool:
    return "y_n" in lowered_equation and "t_n^2" in lowered_equation


def _is_indexed_hit_inequality(lowered_equation: str) -> bool:
    return "y_n" in lowered_equation and "n h" in lowered_equation and (">=" in lowered_equation or ">" in lowered_equation)


def _sub_reveal(
    id: str,
    text: str,
    visual_instruction: str,
    formula_lines: list[str],
    reveal_ids: list[str],
    highlight_ids: list[str],
) -> dict:
    return {
        "id": id,
        "text": text,
        "visual_instruction": visual_instruction,
        "formula_lines": [line for line in formula_lines if line],
        "reveal_ids": list(dict.fromkeys(reveal_ids)),
        "highlight_ids": list(dict.fromkeys(highlight_ids)),
        "visual_plan": _visual_plan_for_reveal(id, text, visual_instruction, formula_lines, reveal_ids, highlight_ids),
    }


def _visual_plan_for_beat(step: dict, sub_reveals: list[dict], result: EvaluationResult) -> dict:
    step_id = str(step.get("id") or "")
    action = str(step.get("visual_action") or step.get("animation_intent") or "focus_relevant_step")
    focus_ids = list(dict.fromkeys(list(step.get("focus_ids") or []) + list(step.get("highlight_ids") or [])))
    reveal_ids = list(dict.fromkeys(focus_ids + [item for reveal in sub_reveals for item in reveal.get("reveal_ids", [])]))
    highlight_ids = list(dict.fromkeys(list(step.get("highlight_ids") or focus_ids) + [item for reveal in sub_reveals for item in reveal.get("highlight_ids", [])]))
    text_blob = " ".join(
        [
            step_id,
            str(step.get("title") or ""),
            str(step.get("explanation") or ""),
            str(step.get("equation") or step.get("formula") or ""),
            " ".join(str(line) for reveal in sub_reveals for line in reveal.get("formula_lines", [])),
            " ".join(reveal.get("text", "") for reveal in sub_reveals),
        ]
    ).lower()
    labels = _visual_labels_from_text(text_blob)
    visual_ids = list(dict.fromkeys(focus_ids + reveal_ids + highlight_ids))
    has_incline = _visual_plan_has_incline_context(result=result, focus_ids=visual_ids, text=text_blob)
    visible_vectors = _visual_vectors_from_text(text_blob, action, visual_ids, labels, has_incline=has_incline)
    if step_id == "invariant" and not _focus_requests_vector(focus_ids) and not _text_requests_axes_or_components(text_blob):
        visible_vectors = ["__none__"]
    if visible_vectors == ["__none__"]:
        labels = [
            label for label in labels
            if not str(label.get("target_id") or "").startswith(("gravity:", "velocity:"))
        ]
    overlays = _visual_overlays_from_text(text_blob, action, visible_vectors, step_id, has_incline=has_incline)
    motion = _visual_motion_from_text(text_blob, action, step_id)
    if step_id == "takeaway":
        plan = {
            "type": "text_only",
            "visual_action": "highlight_final_answer",
            "scene_phase": "answer",
            "show_ids": ["answer", *focus_ids],
            "hide_ids": [],
            "highlight_ids": ["answer", *highlight_ids[:3]],
            "visible_vectors": ["__none__"],
            "overlays": ["show_final_answer"],
            "labels": [{"target_id": "answer", "text": str(result.computed_text or "answer"), "placement": "center", "priority": 1}],
            "motion": {"mode": "freeze", "event": "answer"},
            "camera": "full_scene",
        }
        return attach_beat_visual_spec(
            result=result,
            step_id=step_id,
            title=str(step.get("title") or ""),
            text=text_blob,
            visual_plan=plan,
        )
    plan = {
        "type": "scene",
        "visual_action": action,
        "scene_phase": _scene_phase_from_text(text_blob, action),
        "show_ids": reveal_ids,
        "hide_ids": _hide_ids_for_text(text_blob),
        "highlight_ids": highlight_ids,
        "visible_vectors": visible_vectors,
        "overlays": overlays,
        "labels": labels,
        "motion": motion,
        "camera": _camera_hint_for_text(text_blob, action),
    }
    return attach_beat_visual_spec(
        result=result,
        step_id=step_id,
        title=str(step.get("title") or ""),
        text=text_blob,
        visual_plan=plan,
    )


def _visual_plan_for_reveal(
    id: str,
    text: str,
    visual_instruction: str,
    formula_lines: list[str],
    reveal_ids: list[str],
    highlight_ids: list[str],
) -> dict:
    text_blob = " ".join([id, text, visual_instruction, " ".join(formula_lines)]).lower()
    labels = _visual_labels_from_text(text_blob)
    has_incline = _ids_have_incline_context(list(reveal_ids) + list(highlight_ids))
    plan = {
        "type": "scene",
        "show_ids": list(dict.fromkeys(reveal_ids)),
        "highlight_ids": list(dict.fromkeys(highlight_ids)),
        "visible_vectors": _visual_vectors_from_text(text_blob, "", list(reveal_ids), labels, has_incline=has_incline),
        "labels": labels,
        "motion": _visual_motion_from_text(text_blob, "", id),
    }
    plan["visual_state"] = _visual_state_for_plan(plan)
    return plan


def _visual_state_for_plan(plan: dict) -> dict:
    visible_ids = [str(item) for item in plan.get("show_ids") or [] if str(item)]
    vector_ids = [str(item) for item in plan.get("visible_vectors") or [] if str(item)]
    highlight_ids = [str(item) for item in plan.get("highlight_ids") or [] if str(item)]
    label_ids = [str(label.get("target_id")) for label in plan.get("labels") or [] if str(label.get("target_id") or "")]
    return {
        "visible_ids": list(dict.fromkeys(visible_ids)),
        "visible_vectors": list(dict.fromkeys(vector_ids)),
        "highlight_ids": list(dict.fromkeys(highlight_ids)),
        "label_ids": list(dict.fromkeys(label_ids)),
        "dimmed_ids": list(dict.fromkeys(str(item) for item in plan.get("dimmed_ids") or [] if str(item))),
        "persist_until": "next_beat",
    }


def _visual_labels_from_text(text: str) -> list[dict]:
    labels: list[dict] = []
    compact = text.replace(" ", "")
    if "gsin" in compact or "g_parallel" in compact or "gparallel" in compact:
        labels.append({"target_id": "gravity:tangent_component", "text": _component_label(text, "g sin alpha"), "placement": "above_arrow", "priority": 1})
    if "gcos" in compact or "g_normal" in compact or "gnormal" in compact:
        labels.append({"target_id": "gravity:normal_component", "text": _component_label(text, "g cos alpha"), "placement": "above_arrow", "priority": 1})
    if "v_n=0" in compact or "normalcomponentofvelocityiszero" in compact or "normal velocity component" in text:
        labels.append({"target_id": "velocity:normal_component", "text": "v_n = 0", "placement": "above_arrow", "priority": 1})
    if "along-plane component" in text or "final velocity has zero along" in text or "parallel" in text:
        label = "v_parallel = 0" if "zero" in text or "=0" in compact else "v_parallel"
        labels.append({"target_id": "velocity:tangent_component", "text": label, "placement": "above_arrow", "priority": 1})
    if "t_n" in text:
        labels.append({"target_id": "quantity:t_n", "text": "t_n = x_n / v_x", "placement": "board", "priority": 2})
    if "y_n" in text or "drop" in text:
        labels.append({"target_id": "quantity:drop", "text": "y_n = 1/2 g t_n^2", "placement": "board", "priority": 2})
    return _dedupe_labels(labels)


def _component_label(text: str, fallback: str) -> str:
    if "beta" in text:
        return fallback.replace("alpha", "beta")
    if "theta" in text:
        return fallback.replace("alpha", "theta")
    if "60" in text:
        return fallback.replace("alpha", "60deg")
    return fallback


def _dedupe_labels(labels: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for label in labels:
        key = (str(label.get("target_id")), str(label.get("text")))
        if key in seen:
            continue
        seen.add(key)
        out.append(label)
    return out


def _visual_plan_has_incline_context(*, result: EvaluationResult, focus_ids: list[str], text: str) -> bool:
    incline_cases = {
        "inclined_plane_impact_time",
        "inclined_plane_right_angle_impact_condition",
        "inclined_plane_same_point_time_ratio",
        "inclined_plane_max_normal_distance_velocity_component",
        "perpendicular_launch_range_on_incline",
        "max_range_on_incline",
        "horizontal_launch_onto_incline_distance",
        "projectile_collides_with_sliding_particle_on_incline",
        "motion_on_smooth_incline_perpendicular_to_slope",
        "two_inclines_perpendicular_launch_impact",
    }
    return result.engine_case in incline_cases or _ids_have_incline_context(focus_ids)


def _ids_have_incline_context(ids: list[str]) -> bool:
    joined = " ".join(str(item).lower() for item in ids)
    return "incline" in joined or "inclined_plane" in joined or "surface:plane" in joined


def _focus_requests_vector(focus_ids: list[str]) -> bool:
    joined = " ".join(str(item).lower() for item in focus_ids)
    return "vector:" in joined or "quantity:u" in joined or "velocity" in joined


def _text_requests_axes_or_components(text: str) -> bool:
    return any(
        token in text
        for token in (
            "axis",
            "component",
            "resolve",
            "x-y plane",
            "x -y plane",
            "horizontal and vertical",
            "horizontal motion",
            "vertical motion",
            "u_x",
            "u_y",
            "v_x",
            "v_y",
        )
    )


def _visual_vectors_from_text(text: str, action: str, focus_ids: list[str], labels: list[dict], *, has_incline: bool) -> list[str]:
    vectors: list[str] = []
    label_targets = {str(item.get("target_id")) for item in labels}
    component_or_axis_text = (
        "axis" in text
        or "component" in text
        or "resolve" in text
        or "u_x" in text
        or "u_y" in text
        or "v_x" in text
        or "v_y" in text
    )
    if has_incline and any(target.startswith("gravity:") for target in label_targets):
        if any("tangent" in target or "parallel" in target for target in label_targets):
            vectors.append("gravity:tangent_component")
        if any("normal" in target for target in label_targets):
            vectors.append("gravity:normal_component")
        vectors.extend(["incline:tangent_axis", "incline:normal_axis"])
    if has_incline and any(target.startswith("velocity:") for target in label_targets):
        if any("tangent" in target or "parallel" in target for target in label_targets):
            vectors.append("velocity:tangent_component")
        if any("normal" in target for target in label_targets):
            vectors.append("velocity:normal_component")
        vectors.extend(["incline:tangent_axis", "incline:normal_axis"])
    if has_incline and ("axis" in text or "incline:normal_axis" in " ".join(focus_ids) or "incline:tangent_axis" in " ".join(focus_ids)):
        vectors.extend(["incline:tangent_axis", "incline:normal_axis"])
    if has_incline and any(token in text for token in ("along the plane", "along-plane", "normal to the plane", "normal direction", "range along")):
        vectors.extend(["incline:tangent_axis", "incline:normal_axis"])
    if not has_incline and component_or_axis_text:
        vectors.extend(["x_axis", "y_axis"])
    if "vector:u" in focus_ids or "quantity:u" in focus_ids or "launch vector" in text or action == "zoom_launch_vector":
        vectors.extend(["*:v"])
    if "velocity component" in text or "resolve the launch" in text or "u_x" in text or "u_y" in text or "v_x" in text or "v_y" in text:
        vectors.extend(["*:v", "*:vx", "*:vy"])
    if "vertical" in text:
        vectors.extend(["*:vy", "*:a"])
    if not vectors and ("answer" in text or action == "highlight_final_answer"):
        return ["__none__"]
    if not vectors and action == "show_full_scene":
        return ["__none__"]
    return list(dict.fromkeys(vectors or ["*:v"]))


def _visual_overlays_from_text(text: str, action: str, visible_vectors: list[str], step_id: str, *, has_incline: bool) -> list[str]:
    if action == "show_launch_setup":
        return ["show_scene"]
    overlays: list[str] = []
    motion_mode = str(_visual_motion_from_text(text, action, step_id).get("mode") or "")
    static = _is_static_visual_text(text, action, step_id) or motion_mode in {"static", "freeze"}
    if not static:
        overlays.append("show_trajectory")
    if any(item not in {"__none__"} for item in visible_vectors):
        overlays.append("show_velocity_components")
    if has_incline and ("incline:normal_axis" in visible_vectors or "perpendicular" in text or "right angle" in text):
        overlays.append("show_perpendicular_marker")
    if "range" in text:
        overlays.append("show_range_marker")
    if "same height" in text or "same level" in text or "delta_y" in text or "vertical displacement" in text:
        overlays.append("show_same_height")
    if "wall" in text:
        overlays.append("show_wall")
    if "target" in text:
        overlays.append("show_target")
    if "timer" in text or " time" in text or "t_n" in text:
        overlays.append("show_timer")
    if "height" in text or "drop" in text or "y_n" in text:
        overlays.append("show_height_marker")
    if not static and action not in {"show_full_scene"}:
        overlays.append("show_motion_progress")
    if "answer" in text or action == "highlight_final_answer":
        overlays.append("show_final_answer")
    if step_id == "invariant" and any(token in text for token in ("parametric", "curve", "path shape")):
        overlays.append("show_trajectory")
    return list(dict.fromkeys(overlays or ["show_scene"]))


def _visual_motion_from_text(text: str, action: str, step_id: str) -> dict:
    if step_id == "takeaway" or "answer" in text:
        return {"mode": "freeze", "event": "answer"}
    if step_id == "invariant":
        return {"mode": "static"}
    if _is_formula_or_relation_text(text) and not _has_explicit_motion_language(text):
        return {"mode": "static"}
    if action == "show_full_scene":
        return {"mode": "static"}
    if "maximum normal" in text or "farthest" in text:
        return {"mode": "freeze", "event": "max_normal_distance"}
    if action in {"highlight_collision", "show_normal_return"} or "collision" in text or "impact" in text:
        return {"mode": "partial", "event": "impact"}
    if action == "highlight_vertical_motion" or "landing" in text or "returns to the plane" in text or "comes back" in text:
        return {"mode": "partial"}
    if action == "highlight_range" and any(token in text for token in ["flight", "landing", "impact", "trajectory", "motion"]):
        return {"mode": "partial"}
    if "component" in text or "axis" in text or "given" in text or "diagram" in text:
        return {"mode": "static"}
    if "trajectory" in text or "motion" in text:
        return {"mode": "partial"}
    return {"mode": "static"}


def _scene_phase_from_text(text: str, action: str) -> str:
    if "maximum normal" in text:
        return "max_normal_distance"
    if "collision" in text:
        return "collision"
    if "impact" in text or "right angle" in text:
        return "impact"
    if "stair" in text:
        return "staircase_step"
    if "component" in text or "axis" in text:
        return "component_resolution"
    if "answer" in text or action == "highlight_final_answer":
        return "answer"
    return action or "setup"


def _hide_ids_for_text(text: str) -> list[str]:
    hidden = []
    if "component" in text or "axis" in text or "given" in text:
        hidden.extend(["quantity:R", "quantity:H", "event:landing", "event:apex"])
    return hidden


def _camera_hint_for_text(text: str, action: str) -> str:
    if "component" in text or "axis" in text or action == "zoom_launch_vector":
        return "setup"
    if "impact" in text:
        return "impact"
    if "collision" in text:
        return "collision"
    if "landing" in text:
        return "landing"
    return "full_scene"


def _is_static_visual_text(text: str, action: str, step_id: str) -> bool:
    if action in {"highlight_collision", "show_normal_return"}:
        return False
    if action == "highlight_vertical_motion":
        return not _has_explicit_motion_language(text)
    if action == "highlight_range" and _has_explicit_motion_language(text):
        return False
    if action in {"highlight_range", "show_incline_axes", "zoom_launch_vector"}:
        return True
    if any(token in text for token in ["given", "diagram", "axis", "component", "condition", "equation", "substitute", "let n", "step number", "inequality", "first whole number", "first integer"]):
        return True
    return False


def _is_formula_or_relation_text(text: str) -> bool:
    return any(token in text for token in [
        "formula",
        "relation",
        "equation",
        "substitute",
        "simplify",
        "equals",
        "constant horizontal velocity",
        "symbolic",
        "replace",
        "satisfies",
    ])


def _has_explicit_motion_language(text: str) -> bool:
    return any(token in text for token in [
        "animate",
        "watch",
        "replay",
        "flies",
        "flight path",
        "comes back",
        "returns to",
        "strikes",
        "strike ",
        "hits ",
        "hit ",
        "touches",
        "catch",
        "collide",
        "meet after",
        "motion progress",
    ])


def _learner_message_for_step(step: dict, result: EvaluationResult) -> str:
    explanation = str(step.get("explanation") or "").strip()
    teaching_goal = str(step.get("teaching_goal") or step.get("student_goal") or "").strip()
    if explanation and not _is_weak_teacher_text(explanation):
        return explanation
    tailored = _tailored_learner_message(step, result)
    if tailored:
        return tailored
    if teaching_goal:
        return teaching_goal
    unknown = str((result.equation_plan or {}).get("unknown") or "the requested quantity")
    return f"Use this part of the scene to move toward {unknown}."


def _is_weak_teacher_text(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in [
        "this equation is used because",
        "now substitute the known values",
        "report only the requested quantity",
        "now we use the relation",
        "using physical invariant",
        "compute the requested answer",
    ])


def _tailored_learner_message(step: dict, result: EvaluationResult) -> str:
    step_id = str(step.get("id") or "").lower()
    title = str(step.get("title") or "").lower()
    equation = str(step.get("equation") or step.get("formula") or "").lower()
    engine = str(result.engine_case or "")
    unknown = str((result.equation_plan or {}).get("unknown") or "the requested quantity").replace("_", " ")
    if engine == "perpendicular_launch_range_on_incline":
        if "t_return" in equation or "time" in title:
            return "The ball leaves normal to the plane and returns to the plane under the normal component of gravity."
        if "1/2" in equation and "sin" in equation:
            return "Along the plane, the initial component is zero. The range comes only from the down-plane component of gravity during the return time."
        if "2u^2" in equation or "compute" in title or "answer" in title:
            return f"Now combine return time with down-plane displacement to get {unknown}."
    if engine == "projectile_collides_with_sliding_particle_on_incline" and step_id == "solve_u":
        return "The collision time is given. Put that time into the normal-return equation to isolate the required launch speed."
    if "compute" in title or "answer" in title or step_id in {"answer", "solve_3", "solve_4"}:
        return f"Now simplify the active relation and write {unknown} with the correct unit or option."
    if engine == "inclined_plane_max_normal_distance_velocity_component":
        return "At the farthest point from the incline, the particle has stopped moving away from the plane for that instant. So the normal component of velocity is zero there."
    if engine == "inclined_plane_right_angle_impact_condition":
        return "For a right-angle hit, the final velocity must be normal to the incline. That means the final along-plane component is zero."
    if engine == "two_inclines_perpendicular_launch_impact":
        return "The diagram fixes two velocity directions: launch is normal to one plane and impact is normal to the other. We use those directions to compare the same velocity components."
    if engine == "motion_on_smooth_incline_perpendicular_to_slope":
        return "On a smooth incline, gravity creates speed only down the line of greatest slope. The initial sideways component stays perpendicular to that gained component."
    if "g sin" in equation or "g cos" in equation or "component" in title:
        return "We split the vector along axes that match the surface. One component lies along the plane; the other is normal to the plane."
    return ""


def _visual_instruction_for_step(step: dict) -> str:
    focus = list(step.get("focus_ids") or step.get("highlight_ids") or [])
    action = str(step.get("visual_action") or step.get("animation_intent") or "focus_relevant_step").replace("_", " ")
    if focus:
        return f"{action}. Highlight {', '.join(str(item) for item in focus[:4])}."
    return action


def _formula_lines(*lines: str) -> list[str]:
    out: list[str] = []
    for line in lines:
        cleaned = str(line or "").strip()
        if cleaned and cleaned not in out:
            out.append(cleaned)
    return out


def _is_vector_resolution_text(*, step_id: str, title: str, equation: str, focus_ids: list[str]) -> bool:
    lowered = " ".join([step_id, title, equation, " ".join(focus_ids)]).lower()
    if _is_incline_return_time_equation(equation) or _is_incline_along_displacement_equation(equation) or _is_incline_range_formula_equation(equation):
        return False
    if equation.strip().lower().startswith(("s =", "s=", "r =", "r=", "t =", "t=", "t_return", "treturn")):
        return False
    if "constant" in lowered or "no horizontal force" in lowered:
        return False
    if any(token in lowered for token in ["landing", "range", "flight", "answer", "takeaway", "collision_condition"]):
        return False
    if "resolve" in lowered or "component" in lowered:
        return True
    if any(token in lowered for token in ["normal_axis", "tangent_axis"]):
        return True
    if re.search(r"\b[uv]_[xy]\b", lowered) and any(token in lowered for token in ("resolve", "component", "sin", "cos", "theta", "angle")):
        return True
    return False


def _is_diagram_condition_step(step_id: str, equation: str, focus_ids: list[str]) -> bool:
    lowered = " ".join([step_id, equation, " ".join(focus_ids)]).lower()
    return "read_diagram" in lowered or "diagram" in lowered or "projected normal" in lowered or "released on" in lowered


def _is_same_axis_motion_step(step_id: str, equation: str) -> bool:
    lowered = f"{step_id} {equation}".lower()
    return "along_plane" in lowered or ("s_p" in lowered and "s_q" in lowered)


def _is_normal_return_step(step_id: str, equation: str) -> bool:
    lowered = f"{step_id} {equation}".lower()
    return "normal_plane" in lowered or "n_p" in lowered or "normal separation" in lowered


def _axis_ids_from_focus(focus_ids: list[str], fallback: list[str]) -> list[str]:
    axes = [item for item in focus_ids if "axis" in item]
    return axes or fallback


def _parent_equation_for(equation: str) -> str:
    lowered = equation.lower().replace(" ", "")
    if "s=" in lowered or "x=" in lowered or "y=" in lowered or "h+" in lowered or "gt^2" in lowered or "t^2" in lowered:
        return "s = ut + 1/2 at^2"
    if "v_y" in lowered or lowered.startswith("v=") or "v=" in lowered:
        return "v = u + at"
    if "v^2" in lowered or "sqrt" in lowered:
        return "v^2 = u^2 + 2as"
    if "r=" in lowered or "range" in lowered:
        return "R = u_x t"
    return ""


def _relation_reason(equation: str) -> str:
    lowered = equation.lower()
    if _is_nonzero_time_root_equation(equation):
        return "We are solving the landing-time equation and choosing the later physical solution."
    if _is_zero_vertical_event_equation(equation):
        return "The event condition gives the vertical displacement equation for landing."
    if "0 =" in lowered:
        return "Here, the event condition makes one displacement or velocity zero, so we write that condition explicitly."
    if "x =" in lowered or "r =" in lowered:
        return "In horizontal motion there is no acceleration, so we use constant horizontal velocity to get distance."
    if "y =" in lowered or "h +" in lowered:
        return "Vertical motion carries the gravitational term, so we use it for height or time."
    if "sin" in lowered or "cos" in lowered or "tan" in lowered:
        return "This relation comes from projecting a vector onto the axis we chose."
    return "This relation contains the unknown and the quantities already established, so it is the next solvable link in the chain."


def _angle_symbol_from_text(text: str) -> str:
    lowered = text.lower()
    if "alpha" in lowered or "α" in text:
        return "alpha"
    if "theta" in lowered or "θ" in text:
        return "theta"
    if "60" in text:
        return "60deg"
    return "angle"


def _component_lines_for(equation: str, angle: str) -> list[str]:
    lowered = equation.lower()
    if "u_x" in lowered and "u_y" in lowered:
        return [f"u_x = u cos({angle})", f"u_y = u sin({angle})"]
    if "v_x" in lowered and "v_y" in lowered:
        return [f"v_x = v cos({angle})", f"v_y = v sin({angle})"]
    if "normal" in lowered or "g cos" in lowered or "g sin" in lowered:
        return [f"g_normal = g cos({angle})", f"g_parallel = g sin({angle})"]
    return [f"adjacent component = magnitude cos({angle})", f"opposite component = magnitude sin({angle})"]


def _component_reveal_ids_for(equation: str, focus_ids: list[str]) -> tuple[list[str], list[str], list[str]]:
    lowered = equation.lower()
    if "u_x" in lowered and "u_y" in lowered:
        return ["vector:u"], ["vector:ux", "quantity:ux"], ["vector:uy", "quantity:uy"]
    if "v_x" in lowered and "v_y" in lowered:
        return ["vector:v"], ["vector:vx", "quantity:vx"], ["vector:vy", "quantity:vy"]
    if "normal" in lowered or "g cos" in lowered or "g sin" in lowered:
        return ["vector:g"], ["incline:normal_axis"], ["incline:tangent_axis"]
    return [focus_ids[0]] if focus_ids else ["vector:v"], focus_ids[1:2] or ["vector:vx"], focus_ids[2:3] or ["vector:vy"]




def _smooth_incline_speed(result: EvaluationResult) -> list[dict]:
    return [
        _step(
            id="components",
            title="Use perpendicular directions on the plane",
            formula="v^2 = v_0^2 + (g sin alpha t)^2",
            explanation="The initial velocity is perpendicular to the line of greatest slope. Gravity adds a down-slope component, perpendicular to the initial component.",
            animation_intent="show_smooth_plane_component_axes",
            focus_ids=["incline", "initial_velocity"],
        ),
        _step(
            id="down_slope",
            title="Find the new down-slope component",
            formula="v_s = g sin(alpha) t",
            explanation=_trace_or(result, 1, "After one second, acceleration down the slope creates the second component of velocity."),
            animation_intent="animate_down_slope_velocity_growth",
            focus_ids=["down_slope_velocity"],
        ),
        _step(
            id="resultant",
            title="Combine perpendicular components",
            formula=result.computed_text or "",
            explanation=_trace_or(result, 2, f"The resultant speed is {result.computed_text}."),
            animation_intent="show_resultant_velocity",
            focus_ids=["resultant_velocity", "answer"],
        ),
    ]


def _generic_walkthrough(result: EvaluationResult) -> list[dict]:
    steps: list[dict] = [
        _step(
            id="identify",
            title="Identify the requested quantity",
            formula="",
            explanation=f"This problem is routed to `{result.engine_case}`.",
            animation_intent="show_problem_setup",
            focus_ids=["setup"],
        )
    ]
    for index, trace in enumerate(result.trace, start=1):
        steps.append(
            _step(
                id=f"solve_{index}",
                title=f"Step {index}",
                formula="",
                explanation=trace,
                animation_intent="show_solution_step",
                focus_ids=["solution"],
            )
        )
    if result.computed_text:
        steps.append(
            _step(
                id="answer",
                title="Final answer",
                formula=result.computed_text,
                explanation=f"The answer is {result.computed_text}.",
                animation_intent="highlight_final_answer",
                focus_ids=["answer"],
            )
        )
    return steps


def _trace_or(result: EvaluationResult, index: int, fallback: str) -> str:
    if 0 <= index < len(result.trace):
        return result.trace[index]
    return fallback
