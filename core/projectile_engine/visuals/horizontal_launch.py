from __future__ import annotations

import math
import re
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
            "beats": [
                "setup",
                "time_of_flight",
                "horizontal_range",
                "impact_vertical_velocity",
                "impact_speed",
                "impact_angle",
                "final_answer",
            ],
            "selection_policy": "Horizontal launch from a height: launch angle is zero, u_y starts at zero, horizontal speed stays constant.",
            "renderer_templates": [
                "horizontal-cliff-setup",
                "horizontal-cliff-fall-time",
                "horizontal-cliff-range",
                "horizontal-cliff-impact-vertical",
                "horizontal-cliff-impact-speed",
                "horizontal-cliff-impact-angle",
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
        if "impact angle" in blob or "tan" in blob or "quantity:impact_angle" in blob:
            return "impact_angle"
        if "impact speed" in blob or "combine" in blob or "sqrt" in blob or "resultant" in blob:
            return "impact_speed"
        if "vertical velocity" in blob or "v_y" in blob or "vy" in blob or "vᵧ" in blob or "-gt" in blob:
            return "impact_vertical_velocity"
        if "range" in blob or "horizontal distance" in blob or "distance covered" in blob or "how far" in blob:
            return "horizontal_range"
        if "time" in blob or "flight" in blob or "fall" in blob:
            return "time_of_flight"
        if "component" in blob or "u_y" in blob or "uy" in blob or "uᵧ" in blob or context.step_id == "invariant":
            return "setup"
        if "height" in blob or "drop" in blob:
            return "time_of_flight"
        return "setup"

    def student_text_for_beat(self, beat: str) -> str:
        if beat == "setup":
            return "Recognize this as a horizontal launch from a height."
        if beat == "time_of_flight":
            return "The fall time comes only from vertical motion and the tower height."
        if beat == "horizontal_range":
            return "Horizontal distance uses constant horizontal speed after the fall time is known."
        if beat == "impact_vertical_velocity":
            return "Gravity builds the downward velocity during the fall."
        if beat == "impact_speed":
            return "Impact speed is the resultant of the horizontal and vertical velocity components."
        if beat == "impact_angle":
            return "The impact angle comes from the velocity triangle just before impact."
        if beat == "final_answer":
            return "State the requested horizontal-launch quantities with units."
        return "Use the launch height and zero initial vertical velocity."

    def must_show_for_beat(self, context: BeatContext, beat: str) -> list[str]:
        items: list[str] = ["projectile", "cliff_or_height_reference", "height_drop_marker"]
        if beat in {"setup", "horizontal_range", "impact_vertical_velocity", "impact_speed", "impact_angle"}:
            items.append("horizontal_velocity_arrow")
        if beat in {"setup", "time_of_flight"}:
            items.append("gravity_direction")
        if beat in {"horizontal_range", "final_answer"}:
            items.append("horizontal_range_marker")
        if beat == "impact_vertical_velocity":
            items.extend(["trajectory_path", "impact_point", "impact_vertical_velocity_vector"])
        if beat == "impact_speed":
            items.extend(["impact_velocity_vector", "impact_velocity_components", "impact_velocity_triangle"])
        if beat == "impact_angle":
            items.extend(["impact_velocity_vector", "impact_velocity_components", "impact_velocity_triangle", "impact_angle_arc"])
        return dedupe_strings(items)

    def must_not_show_for_beat(self, beat: str) -> list[str]:
        forbidden = [
            item for item in self.forbidden_global
            if not (beat == "impact_angle" and item == "theta_arc")
        ]
        forbidden.extend(["generic_angled_projectile_template", "apex_marker"])
        if beat in {"setup", "time_of_flight"}:
            forbidden.extend(["range_formula_first", "impact_velocity_triangle", "impact_angle_arc", "resultant_velocity_vector"])
        if beat == "impact_vertical_velocity":
            forbidden.extend(["impact_velocity_triangle", "impact_angle_arc", "resultant_velocity_vector", "horizontal_range_marker"])
        if beat == "impact_speed":
            forbidden.extend(["impact_angle_arc", "horizontal_range_marker"])
        if beat == "impact_angle":
            forbidden.extend(["horizontal_range_marker"])
        return dedupe_strings(forbidden)

    def labels_for_beat(self, context: BeatContext, beat: str) -> list[dict[str, Any]]:
        speed = quantity_number(context.result, "ux", "u_x", "vx", "v_x", "horizontal_speed", "speed", "velocity", "v0", "u")
        launch_speed_text = f"u = {format_number(speed)} m/s" if speed is not None else "u"
        vx_text = "v_x"
        labels: list[dict[str, Any]] = []
        if beat in {"setup", "impact_vertical_velocity", "impact_speed", "impact_angle", "horizontal_range"}:
            labels.append({
                "target_id": "velocity:x_component",
                "text": launch_speed_text if beat == "setup" else vx_text,
                "math": "u_x = u",
                "placement": "above_arrow",
                "priority": 1,
            })
        if beat in {"setup", "time_of_flight"}:
            labels.append({
                "target_id": "vector:g",
                "text": "g",
                "math": "g",
                "placement": "right_of_arrow",
                "priority": 1,
            })
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
        impact_vy = _impact_vertical_speed(context.result)
        impact_speed = _impact_speed(context.result)
        impact_angle = _impact_angle(context.result)
        if beat == "impact_vertical_velocity":
            labels.append({
                "target_id": "velocity:impact_y_component",
                "text": "v_y = gt",
                "math": "v_y = gt",
                "placement": "right_of_arrow",
                "priority": 1,
            })
        if beat in {"impact_speed", "impact_angle"}:
            labels.extend([
                {"target_id": "velocity:impact_x_component", "text": vx_text, "placement": "above_arrow", "priority": 1},
                {
                    "target_id": "velocity:impact_y_component",
                    "text": "v_y",
                    "placement": "right_of_arrow",
                    "priority": 1,
                },
            ])
        if beat == "impact_speed":
            labels.append({
                "target_id": "velocity:impact",
                "text": "v",
                "math": "v = sqrt(v_x^2 + v_y^2)",
                "placement": "above_arrow",
                "priority": 1,
            })
        if beat == "impact_angle":
            labels.extend([
                {
                    "target_id": "velocity:impact",
                    "text": "v",
                    "placement": "above_arrow",
                    "priority": 2,
                },
                {
                    "target_id": "quantity:impact_angle",
                    "text": "theta",
                    "math": "tan theta = v_y / v_x",
                    "placement": "outside_angle_arc",
                    "priority": 1,
                },
            ])
        return dedupe_labels(labels)

    def renderer_hints_for_beat(self, beat: str) -> dict[str, Any]:
        svg_template = {
            "setup": "horizontal-cliff-setup",
            "time_of_flight": "horizontal-cliff-fall-time",
            "horizontal_range": "horizontal-cliff-range",
            "impact_vertical_velocity": "horizontal-cliff-impact-vertical",
            "impact_speed": "horizontal-cliff-impact-speed",
            "impact_angle": "horizontal-cliff-impact-angle",
            "final_answer": "horizontal-cliff-impact-angle",
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
        ]
        if beat in {"setup", "impact_vertical_velocity", "impact_speed", "impact_angle"}:
            primitives.append({"type": "vector", "target_id": "velocity:x_component", "required": True})
        if beat in {"setup", "time_of_flight"}:
            primitives.append({"type": "vector", "target_id": "vector:g", "required": True})
        if beat == "horizontal_range":
            primitives.append({"type": "range_marker", "target_id": "quantity:R", "required": True})
        if beat == "impact_vertical_velocity":
            primitives.append({"type": "vector", "target_id": "velocity:impact_y_component", "required": True})
        if beat in {"impact_speed", "impact_angle"}:
            primitives.append({"type": "impact_velocity_triangle", "target_id": "velocity:impact", "required": True})
        if beat == "impact_angle":
            primitives.append({"type": "angle_arc", "target_id": "quantity:impact_angle", "required": True})
        return primitives

    def checks_for_beat(self, beat: str) -> list[dict[str, Any]]:
        checks = super().checks_for_beat(beat)
        checks.extend([
            {"type": "forbid_theta_decomposition", "severity": "error"},
        ])
        return checks

    def visible_vectors(self, existing: list[Any], spec: dict[str, Any]) -> list[str]:
        vectors = [str(item) for item in existing if str(item)]
        must_show = set(str(item) for item in spec.get("must_show") or [])
        if "horizontal_velocity_arrow" in must_show:
            vectors.append("*:vx")
        if "gravity_direction" in must_show:
            vectors.append("*:a")
        if "impact_vertical_velocity_vector" in must_show:
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
        if beat in {"setup", "time_of_flight"}:
            blocked.add("trajectory:path")
            ids = [item for item in ids if item not in blocked]
            ids.extend(["point:launch", "quantity:launch_height"])
        elif beat == "horizontal_range":
            ids.extend(["point:landing", "event:landing", "quantity:R", "trajectory:path"])
        elif beat in {"impact_vertical_velocity", "impact_speed", "impact_angle", "final_answer"}:
            ids.extend(["point:landing", "event:landing", "trajectory:path"])
            if beat == "impact_angle":
                ids.append("quantity:impact_angle")
        return dedupe_strings(ids)

    def visual_action(self, existing: str, spec: dict[str, Any]) -> str:
        beat = str(spec.get("beat") or "")
        if beat == "setup":
            return "show_launch_setup"
        if beat == "time_of_flight":
            return "highlight_vertical_motion"
        if beat == "horizontal_range":
            return "highlight_range"
        if beat == "impact_vertical_velocity":
            return "show_impact_vertical_velocity"
        if beat == "impact_speed":
            return "show_impact_velocity_triangle"
        if beat == "impact_angle":
            return "show_impact_angle"
        if beat == "final_answer":
            return "highlight_final_answer"
        return existing or "show_full_scene"


def _impact_vertical_speed(result: Any) -> float | None:
    text = "\n".join(str(item) for item in getattr(result, "trace", []) or [])
    match = re.search(r"v_y\s*=\s*-?g\s*t\s*=\s*(-?[0-9]+(?:\.[0-9]+)?)", text, re.I)
    if match:
        return abs(float(match.group(1)))
    plan = getattr(result, "equation_plan", {}) or {}
    givens = "\n".join(str(item) for item in plan.get("givens") or [])
    height = quantity_number(result, "launch_height", "height", "h", "H")
    g = quantity_number(result, "g") or _number_after_key(givens, "g") or 10.0
    if height is not None:
        return math.sqrt(2 * g * height)
    return None


def _impact_speed(result: Any) -> float | None:
    text = "\n".join(str(item) for item in getattr(result, "trace", []) or [])
    match = re.search(r"Impact speed is \|v\|[^=]*=\s*([0-9]+(?:\.[0-9]+)?)\s*m/s", text, re.I)
    if match:
        return float(match.group(1))
    vx = quantity_number(result, "ux", "u_x", "vx", "v_x", "horizontal_speed", "speed", "velocity", "v0", "u")
    vy = _impact_vertical_speed(result)
    if vx is not None and vy is not None:
        return math.hypot(vx, vy)
    return None


def _impact_angle(result: Any) -> float | None:
    text = "\n".join(str(item) for item in getattr(result, "trace", []) or [])
    match = re.search(r"=\s*([0-9]+(?:\.[0-9]+)?)\s*deg", text, re.I)
    if match and "angle" in text.lower():
        return float(match.group(1))
    vx = quantity_number(result, "ux", "u_x", "vx", "v_x", "horizontal_speed", "speed", "velocity", "v0", "u")
    vy = _impact_vertical_speed(result)
    if vx is not None and vy is not None and abs(vx) > 1e-9:
        return math.degrees(math.atan(abs(vy) / abs(vx)))
    return None


def _number_after_key(text: str, key: str) -> float | None:
    match = re.search(rf"\b{re.escape(key)}\b\s*=\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
    return float(match.group(1)) if match else None
