# Walkthrough Transcript Patterns

Source files:
- `transcript/cliff.txt`
- `transcript/theoryandquestions.txt`
- `transcript/random_question.txt`
- `transcript/pyqs_hindi.txt`

Purpose: extract reusable teaching patterns from strong explanations. These notes should guide the walkthrough engine, but should not copy transcript wording.

## Core Teaching Moves

### 1. Read And Classify The Problem

Good explanations first identify the problem family before solving.

Observed pattern:
- State what is given in the question.
- Identify whether it is same-height projectile, cliff/uneven height, horizontal launch, bounce, relative motion, graph/kinematics, etc.
- Say what is being asked before choosing equations.

Implementation requirement:
- Every walkthrough starts with a `problem_classification` move.
- The scene should highlight the full physical setup, not animate motion yet.
- The solution panel should show `Given` and `To Find` before equations.

### 2. Draw Or Reconstruct The Diagram First

The cliff transcript explicitly starts by drawing the cliff, ground, launch point, trajectory, axes, and origin before solving. The Hindi examples also keep reading the language while constructing the physical picture.

Implementation requirement:
- Step 1 camera target should be the entire scene bounds.
- Highlight launch point, ground/reference surface, axes, and requested measurement.
- If the question has an image, extracted diagram semantics should be shown as labels.
- If the question is text-only, generate a clean diagram from the model.

### 3. Define Coordinates And Sign Convention

Teachers spend time deciding x/y axes and positive direction. They also warn that sign choices can differ, but must stay consistent.

Implementation requirement:
- The walkthrough should display a small coordinate badge:
  - `+x`: right / along plane / chosen direction
  - `+y`: up / down / normal direction
  - `g`: direction and sign
- The scene should draw axis arrows before showing equations.
- Equations should use the chosen sign convention consistently.

### 4. Resolve Velocity Into Components

Both English projectile transcripts explain components visually with a right triangle and the adjacent/opposite rule. They also mention that cos/sin depends on where the angle is measured from.

Implementation requirement:
- Component step must zoom to the launch vector.
- Draw velocity vector `u`, component arrows `u_x`, `u_y`, and the angle arc.
- Formula should appear next to the arrows:
  - `u_x = u cos(theta)` if angle is from horizontal
  - `u_y = u sin(theta)` if angle is from horizontal
- If angle is from vertical, swap sin/cos and explicitly say why.

### 5. Explain Physical Independence

Strong explanations repeatedly state that horizontal and vertical motions are independent:
- horizontal velocity stays constant when no horizontal acceleration exists
- vertical motion is controlled by gravity
- time of flight is decided by vertical motion in ordinary projectile cases

Implementation requirement:
- Add a `separate_axes` move before using kinematics.
- Visually dim the irrelevant axis and highlight the axis currently being solved.
- Example: when solving time, highlight vertical axis and vertical equation only.

### 6. Choose Equation Based On Missing Quantity

The theory transcript chooses `v^2 = u^2 + 2as` when time is not known. This is a key teaching behavior.

Implementation requirement:
- Equation selection step should state:
  - known quantities
  - target quantity
  - why this equation is selected
- Do not just display a formula. Show the reason it is the right tool.

Example rule:
- If time is missing and displacement/initial/final velocity are known, prefer `v^2 = u^2 + 2as`.
- If displacement and acceleration are known for horizontal launch, solve vertical time first.
- If range is requested for same-height projectile, use derived or direct range relation depending on teaching depth.

### 7. Substitute Values In A Separate Calculation Block

Good explanations separate concept from arithmetic. They first show the relation, then substitute, then simplify.

Implementation requirement:
- Each step should have:
  - `principle`
  - `equation`
  - `substitution`
  - `calculation`
  - `result`
- The UI should not interleave explanation text and equations awkwardly.
- Values should visually travel/highlight from `Given` into the equation where possible.

### 8. Use Intermediate Results As New Givens

Teachers often solve maximum height, then use that height for final velocity, or solve first bounce time and use it in a series. Intermediate quantities become givens for later steps.

Implementation requirement:
- Walkthrough state should maintain a `known_values` ledger.
- After each boxed intermediate answer, add it to the current known values.
- Later steps should reference intermediate results visibly.

### 9. Warn About Common Traps

Repeated trap patterns:
- angle from vertical vs horizontal
- horizontal does not always mean cos
- downward/upward signs must be consistent
- final velocity means resultant velocity, not just vertical velocity
- range on incline is not horizontal range
- relative motion must use the correct frame
- if friction/drag is not stated, do not invent it

Implementation requirement:
- Add optional `trap_note` per step.
- Display it as a small study note, not a large warning.
- Tie it to the visual object where possible.

### 10. Keep Motion And Calculation In Sync

Good video explanations do not animate the whole trajectory while solving every equation. They show only the relevant visual at that moment.

Implementation requirement:
- Step animation is not full lifecycle playback.
- Each step has a local visual action:
  - setup: full scene, labels
  - components: zoom launch vector
  - vertical time: highlight y-axis and vertical equation
  - horizontal range: highlight range bracket
  - final velocity: highlight velocity triangle at impact
  - bounce/series: highlight repeated intervals and ratio pattern
- Full animation remains a separate control.

## Walkthrough Contract

Each walkthrough step should map to this structure:

```ts
WalkthroughMove {
  id: string
  title: string
  teaching_goal: string
  visual_action: string
  camera_target_ids: string[]
  highlight_ids: string[]
  principle?: string
  equation?: string
  substitution?: string
  calculation?: string
  result?: string
  trap_note?: string
  next_known_values?: string[]
}
```

## Immediate Product Implications

Do before deployment:
- Generic scene framing so full setup, component zoom, and range/impact views are reliable.
- Step-level camera targets and highlights.
- Calculation block separated from explanation text.
- Known-values ledger.
- Trap notes for angle/sign/frame/range mistakes.

Do later:
- Alternate solution methods.
- Voice narration.
- More language styles.
- Full transcript-driven prompt tuning.

