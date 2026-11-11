# Independent multi-particle playback

The manual/import playground can now simulate all particles in a scene together.
This is not yet an interacting-body solver or a multi-body AI interpreter.

## Contract

`POST /v1/simulations/scene` accepts `scene`, `max_time` (0 < t <= 300 s),
and `samples` (2..1001 base samples per track). Exact encounter start/end states
are additionally inserted into participating tracks, so returned sample counts
may exceed this base count. The existing scene limit is 16 particles.
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

The atomic AI generator accepts up to four independent particles and explicit
launch schedules. Generated scenes remain review candidates, not certified
question interpretations. No sliding,
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

## Free-flight encounters

`POST /v1/simulations/scene` now also returns `encounters`. These are analytical
point-particle results, not intersections of sampled paths or rendered spheres.
Each entry has sorted `particle_ids`, `kind`, absolute `time`, `end_time`, and
the position at `time`.

- `meeting`: both particles occupy the same position at one instant;
  `end_time` equals `time`.
- `coincident`: both follow the same motion throughout their overlapping flight
  interval. `time` and `end_time` delimit that interval.
- Search starts only after both launches and stops at the earlier first surface
  contact or requested horizon, including endpoints. Waiting bodies and held
  impact markers are excluded.
- Equal gravity cancels in relative motion. The detector solves the remaining
  linear equation and verifies both coordinates, independent of sample count.
  Numerical equality uses a 1e-9 metre floor or 64 coordinate ULPs, whichever is
  larger; endpoint clamping is limited to 64 time ULPs.
- Results are sorted by time, then particle IDs. `interaction` remains
  `independent`: velocities and paths do not change at a meeting.

The playground lists these events under Free-flight meetings. Selecting a meeting
pauses and seeks to its exact time without changing particle selection or camera.
Moving-together intervals have separate start/end controls. Resimulation replaces
the event list, and single-particle scenes do not retain prior events. Older API
responses without the field show data unavailable, not a false no-meetings claim.
The AI interpreter does not implement collision response, closest approach,
and solving an unknown interception speed/angle are not implemented.

Run `python scripts/regress_playground_encounters.py` for encounter checks,
including 100 seeded constructed meetings with varied gravity, speed, position
and launch time. The web audit `node scripts/audit-playground-encounters.mjs`
checks exact rendered positions, pause/resume, camera and selection preservation,
reset, changed schedules, interval navigation and desktop/mobile layout. Screenshots
and reports are saved in `/tmp/physica-encounters`.

2026-11-10 checkpoint: 94 backend tests, encounter/ensemble/delayed-launch
desktop-mobile browser audits, and frontend production build passed. No live
AI-provider suite or deployment was run for this UI integration.

## AI recipe boundary

The existing `build_and_simulate` recipe now accepts optional `launches`, each
containing `particle_id` and absolute `launch_time`. Missing entries default to
zero. Duplicate schedules, unknown particles, invalid times and more than four
particles reject the entire candidate. The selected particle must exist. Multi-body
recipes currently require finite geometry; continuing staircase expansion remains
single-particle only. The older staged tool workflow remains single-particle.

Generation returns the selected `simulation`, the complete `ensemble` when there
are multiple particles, and the original `max_time`. The UI retains that horizon
when editing annotations and rejects incomplete ensembles without replacing the
previous scene. Reports retain all schedules, tracks and API operations.

Review every source value and assumption. Schema validation and the physics
engine cannot prove that an LLM interpreted arbitrary text correctly. Unknown
launch speeds/angles requiring inverse solving and collision response remain
outside the prompt's supported scope. Next: broaden live interpretation coverage
before claiming general multi-body question support.

2026-11-11 acceptance: 96 offline backend tests and desktop/mobile generation UI
checks passed. Live delayed-launch and two-particle source-value checks, plus
collision-response refusal, passed. The two-particle checker initially incorrectly
expected both particles to land by t=4; Q launches at t=1 and lands at 4.16227766 s.
The original saved response passed the corrected checker without another model
call. An additional level-ground live check was rate-limited by Groq; the full
nine-case provider suite has not passed on this prompt. No deployment performed.
