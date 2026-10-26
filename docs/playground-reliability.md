# Playground reliability gate

This gate covers numeric, single-point-particle flight under constant downward
gravity against stationary finite ground, wedges and stairs. It does not certify
all kinematics questions, images, symbolic solving, drag, sliding or interacting
bodies. No DPP answer key or saved question answer is used by these checks.

## Deterministic checks

Run from the API repository:

```sh
PHYSICA_RELIABILITY_REPORT=/tmp/physica-reliability/scenes.json \
  python scripts/regress_playground_reliability.py
python -m unittest discover -s scripts -p 'regress_playground_*.py'
```

The matrix evaluates 124 analytically checked scenarios:

| Family | Variants | Independent expectation |
| --- | ---: | --- |
| Level ground | 32 | Flight time and horizontal range from launch components |
| Horizontal cliff launch | 36 | Free-fall time and horizontal displacement |
| Normal launch from incline | 24 | Return time from normal gravity component |
| Staircase | 32 | First tread containing the parabolic trajectory intersection |

Inputs vary speed, gravity, dimensions, direction and coordinate origin. Each
scenario checks position, velocity, energy conservation, contact coordinates,
sample-count independence and agreement with rendered collision boundaries.
Exact end-time checks include the analytical collision instant and a genuinely
earlier horizon. Machine-scale overshoot (64 ulps) is clamped to the requested
endpoint; a later physical collision is not pulled into the simulated interval.
Separate cases check finite-ground misses, insufficient time horizons and
surface-order-independent simultaneous contacts.

## Contact convention

`contact.touching_faces` lists all boundary segments at the contact point, using
the engine's spatial tolerance of 1e-8 m. The primary face is stable: top/tread
faces precede other faces, then surface ID and face name break ties. Contact time
and position remain the earliest analytical intersection, not a sampled event.

For horizontal u=10 m/s with 1 m steps and g=10, the point (20,-20) is shared by
`tread:20` and `riser:21`. The UI labels this a corner, not a contradictory pair of
answers. With g=9.8, the first contact is inside tread 21. Distinct surfaces at the
same contact point are labelled shared contact. Old saved reports without the
new field retain their original face label until re-simulated.

## Browser checks

After starting the local backend/frontend, run from the web repository:

```sh
node scripts/audit-playground-reliability.mjs
node scripts/audit-playground-measurements.mjs
node scripts/audit-playground.mjs
```

The first command reads the exported engine fixtures and exercises 10 scenes at
1440 px and 390 px widths. It checks start/mid-flight/contact via the time slider,
stable camera framing, particle visibility, label clipping/overlap, nonblank
canvas pixels and completed trajectory point count. Screenshots and a JSON report
are stored under `/tmp/physica-reliability/browser/` for visual inspection.

Two rendering regressions found by this sweep were repaired:

- Wide ground segments no longer make the flight microscopic. View fitting uses
  the ground portion near the flight while collision retains the full finite span.
- Scrubbing to a rounded final time no longer collapses the travelled trajectory
  into a straight launch-to-impact chord.

## Live interpretation gate

This is separate from deterministic physics verification and uses the locally
configured provider. It is opt-in, bounded to six cases, spaced by default, with
no automatic retries or fallback model. It keeps failures in its output.

```sh
python scripts/audit_playground_live.py --live \
  --output /tmp/physica-reliability/live.json
```

Cases: level-ground launch; translated leftward cliff launch; descending incline;
explicitly finite stairs; missing speed; unsupported drag. The checker validates
source values, direction, finite extents, horizon, physical result and requested
engine-backed measurements. Model status `review` alone is not a pass.

The first 2026-10-26 run passed five of six. Finite stairs failed before simulation:
the model returned a null position, followed by an upstream request failure.
Report `fec75f26-949d-4c91-90ed-87a1f42a0433` preserves that failure. A nested
JSON-schema exclusivity experiment regressed all three follow-up live cases
(ground, incline, finite stairs); it was removed before committing. Existing API
validation remains authoritative, with clearer placement/launch field descriptions.
Safe HTTP status diagnostics distinguish upstream outages, denied access, request
size (413), and other rejection without logging raw provider messages.

A later run recovered finite stairs (`aa43f57b-e4c3-4076-ba48-349df240475f`) but
hit HTTP 413 before execution on the longer incline request
(`2f803f93-8f89-4978-91bc-a3ecd25ed01d`). Request/tool-schema budget work therefore
remains open. Do not present this milestone as a universal live-model pass.
The live checker also accepts a direct line as horizontal range when its endpoints
are at equal height; that representation is geometrically equivalent, not an
incorrect interpretation. Earlier raw audit results are preserved for review.
