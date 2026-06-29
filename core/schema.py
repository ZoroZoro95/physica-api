from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, Any
from uuid import uuid4


# ─────────────────────────────────────────────
# Constraints (pulleys, ropes, levers, surfaces)
# ─────────────────────────────────────────────

ConstraintType = Literal["rope", "rigid", "surface", "pivot", "gear"]

class Constraint(BaseModel):
    type: ConstraintType
    object_ids: list[str]
    relationship: str
    ratio: Optional[float] = None


# ─────────────────────────────────────────────
# Cinematic Camera
# ─────────────────────────────────────────────

class CameraState(BaseModel):
    position: list[float] = Field(default=[12.0, 8.0, 12.0], min_length=3, max_length=3)
    target: list[float] = Field(default=[0.0, 0.0, 0.0], min_length=3, max_length=3)
    fov: float = 45.0
    transition_duration: float = 1.2
    ease: Literal["linear", "easeIn", "easeOut", "easeInOut"] = "easeInOut"


# ─────────────────────────────────────────────
# Scene effects
# ─────────────────────────────────────────────

class SceneEffects(BaseModel):
    background_color: str = "#0f0f1a"
    fog: bool = False
    grid: bool = True
    bloom: bool = True
    ambient_intensity: float = 0.6
    directional_intensity: float = 1.2


# ─────────────────────────────────────────────
# Scene Object
# ─────────────────────────────────────────────

ObjectType = Literal[
    "sphere", "box", "plane", "cylinder",
    "line", "arrow", "axes", "trail",
    "rope", "spring", "arc", "label"
]

class SceneObject(BaseModel):
    id: str
    type: ObjectType
    position: list[float] = Field(..., min_length=3, max_length=3)
    rotation: list[float] = Field(default=[0.0, 0.0, 0.0], min_length=3, max_length=3)
    color: str = "#888888"
    label: Optional[str] = None
    label_always_visible: bool = False
    args: Optional[list] = None
    path: Optional[list[list[float]]] = None
    rotation_path: Optional[list[list[float]]] = None
    physics_intent: Optional[dict] = None
    visible: bool = True
    opacity: float = 1.0
    emissive: bool = False
    emissive_intensity: float = 0.4

    @field_validator("path")
    @classmethod
    def path_must_be_3d(cls, v):
        if v is not None:
            for pt in v:
                if len(pt) != 3:
                    raise ValueError("Each path point must be [x, y, z]")
        return v

    @field_validator("color")
    @classmethod
    def color_must_be_hex(cls, v):
        if not v.startswith("#"):
            raise ValueError(f"Color must be hex like #FF0000, got: {v}")
        return v


# ─────────────────────────────────────────────
# Annotation
# ─────────────────────────────────────────────

class Annotation(BaseModel):
    id: str
    text: str
    position: list[float] = Field(..., min_length=3, max_length=3)
    color: str = "#FFFFFF"
    size: Literal["sm", "md", "lg"] = "md"
    fade_in_chapter: str = ""
    path: Optional[list[list[float]]] = None


# ─────────────────────────────────────────────
# Chapter
# ─────────────────────────────────────────────

class Chapter(BaseModel):
    id: str
    title: str
    narration: str
    camera: CameraState = Field(default_factory=CameraState)
    objects: list[SceneObject]
    annotations: list[Annotation] = Field(default=[])
    constraints: list[Constraint] = Field(default=[])
    reveal_ids: list[str] = Field(default=[])
    hide_ids: list[str] = Field(default=[])
    autoplay: bool = True
    loop: bool = False
    duration_hint: float = Field(default=6.0)
    formula: Optional[str] = None
    derivation: Optional[str] = None


# ─────────────────────────────────────────────
# Full Scene
# ─────────────────────────────────────────────

class PhysicsScene(BaseModel):
    topic: str
    subject: Literal[
        "projectile_basic", "projectile_split", "projectile_collision",
        "projectile_moving_cart", "projectile_relative", "projectile_curvature",
        "projectile_piecewise", "projectile_inclined", "projectile_angle_pair",
        "projectile_monkey_gun", "projectile_wall", "projectile_intercept",
        "projectile_moving_wedge",
        "projectile_motion", "shm", "circular_motion",
        "electrostatics", "waves", "mechanics", "other"
    ] = "other"
    storyboard: Optional[str] = None
    effects: SceneEffects = Field(default_factory=SceneEffects)
    chapters: list[Chapter] = Field(..., min_length=1)

    @field_validator("chapters")
    @classmethod
    def must_have_chapters(cls, v):
        if not v:
            raise ValueError("Scene must have at least one chapter")
        return v


# ─────────────────────────────────────────────
# Session
# ─────────────────────────────────────────────

class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    scene: PhysicsScene
    current_chapter_index: int = 0
    history: list[dict] = Field(default=[])
    completed: bool = False

    def current_chapter(self) -> Chapter:
        return self.scene.chapters[self.current_chapter_index]

    def advance(self) -> bool:
        if self.current_chapter_index < len(self.scene.chapters) - 1:
            self.current_chapter_index += 1
            return True
        self.completed = True
        return False


# ─────────────────────────────────────────────
# Interactive Tutoring
# ─────────────────────────────────────────────

class InteractiveOption(BaseModel):
    """A single option for student interaction"""
    id: str  # unique within this step
    text: str  # display text
    type: Literal["yes", "no", "choice", "continue"] = "choice"  # button type


class TutorStep(BaseModel):
    """A single teaching step with question and options"""
    step_id: str = Field(default_factory=lambda: str(uuid4()))
    step_type: Literal["introduction", "given", "question", "explanation", "solving", "understanding", "testing", "formula", "final"] = "question"
    question: str  # main teaching content or question
    follow_up: Optional[str] = None  # optional context/follow-up
    options: list[InteractiveOption] = Field(default=[])  # interaction options for student
    highlight_id: Optional[str] = None  # 3D object to highlight
    chapter_index: int = 0  # which chapter this step belongs to
    optional_clarification: Optional[str] = None  # doubt feedback if student asks


# ─────────────────────────────────────────────
# Image Question Extraction
# ─────────────────────────────────────────────

DiagramEntityKind = Literal[
    "point", "line", "incline", "axis", "projectile", "target",
    "wall", "staircase", "velocity_arrow", "angle", "distance",
    "height", "surface", "other"
]

class DiagramEntity(BaseModel):
    id: str
    kind: DiagramEntityKind
    label: Optional[str] = None
    label_display: Optional[str] = None
    label_solver: Optional[str] = None
    value: Optional[str] = None
    unit: Optional[str] = None
    description: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DiagramExtraction(BaseModel):
    present: bool = False
    type: Literal[
        "none", "basic_projectile", "incline", "staircase", "target",
        "wall", "two_inclines", "3d_axes", "other"
    ] = "none"
    entities: list[DiagramEntity] = Field(default=[])
    coordinate_system: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ExtractQuestionResponse(BaseModel):
    debug_report_id: Optional[str] = None
    debug_report_path: Optional[str] = None
    question_text: str
    question_text_raw: str = ""
    question_text_display: str = ""
    question_text_solver: str = ""
    cleaned_prompt: str
    is_projectile_question: bool
    question_type: Literal["mcq", "subjective", "unknown"] = "unknown"
    options: list[str] = Field(default=[])
    diagram: DiagramExtraction = Field(default_factory=DiagramExtraction)
    givens: list[str] = Field(default=[])
    requested_quantity: Optional[str] = None
    suggested_engine_case: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_review: bool = True
    warnings: list[str] = Field(default=[])


class SolveQuestionRequest(BaseModel):
    debug_report_id: Optional[str] = None
    question_text_solver: str
    options: list[str] = Field(default=[])
    suggested_engine_case: Optional[str] = None
    givens: list[str] = Field(default=[])
    requested_quantity: Optional[str] = None
    diagram: Optional[DiagramExtraction] = None


class WalkthroughStep(BaseModel):
    id: str
    title: str
    student_goal: str = ""
    teaching_goal: str = ""
    visual_action: str = ""
    concept_used: str = ""
    formula: str = ""
    equation: str = ""
    substitution: str = ""
    calculation: str = ""
    result: str = ""
    explanation: str
    trap_note: str = ""
    animation_intent: str = ""
    focus_ids: list[str] = Field(default=[])
    camera_target_ids: list[str] = Field(default_factory=list)
    highlight_ids: list[str] = Field(default_factory=list)
    animation_focus: str = ""
    objects_to_highlight: list[str] = Field(default_factory=list)
    known_values: list[str] = Field(default_factory=list)
    next_known_values: list[str] = Field(default_factory=list)
    voiceover_text: str = ""


class ExplainerSubReveal(BaseModel):
    id: str
    text: str = ""
    visual_instruction: str = ""
    formula_lines: list[str] = Field(default_factory=list)
    reveal_ids: list[str] = Field(default_factory=list)
    highlight_ids: list[str] = Field(default_factory=list)
    visual_plan: dict[str, Any] = Field(default_factory=dict)


class ExplainerBeat(BaseModel):
    id: str
    step_id: str = ""
    title: str = ""
    learner_message: str = ""
    visual_instruction: str = ""
    animation_phase: str = ""
    formula_lines: list[str] = Field(default_factory=list)
    sub_reveals: list[ExplainerSubReveal] = Field(default_factory=list)
    reveal_ids: list[str] = Field(default_factory=list)
    highlight_ids: list[str] = Field(default_factory=list)
    why_it_matters: str = ""
    visual_plan: dict[str, Any] = Field(default_factory=dict)


class DiagramModel(BaseModel):
    kind: str = "none"
    coordinate_frame: dict[str, Any] = Field(default_factory=dict)
    points: dict[str, dict[str, Any]] = Field(default_factory=dict)
    surfaces: list[dict[str, Any]] = Field(default_factory=list)
    vectors: list[dict[str, Any]] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)


class EquationStepModel(BaseModel):
    id: str
    title: str
    equation: str = ""
    substitution: str = ""
    explanation: str = ""
    focus_ids: list[str] = Field(default_factory=list)


class EquationPlanModel(BaseModel):
    template_id: str = ""
    engine_case: str = ""
    goal: str = ""
    givens: list[str] = Field(default_factory=list)
    unknown: str = ""
    invariant: str = ""
    steps: list[EquationStepModel] = Field(default_factory=list)
    final_answer: str = ""
    exam_takeaway: str = ""


class SolutionWalkthrough(BaseModel):
    engine_case: str
    answer: Optional[str] = None
    matched_option: Optional[str] = None
    diagram_model: DiagramModel = Field(default_factory=DiagramModel)
    steps: list[WalkthroughStep] = Field(default=[])
    explainer_beats: list[ExplainerBeat] = Field(default_factory=list)


class SolveQuestionResponse(BaseModel):
    debug_report_id: Optional[str] = None
    debug_report_path: Optional[str] = None
    status: Literal["passed", "failed", "unsupported", "needs_review"]
    engine_case: Optional[str] = None
    template_id: Optional[str] = None
    template_confidence: Optional[float] = None
    template_reason: str = ""
    template_warnings: list[str] = Field(default_factory=list)
    diagram_valid: Optional[bool] = None
    diagram_warnings: list[str] = Field(default_factory=list)
    equation_plan: Optional[EquationPlanModel] = None
    answer: Optional[str] = None
    matched_option: Optional[str] = None
    computed_value: Optional[float] = None
    trace: list[str] = Field(default=[])
    walkthrough: Optional[SolutionWalkthrough] = None
    animation_scene_spec: Optional[dict[str, Any]] = None
    reason: str = ""
    feedback_ticket_id: Optional[str] = None
    feedback_status: Optional[str] = None


class AuthGoogleRequest(BaseModel):
    id_token: str


class AuthUserResponse(BaseModel):
    token: str
    user: dict[str, Any]


class FeedbackTicketRequest(BaseModel):
    question_text_solver: str
    debug_report_id: Optional[str] = None
    solve_request: dict[str, Any] = Field(default_factory=dict)
    solve_response: dict[str, Any] = Field(default_factory=dict)


class FeedbackRetryResponse(BaseModel):
    checked: int
    resolved: int
    still_open: int
    resolved_ticket_ids: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────
# API shapes
# ─────────────────────────────────────────────

class GenerateRequest(BaseModel):
    prompt: str
    image_base64: Optional[str] = None
    image_mime_type: str = "image/jpeg"

class TeachRequest(BaseModel):
    session_id: str
    student_message: str
    frame_base64: Optional[str] = None
    current_chapter_index: Optional[int] = None
    interactive_mode: bool = True  # Enable interactive step-by-step tutoring

class GenerateResponse(BaseModel):
    session_id: str
    scene: PhysicsScene
    current_chapter: Chapter
    message: str

class TeachResponse(BaseModel):
    session_id: str
    narration: str  # main teaching content
    advance_chapter: bool
    next_chapter: Optional[Chapter] = None
    completed: bool = False
    # ── Interactive Tutoring ───────────────────
    current_step: Optional[TutorStep] = None  # structured interactive step
    interactive_options: list[InteractiveOption] = Field(default=[])  # options for student
    step_type: Literal["introduction", "given", "question", "explanation", "solving", "understanding", "testing", "formula", "final"] = "question"
    is_doubt_feedback: bool = False  # whether this is answering a doubt
    # ── Phase 1 additions ──────────────────────
    highlight_id: Optional[str] = None  # object id to pulse-highlight in the 3D scene
    step_number: int = 0  # current chapter index at time of response
