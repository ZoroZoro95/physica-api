# Explainer Mode Contract

This document defines the target teaching flow for projectile-motion solutions. It is intentionally product-facing and implementation-facing, but it is not code.

## Core Decision

We will support two solution modes:

1. Explainer Mode
2. Complete Mode

Both modes use the same underlying physics scene, actors, trajectories, quantities, and formulas. The difference is presentation.

## Explainer Mode

Explainer Mode is the guided tutor experience.

The learner should feel that the AI is saying:

> Look at this part of the diagram. This quantity changes. This part stays the same. Now watch the animation change. That is why this equation appears.

The UI should feel like a ChatGPT-style explanation, not a block of step cards.

### UI Behavior

- Text appears one beat at a time.
- A button like `Ahead` moves to the next beat.
- Previous explanation text stays visible above.
- New explanation appears below previous explanation.
- Animation updates in sync with the newest beat.
- The learner can pause and inspect the animation.
- The camera stays fixed in a suitable full-scene view unless the user manually zooms or pans.
- No forced camera cuts between steps.
- No `Step 1`, `Step 2` block UI.
- No right-side list showing all future steps at once.

### Animation Behavior

The animation should change calmly and visibly per beat.

Each beat should define:

- what appears
- what changes
- what is highlighted
- what formula appears, if any
- what the learner should notice

The animation should not show irrelevant quantities. For example, in an incline collision problem, do not show apex, range, `u_x`, `u_y`, or landing unless the beat requires them.

## Complete Mode

Complete Mode is the reference solution experience.

### UI Behavior

- Full solution is visible at once.
- It should look like a clean solution manual.
- User can click `Show animation`.
- Animation runs as full lifecycle playback.
- User can pause, replay, scrub, zoom, and inspect.

Complete Mode is not the guided tutor. It is for students who want the whole answer and the full animation available immediately.

## Shared Scene Principle

Explainer Mode and Complete Mode must use the same underlying physics scene.

```text
same actors
same surfaces
same trajectories
same quantities
same events
same formulas
same final answer
```

Only the teaching layer changes.

```text
Explainer Mode = beat-by-beat reveal
Complete Mode = full solution + full animation
```

## Explainer Beat Schema

The main generated object should be `explainer_beats`.

Each beat should answer four questions:

1. What should the learner look at?
2. What changes in the animation?
3. Why does that change matter?
4. What equation appears, if any?

Suggested schema:

```json
{
  "id": "split_gravity",
  "learner_message": "The trick is to use axes along and perpendicular to the plane.",
  "visual_instruction": "Show gravity downward, then split it into components along and normal to the incline.",
  "animation_phase": "gravity_split",
  "show_objects": ["incline", "particle_p", "particle_q", "gravity_vector"],
  "hide_objects": ["apex", "range_marker", "landing_marker"],
  "highlight_objects": ["gravity_vector", "g_parallel", "g_normal"],
  "formula": "g_parallel = g sin 60°, g_normal = g cos 60°",
  "why_it_matters": "The along-plane component controls sliding, while the normal component controls when P returns to the plane."
}
```

## Narration Rules

Narration should sound like a calm teacher, not a generated solution template.

Bad:

```text
Apply collision condition.
```

Good:

```text
At collision, P has returned to the plane. So its perpendicular displacement must be zero.
```

Bad:

```text
Use relation to find projection speed.
```

Good:

```text
Now that we know P must return to the plane after 4 seconds, we can solve for the launch speed.
```

Rules:

- Use short sentences.
- Explain why the equation is chosen before showing it.
- Do not dump all formulas at once.
- Do not use generic labels like `Apply formula`, `Compute answer`, or `Use relation`.
- Do not say “obviously”.
- Do not skip the visual reason for an equation.
- Use the same symbols seen in the problem whenever possible.
- Keep variables readable: `u`, `g sin 60°`, `g cos 60°`, `t = 4 s`.

## Beat Granularity Rule

Explainer beats should use baby steps, but not microscopic steps.

Each beat should contain:

- one main visual idea
- one main reasoning idea
- one equation family at most

A beat may have small internal reveals. For example, a gravity-splitting beat can reveal gravity first, then axes, then one component, then the other component. These are sub-reveals inside one beat, not four separate learner steps.

Do not create a separate beat for every algebra line unless the algebra line changes the physical idea. The learner should feel guided, not interrupted.

## Formula Beat Rules

Formula beats must show how an equation is born from the physics, not jump straight to the final derived form.

Required order:

1. State the parent equation.
2. State the axis or direction where it is being used.
3. State why each term is kept, removed, or signed positive/negative.
4. Substitute known values line by line.
5. Connect the equation back to the visible animation.

Example pattern:

```text
Parent equation:
s = ut + 1/2 at²

Normal to the plane:
s_normal = 0 at collision because P has returned to the plane.
u_normal = u because P was launched perpendicular to the plane.
a_normal = -g cos 60° because gravity pulls P back toward the plane.

So:
0 = ut - 1/2 g cos 60° t²
```

Validation should reject a formula beat that starts directly with:

```text
0 = ut - 1/2 g cos 60° t²
```

unless the parent equation and substitutions were shown immediately before it.

## Vector Resolution Rules

Vector resolution must unfold progressively.

Required visual order:

1. Show the original vector first, for example gravity `g` downward.
2. Show the chosen axes, for example along-plane and normal-to-plane axes.
3. Reveal one component arrow.
4. Label that component.
5. Reveal the second component arrow.
6. Label that component.

For an incline of angle `alpha`:

```text
normal component = g cos alpha
along-plane component = g sin alpha
```

The explanation should include why:

```text
The normal axis is tilted by the same angle alpha from vertical, so gravity's projection into the plane is g cos alpha.
The remaining component along the plane is perpendicular to that normal component, so it is g sin alpha.
```

The exact wording can be shorter in the UI, but the generated reasoning must contain this idea.

## Animation Rules

The animation should be a teaching object, not decoration.

Rules:

- Keep fixed full-scene camera by default.
- Make the important visual change per beat.
- Highlight only what matters for the current beat.
- Hide irrelevant markers.
- Avoid showing every computed quantity in the legend.
- Do not show apex/range/landing unless the problem or beat needs them.
- Show formulas near the relevant visual object when possible.
- Use clean 2D-style arrows for vectors, even inside 3JS.
- Labels should be short: `P`, `Q`, `g`, `g sin 60°`, `g cos 60°`, `u`.

## Example: Incline Collision Problem

Question:

```text
A particle P is projected from a point on the surface of smooth inclined plane. Simultaneously another particle Q is released on the smooth inclined plane from the same position. P and Q collide after t = 4 second. The speed of projection of P is:
```

Diagram facts:

```text
incline angle = 60°
P is projected perpendicular to the plane
Q is released on the plane
P and Q start from the same point
```

Final answer:

```text
10 m/s
```

### Beat 1: Setup

Learner message:

```text
Both particles start from the same point. Q is released, so it slides down the smooth plane. P is projected perpendicular to the plane.
```

Visual instruction:

```text
Show a 60° inclined plane. Place P and Q at the same point. Show Q on the plane and show P's launch arrow perpendicular to the plane.
```

Formula:

```text
None
```

Highlight:

```text
P, Q, incline, perpendicular launch arrow
```

### Beat 2: Split Gravity

Learner message:

```text
The trick is to use axes along and perpendicular to the plane.
```

Visual instruction:

```text
Show gravity downward first. Then draw the along-plane and normal axes. Reveal g cos 60° into the plane, then reveal g sin 60° along the plane. Each component arrow should appear one by one, with its label appearing only after the arrow is visible.
```

Formula:

```text
normal component = g cos 60°
along-plane component = g sin 60°
g_parallel = g sin 60°
g_normal = g cos 60°
```

Resolution explanation:

```text
The normal to the plane is tilted by 60° from vertical, so gravity's projection into the plane is g cos 60°. The along-plane component is the complementary projection, so it is g sin 60°.
```

Highlight:

```text
gravity vector, along-plane component, normal component
```

### Beat 3: Along-Plane Motion

Learner message:

```text
Along the plane, both particles have the same acceleration: g sin 60°. So their along-plane positions are always the same.
```

Visual instruction:

```text
First highlight g sin 60° along the plane. Then animate Q sliding down the plane. Show P's shadow/projection on the plane moving exactly with Q.
```

Formula:

```text
Parent equation:
s = ut + 1/2 at²

Along the plane:
u_parallel = 0 for both particles
a_parallel = g sin 60° for both particles

s_P = 1/2 g sin 60° t²
s_Q = 1/2 g sin 60° t²
```

Highlight:

```text
Q, P's projection on plane, along-plane component
```

### Beat 4: Perpendicular Motion Of P

Learner message:

```text
So collision depends only on when P returns to the plane.
```

Visual instruction:

```text
Show P moving away from the plane, slowing down, then returning to the plane.
```

Formula:

```text
None
```

Highlight:

```text
P, perpendicular distance from plane
```

### Beat 5: Collision Equation

Learner message:

```text
At collision, P is back on the plane. That means its perpendicular displacement is zero.
```

Visual instruction:

```text
Highlight the collision point where P returns to the plane and meets Q.
```

Formula:

```text
Parent equation:
s = ut + 1/2 at²

Normal to the plane:
s_normal = 0 at collision
u_normal = u
a_normal = -g cos 60°

0 = ut - 1/2 g cos 60° t²
```

Highlight:

```text
collision point, perpendicular displacement
```

### Beat 6: Substitute

Learner message:

```text
Now substitute g = 10 and t = 4 seconds.
```

Visual instruction:

```text
Keep the collision point highlighted. Show the calculation next to the scene.
```

Formula:

```text
0 = ut - 1/2 g cos 60° t²
ut = 1/2 g cos 60° t²
u = 1/2 g cos 60° t
u = 1/2(10)(1/2)(4)
u = 10 m/s
```

Highlight:

```text
final answer
```

## Complete Mode Version

Complete Mode should present the same solution all at once:

```text
Given:
t = 4 s
alpha = 60°
g = 10 m/s²

Use axes along and perpendicular to the plane.

Along the plane:
s_P = 1/2 g sin alpha t²
s_Q = 1/2 g sin alpha t²

So along-plane motion is already matched.

Normal to the plane:
n_P = ut - 1/2 g cos alpha t²
n_Q = 0

At collision:
n_P = 0

0 = ut - 1/2 g cos alpha t²
u = 1/2 g cos alpha t
u = 1/2(10)(1/2)(4)
u = 10 m/s

Final Answer:
10 m/s
```

Complete Mode may show a `Show animation` button that runs the full lifecycle.

## Validation Rules

Generated explainer beats should fail validation if:

- A beat has no clear visual change.
- A beat has narration but no object to look at.
- A formula appears before the visual reason for it.
- The final answer appears before the key constraint is explained.
- The output uses generic phrases like `apply formula` or `use relation`.
- The animation includes irrelevant quantities by default.
- Camera instructions require step-specific camera cuts.
- Diagram-derived facts are used without being listed as diagram facts.
- A problem requiring a diagram constraint proceeds without extracting that constraint.
- A vector-resolution beat shows all component arrows and labels at once.
- A formula beat starts from a derived equation without first showing the parent equation.
- Substitution is skipped or compressed into a mental-calculation jump.

## Implementation Direction

The system should eventually generate:

```text
question_understanding
diagram_facts
physics_constraints
explainer_beats
complete_solution
animation_scene
```

The explainer beats should drive the UI and animation sync. The current `walkthrough steps`, `focus_ids`, and `storyboard` can become internal implementation details, but they should not be the main teaching contract.
