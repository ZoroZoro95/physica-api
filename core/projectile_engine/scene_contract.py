from __future__ import annotations

import math
from typing import Any

from .visual_contract import validate_beat_visual_spec


def validate_animation_scene_spec(scene: dict[str, Any]) -> list[str]:
    """Return scene-contract errors. Empty list means the scene is internally coherent."""
    errors: list[str] = []
    if int(scene.get("schema_version") or 0) < 2:
        errors.append("schema_version must be >= 2")

    problem = scene.get("problem") or {}
    for key in ("world", "unknown", "engine_case"):
        if not problem.get(key):
            errors.append(f"problem.{key} is required")

    geometry = scene.get("geometry") or {}
    points = geometry.get("points") or {}
    if not isinstance(points, dict) or "launch" not in points:
        errors.append("geometry.points.launch is required")

    for point_id, point in points.items():
        if not _is_number(point.get("x")) or not _is_number(point.get("y")):
            errors.append(f"point {point_id} must have numeric x and y")

    for surface in geometry.get("surfaces") or []:
        has_ref_points = surface.get("from") in points and surface.get("to") in points
        has_xy_points = _is_pair(surface.get("from_xy")) and _is_pair(surface.get("to_xy"))
        if not has_ref_points and not has_xy_points:
            errors.append(f"surface {surface.get('id') or surface.get('label') or '?'} needs from/to refs or from_xy/to_xy")

    actors = scene.get("actors") or []
    actor_ids = {str(actor.get("id")) for actor in actors if actor.get("id")}
    if not actor_ids:
        errors.append("at least one actor is required")

    trajectories = scene.get("trajectories") or []
    if not trajectories:
        errors.append("at least one trajectory is required")
    for trajectory in trajectories:
        actor = str(trajectory.get("actor") or "")
        if actor and actor not in actor_ids:
            errors.append(f"trajectory {trajectory.get('id') or '?'} references unknown actor {actor}")
        sampled = trajectory.get("sampled_points") or []
        if len(sampled) < 2:
            errors.append(f"trajectory {trajectory.get('id') or '?'} needs at least two sampled points")
        for index, point in enumerate(sampled[:1] + sampled[-1:]):
            if not _is_number(point.get("x")) or not _is_number(point.get("y")):
                errors.append(f"trajectory {trajectory.get('id') or '?'} sample {index} must have numeric x and y")
        _validate_time_window(trajectory.get("time_window"), f"trajectory {trajectory.get('id') or '?'}", errors)

    motions = scene.get("motions") or ([] if not scene.get("motion") else [scene["motion"]])
    for motion in motions:
        actor = str(motion.get("actor") or "")
        if actor and actor not in actor_ids:
            errors.append(f"motion references unknown actor {actor}")
        if not _is_positive(motion.get("duration")):
            errors.append(f"motion for {actor or '?'} needs positive duration")
        if not isinstance(motion.get("initial"), dict) or not isinstance(motion.get("acceleration"), dict):
            errors.append(f"motion for {actor or '?'} needs initial and acceleration")
        _validate_time_window(motion.get("time_window"), f"motion {actor or '?'}", errors)

    event_ids: set[str] = set()
    for event in scene.get("events") or []:
        event_id = str(event.get("id") or "")
        if not event_id:
            errors.append("event id is required")
        event_ids.add(event_id)
        if not _is_number(event.get("time")):
            errors.append(f"event {event_id or '?'} needs numeric time")
        point_id = event.get("point")
        if point_id and point_id not in points:
            errors.append(f"event {event_id or '?'} references unknown point {point_id}")

    vector_ids: set[str] = set()
    for vector in scene.get("live_vectors") or []:
        vector_id = str(vector.get("id") or "")
        vector_ids.add(vector_id)
        actor = str(vector.get("actor") or "")
        if vector.get("kind") != "axis" and actor and actor not in actor_ids:
            errors.append(f"live vector {vector_id or '?'} references unknown actor {actor}")
        if not vector.get("component"):
            errors.append(f"live vector {vector_id or '?'} needs component")

    camera_ids = {str(camera.get("id")) for camera in scene.get("camera_bookmarks") or [] if camera.get("id")}
    if "full_scene" not in camera_ids:
        errors.append("camera_bookmarks must include full_scene")
    for camera in scene.get("camera_bookmarks") or []:
        if camera.get("target") != "scene" and camera.get("target") not in points:
            errors.append(f"camera {camera.get('id') or '?'} references unknown target {camera.get('target')}")
        if not _is_positive(camera.get("zoom")):
            errors.append(f"camera {camera.get('id') or '?'} needs positive zoom")

    storyboard = scene.get("storyboard") or []
    if not storyboard:
        errors.append("storyboard is required")
    for step in storyboard:
        step_id = str(step.get("step_id") or "")
        if not step_id:
            errors.append("storyboard step_id is required")
        if step.get("camera") not in camera_ids:
            errors.append(f"storyboard step {step_id or '?'} references unknown camera {step.get('camera')}")
        if not step.get("visible_vectors"):
            errors.append(f"storyboard step {step_id or '?'} needs visible_vectors")
        if not step.get("visual_focus"):
            errors.append(f"storyboard step {step_id or '?'} needs visual_focus")
        if not step.get("overlays"):
            errors.append(f"storyboard step {step_id or '?'} needs overlays")
        if not str(step.get("why") or "").strip():
            errors.append(f"storyboard step {step_id or '?'} needs why")
        beat_visual_spec = step.get("beat_visual_spec")
        if not isinstance(beat_visual_spec, dict):
            errors.append(f"storyboard step {step_id or '?'} needs beat_visual_spec")
        else:
            text = " ".join(
                str(item or "")
                for item in (
                    step.get("why"),
                    step.get("equation"),
                    step.get("substitution"),
                    json_safe_text(step.get("labels") or []),
                )
            )
            for error in validate_beat_visual_spec(beat_visual_spec, text=text):
                errors.append(f"storyboard step {step_id or '?'} {error}")

    return errors


def _validate_time_window(value: Any, label: str, errors: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        errors.append(f"{label} time_window must be an object")
        return
    start = value.get("start")
    end = value.get("end")
    if not _is_number(start) or not _is_number(end) or end <= start:
        errors.append(f"{label} time_window must have numeric start < end")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _is_positive(value: Any) -> bool:
    return _is_number(value) and float(value) > 0


def _is_pair(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and _is_number(value[0]) and _is_number(value[1])


def json_safe_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(json_safe_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(json_safe_text(item) for item in value.values())
    return str(value or "")
