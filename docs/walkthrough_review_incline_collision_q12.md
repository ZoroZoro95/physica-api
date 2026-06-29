# Walkthrough Review: Incline Collision Q12

Generated on: 2026-06-08

Purpose: store the current walkthrough and animation instructions for review. This is not a target design. It is the current output we need to critique and improve.

## Input

Question:

```text
A particle P is projected from a point on the surface of smooth inclined plane. Simultaneously another particle Q is released on the smooth inclined plane from the same position. P and Q collide after t = 4 second. The speed of projection of P is:
```

Diagram facts supplied to solver:

```json
{
  "present": true,
  "type": "incline",
  "entities": [
    {
      "id": "inclined_surface",
      "kind": "incline",
      "label": "incline",
      "description": "smooth inclined plane",
      "confidence": 0.9
    },
    {
      "id": "incline_angle",
      "kind": "angle",
      "label": "incline angle",
      "value": "60",
      "unit": "deg",
      "description": "incline angle with horizontal",
      "confidence": 0.9
    }
  ]
}
```

## Solver Result

```text
status: passed
engine_case: projectile_collides_with_sliding_particle_on_incline
answer: 10 m/s
```

Givens used:

```text
time=4s
incline=60deg
g=10m/s^2
```

Trace:

```text
1. Take axes along the plane and normal to the plane. From the diagram, P is projected normal to the 60deg incline and Q is released from rest on it.
2. Along the plane, both particles have zero initial along-plane velocity and the same acceleration g sin(alpha), so their along-plane positions remain equal.
3. Normal to the plane, Q stays on the plane, so n_Q = 0. Projectile P has n_P = ut - (1/2)g cos(alpha)t^2.
4. Collision requires n_P = 0 at t = 4s, so u = (g cos(alpha)t)/2.
5. u = (10 cos(60deg) x 4)/2 = 10 m/s.
```

## Equation Plan

Goal:

```text
Find the speed with which P must be projected so that it collides with Q on the smooth incline.
```

Invariant:

```text
Resolve motion along the incline and normal to the incline. Collision requires both along-plane and normal separation to be zero at the same time.
```

Steps:

| id | title | equation | substitution | explanation | focus_ids |
|---|---|---|---|---|---|
| read_diagram | Read the diagram condition | P is projected normal to the incline; Q is released on the incline |  | The missing physics is in the figure: P starts perpendicular to the plane, while Q starts from rest and remains constrained to the smooth plane. | point:launch, surface:inclined_plane, incline:normal_axis, actor:projectile_p, actor:slider_q |
| along_plane | Check motion along the plane | s_P = 1/2 g sin(alpha)t^2, s_Q = 1/2 g sin(alpha)t^2 | Both particles start with zero along-plane velocity, so after 4s their along-plane displacement is identical. | Along the incline, P and Q have the same acceleration component g sin(alpha). This direction does not determine u; it only confirms they stay aligned along the plane. | surface:inclined_plane, incline:tangent_axis, trajectory:p, trajectory:q |
| normal_plane | Write normal separation | n_P = ut - 1/2 g cos(alpha)t^2, n_Q = 0 | Q stays on the plane, so only P's normal displacement must be brought back to zero. | Normal to the incline, P first moves away from the plane with speed u, while gravity pulls it back with component g cos(alpha). | incline:normal_axis, actor:projectile_p, trajectory:p, point:collision |
| collision_condition | Apply collision condition | 0 = ut - 1/2 g cos(alpha)t^2 | At collision, P is back on the plane at the same point as Q. | Set normal separation to zero. The root t = 0 is the launch instant; the given nonzero collision time gives u. | point:collision, event:collision, trajectory:p, trajectory:q |
| solve_u | Solve for projection speed | u = g cos(alpha)t / 2 | u = 10 cos(60deg) x 4 / 2 = 10 x 0.5 x 4 / 2 | Now substitute the incline angle and collision time. | quantity:u, point:collision, event:collision |
| answer | State the answer | u = 10 m/s |  | The speed of projection of P is 10 m/s. | answer, quantity:u, actor:projectile_p |

Final answer:

```text
10 m/s
```

Exam takeaway:

```text
For this setup, the along-plane motion is already synchronized; the speed is fixed by the normal-to-plane return condition.
```

## Walkthrough Steps Returned

### invariant

Title: Given and what to find

Student goal:

```text
Understand what the question is really asking before calculating.
```

Teaching goal:

```text
Understand what the question is really asking before calculating.
```

Concept used:

```text
Resolve motion along and normal to the inclined plane.
```

Explanation:

```text
Find the speed with which P must be projected so that it collides with Q on the smooth incline. Resolve motion along the incline and normal to the incline. Collision requires both along-plane and normal separation to be zero at the same time.
```

Visual action:

```text
show_full_scene
```

Focus/highlight:

```text
point:launch
surface:inclined_plane
incline:normal_axis
incline:tangent_axis
actor:projectile_p
actor:slider_q
```

### read_diagram

Title: Read the diagram condition

Teaching goal:

```text
Extract the hidden condition from the diagram: P is launched normal to the plane and Q stays on the plane.
```

Formula/equation:

```text
P is projected normal to the incline; Q is released on the incline
```

Explanation:

```text
The missing physics is in the figure: P starts perpendicular to the plane, while Q starts from rest and remains constrained to the smooth plane.
```

Visual action:

```text
show_incline_axes
```

Camera targets:

```text
setup
surface:inclined_plane
incline:normal_axis
incline:tangent_axis
```

### along_plane

Title: Check motion along the plane

Teaching goal:

```text
Show why the along-plane motion of P and Q stays synchronized.
```

Formula/equation:

```text
s_P = 1/2 g sin(alpha)t^2,  s_Q = 1/2 g sin(alpha)t^2
```

Substitution/calculation:

```text
Both particles start with zero along-plane velocity, so after 4s their along-plane displacement is identical.
```

Explanation:

```text
Along the incline, P and Q have the same acceleration component g sin(alpha). This direction does not determine u; it only confirms they stay aligned along the plane.
```

Visual action:

```text
compare_incline_motion
```

Camera targets:

```text
surface:inclined_plane
incline:tangent_axis
trajectory:p
trajectory:q
```

### normal_plane

Title: Write normal separation

Teaching goal:

```text
Use normal separation to turn the collision event into an equation for u.
```

Formula/equation:

```text
n_P = ut - 1/2 g cos(alpha)t^2,  n_Q = 0
```

Substitution/calculation:

```text
Q stays on the plane, so only P's normal displacement must be brought back to zero.
```

Explanation:

```text
Normal to the incline, P first moves away from the plane with speed u, while gravity pulls it back with component g cos(alpha).
```

Visual action:

```text
show_normal_return
```

Camera targets:

```text
incline:normal_axis
trajectory:p
point:collision
```

### collision_condition

Title: Apply collision condition

Teaching goal:

```text
Use normal separation to turn the collision event into an equation for u.
```

Formula/equation:

```text
0 = ut - 1/2 g cos(alpha)t^2
```

Substitution/calculation:

```text
At collision, P is back on the plane at the same point as Q.
```

Explanation:

```text
Set normal separation to zero. The root t = 0 is the launch instant; the given nonzero collision time gives u.
```

Visual action:

```text
highlight_collision
```

Camera targets:

```text
point:collision
event:collision
```

### solve_u

Title: Solve for projection speed

Teaching goal:

```text
Substitute the collision time and incline angle without skipping the algebra.
```

Formula/equation:

```text
u = g cos(alpha)t / 2
```

Substitution/calculation:

```text
u = 10 cos(60deg) x 4 / 2 = 10 x 0.5 x 4 / 2
```

Explanation:

```text
Now substitute the incline angle and collision time.
```

Visual action:

```text
highlight_collision
```

Camera targets:

```text
point:collision
event:collision
```

### answer

Title: State the answer

Teaching goal:

```text
Report the required projection speed of P.
```

Formula/equation:

```text
u = 10 m/s
```

Explanation:

```text
The speed of projection of P is 10 m/s.
```

Visual action:

```text
highlight_final_answer
```

Camera targets:

```text
answer
quantity:u
actor:projectile_p
```

## Animation Storyboard Returned

| step_id | visual_action | camera | visible_vectors | overlays | visual_focus |
|---|---|---|---|---|---|
| invariant | show_full_scene | full_scene | __none__ | show_trajectory | point:launch, surface:inclined_plane, incline:normal_axis, incline:tangent_axis, actor:projectile_p, actor:slider_q |
| read_diagram | show_incline_axes | full_scene | incline:tangent_axis, incline:normal_axis | show_trajectory, show_motion_progress | point:launch, surface:inclined_plane, incline:normal_axis, actor:projectile_p, actor:slider_q |
| along_plane | compare_incline_motion | full_scene | incline:tangent_axis, incline:normal_axis | show_trajectory, show_motion_progress | surface:inclined_plane, incline:tangent_axis, trajectory:p, trajectory:q |
| normal_plane | show_normal_return | collision | *:v, *:a, incline:normal_axis, incline:tangent_axis | show_trajectory, show_motion_progress, show_timer | incline:normal_axis, actor:projectile_p, trajectory:p, point:collision |
| collision_condition | highlight_collision | collision | *:v, *:a, incline:normal_axis | show_trajectory, show_motion_progress, show_timer | point:collision, event:collision, trajectory:p, trajectory:q |
| solve_u | highlight_collision | collision | *:v, *:a, incline:normal_axis | show_trajectory, show_motion_progress, show_timer | quantity:u, point:collision, event:collision |
| answer | highlight_final_answer | setup | __none__ | show_trajectory | answer, quantity:u, actor:projectile_p |

## Animation Quantities Returned

```json
{
  "u": {"value": 10.000000000000002, "unit": "m/s", "label": "u_P"},
  "theta": {"value": 30.00000000000001, "unit": "deg", "label": "theta"},
  "alpha": {"value": 60.0, "unit": "deg", "label": "alpha"},
  "g": {"value": 10.0, "unit": "m/s^2", "label": "g"},
  "ux": {"value": 8.660254037844387, "unit": "m/s", "label": "u_x"},
  "uy": {"value": 5.000000000000002, "unit": "m/s", "label": "u_y"},
  "T": {"value": 4.0, "unit": "s", "label": "t"},
  "R": {"value": 69.28203230275508, "unit": "m", "label": "s_Q"},
  "H": {"value": 77.45966966612251, "unit": "m", "label": "H"}
}
```

## Animation Events Returned

```json
[
  {"id": "event:launch", "time": 0.0, "point": "launch", "label": "P projected, Q released"},
  {"id": "event:apex", "time": 0.5000000000000002, "point": "apex", "label": "P apex"},
  {"id": "event:collision", "time": 4.0, "point": "collision", "label": "P and Q collide"}
]
```

## Initial Critique Notes

These are obvious review flags from the current output:

- `student_goal` is still generic in several steps.
- `voiceover_text` reads mechanically and is not teacher-like.
- `animation_scene_steps.concept_used` still falls back to generic `projectile model` / `component trigonometry`.
- `answer` camera target goes to `setup`, which may not be the right visual moment.
- `theta`, `ux`, `uy`, `R`, and `H` are present in animation quantities even though the teaching path is about tangent/normal separation. These may distract unless hidden from the default legend.
- Storyboard uses actions like `show_normal_return`, but the renderer may not yet have a real visual primitive for normal separation.
- The current contract is closer than before, but it is still not a proper Khan-style narrative.
