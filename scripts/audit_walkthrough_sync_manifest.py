#!/usr/bin/env python3
"""Audit walkthrough/storyboard/render contracts for a projectile manifest."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.projectile_engine import build_solution_walkthrough, evaluate_manifest_entry
from core.projectile_engine.animation_scene import build_animation_scene_spec
from core.walkthrough_sync_audit import audit_walkthrough_sync, render_beat_pairing_markdown


DEFAULT_MANIFEST = ROOT / "questions" / "manifest" / "projectile_dpp_manifest.json"
DEFAULT_OUT_DIR = ROOT / "questions" / "walkthrough_sync_manifest_audits" / "latest"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--limit", type=int, default=0, help="Only audit the first N manifest entries.")
    parser.add_argument("--case", action="append", default=[], help="Audit labels containing this text, e.g. Q05 or projectileinc.")
    parser.add_argument("--fail-on-issues", action="store_true", help="Exit non-zero when any sync issues are found.")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    out_dir = args.out_dir.resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    if args.case:
        needles = [needle.lower() for needle in args.case]
        entries = [
            entry for entry in entries
            if any(needle in _entry_label(entry).lower() or needle in str(entry.get("engine_case", "")).lower() for needle in needles)
        ]
    if args.limit:
        entries = entries[: args.limit]

    summaries: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        summaries.append(_audit_entry(entry, index=index, out_dir=out_dir))

    summary = _run_summary(summaries, manifest_path=manifest_path)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "README.md").write_text(_render_readme(summary, summaries), encoding="utf-8")

    print(_one_line_summary(summary))
    print(out_dir)
    if args.fail_on_issues and summary["sync_issue_cases"]:
        raise SystemExit(1)


def _audit_entry(entry: dict[str, Any], *, index: int, out_dir: Path) -> dict[str, Any]:
    label = _entry_label(entry)
    case_id = f"{index:02d}_{slugify(label)}_{slugify(str(entry.get('engine_case') or 'case'))}"
    case_dir = out_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "case_id": case_id,
        "label": label,
        "engine_case": entry.get("engine_case"),
        "question_text": entry.get("question_text"),
        "solver_status": "not_run",
        "scene_status": "not_run",
        "sync_ok": False,
        "hard_fail_reason": "",
        "finding_count": 0,
        "finding_categories": [],
        "case_dir": str(case_dir.relative_to(out_dir)),
    }
    (case_dir / "entry.json").write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    walkthrough = None
    animation_scene = None
    audit = None
    try:
        result = evaluate_manifest_entry(entry)
        summary["solver_status"] = result.status
        summary["answer"] = result.computed_text
        summary["matched_option"] = result.predicted_option_letter
        (case_dir / "solve.json").write_text(json.dumps(_to_jsonable(result), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception as exc:
        summary["solver_status"] = "error"
        summary["hard_fail_reason"] = f"solver crashed: {exc}"
        (case_dir / "error.json").write_text(json.dumps({"stage": "solve", "error": str(exc)}, indent=2) + "\n", encoding="utf-8")
        _write_case_readme(case_dir, summary, audit)
        return summary

    if result.status != "passed":
        summary["hard_fail_reason"] = result.reason or f"solver status {result.status}"
        _write_case_readme(case_dir, summary, audit)
        return summary

    try:
        walkthrough = build_solution_walkthrough(result)
        animation_scene = build_animation_scene_spec(
            result=result,
            question_text=str(entry.get("question_text") or ""),
            givens=list(entry.get("knowns") or []),
        )
        summary["scene_status"] = "ok" if animation_scene else "missing"
        (case_dir / "walkthrough.json").write_text(json.dumps(walkthrough, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if animation_scene is not None:
            (case_dir / "animation_scene.json").write_text(json.dumps(animation_scene, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception as exc:
        summary["scene_status"] = "error"
        summary["hard_fail_reason"] = f"walkthrough/scene build crashed: {exc}"
        (case_dir / "error.json").write_text(json.dumps({"stage": "scene", "error": str(exc)}, indent=2) + "\n", encoding="utf-8")
        _write_case_readme(case_dir, summary, audit)
        return summary

    audit = audit_walkthrough_sync(walkthrough=walkthrough, animation_scene=animation_scene)
    findings = list(audit.get("findings") or [])
    categories = [_finding_category(finding) for finding in findings]
    summary.update({
        "sync_ok": bool(audit.get("ok")),
        "hard_fail_reason": audit.get("hard_fail_reason") or "",
        "finding_count": len(findings),
        "finding_categories": sorted(set(categories)),
        "walkthrough_score": audit.get("walkthrough_score"),
        "animation_score": audit.get("animation_score"),
        "teacher_score": audit.get("teacher_score"),
    })
    (case_dir / "audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (case_dir / "render_probe_contract.json").write_text(
        json.dumps(audit.get("render_probe_contract") or {}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (case_dir / "render_payload.json").write_text(
        json.dumps({
            "solver": {
                "status": result.status,
                "reason": result.reason,
                "engine_case": result.engine_case,
                "answer": result.computed_text,
                "matched_option": result.predicted_option_letter,
            },
            "walkthrough": walkthrough,
            "animation_scene_spec": animation_scene,
            "audit": audit,
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_case_readme(case_dir, summary, audit)
    return summary


def _run_summary(summaries: list[dict[str, Any]], *, manifest_path: Path) -> dict[str, Any]:
    status_counts = Counter(item.get("solver_status") for item in summaries)
    scene_counts = Counter(item.get("scene_status") for item in summaries)
    category_counts = Counter(
        category
        for item in summaries
        for category in item.get("finding_categories") or []
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "total_cases": len(summaries),
        "solver_status_counts": dict(sorted(status_counts.items())),
        "scene_status_counts": dict(sorted(scene_counts.items())),
        "sync_ok_cases": sum(1 for item in summaries if item.get("sync_ok")),
        "sync_issue_cases": sum(1 for item in summaries if item.get("hard_fail_reason") or item.get("finding_count")),
        "finding_category_counts": dict(category_counts.most_common()),
        "cases": summaries,
    }


def _render_readme(summary: dict[str, Any], summaries: list[dict[str, Any]]) -> str:
    lines = [
        "# Walkthrough Sync Manifest Audit",
        "",
        f"- Manifest: `{summary['manifest']}`",
        f"- Total cases: `{summary['total_cases']}`",
        f"- Solver status: `{json.dumps(summary['solver_status_counts'], sort_keys=True)}`",
        f"- Scene status: `{json.dumps(summary['scene_status_counts'], sort_keys=True)}`",
        f"- Sync OK: `{summary['sync_ok_cases']}`",
        f"- Sync issues: `{summary['sync_issue_cases']}`",
        "",
        "## Finding Categories",
        "",
    ]
    category_counts = summary.get("finding_category_counts") or {}
    lines.extend([f"- `{name}`: {count}" for name, count in category_counts.items()] or ["- No findings."])
    lines.extend([
        "",
        "## Cases",
        "",
        "| Case | Solver | Scene | Sync | Findings | Categories |",
        "| --- | --- | --- | --- | ---: | --- |",
    ])
    for item in summaries:
        categories = ", ".join(item.get("finding_categories") or []) or "-"
        sync = "ok" if item.get("sync_ok") else (item.get("hard_fail_reason") or "issues")
        case_link = f"[{item['label']}]({item['case_dir']}/README.md)"
        lines.append(
            f"| {case_link} | `{item.get('solver_status')}` | `{item.get('scene_status')}` | "
            f"`{sync}` | {item.get('finding_count', 0)} | `{categories}` |"
        )
    return "\n".join(lines) + "\n"


def _write_case_readme(case_dir: Path, summary: dict[str, Any], audit: dict[str, Any] | None) -> None:
    lines = [
        f"# {summary['label']}",
        "",
        f"- Engine case: `{summary.get('engine_case') or '-'}`",
        f"- Solver: `{summary.get('solver_status')}`",
        f"- Scene: `{summary.get('scene_status')}`",
        f"- Sync: `{'ok' if summary.get('sync_ok') else (summary.get('hard_fail_reason') or 'issues')}`",
        f"- Findings: `{summary.get('finding_count', 0)}`",
        "",
        "## Question",
        "",
        "```text",
        str(summary.get("question_text") or "").strip(),
        "```",
        "",
        "## Findings",
        "",
    ]
    findings = list((audit or {}).get("findings") or [])
    lines.extend([f"- {finding}" for finding in findings] or ["- No automated findings."])
    if audit:
        lines.extend(["", "## Beat Pairings", ""])
        lines.extend(render_beat_pairing_markdown(audit))
    case_dir.joinpath("README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _one_line_summary(summary: dict[str, Any]) -> str:
    return (
        "Manifest sync audit: "
        f"{summary['sync_ok_cases']} ok / "
        f"{summary['sync_issue_cases']} issues / "
        f"{summary['total_cases']} total; "
        f"categories={summary['finding_category_counts']}"
    )


def _entry_label(entry: dict[str, Any]) -> str:
    return f"{entry.get('pdf_id', 'manifest')} Q{int(entry.get('question_number') or 0):02d}"


def _finding_category(finding: str) -> str:
    lowered = finding.lower()
    if "missing scene point" in lowered:
        return "missing_scene_point"
    if "trajectory overlay" in lowered:
        return "static_trajectory_overlay"
    if "axis vector" in lowered:
        return "missing_axis_vector"
    if "acceleration vectors" in lowered or "resolved gravity" in lowered:
        return "missing_resolved_gravity_vector"
    if "formula" in lowered or "substitution" in lowered:
        return "weak_formula_reveal"
    if "teacher text" in lowered or "generic" in lowered:
        return "generic_teacher_text"
    if "storyboard" in lowered:
        return "missing_storyboard"
    if "missing animation scene" in lowered:
        return "missing_animation_scene"
    if "missing walkthrough" in lowered:
        return "missing_walkthrough"
    return "other"


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return slug[:96] or "case"


if __name__ == "__main__":
    main()
