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

## Request-budget follow-up: 2026-10-26

An experiment retaining local JSON-schema references reduced repetition but
regressed ground-launch tool calls. It was reverted; provider schemas still
inline references and use the original API validation types. A shorter prompt
alone also failed the gate: the incline recipe rounded a derived height, and
finite stairs still encountered HTTP 413. Neither experiment counts as a pass.

The current candidate keeps the compatible schema, reduces redundant prompt
instructions, and requests 2000 rather than 3000 completion tokens. Given slope
angles and surface-relative launch directions must use the corresponding engine
commands rather than model-calculated approximations. This is a general recipe
rule, not a stored answer or per-question special case.

Provider output ending with `finish_reason=length` is rejected before executing
any tools. HTTP 413/429 reports retain only numeric `token_limit`,
`requested_tokens`, `used_tokens` and an allowlisted token window when supplied;
raw provider messages and
organization identifiers are not saved. The generation model and bounded
retry count are unchanged. Long or complex requests can still exceed the budget;
these guards do not promise arbitrary-length input support.

Verification: 65 offline test methods and the desktop/mobile playground browser
audit pass. The final live run passed ground and translated cliff cases (reports
`8d3fd217-89a2-45cf-852e-97e7a2d78887` and
`1f3bc49a-cd5e-49bc-a1ac-a2410acc412b`). Incline and finite stairs then hit
provider rate limits (`7c6068ef-fe8a-4a5d-8df5-67d9c7912fef` and
`01035bd9-8eb8-443a-b0c8-81973f157149`). Further calls were stopped; missing-speed
and drag cases were not rerun with this final candidate. They passed the preceding
short-prompt run. The live gate remains NOT READY, not 6/6 passed. After quota
resets, rerun the complete six-case gate before beginning multi-object expansion.
