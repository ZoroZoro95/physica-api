# Playground API: first vertical slice

Separate entry point, not mounted in the student app. AI callers submit typed
JSON operations, never Python, JavaScript, formulas to evaluate, or drawing code.
This branch does not change the existing Railway entry point.

## Run and verify

Use the repository's Python environment with its existing requirements:

```sh
pip install -r requirements-dev.txt
python -m uvicorn core.playground.main:app --host 127.0.0.1 --port 8001
python scripts/demo_playground_api.py
python scripts/regress_playground_api.py
```

Run the demo and tests in another terminal while the server runs. HTTP tests use
`httpx` from the development requirements; runtime requirements are unchanged.

Interactive API documentation: `http://127.0.0.1:8001/docs`.
Machine-readable tool contracts: `http://127.0.0.1:8001/openapi.json`.
The demo makes real HTTP requests: descending 30-degree wedge, perpendicular
10 m/s launch, g=10; expected range along the surface is 40/3 metres.

## Contract

All lengths are metres, times seconds, speeds metres/second, and angles degrees.
Motion is in XY; positive y is up and gravity points down. Wedges are extruded
along z for a future 3D renderer. Particles are mathematical points, not spheres
with collision radius. Surfaces are stationary. Drag is absent.

| Endpoint | Input and output |
| --- | --- |
| POST /v1/scenes | Explicit gravity; returns empty scene state and UUID |
| POST /v1/scenes/apply | Scene plus ordered commands; returns updated state |
| POST /v1/scenes/validate | Imported scene; validates references and returns canonical state with defaults |
| POST /v1/simulations | Scene, particle ID, time limit, sample count; returns motion through earliest surface contact or time limit |
| POST /v1/geometry | Scene; returns finite ground segments and indexed wedge meshes from the collision geometry |

The service is **stateless**: the caller stores the returned scene and sends it
with the next request. IDs identify a scene snapshot, not a server-side session.
Revision numbers describe caller-managed snapshots, not concurrent-write locks.
Failed command batches return 422 without changing the caller's original scene.
No scene is stored by this service; no database, AI key, or student login is used.

Supported commands:

- `add_surface`: finite ground segment or wedge specified by dimensions.
- `add_wedge`: width, signed angle and optional depth. Positive angle rises to
  the right, negative descends. Origin is the lower-left base coordinate.
- `add_particle`: explicit position OR a fraction along a surface's top edge,
  measured left to right. This sets initial position, not a sliding constraint.
- `set_launch`: nonnegative speed and either an angle from +x, the outward/upward
  surface normal, or the left-to-right surface tangent. Speed zero means release.
- `set_annotation`: show/hide a velocity, x/y velocity, gravity, or highlight
  instruction. Annotations persist until hidden; they cannot alter physics.

Example command batch, after creating a scene:

```json
[
  {"op":"add_wedge","id":"ramp","width":100,"angle_deg":-30},
  {"op":"add_particle","id":"ball","on_surface":{"surface_id":"ramp","fraction":0.3}},
  {"op":"set_launch","particle_id":"ball","speed":10,"direction":"surface_normal","surface_id":"ramp"}
]
```

`simulate` checks every finite face of every surface, including wedge sides and
base. It solves line/path intersections with NumPy polynomial roots and samples
the analytical constant-gravity equations. Contact detection is independent of
sample count. A boundary launch may depart; an inward launch stops at t=0.
Starting inside a solid is rejected. No-contact within the requested horizon
returns `time_limit`, not an invented landing. A launch must be set explicitly.

Meshes use the exact polygon used for contact, not a separate illustration.
Annotations are presentation instructions only. The separate viewer uses returned
positions and velocities for moving arrows; annotations never change motion.

## Limits and exclusions

This is a local prototype, not a public deployment. Bind to loopback. There is no
authentication, rate limiting, persistent scene ownership, or production ingress
body limit. Model limits cap objects (32 surfaces, 16 particles), commands (64),
samples (1001), and time (300 s). Nonfinite numbers and unknown fields are rejected.

Each simulation follows one selected particle. Other particles do not collide
with it. There are no bounces, sliding constraints, moving surfaces,
fragmentation or symbolic unknown solving. A bounded local text tool adapter now
exists (see `playground-agent.md`), but live-provider acceptance is still pending.
The existing question solver remains separate and unchanged.

## Staircases

`add_surface` accepts `kind: "staircase"`, with `id`, positive `rise` and `run`,
integer `count` (1-128), optional `origin`, `direction` (`right` or `left`), `depth`
and `base_thickness`. Origin is the top departure corner. A one-run approach
platform lies behind it. Step 1 is one rise below origin, spanning one run in
the descent direction. Numbering is independent of labels and world coordinates.

Use explicit particle coordinates and an angle launch: stairs have no single
surface tangent or normal, so ambiguous `on_surface` placement is rejected.
Contacts distinguish `tread:N`, `riser:N`, `platform`, `rear`, `end`, `base`.
At a shared corner either incident face can identify the same physical contact.
Stairs are stationary solids; rolling and bouncing are not implemented.

Geometry returns extruded columns tiling the collision solid and its exterior
outline. `python scripts/regress_playground_stairs.py` checks 118 requests covering
changed dimensions, origins, mirroring, sample-count independence, corners,
release/departure, invalid inputs and mesh/collision endpoint agreement.

## Viewer and next acceptance milestone

The separate frontend `/playground` viewer consumes geometry and samples for
wedges, ground and stairs. Its browser audit checks desktop/mobile rendering,
playback, mirrored stairs and agreement with the returned contact position.
Next evaluate the local AI adapter against real model outputs. Do not route the
student app through it until those checks pass.

## Verification checkpoint

The baseline regression script exercises 78 structured API requests plus raw nonfinite
input rejection and numerical assertions: conserved energy, constant horizontal
velocity, mirrored wedge slopes, contact independent of sample count, vertical
side contact, finite surfaces, corner departure, explicit release, invalid IDs,
atomic batches, and presentation/physics separation. The live HTTP demo verifies
2.3094010768 s to contact and 13.3333333333 m along the 30-degree incline.
These are API/physics checks, not visual-rendering or autonomous-AI acceptance.
