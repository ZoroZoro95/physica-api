# Goals & Roadmap

This document outlines the current objectives and the long-term vision for `physica`.

## 🎯 Current Goals (May 2024)

### 1. Deterministic Accuracy
- **Objective**: Ensure 100% agreement between the AI's narration and the Three.js visualization.
- **Tasks**:
  - [x] Implement backend validation for object presence.
  - [x] Bound coordinate data within safe viewable ranges.
  - [x] Fix "floating" objects by enforcing ground-plane collision detection in the solver.

### 2. Pedagogical Consistency
- **Objective**: Force every generated scene to adhere to the 4-chapter pipeline.
- **Tasks**:
  - [x] Update `PromptEngine` system prompt to mandate the 4 chapters.
  - [x] Implement chapter-specific narration that never repeats.
  - [x] Add manual "Advance" controls for the teacher/user to bypass AI stalling.

### 3. Visual Polish
- **Objective**: Achieve a "premium STEM tool" look.
- **Tasks**:
  - [x] Implement "JetBrains Mono" font and sleek dark UI.
  - [x] Add glassmorphism effects to panels.
  - [/] Improve Three.js lighting and material responsiveness (ongoing).

## 🚀 Future Roadmap

### Short-Term (Next 2 Weeks)
- **RAG Integration**: Fully connect the `rag` module to external physics textbooks for even better accuracy in "edge case" problems.
- **Multi-Object Support**: Support collisions between two objects (e.g., billiard ball physics).
- **Label System**: Automated Three.js labels for vectors (velocity, gravity, force).

### Mid-Term (1-2 Months)
- **Math Overlay**: A LaTeX rendering layer that shows equations alongside the 3D animation.
- **Mobile Optimization**: Responsive controls for tablets and mobile devices.
- **Session Persistence**: Database integration (Postgres/Redis) to save and share physics scenes.

### Long-Term (Vision)
- **Voice Interaction**: Real-time voice conversation with the AI teacher.
- **XR Support**: View the physics visualizations in AR/VR.
- **Customizable Teacher Personas**: Choose between different teaching styles (e.g., Socratic, Direct, Humorous).
