from __future__ import annotations

from typing import Any


def beat_motion(motion: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Resolve playback once, for both the teaching plan and scene storyboard."""
    if spec.get("family") != "level_ground_projectile":
        return dict(motion)
    return {
        "setup": {"mode": "static"},
        "initial_components": {"mode": "static"},
        "component_substitution": {"mode": "static"},
        "time_to_peak": {"mode": "partial", "event": "apex"},
        "maximum_height": {"mode": "partial", "event": "apex"},
        "landing_condition": {"mode": "lifecycle", "event": "landing"},
        "time_of_flight": {"mode": "freeze", "event": "landing"},
        "horizontal_range": {"mode": "freeze", "event": "landing"},
        "final_answer": {"mode": "lifecycle", "event": "landing"},
    }.get(str(spec.get("beat") or ""), dict(motion))


def beat_overlays(overlays: list[str], spec: dict[str, Any], action: str) -> list[str]:
    if spec.get("family") == "level_ground_projectile":
        beat = str(spec.get("beat") or "")
        if beat == "setup" or action == "show_launch_setup":
            return ["show_scene"]
        if beat in {"initial_components", "component_substitution"} or action in {"zoom_launch_vector", "show_time_component_substitution"}:
            return ["show_velocity_components"]
        if beat == "time_to_peak" or action == "show_peak_time":
            return ["show_scene"]
        allowed = {
            "landing_condition": {"show_trajectory", "show_same_height", "show_motion_progress"},
            "time_of_flight": {"show_trajectory", "show_same_height", "show_timer"},
            "maximum_height": {"show_trajectory", "show_height_marker", "show_motion_progress"},
            "horizontal_range": {"show_trajectory", "show_range_marker"},
            "final_answer": {"show_trajectory", "show_final_answer", "show_range_marker", "show_height_marker", "show_timer"},
        }.get(beat)
        if allowed:
            required = {
                "landing_condition": ["show_trajectory", "show_same_height"],
                "time_of_flight": ["show_trajectory", "show_same_height", "show_timer"],
                "maximum_height": ["show_trajectory", "show_height_marker"],
                "horizontal_range": ["show_trajectory", "show_range_marker"],
                "final_answer": ["show_trajectory"],
            }.get(beat, [])
            return list(dict.fromkeys(required + [item for item in overlays if item in allowed]))
    return list(dict.fromkeys(overlays or ["show_scene"]))
