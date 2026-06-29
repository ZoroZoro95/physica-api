import numpy as np
from typing import List, Tuple, Optional


# ─────────────────────────────────────────────
# SCALE CONTRACT
# All physics runs in "scene units" not metres.
# The LLM is told: 1 scene unit ≈ 10 real metres.
# So a 75m cliff = 7.5 units, v=20m/s = 2.0 units/s.
# Gravity in scene units = 9.81 / 10 = 0.981 ≈ 1.0
# This keeps everything inside [-10, 10] box.
# ─────────────────────────────────────────────

SCENE_GRAVITY = 1.0   # scene units/s²  (= ~10 m/s² real)


def calculate_projectile_path(
    start_pos: Tuple[float, float, float],
    velocity: Tuple[float, float, float],
    gravity: float = SCENE_GRAVITY,
    num_points: int = 20,
) -> List[List[float]]:
    """
    Computes parabolic path. Stops when y hits 0 (ground).
    Auto-calculates duration so ball lands cleanly.
    velocity is in scene units/s.
    """
    vx, vy, vz = velocity
    sx, sy, sz = start_pos

    # Time to land: solve sy + vy*t - 0.5*g*t² = 0
    # 0.5g*t² - vy*t - sy = 0
    a = 0.5 * gravity
    b = -vy
    c = -sy
    discriminant = b * b - 4 * a * c
    if discriminant < 0 or a == 0:
        duration = 4.0
    else:
        t1 = (-b + np.sqrt(discriminant)) / (2 * a)
        t2 = (-b - np.sqrt(discriminant)) / (2 * a)
        positive = [t for t in [t1, t2] if t > 0.01]
        duration = max(positive) if positive else 4.0

    # Clamp duration so animation doesn't drag
    duration = np.clip(duration, 1.0, 8.0)

    t = np.linspace(0, duration, num_points)
    x = sx + vx * t
    y = sy + vy * t - 0.5 * gravity * t ** 2
    z = sz + vz * t

    # Floor at ground (y=0).
    # Only trigger landing AFTER the ball has been airborne (i > 0 and was above ground).
    landed = False
    path = []
    for i in range(num_points):
        if landed:
            # Freeze at landing x/z
            path.append([path[-1][0], 0.0, path[-1][2]])
        elif i > 0 and y[i] <= 0:
            # Interpolate exact landing point between i-1 and i
            dy = y[i] - y[i - 1]
            frac = (0.0 - y[i - 1]) / dy if abs(dy) > 1e-9 else 0.0
            lx = float(x[i - 1] + frac * (x[i] - x[i - 1]))
            lz = float(z[i - 1] + frac * (z[i] - z[i - 1]))
            path.append([lx, 0.0, lz])
            landed = True
        else:
            path.append([float(x[i]), float(max(y[i], 0.0)), float(z[i])])

    return path


def calculate_shm_path(
    equilibrium: Tuple[float, float, float],
    amplitude: float,
    frequency: float = 0.5,
    axis: int = 1,          # 0=x, 1=y, 2=z
    num_cycles: float = 2.0,
    num_points: int = 20,
) -> List[List[float]]:
    """
    Sinusoidal oscillation around equilibrium point.
    num_cycles controls how many full cycles are shown.
    """
    duration = num_cycles / frequency
    t = np.linspace(0, duration, num_points)

    path = []
    for i in range(num_points):
        pos = list(equilibrium)
        pos[axis] = equilibrium[axis] + amplitude * np.sin(2 * np.pi * frequency * t[i])
        path.append([float(p) for p in pos])
    return path


def calculate_circular_path(
    center: Tuple[float, float, float],
    radius: float,
    plane: str = "xz",      # "xz" | "xy" | "yz"
    num_cycles: float = 1.0,
    num_points: int = 20,
    clockwise: bool = False,
) -> List[List[float]]:
    """
    Circular path around center in the given plane.
    """
    sign = -1 if clockwise else 1
    t = np.linspace(0, num_cycles * 2 * np.pi * sign, num_points)

    path = []
    for i in range(num_points):
        cx, cy, cz = center
        if plane == "xz":
            path.append([cx + radius * np.cos(t[i]), cy, cz + radius * np.sin(t[i])])
        elif plane == "xy":
            path.append([cx + radius * np.cos(t[i]), cy + radius * np.sin(t[i]), cz])
        else:  # yz
            path.append([cx, cy + radius * np.cos(t[i]), cz + radius * np.sin(t[i])])
    return path


def calculate_pendulum_path(
    pivot: Tuple[float, float, float],
    length: float,
    max_angle_deg: float = 30.0,
    gravity: float = SCENE_GRAVITY,
    num_cycles: float = 1.5,
    num_points: int = 20,
) -> List[List[float]]:
    """
    Pendulum bob path (arc in xz or xy plane).
    Uses small-angle approximation: θ(t) = θ₀ cos(ωt), ω = sqrt(g/L)
    """
    g = gravity
    omega = np.sqrt(g / max(length, 0.1))
    theta0 = np.radians(max_angle_deg)
    period = 2 * np.pi / omega
    duration = num_cycles * period
    t = np.linspace(0, duration, num_points)

    px, py, pz = pivot
    path = []
    for i in range(num_points):
        theta = theta0 * np.cos(omega * t[i])
        bx = px + length * np.sin(theta)
        by = py - length * np.cos(theta)
        path.append([float(bx), float(by), float(pz)])
    return path


# ─────────────────────────────────────────────
# Dispatcher — called from prompt_engine
# ─────────────────────────────────────────────

def solve_physics(intent: dict, start_pos: List[float]) -> Optional[List[List[float]]]:
    """
    intent = {"type": "projectile"|"shm"|"circular"|"pendulum", "params": {...}}
    start_pos = [x, y, z] in scene units
    Returns 20-point path or None.
    """
    if not intent:
        return None

    typ = intent.get("type", "")
    params = intent.get("params", {})
    pos = tuple(start_pos)

    try:
        if typ == "projectile":
            v = params.get("velocity", [2.0, 3.0, 0.0])
            # Clamp velocity to sane scene-unit range
            v = [np.clip(vi, -8.0, 8.0) for vi in v]
            return calculate_projectile_path(
                start_pos=pos,
                velocity=tuple(v),
                gravity=params.get("gravity", SCENE_GRAVITY),
            )

        elif typ == "shm":
            return calculate_shm_path(
                equilibrium=pos,
                amplitude=np.clip(params.get("amplitude", 1.5), 0.2, 5.0),
                frequency=np.clip(params.get("frequency", 0.5), 0.1, 2.0),
                axis=params.get("axis", 1),
                num_cycles=params.get("num_cycles", 2.0),
            )

        elif typ == "circular":
            return calculate_circular_path(
                center=pos,
                radius=np.clip(params.get("radius", 2.0), 0.5, 8.0),
                plane=params.get("plane", "xz"),
                num_cycles=params.get("num_cycles", 1.0),
                clockwise=params.get("clockwise", False),
            )

        elif typ == "pendulum":
            return calculate_pendulum_path(
                pivot=pos,
                length=np.clip(params.get("length", 3.0), 0.5, 8.0),
                max_angle_deg=np.clip(params.get("max_angle_deg", 30.0), 5.0, 60.0),
                gravity=params.get("gravity", SCENE_GRAVITY),
                num_cycles=params.get("num_cycles", 1.5),
            )

    except Exception as e:
        print(f"[physics_solver] Failed for type={typ}: {e}")

    return None