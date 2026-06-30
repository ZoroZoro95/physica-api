# Project Overview & Philosophy

## The Vision
`physica` aims to bridge the gap between static textbook diagrams and complex simulation software. Most AI-generated visuals today suffer from "hallucinated data"—where an object might move in a way that looks cool but violates physical laws. `physica` solves this by combining the creative power of LLMs with the deterministic precision of physics solvers.

## The 4-Chapter Pedagogical Pipeline
Every physics problem solved by `physica` follows a standard story arc to ensure maximum learning efficiency:

1.  **The Setup (Initial State)**:
    - The object is introduced in its reference frame (usually at [0,0,0]).
    - The coordinate system (Axes) is established.
    - Narrator introduces the context of the problem.

2.  **The Parameters (Problem Constraints)**:
    - Vectors and indicators appear (e.g., Velocity arrows, Angle arcs).
    - Labels display the known values (v=10m/s, θ=30°).
    - The student is prepared for what is about to happen.

3.  **The Execution (The Physics)**:
    - The simulation runs.
    - Paths and trajectories are drawn in real-time.
    - This chapter uses the `physics_intent` schema to calculate motion deterministically.

4.  **The Result (Conclusion)**:
    - The final state is reached (e.g., the ball hits the ground).
    - Final math results are displayed (Range, Max Height, Time of Flight).
    - The AI teacher reviews the key takeaways.

## Interactive Learning
The AI Teacher isn't just a narrator; it's a guide.
- **Visual Context**: The teacher sees what the student sees (using frame capture from the Three.js canvas).
- **Adaptive Advancement**: The teacher can decide when the student is ready to move to the next chapter based on their questions.
- **Hallucination Prevention**: All coordinate data is validated against safety bounds and physical limits before rendering.
