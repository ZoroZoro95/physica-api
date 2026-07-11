from __future__ import annotations

from typing import Any

from .family_pack import BaseVisualFamilyPack
from .horizontal_launch import HorizontalLaunchPack
from .level_ground import LevelGroundProjectilePack
from .types import VisualFamilyPack


class HeightLaunchPack(BaseVisualFamilyPack):
    family = "height_launch"
    engine_cases = (
        "height_launch_time_of_flight",
        "height_launch_range",
        "height_launch_multi_quantity",
        "max_range_from_height_fixed_speed",
    )

    def describe(self) -> dict[str, Any]:
        payload = super().describe()
        payload.update({
            "beats": ["setup", "initial_components", "time_of_flight", "horizontal_range", "impact_velocity", "final_answer"],
            "selection_policy": "Projectile launched from a nonzero height, not necessarily horizontal.",
            "renderer_templates": ["height-launch-components", "height-launch-fall", "height-launch-impact"],
        })
        return payload


class InclinedPlanePack(BaseVisualFamilyPack):
    family = "inclined_plane_projectile"
    engine_cases = (
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
    )

    def describe(self) -> dict[str, Any]:
        payload = super().describe()
        payload.update({
            "beats": ["setup", "incline_axes", "axis_resolution", "normal_motion", "tangent_motion", "impact_condition", "final_answer"],
            "selection_policy": "Projectile constrained or measured against an inclined plane; axes must follow tangent and normal directions.",
            "renderer_templates": ["incline-axis-resolution", "incline-normal-distance", "incline-impact"],
        })
        return payload

    def infer_beat(self, context) -> str:
        selected_beat = str(context.visual_plan.get("_visual_director_beat") or "").strip()
        if selected_beat:
            return selected_beat
        blob = " ".join([context.step_id, context.title, context.text, str(context.visual_plan.get("visual_action") or "")]).lower()
        if "answer" in blob or context.step_id == "takeaway":
            return "final_answer"
        if "normal" in blob or "perpendicular" in blob or "maximum distance" in blob:
            return "normal_motion"
        if "tangent" in blob or "along the plane" in blob:
            return "tangent_motion"
        if "resolve" in blob or "component" in blob or "axis" in blob:
            return "axis_resolution"
        if "impact" in blob or "strike" in blob or "hit" in blob:
            return "impact_condition"
        return "incline_axes"


class TwoProjectilesPack(BaseVisualFamilyPack):
    family = "two_projectiles"
    engine_cases = (
        "two_projectile_interception_time_ratio",
        "two_projectile_collision_time",
        "two_projectile_same_speed_comparison",
        "relative_projectile_apex_collision",
        "monkey_hunter_condition",
    )

    def describe(self) -> dict[str, Any]:
        payload = super().describe()
        payload.update({
            "beats": ["setup", "separate_actors", "relative_motion", "collision_event", "final_answer"],
            "selection_policy": "Two bodies or two projectiles must be shown as separate labelled actors, not collapsed into one path.",
            "renderer_templates": ["two-projectiles-separate", "two-projectiles-relative", "two-projectiles-collision"],
        })
        return payload

    def infer_beat(self, context) -> str:
        selected_beat = str(context.visual_plan.get("_visual_director_beat") or "").strip()
        if selected_beat:
            return selected_beat
        blob = " ".join([context.step_id, context.title, context.text, str(context.visual_plan.get("visual_action") or "")]).lower()
        if "answer" in blob or context.step_id == "takeaway":
            return "final_answer"
        if "relative" in blob or "same time" in blob:
            return "relative_motion"
        if "collision" in blob or "collide" in blob or "intercept" in blob or "hit" in blob:
            return "collision_event"
        return "separate_actors"


class StaircasePack(BaseVisualFamilyPack):
    family = "staircase_projectile"
    engine_cases = ("staircase_collision", "staircase_projectile_collision")

    def describe(self) -> dict[str, Any]:
        payload = super().describe()
        payload.update({
            "beats": ["setup", "step_geometry", "fall_relation", "step_hit", "final_answer"],
            "selection_policy": "Projectile over equal stair treads and risers; show the discrete staircase and the selected step.",
            "renderer_templates": ["staircase-geometry", "staircase-trajectory", "staircase-hit-step"],
        })
        return payload


class StandardProjectilePack(BaseVisualFamilyPack):
    family = "standard_projectile"
    engine_cases = ()


def default_visual_family_packs() -> tuple[VisualFamilyPack, ...]:
    return (
        HorizontalLaunchPack(),
        HeightLaunchPack(),
        InclinedPlanePack(),
        TwoProjectilesPack(),
        StaircasePack(),
        LevelGroundProjectilePack(),
        StandardProjectilePack(),
    )
