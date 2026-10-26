from __future__ import annotations

from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

Number = Annotated[float, Field(allow_inf_nan=False, ge=-100_000, le=100_000)]
Positive = Annotated[float, Field(allow_inf_nan=False, ge=1e-6, le=10_000)]
ObjectId = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Point(Model):
    x: Number = 0
    y: Number = 0


class Ground(Model):
    kind: Literal["ground"] = "ground"
    id: ObjectId
    y: Number = 0
    x_min: Number = -1000
    x_max: Number = 1000

    @model_validator(mode="after")
    def ordered(self):
        if self.x_max - self.x_min < 1e-6:
            raise ValueError("Ground span must be at least 1e-6 metres")
        return self


class Wedge(Model):
    kind: Literal["wedge"] = "wedge"
    id: ObjectId
    origin: Point = Field(default_factory=Point)
    width: Positive
    height: Positive
    depth: Positive = 1
    rising: bool = True


class Staircase(Model):
    kind: Literal["staircase"] = "staircase"
    id: ObjectId
    # Origin is the departure corner; a one-run approach platform lies behind it.
    origin: Point = Field(default_factory=Point)
    rise: Positive
    run: Positive
    count: int = Field(ge=1, le=128)
    direction: Literal["right", "left"] = "right"
    depth: Positive = 1
    base_thickness: Positive = 1

    @model_validator(mode="after")
    def bounded_extent(self):
        if self.count*self.run > 10_000 or self.count*self.rise+self.base_thickness > 10_000:
            raise ValueError("Staircase extent must not exceed 10000 metres")
        return self


Surface = Annotated[Ground | Wedge | Staircase, Field(discriminator="kind")]


class Particle(Model):
    id: ObjectId
    position: Point
    velocity: Point = Field(default_factory=Point)
    launch_set: bool = False


class Annotation(Model):
    target: ObjectId
    quantity: Literal["velocity", "velocity_x", "velocity_y", "gravity", "highlight"]


class FixedAnchor(Model):
    kind: Literal["point"]
    point: Point


class ObjectAnchor(Model):
    kind: Literal["object"]
    target: ObjectId
    feature: Literal["launch", "contact", "origin", "top_start", "top_end",
                     "base_start", "base_end", "step_upper", "step_start", "step_end"]
    step: int = Field(default=1, ge=1, le=128)


Anchor = Annotated[FixedAnchor | ObjectAnchor, Field(discriminator="kind")]


class DistanceMeasurement(Model):
    kind: Literal["distance"]
    id: ObjectId
    label: str = Field(min_length=1, max_length=60)
    start: Anchor
    end: Anchor
    axis: Literal["horizontal", "vertical", "direct"] = "direct"
    side: Literal[-1, 1] = 1


class AngleMeasurement(Model):
    kind: Literal["angle"]
    id: ObjectId
    label: str = Field(min_length=1, max_length=60)
    start: Anchor
    vertex: Anchor
    end: Anchor


Measurement = Annotated[DistanceMeasurement | AngleMeasurement, Field(discriminator="kind")]


def check_measurement(measurement, surfaces, particles):
    objects = {item.id: item for item in [*surfaces, *particles]}
    anchors = [measurement.start, measurement.end]
    if isinstance(measurement, AngleMeasurement):
        anchors.append(measurement.vertex)
    for anchor in anchors:
        if not isinstance(anchor, ObjectAnchor):
            continue
        obj = objects.get(anchor.target)
        if obj is None:
            raise ValueError("Measurement target does not exist")
        if isinstance(obj, Particle):
            allowed = {"launch", "contact"}
        elif isinstance(obj, Staircase):
            allowed = {"origin", "step_upper", "step_start", "step_end"}
        else:
            allowed = {"origin", "top_start", "top_end", "base_start", "base_end"}
        if anchor.feature not in allowed:
            raise ValueError(f"Measurement feature {anchor.feature} is not supported by {anchor.target}")
        if anchor.feature.startswith("step_") and anchor.step > obj.count:
            raise ValueError("Measurement step exceeds staircase count")
        if not anchor.feature.startswith("step_") and anchor.step != 1:
            raise ValueError("Only staircase step features accept a step index")


class Scene(Model):
    schema_version: Literal["1"] = "1"
    id: str = Field(default_factory=lambda: str(uuid4()), max_length=64)
    revision: int = Field(default=0, ge=0)
    gravity: Positive = 9.8
    surfaces: list[Surface] = Field(default_factory=list, max_length=32)
    particles: list[Particle] = Field(default_factory=list, max_length=16)
    annotations: list[Annotation] = Field(default_factory=list, max_length=80)
    # None preserves default staircase dimensions for existing scene files.
    # An explicit list (including []) replaces defaults.
    measurements: list[Measurement] | None = Field(default=None, max_length=24)

    @model_validator(mode="after")
    def references(self):
        ids = [item.id for item in [*self.surfaces, *self.particles]]
        if len(ids) != len(set(ids)):
            raise ValueError("Object IDs must be unique within a scene")
        particles = {p.id for p in self.particles}
        for annotation in self.annotations:
            if annotation.target not in ids:
                raise ValueError("Annotation target does not exist")
            if annotation.quantity != "highlight" and annotation.target not in particles:
                raise ValueError("Vector annotations require a particle")
        measurements = self.measurements or []
        if len({m.id for m in measurements}) != len(measurements):
            raise ValueError("Measurement IDs must be unique")
        for measurement in measurements:
            check_measurement(measurement, self.surfaces, self.particles)
        return self


class AddSurface(Model):
    op: Literal["add_surface"]
    surface: Surface


class AddWedge(Model):
    """Use for a slope specified by angle. Engine derives height without rounding."""
    op: Literal["add_wedge"]
    id: ObjectId
    origin: Point = Field(default_factory=Point)
    width: Positive
    angle_deg: Annotated[float, Field(gt=-90, lt=90, allow_inf_nan=False)]
    depth: Positive = 1

    @model_validator(mode="after")
    def nonzero_angle(self):
        if abs(self.angle_deg) < 1e-6:
            raise ValueError("Use ground for a zero-angle surface")
        return self


class Placement(Model):
    surface_id: ObjectId
    fraction: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class AddParticle(Model):
    """Create a particle at exactly one placement. Set its velocity separately with set_launch."""
    op: Literal["add_particle"]
    id: ObjectId
    position: Point | None = Field(default=None, description="Explicit coordinates {x,y}; required unless on_surface is provided. Never leave both placements null.")
    on_surface: Placement | None = Field(default=None, description="Alternative to position: place on a named ground/wedge at fraction 0..1. Not supported for staircases.")

    @model_validator(mode="after")
    def one_position(self):
        if (self.position is None) == (self.on_surface is None):
            raise ValueError("Specify exactly one of position or on_surface")
        return self


class SetLaunch(Model):
    """Set the initial velocity of an already added particle. Use angle_deg OR surface_id, not both."""
    op: Literal["set_launch"]
    particle_id: ObjectId
    speed: Annotated[float, Field(ge=0, le=10_000, allow_inf_nan=False)]
    direction: Literal["angle", "surface_normal", "surface_tangent"]
    angle_deg: Annotated[float, Field(ge=-360, le=360, allow_inf_nan=False)] | None = None
    surface_id: ObjectId | None = None

    @model_validator(mode="after")
    def direction_fields(self):
        if self.direction == "angle":
            if self.angle_deg is None or self.surface_id is not None:
                raise ValueError("angle requires angle_deg and no surface_id")
        elif self.surface_id is None or self.angle_deg is not None:
            raise ValueError("Surface-relative launch requires surface_id and no angle_deg")
        return self


class SetAnnotation(Model):
    op: Literal["set_annotation"]
    annotation: Annotation
    visible: bool = True


class SetMeasurement(Model):
    op: Literal["set_measurement"]
    measurement: Measurement
    visible: bool = True


Command = Annotated[AddSurface | AddWedge | AddParticle | SetLaunch | SetAnnotation | SetMeasurement, Field(discriminator="op")]


class ApplyRequest(Model):
    scene: Scene
    commands: list[Command] = Field(min_length=1, max_length=64)


class CreateRequest(Model):
    gravity: Positive = 9.8


class SimulateRequest(Model):
    scene: Scene
    particle_id: ObjectId
    max_time: Annotated[float, Field(gt=0, le=300, allow_inf_nan=False)] = 10
    samples: int = Field(default=121, ge=2, le=1001)


class Vector(Model):
    x: Annotated[float, Field(allow_inf_nan=False)]
    y: Annotated[float, Field(allow_inf_nan=False)]


class Sample(Model):
    t: float
    position: Vector
    velocity: Vector


class ContactFace(Model):
    surface_id: ObjectId
    face: str


class Contact(Model):
    time: float
    surface_id: ObjectId
    face: str
    position: Vector
    velocity: Vector
    touching_faces: list[ContactFace] = Field(default_factory=list)


class ResolvedMeasurement(Model):
    id: str
    label: str
    kind: Literal["distance", "angle"]
    status: Literal["ready", "unavailable"]
    points: list[Vector] = Field(default_factory=list)
    value: float | None = None
    unit: Literal["m", "deg"]
    axis: Literal["horizontal", "vertical", "direct"] = "direct"
    side: Literal[-1, 1] = 1
    reason: str | None = None


class Simulation(Model):
    scene_id: str
    revision: int
    particle_id: ObjectId
    status: Literal["contact", "time_limit"]
    contact: Contact | None
    samples: list[Sample]
    annotations: list[Annotation]
    measurements: list[ResolvedMeasurement] = Field(default_factory=list)
