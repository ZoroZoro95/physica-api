#!/usr/bin/env python3
"""Summarize local image-question debug reports into code-action buckets."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.projectile_engine.intent import requested_quantity_case
from core.projectile_engine import solve_ad_hoc_question

REPORT_ROOT = ROOT / "questions" / "debug_reports"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20, help="Maximum reports to inspect, newest first.")
    parser.add_argument("--root", type=Path, default=REPORT_ROOT)
    parser.add_argument("--stored", action="store_true", help="Use stored solve.json responses instead of replaying current solver code.")
    args = parser.parse_args()

    report_dirs = sorted(
        [path for path in args.root.glob("*") if path.is_dir()],
        key=lambda path: path.name,
        reverse=True,
    )[: args.limit]

    if not report_dirs:
        print(f"No debug reports found in {args.root}")
        return

    buckets: Counter[str] = Counter()
    for report_dir in report_dirs:
        extraction = _read_json(report_dir / "extraction.json")
        solve = _read_json(report_dir / "solve.json")
        if solve and not args.stored:
            solve = _replayed_solve(solve)
        diagnosis = _diagnose(extraction, solve)
        buckets[diagnosis] += 1

        response = solve.get("response") or {}
        stored = solve.get("stored_response") or {}
        print(
            f"{report_dir.name}: {diagnosis} "
            f"status={response.get('status', '-')} "
            f"case={response.get('engine_case') or extraction.get('suggested_engine_case') or '-'}"
        )
        if stored and stored.get("status") != response.get("status"):
            print(f"  stored_status: {stored.get('status', '-')} -> current_status: {response.get('status', '-')}")
        reason = response.get("reason") or solve.get("error") or extraction.get("error") or ""
        if reason:
            print(f"  reason: {' '.join(reason.split())[:220]}")
        print(f"  report: {report_dir / 'report.md'}")

    print()
    print("Buckets:")
    for bucket, count in buckets.most_common():
        print(f"- {bucket}: {count}")


def _diagnose(extraction: dict, solve: dict) -> str:
    response = solve.get("response") or {}
    request = solve.get("request") or {}
    status = response.get("status")
    reason = response.get("reason") or solve.get("error") or extraction.get("error") or ""
    engine_case = response.get("engine_case") or extraction.get("suggested_engine_case")
    requested_quantity = request.get("requested_quantity") or extraction.get("requested_quantity")
    requested_case = requested_quantity_case(requested_quantity, request.get("question_text_solver") or "")
    diagram = extraction.get("diagram") or {}

    if extraction.get("error"):
        return "extraction_failure"
    if status == "passed" and requested_case and requested_case != engine_case:
        return "wrong_quantity_pass"
    if extraction and extraction.get("confidence", 1) < 0.75:
        return "low_confidence_extraction"
    if diagram.get("present") and not (diagram.get("entities") or []):
        return "diagram_entity_extraction"
    if status == "unsupported":
        return "missing_engine_case"
    if status == "failed" and "missing known" in reason:
        return "text_parser_missing_givens"
    if status == "failed" and "no match" in reason:
        return "option_matching"
    if status == "passed":
        return "passed_solver"
    return "unknown"


def _replayed_solve(solve: dict) -> dict:
    request = solve.get("request") or {}
    if not request:
        return solve
    result = solve_ad_hoc_question(
        question_text=request.get("question_text_solver") or "",
        engine_case=request.get("suggested_engine_case"),
        options=request.get("options") or [],
        givens=request.get("givens") or [],
        requested_quantity=request.get("requested_quantity"),
    )
    return {
        **solve,
        "stored_response": solve.get("response") or {},
        "response": {
            "status": result.status,
            "engine_case": result.engine_case,
            "answer": result.computed_text,
            "matched_option": result.predicted_option_letter,
            "computed_value": result.computed_value,
            "trace": result.trace,
            "reason": result.reason,
        },
        "error": "",
    }


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
