"""Bounded representation of explicitly continuing geometry, not answer lookup."""
from math import ceil

from pydantic import Field

from .engine import simulate
from .models import Model, ObjectId, Scene, SimulateRequest, Simulation, Staircase


class PlannedSimulationRequest(SimulateRequest):
    continuing_staircases: list[ObjectId] = Field(default_factory=list, max_length=32)


class ExtentChange(Model):
    surface_id: ObjectId
    previous_count: int
    planned_count: int
    basis: str = "Explicitly continuing staircase; horizontal travel over requested horizon"


class PlannedSimulation(Model):
    scene: Scene
    simulation: Simulation
    extent_changes: list[ExtentChange]


def plan_simulation(request: PlannedSimulationRequest) -> PlannedSimulation:
    scene = request.scene.model_copy(deep=True)
    particle = next((p for p in scene.particles if p.id == request.particle_id), None)
    if particle is None:
        raise ValueError("Particle does not exist")
    ids = request.continuing_staircases
    if len(ids) != len(set(ids)):
        raise ValueError("Continuing staircase IDs must be unique")
    surfaces = {surface.id: surface for surface in scene.surfaces}
    changes = []
    for surface_id in ids:
        surface = surfaces.get(surface_id)
        if not isinstance(surface, Staircase):
            raise ValueError("Continuing extent is supported only for an existing staircase")
        sign = 1 if surface.direction == 'right' else -1
        start = sign * (particle.position.x - surface.origin.x)
        end = start + sign * particle.velocity.x * max(0, request.max_time-particle.launch_time)
        # Include the vertical face at an exact end-of-tread coordinate. The
        # artificial closing face of a finite extrusion must be beyond the path.
        needed = max(surface.count, ceil(max(0, start, end) / surface.run) + 1)
        if needed > 128 or needed * surface.run > 10_000 or needed * surface.rise + surface.base_thickness > 10_000:
            raise ValueError("Continuing extent exceeds scene limits; shorten the horizon. No physical input was changed.")
        if needed != surface.count:
            changes.append(ExtentChange(surface_id=surface.id,
                previous_count=surface.count, planned_count=needed))
            surface.count = needed
    if changes:
        scene.revision += 1
    scene = Scene.model_validate(scene.model_dump())
    simulation = simulate(SimulateRequest(scene=scene, particle_id=request.particle_id,
        max_time=request.max_time, samples=request.samples))
    return PlannedSimulation(scene=scene, simulation=simulation, extent_changes=changes)
