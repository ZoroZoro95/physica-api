"""Simultaneous independent flights on one clock, ending at each first contact."""
from .engine import simulate
from .measurements import resolve_measurements
from .models import SceneSimulateRequest, SceneSimulation, SimulateRequest


def simulate_scene(request: SceneSimulateRequest) -> SceneSimulation:
    scene = request.scene
    if not scene.particles:
        raise ValueError('Add at least one particle before simulating the scene')
    tracks = [simulate(SimulateRequest(scene=scene, particle_id=p.id,
        max_time=request.max_time, samples=request.samples)) for p in scene.particles]
    # Resolve contact anchors only after every flight is known. These are final
    # contact dimensions, not instantaneous separation between moving bodies.
    by_id = {track.particle_id: track for track in tracks}
    for track in tracks:
        track.measurements = resolve_measurements(scene, track, by_id)
    return SceneSimulation(scene_id=scene.id, revision=scene.revision,
        duration=max(track.samples[-1].t for track in tracks), tracks=tracks)
