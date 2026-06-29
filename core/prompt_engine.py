"""
prompt_engine.py — LLM responsibilities:
  1. Classify problem subtype + extract raw numbers (real-world units).
  2. Generate direct, clear teaching narration with optional [HIGHLIGHT: id] tags.

All physics math lives in projectile_solver.py + physics_solver.py.
"""

import json
import re
import base64
import math
import importlib
from typing import Optional
from .schema import PhysicsScene, Session, ExtractQuestionResponse
from .scene_templates import build_scene_from_template


# ─────────────────────────────────────────────
# Param extraction prompt  (unchanged)
# ─────────────────────────────────────────────

PARAM_EXTRACTION_PROMPT = """
You are a physics problem classifier and parameter extractor.
Output ONLY a single raw JSON object. No markdown, no explanation.
NEVER output multiple JSON objects, a list of JSONs, or comma-separated JSON blocks. Even if the problem asks multiple questions, has multiple parts, or asks for multiple points/times, extract only one primary set of parameters or the first query point in a single JSON object.
All values must be valid JSON numbers. NO strings, NO units, NO expressions.
Use real-world units (metres, m/s, kg, degrees, seconds).
If a value is given as an expression (e.g. 20*sqrt(2)), convert it to a decimal (28.28).
DO NOT compute physics answers. Just extract the given parameters.

━━━ SUBJECT CLASSIFICATION ━━━

Pick exactly one subject:

  projectile_basic      — standard angle/height launch, no special events
  projectile_split      — projectile splits/explodes into fragments (momentum conservation)
  projectile_collision  — two projectiles that may meet/collide mid-air
  projectile_moving_cart— projectile launched from or onto a moving cart/truck/train (flat surface)
  projectile_moving_wedge— projectile launched on a MOVING WEDGE/INCLINE (incline + cart combined)
  projectile_inclined   — projectile launched on a STATIONARY inclined plane/slope/ramp
  projectile_relative   — relative velocity or relative trajectory between two projectiles
  projectile_curvature  — asks for radius of curvature at a point along the path
  projectile_piecewise  — gravity changes at a specific altitude (two-zone atmosphere)
  projectile_angle_pair — θ vs (90°−θ) same-range comparison, conceptual question
  projectile_monkey_gun — gun/dart aimed at a freely-falling target
  projectile_wall       — minimum speed/angle to clear a wall at a given distance
  projectile_intercept  — intercept a body dropped/falling from a height
  shm                   — spring-mass, pendulum, SHM, oscillation
  circular_motion       — circular orbit, satellite, banked road, centripetal
  other                 — anything else

CRITICAL DISAMBIGUATION:
  - If the problem has BOTH a moving cart/wedge AND an inclined surface → projectile_moving_wedge
  - If only an inclined surface (stationary) → projectile_inclined
  - If only a moving flat platform → projectile_moving_cart

━━━ OUTPUT FORMATS ━━━

─── projectile_basic ───
{
  "subject": "projectile_basic",
  "topic": "one-line description",
  "params": {
    "speed":  <launch speed m/s>,
    "angle":  <degrees above horizontal, 0=horizontal, 90=straight up>,
    "height": <launch height above ground in metres, 0 if ground launch>,
    "gravity": <g in m/s², default 10.0>,
    "label_speed": "<e.g. '20 m/s'>",
    "label_angle": "<e.g. '45°'>"
  }
}

EXAMPLES:
  "Ball at 30° with 20 m/s"  → speed=20, angle=30, height=0
  "Thrown horizontally at 15 m/s from 45 m cliff"  → speed=15, angle=0, height=45
  "Stone dropped from 80 m"  → speed=0, angle=90, height=80

─── projectile_split ───
{
  "subject": "projectile_split",
  "topic": "...",
  "params": {
    "speed": <m/s>, "angle": <deg>, "height": <m>, "gravity": <m/s²>,
    "m_total": <total mass kg, use 1.0 if not given>,
    "m1": <mass of fragment 1, default half>,
    "vx1_after": <horizontal velocity of frag 1 after split, 0 if it drops straight>,
    "vy1_after": <vertical velocity of frag 1 after split, 0 if at peak>
  }
}

─── projectile_collision ───
{
  "subject": "projectile_collision",
  "topic": "...",
  "params": {
    "ax0": <A start x m>, "ay0": <A start y m>,
    "avx": <A horizontal velocity m/s>, "avy": <A vertical velocity m/s>,
    "bx0": <B start x m>, "by0": <B start y m>,
    "bvx": <B horizontal velocity m/s>, "bvy": <B vertical velocity m/s>,
    "gravity": <m/s²>
  }
}

─── projectile_moving_cart ───
{
  "subject": "projectile_moving_cart",
  "topic": "...",
  "params": {
    "u_cart": <cart speed m/s, rightward positive>,
    "vx_relative": <ball's horizontal velocity as seen from cart, m/s>,
    "vy_relative": <ball's vertical velocity as seen from cart, m/s>,
    "height": <launch height m, 0 for ground>,
    "gravity": <m/s²>
  }
}

─── projectile_relative ───
{
  "subject": "projectile_relative",
  "topic": "...",
  "params": {
    "ax0": <A x m>, "ay0": <A y m>,
    "avx": <A vx m/s>, "avy": <A vy m/s>,
    "bx0": <B x m>, "by0": <B y m>,
    "bvx": <B vx m/s>, "bvy": <B vy m/s>,
    "gravity": <m/s²>
  }
}

─── projectile_curvature ───
{
  "subject": "projectile_curvature",
  "topic": "...",
  "params": {
    "speed": <m/s>, "angle": <deg>, "height": <m>, "gravity": <m/s²>,
    "query_at": <"launch"|"peak"|"landing"|"t_query">,
    "t_query": <seconds after launch, only if query_at is t_query, else 0>
  }
}

─── projectile_piecewise ───
{
  "subject": "projectile_piecewise",
  "topic": "...",
  "params": {
    "speed": <m/s>, "angle": <deg>, "height": <m>,
    "gravity": <g in lower zone m/s²>,
    "g2": <g in upper zone m/s²>,
    "h_boundary": <altitude where gravity changes, metres>
  }
}

─── projectile_inclined ───
{
  "subject": "projectile_inclined",
  "topic": "...",
  "params": {
    "speed": <launch speed m/s>,
    "theta": <angle ABOVE the incline surface in degrees>,
    "alpha": <incline angle from horizontal in degrees>,
    "gravity": <m/s², default 10.0>
  }
}

─── projectile_angle_pair ───
{
  "subject": "projectile_angle_pair",
  "topic": "...",
  "params": {
    "speed": <v0 m/s>,
    "angle": <the SMALLER of the two angles, must be < 45>,
    "gravity": <m/s², default 10.0>
  }
}

─── projectile_monkey_gun ───
{
  "subject": "projectile_monkey_gun",
  "topic": "...",
  "params": {
    "speed": <muzzle speed m/s>,
    "d": <horizontal distance to target in metres>,
    "h": <height of target in metres>,
    "gravity": <m/s², default 10.0>
  }
}

─── projectile_wall ───
{
  "subject": "projectile_wall",
  "topic": "...",
  "params": {
    "d_wall": <horizontal distance to wall in metres>,
    "h_wall": <wall height in metres>,
    "angle": <launch angle in degrees, or 45 if not specified>,
    "speed": <launch speed m/s, or 0 to compute minimum>,
    "gravity": <m/s², default 10.0>
  }
}

─── projectile_intercept ───
{
  "subject": "projectile_intercept",
  "topic": "...",
  "params": {
    "speed": <projectile launch speed m/s>,
    "d": <horizontal distance to drop point in metres>,
    "H": <height from which body is dropped in metres>,
    "gravity": <m/s², default 10.0>
  }
}

─── shm ───
{
  "subject": "shm",
  "topic": "...",
  "params": {
    "amplitude": <scene units — real_metres / 10>,
    "frequency": <Hz>, "axis": 1, "equilibrium": [0, 2, 0]
  }
}

─── circular_motion ───
{
  "subject": "circular_motion",
  "topic": "...",
  "params": {
    "radius": <scene units>, "center": [0, 3, 0], "plane": "xz", "speed": <scene units/s>
  }
}

─── other ───
{
  "subject": "other",
  "topic": "...",
  "params": {}
}

CRITICAL RULES:
- Output ONLY the JSON object. Nothing else.
- Never compute physics answers. Only extract what the problem states.
- For collision/relative: decompose speed+angle into (vx, vy) before emitting.
- For split: fragment 1 velocity defaults to (0, 0) if the problem says it "falls vertically".
- If gravity is not stated, default to 10.0 m/s².
"""


# ─────────────────────────────────────────────
# Teaching system prompt  (Interactive Version)
# ─────────────────────────────────────────────

INTERACTIVE_TEACHING_PROMPT = """
You are Prof. Newton, a highly engaging, intuitive, and passionate physics tutor inspired by world-class teachers like Abdul Bari and Andrew Ng.
Your job is to teach step-by-step, explaining the physical intuition and "why" behind the physics before jumping into equations, and linking your explanations directly to the 3D scene elements.

PEDAGOGICAL TEACHING STYLE:
- **Never just state dry facts or read variables.** Talk like an excited teacher in a high-quality video.
- **Physical Intuition First**: Explain *why* things behave the way they do (e.g. "Gravity acts like a constant downward pull, stealing the ball's vertical speed point-by-point, while horizontal speed remains untouched because there is no air friction pushing sideways!").
- **Visual Scaffolding**: Reference concrete parts of the 3D animation (e.g. "Do you see the red sphere?", "Notice the yellow velocity arrow pointing straight up?").
- **Pacing**: Speak directly, with passion and warmth, keeping questions and explanations highly accessible yet intellectually satisfying.

UNDERSTANDING THE FLOW:
- When student message is "start_tutoring": BEGIN the lesson (Phase 1: Introduction). Start by introducing the scenario and showing the initial state.
- After student clicks "Yes" (or equivalent positive choice): Progress to the NEXT concept/step.
- After student clicks "No" (or equivalent confusion): Clarify the CURRENT concept using a different, intuitive analogy, and ask again.
- Look at the conversation history to know what phase you're in.

NATURAL PROGRESSION (Classroom Storyboard):
Phase 1 (Start): Introduction to problem + ask them to observe the initial state. (chapter_index: 0)
Phase 2: Given parameters and physical setup. (chapter_index: 1)
Phase 3: Deep conceptual intuition check (e.g. velocity splitting). (chapter_index: 1 or 2)
Phase 4: Introducing the mathematical relation/formula. (chapter_index: 2)
Phase 5: Step-by-step solving & derivation. (chapter_index: 2 or 3)
Phase 6: Verification check or conceptual quiz question. (chapter_index: 3)
Phase 7: Final state review & wrap up. (chapter_index: 3)

RULES:
- Keep explanations and questions engaging, clear, and focused (3-4 sentences max per turn).
- ALWAYS provide exactly 2-3 button options. Ensure option texts are conversational (e.g. "Yes, makes sense!", "Wait, why does Vx stay constant?").
- Match the `chapter_index` exactly with the Scene Chapters structure provided in your context.
- Output ONLY valid JSON. No ```json markdown code blocks, no trailing comments.

OUTPUT JSON FORMAT:
{
  "question": "Your highly engaging explanation and next question/observation prompt.",
  "step_type": "introduction|given|understanding|formula|solving|testing|final",
  "options": [
    {"text": "Yes, I understand!", "id": "yes", "type": "yes"},
    {"text": "No, explain more", "id": "no", "type": "no"}
  ],
  "highlight_id": "object_id_to_highlight",
  "chapter_index": 0
}

EXAMPLES:

─── Phase 1: Start (student: "start_tutoring") ───
{
  "question": "Welcome to our digital classroom! We are looking at a classic physics challenge: a ball launched at 30° with a speed of 20 m/s. Before we look at any math, take a look at the red sphere sitting at the origin. Ready to see the story of its flight unfold?",
  "step_type": "introduction",
  "options": [
    {"text": "Yes, let's start!", "id": "yes", "type": "yes"},
    {"text": "Where is the launch point?", "id": "no", "type": "no"}
  ],
  "highlight_id": "ball",
  "chapter_index": 0
}

─── Phase 2: Given parameters (student: "Yes, let's start!") ───
{
  "question": "Excellent! Now let's notice the launch vector—it rises at 30 degrees with a speed of 20 m/s. In physics, we need to divide and conquer. Do you see the yellow arrow indicating vertical launch speed, and the blue arrow indicating horizontal launch speed?",
  "step_type": "given",
  "options": [
    {"text": "Yes, I see the vectors", "id": "yes", "type": "yes"},
    {"text": "Which vector is which?", "id": "no", "type": "no"}
  ],
  "highlight_id": "velocity_vector",
  "chapter_index": 1
}

─── Phase 3: Conceptual Check (student: "Yes, I see the vectors") ───
{
  "question": "Beautiful! Here is the magic: the blue horizontal speed (17.3 m/s) stays exactly the same the entire time! But gravity is constantly pulling downward, stealing 10 m/s of vertical speed every single second. This difference in forces causes the curved arc. Make physical sense?",
  "step_type": "understanding",
  "options": [
    {"text": "Perfect sense!", "id": "yes", "type": "yes"},
    {"text": "Why doesn't Vx change?", "id": "no", "type": "no"}
  ],
  "highlight_id": "ball",
  "chapter_index": 1
}

─── Phase 4: Formula (student: "Perfect sense!") ───
{
  "question": "Now, let's put equations to our intuition! To calculate how high the ball will fly, we use the vertical velocity component: h_max = (v₀ sin θ)² / (2g). In our case, that's (20 × sin 30°)² / 20 = 5 meters. Do you see how this formula directly measures the vertical kinetic energy battle against gravity?",
  "step_type": "formula",
  "options": [
    {"text": "Clear! Let's solve.", "id": "yes", "type": "yes"},
    {"text": "Why is sin 30° used here?", "id": "no", "type": "no"}
  ],
  "highlight_id": "ball",
  "chapter_index": 2
}

─── Phase 6: Quiz Check (student finishes steps) ───
{
  "question": "Quick question to test your intuition! If we launched this exact same ball on the Moon, where gravity is much weaker, would the peak height be HIGHER, LOWER, or the SAME?",
  "step_type": "testing",
  "options": [
{
  "question": "Excellent! You now understand the complete projectile motion flow. The max height is 5 meters and total flight time is 2 seconds. Ready to try a new problem?",
  "step_type": "final",
  "options": [
    {"text": "Yes, new problem", "id": "yes", "type": "yes"},
    {"text": "Review this one", "id": "no", "type": "no"}
  ]
}

TRACKING PHASES (from conversation history):
- Count "yes" responses to know how many steps completed
- If last student message was "no", stay in current phase
- If doubt detected, clarify then continue from that phase
"""


# ─────────────────────────────────────────────
# Dynamic Scene Generator prompt
# Used as ultimate fallback for complex questions
# ─────────────────────────────────────────────

DYNAMIC_SCENE_PROMPT = """
You are a physics teacher AND a 3D scene architect. You must solve the physics problem
correctly and then produce a beautiful animated storyboard for a student to watch.

SCALE CONTRACT (MANDATORY):
  - 1 scene unit = 10 real-world metres.
  - scene_x = real_x / 10,  scene_y = real_y / 10
  - scene_g = 1.0 (instead of 9.8 m/s²)
  - All path coordinates must use SCENE units.
  - scene_vx = real_vx / 10,  scene_vy = real_vy / 10

SOLVING PROTOCOL:
  1. Read the problem carefully. Identify all given quantities.
  2. Solve the physics MATHEMATICALLY:
     - Write out the equations step by step.
     - Compute exact numerical answers.
  3. Build 3-4 storyboard chapters showing:
     ch1: Setup – show the initial conditions with labelled objects.
     ch2: Decomposition / Key step – show the critical physics concept.
     ch3: Solution motion – animate the actual trajectory with correct path points.
     ch4 (optional): Result – label the final answer clearly.

PATH ARRAY RULES:
  - Every moving sphere/trail must have a "path" array with exactly 20 [x,y,z] points.
  - Points must trace the REAL calculated trajectory, scaled to scene units.
  - For projectiles: x = vx*t/10, y = y0/10 + vy*t/10 - 0.5*(1.0)*t^2
    where t runs from 0 to T_flight in 20 steps.
  - z is always 0.0.

FORMULA AND DERIVATION:
  - Every chapter MUST have "formula" and "derivation" fields with:
    formula: the exact symbolic equation used in this step (LaTeX-style is fine)
    derivation: a short 2-3 sentence explanation of why this equation applies.

OBJECT TYPES AVAILABLE:
  sphere, box, plane, cylinder, line, arrow, axes, trail, rope, spring, arc, label

COLOR PALETTE:
  Ball/projectile: #FC6255 (red)   Ground: #83C167 (green)   Wall/surface: #888888
  Vx arrows: #58C4DD (blue)        Vy arrows: #FFFF00 (yellow)  Text: #FFFFFF
  Incline: #A0522D (brown)         Target: #FF6B00 (orange)

OUTPUT FORMAT — output ONLY valid JSON, no markdown, no explanation:
{
  "topic": "one-line description",
  "subject": "projectile_inclined" | "projectile_basic" | "other" | ...,
  "chapters": [
    {
      "id": "setup",
      "title": "Chapter title",
      "narration": "What the tutor says (2-4 sentences, direct and clear).",
      "formula": "symbolic equation",
      "derivation": "short derivation explanation",
      "duration_hint": 6.0,
      "autoplay": true,
      "loop": false,
      "camera": {"position": [12, 8, 12], "target": [0, 2, 0], "fov": 45},
      "objects": [
        {"id": "ground", "type": "plane", "position": [0,0,0], "color": "#83C167", "args": [20,20], "visible": true},
        {"id": "axes", "type": "axes", "position": [0,0,0], "args": [5], "color": "#888888", "visible": true},
        {"id": "ball", "type": "sphere", "position": [0,0,0], "color": "#FC6255",
         "label": "ball", "label_always_visible": true,
         "path": [[0,0,0], ...20 points...],
         "physics_intent": {"type": "projectile", "params": {"velocity": [vx_s, vy_s, 0], "vx_real": vx_r, "vy_real": vy_r, "v0_real": v0, "T": T_flight}}}
      ],
      "annotations": [
        {"id": "lbl1", "text": "label text", "position": [x, y, 0], "color": "#FFFF00", "size": "sm"}
      ],
      "reveal_ids": [],
      "hide_ids": []
    }
  ]
}

CRITICAL RULES:
- Output ONLY the JSON object. Nothing else. No ```json fences.
- path must have exactly 20 points.
- All coordinates in SCENE units (real / 10).
- narration must be direct, friendly, 2-4 sentences.
- formula and derivation are REQUIRED on every chapter.
"""


# ─────────────────────────────────────────────
# Teaching system prompt  (Phase 2 rewrite)
# ─────────────────────────────────────────────

TEACHING_SYSTEM_PROMPT = """
You are a direct, highly clear JEE physics explanation guide.
Your role is to explain what is happening in the 3D animation the student is watching.

STYLE RULES:
- 2-4 sentences maximum per response. No padding, no filler phrases.
- Use exact numbers from the chapter script. Never vague.
- Reference visible objects by name (e.g. "the red ball", "the blue arrow", "the yellow boundary line").
- For doubts: give one clean re-explanation from a different angle. No Socratic loops.
- Never ask questions back. State facts clearly and stop.

HIGHLIGHT TAG:
If your explanation refers to a specific object that the student should focus on,
insert [HIGHLIGHT: object_id] anywhere in your response, where object_id is the id
of that object from the chapter's object list.
Example: "Watch [HIGHLIGHT: ball] as it leaves the peak — Vy becomes zero here."
Only use ONE highlight tag per response. Only use it when it genuinely helps focus attention.

DOUBT CONTROL:
The student's message is a doubt or interruption inside the current scene.
Answer only that doubt in the context of the current chapter. Never advance the lesson.
If the student says "got it", "yes", "ok", "understood", "continue", or "move on",
acknowledge briefly but do not emit any control token.
"""


# ─────────────────────────────────────────────
# Image Question Extraction Prompt
# ─────────────────────────────────────────────

IMAGE_QUESTION_EXTRACTION_PROMPT = """
You extract physics questions from uploaded images. Your job is OCR + diagram fact extraction only.
Do NOT solve the problem. Do NOT invent missing values. If a value is unclear, add a warning and lower confidence.

Output ONLY valid JSON matching this shape:
{
  "question_text": "student-facing extracted text; same as question_text_display",
  "question_text_raw": "closest OCR transcription from the image, preserving source quirks where possible",
  "question_text_display": "clean student-facing text using symbols like θ, α, β, t₁, t₂; no $...$ delimiters",
  "question_text_solver": "ASCII solver-facing text using theta, alpha, beta, t1, t2, sqrt(), deg, ^",
  "cleaned_prompt": "solver-facing prompt; same style as question_text_solver and include option text if MCQ",
  "is_projectile_question": true,
  "question_type": "mcq|subjective|unknown",
  "options": ["...", "...", "...", "..."],
  "diagram": {
    "present": true,
    "type": "none|basic_projectile|incline|staircase|target|wall|two_inclines|3d_axes|other",
    "entities": [
      {
        "id": "short_id",
        "kind": "point|line|incline|axis|projectile|target|wall|staircase|velocity_arrow|angle|distance|height|surface|other",
        "label": "A",
        "label_display": "θ",
        "label_solver": "theta",
        "value": "30",
        "unit": "deg",
        "description": "incline angle with horizontal",
        "confidence": 0.92
      }
    ],
    "coordinate_system": "x horizontal, y vertical",
    "confidence": 0.85
  },
  "givens": ["v0=10 m/s", "angle=60 deg"],
  "requested_quantity": "time_to_hit_incline",
  "suggested_engine_case": "inclined_plane_impact_time",
  "confidence": 0.82,
  "needs_review": true,
  "warnings": ["diagram angle label is blurry"]
}

Rules:
- Preserve MCQ options in order. If options are absent, return [].
- Never wrap math in $...$ delimiters.
- Display fields should use readable symbols: θ, α, β, t₁, t₂, R₁, R₂, H, T.
- Solver fields should use ASCII tokens: theta, alpha, beta, t1, t2, R1, R2, H, T.
- Use sqrt(3), not √3, in solver fields. Use deg, not °, in solver fields.
- For diagrams, extract geometry facts: incline angle, wall height, step size, launch point, target, velocity arrow direction, axes, and labeled distances.
- Diagram entity requirements by diagram type:
  - staircase: include one `staircase` entity and one `surface` entity whose description says "vertical faces".
  - incline: include an `incline` or `surface` entity, its angle entity, and an impact point if the projectile hits/strikes the plane.
  - two_inclines: extract role-based geometry, not fixed letters. Include left/right incline surface entities with their visible labels if present, the intersection point, launch point, impact point, both incline angle entities, and right-angle/perpendicular marker entities when shown.
  - target: include a `target` entity or point entity with target coordinates/label.
  - 3d_axes: include axis entities and the line constraint entity.
  - smooth incline / greatest slope diagrams: include line of greatest slope and the perpendicular velocity arrow.
- If an image has no diagram, set diagram.present=false and diagram.type="none".
- `cleaned_prompt` must be readable text that can be passed to the solver after user review.
- `suggested_engine_case` must match what the question asks to solve, not merely the closest-looking setup.
  Example: if the question asks for velocity at Q, do not return `inclined_plane_impact_time`.
  Example: if the question asks which step is hit, return `staircase_collision`, not `fielder_catch_before_ground`.
  Example: if the question asks an air-drag qualitative MCQ, return `air_drag_conceptual_timing`, not `projectile_with_horizontal_acceleration`.
- `suggested_engine_case` must be one of these exact names when applicable:
  parametric_initial_speed,
  velocity_change_interval,
  parametric_curve_classification,
  velocity_angle_event_speed,
  horizontal_throw_velocity_angle_time,
  velocity_perpendicular_to_initial_event,
  same_range_doubled_angle_time_ratio,
  target_angle_from_short_overshoot,
  fielder_catch_before_ground,
  average_velocity_to_peak,
  projectile_with_horizontal_acceleration,
  max_range_from_height_fixed_speed,
  inclined_plane_impact_time,
  air_drag_conceptual_timing,
  inclined_plane_same_point_time_ratio,
  inclined_plane_right_angle_impact_condition,
  target_reachability_fixed_speed,
  staircase_collision,
  minimum_speed_to_hit_target,
  inclined_plane_max_normal_distance_velocity_component,
  perpendicular_launch_range_on_incline,
  max_range_on_incline,
  horizontal_launch_onto_incline_distance,
  two_inclines_perpendicular_launch_impact,
  projectile_collides_with_sliding_particle_on_incline,
  motion_on_smooth_incline_perpendicular_to_slope,
  three_dimensional_projectile_line_intersection.
  If none fits, use null.
- `needs_review` should be true unless confidence >= 0.93 and no warnings.
- Output exactly one JSON object.
"""


# ─────────────────────────────────────────────
# Prompt Engine
# ─────────────────────────────────────────────

class PromptEngine:
    def __init__(self, api_key: str):
        self.api_key = api_key
        if api_key.startswith("gsk_"):
            self.provider = "groq"
            groq_module = importlib.import_module("groq")
            Groq = groq_module.Groq
            self.client = Groq(api_key=api_key)
            self.model = "meta-llama/llama-4-scout-17b-16e-instruct"
        else:
            self.provider = "gemini"
            genai = importlib.import_module("google.generativeai")
            genai.configure(api_key=api_key)
            self.json_model   = genai.GenerativeModel("models/gemini-1.5-flash")
            self.vision_model = genai.GenerativeModel("models/gemini-1.5-flash")

    # ── Scene generation ──────────────────────

    def generate_scene(
        self,
        prompt: str,
        rag_context: str = "",
        image_bytes: Optional[bytes] = None,
        image_mime_type: str = "image/jpeg",
    ) -> PhysicsScene:

        extracted = self._extract_params(prompt, rag_context, image_bytes, image_mime_type)
        print(f"[engine] extracted: {json.dumps(extracted, indent=2)}")

        subject = extracted.get("subject", "other")
        params  = extracted.get("params", {})
        topic   = extracted.get("topic", prompt[:100])

        scene_dict = build_scene_from_template(subject, params, topic)

        if scene_dict is None or subject == "other":
            print(f"[engine] no template for subject={subject}, using dynamic LLM scene generator")
            scene_dict = self._generate_dynamic_scene(prompt, rag_context, image_bytes, image_mime_type)

        return PhysicsScene(**scene_dict)

    def _extract_params(self, prompt, rag_context, image_bytes, mime_type) -> dict:
        full = f"{rag_context}\n\nProblem: {prompt}" if rag_context else f"Problem: {prompt}"
        if self.provider == "groq":
            raw = self._groq_extract(full, image_bytes, mime_type)
        else:
            raw = self._gemini_extract(full, image_bytes, mime_type)
        return self._parse_json(raw)

    def _groq_extract(self, prompt, image_bytes, mime_type) -> str:
        content = [{"type": "text", "text": prompt}]
        if image_bytes:
            b64 = base64.b64encode(image_bytes).decode()
            content.append({"type": "image_url",
                             "image_url": {"url": f"data:{mime_type};base64,{b64}"}})
        try:
            resp = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": PARAM_EXTRACTION_PROMPT},
                    {"role": "user",   "content": content},
                ],
                model=self.model,
                response_format={"type": "json_object"},
            )
        except Exception:
            resp = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": PARAM_EXTRACTION_PROMPT},
                    {"role": "user",   "content": content},
                ],
                model=self.model,
            )
        return resp.choices[0].message.content

    def _gemini_extract(self, prompt, image_bytes, mime_type) -> str:
        parts = [PARAM_EXTRACTION_PROMPT, prompt]
        if image_bytes:
            parts.append({"mime_type": mime_type, "data": image_bytes})
        resp = self.json_model.generate_content(
            [{"role": "user", "parts": parts}],
            generation_config={"response_mime_type": "application/json", "temperature": 0.0},
        )
        return resp.text

    def _parse_json(self, raw: str) -> dict:
        raw = raw.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            raw = match.group(0)
        raw = re.sub(r',\s*([\]}])', r'\1', raw)
        try:
            return json.loads(raw)
        except Exception as e:
            print(f"[engine] JSON parse failed: {e}\nRaw: {raw[:300]}")
            return {"subject": "other", "topic": "Physics", "params": {}}

    # ── Image question extraction ─────────────

    def extract_question_from_image(
        self,
        image_bytes: bytes,
        image_mime_type: str = "image/jpeg",
        hint: str = "",
    ) -> ExtractQuestionResponse:
        if not image_bytes:
            raise ValueError("image_bytes is required")

        prompt = (
            f"Optional user hint: {hint}\n\nExtract the physics question and diagram facts from this image."
            if hint else
            "Extract the physics question and diagram facts from this image."
        )

        if self.provider == "groq":
            raw = self._groq_extract_question_image(prompt, image_bytes, image_mime_type)
        else:
            raw = self._gemini_extract_question_image(prompt, image_bytes, image_mime_type)

        parsed = self._parse_json(raw)
        parsed = self._normalize_question_extraction(parsed)
        return ExtractQuestionResponse(**parsed)

    def _groq_extract_question_image(self, prompt: str, image_bytes: bytes, mime_type: str) -> str:
        b64 = base64.b64encode(image_bytes).decode()
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
        ]
        try:
            resp = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": IMAGE_QUESTION_EXTRACTION_PROMPT},
                    {"role": "user", "content": content},
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
        except Exception:
            resp = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": IMAGE_QUESTION_EXTRACTION_PROMPT},
                    {"role": "user", "content": content},
                ],
                model=self.model,
                temperature=0.0,
            )
        return resp.choices[0].message.content

    def _gemini_extract_question_image(self, prompt: str, image_bytes: bytes, mime_type: str) -> str:
        parts = [IMAGE_QUESTION_EXTRACTION_PROMPT, prompt, {"mime_type": mime_type, "data": image_bytes}]
        resp = self.vision_model.generate_content(
            [{"role": "user", "parts": parts}],
            generation_config={"response_mime_type": "application/json", "temperature": 0.0},
        )
        return resp.text

    def _normalize_question_extraction(self, parsed: dict) -> dict:
        diagram = parsed.get("diagram") or {}
        if not isinstance(diagram, dict):
            diagram = {}

        confidence = float(parsed.get("confidence") or 0.0)
        warnings = parsed.get("warnings") or []
        if not isinstance(warnings, list):
            warnings = [str(warnings)]

        question_text_raw = str(parsed.get("question_text_raw") or parsed.get("question_text") or "").strip()
        question_text_display = str(parsed.get("question_text_display") or parsed.get("question_text") or question_text_raw).strip()
        question_text_solver = str(parsed.get("question_text_solver") or parsed.get("cleaned_prompt") or parsed.get("question_text") or question_text_raw).strip()
        cleaned_prompt = str(parsed.get("cleaned_prompt") or question_text_solver).strip()

        entities = diagram.get("entities") if isinstance(diagram.get("entities"), list) else []
        normalized_entities = []
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            label = entity.get("label")
            kind = self._normalize_diagram_entity_kind(entity.get("kind"))
            entity_id = entity.get("id")
            description = entity.get("description")
            normalized_entities.append({
                **entity,
                "id": str(entity_id or ""),
                "kind": kind,
                "label_display": entity.get("label_display") or label,
                "label_solver": entity.get("label_solver") or label,
                "description": str(description or ""),
            })

        normalized = {
            "question_text": question_text_display,
            "question_text_raw": question_text_raw,
            "question_text_display": question_text_display,
            "question_text_solver": question_text_solver,
            "cleaned_prompt": cleaned_prompt,
            "is_projectile_question": bool(parsed.get("is_projectile_question", False)),
            "question_type": parsed.get("question_type") if parsed.get("question_type") in {"mcq", "subjective", "unknown"} else "unknown",
            "options": parsed.get("options") if isinstance(parsed.get("options"), list) else [],
            "diagram": {
                "present": bool(diagram.get("present", False)),
                "type": diagram.get("type") if diagram.get("type") in {
                    "none", "basic_projectile", "incline", "staircase", "target",
                    "wall", "two_inclines", "3d_axes", "other"
                } else "other",
                "entities": normalized_entities,
                "coordinate_system": diagram.get("coordinate_system"),
                "confidence": float(diagram.get("confidence") or 0.0),
            },
            "givens": parsed.get("givens") if isinstance(parsed.get("givens"), list) else [],
            "requested_quantity": parsed.get("requested_quantity"),
            "suggested_engine_case": parsed.get("suggested_engine_case"),
            "confidence": confidence,
            "needs_review": bool(parsed.get("needs_review", confidence < 0.93 or bool(warnings))),
            "warnings": warnings,
        }
        self._enrich_projectile_diagram_entities(normalized)

        if not normalized["question_text"]:
            normalized["warnings"].append("No question text could be extracted.")
            normalized["needs_review"] = True
        return normalized

    def _normalize_diagram_entity_kind(self, kind: object) -> str:
        allowed = {
            "point", "line", "incline", "axis", "projectile", "target",
            "wall", "staircase", "velocity_arrow", "angle", "distance",
            "height", "surface", "other"
        }
        raw = str(kind or "other").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "launch_point": "point",
            "impact_point": "point",
            "landing_point": "point",
            "intersection_point": "point",
            "target_point": "point",
            "start_point": "point",
            "end_point": "point",
            "arrow": "velocity_arrow",
            "vector": "velocity_arrow",
            "velocity": "velocity_arrow",
            "initial_velocity": "velocity_arrow",
            "final_velocity": "velocity_arrow",
            "inclined_plane": "incline",
            "incline_plane": "incline",
            "plane": "incline",
            "slope": "incline",
            "ramp": "incline",
            "ground": "surface",
            "floor": "surface",
            "step": "staircase",
            "steps": "staircase",
            "range": "distance",
            "displacement": "distance",
            "vertical_height": "height",
            "angle_marker": "angle",
            "coordinate_axis": "axis",
        }
        return raw if raw in allowed else aliases.get(raw, "other")

    def _enrich_projectile_diagram_entities(self, normalized: dict) -> None:
        diagram = normalized["diagram"]
        entities = diagram["entities"]
        text = " ".join(
            str(normalized.get(key) or "")
            for key in ("question_text_solver", "question_text_raw", "question_text_display", "cleaned_prompt")
        )
        text_l = text.lower()
        engine_case = str(normalized.get("suggested_engine_case") or "")

        if diagram["type"] == "none":
            inferred_type = self._infer_diagram_type_from_text(text_l, engine_case)
            if inferred_type != "none":
                diagram["type"] = inferred_type
                diagram["present"] = True

        if diagram["type"] == "staircase" or engine_case == "staircase_collision":
            diagram["present"] = True
            diagram["type"] = "staircase"
            self._append_entity_once(entities, {
                "id": "staircase",
                "kind": "staircase",
                "label": "staircase",
                "description": "staircase with repeated steps",
                "confidence": 0.78,
            })
            self._append_entity_once(entities, {
                "id": "vertical_faces",
                "kind": "surface",
                "label": "vertical faces",
                "description": "vertical faces of the staircase",
                "confidence": 0.78,
            })
            self._append_stair_dimensions(entities, text_l)

        if diagram["type"] == "two_inclines" or engine_case == "two_inclines_perpendicular_launch_impact":
            diagram["present"] = True
            diagram["type"] = "two_inclines"
            self._append_entity_once(entities, {
                "id": "plane_OA",
                "kind": "incline",
                "label": "OA",
                "description": "plane OA, one of the two inclined planes",
                "confidence": 0.78,
            })
            self._append_entity_once(entities, {
                "id": "plane_OB",
                "kind": "incline",
                "label": "OB",
                "description": "plane OB, one of the two inclined planes",
                "confidence": 0.78,
            })
            for point in ("P", "Q", "O", "A", "B"):
                if re.search(rf"\b{point.lower()}\b", text_l):
                    self._append_entity_once(entities, {
                        "id": point,
                        "kind": "point",
                        "label": point,
                        "label_display": point,
                        "label_solver": point,
                        "description": f"labeled point {point}",
                        "confidence": 0.76,
                    })
            for plane, angle in self._extract_two_incline_angles(text_l).items():
                self._append_entity_once(entities, {
                    "id": f"angle_{plane}",
                    "kind": "angle",
                    "label": plane.upper(),
                    "value": f"{angle:g}",
                    "unit": "deg",
                    "description": f"angle of plane {plane.upper()} with horizontal",
                    "confidence": 0.74,
                })
            if "perpendicular" in text_l or "right angle" in text_l:
                self._append_entity_once(entities, {
                    "id": "perpendicular_markers",
                    "kind": "angle",
                    "label": "90deg",
                    "value": "90",
                    "unit": "deg",
                    "description": "right angle / perpendicular marker in the diagram",
                    "confidence": 0.72,
                })

        if diagram["type"] == "incline" or engine_case in {
            "inclined_plane_impact_time",
            "inclined_plane_same_point_time_ratio",
            "inclined_plane_right_angle_impact_condition",
            "inclined_plane_max_normal_distance_velocity_component",
            "perpendicular_launch_range_on_incline",
            "max_range_on_incline",
            "horizontal_launch_onto_incline_distance",
            "projectile_collides_with_sliding_particle_on_incline",
            "motion_on_smooth_incline_perpendicular_to_slope",
        }:
            diagram["present"] = True
            diagram["type"] = "incline"
            self._append_entity_once(entities, {
                "id": "inclined_surface",
                "kind": "incline",
                "label": "incline",
                "description": "inclined surface / inclined plane",
                "confidence": 0.78,
            })
            angle = self._extract_first_angle(text_l)
            if angle is not None:
                self._append_entity_once(entities, {
                    "id": "incline_angle",
                    "kind": "angle",
                    "label": "incline angle",
                    "value": f"{angle:g}",
                    "unit": "deg",
                    "description": "incline angle with horizontal",
                    "confidence": 0.72,
                })
            if any(word in text_l for word in ("hit", "hits", "strike", "strikes", "impact")):
                self._append_entity_once(entities, {
                    "id": "impact_point",
                    "kind": "point",
                    "label": "Q",
                    "label_display": "Q",
                    "label_solver": "Q",
                    "description": "impact / strike point on inclined plane",
                    "confidence": 0.70,
                })
            if "greatest slope" in text_l:
                self._append_entity_once(entities, {
                    "id": "line_of_greatest_slope",
                    "kind": "line",
                    "label": "greatest slope",
                    "description": "line of greatest slope on the smooth inclined plane",
                    "confidence": 0.76,
                })
            if "perpendicular" in text_l:
                self._append_entity_once(entities, {
                    "id": "perpendicular_velocity",
                    "kind": "velocity_arrow",
                    "label": "v_perp",
                    "description": "velocity perpendicular to the line/surface",
                    "confidence": 0.72,
                })

        if diagram["type"] == "target" or engine_case in {"minimum_speed_to_hit_target", "target_reachability_fixed_speed", "target_angle_from_short_overshoot"}:
            if "target" in text_l or re.search(r"\(\s*[-+]?\d", text_l):
                diagram["present"] = True
                diagram["type"] = "target"
                self._append_entity_once(entities, {
                    "id": "target_point",
                    "kind": "target",
                    "label": "target",
                    "description": "target point for projectile trajectory",
                    "confidence": 0.76,
                })

        if diagram["type"] == "3d_axes" or engine_case == "three_dimensional_projectile_line_intersection":
            diagram["present"] = True
            diagram["type"] = "3d_axes"
            for axis in ("x", "y", "z"):
                self._append_entity_once(entities, {
                    "id": f"{axis}_axis",
                    "kind": "axis",
                    "label": axis,
                    "description": f"{axis} axis in 3D coordinate diagram",
                    "confidence": 0.72,
                })
            self._append_entity_once(entities, {
                "id": "line_constraint",
                "kind": "line",
                "label": "line",
                "description": "horizontal line constraint for projectile impact",
                "confidence": 0.72,
            })

    def _infer_diagram_type_from_text(self, text: str, engine_case: str) -> str:
        if engine_case == "staircase_collision" or "staircase" in text or "step" in text:
            return "staircase"
        if engine_case == "two_inclines_perpendicular_launch_impact" or ("plane oa" in text and "plane ob" in text):
            return "two_inclines"
        if engine_case == "three_dimensional_projectile_line_intersection":
            return "3d_axes"
        if "target" in text:
            return "target"
        if "incline" in text or "inclined" in text:
            return "incline"
        return "none"

    def _append_entity_once(self, entities: list[dict], entity: dict) -> None:
        entity_id = entity["id"]
        if any(str(existing.get("id")) == entity_id for existing in entities if isinstance(existing, dict)):
            return
        label = entity.get("label")
        entities.append({
            "value": None,
            "unit": None,
            "description": "",
            "confidence": 0.0,
            **entity,
            "label_display": entity.get("label_display") or label,
            "label_solver": entity.get("label_solver") or label,
        })

    def _append_stair_dimensions(self, entities: list[dict], text: str) -> None:
        height_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*m\s*(?:high|height)", text)
        width_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*m\s*(?:wide|width)", text)
        if height_match:
            self._append_entity_once(entities, {
                "id": "step_height",
                "kind": "height",
                "label": "step height",
                "value": height_match.group(1),
                "unit": "m",
                "description": "height of each stair step",
                "confidence": 0.80,
            })
        if width_match:
            self._append_entity_once(entities, {
                "id": "step_width",
                "kind": "distance",
                "label": "step width",
                "value": width_match.group(1),
                "unit": "m",
                "description": "width of each stair step",
                "confidence": 0.80,
            })

    def _extract_two_incline_angles(self, text: str) -> dict[str, float]:
        angles = [float(value) for value in re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*(?:deg|degree|degrees)", text)]
        if len(angles) >= 2 and "respectively" in text:
            return {"oa": angles[0], "ob": angles[1]}
        found: dict[str, float] = {}
        for plane in ("oa", "ob"):
            match = re.search(rf"{plane}[^0-9]{{0,80}}([0-9]+(?:\.[0-9]+)?)\s*(?:deg|degree|degrees)", text)
            if match:
                found[plane] = float(match.group(1))
        return found

    def _extract_first_angle(self, text: str) -> float | None:
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:deg|degree|degrees)", text)
        return float(match.group(1)) if match else None

    def _generate_dynamic_scene(
        self,
        prompt: str,
        rag_context: str = "",
        image_bytes: Optional[bytes] = None,
        image_mime_type: str = "image/jpeg",
    ) -> dict:
        """Call the LLM to generate a complete PhysicsScene JSON for complex/diagram questions."""
        full = f"{rag_context}\n\nProblem: {prompt}" if rag_context else f"Problem: {prompt}"
        try:
            if self.provider == "groq":
                raw = self._groq_dynamic(full, image_bytes, image_mime_type)
            else:
                raw = self._gemini_dynamic(full, image_bytes, image_mime_type)

            parsed = self._parse_json(raw)
            # Validate by constructing — if it fails, fall to _fallback_scene
            from .schema import PhysicsScene as PS
            PS(**parsed)  # validation check
            return parsed
        except Exception as e:
            print(f"[engine] dynamic scene generation failed: {e}")
            return self._fallback_scene(prompt[:80], prompt)

    def _groq_dynamic(self, prompt: str, image_bytes, mime_type) -> str:
        content = [{"type": "text", "text": prompt}]
        if image_bytes:
            b64 = base64.b64encode(image_bytes).decode()
            content.append({"type": "image_url",
                             "image_url": {"url": f"data:{mime_type};base64,{b64}"}})
        try:
            resp = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": DYNAMIC_SCENE_PROMPT},
                    {"role": "user",   "content": content},
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.1,
            )
        except Exception:
            resp = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": DYNAMIC_SCENE_PROMPT},
                    {"role": "user",   "content": content},
                ],
                model=self.model,
                temperature=0.1,
            )
        return resp.choices[0].message.content

    def _gemini_dynamic(self, prompt: str, image_bytes, mime_type) -> str:
        parts = [DYNAMIC_SCENE_PROMPT, prompt]
        if image_bytes:
            parts.append({"mime_type": mime_type, "data": image_bytes})
        resp = self.json_model.generate_content(
            [{"role": "user", "parts": parts}],
            generation_config={"response_mime_type": "application/json", "temperature": 0.1},
        )
        return resp.text

    def _fallback_scene(self, topic: str, prompt: str) -> dict:
        return {
            "topic": topic, "subject": "other",
            "chapters": [{
                "id": "intro", "title": "Scene",
                "narration": f"Visualisation of: {topic}",
                "camera": {"position": [10, 8, 10], "target": [0, 2, 0], "fov": 45},
                "objects": [
                    {"id": "ground", "type": "plane", "position": [0, 0, 0],
                     "color": "#83C167", "args": [20, 20], "visible": True},
                    {"id": "axes", "type": "axes", "position": [0, 0, 0],
                     "args": [4], "color": "#888888", "visible": True},
                ],
                "annotations": [], "reveal_ids": [], "hide_ids": [],
                "autoplay": True, "loop": False, "duration_hint": 4.0,
            }],
        }

    # ── Teaching narration ────────────────────
    # Phase 2: returns (clean_text, should_advance, highlight_id)

    def generate_narration(
        self,
        session: Session,
        student_message: str,
        frame_bytes: Optional[bytes] = None,
    ) -> tuple[str, bool, Optional[str]]:
        chapter = session.current_chapter()

        # Build object id list so the LLM knows what's available to highlight
        obj_ids = [o.id for o in chapter.objects]
        context = (
            f"Chapter: {chapter.title}\n"
            f"Script: {chapter.narration}\n"
            f"Available object IDs for [HIGHLIGHT]: {obj_ids}\n"
            f"Student: {student_message}"
        )

        if self.provider == "gemini" and frame_bytes:
            raw_text = self._gemini_teach(context, session.history, frame_bytes)
        else:
            raw_text = self._groq_teach(context, session.history)

        # Lesson progression is controlled by the frontend player, never by chat.
        advance = False

        # Extract [HIGHLIGHT: object_id] — capture the id, strip the tag
        highlight_id: Optional[str] = None
        highlight_match = re.search(r'\[HIGHLIGHT:\s*([^\]]+)\]', raw_text, re.IGNORECASE)
        if highlight_match:
            highlight_id = highlight_match.group(1).strip()

        # Strip both tags from the spoken text
        clean = re.sub(r'\[HIGHLIGHT:[^\]]*\]', '', raw_text, flags=re.IGNORECASE)
        clean = re.sub(r'\n?ADVANCE\s*$', '', clean, flags=re.IGNORECASE).strip()

        return clean, advance, highlight_id

    def _groq_teach(self, context: str, history: list) -> str:
        messages = [{"role": "system", "content": TEACHING_SYSTEM_PROMPT}]
        messages += history[-6:]
        messages.append({"role": "user", "content": context})
        resp = self.client.chat.completions.create(
            messages=messages, model=self.model
        )
        return resp.choices[0].message.content

    def _gemini_teach(self, context: str, history: list, frame_bytes: bytes) -> str:
        parts = [TEACHING_SYSTEM_PROMPT, context]
        if frame_bytes:
            parts.append({"mime_type": "image/jpeg", "data": frame_bytes})
        resp = self.vision_model.generate_content([{"role": "user", "parts": parts}])
        return resp.text

    # ── Interactive Teaching (new) ────────────

    def generate_interactive_step(
        self,
        session: Session,
        student_message: str,
        frame_bytes: Optional[bytes] = None,
    ) -> tuple:
        """
        Generate an interactive teaching step with questions and options.
        Returns: (narration, interactive_options, step_type, highlight_id, chapter_index)
        """
        # Let's count chapters and let LLM know what the chapters are!
        chapters_info = [
            f"Chapter {i}: {ch.title} - {ch.narration}"
            for i, ch in enumerate(session.scene.chapters)
        ]
        chapters_str = "\n".join(chapters_info)

        chapter = session.current_chapter()
        obj_ids = [o.id for o in chapter.objects]

        context = (
            f"Scene Chapters structure:\n{chapters_str}\n\n"
            f"Current Chapter Index: {session.current_chapter_index}\n"
            f"Current Chapter Title: {chapter.title}\n"
            f"Current Chapter Script: {chapter.narration}\n"
            f"Available objects in current chapter: {obj_ids}\n"
            f"Student message: {student_message}"
        )

        raw_text = (
            self._gemini_interactive_teach(context, session.history)
            if self.provider == "gemini"
            else self._groq_interactive_teach(context, session.history)
        )
        parsed = self._parse_json(raw_text)

        # Extract fields from parsed JSON
        question = parsed.get("question", "")
        step_type = parsed.get("step_type", "question")
        highlight_id = parsed.get("highlight_id")
        options_data = parsed.get("options", [])
        
        # Determine the chapter_index. If not present in JSON, use the current index.
        chapter_index = parsed.get("chapter_index", session.current_chapter_index)

        # Build interactive options
        from .schema import InteractiveOption
        options = [
            InteractiveOption(
                id=opt.get("id", f"opt_{i}"), 
                text=opt.get("text", ""),
                type=opt.get("type", "choice")
            )
            for i, opt in enumerate(options_data)
        ]

        return question, options, step_type, highlight_id, chapter_index

    def _groq_interactive_teach(self, context: str, history: list) -> str:
        """Call Groq with interactive teaching prompt"""
        messages = [{"role": "system", "content": INTERACTIVE_TEACHING_PROMPT}]
        messages += history[-6:]
        messages.append({"role": "user", "content": context})

        try:
            resp = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                response_format={"type": "json_object"},
            )
        except Exception:
            resp = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
            )

        return resp.choices[0].message.content

    def _gemini_interactive_teach(self, context: str, history: list) -> str:
        """Call Gemini with interactive teaching prompt (JSON mode)."""
        parts = [INTERACTIVE_TEACHING_PROMPT, context]
        resp = self.json_model.generate_content(
            [{"role": "user", "parts": parts}],
            generation_config={"response_mime_type": "application/json", "temperature": 0.3},
        )
        return resp.text
