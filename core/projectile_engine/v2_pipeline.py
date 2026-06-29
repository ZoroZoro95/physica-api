import json
from typing import Dict, Any

from .v2_models import Timeline
from .v2_parser import V2PhysicsParser
from .v2_scene_builder import build_scene_graph
from .v2_solver import solve_physics
from .v2_concepts import extract_concepts
from .v2_director import build_storyboard
from .v2_narrator import V2Narrator
from .v2_timeline import build_timeline

def run_v2_pipeline(question_text: str, engine_case: str) -> Dict[str, Any]:
    """
    Main entry point for the V2 Video Tutor Engine pipeline.
    """
    
    print("[V2 Pipeline] Stage 1: Physics Parser")
    parser = V2PhysicsParser()
    facts = parser.parse_question(question_text)
    
    print("[V2 Pipeline] Stage 2: Scene Graph Builder")
    scene = build_scene_graph(facts)
    
    print("[V2 Pipeline] Stage 3: Physics Solver")
    solver_result = solve_physics(engine_case, scene, facts.known_values)
    
    print("[V2 Pipeline] Stage 4: Concept Graph")
    concepts = extract_concepts(scene)
    
    print("[V2 Pipeline] Stage 5 & 6: Visual Storyboard")
    storyboard = build_storyboard(scene, solver_result, concepts)
    
    print("[V2 Pipeline] Stage 7: Narration Script")
    narrator = V2Narrator()
    narrations = narrator.generate_narration(storyboard)
    
    print("[V2 Pipeline] Stage 8: Timeline Builder")
    timeline = build_timeline(storyboard, narrations)
    
    # Return as primitive dict to pass to frontend
    return json.loads(timeline.model_dump_json())
