#!/usr/bin/env python3
"""An HTTP client using the same calls an AI tool adapter will make."""
import argparse
import json
import math
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    args = parser.parse_args()

    def post(path, body):
        request = Request(args.url.rstrip("/")+path, data=json.dumps(body).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=10) as response:
            return json.load(response)

    scene = post("/v1/scenes", {"gravity": 10})
    scene = post("/v1/scenes/apply", {"scene": scene, "commands": [
        {"op": "add_wedge", "id": "incline", "width": 100, "angle_deg": -30},
        {"op": "add_particle", "id": "P", "on_surface": {"surface_id": "incline", "fraction": 0.3}},
        {"op": "set_launch", "particle_id": "P", "speed": 10,
         "direction": "surface_normal", "surface_id": "incline"},
        {"op": "set_annotation", "annotation": {"target": "P", "quantity": "velocity"}},
    ]})
    result = post("/v1/simulations", {"scene": scene, "particle_id": "P"})
    meshes = post("/v1/geometry", scene)
    hit = result["contact"]
    assert hit, result
    start = scene["particles"][0]["position"]
    distance = math.hypot(hit["position"]["x"]-start["x"], hit["position"]["y"]-start["y"])
    assert math.isclose(distance, 40/3)
    print(json.dumps({"scene_id": scene["id"], "status": result["status"],
                      "contact_time_s": hit["time"], "range_along_surface_m": distance,
                      "mesh_vertices": len(meshes["meshes"][0]["vertices"]),
                      "trajectory_samples": len(result["samples"])}, indent=2))


if __name__ == "__main__":
    main()
