from typing import List
from .v2_models import StoryboardStep, NarrationStep, TimelineBlock, Timeline

def build_timeline(storyboard: List[StoryboardStep], narrations: List[NarrationStep]) -> Timeline:
    """
    Merges Storyboard steps and Narration steps into a single continuous Timeline JSON.
    """
    blocks = []
    current_time = 0.0

    for step, narration in zip(storyboard, narrations):
        duration = step.primitive.duration_sec
        start_sec = current_time
        end_sec = current_time + duration

        # Collect text overlays if present
        overlays = []
        if step.primitive.text_overlay:
            overlays.append(step.primitive.text_overlay)
        if step.primitive.equation_id:
            overlays.append(f"equation:{step.primitive.equation_id}")

        block = TimelineBlock(
            start_sec=start_sec,
            end_sec=end_sec,
            primitive_type=step.primitive.primitive_type.value,
            camera_view=step.primitive.camera_view,
            narration=narration.narration_text,
            overlays=overlays
        )
        blocks.append(block)
        current_time = end_sec

    return Timeline(timeline=blocks)
