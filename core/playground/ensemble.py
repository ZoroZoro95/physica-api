"""Independent scheduled flights on one clock, ending at each first contact."""
from .engine import simulate, state
from .encounters import find_encounters
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
    encounters = find_encounters(scene, tracks)
    # Include exact event states so playback does not interpolate past a meeting.
    particles = {p.id: p for p in scene.particles}
    for track in tracks:
        times = {t for event in encounters if track.particle_id in event.particle_ids
                 for t in (event.time, event.end_time)}
        samples = {sample.t: sample for sample in track.samples}
        particle = particles[track.particle_id]
        for time in times:
            sample = state(particle, scene.gravity, time-particle.launch_time)
            sample.t = time
            samples[time] = sample
        track.samples = [samples[t] for t in sorted(samples)]
    return SceneSimulation(scene_id=scene.id, revision=scene.revision,
        duration=max(track.samples[-1].t for track in tracks), tracks=tracks,
        encounters=encounters)
