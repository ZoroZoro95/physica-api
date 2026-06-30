from typing import List
from .v2_models import SceneGraph, Concept

def extract_concepts(scene: SceneGraph) -> List[Concept]:
    """
    Deterministically converts the physics scene into a list of required teaching concepts.
    """
    concepts = []

    # Check for inclined planes
    has_incline = any(s.kind == "inclined_plane" for s in scene.surfaces)
    if has_incline:
        concepts.append(Concept.ROTATED_AXES)
        concepts.append(Concept.GRAVITY_RESOLUTION)

    # Check for specific collision/perpendicular setup (Milestone 1)
    has_normal_launch = any(
        obj.initial_velocity and obj.initial_velocity.direction == "normal_to_surface"
        for obj in scene.objects
    )
    has_collision_event = any(e.kind == "collision" for e in scene.events)

    if has_incline and has_normal_launch and has_collision_event:
        concepts.append(Concept.SHADOW_PROJECTION)
        concepts.append(Concept.SAME_PARALLEL_MOTION)
        concepts.append(Concept.PERPENDICULAR_RETURN)

    return concepts
