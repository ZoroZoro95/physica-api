# Independent multi-particle playback

The manual/import playground can now simulate all particles in a scene together.
This is not yet an interacting-body solver or a multi-body AI interpreter.

## Contract

`POST /v1/simulations/scene` accepts `scene`, `max_time` (0 < t <= 300 s),
and `samples` (2..1001 per track). The existing scene limit is 16 particles.
Every particle must have an explicitly set launch, including speed zero for a
release. Empty scenes or any invalid particle reject the whole request.

All launches occur at shared time zero under the scene's downward gravity.
Each track uses the existing analytical first-surface-contact solver. The result
contains scene ID/revision, `interaction: independent`, tracks keyed by
`particle_id`, and a duration equal to the latest track endpoint. If a flight
has no contact before `max_time`, its endpoint is that horizon.

The viewer interpolates these returned tracks at one common time. At first
contact, a particle becomes an impact marker while other flights continue.
The retained velocity is the incoming impact velocity, NOT a claim of zero
velocity or continued motion after contact. The UI labels those readouts and
hides that marker's moving vectors after impact.

Measurements may reference final contact anchors from different particles.
These are distances between their impact locations, not instantaneous relative
displacement. Missing contacts remain unavailable, never guessed.

## UI behavior

- Add particle appends an explicitly positioned, angled launch to the current
  manual/imported scene and resets playback to zero.
- Particle selection changes inspected readouts/annotations, not time or camera.
- Every track remains visible, with a particle label and matching legend color.
- Invalid additions preserve the last valid scene and playback state.
- Import/export retains particles and annotations; importing rebuilds all tracks.
- Existing single-particle API and generation results remain compatible.

The AI generator still rejects multi-body questions. No delayed launch, sliding,
fragmentation, inter-particle collision detection/response or interception solving
is implied. Crossing paths currently pass through one another as independent
point particles; the UI explicitly states this limitation.

## Verification

Run `python -m unittest discover -s scripts -p 'regress_playground_*.py'`.
The ensemble tests compare with the original single-particle endpoint and
independent analytical expectations, including mirrored/translated scenes,
different contact times, finite horizons, immediate contacts, cross-particle
contact measurements and atomic rejection of invalid input.

From the web repository with both local services running:

```sh
node scripts/audit-playground-ensemble.mjs
node scripts/audit-playground.mjs
```

The ensemble audit checks desktop/mobile motion, pause/scrub, unchanged camera
and time on selection, particle-specific vectors, nonblank rendering, label
clipping/overlap, adding a third particle, and preservation after invalid input.
It also checks that an addition preserves a generated scene's finite horizon.
Screenshots are written to `/tmp/physica-ensemble`. At this checkpoint all 74
backend test methods, frontend type checking/build, and both browser audits
passed. A single-particle label check failed once while a production build ran
concurrently; two isolated reruns passed. Run builds and visual audits separately
to avoid dev-output and rendering contention; this is not a universal layout
guarantee for arbitrary scenes.

Next: add explicit launch timing and mathematically verified encounter events
before exposing multi-body recipes to the AI interpreter. Do not infer collision
response from overlapping rendered spheres.
