from __future__ import annotations

from typing import Any

from .types import BeatContext
from .utils import dedupe_labels, dedupe_strings, normalize_spec


class BaseVisualFamilyPack:
    family = "standard_projectile"
    engine_cases: tuple[str, ...] = ()
    forbidden_global: tuple[str, ...] = ()

    def describe(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "engine_cases": list(self.engine_cases),
            "beats": ["setup", "initial_components", "axis_resolution", "final_answer"],
            "selection_policy": "Fallback pack for projectile beats without a more specific visual family.",
        }

    def matches(self, result) -> bool:
        return result.engine_case in self.engine_cases if self.engine_cases else True

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
        if "component" in blob or "horizontal and vertical" in blob or "u_y" in blob or "uy" in blob or "uₓ" in blob:
            return "initial_components"
        if "axis" in blob or "resolve" in blob:
            return "axis_resolution"
        return "setup"

    def student_text_for_beat(self, beat: str) -> str:
        if beat == "initial_components":
            return "Resolve the initial velocity into the components used by the equations."
        if beat == "axis_resolution":
            return "Choose axes that match the physical constraint before substituting values."
        if beat == "final_answer":
            return "State only the requested quantity with units."
        return "Show the exact physical quantity used in this step."

    def must_show_for_beat(self, context: BeatContext, beat: str) -> list[str]:
        items = ["projectile"]
        if self.family == "inclined_plane_projectile":
            items.extend(["inclined_plane", "incline_axes"])
            if "component" in context.text or "resolve" in context.text:
                items.append("resolved_components")
        elif self.family == "two_projectiles":
            items.extend(["both_projectiles", "separate_actor_labels"])
        elif self.family == "staircase_projectile":
            items.extend(["staircase", "horizontal_velocity_arrow"])
        elif beat == "initial_components":
            items.extend(["launch_velocity_arrow", "x_component_arrow", "y_component_arrow", "theta_reference"])
        return dedupe_strings(items)

    def must_not_show_for_beat(self, beat: str) -> list[str]:
        return dedupe_strings(list(self.forbidden_global))

    def labels_for_beat(self, context: BeatContext, beat: str) -> list[dict[str, Any]]:
        if beat != "initial_components":
            return []
        return dedupe_labels([
            {"target_id": "velocity:x_component", "text": "u_x = u cos θ", "placement": "below_arrow", "priority": 1},
            {"target_id": "velocity:y_component", "text": "u_y = u sin θ", "placement": "right_of_arrow", "priority": 1},
        ])

    def renderer_hints_for_beat(self, beat: str) -> dict[str, Any]:
        return {
            "svg_template": "",
            "camera": "full_scene",
            "layout_mode": "textbook_clean",
            "label_strategy": "contract_slots",
        }

    def render_primitives_for_beat(self, context: BeatContext, beat: str) -> list[dict[str, Any]]:
        return [{"type": "projectile_context", "target_id": "projectile", "required": True}]

    def checks_for_beat(self, beat: str) -> list[dict[str, Any]]:
        return [
            {"type": "no_label_overlap", "severity": "error"},
            {"type": "required_labels_visible", "severity": "error"},
            {"type": "forbidden_objects_absent", "severity": "error"},
        ]

    def build_spec(self, context: BeatContext) -> dict[str, Any]:
        beat = self.infer_beat(context)
        return normalize_spec({
            "schema_version": 1,
            "family": self.family,
            "engine_case": context.result.engine_case,
            "step_id": context.step_id,
            "beat": beat,
            "student_text": self.student_text_for_beat(beat),
            "must_show": self.must_show_for_beat(context, beat),
            "must_not_show": self.must_not_show_for_beat(beat),
            "labels": self.labels_for_beat(context, beat),
            "renderer_hints": self.renderer_hints_for_beat(beat),
            "render_primitives": self.render_primitives_for_beat(context, beat),
            "checks": self.checks_for_beat(beat),
        })

    def visible_vectors(self, existing: list[Any], spec: dict[str, Any]) -> list[str]:
        return dedupe_strings(list(existing) or ["__none__"])

    def visible_ids(self, existing: list[Any], spec: dict[str, Any]) -> list[str]:
        return dedupe_strings(list(existing))

    def visual_action(self, existing: str, spec: dict[str, Any]) -> str:
        return existing or "show_full_scene"
