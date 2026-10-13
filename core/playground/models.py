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


Surface = Annotated[Ground | Wedge, Field(discriminator="kind")]


class Particle(Model):
    id: ObjectId
    position: Point
    velocity: Point = Field(default_factory=Point)
    launch_set: bool = False


class Annotation(Model):
    target: ObjectId
    quantity: Literal["velocity", "velocity_x", "velocity_y", "gravity", "highlight"]


class Scene(Model):
    schema_version: Literal["1"] = "1"
    id: str = Field(default_factory=lambda: str(uuid4()), max_length=64)
    revision: int = Field(default=0, ge=0)
    gravity: Positive = 9.8
    surfaces: list[Surface] = Field(default_factory=list, max_length=32)
    particles: list[Particle] = Field(default_factory=list, max_length=16)
    annotations: list[Annotation] = Field(default_factory=list, max_length=80)

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
        return self


class AddSurface(Model):
    op: Literal["add_surface"]
    surface: Surface


class AddWedge(Model):
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
    op: Literal["add_particle"]
    id: ObjectId
    position: Point | None = None
    on_surface: Placement | None = None

    @model_validator(mode="after")
    def one_position(self):
        if (self.position is None) == (self.on_surface is None):
            raise ValueError("Specify exactly one of position or on_surface")
        return self


class SetLaunch(Model):
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


Command = Annotated[AddSurface | AddWedge | AddParticle | SetLaunch | SetAnnotation, Field(discriminator="op")]


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


class Contact(Model):
    time: float
    surface_id: ObjectId
    face: str
    position: Vector
    velocity: Vector


class Simulation(Model):
    scene_id: str
    revision: int
    particle_id: ObjectId
    status: Literal["contact", "time_limit"]
    contact: Contact | None
    samples: list[Sample]
    annotations: list[Annotation]
