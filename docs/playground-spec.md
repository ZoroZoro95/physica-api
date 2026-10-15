# Physica Playground: Capability Specification

Date: 2026-10-15
Status: proposed product scope; current capabilities checked against source.
This document does not claim the proposed features are implemented.

## 1. Purpose

A separate, physics-aware environment that AI can operate through validated API
calls. AI describes a scene using existing objects, motion models, events and
presentation instructions. The engine computes motion; the viewer renders it.

The playground is not an arbitrary-code generator, a second question-answering
LLM, or a promise to solve every JEE question. A reusable object catalogue alone
cannot provide that coverage: constraints, reference frames and event conditions
must also be supported and tested.

The manual viewer is for inspection and testing. It is not intended to replace
the student's question-to-solution experience with a scene-building task.

## 2. What Works Today

| Capability | Current boundary |
| --- | --- |
| Point particle | Position, launch speed and direction; displayed ball has no collision radius |
| Ground | Stationary, finite horizontal collision segment |
| Wedge | Stationary solid, rising or descending; extruded 3D appearance, XY physics |
| Launch | Angle from +x, outward surface normal, or left-to-right surface tangent |
| Release | Explicit zero initial speed |
| Motion | Constant downward gravity; no drag; stop at first surface contact |
| Multiple objects | Scene accepts several objects, but each simulation follows one selected particle |
| Readouts | Position, velocity, contact time and surface |
| Presentation | Trajectory, velocity/components/gravity labels, playback, scrub, pan/zoom and fit |
| Scene exchange | Validated JSON import/export and stateless command batches |

Current limits: 32 surfaces, 16 particles, 64 commands per batch, 1001 samples
and a 300-second simulation horizon. These are request limits, not proof of
multi-body support. The current viewer requests 501 samples over at most 30 s.

Not implemented: AI tool-calling integration, moving surfaces,
particle-to-particle collisions, sliding constraints, bounces, fragmentation,
symbolic solving, or production access control.

## 3. Object Catalogue

Names such as stone, ball and marble should normally use the same particle
model. A different appearance must not silently introduce rolling or rotation.

| Object / primitive | What we should be able to do | Phase |
| --- | --- | --- |
| Particle / ball / stone | Place, release, launch, prescribe valid motion, track position and velocity | Current ballistic subset; expand in B |
| Ground / horizontal platform | Set height and finite extent; detect arrival, departure and clearance | Ground current; platform semantics in A |
| Wedge / inclined plane | Set signed slope and dimensions; launch relative to its tangent/normal; intersect trajectory | Stationary wedge current; sliding in C |
| Staircase | Set rise, run, count, origin and direction; identify first struck tread/riser/corner | A |
| Wall / tower / cliff / ledge | Build finite boundaries with a top and edge; test impact or clearance | A |
| Target / gate / reference point | Set position or opening; measure hit, miss and clearance without inventing a solid | A |
| Multiple particles | Independent starts, delayed launches, shared clock, separation and coincidence events | B |
| Car / train / runner | Particle or finite-length marker with prescribed 1D motion; crossing and overtaking | B |
| Lift / moving platform | Prescribed motion and moving reference frame; relative launch and contact | C |
| Boat / swimmer / river | Prescribed velocity relative to a uniform flow; ground-relative path and crossing | C |
| Rain / wind reference | Relative-velocity vectors; wind changes motion only through an explicit supported model | C |
| Circular-motion marker | Prescribed centre, radius and angular motion; tangent velocity and acceleration | C |
| Axes / ruler / angle / bracket / projection | Nonphysical measuring and explanation objects, attached to scene entities | A onward |

Tower, wall and staircase geometry should be compositions of reusable primitives,
not new question-specific solvers. Train length matters for crossing events, but
a decorative train mesh does not require wheel dynamics.

## 4. Actions and Physics Contract

### Scene construction

- Create a scene with explicit units, gravity and coordinate frame.
- Add, update or remove objects using stable IDs; validate dependent references.
- Place objects using coordinates or geometric relationships, not guessed labels.
- Specify angle reference and direction explicitly: horizontal, vertical, tangent
  or normal. Keep object IDs independent of labels such as P, Q, A and B.
- Preserve source provenance: supplied value, derived value, or illustrative choice.

### Motion

- A: ballistic motion and first contact against stationary geometry.
- B: rest, constant velocity, constant acceleration, delayed start and piecewise
  motion with explicit transition conditions on a shared timeline.
- C: uniform-flow relative motion, moving frames and prescribed circular motion.
- C: smooth-surface sliding as an explicit constrained model. Placing a particle
  on a wedge must never imply that constraint automatically.

Changing speed before a run changes the initial condition. Changing it during a
run requires a declared acceleration interval or velocity-change event; it must
not silently teleport the state. Playback speed changes viewing time, not physics.

### Measurements and events

Expose position, displacement, distance travelled, velocity, speed, acceleration,
elapsed time and components in a named basis. Add range, height and separation
only with a stated reference and interval.

Events should cover first contact, apex relative to a specified axis, target
crossing, equal positions, closest approach and entering/leaving a region.
Distinguish a point coincidence from physical collision with finite-size bodies.
Return no-event-within-horizon separately from an actual impossibility proof.

## 5. AI-to-Playground Flow

1. Extract entities, givens, unknowns, constraints and diagram relationships.
2. Resolve ambiguity or request clarification. Do not guess missing directions.
3. Select supported motion models and call typed scene operations.
4. Validate IDs, units, geometry, motion compatibility and resource limits.
5. Simulate and inspect events and measured quantities.
6. Build explanation beats referencing actual object IDs and computed results.
7. Validate those references, then render the explanation and full lifecycle.

The AI must not submit executable Python/JavaScript or arbitrary formulas for
evaluation. Unsupported models must return a useful limitation, not a visually
plausible substitute. Tool retries must be bounded and logged.

The question solver remains responsible for deriving unknowns. The playground
simulates specified states and verifies compatible results; simulation alone is
not a general symbolic solver. Unknown angles may use visibly labelled example
values for illustration, never values presented as the question's givens.

## 6. Viewer and Explanation Contract

- Full scene: one overall simulation, with a fixed, fitted camera by default.
- Explanation: at most two smaller inspection windows, each filtered to the
  intended object, axis or relationship. No duplicated full scenes.
- A beat declares its visual targets, labels, highlight state and motion interval.
  Static reasoning must not trigger a complete trajectory replay.
- Revealed annotations persist until explicitly hidden or superseded. Previously
  established quantities remain subdued; the current idea gets emphasis.
- Vector origins follow their owning object and use the same simulation clock.
  Initial-velocity arrows stay at launch and are labelled as initial quantities.
- Resolve vectors in the named basis: horizontal/vertical or tangent/normal.
  Labels must match the text, including u versus v and angle reference.
- Show a trajectory when it explains the vector context; suppress unrelated apex,
  reference and impact markers in component-only views.
- Use thin arrows, legible formula labels and a persistent parameter legend.
  Keep vector scale consistent within a comparison; disclose visual scaling.
- Layout must detect label collisions and clipping. Reposition labels with leader
  lines or move secondary values to the legend. Never silently hide a required label.
- Play, pause, replay beat, full lifecycle, scrub, speed, pan, zoom and reset view
  are separate controls. Collapsed inspection windows consume no diagram area.
- Use 3D geometry where it clarifies wedges/stairs; planar motion does not require
  camera rotation. Genuine motion across an inclined surface needs a plane-local
  two-dimensional model, not the current side-view wedge model.

## 7. Delivery and Acceptance Gates

| Phase | Deliverable | Required evidence before calling it supported |
| --- | --- | --- |
| A: complete stationary projectile scene | Stairs, walls, platforms, targets; AI adapter for these and existing wedges | Text and image cases build via API; numerical contacts agree with analytical checks; rendered geometry matches collision geometry |
| B: general linear and relative kinematics | Shared timeline, multiple bodies, delayed starts, prescribed motion and events | Overtaking, delayed interception, vertical meeting and finite-train crossing tests; matched clocks and independent inspection views |
| C: explicit extended models | Moving frames, flow, circular motion and smooth-surface constraints | Independent reference solutions for each model; reject incompatible combinations; verify velocities in the requested frame |
| Integration | Solver + explanation + viewer consume the same scene/result | Correct unknowns, no invented givens, valid beat references, persistent labels, static versus moving beats verified |
| Public readiness | Protected API and reproducible deployment | Authentication/ownership policy, request limits, timeouts, error reporting and deployment smoke tests |

For every model, test changed numbers, renamed objects, mirrored directions,
different origins, boundary cases and unsupported inputs. DPP matches alone are
not a generalisation test. Keep a held-out question set with diagrams.

Visual acceptance requires desktop/mobile screenshots, no clipped or overlapping
required labels, correct vector attachment through playback, visible contact,
and identical physics when annotations are toggled. API acceptance requires
deterministic results and contact accuracy independent of rendering sample count.

## 8. Explicit Exclusions

Do not include friction dynamics, rolling, rigid-body rotation, ropes/pulleys,
springs, drag, restitution-based bouncing or fragmentation in the initial scope.
They require additional physical models, not just extra objects. In particular,
an explosion problem needs momentum/event rules beyond kinematics.

Do not advertise "all kinematics" until the agreed model matrix and held-out tests
pass. Even then, disclose the supported assumptions and reject unsupported mixtures.

## 9. Next Concrete Milestone

Finish Phase A as an end-to-end slice: AI creates a staircase scene through the
API, launches a particle, identifies the first contact, and displays that same
contact in the viewer. Verify changed step dimensions, speed, origin and mirrored
direction. This proves reusable scene construction, not another hardcoded answer.

## 10. Implementation Checkpoint: 2026-10-15

Staircase support from Phase A is implemented in the API and separate viewer:
configurable rise, run, count and descent; tread/riser contact; mirrored geometry;
numerical and browser regression coverage. This supersedes the staircase row's
planned status. Phase A remains incomplete: the AI adapter, dedicated wall/target
primitives and extraction-to-scene integration are outstanding. There is no claim
of AI-generated scene acceptance yet.

Source audit: `core/playground/models.py`, `docs/playground-api.md`, and the split
frontend's `docs/playground-viewer.md`.
