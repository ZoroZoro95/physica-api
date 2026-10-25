# Declarative measurements

Measurements annotate the existing point-particle simulation; they do not change
physics. The AI supplies references, never calculated values. `set_measurement`
is available in both atomic scene recipes and ordinary `/v1/scenes/apply` batches.
Add referenced objects first. Import/export preserves `scene.measurements`.

## Distance example

```json
{
  "op": "set_measurement",
  "measurement": {
    "kind": "distance", "id": "height", "label": "Height",
    "start": {"kind": "object", "target": "P", "feature": "launch"},
    "end": {"kind": "object", "target": "P", "feature": "contact"},
    "axis": "vertical", "side": -1
  }
}
```

Axes: `horizontal` and `vertical` return absolute projected separation;
`direct` returns Euclidean distance (not distance travelled along a trajectory).
`side` controls dimension placement, not the sign of the answer.

An `angle` measurement has `start`, `vertex`, and `end` anchors instead of axis
and side. It returns the smaller angle, 0 to 180 degrees. Zero-length rays are
unavailable, not zero-degree angles.

## Anchors

- Fixed coordinates: `{"kind":"point","point":{"x":0,"y":0}}`.
- Particle: `launch` or `contact`. Contact belongs to the selected particle's
  simulation; another particle's contact is never substituted.
- Wedge/ground: `origin`, `top_start`, `top_end`, `base_start`, `base_end`.
  Start/end are ordered left-to-right. A ground's base and top coincide.
- Staircase: `origin`, `step_upper`, `step_start`, `step_end`, with optional
  one-based `step` (default 1). Upper/start span the riser; start/end span the tread.

Unknown objects, incompatible features, out-of-range steps, duplicate IDs and
extra fields such as a model-supplied `value` are rejected. Limit: 24 explicit
measurements per scene. Reusing an ID replaces that measurement; `visible:false`
removes it.

## Resolution and compatibility

Each simulation returns `measurements` with status, points, numeric value, unit,
and a reason when unavailable. Missing contact does not hide known dimensions.
Values are recomputed from the supplied validated scene on every simulation.
They are static geometry/event measurements, not current-time readouts.

For old scenes, absent/null `scene.measurements` enables legacy staircase
dimensions and launch-to-contact drop. An explicit list replaces these defaults;
an empty list disables them. The first `set_measurement` starts an explicit list.
The UI's Dimensions and angles checkbox only toggles display; it does not mutate
the scene or reset the camera. Imported scenes should be re-simulated after an
API upgrade to obtain resolved measurements.

## Verification

`python scripts/regress_playground_measurements.py`: deterministic references,
values, mirrored wedges, absent contacts, invalid inputs, update/removal, defaults,
and scripted atomic AI orchestration. Frontend audits cover desktop/mobile
staircases, cliffs, slope lengths, angle arcs, label overlap and visibility.

Live acceptance: report `4c043a44-25ca-4fba-ba06-d2a09e0f9d8c` requested a 45 m
cliff launch at 10 m/s, g=10; the model requested height/range annotations and the
engine returned 45 m / 30 m. This is one live case, not proof of universal model
interpretation. No new sliding, drag, or multi-body physics is introduced.
