#!/usr/bin/env python3
"""Regression checks for walkthrough/animation sync audit artifacts.

This gate checks the audit infrastructure, not final teacher quality. Quality
failures are reported by the audit as findings; this script fails when the
solver cannot produce an auditable beat/render contract.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.projectile_engine import build_solution_walkthrough, solve_ad_hoc_question
from core.projectile_engine.animation_scene import build_animation_scene_spec
from core.walkthrough_sync_audit import audit_walkthrough_sync


CASES = [
    {
        "name": "height-launch time",
        "question": (
            "Question 3: If a stone is thrown horizontally from a cliff with a velocity of 10 m/s, "
            "how long will it take to fall 45 m to the ground?"
        ),
        "requested_quantity": "time_of_flight",
    },
    {
        "name": "component range and time",
        "question": "A ball is thrown at u=16 m/s at 53 deg. Find range and time of flight.",
        "requested_quantity": None,
    },
]


def main() -> None:
    failures: list[str] = []
    for case in CASES:
        result = solve_ad_hoc_question(
            question_text=case["question"],
            engine_case=None,
            options=[],
            givens=[],
            requested_quantity=case["requested_quantity"],
        )
        if result.status != "passed":
            failures.append(f"{case['name']}: solver status={result.status} reason={result.reason}")
            continue
        walkthrough = build_solution_walkthrough(result)
        scene = build_animation_scene_spec(result=result, question_text=case["question"], givens=[])
        audit = audit_walkthrough_sync(walkthrough=walkthrough, animation_scene=scene)
        pairings = audit.get("beat_pairings") or []
        probes = (audit.get("render_probe_contract") or {}).get("beat_probes") or []
        if not pairings:
            failures.append(f"{case['name']}: audit produced no beat pairings")
            continue
        if len(pairings) != len(walkthrough.get("explainer_beats") or []):
            failures.append(f"{case['name']}: pairings do not cover every explainer beat")
        if len(probes) != len(pairings):
            failures.append(f"{case['name']}: render probes do not cover every pairing")
        if not all((probe.get("surface_selector") or "").startswith("[data-audit-surface='teaching-board-2d']") for probe in probes):
            failures.append(f"{case['name']}: render probes are missing teaching-board selectors")
        if not any(probe.get("requires_render_verification") for probe in probes):
            failures.append(f"{case['name']}: no probe requires rendered verification")
        if scene and not scene.get("storyboard"):
            failures.append(f"{case['name']}: scene has no storyboard")

    source_checks = [
        (ROOT / "frontend/components/TeachingBoard2D.tsx", "data-audit-surface=\"teaching-board-2d\""),
        (ROOT / "frontend/components/TeachingBoard2D.tsx", "data-audit-vector-id"),
        (ROOT / "frontend/components/TeachingBoard2D.tsx", "data-audit-trajectory-id"),
        (ROOT / "frontend/components/AnimationScene3D.tsx", "data-audit-surface=\"animation-scene-3d\""),
    ]
    for path, needle in source_checks:
        text = path.read_text(encoding="utf-8")
        if needle not in text:
            failures.append(f"{path.relative_to(ROOT)}: missing render probe hook {needle!r}")

    if failures:
        print("Walkthrough sync audit regressions failed:")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print("Walkthrough sync audit regressions passed.")


if __name__ == "__main__":
    main()
