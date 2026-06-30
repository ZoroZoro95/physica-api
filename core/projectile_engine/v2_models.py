from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from enum import Enum

# ------------------------------------------------------------------------------
# Stage 1: Physics Facts
# ------------------------------------------------------------------------------

class FactObject(BaseModel):
    id: str
    type: str

class FactSurface(BaseModel):
    id: str
    type: str
    angle_deg: Optional[float] = None
    smooth: Optional[bool] = None

class FactAction(BaseModel):
    object_id: str
    type: str
    direction: Optional[str] = None
    speed: Optional[str] = None
    surface_id: Optional[str] = None

class FactEvent(BaseModel):
    type: str
    objects: List[str]
    time_sec: Optional[float] = None

class FactUnknown(BaseModel):
    symbol: str
    quantity: str

class PhysicsFacts(BaseModel):
    objects: List[FactObject]
    surfaces: List[FactSurface]
    actions: List[FactAction]
    events: List[FactEvent]
    known_values: Dict[str, Any]
    unknown: FactUnknown


# ------------------------------------------------------------------------------
# Stage 2: Scene Graph
# ------------------------------------------------------------------------------

class WorldConfig(BaseModel):
    gravity: float = 10.0

class VectorMagnitudeDir(BaseModel):
    magnitude: Any
    direction: Optional[str] = None

class SceneObject(BaseModel):
    id: str
    kind: str
    position: Optional[str] = None
    initial_velocity: Optional[VectorMagnitudeDir] = None

class SceneSurface(BaseModel):
    id: str
    kind: str
    angle_deg: Optional[float] = None

class SceneEvent(BaseModel):
    kind: str
    time_sec: Optional[float] = None

class SceneGraph(BaseModel):
    world: WorldConfig
    objects: List[SceneObject]
    surfaces: List[SceneSurface]
    events: List[SceneEvent]


# ------------------------------------------------------------------------------
# Stage 3: Physics Solver Result
# ------------------------------------------------------------------------------

class SolverAnswer(BaseModel):
    symbol: str
    value: Any
    unit: str

class EquationRecord(BaseModel):
    id: str
    latex: str

class SolverResult(BaseModel):
    answer: Optional[SolverAnswer] = None
    equations: List[EquationRecord] = Field(default_factory=list)
    reasoning: List[str] = Field(default_factory=list)


# ------------------------------------------------------------------------------
# Stage 4: Concept Graph
# ------------------------------------------------------------------------------

class Concept(str, Enum):
    # Coordinate system concepts
    ROTATED_AXES = "rotated_axes"
    GRAVITY_RESOLUTION = "gravity_resolution"
    INDEPENDENT_AXES = "independent_axes"

    # Incline-specific
    SHADOW_PROJECTION = "shadow_projection"
    SAME_PARALLEL_MOTION = "same_parallel_motion"
    PERPENDICULAR_RETURN = "perpendicular_return"

    # Basic projectile
    CONSTANT_HORIZONTAL_VELOCITY = "constant_horizontal_velocity"
    VERTICAL_FREE_FALL = "vertical_free_fall"
    PARABOLIC_TRAJECTORY = "parabolic_trajectory"
    SYMMETRY_OF_FLIGHT = "symmetry_of_flight"

    # Height-based
    LAUNCH_FROM_HEIGHT = "launch_from_height"
    HORIZONTAL_THROW = "horizontal_throw"

    # Angle/range
    COMPLEMENTARY_ANGLES = "complementary_angles"
    MAX_RANGE_AT_45 = "max_range_at_45"
    RANGE_EQUALS_HEIGHT = "range_equals_height"

    # Relative motion
    RELATIVE_VELOCITY = "relative_velocity"
    ZERO_RELATIVE_ACCELERATION = "zero_relative_acceleration"
    MONKEY_GUN_PRINCIPLE = "monkey_gun_principle"

    # Collision
    PROJECTILE_COLLISION = "projectile_collision"
    SAME_LAUNCH_POINT = "same_launch_point"

    # Split / explosion
    SPLIT_AT_APEX = "split_at_apex"
    MOMENTUM_CONSERVATION = "momentum_conservation"

    # Bounce
    COEFFICIENT_OF_RESTITUTION = "coefficient_of_restitution"
    ENERGY_LOSS_ON_BOUNCE = "energy_loss_on_bounce"

    # Wall / target
    WALL_CLEARANCE = "wall_clearance"
    TARGET_INTERCEPT = "target_intercept"
    MINIMUM_SPEED_CONDITION = "minimum_speed_condition"

    # Piecewise
    PIECEWISE_GRAVITY = "piecewise_gravity"


# ------------------------------------------------------------------------------
# Stage 5: Visual Primitives
# ------------------------------------------------------------------------------

class PrimitiveType(str, Enum):
    # ── Universal setup / inspection ─────────────────────────────────────────
    SHOW_SETUP                    = "show_setup"              # Static scene, label everything
    HIGHLIGHT_OBJECT              = "highlight_object"        # Pulse/glow one object
    LABEL_GIVEN_VALUES            = "label_given_values"      # Annotate given numbers on scene
    FREEZE_FRAME                  = "freeze_frame"            # Pause + zoom into an event point
    PLAY_RAW_MOTION               = "play_raw_motion"         # Full trajectory animation
    SLOW_MOTION                   = "slow_motion"             # Same motion at 0.25x speed
    REPLAY_MOTION                 = "replay_motion"           # Loop the trajectory once more

    # ── Vector decomposition ──────────────────────────────────────────────────
    SPLIT_VECTOR                  = "split_vector"            # Animate Vx, Vy splitting from V
    DRAW_VELOCITY_ARROW           = "draw_velocity_arrow"     # Draw V vector at a point
    ANIMATE_VX_CONSTANT           = "animate_vx_constant"    # Show Vx unchanging across frames
    ANIMATE_VY_CHANGING           = "animate_vy_changing"    # Show Vy decreasing, reversing
    SHOW_VELOCITY_AT_APEX         = "show_velocity_at_apex"  # Vy=0 at peak, only Vx remains
    SHOW_VELOCITY_COMPONENTS_LIVE = "show_velocity_components_live"  # Live updating Vx/Vy bars

    # ── Coordinate / axis transforms ─────────────────────────────────────────
    ROTATE_AXES                   = "rotate_axes"             # Smoothly tilt world frame to incline
    SHOW_INCLINE_COMPONENTS       = "show_incline_components" # g_parallel & g_perpendicular on incline
    SHOW_NORMAL_VECTOR            = "show_normal_vector"      # Draw normal to incline surface

    # ── Incline-specific ─────────────────────────────────────────────────────
    SHOW_SHADOW_PROJECTION        = "show_shadow_projection"  # Project P shadow onto plane
    COMPARE_PARALLEL_MOTION       = "compare_parallel_motion" # Side-by-side along-plane motion
    ISOLATE_PERPENDICULAR_MOTION  = "isolate_perpendicular_motion" # Only perp-to-plane channel
    ANIMATE_INCLINE_LAUNCH        = "animate_incline_launch"  # Launch up/across incline

    # ── Height launch ─────────────────────────────────────────────────────────
    SHOW_CLIFF                    = "show_cliff"              # Draw cliff / tower geometry
    ANIMATE_HORIZONTAL_THROW      = "animate_horizontal_throw" # Vx only at launch
    SHOW_DROP_LINE                = "show_drop_line"          # Vertical drop reference line

    # ── Range / symmetry ─────────────────────────────────────────────────────
    SHOW_RANGE_BRACKET            = "show_range_bracket"      # Horizontal range arrow
    SHOW_HEIGHT_MARKER            = "show_height_marker"      # Vertical height dashed line
    SHOW_FLIGHT_TIME_TIMER        = "show_flight_time_timer"  # Counting timer overlaid
    HIGHLIGHT_APEX                = "highlight_apex"          # Glow at peak point
    SHOW_ANGLE_ARC                = "show_angle_arc"          # Draw launch angle arc
    SHOW_COMPLEMENTARY_ANGLES     = "show_complementary_angles" # Both θ and 90°-θ arcs
    SHOW_SAME_RANGE               = "show_same_range"         # Overlay two paths with same R

    # ── Relative motion / Monkey-Gun ─────────────────────────────────────────
    SHOW_TWO_OBJECTS              = "show_two_objects"        # Both objects simultaneously
    ANIMATE_RELATIVE_MOTION       = "animate_relative_motion" # Motion of A relative to B
    MONKEY_GUN_DROP               = "monkey_gun_drop"         # Monkey drops, dart fires together
    SHOW_COMMON_FRAME             = "show_common_frame"       # Frame where gravity cancels

    # ── Collision of two projectiles ─────────────────────────────────────────
    SHOW_COLLISION_POINT          = "show_collision_point"    # Mark where paths intersect
    ANIMATE_COLLISION             = "animate_collision"       # Both particles meet at C
    SHOW_PARAMETRIC_PATHS         = "show_parametric_paths"   # x(t),y(t) for both

    # ── Split / Explosion at apex ─────────────────────────────────────────────
    SHOW_PRE_SPLIT_MOTION         = "show_pre_split_motion"   # Normal flight up to apex
    ANIMATE_SPLIT_EXPLOSION       = "animate_split_explosion" # Fragments diverge at apex
    SHOW_FRAGMENT_PATHS           = "show_fragment_paths"     # Each fragment's arc
    MOMENTUM_ARROW_BALANCE        = "momentum_arrow_balance"  # Before/after momentum arrows

    # ── Bounce / Restitution ─────────────────────────────────────────────────
    ANIMATE_BOUNCE                = "animate_bounce"          # Ball bounces off floor
    SHOW_RESTITUTION_RATIO        = "show_restitution_ratio"  # e = v_after / v_before diagram
    SHOW_ENERGY_BAR               = "show_energy_bar"         # KE bar decreasing each bounce

    # ── Wall / Target ─────────────────────────────────────────────────────────
    SHOW_WALL                     = "show_wall"               # Draw the wall obstacle
    ANIMATE_WALL_CLEAR            = "animate_wall_clear"      # Projectile just clears wall
    SHOW_TARGET                   = "show_target"             # Mark the target point
    ANIMATE_TARGET_HIT            = "animate_target_hit"      # Projectile reaches target
    SHOW_MIN_SPEED_ENVELOPE       = "show_min_speed_envelope" # Draw the parabola of safety

    # ── Piecewise gravity ────────────────────────────────────────────────────
    SHOW_GRAVITY_BOUNDARY         = "show_gravity_boundary"   # Horizontal line where g changes
    ANIMATE_PIECEWISE_MOTION      = "animate_piecewise_motion" # Different curves above/below

    # ── Math overlays ────────────────────────────────────────────────────────
    SHOW_EQUATION                 = "show_equation"           # Bring up LaTeX equation
    SUBSTITUTE_VALUES             = "substitute_values"       # Fill numbers into equation
    DERIVE_STEP                   = "derive_step"             # Animate one algebraic step
    HIGHLIGHT_KEY_TERM            = "highlight_key_term"      # Pulse one term in equation
    SHOW_REASONING_TEXT           = "show_reasoning_text"     # Display a reasoning sentence
    FINAL_ANSWER                  = "final_answer"            # Big answer reveal

class VisualPrimitive(BaseModel):
    primitive_type: PrimitiveType
    duration_sec: float
    camera_view: str
    targets: List[str] = Field(default_factory=list)
    text_overlay: Optional[str] = None
    equation_id: Optional[str] = None


# ------------------------------------------------------------------------------
# Stage 6 & 7: Storyboard & Narration
# ------------------------------------------------------------------------------

class StoryboardStep(BaseModel):
    primitive: VisualPrimitive
    physics_reason: str = ""

class NarrationStep(BaseModel):
    narration_text: str


# ------------------------------------------------------------------------------
# Stage 8: Timeline Builder
# ------------------------------------------------------------------------------

class TimelineBlock(BaseModel):
    start_sec: float
    end_sec: float
    primitive_type: str
    camera_view: str
    narration: str
    overlays: List[str] = Field(default_factory=list)

class Timeline(BaseModel):
    timeline: List[TimelineBlock]
