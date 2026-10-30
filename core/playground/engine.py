"""Analytical point-particle motion and finite surface contacts in the XY plane."""
from __future__ import annotations

import math

import numpy as np

from .models import (
    AddParticle, AddSurface, AddWedge, ApplyRequest, Contact, ContactFace, Ground, Particle, Point,
    Sample, Scene, ScheduleLaunchRequest, SetAnnotation, SetLaunch, SetMeasurement, SimulateRequest, Simulation, Staircase, Surface, Vector, Wedge,
)
from .measurements import resolve_measurements

EPS = 1e-8


def polygon(surface: Surface) -> list[Point]:
    if isinstance(surface, Ground):
        return [Point(x=surface.x_min, y=surface.y), Point(x=surface.x_max, y=surface.y)]
    x, y, w, h = surface.origin.x, surface.origin.y, surface.width, surface.height
    # Counterclockwise triangle; top endpoints are always ordered left to right.
    if surface.rising:
        return [Point(x=x, y=y), Point(x=x+w, y=y), Point(x=x+w, y=y+h)]
    return [Point(x=x, y=y), Point(x=x+w, y=y), Point(x=x, y=y+h)]


def top(surface: Surface) -> tuple[Point, Point]:
    if isinstance(surface, Staircase):
        raise ValueError("Staircase has multiple faces; use explicit coordinates and an angle launch")
    vertices = polygon(surface)
    if isinstance(surface, Ground):
        return vertices[0], vertices[1]
    return (vertices[0], vertices[2]) if surface.rising else (vertices[2], vertices[1])


def find(items, object_id):
    for item in items:
        if item.id == object_id:
            return item
    raise ValueError(f"Unknown object: {object_id}")


def apply(request: ApplyRequest) -> Scene:
    scene = request.scene.model_copy(deep=True)
    for command in request.commands:
        if isinstance(command, AddSurface):
            scene.surfaces.append(command.surface.model_copy(deep=True))
        elif isinstance(command, AddWedge):
            scene.surfaces.append(Wedge(
                id=command.id, origin=command.origin, width=command.width, depth=command.depth,
                height=command.width*abs(math.tan(math.radians(command.angle_deg))),
                rising=command.angle_deg > 0,
            ))
        elif isinstance(command, AddParticle):
            position = command.position
            if command.on_surface:
                a, b = top(find(scene.surfaces, command.on_surface.surface_id))
                f = command.on_surface.fraction
                position = Point(x=a.x + f*(b.x-a.x), y=a.y + f*(b.y-a.y))
            scene.particles.append(Particle(id=command.id, position=position))
        elif isinstance(command, SetLaunch):
            particle = find(scene.particles, command.particle_id)
            if command.direction == "angle":
                angle = math.radians(command.angle_deg)
            else:
                a, b = top(find(scene.surfaces, command.surface_id))
                angle = math.atan2(b.y-a.y, b.x-a.x)
                if command.direction == "surface_normal":
                    angle += math.pi / 2
            particle.velocity = Point(x=command.speed*math.cos(angle), y=command.speed*math.sin(angle))
            particle.launch_set = True
        elif isinstance(command, SetAnnotation):
            scene.annotations = [a for a in scene.annotations if a != command.annotation]
            if command.visible:
                scene.annotations.append(command.annotation.model_copy(deep=True))
        elif isinstance(command, SetMeasurement):
            scene.measurements = [m for m in scene.measurements or [] if m.id != command.measurement.id]
            if command.visible:
                scene.measurements.append(command.measurement.model_copy(deep=True))
        # Revalidate after each action; a batch is returned only if every action succeeds.
        scene = Scene.model_validate(scene.model_dump())
    scene.revision += 1
    return scene


def schedule_launch(request: ScheduleLaunchRequest) -> Scene:
    scene = request.scene.model_copy(deep=True)
    find(scene.particles, request.particle_id).launch_time = request.launch_time
    scene.revision += 1
    return Scene.model_validate(scene.model_dump())


def state(particle: Particle, gravity: float, t: float) -> Sample:
    p, v = particle.position, particle.velocity
    return Sample(t=t, position=Vector(x=p.x+v.x*t, y=p.y+v.y*t-gravity*t*t/2),
                  velocity=Vector(x=v.x, y=v.y-gravity*t))


def faces(surface: Surface):
    if isinstance(surface, Staircase):
        sign = 1 if surface.direction == "right" else -1
        x, y = surface.origin.x, surface.origin.y
        yield "platform", Point(x=x-sign*surface.run, y=y), Point(x=x, y=y)
        for i in range(1, surface.count+1):
            a = Point(x=x+sign*(i-1)*surface.run, y=y-(i-1)*surface.rise)
            b = Point(x=a.x, y=y-i*surface.rise)
            c = Point(x=x+sign*i*surface.run, y=b.y)
            yield f"riser:{i}", a, b
            yield f"tread:{i}", b, c
        bottom = y-surface.count*surface.rise-surface.base_thickness
        end = Point(x=c.x, y=bottom)
        start = Point(x=x-sign*surface.run, y=bottom)
        yield "end", c, end
        yield "base", end, start
        yield "rear", start, Point(x=x-sign*surface.run, y=y)
        return
    vertices = polygon(surface)
    if isinstance(surface, Ground):
        yield "top", vertices[0], vertices[1]
        return
    for i, a in enumerate(vertices):
        b = vertices[(i+1) % 3]
        name = "base" if i == 0 else "side" if a.x == b.x else "top"
        yield name, a, b


def cross(a, b):
    return a[0]*b[1] - a[1]*b[0]


def inside(particle: Particle, surface: Surface) -> bool:
    p = particle.position
    if isinstance(surface, Staircase):
        sign = 1 if surface.direction == "right" else -1
        x = sign*(p.x-surface.origin.x)
        bottom = surface.origin.y-surface.count*surface.rise-surface.base_thickness
        if not -surface.run+EPS < x < surface.count*surface.run-EPS or p.y <= bottom+EPS:
            return False
        # Internal cell boundaries are solid too; use the lower adjacent tread.
        step = max(0, min(surface.count, math.floor(x/surface.run)+1))
        return p.y < surface.origin.y-step*surface.rise-EPS
    if isinstance(surface, Ground):
        return surface.x_min <= p.x <= surface.x_max and p.y < surface.y-EPS
    return all(cross((b.x-a.x, b.y-a.y), (p.x-a.x, p.y-a.y)) > EPS
               for _, a, b in faces(surface))


def contact_times(particle: Particle, g: float, a: Point, b: Point):
    dx, dy = b.x-a.x, b.y-a.y
    length = math.hypot(dx, dy)
    dx, dy = dx/length, dy/length
    p, v = particle.position, particle.velocity
    coefficients = [cross((p.x-a.x, p.y-a.y), (dx, dy)),
                    cross((v.x, v.y), (dx, dy)), g*dx/2]
    # NumPy handles both linear (vertical wall) and quadratic intersections.
    if all(abs(c) < EPS for c in coefficients):
        return [0.0]
    roots = np.polynomial.polynomial.polyroots(coefficients)
    return sorted(float(r.real) for r in roots if abs(r.imag) < EPS and r.real >= -EPS)


def enters_at_start(particle: Particle, surface: Surface, g: float) -> bool:
    p, v = particle.position, particle.velocity
    if isinstance(surface, Ground):
        return v.y < -EPS or (abs(v.y) <= EPS and g > 0)
    if isinstance(surface, Staircase):
        # Union of rectangular columns. Check the infinitesimal motion against
        # each column, without a numerical time step that might skip a thin stair.
        def enters(distance, velocity, acceleration):
            if distance < -EPS:
                return False
            return distance > EPS or velocity > EPS or (abs(velocity) <= EPS and acceleration > 0)

        for left, right, bottom, upper in stair_cells(surface):
            if all(enters(*terms) for terms in (
                (p.x-left, v.x, 0), (right-p.x, -v.x, 0),
                (p.y-bottom, v.y, -g), (upper-p.y, -v.y, g),
            )):
                return True
        return False
    # At a corner, entering one half-plane is insufficient: the particle must
    # enter every half-plane defining the convex solid, not depart another face.
    for _, a, b in faces(surface):
        length = math.hypot(b.x-a.x, b.y-a.y)
        edge = ((b.x-a.x)/length, (b.y-a.y)/length)
        distance = cross(edge, (p.x-a.x, p.y-a.y))
        if distance < -EPS:
            return False
        if abs(distance) <= EPS:
            velocity = cross(edge, (v.x, v.y))
            acceleration = cross(edge, (0, -g))
            if velocity < -EPS or (abs(velocity) <= EPS and acceleration <= 0):
                return False
    return True


def simulate(request: SimulateRequest) -> Simulation:
    particle = find(request.scene.particles, request.particle_id)
    delay = particle.launch_time
    if delay > request.max_time:
        if not particle.launch_set:
            raise ValueError("Set the launch explicitly; use speed=0 for release from rest")
        for surface in request.scene.surfaces:
            if inside(particle, surface):
                raise ValueError(f"Particle starts inside solid surface: {surface.id}")
        result = Simulation(scene_id=request.scene.id, revision=request.scene.revision,
            particle_id=particle.id, status='waiting', launch_time=delay, contact=None,
            samples=[Sample(t=t, position=Vector(x=particle.position.x, y=particle.position.y),
                velocity=Vector(x=0, y=0)) for t in [0.0, request.max_time]],
            annotations=request.scene.annotations)
        result.measurements = resolve_measurements(request.scene, result)
        return result
    # The public horizon is absolute scene time. A launch exactly at its end
    # has a zero-duration flight; the internal solver handles that boundary.
    flight_request = request.model_copy(update={'max_time': request.max_time-delay})
    result = _simulate_flight(flight_request)
    result.launch_time = delay
    if delay:
        for sample in result.samples:
            sample.t = min(request.max_time, sample.t + delay)
        if result.contact:
            result.contact.time = min(request.max_time, result.contact.time + delay)
    return result


def _simulate_flight(request: SimulateRequest) -> Simulation:
    scene = request.scene
    particle = find(scene.particles, request.particle_id)
    if not particle.launch_set:
        raise ValueError("Set the launch explicitly; use speed=0 for release from rest")
    earliest = None
    for surface in scene.surfaces:
        if inside(particle, surface):
            raise ValueError(f"Particle starts inside solid surface: {surface.id}")
        for face, a, b in faces(surface):
            dx, dy = b.x-a.x, b.y-a.y
            for t in contact_times(particle, scene.gravity, a, b):
                t = max(0.0, t)
                # A root at the requested endpoint may round a few ulps past it.
                # Clamp only machine-scale drift, not a genuinely later event.
                tolerance = 64 * math.ulp(max(t, request.max_time, 1.0))
                if request.max_time < t <= request.max_time + tolerance:
                    t = request.max_time
                if t > request.max_time or (earliest and t >= earliest.time):
                    continue
                sample = state(particle, scene.gravity, t)
                fraction = ((sample.position.x-a.x)*dx + (sample.position.y-a.y)*dy)/(dx*dx+dy*dy)
                if not -EPS <= fraction <= 1+EPS:
                    continue
                if t <= EPS:
                    if not enters_at_start(particle, surface, scene.gravity):
                        continue
                earliest = Contact(time=t, surface_id=surface.id, face=face,
                                   position=sample.position, velocity=sample.velocity)
    if earliest:
        # At a shared vertex the root order can change under mirroring. Report
        # every face at the same physical point rather than an arbitrary riser.
        p = earliest.position
        touching = []
        for surface in scene.surfaces:
            for name, a, b in faces(surface):
                dx, dy = b.x-a.x, b.y-a.y
                length = math.hypot(dx, dy)
                along = ((p.x-a.x)*dx + (p.y-a.y)*dy) / length
                normal = abs((p.x-a.x)*dy - (p.y-a.y)*dx) / length
                if normal <= EPS and -EPS <= along <= length+EPS:
                    touching.append(ContactFace(surface_id=surface.id, face=name))
        touching.sort(key=lambda f: (0 if f.face == 'top' or f.face.startswith('tread:') else 1,
                                    f.surface_id, f.face))
        if touching:
            earliest.touching_faces = touching
            earliest.surface_id, earliest.face = touching[0].surface_id, touching[0].face
    duration = earliest.time if earliest else request.max_time
    times = np.linspace(0, duration, request.samples) if duration > 0 else [0.0]
    result = Simulation(scene_id=scene.id, revision=scene.revision, particle_id=particle.id,
                      status="contact" if earliest else "time_limit", contact=earliest,
                      samples=[state(particle, scene.gravity, float(t)) for t in times],
                      annotations=scene.annotations)
    result.measurements = resolve_measurements(scene, result)
    return result


def stair_cells(surface: Staircase):
    sign = 1 if surface.direction == "right" else -1
    x, y = surface.origin.x, surface.origin.y
    bottom = y-surface.count*surface.rise-surface.base_thickness
    for i in range(-1, surface.count):
        a, b = x+sign*i*surface.run, x+sign*(i+1)*surface.run
        yield min(a, b), max(a, b), bottom, y-(i+1)*surface.rise


def stair_geometry(surface: Staircase) -> dict:
    vertices, triangles = [], []
    # Rectangular columns tile the solid exactly. Only the exterior boundary
    # is outlined, so column seams do not become fictitious diagram surfaces.
    for left, right, bottom, upper in stair_cells(surface):
        offset = len(vertices)
        vertices.extend([[x, y, z] for z in [-surface.depth/2, surface.depth/2]
                         for x, y in [(left, bottom), (right, bottom), (right, upper), (left, upper)]])
        triangles.extend([[offset+j for j in face] for face in (
            [0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
            [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
            [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7],
        )])
    outline = []
    for _, a, b in faces(surface):
        for z in [-surface.depth/2, surface.depth/2]:
            outline.extend([[a.x, a.y, z], [b.x, b.y, z]])
        outline.extend([[a.x, a.y, -surface.depth/2], [a.x, a.y, surface.depth/2]])
    return {"id": surface.id, "kind": "staircase", "vertices": vertices,
            "triangles": triangles, "outline": outline,
            "collision_faces": [{"face": name, "from": a.model_dump(), "to": b.model_dump()}
                                for name, a, b in faces(surface)]}


def geometry(scene: Scene) -> list[dict]:
    """Extrude the exact collision polygon, so a renderer need not reconstruct it."""
    meshes = []
    for surface in scene.surfaces:
        if isinstance(surface, Staircase):
            meshes.append(stair_geometry(surface))
            continue
        points = polygon(surface)
        if isinstance(surface, Ground):
            meshes.append({"id": surface.id, "kind": "ground", "segment": [p.model_dump() for p in points]})
            continue
        vertices = [[p.x, p.y, z] for z in [-surface.depth/2, surface.depth/2] for p in points]
        triangles = [[0, 2, 1], [3, 4, 5], [0, 1, 4], [0, 4, 3],
                     [1, 2, 5], [1, 5, 4], [2, 0, 3], [2, 3, 5]]
        meshes.append({"id": surface.id, "kind": "wedge", "vertices": vertices, "triangles": triangles,
                       "collision_faces": [{"face": name, "from": a.model_dump(), "to": b.model_dump()}
                                           for name, a, b in faces(surface)]})
    return meshes
