from __future__ import annotations

from typing import Any

from .family_pack import BaseVisualFamilyPack
from .types import BeatContext
from .utils import dedupe_labels, dedupe_strings


class LevelGroundProjectilePack(BaseVisualFamilyPack):
    family = "level_ground_projectile"
    engine_cases = (
        "level_ground_range",
        "level_ground_time_of_flight",
        "level_ground_multi_quantity",
        "level_ground_range_and_time",
        "level_ground_time_of_flight_derivation",
        "level_ground_max_height",
        "level_ground_time_to_peak",
        "level_ground_position_at_time",
        "level_ground_velocity_at_time",
        "same_height_times_initial_speed",
        "trajectory_equation_max_height",
        "projectile_height_scaling",
        "range_angle_scaling",
        "range_equals_max_height_angle",
        "level_ground_launch_angle_from_range",
        "same_range_doubled_angle_time_ratio",
        "average_velocity_to_peak",
    )

    def describe(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "engine_cases": list(self.engine_cases),
            "beats": [
                "setup",
                "initial_components",
                "time_to_peak",
                "landing_condition",
                "time_of_flight",
                "maximum_height",
                "horizontal_range",
                "final_answer",
            ],
            "selection_policy": "Same-level projectile: resolve launch once, use vertical motion for time/height, and horizontal motion for range.",
            "renderer_templates": [
                "level-ground-setup",
                "level-ground-components",
                "level-ground-time-to-peak",
                "level-ground-time-flight",
                "level-ground-apex",
                "level-ground-range",
                "level-ground-summary",
            ],
        }

    def infer_beat(self, context: BeatContext) -> str:
        selected_beat = str(context.visual_plan.get("_visual_director_beat") or "").strip()
        if selected_beat:
            return selected_beat
        blob = " ".join([
            context.step_id,
            context.title,
            context.text,
            str(context.visual_plan.get("visual_action") or ""),
            " ".join(str(item) for item in context.visual_plan.get("show_ids") or []),
            " ".join(str(item) for item in context.visual_plan.get("highlight_ids") or []),
        ]).lower()
        compact = blob.replace(" ", "")
        if context.step_id == "takeaway" or "answer" in blob or "final" in blob:
            return "final_answer"
        if context.step_id == "invariant":
            return "setup"
        if context.step_id.endswith("solve_1") or "resolve the launch velocity" in blob:
            return "initial_components"
        if "t_peak" in blob or "tₚₑₐₖ" in blob or "time to peak" in blob or "time-to-peak" in blob or "time to reach the maximum height" in blob:
            return "time_to_peak"
        if "r=u_xt" in compact or "r=uₓt" in compact or "quantity:r" in blob or "convert time into range" in blob:
            return "horizontal_range"
        if "apply the landing condition" in context.title.lower() or "use zero vertical displacement" in context.title.lower():
            return "landing_condition"
        if "t=2u_y/g" in compact or "t=2uᵧ/g" in compact or "nonzero root" in blob or "same-height landing" in blob:
            return "time_of_flight"
        if "h=u_y^2" in compact or "h=uᵧ²" in compact or "maximum height" in blob or "highest point" in blob:
            return "maximum_height"
        if "component" in blob or "resolve" in blob or "u_x" in blob or "u_y" in blob or "uₓ" in blob or "uᵧ" in blob or "vector:u" in blob:
            return "initial_components"
        return "setup"

    def student_text_for_beat(self, beat: str) -> str:
        if beat == "setup":
            return "Show one same-level projectile path and the launch angle from the horizontal."
        if beat == "initial_components":
            return "Resolve the launch speed into horizontal and vertical components."
        if beat == "time_of_flight":
            return "Use vertical motion and same-height landing to get total flight time."
        if beat == "landing_condition":
            return "Launch and landing are at the same height, so write the vertical displacement equation with Delta y = 0."
        if beat == "time_to_peak":
            return "Use vertical velocity and the apex condition v_y = 0 to get time to peak."
        if beat == "maximum_height":
            return "At the highest point the vertical velocity is zero, so height comes from vertical motion."
        if beat == "horizontal_range":
            return "Range is constant horizontal velocity multiplied by total flight time."
        if beat == "final_answer":
            return "Show the requested time, height, and range on one clean summary diagram."
        return super().student_text_for_beat(beat)

    def must_show_for_beat(self, context: BeatContext, beat: str) -> list[str]:
        items = ["projectile", "level_ground"]
        if beat in {"setup", "initial_components"}:
            items.extend(["launch_velocity_arrow", "theta_reference"])
        else:
            items.append("trajectory_path")
        if beat == "initial_components":
            items.extend(["x_component_arrow", "y_component_arrow"])
        if beat == "time_to_peak":
            items.extend(["apex_marker", "vertical_velocity_arrow", "gravity_arrow", "time_to_peak_marker"])
        if beat == "landing_condition":
            items.extend(["same_height_landing", "vertical_displacement_equation"])
        if beat == "time_of_flight":
            items.extend(["same_height_landing", "vertical_motion_marker", "time_marker"])
        if beat == "maximum_height":
            items.extend(["apex_marker", "height_marker", "horizontal_velocity_at_apex"])
        if beat == "horizontal_range":
            items.extend(["range_marker", "horizontal_velocity_arrow", "landing_point"])
        if beat == "final_answer":
            items.extend(["time_marker", "height_marker", "range_marker"])
        return dedupe_strings(items)

    def must_not_show_for_beat(self, beat: str) -> list[str]:
        forbidden = ["cliff_or_height_reference", "impact_velocity_triangle", "inclined_plane"]
        if beat in {"setup", "initial_components", "time_to_peak", "time_of_flight", "maximum_height"}:
            forbidden.append("final_answer_box")
        if beat == "time_to_peak":
            forbidden.extend(["height_marker", "range_marker", "horizontal_velocity_arrow"])
        if beat == "landing_condition":
            forbidden.extend(["solved_flight_time", "launch_angle", "velocity_components", "gravity_arrow"])
        if beat in {"setup", "initial_components"}:
            forbidden.extend(["range_formula_first", "impact_velocity_vector"])
        return dedupe_strings(forbidden)

    def labels_for_beat(self, context: BeatContext, beat: str) -> list[dict[str, Any]]:
        labels: list[dict[str, Any]] = []
        if beat in {"setup", "initial_components"}:
            labels.extend([
                {"target_id": "velocity:launch", "text": "u", "placement": "near_arrow_head", "priority": 1},
                {"target_id": "quantity:theta", "text": "theta", "placement": "outside_angle_arc", "priority": 1},
            ])
        if beat == "initial_components":
            labels.extend([
                {"target_id": "velocity:x_component", "text": "u_x", "placement": "near_arrow_head", "priority": 1},
                {"target_id": "velocity:y_component", "text": "u_y", "placement": "near_arrow_head", "priority": 1},
            ])
        if beat == "landing_condition":
            labels.extend([
                {"target_id": "quantity:delta_y", "text": "Delta y = 0", "placement": "between_launch_landing", "priority": 1},
                {"target_id": "equation:vertical_displacement", "text": "0 = u_y T - (1/2)gT^2", "placement": "below_path", "priority": 1},
            ])
        if beat == "time_of_flight":
            labels.extend([
                {"target_id": "quantity:T", "text": "T = 2u_y/g", "placement": "below_path", "priority": 1},
                {"target_id": "quantity:delta_y", "text": "Delta y = 0", "placement": "between_launch_landing", "priority": 2},
            ])
        if beat == "time_to_peak":
            labels.extend([
                {"target_id": "velocity:y_component", "text": "u_y", "placement": "near_arrow_head", "priority": 1},
                {"target_id": "vector:g", "text": "g", "placement": "near_arrow_head", "priority": 1},
                {"target_id": "velocity:apex_y_component", "text": "v_y = 0", "placement": "beside_apex", "priority": 1},
                {"target_id": "quantity:t_peak", "text": "t_peak = u_y/g", "placement": "below_path", "priority": 1},
            ])
        if beat == "maximum_height":
            labels.extend([
                {"target_id": "velocity:apex_y_component", "text": "v_y = 0", "placement": "beside_apex", "priority": 1},
                {"target_id": "quantity:H", "text": "H", "placement": "beside_height_marker", "priority": 1},
            ])
        if beat == "horizontal_range":
            labels.extend([
                {"target_id": "quantity:R", "text": "R = u_x T", "placement": "below_range_marker", "priority": 1},
                {"target_id": "velocity:x_component", "text": "u_x", "placement": "above_arrow", "priority": 2},
            ])
        return dedupe_labels(labels)

    def renderer_hints_for_beat(self, beat: str) -> dict[str, Any]:
        svg_template = {
            "setup": "level-ground-setup",
            "initial_components": "level-ground-components",
            "time_to_peak": "level-ground-time-to-peak",
            "landing_condition": "level-ground-landing-condition",
            "time_of_flight": "level-ground-time-flight",
            "maximum_height": "level-ground-apex",
            "horizontal_range": "level-ground-range",
            "final_answer": "level-ground-summary",
        }.get(beat, "level-ground-setup")
        return {
            "svg_template": svg_template,
            "camera": "full_scene",
            "layout_mode": "textbook_clean",
            "label_strategy": "contract_slots",
        }

    def render_primitives_for_beat(self, context: BeatContext, beat: str) -> list[dict[str, Any]]:
        primitives = [{"type": "trajectory", "target_id": "trajectory:path", "required": True}]
        if beat in {"setup", "initial_components"}:
            primitives.extend([
                {"type": "vector", "target_id": "velocity:launch", "required": True},
                {"type": "angle_arc", "target_id": "quantity:theta", "required": True},
            ])
        if beat == "initial_components":
            primitives.extend([
                {"type": "vector", "target_id": "velocity:x_component", "required": True},
                {"type": "vector", "target_id": "velocity:y_component", "required": True},
            ])
        if beat in {"landing_condition", "time_of_flight"}:
            primitives.append({"type": "same_height_marker", "target_id": "quantity:delta_y", "required": True})
        if beat == "time_to_peak":
            primitives.extend([
                {"type": "vector", "target_id": "velocity:y_component", "required": True},
                {"type": "vector", "target_id": "vector:g", "required": True},
                {"type": "event", "target_id": "event:apex", "required": True},
            ])
        if beat == "maximum_height":
            primitives.extend([
                {"type": "height_marker", "target_id": "quantity:H", "required": True},
                {"type": "vector", "target_id": "velocity:x_component", "required": True},
            ])
        if beat == "horizontal_range":
            primitives.append({"type": "range_marker", "target_id": "quantity:R", "required": True})
        return primitives

    def visible_vectors(self, existing: list[Any], spec: dict[str, Any]) -> list[str]:
        beat = str(spec.get("beat") or "")
        if beat == "setup":
            return ["*:v"]
        if beat == "initial_components":
            return ["*:v", "*:vx", "*:vy"]
        if beat == "time_to_peak":
            return ["*:vy", "*:a"]
        if beat in {"landing_condition", "time_of_flight"}:
            return ["__none__"]
        vectors = [str(item) for item in existing if str(item) and str(item) != "__none__"]
        if beat in {"horizontal_range", "maximum_height"}:
            vectors.append("*:vx")
        if beat in {"initial_components", "time_of_flight"}:
            vectors.append("*:vy")
        if beat == "time_of_flight":
            vectors.append("*:a")
        if beat == "final_answer":
            return ["__none__"]
        return dedupe_strings(vectors or ["__none__"])

    def visible_ids(self, existing: list[Any], spec: dict[str, Any]) -> list[str]:
        beat = str(spec.get("beat") or "")
        if beat == "setup":
            return ["projectile", "level_ground", "point:launch", "velocity:launch", "quantity:theta"]
        ids = [str(item) for item in existing if str(item)]
        if beat == "initial_components":
            return ["projectile", "level_ground", "point:launch", "velocity:launch", "quantity:ux", "quantity:uy", "quantity:theta", "vector:ux", "vector:uy"]
        elif beat == "landing_condition":
            ids = ["projectile", "level_ground", "point:launch", "point:landing", "quantity:delta_y", "equation:vertical_displacement", "trajectory:path"]
        elif beat == "time_of_flight":
            ids = ["projectile", "level_ground", "point:launch", "point:landing", "quantity:T", "quantity:delta_y", "trajectory:path"]
        elif beat == "time_to_peak":
            ids = ["projectile", "level_ground", "point:launch", "event:apex", "quantity:t_peak", "quantity:uy", "vector:uy", "vector:g", "trajectory:path"]
        elif beat == "maximum_height":
            ids = ["projectile", "level_ground", "event:apex", "quantity:H", "trajectory:path", "vector:ux"]
        elif beat == "horizontal_range":
            ids = ["projectile", "level_ground", "point:launch", "point:landing", "quantity:R", "trajectory:path", "vector:ux"]
        elif beat == "final_answer":
            ids = ["answer", "projectile", "level_ground", "quantity:T", "quantity:H", "quantity:R", "trajectory:path"]
        return dedupe_strings(ids)

    def visual_action(self, existing: str, spec: dict[str, Any]) -> str:
        beat = str(spec.get("beat") or "")
        if beat == "setup":
            return "show_launch_setup"
        if beat == "initial_components":
            return "zoom_launch_vector"
        if beat == "time_of_flight":
            return "show_flight_time_root"
        if beat == "landing_condition":
            return "show_landing_condition"
        if beat == "time_to_peak":
            return "show_peak_time"
        if beat == "maximum_height":
            return "highlight_apex"
        if beat == "horizontal_range":
            return "highlight_range"
        if beat == "final_answer":
            return "highlight_final_answer"
        return existing or "show_full_scene"
