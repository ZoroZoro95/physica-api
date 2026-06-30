"""
projectile_solver.py — Exact analytical solutions for all projectile motion subtypes.

DESIGN PRINCIPLE
  The LLM's only job: classify the problem + extract raw numbers from text.
  This module's job: solve everything exactly using high-school physics.
  No approximations, no LLM math.

UNITS
  All inputs:  REAL-WORLD units (m, m/s, degrees, kg, seconds).
  All outputs: REAL-WORLD units PLUS scene-unit equivalents where needed.
  scene_templates.py converts to scene units for rendering.

SUPPORTED SUBTYPES
  projectile_basic      — angle launch / horizontal throw / drop from height
  projectile_split      — projectile explodes at peak; momentum conservation
  projectile_collision  — two projectiles; find if/when/where they meet
  projectile_moving_cart— projectile launched from / lands on a moving cart
  projectile_relative   — relative velocity / relative trajectory questions
  projectile_curvature  — radius of curvature at a point along trajectory
  projectile_piecewise  — variable gravity (e.g. two-zone atmosphere)
"""

import math
import re
from dataclasses import dataclass, field
from typing import Optional


def safe_get_float(params: dict, key: str, default: float = 0.0) -> float:
    """Safely extracts a float from params, handling units and expressions."""
    v = params.get(key)
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        # Remove units (m, m/s, kg, degrees)
        v = re.sub(r'\s*[a-zA-Z/°]+$', '', v.strip())
        try:
            if any(op in v for op in ["*", "/", "+", "-"]):
                # Simple math expression evaluation
                return float(eval(v, {"__builtins__": None, "math": math}, {}))
            return float(v)
        except Exception:
            # Fallback: remove everything except numbers, dots, and minus
            v_clean = re.sub(r'[^0-9\.\-]', '', v)
            try:
                return float(v_clean)
            except Exception:
                return default
    return default


# ─────────────────────────────────────────────
# Shared constants
# ─────────────────────────────────────────────

DEFAULT_G = 10.0   # m/s²  (JEE standard; extracted value overrides)


# ─────────────────────────────────────────────
# Data classes — typed, explicit, no magic dicts
# ─────────────────────────────────────────────

@dataclass
class Vec2:
    x: float
    y: float

    def magnitude(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2)

    def angle_deg(self) -> float:
        """Angle above positive x-axis, degrees."""
        return math.degrees(math.atan2(self.y, self.x))

    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.y - other.y)

    def scale(self, k: float) -> "Vec2":
        return Vec2(self.x * k, self.y * k)


@dataclass
class ProjectileState:
    """Kinematic snapshot at a single time instant."""
    t: float           # seconds since launch
    x: float           # metres
    y: float           # metres
    vx: float          # m/s
    vy: float          # m/s

    @property
    def speed(self) -> float:
        return math.sqrt(self.vx ** 2 + self.vy ** 2)

    @property
    def angle_deg(self) -> float:
        return math.degrees(math.atan2(self.vy, self.vx))

    @property
    def pos(self) -> Vec2:
        return Vec2(self.x, self.y)

    @property
    def vel(self) -> Vec2:
        return Vec2(self.vx, self.vy)


@dataclass
class BasicSolution:
    """Solution for a standard projectile (no splitting, no interaction)."""
    # Inputs (real-world)
    v0: float
    angle_deg: float
    launch_height: float   # metres above ground
    g: float

    # Derived at launch
    vx0: float = field(init=False)
    vy0: float = field(init=False)

    # Key results
    t_peak: float = field(init=False)
    t_flight: float = field(init=False)
    x_range: float = field(init=False)
    y_peak: float = field(init=False)       # height above ground at peak
    y_peak_above_launch: float = field(init=False)
    v_at_peak: float = field(init=False)    # = vx0
    v_at_landing: float = field(init=False)
    vy_at_landing: float = field(init=False)

    # Path (20 points, real-world metres)
    path_real: list = field(default_factory=list)

    def __post_init__(self):
        rad = math.radians(self.angle_deg)
        self.vx0 = self.v0 * math.cos(rad)
        self.vy0 = self.v0 * math.sin(rad)
        self._solve()

    def _solve(self):
        g = self.g
        vx, vy0, sy = self.vx0, self.vy0, self.launch_height

        # Time to peak: vy0 - g*t = 0
        self.t_peak = vy0 / g if g > 0 else 0.0

        # Peak height above launch
        self.y_peak_above_launch = (vy0 ** 2) / (2 * g) if g > 0 else 0.0
        self.y_peak = sy + self.y_peak_above_launch

        # Time of flight: sy + vy0*t - 0.5*g*t² = 0
        # 0.5g t² - vy0 t - sy = 0
        a = 0.5 * g
        b = -vy0
        c = -sy
        disc = b * b - 4 * a * c
        if disc < 0 or a == 0:
            self.t_flight = 2 * self.t_peak if self.t_peak > 0 else 4.0
        else:
            t1 = (-b + math.sqrt(disc)) / (2 * a)
            t2 = (-b - math.sqrt(disc)) / (2 * a)
            candidates = [t for t in [t1, t2] if t > 0.001]
            self.t_flight = max(candidates) if candidates else 4.0

        self.x_range = vx * self.t_flight
        self.vy_at_landing = vy0 - g * self.t_flight
        self.v_at_landing = math.sqrt(vx ** 2 + self.vy_at_landing ** 2)
        self.v_at_peak = abs(vx)

        # Build 20-point path in real metres
        self.path_real = []
        for i in range(20):
            t = i / 19 * self.t_flight
            x = vx * t
            y = sy + vy0 * t - 0.5 * g * t ** 2
            y = max(y, 0.0)
            self.path_real.append([x, y])

    def state_at(self, t: float) -> ProjectileState:
        """Kinematic state at time t (seconds after launch)."""
        t = min(t, self.t_flight)
        return ProjectileState(
            t=t,
            x=self.vx0 * t,
            y=self.launch_height + self.vy0 * t - 0.5 * self.g * t ** 2,
            vx=self.vx0,
            vy=self.vy0 - self.g * t,
        )


@dataclass
class SplitSolution:
    """
    Projectile splits at peak into two fragments.
    Conservation of momentum: m*vx_peak = m1*vx1 + m2*vx2
                               0 = m1*vy1 + m2*vy2  (vy at peak = 0)

    Typical JEE scenario: one fragment drops straight down (vx1=0, vy1=0 after split)
    so second fragment's velocity is found from momentum conservation.
    """
    # Phase 1: projectile up to split
    base: BasicSolution

    # Split parameters (all real-world)
    m_total: float       # total mass kg (or 1.0 for ratio problems)
    m1: float            # mass of fragment 1 kg
    m2: float            # mass of fragment 2 kg
    vx1_after: float     # fragment 1 horizontal velocity after split (m/s)
    vy1_after: float     # fragment 1 vertical velocity after split (m/s)

    # Derived
    split_pos: Vec2 = field(init=False)    # position of split (peak) in real metres
    vx2_after: float = field(init=False)
    vy2_after: float = field(init=False)
    t_frag1_land: float = field(init=False)
    t_frag2_land: float = field(init=False)
    x_frag1_land: float = field(init=False)    # absolute x from launch
    x_frag2_land: float = field(init=False)
    separation: float = field(init=False)      # |x2_land - x1_land|

    def __post_init__(self):
        b = self.base
        # Split happens at peak
        self.split_pos = Vec2(b.vx0 * b.t_peak, b.y_peak)

        # Momentum conservation (x): m*vx0 = m1*vx1 + m2*vx2
        vx2 = (self.m_total * b.vx0 - self.m1 * self.vx1_after) / self.m2
        self.vx2_after = vx2

        # Momentum conservation (y): 0 = m1*vy1 + m2*vy2
        # vy at peak = 0 so total y-momentum = 0
        vy2 = (-self.m1 * self.vy1_after) / self.m2
        self.vy2_after = vy2

        # Fragment 1 fall time from peak height with vy1_after
        self.t_frag1_land = _time_to_ground(self.split_pos.y, self.vy1_after, b.g)
        self.t_frag2_land = _time_to_ground(self.split_pos.y, self.vy2_after, b.g)

        self.x_frag1_land = self.split_pos.x + self.vx1_after * self.t_frag1_land
        self.x_frag2_land = self.split_pos.x + self.vx2_after * self.t_frag2_land
        self.separation = abs(self.x_frag2_land - self.x_frag1_land)

    def frag1_path(self) -> list:
        """20-point path of fragment 1 from split to landing (real metres, absolute coords)."""
        return _build_path(
            self.split_pos.x, self.split_pos.y,
            self.vx1_after, self.vy1_after,
            self.t_frag1_land, self.base.g,
        )

    def frag2_path(self) -> list:
        return _build_path(
            self.split_pos.x, self.split_pos.y,
            self.vx2_after, self.vy2_after,
            self.t_frag2_land, self.base.g,
        )


@dataclass
class CollisionSolution:
    """
    Two projectiles launched from (possibly different) points.
    Find if they collide — and if so, when and where.
    """
    # Projectile A
    ax0: float; ay0: float    # launch position (m)
    avx: float; avy: float    # launch velocity components (m/s)

    # Projectile B
    bx0: float; by0: float
    bvx: float; bvy: float

    g: float = DEFAULT_G

    # Results
    collides: bool = field(init=False)
    t_collision: Optional[float] = field(init=False, default=None)
    x_collision: Optional[float] = field(init=False, default=None)
    y_collision: Optional[float] = field(init=False, default=None)

    def __post_init__(self):
        # Position of A: (ax0 + avx*t,  ay0 + avy*t - 0.5g*t²)
        # Position of B: (bx0 + bvx*t,  by0 + bvy*t - 0.5g*t²)
        # Same gravity → the -0.5g*t² cancels in both y equations!
        # So collision requires:
        #   ax0 + avx*t = bx0 + bvx*t  →  t = (bx0-ax0) / (avx-bvx)   [if avx≠bvx]
        #   ay0 + avy*t = by0 + bvy*t  →  t = (by0-ay0) / (avy-bvy)   [if avy≠bvy]
        self.collides = False
        self.t_collision = None

        dx = self.bx0 - self.ax0
        dy = self.by0 - self.ay0
        dvx = self.avx - self.bvx
        dvy = self.avy - self.bvy

        if abs(dvx) < 1e-9 and abs(dvy) < 1e-9:
            # Same velocity — collide only if same launch point
            if abs(dx) < 1e-6 and abs(dy) < 1e-6:
                self.collides = True
                self.t_collision = 0.0
                self.x_collision = self.ax0
                self.y_collision = self.ay0
            return

        # Both x and y must give same t
        if abs(dvx) > 1e-9 and abs(dvy) > 1e-9:
            tx = dx / dvx
            ty = dy / dvy
            if abs(tx - ty) < 1e-6 and tx > 0:
                self.collides = True
                self.t_collision = tx
        elif abs(dvx) < 1e-9:
            # No x separation possible unless dx=0
            if abs(dx) < 1e-6 and abs(dvy) > 1e-9:
                ty = dy / dvy
                if ty > 0:
                    self.collides = True
                    self.t_collision = ty
        else:
            # No y velocity difference
            if abs(dy) < 1e-6 and abs(dvx) > 1e-9:
                tx = dx / dvx
                if tx > 0:
                    self.collides = True
                    self.t_collision = tx

        if self.collides and self.t_collision is not None:
            t = self.t_collision
            self.x_collision = self.ax0 + self.avx * t
            self.y_collision = self.ay0 + self.avy * t - 0.5 * self.g * t ** 2
            # Verify y ≥ 0
            if self.y_collision is not None and self.y_collision < -0.05:
                self.collides = False
                self.t_collision = None
                self.x_collision = None
                self.y_collision = None


@dataclass
class MovingCartSolution:
    """
    Projectile launched from a cart moving horizontally at speed u_cart.
    In the ground frame, launch velocity = (u_cart + vx_rel, vy_rel).
    Returns landing point in both frames.
    """
    u_cart: float        # cart speed in ground frame (m/s), rightward +
    vx_relative: float   # launch Vx as seen from cart (m/s)
    vy_relative: float   # launch Vy as seen from cart (m/s)
    launch_height: float = 0.0
    g: float = DEFAULT_G

    # Derived
    vx_ground: float = field(init=False)
    vy_ground: float = field(init=False)
    t_flight: float = field(init=False)
    x_land_ground: float = field(init=False)    # landing x in ground frame
    x_land_cart: float = field(init=False)      # landing x relative to cart launch point
    cart_pos_at_landing: float = field(init=False)  # cart's x when ball lands

    def __post_init__(self):
        self.vx_ground = self.u_cart + self.vx_relative
        self.vy_ground = self.vy_relative

        g = self.g
        vy0 = self.vy_ground
        sy = self.launch_height

        a = 0.5 * g
        b = -vy0
        c = -sy
        disc = b * b - 4 * a * c
        if disc < 0 or a == 0:
            self.t_flight = 2 * vy0 / g if g > 0 else 4.0
        else:
            t1 = (-b + math.sqrt(disc)) / (2 * a)
            t2 = (-b - math.sqrt(disc)) / (2 * a)
            candidates = [t for t in [t1, t2] if t > 0.001]
            self.t_flight = max(candidates) if candidates else 4.0

        self.x_land_ground = self.vx_ground * self.t_flight
        self.cart_pos_at_landing = self.u_cart * self.t_flight
        self.x_land_cart = self.x_land_ground - self.cart_pos_at_landing


@dataclass
class CurvatureSolution:
    """
    Radius of curvature of the trajectory at a specific time t_query.

    R = v³ / (g * |cos θ|)   where θ is the angle of velocity above horizontal.
    Equivalently R = v² / a_perp where a_perp = g*cosθ.
    """
    base: BasicSolution
    t_query: float    # seconds after launch at which to compute curvature

    # Results
    state_at_query: ProjectileState = field(init=False)
    radius_of_curvature: float = field(init=False)
    a_perp: float = field(init=False)    # component of g perpendicular to velocity

    def __post_init__(self):
        self.state_at_query = self.base.state_at(self.t_query)
        v = self.state_at_query.speed
        theta_rad = math.atan2(self.state_at_query.vy, self.state_at_query.vx)

        # Gravity is purely downward (-y). Component perpendicular to velocity:
        # a_perp = g * |cos(θ)| where θ is velocity angle from horizontal
        self.a_perp = self.base.g * abs(math.cos(theta_rad))

        if self.a_perp < 1e-9:
            # At the peak θ=0 → no perpendicular component → R = ∞ momentarily
            self.radius_of_curvature = float("inf")
        else:
            self.radius_of_curvature = (v ** 2) / self.a_perp


@dataclass
class PiecewiseGravitySolution:
    """
    Two-zone atmosphere: different g in two height bands.
    Zone 1: 0 ≤ y ≤ h_boundary, gravity = g1
    Zone 2: y > h_boundary,      gravity = g2

    Solves the trajectory by:
    1. Running zone-1 physics until the ball crosses h_boundary (upward).
    2. Running zone-2 physics from that handoff point until peak.
    3. Running zone-2 physics on the way back down until h_boundary.
    4. Running zone-1 physics back to ground.
    """
    vx0: float
    vy0: float
    launch_height: float    # must be < h_boundary for typical problem
    h_boundary: float       # altitude where gravity changes (m)
    g1: float               # gravity below boundary
    g2: float               # gravity above boundary

    # Results
    t_flight: float = field(init=False)
    x_range: float = field(init=False)
    y_peak: float = field(init=False)
    path_real: list = field(default_factory=list)
    segments: list = field(default_factory=list)   # list of phase dicts for narration

    def __post_init__(self):
        self._solve()

    def _solve(self):
        vx = self.vx0
        vy = self.vy0
        sy = self.launch_height
        h_b = self.h_boundary
        g1, g2 = self.g1, self.g2
        x = 0.0
        t = 0.0
        path = [[x, sy]]
        self.segments = []

        # Phase 1: zone 1 (y from sy up to h_boundary)
        # sy + vy*t - 0.5*g1*t² = h_b
        # 0.5g1 t² - vy t + (h_b - sy) = 0
        t_cross_up = _solve_quadratic_positive(0.5 * g1, -vy, (h_b - sy))
        if t_cross_up is None or t_cross_up <= 0:
            # Never reaches boundary — solve as single zone
            sol = BasicSolution(
                v0=math.sqrt(vx ** 2 + vy ** 2),
                angle_deg=math.degrees(math.atan2(vy, vx)),
                launch_height=sy, g=g1
            )
            self.t_flight = sol.t_flight
            self.x_range = sol.x_range
            self.y_peak = sol.y_peak
            self.path_real = [[p[0], p[1]] for p in sol.path_real]
            return

        vy_at_cross_up = vy - g1 * t_cross_up
        x_at_cross_up = x + vx * t_cross_up
        t += t_cross_up
        x = x_at_cross_up
        vy = vy_at_cross_up
        sy = h_b

        self.segments.append({
            "phase": "zone1_up",
            "duration": t_cross_up,
            "entry_vy": self.vy0,
            "exit_vy": vy_at_cross_up,
            "description": f"Rising through zone 1 (g={g1} m/s²) for {t_cross_up:.3f} s",
        })
        _append_segment(path, x_at_cross_up, h_b, vx, vy_at_cross_up, g1, t_cross_up, n=5)

        # Phase 2: zone 2 (y from h_boundary to peak)
        # Peak: vy_up - g2*dt = 0  → dt = vy_up / g2
        if g2 > 0 and vy > 0:
            dt_peak = vy / g2
            y_peak = h_b + vy * dt_peak - 0.5 * g2 * dt_peak ** 2
            x_peak = x + vx * dt_peak
            t += dt_peak
            x = x_peak
            vy_after_peak = 0.0
            self.y_peak = y_peak
            self.segments.append({
                "phase": "zone2_up",
                "duration": dt_peak,
                "entry_vy": vy_at_cross_up,
                "exit_vy": 0.0,
                "description": f"Rising through zone 2 (g={g2} m/s²) for {dt_peak:.3f} s, peak at {y_peak:.1f} m",
            })
            _append_segment(path, x, h_b, vx, vy, g2, dt_peak, n=5)

            # Phase 3: fall from peak back to h_boundary (zone 2)
            # h_b = y_peak - 0.5*g2*dt²  → dt = sqrt(2*(y_peak-h_b)/g2)
            fall_dist = y_peak - h_b
            if fall_dist > 0 and g2 > 0:
                dt_fall_z2 = math.sqrt(2 * fall_dist / g2)
                vy_enter_z1 = -g2 * dt_fall_z2   # downward
                x_at_reentry = x + vx * dt_fall_z2
                t += dt_fall_z2
                x = x_at_reentry
                vy = vy_enter_z1
                sy = h_b
                self.segments.append({
                    "phase": "zone2_down",
                    "duration": dt_fall_z2,
                    "entry_vy": 0.0,
                    "exit_vy": vy_enter_z1,
                    "description": f"Falling through zone 2 for {dt_fall_z2:.3f} s",
                })
                _append_segment(path, x_peak, y_peak, vx, 0.0, g2, dt_fall_z2, n=5)
        else:
            self.y_peak = h_b
            x_peak = x

        # Phase 4: fall from h_boundary to ground (zone 1)
        # h_b + vy*dt - 0.5*g1*dt² = 0
        t_land = _solve_quadratic_positive(0.5 * g1, -vy, h_b)
        if t_land is None:
            t_land = math.sqrt(2 * h_b / g1) if g1 > 0 else 2.0
        x_land = x + vx * t_land
        t += t_land
        self.segments.append({
            "phase": "zone1_down",
            "duration": t_land,
            "entry_vy": vy,
            "exit_vy": vy - g1 * t_land,
            "description": f"Falling through zone 1 for {t_land:.3f} s",
        })
        _append_segment(path, x, h_b, vx, vy, g1, t_land, n=5)

        self.t_flight = t
        self.x_range = x_land
        self.path_real = path


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _time_to_ground(y0: float, vy0: float, g: float) -> float:
    """Time for a projectile at height y0 with vertical velocity vy0 to hit y=0."""
    a = 0.5 * g
    b = -vy0
    c = -y0
    disc = b * b - 4 * a * c
    if disc < 0 or a == 0:
        return abs(vy0 / g) * 2 if g > 0 else 2.0
    t1 = (-b + math.sqrt(disc)) / (2 * a)
    t2 = (-b - math.sqrt(disc)) / (2 * a)
    candidates = [t for t in [t1, t2] if t > 0.001]
    return max(candidates) if candidates else 2.0


def _solve_quadratic_positive(a: float, b: float, c: float) -> Optional[float]:
    """Returns smallest positive root of at² + bt + c = 0, or None."""
    if abs(a) < 1e-12:
        if abs(b) < 1e-12:
            return None
        t = -c / b
        return t if t > 0.001 else None
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    t1 = (-b + math.sqrt(disc)) / (2 * a)
    t2 = (-b - math.sqrt(disc)) / (2 * a)
    candidates = sorted([t for t in [t1, t2] if t > 0.001])
    return candidates[0] if candidates else None


def _build_path(x0, y0, vx, vy0, duration, g, n=20):
    """Build n-point path in real metres starting from (x0,y0)."""
    pts = []
    for i in range(n):
        t = i / (n - 1) * duration
        x = x0 + vx * t
        y = y0 + vy0 * t - 0.5 * g * t ** 2
        pts.append([x, max(y, 0.0)])
    return pts


def _append_segment(path, x0, y0, vx, vy0, g, duration, n=5):
    """Append n points to path list (skips first point to avoid duplicates)."""
    for i in range(1, n + 1):
        t = i / n * duration
        x = x0 + vx * t
        y = y0 + vy0 * t - 0.5 * g * t ** 2
        path.append([x, max(y, 0.0)])


# ─────────────────────────────────────────────
# Public dispatcher
# ─────────────────────────────────────────────

def solve_projectile(subtype: str, params: dict) -> dict:
    """
    Main entry point called from scene_templates.py.

    params: raw dict from LLM (real-world units).
    Returns: dict of solved values, ready for template consumption.
    """
    g = safe_get_float(params, "gravity", DEFAULT_G)
    handlers = {
        "projectile_basic":       _solve_basic,
        "projectile_split":       _solve_split,
        "projectile_collision":   _solve_collision,
        "projectile_moving_cart": _solve_moving_cart,
        "projectile_relative":    _solve_relative,
        "projectile_curvature":   _solve_curvature,
        "projectile_piecewise":   _solve_piecewise,
        "projectile_inclined":    _solve_inclined,
        "projectile_angle_pair":  _solve_angle_pair,
        "projectile_monkey_gun":  _solve_monkey_gun,
        "projectile_wall":        _solve_wall,
        "projectile_intercept":   _solve_intercept,
        "projectile_moving_wedge": _solve_moving_wedge,
        # Legacy alias — keeps backward compat with old "projectile_motion" subject
        "projectile_motion":      _solve_basic,
    }
    handler = handlers.get(subtype, _solve_basic)
    return handler(params, g)


# ─── Individual handlers ─────────────────────

def _solve_basic(params: dict, g: float) -> dict:
    v0    = safe_get_float(params, "speed", safe_get_float(params, "v0", 10.0))
    angle = safe_get_float(params, "angle", 45.0)
    h     = safe_get_float(params, "height", safe_get_float(params, "launch_height", 0.0))

    sol = BasicSolution(v0=v0, angle_deg=angle, launch_height=h, g=g)

    return {
        "subtype": "projectile_basic",
        "v0": v0, "angle": angle, "launch_height": h, "g": g,
        "vx0": sol.vx0, "vy0": sol.vy0,
        "t_peak": sol.t_peak, "t_flight": sol.t_flight,
        "x_range": sol.x_range,
        "y_peak": sol.y_peak,
        "y_peak_above_launch": sol.y_peak_above_launch,
        "v_at_peak": sol.v_at_peak,
        "v_at_landing": sol.v_at_landing,
        "vy_at_landing": sol.vy_at_landing,
        "path_real": sol.path_real,
        # Convenience labels for narration
        "label_speed": params.get("label_speed", f"{v0:.1f} m/s"),
        "label_angle": params.get("label_angle", f"{angle:.1f}°"),
    }


def _solve_split(params: dict, g: float) -> dict:
    v0    = safe_get_float(params, "speed", safe_get_float(params, "v0", 10.0))
    angle = safe_get_float(params, "angle", 45.0)
    h     = safe_get_float(params, "height", 0.0)
    m_total = safe_get_float(params, "m_total", safe_get_float(params, "mass", 1.0))
    m1    = safe_get_float(params, "m1", m_total / 2)
    m2    = m_total - m1

    # Fragment 1 behaviour — default: drops straight down (falls from peak)
    vx1   = safe_get_float(params, "vx1_after", 0.0)
    vy1   = safe_get_float(params, "vy1_after", 0.0)

    base = BasicSolution(v0=v0, angle_deg=angle, launch_height=h, g=g)
    sol  = SplitSolution(
        base=base, m_total=m_total, m1=m1, m2=m2,
        vx1_after=vx1, vy1_after=vy1,
    )

    return {
        "subtype": "projectile_split",
        "v0": v0, "angle": angle, "launch_height": h, "g": g,
        "m_total": m_total, "m1": m1, "m2": m2,
        # Phase 1 (whole projectile to peak)
        "vx0": base.vx0, "vy0": base.vy0,
        "t_peak": base.t_peak,
        "split_x": sol.split_pos.x, "split_y": sol.split_pos.y,
        "path_phase1": base.path_real[:10],   # first half to peak
        # Fragment velocities
        "vx1_after": sol.vx1_after, "vy1_after": sol.vy1_after,
        "vx2_after": sol.vx2_after, "vy2_after": sol.vy2_after,
        # Landing positions
        "t_frag1_land": sol.t_frag1_land, "t_frag2_land": sol.t_frag2_land,
        "x_frag1_land": sol.x_frag1_land,  "x_frag2_land": sol.x_frag2_land,
        "separation": sol.separation,
        # Paths
        "path_frag1": sol.frag1_path(),
        "path_frag2": sol.frag2_path(),
    }


def _solve_collision(params: dict, g: float) -> dict:
    # Projectile A
    ax0 = safe_get_float(params, "ax0", 0.0); ay0 = safe_get_float(params, "ay0", 0.0)
    avx = safe_get_float(params, "avx", 10.0); avy = safe_get_float(params, "avy", 10.0)
    # Projectile B
    bx0 = safe_get_float(params, "bx0", 20.0); by0 = safe_get_float(params, "by0", 0.0)
    bvx = safe_get_float(params, "bvx", -5.0); bvy = safe_get_float(params, "bvy", 10.0)

    sol = CollisionSolution(ax0=ax0, ay0=ay0, avx=avx, avy=avy,
                            bx0=bx0, by0=by0, bvx=bvx, bvy=bvy, g=g)

    return {
        "subtype": "projectile_collision",
        "collides": sol.collides,
        "t_collision": sol.t_collision,
        "x_collision": sol.x_collision,
        "y_collision": sol.y_collision,
        "ax0": ax0, "ay0": ay0, "avx": avx, "avy": avy,
        "bx0": bx0, "by0": by0, "bvx": bvx, "bvy": bvy,
        "g": g,
    }


def _solve_moving_cart(params: dict, g: float) -> dict:
    u_cart = safe_get_float(params, "u_cart", safe_get_float(params, "cart_speed", 5.0))
    vx_rel = safe_get_float(params, "vx_relative", safe_get_float(params, "vx_rel", 0.0))
    vy_rel = safe_get_float(params, "vy_relative", safe_get_float(params, "vy_rel", 10.0))
    h      = safe_get_float(params, "height", 0.0)

    sol = MovingCartSolution(
        u_cart=u_cart, vx_relative=vx_rel, vy_relative=vy_rel,
        launch_height=h, g=g,
    )
    return {
        "subtype": "projectile_moving_cart",
        "u_cart": u_cart, "vx_relative": vx_rel, "vy_relative": vy_rel,
        "launch_height": h, "g": g,
        "vx_ground": sol.vx_ground, "vy_ground": sol.vy_ground,
        "t_flight": sol.t_flight,
        "x_land_ground": sol.x_land_ground,
        "cart_pos_at_landing": sol.cart_pos_at_landing,
        "x_land_cart": sol.x_land_cart,
    }


def _solve_relative(params: dict, g: float) -> dict:
    """
    Relative motion: compute trajectory of B as seen from A.
    In the reference frame of A, gravity acts normally but A's acceleration
    subtracts — if both are under same g, relative acceleration = 0 (straight line).
    """
    # A's launch
    ax0 = safe_get_float(params, "ax0", 0.0); ay0 = safe_get_float(params, "ay0", 0.0)
    avx = safe_get_float(params, "avx", 10.0); avy = safe_get_float(params, "avy", 10.0)
    # B's launch
    bx0 = safe_get_float(params, "bx0", 20.0); by0 = safe_get_float(params, "by0", 0.0)
    bvx = safe_get_float(params, "bvx", -5.0); bvy = safe_get_float(params, "bvy", 10.0)

    # Relative initial position and velocity (B relative to A)
    rel_x0 = bx0 - ax0
    rel_y0 = by0 - ay0
    rel_vx = bvx - avx
    rel_vy = bvy - avy
    # Both under same g → relative acceleration = 0 → straight line trajectory
    rel_acc_y = 0.0

    # Find if they meet (relative displacement = 0)
    # rel_x0 + rel_vx * t = 0  → t = -rel_x0 / rel_vx
    t_meet = None
    if abs(rel_vx) > 1e-9:
        t_candidate = -rel_x0 / rel_vx
        if t_candidate > 0:
            y_meet = rel_y0 + rel_vy * t_candidate
            if abs(y_meet) < 0.05:
                t_meet = t_candidate

    return {
        "subtype": "projectile_relative",
        "ax0": ax0, "ay0": ay0, "avx": avx, "avy": avy,
        "bx0": bx0, "by0": by0, "bvx": bvx, "bvy": bvy,
        "g": g,
        "rel_x0": rel_x0, "rel_y0": rel_y0,
        "rel_vx": rel_vx, "rel_vy": rel_vy,
        "relative_accel": rel_acc_y,
        "t_meet": t_meet,
        "trajectory_is_straight": True,   # always, same g
    }


def _solve_curvature(params: dict, g: float) -> dict:
    v0    = safe_get_float(params, "speed", safe_get_float(params, "v0", 10.0))
    angle = safe_get_float(params, "angle", 45.0)
    h     = safe_get_float(params, "height", 0.0)
    t_q   = safe_get_float(params, "t_query", 0.0)   # 0 = at launch, special = "at_peak"

    base = BasicSolution(v0=v0, angle_deg=angle, launch_height=h, g=g)

    # Common queries
    query_type = params.get("query_at", "t_query")
    if query_type == "peak" or params.get("at_peak", False):
        t_q = base.t_peak
    elif query_type == "launch":
        t_q = 0.0
    elif query_type == "landing":
        t_q = base.t_flight

    sol = CurvatureSolution(base=base, t_query=t_q)
    state = sol.state_at_query

    return {
        "subtype": "projectile_curvature",
        "v0": v0, "angle": angle, "g": g,
        "t_query": t_q, "query_type": query_type,
        "x_at_query": state.x,
        "y_at_query": state.y,
        "vx_at_query": state.vx,
        "vy_at_query": state.vy,
        "speed_at_query": state.speed,
        "angle_at_query": state.angle_deg,
        "a_perp": sol.a_perp,
        "radius_of_curvature": sol.radius_of_curvature,
        # Key special values for narration
        "R_at_launch": (v0 ** 2) / (g * abs(math.cos(math.radians(angle))) + 1e-12),
        "R_at_peak": (base.vx0 ** 2) / g if g > 0 else float("inf"),
    }


def _solve_piecewise(params: dict, g: float) -> dict:
    v0    = safe_get_float(params, "speed", safe_get_float(params, "v0", 20.0))
    angle = safe_get_float(params, "angle", 60.0)
    h     = safe_get_float(params, "height", 0.0)
    h_b   = safe_get_float(params, "h_boundary", safe_get_float(params, "boundary_height", 50.0))
    g2    = safe_get_float(params, "g2", g / 2)   # gravity in upper zone

    rad = math.radians(angle)
    vx0 = v0 * math.cos(rad)
    vy0 = v0 * math.sin(rad)

    sol = PiecewiseGravitySolution(
        vx0=vx0, vy0=vy0, launch_height=h,
        h_boundary=h_b, g1=g, g2=g2,
    )

    return {
        "subtype": "projectile_piecewise",
        "v0": v0, "angle": angle, "g1": g, "g2": g2,
        "h_boundary": h_b,
        "vx0": vx0, "vy0": vy0,
        "t_flight": sol.t_flight,
        "x_range": sol.x_range,
        "y_peak": sol.y_peak,
        "path_real": sol.path_real,
        "segments": sol.segments,
    }
# ── Inclined plane ────────────────────────────

def _solve_inclined(params: dict, g: float) -> dict:
    v0    = safe_get_float(params, "speed", 20.0)
    theta = safe_get_float(params, "theta", 30.0)
    alpha = safe_get_float(params, "alpha", 30.0)

    th_rad = math.radians(theta)
    al_rad = math.radians(alpha)

    # Launch angle wrt horizontal
    launch_horiz = theta + alpha

    # Decompose gravity along and perpendicular to incline
    g_perp  = g * math.cos(al_rad)
    g_along = g * math.sin(al_rad)

    # Decompose initial velocity along and perpendicular to incline
    v0_perp  = v0 * math.sin(th_rad)
    v0_along = v0 * math.cos(th_rad)

    # Time of flight on incline (until perpendicular distance is 0 again)
    t_flight = 2 * v0_perp / g_perp if g_perp > 0 else 0

    # Range along the incline surface
    R_inc = v0_along * t_flight - 0.5 * g_along * t_flight**2

    # Landing coordinates in horizontal/vertical frame
    x_land = R_inc * math.cos(al_rad)
    y_land = R_inc * math.sin(al_rad)

    # Optimal angle (theta wrt incline) for max range
    theta_opt = 45.0 - (alpha / 2.0)
    # Max range formula: v0^2 / (g * (1 + sin alpha))
    R_max = v0**2 / (g * (1 + math.sin(al_rad)))

    # Path in standard horizontal/vertical coordinates
    path = []
    steps = 40
    dt = t_flight / steps if steps > 0 else 0
    for i in range(steps + 1):
        t = i * dt
        # Standard x, y
        x = v0 * math.cos(math.radians(launch_horiz)) * t
        y = v0 * math.sin(math.radians(launch_horiz)) * t - 0.5 * g * t**2
        path.append([x, y, 0])

    # Add the landing point exactly to the path
    if len(path) == 0 or (abs(path[-1][0]-x_land)>0.01 or abs(path[-1][1]-y_land)>0.01):
        path.append([x_land, y_land, 0])

    surface_len = max(R_inc, R_max) * 1.5 if R_max > 0 else 100
    return {
        "v0": v0, "theta_deg": theta, "alpha_deg": alpha, "g": g,
        "launch_angle_horiz": launch_horiz,
        "vx_inc": v0_along, "vy_inc": v0_perp,
        "g_inc_x": g_along, "g_inc_y": g_perp,
        "t_flight": t_flight,
        "range_along_incline": R_inc,
        "x_land": x_land, "y_land": y_land,
        "theta_opt_deg": theta_opt, "range_max": R_max,
        "path_real": path,
        "incline_surface": [[0, 0, 0], [surface_len * math.cos(al_rad), surface_len * math.sin(al_rad), 0]]
    }


# ── Angle pair ────────────────────────────────

def _solve_angle_pair(params: dict, g: float) -> dict:
    v0    = safe_get_float(params, "speed", 20.0)
    angle = safe_get_float(params, "angle", 30.0)
    
    # Ensure angle is the smaller one
    if angle > 45:
        angle = 90 - angle

    partner = 90.0 - angle

    sol_theta   = BasicSolution(v0=v0, angle_deg=angle, launch_height=0.0, g=g)
    sol_partner = BasicSolution(v0=v0, angle_deg=partner, launch_height=0.0, g=g)

    # R = v0^2 sin(2*theta) / g
    R_shared = (v0**2 * math.sin(math.radians(2*angle))) / g
    R_45     = (v0**2) / g

    return {
        "v0": v0, "g": g,
        "theta_deg": angle, "partner_deg": partner,
        "range_shared": R_shared, "range_45": R_45,
        "h_peak_theta": sol_theta.y_peak,
        "h_peak_partner": sol_partner.y_peak,
        "t_flight_theta": sol_theta.t_flight,
        "t_flight_partner": sol_partner.t_flight,
        "path_theta": sol_theta.path_real,
        "path_partner": sol_partner.path_real,
    }


# ── Monkey gun ────────────────────────────────

def _solve_monkey_gun(params: dict, g: float) -> dict:
    v0 = safe_get_float(params, "speed", 25.0)
    d  = safe_get_float(params, "d", 30.0)
    h  = safe_get_float(params, "h", 20.0)

    # Aim directly at monkey
    theta_rad = math.atan2(h, d)
    theta_deg = math.degrees(theta_rad)

    # Time to reach x = d
    vx0 = v0 * math.cos(theta_rad)
    t_meet = d / vx0 if vx0 > 0 else float('inf')

    # y position at t_meet for bullet
    # y = v0*sin(theta)*t - 0.5*g*t^2
    vy0 = v0 * math.sin(theta_rad)
    y_bullet = vy0 * t_meet - 0.5 * g * t_meet**2

    # y position at t_meet for monkey
    # y = h - 0.5*g*t^2
    y_monkey = h - 0.5 * g * t_meet**2

    # They are mathematically equal.
    y_meet = y_bullet

    # Minimum speed for bullet to reach monkey before monkey hits ground (y=0)
    # 0 = h - 0.5*g*t^2 => t_drop = sqrt(2h/g)
    # v0_min = d / (t_drop * cos(theta))
    t_drop = math.sqrt(2 * h / g) if g > 0 else float('inf')
    v0_min = d / (t_drop * math.cos(theta_rad)) if t_drop > 0 else 0

    path_bullet = []
    path_monkey = []
    steps = 30
    dt = t_meet / steps if steps > 0 and not math.isinf(t_meet) else 0

    if not math.isinf(t_meet):
        for i in range(steps + 1):
            t = i * dt
            bx = vx0 * t
            by = vy0 * t - 0.5 * g * t**2
            mx = d
            my = h - 0.5 * g * t**2
            path_bullet.append([bx, by, 0])
            path_monkey.append([mx, my, 0])
    
    return {
        "v0": v0, "d": d, "h": h, "g": g,
        "theta_deg": theta_deg,
        "t_meet": t_meet, "y_meet": y_meet,
        "meets_above_ground": y_meet >= 0,
        "v0_min": v0_min,
        "path_bullet": path_bullet,
        "path_monkey": path_monkey
    }


# ── Wall clearance ────────────────────────────

def _solve_wall(params: dict, g: float) -> dict:
    d_wall = safe_get_float(params, "d_wall", 20.0)
    h_wall = safe_get_float(params, "h_wall", 10.0)
    angle  = safe_get_float(params, "angle", 45.0)
    speed  = safe_get_float(params, "speed", 0.0) # 0 means min speed requested

    # If speed is given, check if it clears
    # Equation of trajectory: y = x*tan(th) - g*x^2/(2*v0^2*cos^2(th))
    th_rad = math.radians(angle)
    tan_th = math.tan(th_rad)
    cos_th = math.cos(th_rad)

    # Minimum speed required at this specific angle to clear the wall (y >= h_wall at x = d_wall)
    # h_wall = d_wall*tan(th) - g*d_wall^2/(2*v^2*cos^2(th))
    # g*d_wall^2/(2*v^2*cos^2(th)) = d_wall*tan(th) - h_wall
    # v^2 = g*d_wall^2 / (2*cos^2(th) * (d_wall*tan(th) - h_wall))
    numerator = g * d_wall**2
    denominator = 2 * (cos_th**2) * (d_wall * tan_th - h_wall)
    
    if denominator > 0:
        v0_min_this_theta = math.sqrt(numerator / denominator)
    else:
        v0_min_this_theta = float('inf') # Angle is too shallow, will never reach h_wall even at infinite speed

    v0_used = speed if speed > 0 else (v0_min_this_theta if not math.isinf(v0_min_this_theta) else 30.0)
    
    # Calculate y at wall for the used speed
    if v0_used > 0:
        y_at_wall = d_wall * tan_th - (g * d_wall**2) / (2 * v0_used**2 * cos_th**2)
    else:
        y_at_wall = 0
        
    clears = y_at_wall >= h_wall

    # Calculate optimal angle for absolute minimum speed to clear the wall
    # The enveloping parabola logic tells us the optimal launch angle is:
    # tan(theta_opt) = (h_wall + sqrt(h_wall^2 + d_wall^2)) / d_wall
    tan_th_opt = (h_wall + math.sqrt(h_wall**2 + d_wall**2)) / d_wall
    th_opt_rad = math.atan(tan_th_opt)
    th_opt_deg = math.degrees(th_opt_rad)
    
    cos_opt = math.cos(th_opt_rad)
    v0_min_optimal = math.sqrt((g * d_wall**2) / (2 * cos_opt**2 * (d_wall * tan_th_opt - h_wall)))

    sol_used = BasicSolution(v0=v0_used, angle_deg=angle, launch_height=0.0, g=g)
    sol_opt  = BasicSolution(v0=v0_min_optimal, angle_deg=th_opt_deg, launch_height=0.0, g=g)

    return {
        "d_wall": d_wall, "h_wall": h_wall, "g": g,
        "theta_deg": angle, "v0_given": speed,
        "v0_min_this_theta": v0_min_this_theta,
        "y_at_wall": y_at_wall,
        "clears": clears,
        "theta_opt_deg": th_opt_deg,
        "v0_min_optimal": v0_min_optimal,
        "path_real": sol_used.path_real,
        "path_optimal": sol_opt.path_real if not math.isinf(v0_min_optimal) else None
    }


# ── Intercept drop ────────────────────────────

def _solve_intercept(params: dict, g: float) -> dict:
    # Mathematically identical to monkey gun, but with different descriptive variables
    v0 = safe_get_float(params, "speed", 25.0)
    d  = safe_get_float(params, "d", 40.0)
    H  = safe_get_float(params, "H", 30.0)

    theta_rad = math.atan2(H, d)
    theta_deg = math.degrees(theta_rad)

    vx0 = v0 * math.cos(theta_rad)
    t_meet = d / vx0 if vx0 > 0 else float('inf')

    vy0 = v0 * math.sin(theta_rad)
    y_meet = vy0 * t_meet - 0.5 * g * t_meet**2

    t_drop = math.sqrt(2 * H / g) if g > 0 else float('inf')
    v0_min = d / (t_drop * math.cos(theta_rad)) if t_drop > 0 else 0

    path_proj = []
    path_drop = []
    steps = 30
    dt = t_meet / steps if steps > 0 and not math.isinf(t_meet) else 0

    if not math.isinf(t_meet):
        for i in range(steps + 1):
            t = i * dt
            bx = vx0 * t
            by = vy0 * t - 0.5 * g * t**2
            mx = d
            my = H - 0.5 * g * t**2
            path_proj.append([bx, by, 0])
            path_drop.append([mx, my, 0])
            
    return {
        "v0": v0, "d": d, "H": H, "g": g,
        "theta_deg": theta_deg,
        "t_meet": t_meet, "y_meet": y_meet,
        "meets_above_ground": y_meet >= 0,
        "v0_min": v0_min,
        "path_projectile": path_proj,
        "path_dropped": path_drop
    }


def _solve_moving_wedge(params: dict, g: float) -> dict:
    u_wedge = safe_get_float(params, "u_wedge",
                safe_get_float(params, "wedge_speed",
                safe_get_float(params, "u_cart",
                safe_get_float(params, "cart_speed", 10.0))))
    alpha   = safe_get_float(params, "alpha",
                safe_get_float(params, "inclination",
                safe_get_float(params, "alpha_deg", 37.0)))
    v_rel   = safe_get_float(params, "v_rel",
                safe_get_float(params, "speed",
                safe_get_float(params, "v0", 25.0)))
    theta   = safe_get_float(params, "theta",
                safe_get_float(params, "angle", 53.0))

    theta_rad = math.radians(theta)
    alpha_rad = math.radians(alpha)

    # Velocity components in relative frame (wedge frame)
    v0x_rel = v_rel * math.cos(theta_rad)
    v0y_rel = v_rel * math.sin(theta_rad)

    # Launch angle relative to incline surface
    theta_incline = theta - alpha
    theta_inc_rad = math.radians(theta_incline)

    # Time of flight on the incline (standard formula for projectile on slope)
    T = (2 * v_rel * math.sin(theta_inc_rad)) / (g * math.cos(alpha_rad)) if math.cos(alpha_rad) != 0 else 0
    if T < 0: T = 0

    # Range along the incline
    v0_along = v_rel * math.cos(theta_inc_rad)
    g_along  = g * math.sin(alpha_rad)
    R_inc = v0_along * T - 0.5 * g_along * T**2

    # Impact velocity in relative frame
    vx_rel_impact = v0x_rel
    vy_rel_impact = v0y_rel - g * T
    v_rel_impact_mag = math.sqrt(vx_rel_impact**2 + vy_rel_impact**2)

    # Ground frame initial velocities
    v0x_ground = v0x_rel + u_wedge
    v0y_ground = v0y_rel

    # Build paths
    steps = 40
    dt = T / steps if T > 0 else 0
    path_rel, path_ground, wedge_path = [], [], []
    for i in range(steps + 1):
        t = i * dt
        path_rel.append(   [v0x_rel    * t,              v0y_rel * t - 0.5 * g * t**2, 0])
        path_ground.append([v0x_ground * t,              v0y_ground * t - 0.5 * g * t**2, 0])
        wedge_path.append( [u_wedge    * t,              0, 0])

    return {
        "u_wedge": u_wedge, "alpha_deg": alpha,
        "v_rel": v_rel, "theta_deg": theta, "g": g,
        "t_flight": T, "range_along_incline": R_inc,
        "vx_rel_impact": vx_rel_impact, "vy_rel_impact": vy_rel_impact,
        "v_rel_impact_mag": v_rel_impact_mag,
        "v0x_ground": v0x_ground, "v0y_ground": v0y_ground,
        "path_rel": path_rel,
        "path_ground": path_ground,
        "wedge_path": wedge_path
    }
