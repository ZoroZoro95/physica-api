"""
scene_templates.py — Deterministic, theoretically correct scene builders.

SCALE CONTRACT (single source of truth):
  SCALE = 10  (1 scene unit = 10 real metres)
  v_scene = v_real / SCALE
  g_scene = g_real / SCALE
  t_scene = t_real  (time is the same in both systems)
  x_real  = x_scene * SCALE

All displayed labels use REAL units (m, m/s, s, degrees).
All scene coordinates / velocities use SCENE units.
Arrow lengths are proportional to real-world velocity magnitudes.
"""

import math
from .physics_solver import calculate_projectile_path, calculate_shm_path, calculate_circular_path, SCENE_GRAVITY
from .projectile_solver import solve_projectile, safe_get_float

SCALE   = 10.0
G_REAL  = SCENE_GRAVITY * SCALE   # ≈ 10.0 m/s²
ARROW_PX = 0.06   # scene units per real m/s — 20 m/s → 1.2 units, visible but not giant


# ─────────────────────────────────────────────
# Unit conversion helpers
# ─────────────────────────────────────────────

def to_scene(real_val: float) -> float:
    return real_val / SCALE

def to_real(scene_val: float) -> float:
    return scene_val * SCALE

def v_to_scene(real_ms: float) -> float:
    return real_ms / SCALE

def flight_time(vx_s, vy_s, sy_s, g=SCENE_GRAVITY):
    a = 0.5 * g; b = -vy_s; c = -sy_s
    disc = b*b - 4*a*c
    if disc < 0:
        return abs(2 * vy_s / g) if g > 0 else 4.0
    t1 = (-b + math.sqrt(disc)) / (2*a)
    t2 = (-b - math.sqrt(disc)) / (2*a)
    candidates = [t for t in [t1, t2] if t > 0.001]
    return max(candidates) if candidates else 4.0


# ─────────────────────────────────────────────
# Shared scene-object helpers
# ─────────────────────────────────────────────

def _ground():
    return {"id":"ground","type":"plane","position":[0,0,0],"color":"#83C167",
            "args":[40,40],"visible":True,"opacity":0.12}

def _axes():
    return {"id":"axes","type":"axes","position":[0,0,0],"args":[5],
            "color":"#888888","visible":True}

def _camera(pos=None, target=None, fov=42, dur=1.2):
    """Standard camera state."""
    return {"position": pos or [14,10,14], "target": target or [4,2,0],
            "fov": fov, "transition_duration": dur, "ease": "easeInOut"}

def _fit_camera(points: list[list[float]], padding: float = 1.4):
    """Calculates a camera position that fits all points in view."""
    if not points:
        return _camera()
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    cx, cy = (min_x + max_x) / 2, (min_y + max_y) / 2
    
    width = max_x - min_x
    height = max_y - min_y
    size = max(width, height, 2.0)  # at least 2 units wide for tiny problems
    
    dist = size * padding
    # Offset camera to look from an angle
    return _camera([cx + dist, cy + dist * 0.6, dist], [cx, cy, 0])

def _chapter(id_, title, narration, objects, camera=None,
             duration=5.0, loop=False, annotations=None, reveal_ids=None):
    return {
        "id": id_, "title": title, "narration": narration,
        "camera": camera or _camera(),
        "objects": objects,
        "annotations": annotations or [],
        "reveal_ids": reveal_ids or [],
        "hide_ids": [], "autoplay": True, "loop": loop,
        "duration_hint": duration,
    }

def _arrow_obj(id_, pos, rot, real_speed_ms, color, label, label_visible=True):
    length = max(abs(real_speed_ms) * ARROW_PX, 0.15)
    return {
        "id": id_, "type": "arrow",
        "position": pos, "rotation": rot,
        "color": color, "args": [length],
        "label": label, "label_always_visible": label_visible,
        "visible": True,
    }

def _sphere(id_, pos_s, color, label, radius=None, path=None, physics_intent=None):
    # Default radius is 0.2 units (~2m real). Scaled down for very small scenes.
    r = radius if radius is not None else 0.22
    obj = {
        "id": id_, "type": "sphere", "position": pos_s,
        "color": color, "args": [r],
        "label": label, "label_always_visible": True, "visible": True,
    }
    if path is not None:
        obj["path"] = path
    if physics_intent is not None:
        obj["physics_intent"] = physics_intent
    return obj

def _annotation(id_, text, pos_s, color="#FFFFFF", size="md"):
    return {"id": id_, "text": text, "position": pos_s, "color": color, "size": size}

def _real_path_to_scene(path_real: list) -> list:
    """Convert list of [x_real, y_real] to [[x_s, y_s, 0.0], ...]"""
    return [[to_scene(p[0]), to_scene(p[1]), 0.0] for p in path_real]


# ─────────────────────────────────────────────
# PROJECTILE MOTION — dispatcher
# Handles all subtypes via projectile_solver.py
# ─────────────────────────────────────────────

def build_projectile_scene(params: dict, topic: str, subtype: str = "projectile_basic") -> dict:
    """
    Entry point for all projectile variants.
    1. Calls projectile_solver.solve_projectile() for exact math.
    2. Converts results to scene units.
    3. Builds chapter list deterministically.
    """
    solved = solve_projectile(subtype, params)
    builders = {
        "projectile_basic":       _build_basic_chapters,
        "projectile_motion":      _build_basic_chapters,   # legacy alias
        "projectile_split":       _build_split_chapters,
        "projectile_collision":   _build_collision_chapters,
        "projectile_moving_cart": _build_moving_cart_chapters,
        "projectile_relative":    _build_relative_chapters,
        "projectile_curvature":   _build_curvature_chapters,
        "projectile_piecewise":   _build_piecewise_chapters,
        "projectile_inclined":    _build_inclined_chapters,
        "projectile_angle_pair":  _build_angle_pair_chapters,
        "projectile_monkey_gun":  _build_monkey_gun_chapters,
        "projectile_wall":        _build_wall_chapters,
        "projectile_intercept":   _build_intercept_chapters,
        "projectile_moving_wedge": _build_moving_wedge_chapters,
    }
    builder = builders.get(subtype, _build_basic_chapters)
    chapters = builder(solved, topic)
    return {"topic": topic, "subject": subtype, "chapters": chapters}


# ── Basic projectile ──────────────────────────

def _build_basic_chapters(s: dict, topic: str) -> list:
    v0_r  = s["v0"]; angle = s["angle"]; h_r = s["launch_height"]; g = s["g"]
    vx_r  = s["vx0"]; vy_r = s["vy0"]
    T     = s["t_flight"]; t_pk = s["t_peak"]
    R     = s["x_range"]; H    = s["y_peak_above_launch"]
    v_land = s["v_at_landing"]; vy_land = s["vy_at_landing"]
    label_speed = s.get("label_speed", f"{v0_r:.1f} m/s")
    label_angle = s.get("label_angle", f"{angle:.1f}°")

    # Convert path to scene
    path_s = _real_path_to_scene(s["path_real"])
    sx_s = 0.0; sy_s = to_scene(h_r)
    land_x_s = to_scene(R)
    max_y_s  = max(p[1] for p in path_s)
    mid_x_s  = land_x_s / 2
    g_scene  = g / SCALE

    # Arrow rotations (Three.js arrow points +Y by default)
    rot_total = [0.0, 0.0, -(math.pi/2 - math.radians(angle))]
    rot_vx    = [0.0, 0.0, -math.pi/2]
    rot_vy    = [0.0, 0.0,  0.0]

    # Ghost path for camera auto-fit
    ghost = {"id":"trajectory_hint","type":"trail","position":[sx_s,sy_s,0],
             "color":"#00000000","path":path_s,"visible":False}

    physics_intent = {
        "type": "projectile",
        "params": {
            "velocity": [v_to_scene(vx_r), v_to_scene(vy_r), 0.0],
            "vx_real": vx_r, "vy_real": vy_r, "v0_real": v0_r,
            "g_real": g, "height_real": h_r, "T": T,
        }
    }

    # Dynamic sizing
    size = max(land_x_s, max_y_s, 2.0)
    ball_r = min(max(size * 0.03, 0.08), 0.25)
    cam_main = _fit_camera(path_s)

    ch1 = _chapter(
        "setup", "The Setup",
        f"A projectile launches from height {h_r:.0f} m at {label_angle} with {label_speed}. "
        f"Horizontal axis is x, vertical is y. Ground at y = 0. "
        f"Gravity g = {g:.1f} m/s². Where do you think it lands?",
        [_ground(), _axes(), ghost,
         *([{"id":"height_line","type":"arrow","position":[sx_s-0.4,0,0],
             "rotation":[0,0,0],"color":"#83C167","args":[sy_s],
             "label":f"h = {h_r:.0f} m","label_always_visible":True,"visible":True}] if h_r > 0 else []),
         _sphere("ball",[sx_s,sy_s,0],"#FC6255",f"v₀ = {label_speed}", radius=ball_r)],
        camera=cam_main, duration=4.0, reveal_ids=["ball"],
    )

    ch2 = _chapter(
        "decomp", "Velocity Decomposition",
        f"v₀ = {label_speed} at {label_angle} splits into: "
        f"Vx = {vx_r:.2f} m/s (constant, no horizontal force) and "
        f"Vy = {vy_r:.2f} m/s (decreases by {g:.1f} m/s each second due to gravity). "
        f"Can you see which component is red and which is blue?",
        [_ground(), _axes(), ghost,
         _sphere("ball",[sx_s,sy_s,0],"#FC6255",f"v₀={label_speed}", radius=ball_r),
         _arrow_obj("v_total",[sx_s,sy_s,0], rot_total, v0_r, "#58C4DD", f"v₀ = {v0_r:.1f} m/s"),
         _arrow_obj("v_x",   [sx_s,sy_s,0], rot_vx,   vx_r, "#58C4DD", f"Vx = {vx_r:.1f} m/s"),
         _arrow_obj("v_y",   [sx_s,sy_s,0], rot_vy,   vy_r, "#FF6B35", f"Vy = {vy_r:.1f} m/s")],
        camera=cam_main, duration=5.0, reveal_ids=["v_total","v_x","v_y"],
    )

    ch3 = _chapter(
        "flight", "The Flight",
        f"Vx stays constant at {vx_r:.2f} m/s throughout. "
        f"Vy starts at {vy_r:.2f} m/s and falls by {g:.1f} m/s every second. "
        f"Peak height above launch = {H:.2f} m reached at t = {t_pk:.2f} s (when Vy = 0). "
        f"Total flight time = {T:.2f} s. Watch for the moment Vy flips direction!",
        [_ground(), _axes(),
         _sphere("ball",[sx_s,sy_s,0],"#FC6255","projectile",
                 radius=ball_r, path=path_s, physics_intent=physics_intent)],
        camera=cam_main, duration=T * 1.5, reveal_ids=["ball"],
    )

    ch4 = _chapter(
        "result", "Results",
        f"Range R = Vx × T = {vx_r:.2f} × {T:.2f} = {R:.2f} m. "
        f"Max height above launch H = Vy² / 2g = {vy_r:.2f}² / {2*g:.1f} = {H:.2f} m. "
        f"Impact speed = {v_land:.2f} m/s at {math.degrees(math.atan2(-abs(vy_land),vx_r)):.1f}° below horizontal.",
        [_ground(), _axes(),
         _sphere("ball",[land_x_s,0,0],"#FC6255",f"landed {R:.1f} m", radius=ball_r)],
        camera=cam_main,
        duration=5.0,
        annotations=[
            _annotation("range_lbl",f"R = {R:.2f} m",[mid_x_s,-0.6,0],"#83C167","md"),
            _annotation("height_lbl",f"H = {H:.2f} m",[sx_s+(land_x_s-sx_s)*0.25, max_y_s+0.7,0],"#FFFF00","md"),
            _annotation("time_lbl",f"T = {T:.2f} s",[land_x_s+0.8,1.0,0],"#888888","sm"),
        ],
    )

    return [ch1, ch2, ch3, ch4]


# ── Projectile split ──────────────────────────

def _build_split_chapters(s: dict, topic: str) -> list:
    v0_r   = s["v0"]; angle = s["angle"]; g = s["g"]
    vx_r   = s["vx0"]; vy_r = s["vy0"]
    t_pk   = s["t_peak"]
    m1, m2 = s["m1"], s["m2"]; mt = s["m_total"]
    sx_s   = to_scene(s["split_x"]); sy_s = to_scene(s["split_y"])
    vx2_r  = s["vx2_after"]; vy2_r = s["vy2_after"]
    vx1_r  = s["vx1_after"]; vy1_r = s["vy1_after"]
    sep    = s["separation"]
    x1_r   = s["x_frag1_land"]; x2_r = s["x_frag2_land"]

    path1_s  = _real_path_to_scene(s["path_phase1"])
    pathF1_s = _real_path_to_scene(s["path_frag1"])
    pathF2_s = _real_path_to_scene(s["path_frag2"])

    # Dynamic sizing
    all_points = path1_s + pathF1_s + pathF2_s
    size = max(to_scene(sep), sx_s, sy_s, 2.0)
    ball_r = min(max(size * 0.03, 0.08), 0.25)
    cam_main = _fit_camera(all_points)

    ch1 = _chapter(
        "ascent", "Projectile Ascent",
        f"A {mt:.0f} kg projectile launches at {angle:.0f}° with {v0_r:.1f} m/s. "
        f"Vx = {vx_r:.2f} m/s, Vy₀ = {vy_r:.2f} m/s. "
        f"It rises for {t_pk:.2f} s, reaching the peak at "
        f"x = {s['split_x']:.1f} m, y = {s['split_y']:.1f} m (Vy = 0 at peak).",
        [_ground(), _axes(),
         _sphere("ball",[0.0, to_scene(s.get("launch_height",0.0)),0],"#FC6255",
                 f"v₀={v0_r:.1f}m/s  θ={angle:.0f}°", radius=ball_r, path=path1_s)],
        camera=cam_main,
        duration=t_pk*1.5,
    )

    ch2 = _chapter(
        "split", "Split at Peak — Momentum",
        f"At the peak, Vy = 0. The projectile SPLITS into two fragments. "
        f"Fragment 1 (m₁ = {m1:.1f} kg): velocity after = ({vx1_r:.2f}, {vy1_r:.2f}) m/s. "
        f"Momentum conservation (x): {mt:.1f}×{vx_r:.2f} = {m1:.1f}×{vx1_r:.2f} + {m2:.1f}×Vx₂ "
        f"→ Vx₂ = {vx2_r:.2f} m/s. "
        f"Momentum conservation (y): 0 = {m1:.1f}×{vy1_r:.2f} + {m2:.1f}×Vy₂ → Vy₂ = {vy2_r:.2f} m/s.",
        [_ground(), _axes(),
         _sphere("peak",[sx_s,sy_s,0],"#FFFF00",f"split at ({s['split_x']:.0f},{s['split_y']:.0f}) m", radius=ball_r),
         _arrow_obj("v1",[sx_s,sy_s,0],[0,0,-math.pi/2+math.atan2(vy1_r,vx1_r+1e-9)],
                    math.sqrt(vx1_r**2+vy1_r**2),"#FC6255",f"F1: ({vx1_r:.1f},{vy1_r:.1f}) m/s"),
         _arrow_obj("v2",[sx_s,sy_s,0],[0,0,-math.pi/2+math.atan2(vy2_r,vx2_r+1e-9)],
                    math.sqrt(vx2_r**2+vy2_r**2),"#58C4DD",f"F2: ({vx2_r:.1f},{vy2_r:.1f}) m/s")],
        camera=cam_main,
        duration=5.0, reveal_ids=["v1","v2"],
    )

    ch3 = _chapter(
        "fragments", "Fragment Trajectories",
        f"Fragment 1 (red, {m1:.1f} kg): lands at x = {x1_r:.1f} m. "
        f"Fragment 2 (blue, {m2:.1f} kg): lands at x = {x2_r:.1f} m. "
        f"Separation between landing points = {sep:.2f} m. "
        f"Notice how momentum conservation fully determines both trajectories!",
        [_ground(), _axes(),
         _sphere("f1",[sx_s,sy_s,0],"#FC6255",f"m₁={m1:.1f}kg", radius=ball_r, path=pathF1_s),
         _sphere("f2",[sx_s,sy_s,0],"#58C4DD",f"m₂={m2:.1f}kg", radius=ball_r, path=pathF2_s)],
        camera=cam_main,
        duration=max(s["t_frag1_land"],s["t_frag2_land"])*1.5,
        annotations=[
            _annotation("sep_lbl",f"Separation = {sep:.1f} m",
                        [(to_scene(x1_r)+to_scene(x2_r))/2, -0.7, 0], "#FFFF00","md"),
            _annotation("x1_lbl",f"F1 lands at {x1_r:.1f} m",[to_scene(x1_r),0.5,0],"#FC6255","sm"),
            _annotation("x2_lbl",f"F2 lands at {x2_r:.1f} m",[to_scene(x2_r),0.5,0],"#58C4DD","sm"),
        ],
    )

    return [ch1, ch2, ch3]


# ── Projectile collision ──────────────────────

def _build_collision_chapters(s: dict, topic: str) -> list:
    ax0,ay0 = s["ax0"],s["ay0"]; avx,avy = s["avx"],s["avy"]
    bx0,by0 = s["bx0"],s["by0"]; bvx,bvy = s["bvx"],s["bvy"]
    g = s["g"]

    # Build paths for both in WORLD space
    from projectile_solver import BasicSolution

    va = math.sqrt(avx**2 + avy**2)
    angle_a = math.degrees(math.atan2(avy, avx + 1e-12))
    sol_a = BasicSolution(v0=va, angle_deg=angle_a, launch_height=ay0, g=g)

    vb = math.sqrt(bvx**2 + bvy**2)
    angle_b = math.degrees(math.atan2(bvy, bvx + 1e-12))
    sol_b = BasicSolution(v0=vb, angle_deg=angle_b, launch_height=by0, g=g)

    # World-space scene paths: offset each projectile by its launch origin
    pathA = [[to_scene(ax0) + to_scene(p[0]), to_scene(p[1]), 0.0] for p in sol_a.path_real]
    pathB = [[to_scene(bx0) + to_scene(p[0]), to_scene(p[1]), 0.0] for p in sol_b.path_real]

    all_pts = pathA + pathB
    min_x = min(p[0] for p in all_pts)
    max_x = max(p[0] for p in all_pts)
    max_y = max(p[1] for p in all_pts)
    cx = (min_x + max_x) / 2
    cy = max_y / 2
    span = max(max_x - min_x, max_y * 2, 5)
    cam_d = span * 0.9
    cam = _camera([cx + cam_d, cy + cam_d * 0.6, cx + cam_d], [cx, cy, 0])

    start_a_s = [to_scene(ax0), to_scene(ay0), 0]
    start_b_s = [to_scene(bx0), to_scene(by0), 0]

    ch1 = _chapter(
        "setup", "Two Projectiles",
        f"Projectile A launches from ({ax0:.0f}, {ay0:.0f}) m with Vx={avx:.1f}, Vy={avy:.1f} m/s. "
        f"Projectile B launches from ({bx0:.0f}, {by0:.0f}) m with Vx={bvx:.1f}, Vy={bvy:.1f} m/s. "
        f"Both launched at t=0. Watch their paths — do they intersect?",
        [_ground(), _axes(),
         _sphere("A", start_a_s, "#FC6255", "A", path=pathA),
         _sphere("B", start_b_s, "#58C4DD", "B", path=pathB)],
        camera=cam,
        duration=max(sol_a.t_flight, sol_b.t_flight) * 1.3,
    )

    if s["collides"] and s["t_collision"] is not None:
        tc = s["t_collision"]; xc = s["x_collision"]; yc = s["y_collision"]
        col_s = [to_scene(xc), to_scene(yc), 0]
        ch2 = _chapter(
            "collision", "Collision!",
            f"They collide at t = {tc:.3f} s at position ({xc:.2f}, {yc:.2f}) m. "
            f"Key insight: since both are under the same gravity, the quadratic term "
            f"cancels — the meeting condition reduces to two LINEAR equations in t. "
            f"Solving x-equation: {ax0:.1f}+{avx:.1f}t = {bx0:.1f}+{bvx:.1f}t → t = {tc:.3f} s.",
            [_ground(), _axes(),
             _sphere("A", start_a_s, "#FC6255", "A", path=pathA),
             _sphere("B", start_b_s, "#58C4DD", "B", path=pathB),
             {"id": "collision_pt", "type": "sphere", "position": col_s,
              "color": "#FFFF00", "args": [0.35], "label": f"IMPACT t={tc:.2f}s",
              "label_always_visible": True, "visible": True}],
            camera=cam,
            duration=tc * 2,
            annotations=[_annotation("col_lbl", f"({xc:.1f}, {yc:.1f}) m",
                                     [col_s[0], col_s[1] + 0.8, 0], "#FFFF00", "md")],
        )
        return [ch1, ch2]
    else:
        ch2 = _chapter(
            "no_collision", "No Collision",
            f"The projectiles do NOT collide. "
            f"For collision, both x and y equations must give the SAME t. "
            f"A's x: {ax0:.0f}+{avx:.1f}t  |  B's x: {bx0:.0f}+{bvx:.1f}t "
            f"→ they only share x at t={(bx0-ax0)/(avx-bvx):.2f}s if Δvx≠0. "
            f"Check if y-coords also match at that t — here they do not.",
            [_ground(), _axes(),
             _sphere("A", start_a_s, "#FC6255", "A", path=pathA),
             _sphere("B", start_b_s, "#58C4DD", "B", path=pathB)],
            camera=cam,
            duration=max(sol_a.t_flight, sol_b.t_flight) * 1.3,
        )
        return [ch1, ch2]



# ── Moving cart ───────────────────────────────

def _build_moving_cart_chapters(s: dict, topic: str) -> list:
    uc  = s["u_cart"]; vxr = s["vx_relative"]; vyr = s["vy_relative"]
    vxg = s["vx_ground"]; vyg = s["vy_ground"]; g = s["g"]
    T   = s["t_flight"]
    x_g = s["x_land_ground"]; x_c = s["x_land_cart"]; x_cart_end = s["cart_pos_at_landing"]

    from projectile_solver import BasicSolution
    sol_ground = BasicSolution(v0=math.sqrt(vxg**2+vyg**2),
                               angle_deg=math.degrees(math.atan2(vyg,vxg+1e-12)),
                               launch_height=s["launch_height"], g=g)
    path_s = _real_path_to_scene(sol_ground.path_real)
    mid_x  = to_scene(x_g)/2
    max_y  = max(p[1] for p in path_s)

    sol_rel = BasicSolution(v0=math.sqrt(vxr**2+vyr**2),
                            angle_deg=math.degrees(math.atan2(vyr,vxr+1e-12)),
                            launch_height=s["launch_height"], g=g)
    path_rel_s = _real_path_to_scene(sol_rel.path_real)
    
    cart_obj_rel = {
        "id": "cart", "type": "box", "position": [0, -0.15, 0],
        "color": "#888888", "args": [0.8, 0.3, 0.5], "label": "cart (stationary)"
    }

    ch1 = _chapter(
        "cart_frame", "Cart (Moving) Frame",
        f"The cart moves at {uc:.1f} m/s rightward. "
        f"In the cart's frame, the ball is launched with Vx_rel = {vxr:.1f} m/s, Vy_rel = {vyr:.1f} m/s. "
        f"In the cart's frame the ball appears to land {x_c:.2f} m from launch point "
        f"({'back on the cart' if abs(x_c) < 0.1 else 'away from the cart'}).",
        [_ground(), _axes(),
         cart_obj_rel,
         _sphere("ball",[0,to_scene(s["launch_height"]),0],"#FC6255",
                 f"v_rel=({vxr:.1f},{vyr:.1f}) m/s", path=path_rel_s)],
        camera=_camera([mid_x+8,max_y+4,mid_x+8],[mid_x,max_y/2,0]),
        duration=T*1.5,
    )

    steps = len(path_s)
    if steps < 2: steps = 20
    dt = T / (steps - 1) if steps > 1 else 0
    cart_path_g = [[to_scene(uc * (i * dt)), -0.15, 0] for i in range(steps)]
    
    cart_obj_g = {
        "id": "cart", "type": "box", "position": [0, -0.15, 0],
        "color": "#888888", "args": [0.8, 0.3, 0.5], "label": "cart (moving)",
        "path": cart_path_g
    }

    ch2 = _chapter(
        "ground_frame", "Ground Frame",
        f"In the ground frame, ball's launch velocity = cart + relative = "
        f"({uc:.1f}+{vxr:.1f}, {vyr:.1f}) = ({vxg:.1f}, {vyg:.1f}) m/s. "
        f"Ball lands at x = {x_g:.2f} m (ground frame). "
        f"Cart travels {x_cart_end:.2f} m in time T = {T:.2f} s. "
        f"Relative landing = {x_g:.2f} - {x_cart_end:.2f} = {x_c:.2f} m from cart.",
        [_ground(), _axes(),
         cart_obj_g,
         _sphere("ball",[0,to_scene(s["launch_height"]),0],"#FC6255",
                 f"v_ground=({vxg:.1f},{vyg:.1f})", path=path_s)],
        camera=_camera([mid_x+8,max_y+4,mid_x+8],[mid_x,max_y/2,0]),
        duration=T*1.5,
        annotations=[
            _annotation("land_g",f"Ball lands {x_g:.1f} m",[to_scene(x_g),0.5,0],"#FC6255","sm"),
            _annotation("land_c",f"Cart at {x_cart_end:.1f} m",[to_scene(x_cart_end),-0.6,0],"#888888","sm"),
        ],
    )

    return [ch1, ch2]


# ── Relative motion ───────────────────────────

def _build_relative_chapters(s: dict, topic: str) -> list:
    ax0,ay0 = s["ax0"],s["ay0"]; avx,avy = s["avx"],s["avy"]
    bx0,by0 = s["bx0"],s["by0"]; bvx,bvy = s["bvx"],s["bvy"]
    g = s["g"]
    rel_vx = s["rel_vx"]; rel_vy = s["rel_vy"]
    t_meet = s.get("t_meet")

    from projectile_solver import BasicSolution
    sol_a = BasicSolution(v0=math.sqrt(avx**2+avy**2),
                          angle_deg=math.degrees(math.atan2(avy,avx+1e-12)),
                          launch_height=ay0, g=g)
    sol_b = BasicSolution(v0=math.sqrt(bvx**2+bvy**2),
                          angle_deg=math.degrees(math.atan2(bvy,bvx+1e-12)),
                          launch_height=by0, g=g)

    pathA = [[to_scene(ax0+p[0]),to_scene(p[1]),0.0] for p in sol_a.path_real]
    pathB = [[to_scene(bx0+p[0]),to_scene(p[1]),0.0] for p in sol_b.path_real]
    all_pts = pathA + pathB
    cx = sum(p[0] for p in all_pts)/len(all_pts)
    cy = max(p[1] for p in all_pts)/2

    # Relative path (straight line since same g)
    rel_pts = [[to_scene(s["rel_x0"]+rel_vx*i/19*max(sol_a.t_flight,sol_b.t_flight)),
                to_scene(s["rel_y0"]+rel_vy*i/19*max(sol_a.t_flight,sol_b.t_flight)),
                0.0] for i in range(20)]

    ch1 = _chapter(
        "ground_view", "Ground Frame",
        f"A and B are launched simultaneously under the same gravity g = {g:.1f} m/s². "
        f"Both follow parabolic paths in the ground frame. "
        f"A: ({ax0:.0f},{ay0:.0f}) m, v=({avx:.1f},{avy:.1f}) m/s. "
        f"B: ({bx0:.0f},{by0:.0f}) m, v=({bvx:.1f},{bvy:.1f}) m/s.",
        [_ground(), _axes(),
         _sphere("A",[to_scene(ax0),to_scene(ay0),0],"#FC6255","A",path=pathA),
         _sphere("B",[to_scene(bx0),to_scene(by0),0],"#58C4DD","B",path=pathB)],
        camera=_camera([cx+10,cy+8,cx+10],[cx,cy,0]),
        duration=max(sol_a.t_flight,sol_b.t_flight)*1.2,
    )

    ch2 = _chapter(
        "relative_view", "Relative Frame (B seen from A)",
        f"Key insight: since both are under the same gravitational acceleration, "
        f"the -½gt² term CANCELS in the relative position. "
        f"Relative velocity of B w.r.t. A = ({rel_vx:.2f}, {rel_vy:.2f}) m/s — CONSTANT. "
        f"So B moves in a STRAIGHT LINE as seen from A! "
        f"{'They meet at t = ' + f'{t_meet:.3f} s' if t_meet else 'They do not meet.'}",
        [_axes(),
         _sphere("origin",[0,to_scene(s["rel_y0"]),0],"#FC6255","A (reference)",radius=0.2),
         _sphere("B_rel",[to_scene(s["rel_x0"]),to_scene(s["rel_y0"]),0],"#58C4DD",
                 "B relative to A", path=rel_pts)],
        camera=_camera([8,6,8],[to_scene(s["rel_x0"])/2, to_scene(s["rel_y0"])/2, 0]),
        duration=max(sol_a.t_flight,sol_b.t_flight)*1.2,
        annotations=[
            _annotation("rel_v",f"v_rel = ({rel_vx:.1f}, {rel_vy:.1f}) m/s",[0.5,to_scene(s["rel_y0"])+0.8,0],"#FFFF00","sm"),
        ],
    )

    return [ch1, ch2]


# ── Radius of curvature ───────────────────────

def _build_curvature_chapters(s: dict, topic: str) -> list:
    v0_r  = s["v0"]; angle = s["angle"]; g = s["g"]
    R_launch = s["R_at_launch"]; R_peak = s["R_at_peak"]
    t_q   = s["t_query"]; qtype = s["query_type"]
    xq, yq = s["x_at_query"], s["y_at_query"]
    vq, aq = s["speed_at_query"], s["angle_at_query"]
    R_q   = s["radius_of_curvature"]
    a_perp = s["a_perp"]

    from projectile_solver import BasicSolution
    base = BasicSolution(v0=v0_r, angle_deg=angle, launch_height=0.0, g=g)
    path_s = _real_path_to_scene(base.path_real)
    max_y_s = max(p[1] for p in path_s)
    mid_x_s = to_scene(base.x_range)/2

    ch1 = _chapter(
        "setup", "Projectile Setup",
        f"Projectile: v₀ = {v0_r:.1f} m/s at {angle:.1f}°, g = {g:.1f} m/s². "
        f"We want the radius of curvature — the radius of the circular arc that best "
        f"fits the trajectory at a chosen point. Formula: R = v² / a⊥ where a⊥ is "
        f"the component of gravity perpendicular to the velocity.",
        [_ground(), _axes(),
         _sphere("ball",[0,0,0],"#FC6255","projectile",path=path_s)],
        camera=_camera([mid_x_s+8,max_y_s+4,mid_x_s+8],[mid_x_s,max_y_s/2,0]),
        duration=base.t_flight*1.2,
    )

    r_label = f"∞" if R_q == float("inf") else f"{R_q:.2f} m"
    ch2 = _chapter(
        "curvature", f"Curvature at {qtype.replace('_',' ').title()}",
        f"At {qtype}: position = ({xq:.2f}, {yq:.2f}) m, speed = {vq:.2f} m/s, angle = {aq:.1f}°. "
        f"Perpendicular acceleration a⊥ = g·cos(θ) = {g:.1f}·cos({aq:.1f}°) = {a_perp:.3f} m/s². "
        f"R = v²/a⊥ = {vq:.2f}²/{a_perp:.3f} = {r_label}. "
        f"At launch: R = {R_launch:.2f} m. At peak: R = {R_peak:.2f} m.",
        [_ground(), _axes(),
         _sphere("ball",[0,0,0],"#FC6255","projectile",path=path_s),
         _sphere("query_pt",[to_scene(xq),to_scene(yq),0],"#FFFF00",f"R={r_label}",radius=0.25)],
        camera=_camera([mid_x_s+8,max_y_s+4,mid_x_s+8],[mid_x_s,max_y_s/2,0]),
        duration=5.0,
        annotations=[
            _annotation("R_lbl",f"R = {r_label}",[to_scene(xq)+0.5,to_scene(yq)+0.8,0],"#FFFF00","md"),
            _annotation("Rl_lbl",f"R_launch = {R_launch:.1f} m",[0.3,max_y_s+0.5,0],"#83C167","sm"),
            _annotation("Rp_lbl",f"R_peak = {R_peak:.1f} m",[mid_x_s,max_y_s+0.5,0],"#58C4DD","sm"),
        ],
    )

    return [ch1, ch2]


# ── Piecewise gravity ─────────────────────────

def _build_piecewise_chapters(s: dict, topic: str) -> list:
    v0_r   = s["v0"]; angle = s["angle"]
    g1, g2 = s["g1"], s["g2"]; h_b = s["h_boundary"]
    T      = s["t_flight"]; R = s["x_range"]; H = s["y_peak"]
    segs   = s["segments"]

    path_s = _real_path_to_scene(s["path_real"])
    max_y  = max(p[1] for p in path_s)
    mid_x  = to_scene(R)/2

    boundary_s = to_scene(h_b)
    boundary_obj = {
        "id":"boundary","type":"plane","position":[mid_x, boundary_s, 0],
        "color":"#FFFF00","args":[20,0.05],"visible":True,"opacity":0.5,
        "label":f"h = {h_b:.0f} m  |  g switches {g1:.1f}→{g2:.1f} m/s²",
        "label_always_visible":True,
    }

    seg_text = " | ".join([seg["description"] for seg in segs])

    ch1 = _chapter(
        "setup", "Two-Zone Atmosphere",
        f"Below {h_b:.0f} m: g₁ = {g1:.1f} m/s². Above {h_b:.0f} m: g₂ = {g2:.1f} m/s². "
        f"The yellow line marks the boundary. "
        f"Launch: {v0_r:.1f} m/s at {angle:.0f}°. "
        f"Watch how the curvature changes as the ball crosses the boundary!",
        [_ground(), _axes(), boundary_obj,
         _sphere("ball",[0,0,0],"#FC6255","projectile",path=path_s)],
        camera=_camera([mid_x+8,max_y+4,mid_x+8],[mid_x,max_y/2,0]),
        duration=T*1.5,
    )

    ch2 = _chapter(
        "results", "Piecewise Results",
        f"Segments: {seg_text}. "
        f"Total flight time = {T:.3f} s. "
        f"Range = {R:.2f} m. "
        f"Peak height = {H:.2f} m (reached in zone 2 where g = {g2:.1f} m/s²). "
        f"Compared to uniform g₁: same launch but less gravity above {h_b:.0f} m → higher peak.",
        [_ground(), _axes(), boundary_obj,
         _sphere("landed",[to_scene(R),0,0],"#FC6255",f"R={R:.1f} m")],
        camera=_camera([mid_x+8,max_y+4,mid_x+8],[mid_x,max_y/2,0]),
        duration=5.0,
        annotations=[
            _annotation("R_lbl",f"R = {R:.1f} m",[mid_x,-0.6,0],"#83C167","md"),
            _annotation("H_lbl",f"H_peak = {H:.1f} m",[mid_x*0.4, max_y+0.8,0],"#FFFF00","md"),
            _annotation("T_lbl",f"T = {T:.2f} s",[to_scene(R)+0.6,1.0,0],"#888888","sm"),
        ],
    )

    return [ch1, ch2]


# ─────────────────────────────────────────────
# SHM (unchanged)
# ─────────────────────────────────────────────

def build_shm_scene(params: dict, topic: str) -> dict:
    amplitude_s = safe_get_float(params, "amplitude", 1.5)
    frequency   = safe_get_float(params, "frequency", 0.5)
    axis        = int(safe_get_float(params, "axis", 1))
    eq_pos      = params.get("equilibrium", [0, 2, 0])

    amplitude_r = to_real(amplitude_s)
    period      = 1.0 / frequency
    omega       = 2 * math.pi * frequency
    max_speed_r = amplitude_r * omega

    path = calculate_shm_path(
        equilibrium=tuple(eq_pos), amplitude=amplitude_s,
        frequency=frequency, axis=axis, num_cycles=3.0,
    )
    anchor_y = eq_pos[1] + amplitude_s + 1.5

    ch1 = _chapter(
        "setup", "Equilibrium",
        f"Mass at equilibrium. Amplitude = {amplitude_r:.1f} m, Period = {period:.2f} s, "
        f"ω = {omega:.2f} rad/s. Max speed = v_max = Aω = {max_speed_r:.2f} m/s.",
        [_ground(), _axes(),
         {"id":"spring","type":"spring","position":[eq_pos[0],anchor_y,eq_pos[2]],
          "color":"#888888","args":[amplitude_s+1.5],"visible":True},
         _sphere("mass",list(eq_pos),"#FC6255","mass")],
        camera=_camera([8,6,8],[0,eq_pos[1],0]), duration=4.0,
    )
    ch2 = _chapter(
        "oscillation", "SHM Oscillation",
        f"x(t) = {amplitude_r:.1f} sin({omega:.2f}t) m. "
        f"At max displacement: v = 0, |a| = Aω² = {amplitude_r*omega**2:.2f} m/s² (maximum). "
        f"At equilibrium: v = {max_speed_r:.2f} m/s (maximum), a = 0.",
        [_ground(), _axes(),
         {"id":"spring","type":"spring","position":[eq_pos[0],anchor_y,eq_pos[2]],
          "color":"#888888","args":[amplitude_s+1.5],"visible":True},
         {"id":"mass","type":"sphere","position":list(eq_pos),"color":"#FC6255",
          "args":[0.35],"label":f"A={amplitude_r:.1f}m  T={period:.2f}s",
          "label_always_visible":True,"visible":True,"path":path,
          "physics_intent":{"type":"shm","params":{
              "amplitude":amplitude_s,"frequency":frequency,"axis":axis,
              "amplitude_real":amplitude_r,"period":period,"omega":omega}}}],
        camera=_camera([8,6,8],[0,eq_pos[1],0]),
        duration=3.0/frequency, loop=True,
    )
    return {"topic":topic,"subject":"shm","chapters":[ch1,ch2]}


# ─────────────────────────────────────────────
# CIRCULAR MOTION (unchanged)
# ─────────────────────────────────────────────

def build_circular_scene(params: dict, topic: str) -> dict:
    radius_s = safe_get_float(params, "radius", 3.0)
    center   = params.get("center", [0, 3, 0])
    plane    = params.get("plane", "xz")
    speed_s  = safe_get_float(params, "speed", 2.0)

    radius_r = to_real(radius_s); speed_r = to_real(speed_s) # NOTE: these might need fix if params already real
    omega    = speed_r / radius_r; period = 2*math.pi/omega
    ac_r     = speed_r**2 / radius_r

    path = calculate_circular_path(center=tuple(center), radius=radius_s,
                                   plane=plane, num_cycles=2.0)
    ch1 = _chapter(
        "circular", "Circular Motion",
        f"Radius = {radius_r:.1f} m, Speed = {speed_r:.1f} m/s. "
        f"ω = {omega:.2f} rad/s, Period T = {period:.2f} s. "
        f"Centripetal acceleration = v²/r = {ac_r:.2f} m/s² (always toward centre).",
        [_axes(),
         {"id":"orbit_ghost","type":"trail","position":list(center),
          "color":"#58C4DD44","path":path,"visible":True},
         {"id":"particle","type":"sphere","position":path[0],
          "color":"#FC6255","args":[0.3],"label":f"v={speed_r:.1f}m/s",
          "label_always_visible":True,"visible":True,"path":path,
          "physics_intent":{"type":"circular","params":{
              "radius":radius_s,"plane":plane,"speed":speed_s,
              "radius_real":radius_r,"speed_real":speed_r,
              "omega":omega,"period":period,"ac":ac_r}}}],
        camera=_camera([12,10,12],list(center)),
        duration=period*2, loop=True,
    )
    return {"topic":topic,"subject":"circular_motion","chapters":[ch1]}


# ─────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────

PROJECTILE_SUBTYPES = {
    "projectile_basic", "projectile_motion",
    "projectile_split", "projectile_collision",
    "projectile_moving_cart", "projectile_relative",
    "projectile_curvature", "projectile_piecewise",
    "projectile_inclined", "projectile_angle_pair",
    "projectile_monkey_gun", "projectile_wall",
    "projectile_intercept", "projectile_moving_wedge",
}

def build_scene_from_template(subject: str, params: dict, topic: str):
    if subject in PROJECTILE_SUBTYPES:
        return build_projectile_scene(params, topic, subtype=subject)
    if subject == "shm":
        return build_shm_scene(params, topic)
    if subject == "circular_motion":
        return build_circular_scene(params, topic)
    return None
# ── Inclined plane ────────────────────────────

def _build_inclined_chapters(s: dict, topic: str) -> list:
    v0 = s["v0"]; theta = s["theta_deg"]; alpha = s["alpha_deg"]; g = s["g"]
    T  = s["t_flight"]
    R_inc = s["range_along_incline"]
    x_land, y_land = s["x_land"], s["y_land"]
    theta_opt = s["theta_opt_deg"]; R_max = s["range_max"]

    path_s = _real_path_to_scene(s["path_real"])
    # Incline surface as a scene line
    surf = s["incline_surface"]
    surf_end_s = [to_scene(surf[1][0]), to_scene(surf[1][1]), 0.0]
    land_s = [to_scene(x_land), to_scene(y_land), 0.0]
    max_y_s = max(p[1] for p in path_s)
    mid_x_s = land_s[0] / 2

    incline_line = {
        "id": "incline", "type": "line",
        "position": [0, 0, 0],
        "color": "#83C167",
        "path": [[0, 0, 0], surf_end_s],
        "visible": True,
        "label": f"incline {alpha:.0f}°",
        "label_always_visible": True,
    }

    ch1 = _chapter(
        "setup", "Inclined Plane Setup",
        f"The plane is inclined at α = {alpha:.0f}° to the horizontal. "
        f"The projectile launches at θ = {theta:.0f}° ABOVE the incline surface, "
        f"which is {s['launch_angle_horiz']:.0f}° from horizontal. "
        f"v₀ = {v0:.1f} m/s, g = {g:.1f} m/s². "
        f"The key trick: use axes ALONG and PERPENDICULAR to the incline.",
        [_ground(), _axes(), incline_line,
         _sphere("ball", [0, 0, 0], "#FC6255",
                 f"v₀={v0:.1f} m/s  θ={theta:.0f}°+α={alpha:.0f}°")],
        camera=_camera([mid_x_s+8, max_y_s+4, mid_x_s+8], [mid_x_s, max_y_s/2, 0]),
        duration=4.0,
    )

    ch2 = _chapter(
        "incline_axes", "Incline-Axis Decomposition",
        f"Along incline: v₀ₓ = v₀cos(θ) = {s['vx_inc']:.2f} m/s, "
        f"deceleration = g·sin(α) = {g*math.sin(math.radians(alpha)):.2f} m/s². "
        f"Perpendicular to incline: v₀ᵧ = v₀sin(θ) = {s['vy_inc']:.2f} m/s, "
        f"deceleration = g·cos(α) = {g*math.cos(math.radians(alpha)):.2f} m/s². "
        f"Time of flight T = 2v₀sin(θ)/(g·cos α) = {T:.3f} s.",
        [_ground(), _axes(), incline_line,
         _sphere("ball", [0, 0, 0], "#FC6255", "projectile", path=path_s)],
        camera=_camera([mid_x_s+8, max_y_s+4, mid_x_s+8], [mid_x_s, max_y_s/2, 0]),
        duration=T * 1.5,
    )

    ch3 = _chapter(
        "result", "Range on Incline",
        f"Range along incline R = {R_inc:.2f} m. "
        f"Landing point in global coords: ({x_land:.2f}, {y_land:.2f}) m — on the surface ✓. "
        f"Formula: R = 2v₀²sin(θ)cos(θ+α) / (g·cos²α). "
        f"Maximum range at θ_opt = 45° - α/2 = {theta_opt:.1f}° → R_max = {R_max:.2f} m "
        f"(current θ = {theta:.0f}°, {'optimal' if abs(theta-theta_opt)<1 else 'not optimal'}).",
        [_ground(), _axes(), incline_line,
         _sphere("landed", land_s, "#FC6255", f"R={R_inc:.1f} m along incline")],
        camera=_camera([mid_x_s+8, max_y_s+4, mid_x_s+8], [mid_x_s, max_y_s/2, 0]),
        duration=5.0,
        annotations=[
            _annotation("R_lbl", f"R_incline = {R_inc:.2f} m",
                        [mid_x_s, to_scene(y_land)+0.6, 0], "#83C167", "md"),
            _annotation("opt_lbl", f"θ_opt = {theta_opt:.1f}°, R_max = {R_max:.1f} m",
                        [0.5, max_y_s + 0.8, 0], "#FFFF00", "sm"),
        ],
    )

    return [ch1, ch2, ch3]


# ── Angle pair ────────────────────────────────

def _build_angle_pair_chapters(s: dict, topic: str) -> list:
    v0 = s["v0"]; g = s["g"]
    th  = s["theta_deg"]; pa = s["partner_deg"]
    R   = s["range_shared"]
    Ht  = s["h_peak_theta"]; Hp = s["h_peak_partner"]
    Tt  = s["t_flight_theta"]; Tp = s["t_flight_partner"]

    path_t_s = _real_path_to_scene(s["path_theta"])
    path_p_s = _real_path_to_scene(s["path_partner"])
    max_y_s  = max(max(p[1] for p in path_t_s), max(p[1] for p in path_p_s))
    land_x_s = to_scene(R)
    mid_x_s  = land_x_s / 2

    ch1 = _chapter(
        "both_paths", "Same Range, Different Shapes",
        f"Both θ = {th:.0f}° (red) and θ = {pa:.0f}° (blue) give the same range "
        f"R = v₀²·sin(2θ)/g = {v0:.1f}²×sin({2*th:.0f}°)/{g:.0f} = {R:.2f} m. "
        f"Reason: sin(2θ) = sin(180°−2θ) = sin(2×{pa:.0f}°). "
        f"But they look completely different — what's different between them?",
        [_ground(), _axes(),
         _sphere("ball_t", [0, 0, 0], "#FC6255", f"θ={th:.0f}°", path=path_t_s),
         _sphere("ball_p", [0, 0, 0], "#58C4DD", f"θ={pa:.0f}°", path=path_p_s)],
        camera=_camera([mid_x_s+8, max_y_s+4, mid_x_s+8], [mid_x_s, max_y_s/2, 0]),
        duration=max(Tt, Tp) * 1.3,
    )

    ch2 = _chapter(
        "differences", "What's Different",
        f"Red (θ={th:.0f}°): T = {Tt:.2f} s, H_peak = {Ht:.2f} m — flatter, faster. "
        f"Blue (θ={pa:.0f}°): T = {Tp:.2f} s, H_peak = {Hp:.2f} m — steeper, slower. "
        f"The steeper angle has T_partner/T_theta = {Tp/Tt:.2f} (= tan({pa:.0f}°)/tan({th:.0f}°) ≈ {math.tan(math.radians(pa))/math.tan(math.radians(th)):.2f}). "
        f"Maximum range of {s['range_45']:.1f} m occurs at θ = 45°.",
        [_ground(), _axes(),
         _sphere("ball_t", [0, 0, 0], "#FC6255", f"{th:.0f}°: T={Tt:.2f}s H={Ht:.1f}m",
                 path=path_t_s),
         _sphere("ball_p", [0, 0, 0], "#58C4DD", f"{pa:.0f}°: T={Tp:.2f}s H={Hp:.1f}m",
                 path=path_p_s)],
        camera=_camera([mid_x_s+8, max_y_s+4, mid_x_s+8], [mid_x_s, max_y_s/2, 0]),
        duration=max(Tt, Tp) * 1.3,
        annotations=[
            _annotation("R_lbl", f"R = {R:.1f} m (both)", [mid_x_s, -0.6, 0], "#FFFF00", "md"),
            _annotation("Ht_lbl", f"H = {Ht:.1f} m", [mid_x_s*0.3, to_scene(Ht)+0.5, 0], "#FC6255", "sm"),
            _annotation("Hp_lbl", f"H = {Hp:.1f} m", [mid_x_s*0.7, to_scene(Hp)+0.5, 0], "#58C4DD", "sm"),
        ],
    )

    return [ch1, ch2]


# ── Monkey-gun ────────────────────────────────

def _build_monkey_gun_chapters(s: dict, topic: str) -> list:
    v0 = s["v0"]; d = s["d"]; h = s["h"]; g = s["g"]
    theta = s["theta_deg"]; t_meet = s["t_meet"]
    y_meet = s["y_meet"]; v0_min = s["v0_min"]

    path_b_s = _real_path_to_scene(s["path_bullet"])
    path_m_s = [[to_scene(p[0]), to_scene(p[1]), 0.0] for p in s["path_monkey"]]

    monkey_s = [to_scene(d), to_scene(h), 0.0]
    meet_s   = [to_scene(d), to_scene(max(y_meet, 0)), 0.0]
    gun_s    = [0.0, 0.0, 0.0]
    max_y_s  = max(max(p[1] for p in path_b_s), to_scene(h))
    mid_x_s  = to_scene(d) / 2

    # Line of sight from gun to monkey initial position
    los_obj = {
        "id": "los", "type": "line", "position": [0, 0, 0],
        "color": "#FFFF0044",
        "path": [gun_s, monkey_s],
        "visible": True,
        "label": f"aim: θ={theta:.1f}°",
        "label_always_visible": True,
    }
    # Monkey hanging (vertical drop line)
    hang_obj = {
        "id": "hang", "type": "line", "position": [0, 0, 0],
        "color": "#88888866",
        "path": [[to_scene(d), to_scene(h)+0.5, 0], monkey_s],
        "visible": True,
    }

    ch1 = _chapter(
        "setup", "Monkey-Gun Setup",
        f"A gun at the origin aims DIRECTLY at a monkey at ({d:.0f}, {h:.0f}) m. "
        f"Aim angle θ = atan({h:.0f}/{d:.0f}) = {theta:.1f}°, v₀ = {v0:.1f} m/s. "
        f"The monkey drops from rest at t = 0, exactly when the gun fires. "
        f"Intuition: will the bullet always hit the monkey?",
        [_ground(), _axes(), los_obj, hang_obj,
         _sphere("gun_pos", gun_s, "#FC6255", f"gun v₀={v0:.1f}m/s"),
         _sphere("monkey", monkey_s, "#83C167", "monkey (drops at t=0)")],
        camera=_camera([mid_x_s+8, max_y_s+4, mid_x_s+8], [mid_x_s, max_y_s/2, 0]),
        duration=4.0,
    )

    ch2 = _chapter(
        "insight", "The Key Insight",
        f"Both the bullet and monkey fall -½gt² from the line of sight. "
        f"Bullet y = v₀sin(θ)·t - ½gt², Monkey y = {h:.0f} - ½gt². "
        f"Subtract: bullet_y - monkey_y = v₀sin(θ)·t - {h:.0f}. "
        f"They meet when v₀sin(θ)·t = {h:.0f} → t* = {t_meet:.3f} s. "
        f"The -½gt² CANCELS — so they always meet for any v₀ > {v0_min:.1f} m/s!",
        [_ground(), _axes(), los_obj,
         _sphere("bullet", gun_s, "#FC6255", "bullet", path=path_b_s),
         _sphere("monkey", monkey_s, "#83C167", "monkey (dropping)", path=path_m_s)],
        camera=_camera([mid_x_s+8, max_y_s+4, mid_x_s+8], [mid_x_s, max_y_s/2, 0]),
        duration=t_meet * 1.6,
    )

    meet_label = f"meet at ({d:.0f}, {y_meet:.1f}) m" if s["meets_above_ground"] \
                 else f"miss! y_meet={y_meet:.1f}m<0 (need v₀>{v0_min:.1f}m/s)"
    ch3 = _chapter(
        "meeting", "The Meeting Point",
        f"At t* = {t_meet:.3f} s, both reach x = {d:.0f} m, y = {y_meet:.2f} m. "
        f"{'They meet above the ground ✓' if s['meets_above_ground'] else f'They would meet underground — increase v₀ above {v0_min:.1f} m/s.'}. "
        f"Minimum safe speed: v₀ > {v0_min:.1f} m/s (so monkey hasn't hit the floor yet).",
        [_ground(), _axes(),
         _sphere("bullet", gun_s, "#FC6255", "bullet", path=path_b_s),
         _sphere("monkey", monkey_s, "#83C167", "monkey", path=path_m_s),
         _sphere("meet_pt", meet_s, "#FFFF00", meet_label, radius=0.35)],
        camera=_camera([mid_x_s+8, max_y_s+4, mid_x_s+8], [mid_x_s, max_y_s/2, 0]),
        duration=t_meet * 1.6,
        annotations=[
            _annotation("meet_lbl", f"t*={t_meet:.2f}s, y={y_meet:.1f}m",
                        [meet_s[0]+0.5, meet_s[1]+0.6, 0], "#FFFF00", "md"),
        ],
    )

    return [ch1, ch2, ch3]


# ── Wall clearance ────────────────────────────

def _build_wall_chapters(s: dict, topic: str) -> list:
    d_wall = s["d_wall"]; h_wall = s["h_wall"]; g = s["g"]
    theta  = s["theta_deg"]
    v0_min = s["v0_min_this_theta"]; clears = s["clears"]
    y_wall = s["y_at_wall"]
    theta_opt = s["theta_opt_deg"]; v0_opt = s["v0_min_optimal"]

    path_s = _real_path_to_scene(s["path_real"])
    path_opt_s = _real_path_to_scene(s["path_optimal"]) if s["path_optimal"] else path_s
    land_x_s = path_s[-1][0]
    max_y_s  = max(max(p[1] for p in path_s),
                   max(p[1] for p in path_opt_s) if path_opt_s else 0,
                   to_scene(h_wall) + 0.5)
    mid_x_s  = max(land_x_s, to_scene(d_wall)) / 2

    wall_obj = {
        "id": "wall", "type": "line", "position": [0, 0, 0],
        "color": "#FC6255",
        "path": [[to_scene(d_wall), 0, 0], [to_scene(d_wall), to_scene(h_wall), 0]],
        "visible": True,
        "label": f"wall: d={d_wall:.0f}m, h={h_wall:.0f}m",
        "label_always_visible": True,
    }

    v0_display = s["v0_given"] if s["v0_given"] > 0 else (
        v0_min if not math.isinf(v0_min) else 30.0)

    ch1 = _chapter(
        "setup", "Wall Clearance Problem",
        f"A wall stands at x = {d_wall:.0f} m with height {h_wall:.0f} m (red line). "
        f"Launch at θ = {theta:.0f}°, v₀ = {v0_display:.1f} m/s. "
        f"Trajectory: y(x) = x·tan(θ) - g·x²·(1+tan²θ)/(2v₀²). "
        f"At x = {d_wall:.0f} m: y = {y_wall:.2f} m — {'CLEARS ✓' if clears else 'BLOCKED ✗'}.",
        [_ground(), _axes(), wall_obj,
         _sphere("ball", [0, 0, 0], "#58C4DD" if clears else "#FC6255",
                 f"{'clears' if clears else 'blocked'}", path=path_s)],
        camera=_camera([mid_x_s+8, max_y_s+4, mid_x_s+8], [mid_x_s, max_y_s/2, 0]),
        duration=5.0,
        annotations=[
            _annotation("y_wall_lbl",
                        f"y at wall = {y_wall:.2f} m ({'✓' if clears else '✗'})",
                        [to_scene(d_wall)+0.5, to_scene(y_wall)+0.3, 0],
                        "#83C167" if clears else "#FC6255", "sm"),
        ],
    )

    min_inf = math.isinf(v0_min)
    ch2 = _chapter(
        "min_speed", "Minimum Speed",
        f"For θ = {theta:.0f}°: min v₀ = √(g·d²/(2cos²θ·(d·tanθ−h))) "
        f"= {'∞ (angle too shallow!)' if min_inf else f'{v0_min:.2f} m/s'}. "
        f"Optimal angle for lowest possible launch speed: "
        f"tan(θ_opt) = (h + √(h²+d²))/d → θ_opt = {theta_opt:.1f}°. "
        f"At θ_opt the minimum speed needed is {v0_opt:.2f} m/s (blue path).",
        [_ground(), _axes(), wall_obj,
         _sphere("ball_given", [0, 0, 0], "#888888", f"θ={theta:.0f}°", path=path_s),
         _sphere("ball_opt",   [0, 0, 0], "#58C4DD", f"θ_opt={theta_opt:.1f}°",
                 path=path_opt_s)],
        camera=_camera([mid_x_s+8, max_y_s+4, mid_x_s+8], [mid_x_s, max_y_s/2, 0]),
        duration=5.0,
        annotations=[
            _annotation("opt_lbl",
                        f"θ_opt={theta_opt:.1f}°, v_min={v0_opt:.1f} m/s",
                        [0.5, max_y_s+0.7, 0], "#58C4DD", "sm"),
        ],
    )

    return [ch1, ch2]


# ── Intercept drop ────────────────────────────

def _build_intercept_chapters(s: dict, topic: str) -> list:
    v0 = s["v0"]; d = s["d"]; H = s["H"]; g = s["g"]
    theta = s["theta_deg"]; t_meet = s["t_meet"]
    y_meet = s["y_meet"]; v0_min = s["v0_min"]

    path_proj_s = _real_path_to_scene(s["path_projectile"])
    path_drop_s = [[to_scene(p[0]), to_scene(p[1]), 0.0] for p in s["path_dropped"]]

    drop_start_s = [to_scene(d), to_scene(H), 0.0]
    meet_s       = [to_scene(d), to_scene(max(y_meet, 0)), 0.0]
    max_y_s      = max(max(p[1] for p in path_proj_s), to_scene(H))
    mid_x_s      = to_scene(d) / 2

    los_obj = {
        "id": "los", "type": "line", "position": [0, 0, 0],
        "color": "#FFFF0044",
        "path": [[0, 0, 0], drop_start_s],
        "visible": True,
        "label": f"aim line: θ={theta:.1f}°",
        "label_always_visible": True,
    }

    ch1 = _chapter(
        "setup", "Intercept the Dropped Body",
        f"A body is dropped from rest at ({d:.0f}, {H:.0f}) m at t = 0. "
        f"A launcher at origin fires simultaneously at v₀ = {v0:.1f} m/s. "
        f"Required aim angle: θ = atan({H:.0f}/{d:.0f}) = {theta:.1f}° — "
        f"aim DIRECTLY at the drop point (yellow line). "
        f"This is the same insight as the monkey-gun problem.",
        [_ground(), _axes(), los_obj,
         _sphere("launcher", [0, 0, 0], "#FC6255", f"v₀={v0:.1f}m/s"),
         _sphere("dropped", drop_start_s, "#58C4DD", f"drops from ({d:.0f},{H:.0f})m")],
        camera=_camera([mid_x_s+8, max_y_s+4, mid_x_s+8], [mid_x_s, max_y_s/2, 0]),
        duration=4.0,
    )

    ch2 = _chapter(
        "flight", "Both in Flight",
        f"Projectile (red): v₀ = {v0:.1f} m/s at θ = {theta:.1f}°. "
        f"Dropped body (blue): free fall from {H:.0f} m, fixed x = {d:.0f} m. "
        f"Both experience -½g·t². The quadratic gravity term cancels in their "
        f"relative position → relative trajectory is a straight line → they always meet.",
        [_ground(), _axes(),
         _sphere("proj", [0, 0, 0], "#FC6255", "projectile", path=path_proj_s),
         _sphere("drop", drop_start_s, "#58C4DD", "dropped body", path=path_drop_s)],
        camera=_camera([mid_x_s+8, max_y_s+4, mid_x_s+8], [mid_x_s, max_y_s/2, 0]),
        duration=t_meet * 1.5,
    )

    ch3 = _chapter(
        "intercept", "Intercept Point",
        f"They meet at t* = {t_meet:.3f} s at height y = {y_meet:.2f} m. "
        f"{'Above ground ✓' if s['meets_above_ground'] else f'Underground ✗ — need v₀ > {v0_min:.1f} m/s.'}. "
        f"Min safe speed: v₀ > {v0_min:.1f} m/s (so dropped body hasn't hit the floor). "
        f"Verify: proj_y = {v0:.1f}·sin({theta:.1f}°)·{t_meet:.3f} - ½·{g:.0f}·{t_meet:.3f}² = {y_meet:.2f} m.",
        [_ground(), _axes(),
         _sphere("proj", [0, 0, 0], "#FC6255", "projectile", path=path_proj_s),
         _sphere("drop", drop_start_s, "#58C4DD", "dropped body", path=path_drop_s),
         _sphere("meet", meet_s, "#FFFF00", f"intercept t={t_meet:.2f}s", radius=0.35)],
        camera=_camera([mid_x_s+8, max_y_s+4, mid_x_s+8], [mid_x_s, max_y_s/2, 0]),
        duration=t_meet * 1.5,
        annotations=[
            _annotation("meet_lbl", f"y={y_meet:.1f}m at t={t_meet:.2f}s",
                        [meet_s[0]+0.5, meet_s[1]+0.6, 0], "#FFFF00", "md"),
            _annotation("vmin_lbl", f"v₀_min = {v0_min:.1f} m/s",
                        [0.5, max_y_s+0.7, 0], "#888888", "sm"),
        ],
    )

    return [ch1, ch2, ch3]


def _build_moving_wedge_chapters(s: dict, topic: str) -> list:
    uw = s["u_wedge"]; al = s["alpha_deg"]; g = s["g"]
    vrel = s["v_rel"]; th = s["theta_deg"]
    T = s["t_flight"]; R_inc = s["range_along_incline"]
    vx_g = s["v0x_ground"]; vy_g = s["v0y_ground"]
    v_impact = s["v_rel_impact_mag"]

    path_rel_s  = _real_path_to_scene(s["path_rel"])
    path_g_s    = _real_path_to_scene(s["path_ground"])
    wedge_path_s = _real_path_to_scene(s["wedge_path"])

    all_pts = path_g_s + path_rel_s
    mid_x  = max(p[0] for p in all_pts) / 2 if all_pts else 5
    max_y  = max(p[1] for p in all_pts) if all_pts else 5

    al_rad = math.radians(al)
    L = max(to_scene(R_inc) * 1.5, 3.0)

    # Incline bar center in local frame
    cx = (L / 2) * math.cos(al_rad)
    cy = (L / 2) * math.sin(al_rad)

    # Chapter 1 — Wedge frame (stationary wedge)
    wedge_obj_rel = {
        "id": "wedge_surface", "type": "box",
        "position": [cx, cy, 0],
        "rotation": [0, 0, al_rad],
        "color": "#888888", "args": [L, 0.1, 3.0],
        "label": "Wedge surface",
        "label_always_visible": True
    }

    ch1 = _chapter(
        "wedge_frame", "Wedge (Relative) Frame",
        f"Wedge moves right at {uw:.1f} m/s. "
        f"In the wedge's frame, ball is launched at {vrel:.1f} m/s at {th:.1f}° to horizontal. "
        f"This is mathematically identical to a stationary {al:.0f}° inclined plane! "
        f"Ball travels {R_inc:.2f} m along the incline before impact at T = {T:.2f} s.",
        [_ground(), _axes(),
         wedge_obj_rel,
         _sphere("ball", [0, 0, 0], "#FC6255", f"v_rel={vrel:.1f}m/s", path=path_rel_s)],
        camera=_camera([mid_x+10, max_y+5, mid_x+10], [mid_x, max_y/2, 0]),
        duration=T * 1.5,
    )

    # Chapter 2 — Ground frame (wedge slides right)
    wedge_ground_path = [[p[0] + cx, p[1] + cy, 0] for p in wedge_path_s]

    wedge_obj_g = {
        "id": "wedge_surface_g", "type": "box",
        "position": [cx, cy, 0],
        "rotation": [0, 0, al_rad],
        "color": "#888888", "args": [L, 0.1, 3.0],
        "label": "Moving wedge",
        "label_always_visible": True,
        "path": wedge_ground_path
    }

    ch2 = _chapter(
        "ground_frame", "Ground Frame",
        f"In the ground frame, ball: Vx = {vx_g:.1f} m/s, Vy = {vy_g:.1f} m/s. "
        f"Wedge slides right at {uw:.1f} m/s. "
        f"At T = {T:.2f} s the ball strikes the incline surface. "
        f"|v_rel| at impact = {v_impact:.2f} m/s.",
        [_ground(), _axes(),
         wedge_obj_g,
         _sphere("ball", [0, 0, 0], "#FC6255",
                 f"v=({vx_g:.1f}, {vy_g:.1f})", path=path_g_s)],
        camera=_camera([mid_x+10, max_y+5, mid_x+10], [mid_x, max_y/2, 0]),
        duration=T * 1.5,
        annotations=[
            _annotation("impact", f"Impact at T={T:.2f}s", path_g_s[-1], "#FFFF00", "sm"),
            _annotation("rinc",   f"R_inc = {R_inc:.2f} m",
                        [cx*0.6, cy*0.6+0.5, 0], "#83C167", "sm"),
        ],
    )

    return [ch1, ch2]

