#!/usr/bin/env python3
"""Real API calls, without an LLM, DB, legacy solver, or network credentials."""
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from core.playground.main import app

client = TestClient(app)
checks = 0


def post(path, payload, status=200):
    global checks
    response = client.post(path, json=payload)
    assert response.status_code == status, response.text
    checks += 1
    return response.json()


def create(commands, gravity=10):
    scene = post("/v1/scenes", {"gravity": gravity})
    return post("/v1/scenes/apply", {"scene": scene, "commands": commands})


def run(scene, particle="ball", **kwargs):
    return post("/v1/simulations", {"scene": scene, "particle_id": particle, **kwargs})


def launch(speed, angle):
    return {"op": "set_launch", "particle_id": "ball", "speed": speed,
            "direction": "angle", "angle_deg": angle}


ground = {"op": "add_surface", "surface": {"kind": "ground", "id": "floor"}}
ball = {"op": "add_particle", "id": "ball", "position": {"x": 0, "y": 0}}
scene = create([ground, ball, launch(25, 45)])
assert post("/v1/scenes/validate", scene) == scene
normalized = post("/v1/scenes/validate", {"particles": [], "surfaces": []})
assert normalized["gravity"] == 9.8 and normalized["annotations"] == []
post("/v1/scenes/validate", {"schema_version": "unsupported"}, 422)
result = run(scene)
assert result["status"] == "contact"
assert math.isclose(result["contact"]["time"], 5/math.sqrt(2))
assert math.isclose(result["contact"]["position"]["x"], 62.5)
assert abs(result["samples"][-1]["position"]["y"]) < 1e-8
assert run(scene, samples=2)["contact"] == run(scene, samples=1001)["contact"]
for sample in result["samples"]:
    assert math.isclose(sample["velocity"]["x"], 25/math.sqrt(2))
    energy = sum(v*v for v in sample["velocity"].values())/2 + 10*sample["position"]["y"]
    assert math.isclose(energy, 25**2/2)

# Same launch physics for arbitrary names, angles, and mirrored geometry.
for rising in (True, False):
    for angle in (20, 30, 45):
        height = 100*math.tan(math.radians(angle))
        wedge = {"kind": "wedge", "id": "ramp", "width": 100, "height": height, "rising": rising}
        incline_scene = create([
            {"op": "add_surface", "surface": wedge},
            {"op": "add_particle", "id": "ball", "on_surface": {"surface_id": "ramp", "fraction": 0.5}},
            {"op": "set_launch", "particle_id": "ball", "speed": 10,
             "direction": "surface_normal", "surface_id": "ramp"},
        ])
        hit = run(incline_scene)["contact"]
        expected_time = 20/(10*math.cos(math.radians(angle)))
        assert math.isclose(hit["time"], expected_time), hit
        start = incline_scene["particles"][0]["position"]
        distance = math.hypot(hit["position"]["x"]-start["x"], hit["position"]["y"]-start["y"])
        expected_range = 20*math.sin(math.radians(angle))/math.cos(math.radians(angle))**2
        assert math.isclose(distance, expected_range), hit
        assert hit["face"] == "top"
        mesh = post("/v1/geometry", incline_scene)["meshes"][0]
        assert len(mesh["vertices"]) == 6 and len(mesh["triangles"]) == 8
        vertices_xy = {(v[0], v[1]) for v in mesh["vertices"]}
        for face in mesh["collision_faces"]:
            assert tuple(face["from"].values()) in vertices_xy
            assert tuple(face["to"].values()) in vertices_xy

for angle in (-30, 30):
    angled = create([{"op": "add_wedge", "id": "ramp", "width": 100, "angle_deg": angle}])
    assert math.isclose(angled["surfaces"][0]["height"], 100/math.sqrt(3))
    assert angled["surfaces"][0]["rising"] == (angle > 0)
    post("/v1/scenes/apply", {"scene": angled, "commands": [
        {"op": "add_wedge", "id": "bad", "width": 100, "angle_deg": 0}
    ]}, 422)

# A vertical wedge side requires a linear intersection, not a flight-time shortcut.
wall = create([
    {"op": "add_surface", "surface": {"kind": "wedge", "id": "wall", "origin": {"x": 5},
                                        "width": 10, "height": 20, "rising": False}},
    {"op": "add_particle", "id": "ball", "position": {"y": 10}}, launch(5, 0),
])
hit = run(wall)["contact"]
assert hit["face"] == "side" and math.isclose(hit["time"], 1)
assert math.isclose(hit["position"]["y"], 5)

cliff = create([ground, {"op": "add_particle", "id": "ball", "position": {"y": 45}}, launch(10, 0)])
assert math.isclose(run(cliff)["contact"]["time"], 3)
assert run(cliff, max_time=1)["status"] == "time_limit"
short_floor = create([
    {"op": "add_surface", "surface": {"kind": "ground", "id": "floor", "x_min": -1, "x_max": 1}},
    ball, launch(25, 45),
])
assert run(short_floor)["status"] == "time_limit"
assert run(create([ground, ball, launch(0, 0)]))["contact"]["time"] == 0
assert run(create([ground, ball, launch(5, -90)]))["contact"]["time"] == 0
# A normal launch at the lower wedge corner departs the solid, even though
# it moves into the base's half-plane. It must not be stopped at t=0.
corner = create([
    {"op": "add_surface", "surface": {"kind": "wedge", "id": "ramp", "width": 20, "height": 10}},
    {"op": "add_particle", "id": "ball", "on_surface": {"surface_id": "ramp", "fraction": 0}},
    {"op": "set_launch", "particle_id": "ball", "speed": 10,
     "direction": "surface_normal", "surface_id": "ramp"},
])
assert run(corner)["status"] == "time_limit"
post("/v1/simulations", {"scene": create([ground, ball]), "particle_id": "ball"}, 422)
buried = create([ground, {"op": "add_particle", "id": "ball", "position": {"y": -1}}, launch(10, 90)])
post("/v1/simulations", {"scene": buried, "particle_id": "ball"}, 422)

# Presentation changes must not alter physics; annotations persist until hidden.
annotation = {"target": "ball", "quantity": "velocity"}
decorated = post("/v1/scenes/apply", {"scene": scene, "commands": [
    {"op": "set_annotation", "annotation": annotation},
]})
assert run(decorated)["samples"] == result["samples"]
assert decorated["annotations"] == [annotation]
hidden = post("/v1/scenes/apply", {"scene": decorated, "commands": [
    {"op": "set_annotation", "annotation": annotation, "visible": False},
]})
assert not hidden["annotations"]
assert scene["revision"] == 1 and decorated["revision"] == 2

# Strict declarative boundary, limits, missing references, atomic batches.
for command in [
    ball,
    {"op": "execute", "code": "arbitrary code"},
    {"op": "add_particle", "id": "other", "position": {}, "on_surface": {"surface_id": "floor", "fraction": 0}},
    {"op": "set_launch", "particle_id": "missing", "speed": 10, "direction": "angle", "angle_deg": 0},
    {"op": "set_launch", "particle_id": "ball", "speed": 10, "direction": "surface_normal", "surface_id": "missing"},
    {"op": "set_annotation", "annotation": {"target": "floor", "quantity": "velocity"}},
]:
    post("/v1/scenes/apply", {"scene": scene, "commands": [command]}, 422)
post("/v1/scenes/apply", {"scene": scene, "commands": [launch(100, 60), ball]}, 422)
assert run(scene)["samples"] == result["samples"]
post("/v1/simulations", {"scene": scene, "particle_id": "ball", "samples": 1002}, 422)
post("/v1/scenes", {"gravity": "NaN"}, 422)
post("/v1/scenes", {"gravity": "Infinity"}, 422)
for invalid in ("NaN", "Infinity", "-Infinity"):
    response = client.post("/v1/scenes", content='{"gravity":'+invalid+'}',
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 422, response.text
post("/v1/scenes/apply", {"scene": scene, "commands": [
    {"op": "add_surface", "surface": {"id": "tiny", "kind": "wedge", "width": 1e-100, "height": 1}}
]}, 422)
assert client.get("/openapi.json").status_code == 200
print(f"PASS playground API: {checks} requests plus numerical, geometry, and isolation assertions")
