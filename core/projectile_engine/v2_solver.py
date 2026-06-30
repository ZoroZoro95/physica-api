import math
from .v2_models import SceneGraph, SolverResult, SolverAnswer, EquationRecord

def solve_physics(engine_case: str, scene: SceneGraph, facts_knowns: dict) -> SolverResult:
    """
    Deterministic solver. Hardcoded for MVP projectile motion variants.
    Returns SolverResult containing answer, equations, and reasoning.
    """

    if engine_case == "projectile_collides_with_sliding_particle_on_incline":
        return _solve_projectile_slider_incline_collision(scene, facts_knowns)

    raise NotImplementedError(f"V2 Solver not yet implemented for: {engine_case}")


def _solve_projectile_slider_incline_collision(scene: SceneGraph, knowns: dict) -> SolverResult:
    # Extract values
    g = scene.world.gravity
    time = float(knowns.get("time_sec", knowns.get("collision_time", 4.0)))

    incline_angle_deg = 60.0
    for surf in scene.surfaces:
        if surf.kind == "inclined_plane" and surf.angle_deg is not None:
            incline_angle_deg = surf.angle_deg
            break

    cos_theta = math.cos(math.radians(incline_angle_deg))

    # Calculate projection speed `u`
    u_val = 0.5 * g * cos_theta * time

    answer = SolverAnswer(
        symbol="u",
        value=u_val,
        unit="m/s"
    )

    equations = [
        EquationRecord(
            id="perpendicular_displacement",
            latex=r"y = ut - \frac{1}{2}g\cos\theta t^2"
        ),
        EquationRecord(
            id="collision_condition",
            latex=r"0 = ut - \frac{1}{2}g\cos\theta t^2"
        ),
        EquationRecord(
            id="speed_result",
            latex=r"u = \frac{1}{2}g\cos\theta t"
        )
    ]

    reasoning = [
        "Both particles have the same acceleration along the incline.",
        "They start with the same along-incline velocity.",
        "Therefore their along-incline positions remain equal.",
        "Collision happens when P returns to the plane, so its perpendicular displacement is zero."
    ]

    return SolverResult(answer=answer, equations=equations, reasoning=reasoning)
