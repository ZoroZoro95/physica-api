from typing import List
from .v2_models import SceneGraph, SolverResult, Concept, StoryboardStep, VisualPrimitive, PrimitiveType

def build_storyboard(
    scene: SceneGraph, 
    solver_result: SolverResult, 
    concepts: List[Concept]
) -> List[StoryboardStep]:
    """
    Deterministically sequences primitives into a Storyboard based on the concepts required.
    """
    storyboard = []
    
    # Base setup
    storyboard.append(StoryboardStep(
        primitive=VisualPrimitive(
            primitive_type=PrimitiveType.SHOW_SETUP,
            duration_sec=6.0,
            camera_view="wide_incline",
            targets=["P", "Q", "incline_1"]
        ),
        physics_reason="Introduce the initial state of the problem."
    ))
    
    storyboard.append(StoryboardStep(
        primitive=VisualPrimitive(
            primitive_type=PrimitiveType.PLAY_RAW_MOTION,
            duration_sec=8.0,
            camera_view="wide_incline",
            targets=["P", "Q"]
        ),
        physics_reason="Show the raw motion before analyzing."
    ))
    
    if Concept.SHADOW_PROJECTION in concepts:
        storyboard.append(StoryboardStep(
            primitive=VisualPrimitive(
                primitive_type=PrimitiveType.FREEZE_FRAME,
                duration_sec=3.0,
                camera_view="collision_view",
                targets=["P", "Q"]
            ),
            physics_reason="Pause at the collision point to highlight the event."
        ))
        
    if Concept.ROTATED_AXES in concepts:
        storyboard.append(StoryboardStep(
            primitive=VisualPrimitive(
                primitive_type=PrimitiveType.ROTATE_AXES,
                duration_sec=6.0,
                camera_view="axis_view",
                targets=["incline_1"]
            ),
            physics_reason="Rotate coordinate axes to align with the incline."
        ))
        
    if Concept.GRAVITY_RESOLUTION in concepts:
        storyboard.append(StoryboardStep(
            primitive=VisualPrimitive(
                primitive_type=PrimitiveType.SPLIT_VECTOR,
                duration_sec=8.0,
                camera_view="vector_view",
                targets=["gravity_vector"]
            ),
            physics_reason="Split gravity into along-plane and normal-to-plane components."
        ))
        
    if Concept.SHADOW_PROJECTION in concepts:
        storyboard.append(StoryboardStep(
            primitive=VisualPrimitive(
                primitive_type=PrimitiveType.SHOW_SHADOW_PROJECTION,
                duration_sec=10.0,
                camera_view="parallel_motion_view",
                targets=["P", "Q", "shadow_P"]
            ),
            physics_reason="Both have same acceleration along the incline."
        ))
        
    if Concept.SAME_PARALLEL_MOTION in concepts:
        storyboard.append(StoryboardStep(
            primitive=VisualPrimitive(
                primitive_type=PrimitiveType.COMPARE_PARALLEL_MOTION,
                duration_sec=8.0,
                camera_view="parallel_motion_view",
                targets=["P", "Q"]
            ),
            physics_reason="Show that their parallel displacements are identical."
        ))
        
    if Concept.PERPENDICULAR_RETURN in concepts:
        storyboard.append(StoryboardStep(
            primitive=VisualPrimitive(
                primitive_type=PrimitiveType.ISOLATE_PERPENDICULAR_MOTION,
                duration_sec=8.0,
                camera_view="perpendicular_view",
                targets=["P", "incline_1"]
            ),
            physics_reason="Focus only on P returning to the plane."
        ))
        
    # Math steps
    if solver_result.equations:
        for i, eq in enumerate(solver_result.equations):
            if i == 0:
                storyboard.append(StoryboardStep(
                    primitive=VisualPrimitive(
                        primitive_type=PrimitiveType.SHOW_EQUATION,
                        duration_sec=7.0,
                        camera_view="equation_view",
                        equation_id=eq.id
                    ),
                    physics_reason="Introduce the displacement equation."
                ))
            else:
                storyboard.append(StoryboardStep(
                    primitive=VisualPrimitive(
                        primitive_type=PrimitiveType.SUBSTITUTE_VALUES,
                        duration_sec=7.0,
                        camera_view="equation_view",
                        equation_id=eq.id
                    ),
                    physics_reason="Substitute values into the equation."
                ))
                
    if solver_result.answer:
        storyboard.append(StoryboardStep(
            primitive=VisualPrimitive(
                primitive_type=PrimitiveType.FINAL_ANSWER,
                duration_sec=5.0,
                camera_view="final_view",
                targets=["P"],
                text_overlay=f"u = {solver_result.answer.value} {solver_result.answer.unit}"
            ),
            physics_reason="State the final calculated result."
        ))
        
    return storyboard
