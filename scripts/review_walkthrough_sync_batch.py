#!/usr/bin/env python3
"""Generate walkthrough/animation sync review artifacts for question images.

This is a diagnostic runner. It calls the same image extraction, deterministic
solver, walkthrough, and animation-scene builders used by the app, then writes
the raw outputs plus a compact markdown audit.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.prompt_engine import PromptEngine
from core.projectile_engine import build_solution_walkthrough, solve_ad_hoc_question
from core.projectile_engine.animation_scene import build_animation_scene_spec
from core.walkthrough_sync_audit import audit_walkthrough_sync, render_beat_pairing_markdown


SCREENSHOT_DIR = Path(os.getenv("PHYSICA_SCREENSHOT_DIR", str(Path.home() / "Desktop"))).expanduser()
DEFAULT_IMAGES = [
    str(SCREENSHOT_DIR / "Screenshot 2026-05-25 at 9.44.11 PM.png"),
    str(SCREENSHOT_DIR / "Screenshot 2026-05-25 at 9.44.18 PM.png"),
    str(SCREENSHOT_DIR / "Screenshot 2026-05-25 at 9.44.24 PM.png"),
    str(SCREENSHOT_DIR / "Screenshot 2026-05-25 at 9.44.30 PM.png"),
    str(SCREENSHOT_DIR / "Screenshot 2026-05-25 at 9.44.36 PM.png"),
    str(SCREENSHOT_DIR / "Screenshot 2026-05-25 at 9.44.42 PM.png"),
    str(SCREENSHOT_DIR / "Screenshot 2026-05-25 at 12.41.58 PM.png"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Review walkthrough and animation sync for image questions.")
    parser.add_argument("images", nargs="*", help="Image paths. Defaults to the current five screenshots.")
    parser.add_argument("--out-dir", type=Path, default=None, help="Directory for review artifacts.")
    parser.add_argument("--no-vlm", action="store_true", help="Skip VLM extraction and only create an empty review shell.")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    image_paths = [Path(path).expanduser().resolve() for path in (args.images or DEFAULT_IMAGES)]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (args.out_dir or ROOT / "questions" / "walkthrough_sync_reviews" / run_id).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("GROQ_API_KEY") or os.getenv("GOOGLE_API_KEY")
    engine = None if args.no_vlm or not api_key else PromptEngine(api_key=api_key)

    summaries: list[dict[str, Any]] = []
    for index, image_path in enumerate(image_paths, start=1):
        case_id = f"q{index:02d}_{slugify(image_path.stem)}"
        case_dir = out_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        summary = process_case(case_id=case_id, image_path=image_path, case_dir=case_dir, engine=engine)
        summaries.append(summary)

    (out_dir / "summary.json").write_text(json.dumps(summaries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "README.md").write_text(render_run_readme(summaries), encoding="utf-8")
    print(out_dir)
    failed = [item for item in summaries if item.get("hard_fail_reason")]
    if failed:
        for item in failed:
            print(f"FAIL {item['case_id']}: {item.get('hard_fail_reason')}", file=sys.stderr)
        raise SystemExit(1)


def process_case(*, case_id: str, image_path: Path, case_dir: Path, engine: PromptEngine | None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "case_id": case_id,
        "image_path": str(image_path),
        "extraction_status": "not_run",
        "solver_status": "not_run",
        "engine_case": None,
        "answer": None,
        "hard_fail_reason": "",
        "audit_path": str(case_dir / "audit.md"),
    }

    if not image_path.exists():
        summary["extraction_status"] = "missing_image"
        summary["hard_fail_reason"] = "image file does not exist"
        write_case_audit(case_dir, summary, None, None, None, None)
        return summary

    extraction = None
    if engine is None:
        summary["extraction_status"] = "skipped_no_vlm"
    else:
        try:
            image_bytes = image_path.read_bytes()
            mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
            extraction_model = engine.extract_question_from_image(image_bytes=image_bytes, image_mime_type=mime_type)
            extraction = extraction_model.model_dump(mode="json")
            summary["extraction_status"] = "ok"
            (case_dir / "extraction.json").write_text(json.dumps(extraction, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception as exc:
            extraction = {"error": str(exc)}
            summary["extraction_status"] = "error"
            summary["hard_fail_reason"] = f"image extraction failed: {exc}"
            (case_dir / "extraction_error.json").write_text(json.dumps(extraction, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    solve_payload = None
    walkthrough = None
    animation_scene = None
    if extraction and not extraction.get("error"):
        question_text = extraction.get("question_text_solver") or extraction.get("cleaned_prompt") or extraction.get("question_text") or ""
        try:
            result = solve_ad_hoc_question(
                question_text=question_text,
                engine_case=extraction.get("suggested_engine_case"),
                options=extraction.get("options") or [],
                givens=extraction.get("givens") or [],
                requested_quantity=extraction.get("requested_quantity"),
                diagram=extraction.get("diagram"),
                require_diagram_validation=bool(extraction.get("diagram")),
            )
            summary["solver_status"] = result.status
            summary["engine_case"] = result.engine_case
            summary["answer"] = result.computed_text
            solve_payload = {
                "status": result.status,
                "reason": result.reason,
                "engine_case": result.engine_case,
                "template_id": result.template_id,
                "template_confidence": result.template_confidence,
                "template_reason": result.template_reason,
                "template_warnings": result.template_warnings,
                "diagram_valid": result.diagram_valid,
                "diagram_warnings": result.diagram_warnings,
                "answer": result.computed_text,
                "matched_option": result.predicted_option_letter,
                "computed_value": result.computed_value,
                "trace": result.trace,
                "equation_plan": result.equation_plan,
            }
            if result.status == "passed":
                walkthrough = build_solution_walkthrough(result)
                animation_scene = build_animation_scene_spec(
                    result=result,
                    question_text=question_text,
                    givens=extraction.get("givens") or [],
                )
            elif not summary["hard_fail_reason"]:
                summary["hard_fail_reason"] = result.reason or f"solver status {result.status}"
            (case_dir / "solve.json").write_text(json.dumps(solve_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            if walkthrough is not None:
                (case_dir / "walkthrough.json").write_text(json.dumps(walkthrough, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            if animation_scene is not None:
                (case_dir / "animation_scene.json").write_text(json.dumps(animation_scene, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception as exc:
            summary["solver_status"] = "error"
            summary["hard_fail_reason"] = f"solve/build failed: {exc}"
            (case_dir / "solve_error.json").write_text(json.dumps({"error": str(exc)}, indent=2) + "\n", encoding="utf-8")

    review = review_sync(extraction, solve_payload, walkthrough, animation_scene)
    if not summary["hard_fail_reason"]:
        summary["hard_fail_reason"] = review.get("hard_fail_reason", "")
    summary.update({
        "walkthrough_score": review.get("walkthrough_score"),
        "animation_score": review.get("animation_score"),
        "teacher_score": review.get("teacher_score"),
    })
    write_case_audit(case_dir, summary, extraction, solve_payload, walkthrough, animation_scene, review)
    return summary


def review_sync(
    extraction: dict[str, Any] | None,
    solve_payload: dict[str, Any] | None,
    walkthrough: dict[str, Any] | None,
    animation_scene: dict[str, Any] | None,
) -> dict[str, Any]:
    findings: list[str] = []

    if not extraction:
        return {
            "hard_fail_reason": "no extraction available",
            "findings": ["No extraction was generated."],
            "walkthrough_score": 0,
            "animation_score": 0,
            "teacher_score": 0,
        }
    if extraction.get("error"):
        return {
            "hard_fail_reason": "image extraction failed",
            "findings": [str(extraction.get("error"))],
            "walkthrough_score": 0,
            "animation_score": 0,
            "teacher_score": 0,
        }

    diagram = extraction.get("diagram") or {}
    if diagram.get("present") and not diagram.get("entities"):
        findings.append("Diagram is present, but normalized extraction has no diagram entities.")
    if extraction.get("confidence", 1) < 0.75:
        findings.append(f"Extraction confidence is low: {extraction.get('confidence')}.")

    if not solve_payload or solve_payload.get("status") != "passed":
        hard_fail = solve_payload.get("reason") if solve_payload else "solver did not run"
        findings.append(f"Solver did not pass: {hard_fail}")
        return {
            "hard_fail_reason": hard_fail,
            "findings": findings,
            "walkthrough_score": 0,
            "animation_score": 0,
            "teacher_score": 0,
        }

    audit = audit_walkthrough_sync(walkthrough=walkthrough, animation_scene=animation_scene)
    return {
        **audit,
        "findings": [*findings, *(audit.get("findings") or [])],
    }


def write_case_audit(
    case_dir: Path,
    summary: dict[str, Any],
    extraction: dict[str, Any] | None,
    solve_payload: dict[str, Any] | None,
    walkthrough: dict[str, Any] | None,
    animation_scene: dict[str, Any] | None,
    review: dict[str, Any] | None = None,
) -> None:
    review = review or {"findings": []}
    lines = [
        f"# {summary['case_id']}",
        "",
        f"- Image: `{summary['image_path']}`",
        f"- Extraction: `{summary['extraction_status']}`",
        f"- Solver: `{summary['solver_status']}`",
        f"- Engine case: `{summary.get('engine_case') or '-'}`",
        f"- Answer: `{summary.get('answer') or '-'}`",
        f"- Hard fail: `{summary.get('hard_fail_reason') or '-'}`",
        f"- Walkthrough score: `{summary.get('walkthrough_score')}`",
        f"- Animation score: `{summary.get('animation_score')}`",
        f"- Teacher score: `{summary.get('teacher_score')}`",
        "",
        "## Extracted Question",
        "",
        code_block((extraction or {}).get("question_text_display") or (extraction or {}).get("question_text_solver") or ""),
        "",
        "## Diagram Facts",
        "",
        code_block(json.dumps((extraction or {}).get("diagram") or {}, indent=2, ensure_ascii=False)),
        "",
        "## Findings",
        "",
    ]
    findings = review.get("findings") or []
    lines.extend([f"- {item}" for item in findings] or ["- No automated findings."])
    lines.extend(["", "## Beat Pairing", ""])
    lines.extend(render_beat_pairing_markdown(review))
    (case_dir / "audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_beat_pairing(walkthrough: dict[str, Any] | None, animation_scene: dict[str, Any] | None) -> list[str]:
    if not walkthrough or not animation_scene:
        return ["No paired walkthrough/animation data."]
    storyboard = {
        str(step.get("step_id")): step
        for step in animation_scene.get("storyboard") or []
    }
    lines: list[str] = []
    for beat in walkthrough.get("explainer_beats") or []:
        step_id = str(beat.get("step_id") or beat.get("id") or "")
        paired = storyboard.get(step_id, {})
        lines.extend([
            f"### {beat.get('title') or beat.get('id')}",
            "",
            f"- Step id: `{step_id}`",
            f"- Beat visual: `{beat.get('visual_instruction') or '-'}`",
            f"- Animation action: `{paired.get('visual_action') or '-'}`",
            f"- Visible vectors: `{', '.join(paired.get('visible_vectors') or []) or '-'}`",
            f"- Overlays: `{', '.join(paired.get('overlays') or []) or '-'}`",
            f"- Highlights: `{', '.join(paired.get('highlight_ids') or []) or '-'}`",
            "",
            code_block(str(beat.get("learner_message") or "")),
            "",
        ])
    return lines


def render_run_readme(summaries: list[dict[str, Any]]) -> str:
    lines = [
        "# Walkthrough Sync Review Batch",
        "",
        "| Case | Extraction | Solver | Engine | Answer | Hard fail |",
        "|---|---|---|---|---|---|",
    ]
    for item in summaries:
        lines.append(
            f"| {item['case_id']} | {item['extraction_status']} | {item['solver_status']} | "
            f"{item.get('engine_case') or '-'} | {escape_md(item.get('answer') or '-')} | "
            f"{escape_md(item.get('hard_fail_reason') or '-')} |"
        )
    lines.append("")
    lines.append("Open each case `audit.md` for beat-by-beat pairing.")
    return "\n".join(lines) + "\n"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


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
    if visual_action in {"show_full_scene", "show_motion_progress", "highlight_collision"}:
        return False
    return any(token in text for token in ("given", "read the diagram", "axis", "component", "condition", "equation", "substitute"))


def has_formula_without_substitution(beat: dict[str, Any]) -> bool:
    reveals = beat.get("sub_reveals") or []
    has_formula = any(reveal.get("formula_lines") for reveal in reveals)
    has_substitution_text = any(
        re.search(r"\d+\s*[×x*/+-]\s*\d+|substitut|put .*value|=", " ".join(reveal.get("formula_lines") or []) + " " + str(reveal.get("text") or ""), re.I)
        for reveal in reveals
    )
    return has_formula and not has_substitution_text


def generic_teacher_text(text: str) -> bool:
    weak_phrases = [
        "now we use the relation",
        "this equation is used because",
        "using physical invariant",
        "compute the requested answer",
        "use the highlighted diagram quantity",
    ]
    return any(phrase in text for phrase in weak_phrases)


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


def code_block(text: str) -> str:
    return "```text\n" + str(text).strip() + "\n```"


def slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()[:80] or "image"


def escape_md(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    main()
