#!/usr/bin/env python3
"""Run the 60-question projectile practice corpus through solver and beat audits."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "testdata" / "projectile" / "practice_60_manifest.json"
DEFAULT_OUT_DIR = ROOT / "questions" / "projectile_practice_runs" / "latest"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.projectile_engine import build_solution_walkthrough, solve_ad_hoc_question  # noqa: E402
from core.projectile_engine.animation_scene import build_animation_scene_spec  # noqa: E402
from core.walkthrough_sync_audit import audit_walkthrough_sync  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--case", type=int, action="append", default=[])
    parser.add_argument("--fail-on-issues", action="store_true")
    args = parser.parse_args()

    # Keep this corpus reproducible. Production may use hybrid, but this local
    # acceptance run should expose deterministic parser/solver gaps first.
    os.environ.setdefault("PROJECTILE_CLASSIFIER", "rules")

    entries = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.case:
        wanted = set(args.case)
        entries = [entry for entry in entries if int(entry.get("question_number") or 0) in wanted]
    if args.limit:
        entries = entries[: args.limit]

    out_dir = args.out_dir.resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summaries = [_run_entry(entry, index=index, out_dir=out_dir) for index, entry in enumerate(entries, start=1)]
    summary = summarize(summaries, manifest_path=args.manifest.resolve())
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "README.md").write_text(render_readme(summary, summaries), encoding="utf-8")

    print(one_line_summary(summary))
    print(out_dir)
    if args.fail_on_issues and summary["issue_cases"]:
        raise SystemExit(1)


def _run_entry(entry: dict[str, Any], *, index: int, out_dir: Path) -> dict[str, Any]:
    question_number = int(entry.get("question_number") or index)
    label = f"practice60 Q{question_number:02d}"
    case_id = f"{question_number:02d}_{slugify(entry.get('question_text') or 'question')}"
    case_dir = out_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    question_text = str(entry.get("question_text") or "")
    summary: dict[str, Any] = {
        "case_id": case_id,
        "label": label,
        "question_number": question_number,
        "question_text": question_text,
        "solver_status": "not_run",
        "engine_case": "",
        "answer": "",
        "scene_status": "not_run",
        "sync_ok": False,
        "hard_fail_reason": "",
        "finding_count": 0,
        "finding_categories": [],
        "case_dir": str(case_dir.relative_to(out_dir)),
    }
    (case_dir / "entry.json").write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    try:
        result = solve_ad_hoc_question(
            question_text=question_text,
            engine_case=entry.get("suggested_engine_case"),
            options=list(entry.get("options") or []),
            givens=list(entry.get("givens") or []),
            requested_quantity=entry.get("requested_quantity"),
            diagram=entry.get("diagram"),
            require_diagram_validation=False,
        )
    except Exception as exc:  # noqa: BLE001 - acceptance reports should continue.
        summary.update({"solver_status": "error", "hard_fail_reason": f"solver crashed: {type(exc).__name__}: {exc}"})
        write_case_readme(case_dir, summary, None)
        return summary

    summary.update({
        "solver_status": result.status,
        "engine_case": result.engine_case,
        "answer": result.computed_text or "",
        "hard_fail_reason": result.reason if result.status != "passed" else "",
    })
    (case_dir / "solve.json").write_text(json.dumps(to_jsonable(result), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if result.status != "passed":
        write_case_readme(case_dir, summary, None)
        return summary

    try:
        walkthrough = build_solution_walkthrough(result)
        scene = build_animation_scene_spec(result=result, question_text=question_text, givens=list(entry.get("givens") or []))
        audit = audit_walkthrough_sync(walkthrough=walkthrough, animation_scene=scene)
    except Exception as exc:  # noqa: BLE001 - acceptance reports should continue.
        summary.update({"scene_status": "error", "hard_fail_reason": f"scene crashed: {type(exc).__name__}: {exc}"})
        write_case_readme(case_dir, summary, None)
        return summary

    findings = list(audit.get("findings") or [])
    categories = [finding_category(finding) for finding in findings]
    summary.update({
        "scene_status": "ok" if scene else "missing",
        "sync_ok": bool(audit.get("ok")),
        "hard_fail_reason": audit.get("hard_fail_reason") or "",
        "finding_count": len(findings),
        "finding_categories": sorted(set(categories)),
        "walkthrough_score": audit.get("walkthrough_score"),
        "animation_score": audit.get("animation_score"),
        "teacher_score": audit.get("teacher_score"),
    })
    (case_dir / "walkthrough.json").write_text(json.dumps(walkthrough, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (case_dir / "animation_scene.json").write_text(json.dumps(scene, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (case_dir / "audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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
            "animation_scene_spec": scene,
            "audit": audit,
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_case_readme(case_dir, summary, audit)
    return summary


def summarize(summaries: list[dict[str, Any]], *, manifest_path: Path) -> dict[str, Any]:
    solver_counts = Counter(item.get("solver_status") for item in summaries)
    engine_counts = Counter(item.get("engine_case") or "unknown" for item in summaries)
    category_counts = Counter(category for item in summaries for category in item.get("finding_categories") or [])
    issue_cases = [
        item for item in summaries
        if item.get("solver_status") != "passed" or item.get("hard_fail_reason") or item.get("finding_count")
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "total_cases": len(summaries),
        "solver_status_counts": dict(sorted(solver_counts.items())),
        "engine_case_counts": dict(engine_counts.most_common()),
        "sync_ok_cases": sum(1 for item in summaries if item.get("sync_ok")),
        "issue_cases": len(issue_cases),
        "finding_category_counts": dict(category_counts.most_common()),
        "cases": summaries,
    }


def render_readme(summary: dict[str, Any], summaries: list[dict[str, Any]]) -> str:
    lines = [
        "# Projectile Practice 60 Acceptance Run",
        "",
        f"- Manifest: `{summary['manifest']}`",
        f"- Total cases: `{summary['total_cases']}`",
        f"- Solver status: `{json.dumps(summary['solver_status_counts'], sort_keys=True)}`",
        f"- Sync OK: `{summary['sync_ok_cases']}`",
        f"- Issue cases: `{summary['issue_cases']}`",
        "",
        "## Engine Cases",
        "",
    ]
    lines.extend([f"- `{name}`: {count}" for name, count in summary["engine_case_counts"].items()])
    lines.extend([
        "",
        "## Cases",
        "",
        "| Case | Solver | Engine | Sync | Answer | Findings |",
        "| --- | --- | --- | --- | --- | ---: |",
    ])
    for item in summaries:
        case_link = f"[{item['label']}]({item['case_dir']}/README.md)"
        sync = "ok" if item.get("sync_ok") else (item.get("hard_fail_reason") or "issues")
        answer = str(item.get("answer") or "-").replace("|", "\\|")
        lines.append(
            f"| {case_link} | `{item.get('solver_status')}` | `{item.get('engine_case') or '-'}` | "
            f"`{sync}` | {answer} | {item.get('finding_count', 0)} |"
        )
    return "\n".join(lines) + "\n"


def write_case_readme(case_dir: Path, summary: dict[str, Any], audit: dict[str, Any] | None) -> None:
    lines = [
        f"# {summary['label']}",
        "",
        f"- Solver: `{summary.get('solver_status')}`",
        f"- Engine case: `{summary.get('engine_case') or '-'}`",
        f"- Answer: `{summary.get('answer') or '-'}`",
        f"- Sync: `{'ok' if summary.get('sync_ok') else (summary.get('hard_fail_reason') or 'issues')}`",
        "",
        "## Question",
        "",
        "```text",
        str(summary.get("question_text") or ""),
        "```",
        "",
        "## Findings",
        "",
    ]
    findings = list((audit or {}).get("findings") or [])
    lines.extend([f"- {finding}" for finding in findings] or ["- No automated findings."])
    case_dir.joinpath("README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def finding_category(finding: str) -> str:
    text = finding.lower()
    if "missing" in text:
        return "missing"
    if "generic" in text or "fallback" in text:
        return "generic_fallback"
    if "label" in text:
        return "label"
    if "trajectory" in text:
        return "trajectory"
    if "vector" in text:
        return "vector"
    return "other"


def one_line_summary(summary: dict[str, Any]) -> str:
    return (
        "Practice 60 acceptance: "
        f"{summary['solver_status_counts']} solver / "
        f"{summary['sync_ok_cases']} sync-ok / "
        f"{summary['issue_cases']} issue cases / "
        f"{summary['total_cases']} total"
    )


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


def slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value.lower()).strip("_")[:80] or "case"


if __name__ == "__main__":
    main()
