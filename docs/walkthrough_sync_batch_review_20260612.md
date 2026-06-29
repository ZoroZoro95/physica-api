# Walkthrough Sync Batch Review - 2026-06-12

Batch artifacts:

`questions/walkthrough_sync_reviews/20260612T113429Z`

Images reviewed:

1. Staircase direct-hit question
2. Incline maximum-normal-distance velocity component
3. Two-incline perpendicular launch/impact
4. Smooth incline, velocity perpendicular to greatest slope
5. Incline right-angle impact condition

## Executive Finding

The current system solves these samples, but it is not yet a teacher-quality explainer. The main failure is architectural: walkthrough semantics and animation semantics are not generated from the same beat contract.

Right now:

- `walkthrough.explainer_beats` says what to teach.
- `animation_scene_spec.storyboard` separately guesses what to show.
- The frontend tries to interpret both with loose IDs such as `trajectory:path`, `quantity:R`, `*:a`, and broad visual actions like `focus_relevant_step`.

That is why the result feels unsynced even when the math answer is correct.

## Batch Result

| Case | Extraction | Solver | Engine | Answer | Main failure |
|---|---|---|---|---|---|
| Q01 staircase | ok | passed | `staircase_collision` | `21st` | local beats still play broad trajectory; no step-face-specific animation primitive |
| Q02 max normal distance | ok, low confidence | passed | `inclined_plane_max_normal_distance_velocity_component` | `zero` | asks for normal component, animation highlights range/landing; resolved gravity labels missing |
| Q03 two inclines | ok | passed | `two_inclines_perpendicular_launch_impact` | `10 m/s` | explanation uses generic component text; animation is not tied to OA/OB/right-angle geometry |
| Q04 smooth incline | ok | passed | `motion_on_smooth_incline_perpendicular_to_slope` | `10.0109 m/s` | animation world incorrectly becomes `level_ground`; this is a hard geometry failure |
| Q05 right-angle impact | ok | passed | `inclined_plane_right_angle_impact_condition` | `cot theta = 2 tan alpha` | event condition is not visually represented as final along-plane velocity becoming zero |

## Cross-Cutting Failures

### 1. Animation is not generated from explainer beats

Example from Q02:

- Beat says: maximum normal displacement means normal velocity is zero.
- Storyboard says: `highlight_range`, `quantity:R`, `point:landing`, `trajectory:path`.

This is not a small UI bug. The animation is showing a different semantic object from the beat.

Required change:

Every explainer beat must own a `visual_plan` that the animation consumes directly. The scene storyboard should be derived from beats, not rebuilt independently from equation-plan text.

### 2. Resolved vectors are not real first-class objects

The scene has generic vectors:

- `projectile:v`
- `projectile:vx`
- `projectile:vy`
- `projectile:a`
- `incline:tangent_axis`
- `incline:normal_axis`

But beat text talks about:

- `g sin(alpha)`
- `g cos(alpha)`
- normal velocity
- along-plane velocity
- final along-plane velocity

Those are not modeled as explicit labeled vectors. The frontend cannot label something that does not exist as a semantic vector.

Required change:

Add explicit vector primitives to `AnimationSceneSpec`, for example:

```json
{
  "id": "gravity:tangent_component",
  "actor": "projectile",
  "kind": "component",
  "component": "gravity_tangent",
  "label": "g sin alpha",
  "role": "gravity component along incline",
  "anchor": "launch",
  "direction_ref": "incline:tangent_axis"
}
```

and:

```json
{
  "id": "velocity:normal_component",
  "label": "v_n",
  "role": "velocity component normal to incline"
}
```

### 3. Labels are a data problem, not just a CSS problem

The label renderer can be improved, but the current data often only says `*:a` or `*:v`. There is no instruction that the visible label should be `g sin alpha` or `v_parallel = 0`.

Required change:

Beat visual plans should include `labels_to_show`:

```json
[
  {
    "target_id": "gravity:tangent_component",
    "text": "g sin alpha",
    "placement": "above_arrow",
    "priority": 1
  }
]
```

### 4. Teacher text is still formula-plan text

Bad examples found:

- "This equation is used because it links the highlighted geometry to impact speed."
- "Now substitute the known values and report only the requested quantity."
- Repeated generic component-resolution text across unrelated incline problems.

This sounds generated from metadata, not taught from the physical idea.

Required change:

Each beat needs a real `learner_message` and `board_lines`, not a stitched message from equation title + formula.

Minimum teacher beat shape:

```json
{
  "beat_type": "event_condition",
  "learner_message": "At the farthest point from the incline, the ball stops moving away from the incline for an instant. So the normal component of velocity is zero here.",
  "board_lines": ["v_n = 0"],
  "visual_plan": {
    "show": ["incline", "normal_axis", "velocity:normal_component"],
    "highlight": ["velocity:normal_component"],
    "label": [{"target_id": "velocity:normal_component", "text": "v_n = 0"}],
    "motion": "freeze_at_max_normal_distance"
  }
}
```

### 5. Some solved cases have wrong scene family

Q04 is the clearest failure:

- Extracted/solver engine: `motion_on_smooth_incline_perpendicular_to_slope`
- Animation scene world: `level_ground`

This invalidates any walkthrough sync, because the scene geometry is wrong before teaching starts.

Required change:

Add a hard validation gate:

- If `engine_case` is incline-specific, scene world must be `incline`, `incline_3d`, or another explicit incline world.
- If this validation fails, do not show animation. Return "animation scene unsupported for this solved case" instead of showing a fake level-ground arc.

### 6. Takeaway beat is not in animation storyboard

All five audits show:

`Exam takeaway: no storyboard step with step_id='takeaway'`

This creates a dangling explainer beat with no visual pair.

Required change:

Either include takeaway in storyboard as `highlight_final_answer`, or keep takeaway purely textual and mark it as `visual_plan.type = "text_only"` so the UI does not expect animation sync.

## New Contract Direction

The old contract:

```text
EquationPlan -> Walkthrough
EquationPlan -> AnimationSceneSpec
UI tries to sync by step_id
```

The required contract:

```text
Question + diagram semantics
  -> solved physics model
  -> TeachingBeat[]
       each beat has text + board + visual_plan
  -> AnimationSceneSpec generated from TeachingBeat.visual_plan
  -> UI renders text and animation from same beat
```

## Minimum Beat Visual Plan

```json
{
  "beat_id": "normal_velocity_zero",
  "beat_type": "event_condition",
  "scene_phase": "max_normal_distance",
  "show_ids": ["surface:inclined_plane", "incline:normal_axis", "velocity:normal_component"],
  "hide_ids": ["range", "apex", "future_result"],
  "highlight_ids": ["velocity:normal_component"],
  "motion": {
    "mode": "freeze",
    "event": "max_normal_distance"
  },
  "vectors": [
    {
      "id": "velocity:normal_component",
      "label": "v_n = 0",
      "style": "yellow_blink"
    }
  ],
  "labels": [
    {
      "target_id": "velocity:normal_component",
      "text": "v_n = 0"
    }
  ],
  "board_lines": ["v_n = 0"],
  "camera": "full_scene"
}
```

## Implementation Order

1. Add `TeachingBeat.visual_plan` schema and preserve old fields for compatibility.
2. Generate animation storyboard from `explainer_beats[*].visual_plan`, not from a separate `_scene_steps` pass.
3. Add semantic vector primitives: gravity tangent/normal, velocity tangent/normal, final velocity tangent/normal, displacement along/normal.
4. Add scene-family validation so incline engine cases cannot fall back to level-ground animation.
5. Replace generic component-resolution reveal generation with beat-type-specific reveal templates.
6. Upgrade renderer labels only after the data contains real labels like `g sin alpha`, `g cos alpha`, `v_parallel = 0`.

## Acceptance Gate For Next Iteration

For these five images, a pass means:

- no solved case uses the wrong scene world,
- every explainer beat has a paired visual plan or is explicitly text-only,
- no static teaching beat uses full trajectory as a substitute,
- every mentioned vector/component appears as a labeled vector primitive,
- no beat contains "This equation is used because it links..." or "Now substitute..." as its main teaching sentence,
- Q02 visually freezes at maximum normal distance and labels `v_n = 0`,
- Q04 renders an incline-plane/smooth-plane scene, not level ground.
