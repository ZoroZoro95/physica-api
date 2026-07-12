#!/usr/bin/env python3
"""Regression checks for backend animation scene specs."""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.projectile_engine.animation_scene import build_animation_scene_spec
from core.projectile_engine.evaluator import solve_ad_hoc_question
from core.projectile_engine.scene_contract import validate_animation_scene_spec
from core.projectile_engine.visual_director import default_visual_director
from core.projectile_engine.walkthrough import build_solution_walkthrough


def main() -> None:
    failures: list[str] = []
    cases = [
        {
            "name": "level maximum range",
            "question": "Projectile launched at 45deg with 25 m/s. Find the maximum range.",
            "world": "level_ground",
            "unknown": "maximum_range",
            "quantity": ("R", 62.5),
        },
        {
            "name": "level range and time together",
            "question": "A ball is thrown at u=16 m/s at 53 deg. Find range and time of flight.",
            "world": "level_ground",
            "unknown": "level_ground_multi_quantity",
            "quantity": ("T", 2 * 16 * math.sin(math.radians(53)) / 10),
            "storyboard_camera": "landing",
        },
        {
            "name": "level multi quantity scene",
            "question": (
                "A projectile is launched at 20 m/s at 30deg. Find range, time of flight, "
                "maximum height, and velocity components. Take g = 10 m/s^2."
            ),
            "world": "level_ground",
            "unknown": "level_ground_multi_quantity",
            "quantity": ("H", 5.0),
            "storyboard_camera": "landing",
        },
        {
            "name": "height launch range",
            "question": (
                "A projectile is fired from a 45 m high cliff with speed 20 m/s at 30deg above horizontal. "
                "Find the horizontal range. Take g = 10 m/s^2."
            ),
            "world": "height_launch",
            "unknown": "range",
            "quantity": ("R", 10 * math.sqrt(3) * (1 + math.sqrt(10))),
        },
        {
            "name": "wall clearance",
            "question": (
                "A projectile is launched at 20 m/s at 45deg toward a wall 20 m away and 8 m high. "
                "Does it clear the wall? Take g = 10 m/s^2."
            ),
            "world": "wall",
            "unknown": "wall_clearance",
            "obstacle": "wall",
            "storyboard_overlay": "show_wall",
            "storyboard_camera": "wall_top",
        },
        {
            "name": "target launch angle",
            "question": (
                "A projectile is fired with speed 20 m/s to hit a target at (20 m, 10 m). "
                "Find all launch angles. Take g = 10 m/s^2."
            ),
            "world": "target",
            "unknown": "launch_angle",
            "point": "target",
            "storyboard_overlay": "show_target",
            "storyboard_camera": "target",
        },
        {
            "name": "position at time",
            "question": (
                "A projectile is launched from level ground with speed 20 m/s at 30deg. "
                "Find its position after 1 s. Take g = 10 m/s^2."
            ),
            "world": "level_ground",
            "unknown": "position_at_time",
            "point": "position_at_t",
        },
        {
            "name": "projectile split at apex scene",
            "question": (
                "A projectile is thrown from a point O on the ground at an angle 45deg from the vertical "
                "and with a speed of 5sqrt(2) m/s. The projectile at the highest point of its trajectory "
                "splits into two equal parts. One part falls vertically down to the ground, 0.5 s after "
                "the splitting. The other part, t seconds after the splitting, falls to the ground at a "
                "distance x meters from the point O. The acceleration due to gravity g = 10 m/s^2."
            ),
            "world": "split_at_apex",
            "unknown": "fragment_fall_time",
            "quantity": ("T", 0.5),
            "point": "fragment_2_landing",
            "trajectory_count": 3,
            "phase_windows": True,
            "storyboard_camera": "apex",
            "requires_actor_phase": ("projectile", "fragment_1"),
        },
        {
            "name": "time to peak",
            "question": "A ball is thrown at 15 m/s at an angle of 37 \n∘\n . Calculate time to reach the maximum height.",
            "world": "level_ground",
            "unknown": "time_to_peak",
            "quantity": ("t_peak", 15 * math.sin(math.radians(37)) / 10),
        },
        {
            "name": "vertical upward time to highest point scene",
            "question": "If a ball is thrown upward at 8 m/s, how long to reach the highest point?",
            "world": "level_ground",
            "unknown": "time_to_peak",
            "quantity": ("t_peak", 0.8),
            "storyboard_camera": "apex",
        },
        {
            "name": "time of flight derivation scene",
            "question": "Derive the equation for time of flight for a projectile launched at angle theta with initial speed u",
            "world": "level_ground",
            "unknown": "time_of_flight_derivation",
            "quantity": ("T", 2 * 20 * math.sin(math.radians(45)) / 10),
            "expected_event": "event:landing",
            "storyboard_camera": "landing",
        },
        {
            "name": "horizontal cliff scenario",
            "question": "Ball thrown horizontally at 15 m/s from a 45 m cliff.",
            "world": "height_launch",
            "unknown": "scenario_summary",
            "quantity": ("R", 45.0),
            "surface_type": "vertical_drop",
        },
        {
            "name": "horizontal cliff fall distance time scene",
            "question": (
                "Question 3: If a stone is thrown horizontally from a cliff with a velocity of 10 m/s, "
                "how long will it take to fall 45 m to the ground?"
            ),
            "world": "height_launch",
            "unknown": "time_of_flight",
            "quantity": ("T", 3.0),
            "surface_type": "vertical_drop",
            "expected_event": "event:landing",
            "storyboard_camera": "landing",
        },
        {
            "name": "horizontal tower noun-first height time scene",
            "question": "A stone is thrown horizontally from a tower 80 m high at 5 m/s. How long to reach the ground?",
            "world": "height_launch",
            "unknown": "time_of_flight",
            "quantity": ("T", 4.0),
            "surface_type": "vertical_drop",
            "expected_event": "event:landing",
            "storyboard_camera": "landing",
        },
        {
            "name": "minimum speed target scene",
            "question": (
                "Find the minimum velocity with which a projectile should be fired to hit "
                "a target at (3 m, 4 m). Take g = 10 m/s^2."
            ),
            "world": "target",
            "unknown": "minimum_speed",
            "quantity": ("u", math.sqrt(90)),
            "point": "target",
        },
        {
            "name": "monkey hunter falling target scene",
            "question": (
                "A monkey hangs from a branch 45 m above the ground. A hunter aims directly at the monkey "
                "and fires a projectile with speed 30 m/s. At the instant of firing, the monkey drops. "
                "Explain whether the projectile hits the monkey. Take g = 10 m/s^2."
            ),
            "world": "monkey_hunter",
            "unknown": "falling_target_condition",
            "quantity": ("H", 45.0),
            "point": "hit",
            "surface_type": "aim_line",
            "trajectory_count": 2,
            "actors": {"hunter", "monkey", "projectile"},
            "storyboard_focus": "actor:monkey",
            "expected_event": "event:hit",
        },
        {
            "name": "two projectile collision scene",
            "question": (
                "Projectile A is launched from x=0 with velocity components (20, 30) m/s. "
                "Projectile B is launched simultaneously from x=100 m with velocity components (-10, 30) m/s. "
                "Both have the same gravity. When do they collide?"
            ),
            "world": "multi_projectile",
            "unknown": "collision_time",
            "quantity": ("T", 10 / 3),
            "point": "collision",
            "trajectory_count": 2,
        },
        {
            "name": "two projectile same speed comparison scene",
            "question": (
                "Two projectiles are launched with the same speed of 40 m/s, one at 30 degrees "
                "and the other at 60 degrees. Compare their time of flight, maximum height, and range."
            ),
            "world": "multi_projectile",
            "unknown": "time_height_range_comparison",
            "quantity": ("H2", 60.0),
            "point": "apex_b",
            "trajectory_count": 2,
            "actors": {"projectile_a", "projectile_b"},
            "expected_event": "event:landing_b",
        },
        {
            "name": "two projectile interception ratio comparison scene",
            "question": (
                "A ball is thrown from the location (x0, y0) = (0, 0) of a horizontal playground "
                "with an initial speed v0 at an angle theta0 from the +x-direction. The ball is "
                "to be hit by a stone, which is thrown at the same time from the location "
                "(x1, y1) = (L, 0). The stone is thrown at an angle (180 - theta1) from the "
                "+x-direction with a suitable initial speed. For a fixed v0, when "
                "(theta0, theta1) = (45deg, 45deg), the stone hits the ball after time T1, "
                "and when (theta0, theta1) = (60deg, 30deg), it hits the ball after time T2. "
                "In such a case, (T1/T2)^2 is _______."
            ),
            "world": "multi_projectile",
            "unknown": "time_ratio_squared",
            "quantity": ("ratio_squared", 2.0),
            "point": "collision_2",
            "trajectory_count": 4,
        },
        {
            "name": "two incline transfer scene",
            "question": (
                "Two inclined planes OA and OB with inclinations 30 deg and 60 deg intersect at O. "
                "A particle is projected from P with velocity u = 10*sqrt(3) m/s perpendicular to plane OA. "
                "If it strikes plane OB perpendicularly at Q, find the velocity at Q."
            ),
            "world": "two_inclines",
            "unknown": "impact_speed",
            "quantity": ("v_impact", 10.0),
            "point": "Q",
            "surface_count": 2,
        },
        {
            "name": "staircase scene has treads and risers",
            "question": (
                "A marble rolls down from top of a staircase with constant horizontal velocity 10 m/s. "
                "If each step is 1 m high and 1 m wide. To which step will the marble strike directly?"
            ),
            "world": "staircase",
            "unknown": "step_number",
            "quantity": ("step", 21.0),
            "point": "impact",
            "surface_type": "stair_riser",
            "staircase_contact": True,
        },
        {
            "name": "single incline range scene has incline surface",
            "question": "A projectile is fired perpendicular to an inclined plane of angle 30deg with speed 10 m/s. Find the range on the inclined plane. Take g = 10 m/s^2.",
            "world": "incline",
            "unknown": "range_on_incline",
            "quantity": ("R", 40 / 3),
            "point": "impact",
            "surface_type": "inclined_plane",
            "impact_below_launch": True,
            "surface_descends_right": True,
            "storyboard_focus": "point:impact",
            "allow_no_components": True,
        },
        {
            "name": "projectile and slider incline collision scene",
            "question": (
                "A particle P is projected from a point on the surface of smooth inclined plane. "
                "Simultaneously another particle Q is released on the smooth inclined plane from the same position. "
                "P and Q collide after t = 4 second. The speed of projection of P is:"
            ),
            "world": "incline_collision",
            "unknown": "projection_speed",
            "quantity": ("u", 10.0),
            "givens": ["incline=60deg"],
            "point": "collision",
            "trajectory_count": 2,
            "surface_type": "inclined_plane",
            "allow_no_components": True,
            "storyboard_actions": {"show_incline_axes", "compare_incline_motion", "highlight_collision"},
            "storyboard_focus": "point:collision",
        },
    ]

    for case in cases:
        result = solve_ad_hoc_question(question_text=case["question"], engine_case=None, options=[], givens=case.get("givens", []))
        spec = build_animation_scene_spec(result=result, question_text=case["question"], givens=case.get("givens", []))
        if spec is None:
            failures.append(f"{case['name']}: missing animation scene spec")
            continue
        contract_errors = validate_animation_scene_spec(spec)
        if contract_errors:
            failures.append(f"{case['name']}: contract errors={contract_errors}")
        if spec.get("contract_errors"):
            failures.append(f"{case['name']}: builder contract_errors={spec['contract_errors']}")
        if spec["problem"]["world"] != case["world"]:
            failures.append(f"{case['name']}: world={spec['problem']['world']}")
        if spec["problem"]["unknown"] != case["unknown"]:
            failures.append(f"{case['name']}: unknown={spec['problem']['unknown']}")
        if spec.get("schema_version", 1) < 2:
            failures.append(f"{case['name']}: missing scene spec v2 contract")
        if not spec.get("live_vectors"):
            failures.append(f"{case['name']}: missing live vector contract")
        if not spec.get("camera_bookmarks"):
            failures.append(f"{case['name']}: missing camera bookmarks")
        if not spec.get("storyboard"):
            failures.append(f"{case['name']}: missing storyboard")
        quantity = case.get("quantity")
        if quantity:
            key, expected = quantity
            if not math.isclose(spec["quantities"][key]["value"], expected, rel_tol=1e-6):
                failures.append(f"{case['name']}: {key}={spec['quantities'][key]['value']}")
        point = case.get("point")
        if point and point not in spec["geometry"]["points"]:
            failures.append(f"{case['name']}: missing point {point}")
        trajectory_count = case.get("trajectory_count")
        if trajectory_count and len(spec["trajectories"]) != trajectory_count:
            failures.append(f"{case['name']}: trajectory_count={len(spec['trajectories'])}")
        actors = case.get("actors")
        if actors:
            actual_actors = {actor.get("id") for actor in spec.get("actors", [])}
            missing_actors = set(actors) - actual_actors
            if missing_actors:
                failures.append(f"{case['name']}: missing actors {sorted(missing_actors)}")
        if case.get("phase_windows"):
            windows = {
                trajectory.get("actor"): trajectory.get("time_window")
                for trajectory in spec.get("trajectories", [])
            }
            projectile_end = windows.get("projectile", {}).get("end")
            fragment_starts = [
                windows.get("fragment_1", {}).get("start"),
                windows.get("fragment_2", {}).get("start"),
            ]
            if projectile_end is None or any(start is None for start in fragment_starts):
                failures.append(f"{case['name']}: missing trajectory phase windows")
            elif any(not math.isclose(start, projectile_end, rel_tol=1e-6) for start in fragment_starts):
                failures.append(f"{case['name']}: fragments do not start at projectile split")
        actor_phase = case.get("requires_actor_phase")
        if actor_phase:
            first_actor, second_actor = actor_phase
            first = next((item for item in spec["trajectories"] if item.get("actor") == first_actor), {})
            second = next((item for item in spec["trajectories"] if item.get("actor") == second_actor), {})
            first_window = first.get("time_window") or {}
            second_window = second.get("time_window") or {}
            if not math.isclose(first_window.get("end", -1), second_window.get("start", -2), rel_tol=1e-6):
                failures.append(f"{case['name']}: actor phase handoff is not explicit")
        surface_count = case.get("surface_count")
        if surface_count and len(spec["geometry"].get("surfaces", [])) != surface_count:
            failures.append(f"{case['name']}: surface_count={len(spec['geometry'].get('surfaces', []))}")
        surface_type = case.get("surface_type")
        if surface_type and not any(surface.get("type") == surface_type for surface in spec["geometry"].get("surfaces", [])):
            failures.append(f"{case['name']}: missing surface type {surface_type}")
        if case.get("staircase_contact"):
            impact = spec["geometry"]["points"].get("impact", {})
            on_tread = False
            for surface in spec["geometry"].get("surfaces", []):
                if surface.get("type") != "stair_tread":
                    continue
                x0, y0 = surface.get("from_xy", [None, None])
                x1, y1 = surface.get("to_xy", [None, None])
                if None in {x0, y0, x1, y1}:
                    continue
                if (
                    min(x0, x1) - 1e-6 <= impact.get("x", float("nan")) <= max(x0, x1) + 1e-6
                    and math.isclose(impact.get("y", float("nan")), y0, rel_tol=1e-6, abs_tol=1e-6)
                    and math.isclose(y0, y1, rel_tol=1e-6, abs_tol=1e-6)
                ):
                    on_tread = True
                    break
            if not on_tread:
                failures.append(f"{case['name']}: impact point is not on a stair tread")
        if case.get("impact_below_launch"):
            impact = spec["geometry"]["points"].get("impact", {})
            launch = spec["geometry"]["points"].get("launch", {})
            if impact.get("y", 0) >= launch.get("y", 0):
                failures.append(f"{case['name']}: impact is not below launch")
        if case.get("surface_descends_right"):
            incline = next(
                (surface for surface in spec["geometry"].get("surfaces", []) if surface.get("type") == "inclined_plane"),
                None,
            )
            if not incline or incline.get("to_xy", [0, 0])[1] >= incline.get("from_xy", [0, 0])[1]:
                failures.append(f"{case['name']}: incline does not descend to the right")
        obstacle = case.get("obstacle")
        if obstacle and not any(item.get("id") == obstacle for item in spec["geometry"]["obstacles"]):
            failures.append(f"{case['name']}: missing obstacle {obstacle}")
        storyboard_overlay = case.get("storyboard_overlay")
        if storyboard_overlay and not any(storyboard_overlay in (step.get("overlays") or []) for step in spec["storyboard"]):
            failures.append(f"{case['name']}: missing storyboard overlay {storyboard_overlay}")
        if not all(step.get("visual_action") for step in spec["storyboard"]):
            failures.append(f"{case['name']}: storyboard step missing visual_action")
        if not all("camera_target_ids" in step and "highlight_ids" in step for step in spec["storyboard"]):
            failures.append(f"{case['name']}: storyboard step missing camera/highlight ids")
        non_full_scene_cameras = [
            step.get("camera")
            for step in spec["storyboard"]
            if step.get("camera") != "full_scene"
        ]
        if non_full_scene_cameras:
            failures.append(f"{case['name']}: storyboard should keep fixed full_scene camera, got {non_full_scene_cameras}")
        storyboard_vector = case.get("storyboard_vector")
        if storyboard_vector and not any(storyboard_vector in (step.get("visible_vectors") or []) for step in spec["storyboard"]):
            failures.append(f"{case['name']}: missing storyboard vector {storyboard_vector}")
        storyboard_focus = case.get("storyboard_focus")
        if storyboard_focus and not any(storyboard_focus in (step.get("visual_focus") or []) for step in spec["storyboard"]):
            failures.append(f"{case['name']}: missing storyboard focus {storyboard_focus}")
        storyboard_actions = case.get("storyboard_actions")
        if storyboard_actions:
            actual_actions = {step.get("visual_action") for step in spec["storyboard"]}
            missing_actions = set(storyboard_actions) - actual_actions
            if missing_actions:
                failures.append(f"{case['name']}: missing storyboard actions {sorted(missing_actions)}")
        if case["name"] == "level maximum range":
            storyboard_by_id = {step.get("step_id"): step for step in spec["storyboard"]}
            invariant = storyboard_by_id.get("invariant", {})
            resolve = storyboard_by_id.get("solve_1", {})
            same_height = storyboard_by_id.get("solve_2", {})
            if invariant.get("visual_action") != "show_launch_setup":
                failures.append("level maximum range: invariant step should show only launch setup")
            if "show_range_marker" in (invariant.get("overlays") or []):
                failures.append("level maximum range: invariant step should not show range marker")
            if "*:v" not in (invariant.get("visible_vectors") or []):
                failures.append("level maximum range: invariant step should show the launch velocity vector")
            if "show_velocity_components" not in (resolve.get("overlays") or []):
                failures.append("level maximum range: resolve step does not show velocity components")
            if "show_same_height" not in (same_height.get("overlays") or []):
                failures.append("level maximum range: same-height step does not show delta-y zero")
            if "show_range_marker" in (same_height.get("overlays") or []):
                failures.append("level maximum range: same-height step should not show range marker")
        if case["name"] == "level multi quantity scene":
            storyboard_by_id = {step.get("step_id"): step for step in spec["storyboard"]}
            root_step = storyboard_by_id.get("solve_4", {})
            substitution_step = storyboard_by_id.get("solve_5", {})
            if (root_step.get("beat_visual_spec") or {}).get("beat") != "time_of_flight":
                failures.append("level multi quantity scene: solve_4 must select the physical flight-time root")
            if root_step.get("visible_vectors") != ["__none__"]:
                failures.append("level multi quantity scene: root selection must not show component vectors")
            if (substitution_step.get("beat_visual_spec") or {}).get("beat") != "component_substitution":
                failures.append("level multi quantity scene: solve_5 must separately substitute the vertical component")
            if substitution_step.get("visual_action") != "show_time_component_substitution":
                failures.append("level multi quantity scene: substitution beat has the wrong visual action")
            substitution_vectors = set(substitution_step.get("visible_vectors") or [])
            if substitution_vectors != {"*:v", "*:vy"}:
                failures.append(f"level multi quantity scene: substitution vectors={sorted(substitution_vectors)}")
        if case["name"] == "projectile and slider incline collision scene":
            walkthrough = build_solution_walkthrough(result)
            beat_ids = [beat.get("step_id") for beat in walkthrough.get("explainer_beats", [])]
            expected_beats = [
                "hook_setup",
                "diagram_insight",
                "along_plane_cancels",
                "normal_direction_controls",
                "collision_equation",
                "answer_sanity",
            ]
            if beat_ids != expected_beats:
                failures.append(f"projectile and slider incline collision scene: conceptual beat contract drifted to {beat_ids}")
            beat_text = " ".join(str(beat.get("learner_message") or "") for beat in walkthrough.get("explainer_beats", []))
            if "how fast must P leave the surface" not in beat_text:
                failures.append("projectile and slider incline collision scene: missing hook question")
            if "We can ignore this direction" not in beat_text:
                failures.append("projectile and slider incline collision scene: missing along-plane cancellation insight")
            if "Factor the previous equation" in beat_text or "Given and what to find" in beat_text:
                failures.append("projectile and slider incline collision scene: fell back to textbook-step narration")
            storyboard_by_id = {step.get("step_id"): step for step in spec["storyboard"]}
            invariant = storyboard_by_id.get("invariant", {})
            read_diagram = storyboard_by_id.get("read_diagram", {})
            along_plane = storyboard_by_id.get("along_plane", {})
            solve_u = storyboard_by_id.get("solve_u", {})
            if "*:v" not in (invariant.get("visible_vectors") or []):
                failures.append("projectile and slider incline collision scene: invariant should expose target projection vector")
            if "vector:u" not in (invariant.get("highlight_ids") or []):
                failures.append("projectile and slider incline collision scene: invariant should highlight vector:u")
            for step_name, step in (("read_diagram", read_diagram), ("along_plane", along_plane), ("solve_u", solve_u)):
                if "show_trajectory" in (step.get("overlays") or []):
                    failures.append(f"projectile and slider incline collision scene: {step_name} should not request full trajectory overlay")
            if "show_perpendicular_marker" not in (read_diagram.get("overlays") or []):
                failures.append("projectile and slider incline collision scene: read_diagram should show perpendicular marker")
            live_vector_ids = {vector.get("id") for vector in spec.get("live_vectors", [])}
            for vector_id in ("projectile_p:gravity_tangent_component", "slider_q:gravity_tangent_component", "projectile_p:gravity_normal_component"):
                if vector_id not in live_vector_ids:
                    failures.append(f"projectile and slider incline collision scene: missing live vector {vector_id}")
            live_vectors_by_id = {vector.get("id"): vector for vector in spec.get("live_vectors", [])}
            for vector_id in ("projectile_p:gravity_tangent_component", "slider_q:gravity_tangent_component", "projectile_p:gravity_normal_component"):
                if live_vectors_by_id.get(vector_id, {}).get("anchor") != "launch":
                    failures.append(f"projectile and slider incline collision scene: teaching vector {vector_id} should stay anchored to launch")
            conceptual_along = storyboard_by_id.get("along_plane_cancels", {})
            conceptual_normal = storyboard_by_id.get("normal_direction_controls", {})
            if not {"projectile_p:gravity_tangent_component", "slider_q:gravity_tangent_component"}.issubset(set(conceptual_along.get("visible_vectors") or [])):
                failures.append("projectile and slider incline collision scene: conceptual along beat should show equal P/Q gsin components")
            conceptual_along_state = conceptual_along.get("visual_state") or {}
            if conceptual_along_state.get("persist_until") != "next_beat":
                failures.append("projectile and slider incline collision scene: conceptual along beat should persist board state until next beat")
            if not {"projectile_p:gravity_tangent_component", "slider_q:gravity_tangent_component"}.issubset(set(conceptual_along_state.get("visible_vectors") or [])):
                failures.append("projectile and slider incline collision scene: visual_state should retain equal P/Q gsin vectors")
            label_targets = {label.get("target_id") for label in (conceptual_along.get("labels") or [])}
            if not {"projectile_p:gravity_tangent_component", "slider_q:gravity_tangent_component"}.issubset(label_targets):
                failures.append("projectile and slider incline collision scene: conceptual along beat should label both gsin components")
            if "projectile_p:gravity_normal_component" not in (conceptual_normal.get("visible_vectors") or []):
                failures.append("projectile and slider incline collision scene: conceptual normal beat should show P gcos component")
            if "*:a" not in (along_plane.get("visible_vectors") or []):
                failures.append("projectile and slider incline collision scene: legacy along_plane should show acceleration components")
            if "show_velocity_components" not in (solve_u.get("overlays") or []):
                failures.append("projectile and slider incline collision scene: solve_u should show the projection-speed vector")
        if len(spec["trajectories"][0]["sampled_points"]) < 10:
            failures.append(f"{case['name']}: trajectory undersampled")
        expected_event = case.get("expected_event") or (
            "event:collision" if case["world"] == "multi_projectile"
            else "event:impact" if case["world"] in {"staircase", "two_inclines"}
            else "event:apex"
        )
        if not any(event["id"] == expected_event for event in spec["events"]):
            failures.append(f"{case['name']}: missing {expected_event}")

    root_result = solve_ad_hoc_question(
        question_text=(
            "A stone is projected from level ground with speed 20 m/s at 30 degrees. "
            "Find its time of flight, maximum height, and horizontal range."
        ),
        engine_case=None,
        options=[],
        givens=[],
    )
    forced_wrong_root = default_visual_director().build_beat_visual_spec(
        result=root_result,
        step_id="solve_4",
        title="Choose the nonzero root",
        text="The physical flight time is the later root, T = 2u_y/g.",
        visual_plan={"_visual_director_beat": "initial_components"},
    )
    if forced_wrong_root.get("beat") != "time_of_flight":
        failures.append("level ground nonzero root: deterministic beat must override an incorrect selector guess")
    if (forced_wrong_root.get("renderer_hints") or {}).get("svg_template") != "level-ground-time-flight":
        failures.append("level ground nonzero root: wrong SVG template")
    if forced_wrong_root.get("visible_vectors") not in (None, ["__none__"]):
        failures.append("level ground nonzero root: component vectors leaked into the root-selection beat")

    walkthrough = build_solution_walkthrough(root_result)
    beats = walkthrough.get("explainer_beats") or []
    beats_by_title = {beat.get("title"): beat for beat in beats}
    root_beat = beats_by_title.get("Choose the nonzero root") or {}
    component_beat = beats_by_title.get("Substitute the vertical component") or {}
    range_beat = beats_by_title.get("Convert time into range") or {}

    root_formula_lines = [
        line
        for reveal in (root_beat.get("sub_reveals") or [])
        for line in (reveal.get("formula_lines") or [])
    ]
    if any("sin" in line for line in root_formula_lines):
        failures.append("level ground nonzero root: vertical-component substitution leaked into root selection")

    component_formula_lines = [
        line
        for reveal in (component_beat.get("sub_reveals") or [])
        for line in (reveal.get("formula_lines") or [])
    ]
    if component_formula_lines != [
        "u_y = u sin(theta)",
        "T = 2u_y/g",
        "T = 2u sin(theta)/g",
    ]:
        failures.append("level ground component substitution: expected a symbolic component bridge only")

    range_formula_lines = [
        line
        for reveal in (range_beat.get("sub_reveals") or [])
        for line in (reveal.get("formula_lines") or [])
    ]
    for required in ("a_x = 0", "v_x(t) = u_x", "R = u_x T"):
        if required not in range_formula_lines:
            failures.append(f"level ground range derivation: missing {required}")
    if any(line.lstrip().startswith(("H =", "T =")) for line in range_formula_lines):
        failures.append("level ground range derivation: unrelated height or time calculation leaked into range beat")

    root_scene = build_animation_scene_spec(result=root_result, question_text=root_result.label, givens=[])
    storyboard_by_beat = {
        (step.get("beat_visual_spec") or {}).get("beat"): step
        for step in (root_scene or {}).get("storyboard", [])
    }
    expected_motion = {
        "time_to_peak": {"mode": "partial", "event": "apex"},
        "landing_condition": {"mode": "lifecycle", "event": "landing"},
        "time_of_flight": {"mode": "lifecycle", "event": "landing"},
        "horizontal_range": {"mode": "lifecycle", "event": "landing"},
        "final_answer": {"mode": "lifecycle", "event": "landing"},
    }
    for beat, expected in expected_motion.items():
        actual = (storyboard_by_beat.get(beat) or {}).get("motion")
        if actual != expected:
            failures.append(f"level ground {beat}: expected motion {expected}, got {actual}")

    unsupported = solve_ad_hoc_question(
        question_text="A projectile is launched at 20 m/s toward a vertical screen placed 20 m from launch.",
        engine_case=None,
        options=[],
        givens=[],
    )
    if build_animation_scene_spec(result=unsupported, question_text=unsupported.label, givens=[]) is not None:
        failures.append("unsupported solve produced animation scene")

    if failures:
        print("FAIL " + "; ".join(failures))
        raise SystemExit(1)
    print("PASS animation scene spec regressions")


if __name__ == "__main__":
    main()
