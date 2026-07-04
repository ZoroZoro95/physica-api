from __future__ import annotations

from typing import Any

from .family_pack import BaseVisualFamilyPack
from .types import BeatContext
from .utils import dedupe_labels, dedupe_strings, format_number, quantity_number


class HorizontalLaunchPack(BaseVisualFamilyPack):
    family = "horizontal_launch"
    engine_cases = ("height_launch_horizontal_scenario", "horizontal_throw_velocity_angle_time")
    forbidden_global = ("theta_arc", "u_cos_theta", "u_sin_theta", "angled_launch_vector")

    def describe(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "engine_cases": list(self.engine_cases),
            "beats": ["initial_components", "time_of_flight", "horizontal_range", "impact_velocity", "final_answer"],
            "selection_policy": "Horizontal launch from a height: launch angle is zero, u_y starts at zero, horizontal speed stays constant.",
            "renderer_templates": [
                "horizontal-cliff-setup",
                "horizontal-cliff-fall-time",
                "horizontal-cliff-range",
                "horizontal-cliff-impact",
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
        ]).lower()
        if context.step_id == "takeaway" or "answer" in blob or "final" in blob:
            return "final_answer"
        if "impact speed" in blob or "impact angle" in blob or "just before" in blob:
            return "impact_velocity"
        if "range" in blob or "horizontal distance" in blob or "distance covered" in blob or "how far" in blob:
            return "horizontal_range"
        if "time" in blob or "flight" in blob or "fall" in blob:
            return "time_of_flight"
        if "component" in blob or "u_y" in blob or "uy" in blob or "uᵧ" in blob or context.step_id == "invariant":
            return "initial_components"
        if "height" in blob or "drop" in blob:
            return "height_relation"
        return "initial_components"

    def student_text_for_beat(self, beat: str) -> str:
        if beat == "initial_components":
            return "Initial velocity is horizontal, so the vertical component starts at zero."
        if beat == "time_of_flight":
            return "The fall time comes only from vertical motion because horizontal launch starts with u_y = 0."
        if beat == "horizontal_range":
            return "Horizontal distance uses constant horizontal speed after the fall time is known."
        if beat == "impact_velocity":
            return "Impact velocity combines unchanged horizontal speed with vertical speed gained during the fall."
        if beat == "final_answer":
            return "State the requested horizontal-launch quantities with units."
        return "Use the launch height and zero initial vertical velocity."

    def must_show_for_beat(self, context: BeatContext, beat: str) -> list[str]:
        items: list[str] = ["projectile", "cliff_or_height_reference", "height_drop_marker"]
        if beat in {"initial_components", "time_of_flight", "horizontal_range", "impact_velocity"}:
            items.extend(["horizontal_velocity_arrow", "zero_vertical_component_marker"])
        if beat in {"horizontal_range", "final_answer"}:
            items.append("horizontal_range_marker")
        if beat == "impact_velocity":
            items.extend(["impact_velocity_vector", "impact_velocity_components"])
        return dedupe_strings(items)

    def must_not_show_for_beat(self, beat: str) -> list[str]:
        forbidden = list(self.forbidden_global)
        forbidden.extend(["generic_angled_projectile_template", "apex_marker"])
        if beat in {"initial_components", "time_of_flight"}:
            forbidden.extend(["range_formula_first", "impact_velocity_triangle"])
        return dedupe_strings(forbidden)

    def labels_for_beat(self, context: BeatContext, beat: str) -> list[dict[str, Any]]:
        speed = quantity_number(context.result, "ux", "u_x", "vx", "v_x", "horizontal_speed", "speed", "velocity", "v0", "u")
        ux_text = f"u_x = u = {format_number(speed)} m/s" if speed is not None else "u_x = u"
        labels: list[dict[str, Any]] = [
            {
                "target_id": "velocity:x_component",
                "text": ux_text,
                "math": "u_x = u",
                "placement": "above_arrow",
                "priority": 1,
            },
            {
                "target_id": "velocity:y_component",
                "text": "u_y = 0",
                "math": "u_y = 0",
                "placement": "right_of_launch",
                "priority": 1,
            },
        ]
        height = quantity_number(context.result, "launch_height", "height", "h", "H")
        if height is not None:
            labels.append({
                "target_id": "quantity:launch_height",
                "text": f"h = {format_number(height)} m",
                "math": rf"h = {format_number(height)}\,m",
                "placement": "beside_height_marker",
                "priority": 2,
            })
        if beat == "horizontal_range":
            labels.append({
                "target_id": "quantity:R",
                "text": "R = u_x T",
                "math": "R = u_x T",
                "placement": "below_range_marker",
                "priority": 1,
            })
        if beat == "impact_velocity":
            labels.extend([
                {"target_id": "velocity:impact_x_component", "text": "v_x = u_x", "placement": "above_arrow", "priority": 1},
                {"target_id": "velocity:impact_y_component", "text": "v_y = gt", "placement": "right_of_arrow", "priority": 1},
            ])
        return dedupe_labels(labels)

    def renderer_hints_for_beat(self, beat: str) -> dict[str, Any]:
        svg_template = {
            "initial_components": "horizontal-cliff-setup",
            "time_of_flight": "horizontal-cliff-fall-time",
            "horizontal_range": "horizontal-cliff-range",
            "impact_velocity": "horizontal-cliff-impact",
            "final_answer": "horizontal-cliff-impact",
        }.get(beat, "horizontal-cliff-setup")
        return {
            "svg_template": svg_template,
            "camera": "full_scene",
            "layout_mode": "textbook_clean",
            "label_strategy": "contract_slots",
        }

    def render_primitives_for_beat(self, context: BeatContext, beat: str) -> list[dict[str, Any]]:
        primitives = [
            {"type": "height_marker", "target_id": "quantity:launch_height", "required": True},
            {"type": "vector", "target_id": "velocity:x_component", "required": beat != "final_answer"},
            {"type": "zero_component_badge", "target_id": "velocity:y_component", "required": beat in {"initial_components", "time_of_flight"}},
        ]
        if beat == "horizontal_range":
            primitives.append({"type": "range_marker", "target_id": "quantity:R", "required": True})
        if beat == "impact_velocity":
            primitives.append({"type": "impact_velocity_triangle", "target_id": "velocity:impact", "required": True})
        return primitives

    def checks_for_beat(self, beat: str) -> list[dict[str, Any]]:
        checks = super().checks_for_beat(beat)
        checks.extend([
            {"type": "forbid_theta_decomposition", "severity": "error"},
            {"type": "zero_vertical_component_visible", "severity": "error"},
        ])
        return checks

    def visible_vectors(self, existing: list[Any], spec: dict[str, Any]) -> list[str]:
        vectors = [str(item) for item in existing if str(item)]
        must_show = set(str(item) for item in spec.get("must_show") or [])
        if "horizontal_velocity_arrow" in must_show:
            vectors.append("*:vx")
        if "zero_vertical_component_marker" in must_show:
            vectors.append("*:vy")
        if "impact_velocity_vector" in must_show:
            vectors.extend(["*:v", "*:vx", "*:vy"])
        vectors = [item for item in vectors if item != "*:v" or "impact_velocity_vector" in must_show]
        if any(item != "__none__" for item in vectors):
            vectors = [item for item in vectors if item != "__none__"]
        return dedupe_strings(vectors or ["__none__"])

    def visible_ids(self, existing: list[Any], spec: dict[str, Any]) -> list[str]:
        ids = [str(item) for item in existing if str(item)]
        beat = str(spec.get("beat") or "")
        blocked = {"quantity:R", "event:landing", "point:landing", "event:impact", "point:impact", "impact_velocity_triangle"}
        if beat in {"initial_components", "time_of_flight"}:
            blocked.add("trajectory:path")
            ids = [item for item in ids if item not in blocked]
            ids.extend(["point:launch", "quantity:launch_height"])
        elif beat == "horizontal_range":
            ids.extend(["point:landing", "event:landing", "quantity:R", "trajectory:path"])
        elif beat in {"impact_velocity", "final_answer"}:
            ids.extend(["point:landing", "event:landing"])
        return dedupe_strings(ids)

    def visual_action(self, existing: str, spec: dict[str, Any]) -> str:
        beat = str(spec.get("beat") or "")
        if beat == "initial_components":
            return "show_launch_setup"
        if beat == "time_of_flight":
            return "highlight_vertical_motion"
        if beat == "horizontal_range":
            return "highlight_range"
        if beat == "impact_velocity":
            return "show_impact_velocity_triangle"
        if beat == "final_answer":
            return "highlight_final_answer"
        return existing or "show_full_scene"
