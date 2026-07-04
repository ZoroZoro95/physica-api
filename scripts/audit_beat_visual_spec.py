#!/usr/bin/env python3
"""Audit BeatVisualSpec coverage for projectile acceptance artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.projectile_engine.visual_contract import FORBIDDEN_TEXT_PATTERNS, validate_beat_visual_spec  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--expected-cases", type=int, default=60)
    parser.add_argument("--write-json", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit_dir = args.audit_dir.resolve()
    payloads = sorted(audit_dir.glob("*/render_payload.json"))
    failures: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    if len(payloads) != args.expected_cases:
        failures.append({
            "case_id": "__corpus__",
            "step_id": "",
            "reason": f"expected {args.expected_cases} render_payload.json files, found {len(payloads)}",
        })

    for payload_path in payloads:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        case_id = payload_path.parent.name
        case_failures = audit_payload(case_id, payload)
        failures.extend(case_failures)
        summaries.append({
            "case_id": case_id,
            "solver_status": ((payload.get("solver") or {}).get("status") or ""),
            "engine_case": ((payload.get("solver") or {}).get("engine_case") or ""),
            "beats": len(((payload.get("walkthrough") or {}).get("explainer_beats") or [])),
            "storyboard_steps": len((((payload.get("animation_scene_spec") or {}).get("storyboard")) or [])),
            "failures": len(case_failures),
        })

    report = {
        "audit_dir": str(audit_dir),
        "expected_cases": args.expected_cases,
        "cases": len(payloads),
        "passed": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "case_summaries": summaries,
    }
    if args.write_json:
        args.write_json.parent.mkdir(parents=True, exist_ok=True)
        args.write_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if failures:
        print(f"FAIL BeatVisualSpec audit: {len(failures)} failures")
        for failure in failures[:80]:
            print(f"- {failure['case_id']}/{failure.get('step_id') or '-'}: {failure['reason']}")
        if len(failures) > 80:
            print(f"... {len(failures) - 80} more")
        return 1

    print(f"PASS BeatVisualSpec audit: cases={len(payloads)}")
    return 0


def audit_payload(case_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    solver = payload.get("solver") or {}
    if solver.get("status") != "passed":
        failures.append({"case_id": case_id, "step_id": "", "reason": f"solver status is {solver.get('status') or 'missing'}"})

    walkthrough = payload.get("walkthrough") or {}
    scene = payload.get("animation_scene_spec") or {}
    beats = walkthrough.get("explainer_beats") or []
    storyboard = {str(step.get("step_id") or ""): step for step in scene.get("storyboard") or []}

    if not beats:
        failures.append({"case_id": case_id, "step_id": "", "reason": "walkthrough has no explainer beats"})
    if not storyboard:
        failures.append({"case_id": case_id, "step_id": "", "reason": "animation scene has no storyboard"})

    for beat in beats:
        step_id = str(beat.get("step_id") or beat.get("id") or "")
        if not step_id:
            failures.append({"case_id": case_id, "step_id": "", "reason": "beat is missing step_id"})
            continue
        visual_plan = beat.get("visual_plan") or {}
        beat_spec = beat.get("beat_visual_spec") or visual_plan.get("beat_visual_spec") or {}
        story_step = storyboard.get(step_id)
        if not story_step:
            failures.append({"case_id": case_id, "step_id": step_id, "reason": "no matching storyboard step"})
            continue
        story_spec = story_step.get("beat_visual_spec") or (story_step.get("visual_plan") or {}).get("beat_visual_spec") or {}
        failures.extend(audit_spec(case_id, step_id, "beat", beat_spec, beat))
        failures.extend(audit_spec(case_id, step_id, "storyboard", story_spec, story_step))
        if isinstance(beat_spec, dict) and isinstance(story_spec, dict) and beat_spec and story_spec:
            for key in ("family", "beat", "engine_case"):
                if beat_spec.get(key) != story_spec.get(key):
                    failures.append({
                        "case_id": case_id,
                        "step_id": step_id,
                        "reason": f"beat/storyboard spec mismatch on {key}: {beat_spec.get(key)} != {story_spec.get(key)}",
                    })
        failures.extend(audit_forbidden(case_id, step_id, story_spec, story_step))
    return failures


def audit_spec(case_id: str, step_id: str, owner: str, spec: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(spec, dict) or not spec:
        return [{"case_id": case_id, "step_id": step_id, "reason": f"{owner} missing beat_visual_spec"}]
    text = json.dumps(context, ensure_ascii=False)
    return [
        {"case_id": case_id, "step_id": step_id, "reason": f"{owner} {error}"}
        for error in validate_beat_visual_spec(spec, text=text)
    ]


def audit_forbidden(case_id: str, step_id: str, spec: Any, storyboard_step: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(spec, dict):
        return []
    text = json.dumps({
        "labels": storyboard_step.get("labels") or [],
        "visual_state": storyboard_step.get("visual_state") or {},
        "visible_vectors": storyboard_step.get("visible_vectors") or [],
        "overlays": storyboard_step.get("overlays") or [],
    }, ensure_ascii=False)
    failures: list[dict[str, Any]] = []
    for forbidden in spec.get("must_not_show") or []:
        for pattern in FORBIDDEN_TEXT_PATTERNS.get(str(forbidden), ()):
            if re.search(pattern, text, re.I):
                failures.append({"case_id": case_id, "step_id": step_id, "reason": f"forbidden visual {forbidden} appears in storyboard payload"})
                break
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
