#!/usr/bin/env python3
"""Build a 30-case projectile visual benchmark manifest and sync artifacts.

The benchmark intentionally mixes text-only prompts and image-derived prompts.
Image-derived prompts are seeded from stored extraction/debug reports or from
previously accepted screenshot manifest entries, so the first benchmark run does
not depend on provider/VLM availability.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_ROOT = ROOT / "questions" / "visual_benchmarks"


TEXT_CASES: list[dict[str, Any]] = [
    {
        "id": "text_level_max_range",
        "question": "Projectile launched at 45deg with 25 m/s. Find the maximum range.",
        "engine_case": "level_ground_range",
        "knowns": ["v0=25m/s", "angle=45deg"],
        "requested_quantity": "maximum_range",
    },
    {
        "id": "text_level_range_time",
        "question": "A ball is thrown at u=16 m/s at 53 deg. Find range and time of flight.",
        "engine_case": "level_ground_multi_quantity",
        "knowns": ["v0=16m/s", "angle=53deg"],
        "requested_quantity": "range_time",
    },
    {
        "id": "text_level_multi_quantity",
        "question": "A projectile is launched at 20 m/s at 30deg. Find range, time of flight, maximum height, and velocity components. Take g = 10 m/s^2.",
        "engine_case": "level_ground_multi_quantity",
        "knowns": ["v0=20m/s", "angle=30deg", "g=10m/s^2"],
        "requested_quantity": "multi_quantity",
    },
    {
        "id": "text_height_launch_range",
        "question": "A projectile is fired from a 45 m high cliff with speed 20 m/s at 30deg above horizontal. Find the horizontal range. Take g = 10 m/s^2.",
        "engine_case": "height_launch_range",
        "knowns": ["height=45m", "v0=20m/s", "angle=30deg", "g=10m/s^2"],
        "requested_quantity": "range",
    },
    {
        "id": "text_wall_clearance",
        "question": "A projectile is launched at 20 m/s at 45deg toward a wall 20 m away and 8 m high. Does it clear the wall? Take g = 10 m/s^2.",
        "engine_case": "wall_clearance_condition",
        "knowns": ["v0=20m/s", "angle=45deg", "wall_distance=20m", "wall_height=8m", "g=10m/s^2"],
        "requested_quantity": "wall_clearance",
    },
    {
        "id": "text_target_launch_angle",
        "question": "A projectile is fired with speed 20 m/s to hit a target at (20 m, 10 m). Find all launch angles. Take g = 10 m/s^2.",
        "engine_case": "target_launch_angle_fixed_speed",
        "knowns": ["v0=20m/s", "target=(20,10)m", "g=10m/s^2"],
        "requested_quantity": "launch_angle",
    },
    {
        "id": "text_position_at_time",
        "question": "A projectile is launched from level ground with speed 20 m/s at 30deg. Find its position after 1 s. Take g = 10 m/s^2.",
        "engine_case": "level_ground_position_at_time",
        "knowns": ["v0=20m/s", "angle=30deg", "time=1s", "g=10m/s^2"],
        "requested_quantity": "position_at_time",
    },
    {
        "id": "text_time_to_peak",
        "question": "A ball is thrown at 15 m/s at an angle of 37 deg. Calculate time to reach the maximum height.",
        "engine_case": "level_ground_time_to_peak",
        "knowns": ["v0=15m/s", "angle=37deg"],
        "requested_quantity": "time_to_peak",
    },
    {
        "id": "text_time_of_flight_derivation",
        "question": "Derive the equation for time of flight for a projectile launched at angle theta with initial speed u.",
        "engine_case": "level_ground_time_of_flight_derivation",
        "knowns": [],
        "requested_quantity": "time_of_flight_derivation",
    },
    {
        "id": "text_horizontal_cliff_time",
        "question": "If a stone is thrown horizontally from a cliff with a velocity of 10 m/s, how long will it take to fall 45 m to the ground?",
        "engine_case": "height_launch_time_of_flight",
        "knowns": ["v0=10m/s", "vx=10m/s", "angle=0deg", "height=45m"],
        "requested_quantity": "time_of_flight",
    },
    {
        "id": "text_minimum_speed_target",
        "question": "Find the minimum velocity with which a projectile should be fired to hit a target at (3 m, 4 m). Take g = 10 m/s^2.",
        "engine_case": "minimum_speed_to_hit_target",
        "knowns": ["target=(3,4)m", "g=10m/s^2"],
        "requested_quantity": "minimum_speed",
    },
    {
        "id": "text_two_projectile_collision",
        "question": "Projectile A is launched from x=0 with velocity components (20, 30) m/s. Projectile B is launched simultaneously from x=100 m with velocity components (-10, 30) m/s. Both have the same gravity. When do they collide?",
        "engine_case": "two_projectile_collision_time",
        "knowns": ["A_vx=20m/s", "A_vy=30m/s", "B_x0=100m", "B_vx=-10m/s", "B_vy=30m/s"],
        "requested_quantity": "collision_time",
    },
    {
        "id": "text_two_incline_transfer",
        "question": "Two inclined planes OA and OB with inclinations 30 deg and 60 deg intersect at O. A particle is projected from P with velocity u = 10*sqrt(3) m/s perpendicular to plane OA. If it strikes plane OB perpendicularly at Q, find the velocity at Q.",
        "engine_case": "two_inclines_perpendicular_launch_impact",
        "knowns": ["angle_OA=30deg", "angle_OB=60deg", "u=10sqrt3m/s"],
        "requested_quantity": "impact_speed",
    },
    {
        "id": "text_staircase_collision",
        "question": "A marble rolls down from top of a staircase with constant horizontal velocity 10 m/s. If each step is 1 m high and 1 m wide, to which step will the marble strike directly?",
        "engine_case": "staircase_collision",
        "knowns": ["vx=10m/s", "step_height=1m", "step_width=1m", "g=9.8m/s^2"],
        "requested_quantity": "step_number",
    },
    {
        "id": "text_incline_collision",
        "question": "A particle P is projected from a point on the surface of smooth inclined plane. Simultaneously another particle Q is released on the smooth inclined plane from the same position. P and Q collide after t = 4 second. The speed of projection of P is:",
        "engine_case": "projectile_collides_with_sliding_particle_on_incline",
        "knowns": ["incline=60deg", "collision_time=4s", "g=10m/s^2"],
        "requested_quantity": "projection_speed",
    },
]


SCREENSHOT_MANIFEST_CASES = [
    ("Screenshot 2026-05-25 at 12.41.58 PM.png", "01_projectileinc_q03_inclined_plane_right_angle_impact_condition"),
    ("Screenshot 2026-05-25 at 9.44.11 PM.png", "02_projectileinc_q05_staircase_collision"),
    ("Screenshot 2026-05-25 at 9.44.18 PM.png", "03_projectileinc_q07_inclined_plane_max_normal_distance_velocity_component"),
    ("Screenshot 2026-05-25 at 9.44.24 PM.png", "04_projectileinc_q08_perpendicular_launch_range_on_incline"),
    ("Screenshot 2026-05-25 at 9.44.30 PM.png", "05_projectileinc_q11_two_inclines_perpendicular_launch_impact"),
    ("Screenshot 2026-05-25 at 9.44.36 PM.png", "06_projectileinc_q12_projectile_collides_with_sliding_particle_on_incline"),
    ("Screenshot 2026-05-25 at 9.44.42 PM.png", "07_projectileinc_q13_motion_on_smooth_incline_perpendicular_to_slope"),
]


DEBUG_REPORT_IMAGE_IDS = [
    "20260621T104018Z-5baa7163",
    "20260602T081813Z-7a960391",
    "20260616T064219Z-a7c1424e",
    "20260616T043756Z-17c7af0f",
    "20260612T184748Z-0d8f96f0",
    "20260606T074913Z-b3ce3556",
    "20260602T093809Z-1955e8fd",
    "20260527T133330Z-8c4e24c8",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--skip-audit", action="store_true")
    parser.add_argument("--fail-on-sync-issues", action="store_true")
    args = parser.parse_args()

    run_dir = (args.out_root / args.run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest()
    manifest_path = run_dir / "benchmark_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (run_dir / "case_index.json").write_text(json.dumps(case_index(manifest), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"benchmark_manifest={manifest_path}")
    print(f"cases={len(manifest)} text={sum(1 for item in manifest if item.get('source_type') == 'text')} image={sum(1 for item in manifest if str(item.get('source_type')).startswith('image'))}")

    if not args.skip_audit:
        sync_dir = run_dir / "sync_audit"
        cmd = [sys.executable, str(ROOT / "scripts" / "audit_walkthrough_sync_manifest.py"), str(manifest_path), "--out-dir", str(sync_dir)]
        if args.fail_on_sync_issues:
            cmd.append("--fail-on-issues")
        print("$ " + " ".join(cmd))
        subprocess.run(cmd, cwd=ROOT, check=True)
    return 0


def build_manifest() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, case in enumerate(TEXT_CASES, start=1):
        entries.append({
            "pdf_id": "visual_text",
            "question_number": index,
            "source_type": "text",
            "source_id": case["id"],
            "question_type": "free_response",
            "question_text": case["question"],
            "options": [],
            "expected_option_letter": None,
            "expected_answer": None,
            "engine_case": case["engine_case"],
            "knowns": case.get("knowns", []),
            "requested_quantity": case.get("requested_quantity"),
        })

    image_number = 1
    screenshot_root = ROOT / "questions" / "walkthrough_sync_manifest_audits" / "screenshot_cases_20260621"
    for desktop_name, case_dir_name in SCREENSHOT_MANIFEST_CASES:
        entry_path = screenshot_root / case_dir_name / "entry.json"
        if not entry_path.exists():
            continue
        raw = json.loads(entry_path.read_text(encoding="utf-8"))
        raw.update({
            "pdf_id": "visual_image",
            "question_number": image_number,
            "source_type": "image_screenshot_manifest",
            "source_id": case_dir_name,
            "source_image": str(Path("/Users/siddharth/Desktop") / desktop_name),
        })
        entries.append(raw)
        image_number += 1

    for report_id in DEBUG_REPORT_IMAGE_IDS:
        report_dir = ROOT / "questions" / "debug_reports" / report_id
        entry = entry_from_debug_report(report_dir, image_number)
        if entry is None:
            continue
        entries.append(entry)
        image_number += 1

    return entries


def entry_from_debug_report(report_dir: Path, question_number: int) -> dict[str, Any] | None:
    extraction_path = report_dir / "extraction.json"
    solve_path = report_dir / "solve.json"
    if not extraction_path.exists() or not solve_path.exists():
        return None
    extraction = json.loads(extraction_path.read_text(encoding="utf-8"))
    solve = json.loads(solve_path.read_text(encoding="utf-8"))
    request = solve.get("request") or {}
    response = solve.get("response") or solve.get("stored_response") or {}
    question_text = request.get("question_text_solver") or extraction.get("question_text_solver") or extraction.get("cleaned_prompt") or extraction.get("question_text") or ""
    engine_case = response.get("engine_case") or request.get("suggested_engine_case") or extraction.get("suggested_engine_case")
    if not question_text or not engine_case:
        return None
    knowns = list(request.get("givens") or extraction.get("givens") or [])
    knowns = normalize_debug_knowns(engine_case, knowns, question_text)
    return {
        "pdf_id": "visual_image",
        "question_number": question_number,
        "source_type": "image_debug_report",
        "source_id": report_dir.name,
        "source_image": str(report_dir / "question.png"),
        "question_type": extraction.get("question_type") or "unknown",
        "question_text": question_text,
        "options": request.get("options") or extraction.get("options") or [],
        "expected_option_letter": response.get("matched_option"),
        "expected_answer": response.get("answer"),
        "engine_case": engine_case,
        "knowns": knowns,
        "requested_quantity": request.get("requested_quantity") or extraction.get("requested_quantity"),
    }


def normalize_debug_knowns(engine_case: str, knowns: list[str], question_text: str) -> list[str]:
    normalized = list(knowns)
    joined = "\n".join(normalized)
    if engine_case == "velocity_change_interval" and "dt" not in joined:
        text = question_text.lower()
        if "t1 = 0" in text and "t2 = 0.5" in text:
            normalized.append("dt=0.5s")
    return normalized


def case_index(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for entry in manifest:
        rows.append({
            "label": f"{entry.get('pdf_id')} Q{int(entry.get('question_number') or 0):02d}",
            "source_type": entry.get("source_type"),
            "source_id": entry.get("source_id"),
            "source_image": entry.get("source_image"),
            "engine_case": entry.get("engine_case"),
            "question_text": entry.get("question_text"),
        })
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
