#!/usr/bin/env python3
"""Audit whether rendered SVG templates match the storyboard beat contract.

This is intentionally stricter than the screenshot verifier for algebra-heavy
beats. The visual verifier can judge cleanliness; this script makes sure the
beat did not silently fall back to a generic scene when the walkthrough is
substituting components or angle relations.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


COMPONENT_TEMPLATES = {
    "launch-components",
    "descent-components",
    "incline-velocity-components",
    "incline-perpendicular-setup",
    "incline-gravity-components",
    "incline-impact-setup",
    "incline-impact-condition",
    "incline-impact-relation",
    "incline-normal-distance-condition",
    "incline-normal-return",
    "incline-along-displacement",
    "incline-range-combine",
    "two-inclines-launch-components",
    "two-inclines-impact-components",
    "two-inclines-component-equation",
}

GENERIC_SCENE_TEMPLATES = {
    "range",
    "incline-range",
    "two-inclines-setup",
    "two-inclines-launch",
    "two-inclines-impact",
}

EXPECTED_BY_ENGINE_STEP: dict[str, dict[str, str]] = {
    "two_inclines_perpendicular_launch_impact": {
        "invariant": "two-inclines-setup",
        "solve_1": "two-inclines-launch-components",
        "solve_2": "two-inclines-impact-components",
        "solve_3": "two-inclines-component-equation",
    },
    "perpendicular_launch_range_on_incline": {
        "invariant": "incline-perpendicular-setup",
        "solve_1": "incline-normal-return",
        "solve_2": "incline-along-displacement",
        "solve_3": "incline-range-combine",
    },
    "level_ground_time_to_peak": {
        "invariant": "peak-time-setup",
        "solve_1": "launch-components",
        "solve_2": "peak-time-velocity",
        "solve_3": "peak-time-condition",
        "solve_4": "peak-time-result",
    },
    "level_ground_time_of_flight_derivation": {
        "invariant": "time-derivation-setup",
        "solve_1": "launch-components",
        "solve_2": "time-derivation-equation",
        "solve_3": "time-derivation-factor",
        "solve_4": "time-derivation-result",
        "solve_5": "time-derivation-result",
    },
    "height_launch_time_of_flight": {
        "invariant": "height-launch-time-setup",
        "solve_1": "height-launch-time-condition",
        "solve_2": "height-launch-time-factor",
    },
    "inclined_plane_right_angle_impact_condition": {
        "invariant": "incline-impact-setup",
        "solve_1": "incline-velocity-components",
        "solve_2": "incline-impact-condition",
        "solve_3": "incline-impact-relation",
    },
    "inclined_plane_max_normal_distance_velocity_component": {
        "invariant": "incline-normal-distance-setup",
        "solve_1": "incline-normal-distance-condition",
        "solve_2": "incline-normal-distance-result",
    },
}

REQUIRED_TEXT_BY_TEMPLATE: dict[str, tuple[str, ...]] = {
    "two-inclines-launch-components": ("uₓ = u cos 60°",),
    "two-inclines-impact-components": ("vₓ = v_Q cos 30°",),
    "two-inclines-component-equation": ("u cos 60° = v_Q cos 30°", "solve for v_Q"),
    "incline-normal-return": ("t = 2u/(g cos α)", "g cos α"),
    "incline-along-displacement": ("s = 1/2 g sin α", "g sin α"),
    "incline-range-combine": ("s = 2u² sin α/(g cos²α)",),
    "incline-impact-condition": ("vₜ = 0",),
    "incline-impact-relation": ("cot θ = 2 tan α", "vₜ = 0"),
    "incline-normal-distance-condition": ("vₙ = 0",),
    "incline-perpendicular-setup": ("u ⟂ plane", "range along incline"),
    "peak-time-velocity": ("vᵧ(t) = uᵧ - gt",),
    "peak-time-condition": ("vᵧ = 0",),
    "peak-time-result": ("t_peak",),
    "time-derivation-factor": ("t(uᵧ - 1/2gt) = 0",),
    "height-launch-time-condition": ("0 = h + uᵧt - 1/2gt²",),
    "height-launch-time-factor": ("choose positive root",),
}

COMPONENT_NEEDLES = (
    "resolve",
    "component",
    "cos(",
    " sin(",
    "g cos",
    "g sin",
    "parallel",
    "normal",
    "v_parallel",
    "v_normal",
    "v_x",
    "u_y",
)


@dataclass(frozen=True)
class Failure:
    case_id: str
    step_id: str
    template: str
    reason: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--visual-index",
        type=Path,
        default=Path("questions/visual_benchmarks/smoke_visual_benchmark/visual_index.json"),
    )
    parser.add_argument(
        "--write-json",
        type=Path,
        default=Path("questions/visual_benchmarks/smoke_visual_benchmark/review_queue/svg_beat_contract.json"),
    )
    return parser.parse_args()


def svg_text(svg_path: Path) -> str:
    try:
        root = ET.fromstring(svg_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report bad SVG as a contract failure.
        return f"__SVG_PARSE_ERROR__ {exc}"
    parts: list[str] = []
    for element in root.iter():
        if element.text:
            parts.append(element.text.strip())
    return " ".join(part for part in parts if part)


def normalized_context(item: dict) -> str:
    fields = [
        item.get("title"),
        item.get("learnerMessage"),
        item.get("beatVisual"),
        item.get("visualAction"),
        item.get("engineCase"),
        item.get("answer"),
    ]
    return " ".join(str(field or "") for field in fields).lower()


def needs_component_template(item: dict) -> bool:
    if item.get("templateKind") in COMPONENT_TEMPLATES:
        return False
    focused_context = " ".join(
        str(item.get(field) or "")
        for field in ("title", "beatVisual", "visualAction")
    ).lower()
    if str(item.get("stepId") or "") == "invariant":
        return False
    if str(item.get("visualAction") or "") in {"highlight_range", "highlight_final_answer", "show_full_scene"}:
        return False
    return any(needle in focused_context for needle in COMPONENT_NEEDLES)


def expected_template(item: dict) -> str | None:
    engine_case = str(item.get("engineCase") or "")
    step_id = str(item.get("stepId") or "")
    return EXPECTED_BY_ENGINE_STEP.get(engine_case, {}).get(step_id)


def audit_item(item: dict) -> Iterable[Failure]:
    case_id = str(item.get("caseId") or "")
    step_id = str(item.get("stepId") or "")
    template = str(item.get("templateKind") or "")
    svg_path = Path(str(item.get("svgPath") or ""))
    if not template:
        yield Failure(case_id, step_id, template, "missing templateKind")
        return
    if not svg_path.exists():
        yield Failure(case_id, step_id, template, f"missing svg file: {svg_path}")
        return

    expected = expected_template(item)
    if expected and template != expected:
        yield Failure(case_id, step_id, template, f"expected template {expected}")

    if needs_component_template(item) and template in GENERIC_SCENE_TEMPLATES:
        yield Failure(case_id, step_id, template, "component/angle beat used generic scene template")

    text = svg_text(svg_path)
    if "__SVG_PARSE_ERROR__" in text:
        yield Failure(case_id, step_id, template, text)
        return

    for required in REQUIRED_TEXT_BY_TEMPLATE.get(template, ()):
        if required not in text:
            yield Failure(case_id, step_id, template, f"required SVG text missing: {required}")


def main() -> int:
    args = parse_args()
    data = json.loads(args.visual_index.read_text(encoding="utf-8"))
    visuals = data.get("visuals", [])
    failures = [failure for item in visuals for failure in audit_item(item)]
    summary = {
        "visual_index": str(args.visual_index.resolve()),
        "total_visuals": len(visuals),
        "failures": len(failures),
        "passed": len(visuals) - len({(f.case_id, f.step_id) for f in failures}),
        "failure_items": [failure.__dict__ for failure in failures],
    }
    args.write_json.parent.mkdir(parents=True, exist_ok=True)
    args.write_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if failures:
        print(f"SVG beat contract failed: {len(failures)} failures")
        for failure in failures:
            print(f"- {failure.case_id}/{failure.step_id} [{failure.template}]: {failure.reason}")
        return 1
    print(f"SVG beat contract passed: {len(visuals)} visuals checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
