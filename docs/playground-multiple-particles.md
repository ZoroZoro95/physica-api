# Independent multi-particle playback

The manual/import playground can now simulate all particles in a scene together.
This is not yet an interacting-body solver or a multi-body AI interpreter.

## Contract

`POST /v1/simulations/scene` accepts `scene`, `max_time` (0 < t <= 300 s),
and `samples` (2..1001 per track). The existing scene limit is 16 particles.
Every particle must have an explicitly set launch, including speed zero for a
release. Empty scenes or any invalid particle reject the whole request.

Particles default to launch at shared time zero. Each particle may instead have
`launch_time` in [0, 300] seconds. Before launch it is held at its initial position
with zero actual velocity. Its configured velocity takes effect at launch; gravity
then acts over flight age, not the time spent waiting.
Each track uses the existing analytical first-surface-contact solver. The result
contains scene ID/revision, `interaction: independent`, tracks keyed by
`particle_id`, and a duration equal to the latest track endpoint. If a flight
has no contact before `max_time`, its endpoint is that horizon.

`max_time` is an absolute scene-time horizon. Sample and contact timestamps are
absolute too. A launch after the horizon returns `status: waiting`, no contact,
and stationary samples. At the horizon exactly, the initial flight state is
returned without advancing gravity. Invalid launch configurations still reject
the request even when the launch is outside the horizon.

`POST /v1/scenes/schedule` accepts `scene`, `particle_id`, and `launch_time`.
It returns a revised scene without mutating the supplied scene. Import/export
preserves launch times; old scene files default to zero.

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
- Set launch time edits the selected particle; New launch time schedules an
  added particle. Both rebuild tracks and reset playback while preserving the
  simulation horizon. Waiting particles show zero velocity and no moving vectors.

The AI generator still rejects multi-body and delayed-launch questions. Manual
scheduling is supported, but no sliding,
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
node scripts/audit-playground-launch-times.mjs
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

The scheduled-launch extension adds eight backend test methods (82 total),
covering time translation, waiting, exact horizon/contact boundaries, validation,
scene isolation and continuing staircase geometry. Its browser audit checks
waiting/release/impact, scrubbing, selection, scheduling, additions and export
at desktop/mobile sizes, with canvas and label checks. Reports are saved under
`/tmp/physica-launch-times`.

2026-10-30 checkpoint: all 82 backend tests, all three browser audits and the
frontend production build passed. The targeted live `delayed_launch` case returned
`unsupported` without a scene (report `df9ed79a-d131-4e9f-9edb-18b0034c3e72`).
The other six live-provider cases were not rerun for this checkpoint.

Next: add mathematically verified encounter events before exposing scheduled
multi-body recipes to the AI interpreter. Do not infer collision
response from overlapping rendered spheres.
