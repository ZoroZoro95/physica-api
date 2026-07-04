from __future__ import annotations

import json
import re
from typing import Any

from .projectile_engine.visual_contract import FORBIDDEN_TEXT_PATTERNS, validate_beat_visual_spec


def audit_walkthrough_sync(
    *,
    walkthrough: dict[str, Any] | None,
    animation_scene: dict[str, Any] | None,
) -> dict[str, Any]:
    findings: list[str] = []
    hard_fail = ""

    if not walkthrough:
        hard_fail = "missing walkthrough"
        findings.append(hard_fail)
    if not animation_scene:
        hard_fail = "missing animation scene"
        findings.append(hard_fail)

    beats = (walkthrough or {}).get("explainer_beats") or []
    storyboard = {
        str(step.get("step_id")): step
        for step in (animation_scene or {}).get("storyboard") or []
    }
    live_vectors = (animation_scene or {}).get("live_vectors") or []
    live_vector_labels = " ".join(str(vector.get("label") or "") for vector in live_vectors).lower()
    scene_text = json.dumps(animation_scene or {}, ensure_ascii=False).lower()
    scene_point_ids = set(((animation_scene or {}).get("geometry") or {}).get("points") or {})

    if beats and not storyboard:
        findings.append("Explainer beats exist, but animation storyboard is empty.")
    if storyboard and not beats:
        findings.append("Animation storyboard exists, but explainer beats are empty.")

    beat_findings: list[str] = []
    pairings: list[dict[str, Any]] = []
    for beat in beats:
        step_id = str(beat.get("step_id") or beat.get("id") or "")
        paired = storyboard.get(step_id)
        title = str(beat.get("title") or beat.get("id") or step_id)
        beat_text = beat_text_blob(beat)
        beat_visual_plan = beat.get("visual_plan") or {}
        if beat_visual_plan.get("type") == "text_only":
            pairings.append(_pairing(beat, {}, "text_only", live_vectors, scene_point_ids))
            continue
        if not paired:
            beat_findings.append(f"{title}: no storyboard step with step_id={step_id!r}.")
            pairings.append(_pairing(beat, {}, "missing_storyboard", live_vectors, scene_point_ids))
            continue
        paired_visual_plan = paired.get("visual_plan") or {}
        beat_visual_spec = beat.get("beat_visual_spec") or (beat.get("visual_plan") or {}).get("beat_visual_spec") or {}
        storyboard_visual_spec = paired.get("beat_visual_spec") or paired_visual_plan.get("beat_visual_spec") or {}
        pairings.append(_pairing(beat, paired, "paired", live_vectors, scene_point_ids))
        if paired_visual_plan.get("type") == "text_only":
            continue
        if not isinstance(beat_visual_spec, dict) or not beat_visual_spec:
            beat_findings.append(f"{title}: beat is missing beat_visual_spec.")
        if not isinstance(storyboard_visual_spec, dict) or not storyboard_visual_spec:
            beat_findings.append(f"{title}: storyboard is missing beat_visual_spec.")
        if isinstance(beat_visual_spec, dict) and isinstance(storyboard_visual_spec, dict) and beat_visual_spec and storyboard_visual_spec:
            if beat_visual_spec.get("family") != storyboard_visual_spec.get("family") or beat_visual_spec.get("beat") != storyboard_visual_spec.get("beat"):
                beat_findings.append(
                    f"{title}: beat_visual_spec mismatch beat={beat_visual_spec.get('family')}/{beat_visual_spec.get('beat')} "
                    f"storyboard={storyboard_visual_spec.get('family')}/{storyboard_visual_spec.get('beat')}."
                )
            spec_text = " ".join([
                beat_text,
                json.dumps(paired.get("labels") or [], ensure_ascii=False),
                json.dumps(paired.get("visual_state") or {}, ensure_ascii=False),
                live_vector_labels,
            ])
            for error in validate_beat_visual_spec(storyboard_visual_spec, text=spec_text):
                beat_findings.append(f"{title}: {error}.")
            beat_findings.extend(forbidden_visual_findings(title, storyboard_visual_spec, spec_text))
        overlays = set(paired.get("overlays") or [])
        visible_vectors = set(paired.get("visible_vectors") or [])
        visual_action = str(paired.get("visual_action") or "")
        if "show_trajectory" in overlays and is_static_teaching_beat(beat_text, visual_action):
            beat_findings.append(f"{title}: static teaching beat still asks for full trajectory overlay.")
        if mentions_resolved_gravity_component(beat_text):
            if "*:a" not in visible_vectors and "gravity" not in scene_text:
                beat_findings.append(f"{title}: mentions resolved gravity component, but storyboard does not expose acceleration vectors.")
            if not any(token in live_vector_labels for token in ("gsin", "g sin", "gcos", "g cos")):
                beat_findings.append(f"{title}: resolved gravity component is not labeled in live_vectors.")
        if mentions_axis_resolution(beat_text):
            if not any("axis" in item for item in visible_vectors):
                beat_findings.append(f"{title}: talks about axes/components, but visible_vectors has no axis vector.")
        if has_formula_without_substitution(beat):
            beat_findings.append(f"{title}: formula appears without a clear substitution/calculation reveal.")
        if generic_teacher_text(beat_text):
            beat_findings.append(f"{title}: teacher text is generic or imperative instead of explanatory.")
        missing_points = [
            point_id
            for point_id in _point_ids_from_scene_ids(_highlight_ids_for_pairing(paired))
            if point_id not in scene_point_ids
        ]
        if missing_points:
            beat_findings.append(f"{title}: highlights missing scene point(s): {', '.join(missing_points)}.")

    findings.extend(beat_findings)
    hard_fail = hard_fail or ("beat-animation sync issues" if beat_findings else "")
    return {
        "ok": not hard_fail,
        "hard_fail_reason": hard_fail,
        "findings": findings,
        "walkthrough_score": score_walkthrough(beats, findings),
        "animation_score": score_animation(animation_scene, findings),
        "teacher_score": score_teacher(beats, findings),
        "beat_pairings": pairings,
        "render_probe_contract": {
            "surface": "teaching_board_2d",
            "root_selector": "[data-audit-surface='teaching-board-2d']",
            "full_lifecycle_selector": "[data-audit-surface='animation-scene-3d'][data-audit-step-id='__full_lifecycle']",
            "beat_probes": [pairing["render_probe"] for pairing in pairings],
        },
    }


def render_beat_pairing_markdown(audit: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for pairing in audit.get("beat_pairings") or []:
        lines.extend([
            f"### {pairing.get('title') or pairing.get('beat_id')}",
            "",
            f"- Step id: `{pairing.get('step_id') or '-'}`",
            f"- Pairing status: `{pairing.get('status') or '-'}`",
            f"- Beat visual: `{pairing.get('beat_visual') or '-'}`",
            f"- Animation action: `{pairing.get('animation_action') or '-'}`",
            f"- Visible vectors: `{', '.join(pairing.get('visible_vectors') or []) or '-'}`",
            f"- Rendered vector ids expected: `{', '.join(pairing.get('render_probe', {}).get('expected_vector_ids') or []) or '-'}`",
            f"- Overlays: `{', '.join(pairing.get('overlays') or []) or '-'}`",
            f"- Highlights: `{', '.join(pairing.get('highlight_ids') or []) or '-'}`",
            "",
            code_block(str(pairing.get("learner_message") or "")),
            "",
        ])
    return lines or ["No paired walkthrough/animation data."]


def beat_text_blob(beat: dict[str, Any]) -> str:
    parts = [
        beat.get("title") or "",
        beat.get("learner_message") or "",
        beat.get("visual_instruction") or "",
        beat.get("why_it_matters") or "",
    ]
    for reveal in beat.get("sub_reveals") or []:
        parts.append(reveal.get("text") or "")
        parts.append(reveal.get("visual_instruction") or "")
        parts.extend(reveal.get("formula_lines") or [])
    return " ".join(str(part) for part in parts).lower()


def mentions_resolved_gravity_component(text: str) -> bool:
    compact = text.replace(" ", "")
    return any(token in compact for token in ("gsin", "gcos", "g*sin", "g*cos"))


def mentions_axis_resolution(text: str) -> bool:
    return any(token in text for token in ("axis", "component", "resolve", "along the plane", "normal to"))


def is_static_teaching_beat(text: str, visual_action: str) -> bool:
    if visual_action in {"show_full_scene", "show_motion_progress", "show_normal_return", "highlight_collision"}:
        return False
    return any(token in text for token in ("given", "read the diagram", "axis", "component", "condition", "equation", "substitute"))


def has_formula_without_substitution(beat: dict[str, Any]) -> bool:
    reveals = beat.get("sub_reveals") or []
    has_formula = any(
        _formula_line_needs_substitution(str(line))
        for reveal in reveals
        for line in reveal.get("formula_lines") or []
    )
    has_substitution_text = any(
        re.search(r"\d+\s*[×x*/+-]\s*\d+|substitut|put .*value|=", " ".join(reveal.get("formula_lines") or []) + " " + str(reveal.get("text") or ""), re.I)
        for reveal in reveals
    )
    return has_formula and not has_substitution_text


def _formula_line_needs_substitution(line: str) -> bool:
    cleaned = line.strip().lower()
    if not cleaned or cleaned.startswith(("to find", "normal axis", "u is ", "q stays ")):
        return False
    if re.fullmatch(r"[a-z][a-z0-9_]*", cleaned):
        return False
    return bool(re.search(r"=|>=|<=|∝|sqrt|sin|cos|tan|\bt[_a-z0-9]*\b|\bu[_a-z0-9]*\b|\bv[_a-z0-9]*\b", cleaned))


def generic_teacher_text(text: str) -> bool:
    weak_phrases = [
        "now we use the relation",
        "this equation is used because",
        "using physical invariant",
        "compute the requested answer",
        "use the highlighted diagram quantity",
    ]
    return any(phrase in text for phrase in weak_phrases)


def forbidden_visual_findings(title: str, spec: dict[str, Any], text: str) -> list[str]:
    findings: list[str] = []
    for forbidden in spec.get("must_not_show") or []:
        for pattern in FORBIDDEN_TEXT_PATTERNS.get(str(forbidden), ()):
            if re.search(pattern, text, re.I):
                findings.append(f"{title}: forbidden visual `{forbidden}` appears in synced labels/text.")
                break
    return findings


def score_walkthrough(beats: list[dict[str, Any]], findings: list[str]) -> int:
    if not beats:
        return 0
    penalty = sum(1 for finding in findings if "formula" in finding or "teacher text" in finding)
    return max(0, min(2, 2 - penalty))


def score_animation(animation_scene: dict[str, Any] | None, findings: list[str]) -> int:
    if not animation_scene:
        return 0
    penalty = sum(1 for finding in findings if "storyboard" in finding or "trajectory" in finding or "vector" in finding or "axis" in finding)
    return max(0, min(2, 2 - penalty))


def score_teacher(beats: list[dict[str, Any]], findings: list[str]) -> int:
    if not beats:
        return 0
    penalty = sum(1 for finding in findings if "teacher text" in finding or "substitution" in finding)
    return max(0, min(2, 2 - penalty))


def _pairing(
    beat: dict[str, Any],
    storyboard_step: dict[str, Any],
    status: str,
    live_vectors: list[dict[str, Any]],
    scene_point_ids: set[str],
) -> dict[str, Any]:
    step_id = str(beat.get("step_id") or beat.get("id") or "")
    visible_vector_patterns = storyboard_step.get("visual_state", {}).get("visible_vectors") or storyboard_step.get("visible_vectors") or []
    expected_vector_ids = _resolve_vector_patterns(live_vectors, visible_vector_patterns)
    overlays = [str(item) for item in storyboard_step.get("overlays") or []]
    highlight_ids = _highlight_ids_for_pairing(storyboard_step)
    expected_point_ids = [
        point_id for point_id in _point_ids_from_scene_ids(highlight_ids)
        if point_id in scene_point_ids
    ]
    return {
        "beat_id": beat.get("id") or "",
        "step_id": step_id,
        "title": beat.get("title") or "",
        "status": status,
        "learner_message": beat.get("learner_message") or "",
        "beat_visual": beat.get("visual_instruction") or "",
        "beat_visual_spec": storyboard_step.get("beat_visual_spec") or (storyboard_step.get("visual_plan") or {}).get("beat_visual_spec") or {},
        "animation_action": storyboard_step.get("visual_action") or "",
        "visible_vectors": [str(item) for item in visible_vector_patterns],
        "overlays": overlays,
        "highlight_ids": highlight_ids,
        "render_probe": {
            "step_id": step_id,
            "surface_selector": f"[data-audit-surface='teaching-board-2d'][data-audit-step-id={json.dumps(step_id)}]",
            "expected_vector_ids": expected_vector_ids,
            "expected_vector_selectors": [
                f"[data-audit-vector-id={json.dumps(vector_id)}]"
                for vector_id in expected_vector_ids
            ],
            "expected_highlight_ids": highlight_ids,
            "expected_point_ids": expected_point_ids,
            "expected_surface_ids": _surface_ids_from_scene_ids(highlight_ids),
            "expected_show_trajectory": any(item in overlays for item in ("show_trajectory", "show_motion_progress")),
            "expected_overlay_flags": overlays,
            "requires_render_verification": status == "paired",
        },
    }


def _resolve_vector_patterns(live_vectors: list[dict[str, Any]], patterns: list[Any]) -> list[str]:
    vector_ids = [str(vector.get("id") or "") for vector in live_vectors if vector.get("id")]
    resolved: list[str] = []
    for raw_pattern in patterns:
        pattern = str(raw_pattern)
        if not pattern or pattern == "__none__":
            continue
        if pattern in vector_ids:
            resolved.append(pattern)
            continue
        if pattern.startswith("*:"):
            suffix = pattern[1:]
            resolved.extend(vector_id for vector_id in vector_ids if vector_id.endswith(suffix))
    return sorted(set(resolved))


def _highlight_ids_for_pairing(storyboard_step: dict[str, Any]) -> list[str]:
    return [
        str(item)
        for item in storyboard_step.get("visual_state", {}).get("highlight_ids") or storyboard_step.get("highlight_ids") or []
    ]


def _point_ids_from_scene_ids(scene_ids: list[str]) -> list[str]:
    return sorted({item.split(":", 1)[1] for item in scene_ids if item.startswith("point:") and ":" in item})


def _surface_ids_from_scene_ids(scene_ids: list[str]) -> list[str]:
    return sorted({item.split(":", 1)[1] for item in scene_ids if item.startswith("surface:") and ":" in item})


def code_block(text: str) -> str:
    return "```text\n" + str(text).strip() + "\n```"
