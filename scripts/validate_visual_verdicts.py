#!/usr/bin/env python3
"""Validate model/agent visual-verifier verdicts for the projectile benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


BLOCKING_VERDICTS = {
    "wrong_visual",
    "needs_template",
    "needs_label_layout",
    "missing_svg",
    "unreadable",
    "fail",
    "blocker",
}

SCORE_KEYS = (
    "beat_alignment",
    "cleanliness",
    "angle_vector_correctness",
    "formula_diagram_alignment",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verdicts",
        type=Path,
        default=Path("questions/visual_benchmarks/smoke_visual_benchmark/review_queue/visual_verdicts.json"),
    )
    parser.add_argument("--expected-cases", type=int, default=30)
    parser.add_argument("--expected-beats", type=int, default=128)
    parser.add_argument("--min-score", type=float, default=4.0)
    args = parser.parse_args()

    if not args.verdicts.exists():
      print(f"FAIL missing visual verifier report: {args.verdicts}")
      return 1

    data = json.loads(args.verdicts.read_text(encoding="utf-8"))
    failures: list[str] = []

    queue_data = read_review_queue(args.verdicts)
    total_cases = int(
        data.get("total_cases")
        or data.get("summary", {}).get("total_cases")
        or data.get("summary", {}).get("total")
        or len(data.get("cases") or [])
    )
    total_beats = int(
        data.get("total_beats")
        or data.get("summary", {}).get("total_beats")
        or (queue_data.get("total_beats") if queue_data else 0)
    )
    if total_cases != args.expected_cases:
        failures.append(f"expected {args.expected_cases} cases, found {total_cases}")
    if total_beats != args.expected_beats:
        failures.append(f"expected {args.expected_beats} beats, found {total_beats}")

    blockers = data.get("deployment_blockers") or data.get("blockers") or []
    if blockers:
        failures.append(f"{len(blockers)} deployment blocker(s) present")

    summary = data.get("summary") or {}
    if data.get("deployment_ready") is False:
        failures.append("deployment_ready=false")
    for verdict in BLOCKING_VERDICTS:
        count = int(summary.get(verdict) or 0)
        if count:
            failures.append(f"summary verdict {verdict}={count}")
    min_score = summary.get("min_score")
    if isinstance(min_score, (int, float)) and float(min_score) < args.min_score:
        failures.append(f"summary min_score {float(min_score):.2f} below {args.min_score:.2f}")

    score_values: list[float] = []
    for case in data.get("cases") or []:
        case_id = str(case.get("case_id") or case.get("id") or "unknown")
        verdict = str(case.get("case_verdict") or case.get("verdict") or "pass").lower()
        if verdict in BLOCKING_VERDICTS:
            failures.append(f"{case_id} blocking verdict: {verdict}")
        if case.get("blocker") is True:
            failures.append(f"{case_id} blocker=true")
        issues = case.get("issues") or []
        blocking_issues = [issue for issue in issues if str(issue.get("severity") if isinstance(issue, dict) else "").lower() in {"blocker", "high"}]
        if blocking_issues:
            failures.append(f"{case_id} has {len(blocking_issues)} high/blocker issue(s)")

        scores = extract_scores(case)
        for key, value in scores.items():
            score_values.append(value)
            if value < args.min_score:
                failures.append(f"{case_id} score {key}={value:.2f} below {args.min_score:.2f}")

        for beat in case.get("beats") or []:
            beat_verdict = str(beat.get("verdict") or "pass").lower()
            if beat_verdict in BLOCKING_VERDICTS:
                failures.append(f"{case_id}/{beat.get('step_id')}: blocking verdict {beat_verdict}")

    average_score = sum(score_values) / len(score_values) if score_values else None
    if average_score is None:
        failures.append("visual verifier report has no scored rubric fields")
    elif average_score < args.min_score:
        failures.append(f"average visual verifier score {average_score:.2f} below {args.min_score:.2f}")

    if failures:
        print("FAIL visual verifier verdicts")
        for failure in failures:
            print(f"- {failure}")
        return 1

    score_text = f"{average_score:.2f}" if average_score is not None else "n/a"
    print(f"PASS visual verifier verdicts: cases={total_cases} beats={total_beats} avg_score={score_text}")
    return 0


def extract_scores(case: dict[str, Any]) -> dict[str, float]:
    raw_scores = case.get("scores")
    if not isinstance(raw_scores, dict):
        raw_scores = case.get("score_0_to_5") if isinstance(case.get("score_0_to_5"), dict) else {}
    scores: dict[str, float] = {}
    for key in SCORE_KEYS:
        value = raw_scores.get(key)
        if isinstance(value, (int, float)):
            scores[key] = float(value)
    compact_score = case.get("score")
    if isinstance(compact_score, (int, float)) and not scores:
        scores["overall"] = float(compact_score)
    return scores


def read_review_queue(verdicts_path: Path) -> dict[str, Any] | None:
    queue_path = verdicts_path.parent / "review_queue.json"
    if not queue_path.exists():
        return None
    try:
        return json.loads(queue_path.read_text(encoding="utf-8"))
    except Exception:
        return None


if __name__ == "__main__":
    sys.exit(main())
