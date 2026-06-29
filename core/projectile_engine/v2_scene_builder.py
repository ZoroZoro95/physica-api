from .v2_models import (
    PhysicsFacts,
    SceneGraph,
    SceneObject,
    SceneSurface,
    SceneEvent,
    WorldConfig,
    VectorMagnitudeDir
)

def build_scene_graph(facts: PhysicsFacts) -> SceneGraph:
    """
    Deterministically maps PhysicsFacts into a SceneGraph.
    No LLM is used here.
    """
    
    # World Config
    gravity = float(facts.known_values.get("g", 10.0))
    world = WorldConfig(gravity=gravity)
    
    # Objects
    scene_objects = []
    for obj in facts.objects:
        # Match actions for this object
        obj_actions = [a for a in facts.actions if a.object_id == obj.id]
        
        position = "origin"
        initial_velocity = None
        
        for action in obj_actions:
            if action.surface_id:
                position = f"origin_on_{action.surface_id}"
            
            if action.type == "projected":
                initial_velocity = VectorMagnitudeDir(
                    magnitude=action.speed if action.speed != "unknown" else facts.unknown.symbol,
                    direction=action.direction
                )
            elif action.type == "released_from_rest":
                initial_velocity = VectorMagnitudeDir(magnitude=0)
                
        scene_objects.append(SceneObject(
            id=obj.id,
            kind=obj.type,
            position=position,
            initial_velocity=initial_velocity
        ))
        
    # Surfaces
    scene_surfaces = []
    for surf in facts.surfaces:
        scene_surfaces.append(SceneSurface(
            id=surf.id,
            kind=surf.type,
            angle_deg=surf.angle_deg
        ))
        
    # Events
    scene_events = []
    for ev in facts.events:
        scene_events.append(SceneEvent(
            kind=ev.type,
            time_sec=ev.time_sec
        ))
        
    return SceneGraph(
        world=world,
        objects=scene_objects,
        surfaces=scene_surfaces,
        events=scene_events
    )
