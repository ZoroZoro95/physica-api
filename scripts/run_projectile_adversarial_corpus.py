#!/usr/bin/env python3
"""Run adversarial projectile text cases through the production ad-hoc solver path."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.projectile_engine import build_solution_walkthrough, solve_ad_hoc_question
from core.projectile_engine.animation_scene import build_animation_scene_spec
from core.projectile_engine.cases import SOLVERS, canonical_engine_case


DEFAULT_CORPUS = ROOT / "testdata" / "projectile" / "adversarial_text_cases.json"
DEFAULT_REPORT = ROOT / "questions" / "adversarial_projectile_runs" / "latest" / "summary.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", nargs="?", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--write-report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--no-artifacts", action="store_true", help="Do not write per-case solve/walkthrough/scene artifacts.")
    parser.add_argument("--strict-xfail", action="store_true", help="Fail when an xfail case unexpectedly passes.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    cases = corpus.get("cases") or []
    report_dir = args.write_report.parent
    artifacts_dir = report_dir / "artifacts"
    report_dir.mkdir(parents=True, exist_ok=True)
    if not args.no_artifacts:
        artifacts_dir.mkdir(parents=True, exist_ok=True)

    items = []
    for raw_case in cases:
        item = run_case(raw_case)
        items.append(item)
        if not args.no_artifacts:
            write_case_artifact(artifacts_dir, item)

    summary = summarize(args.corpus, items)
    args.write_report.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print_summary(summary, args.write_report)

    required_failures = [
        item
        for item in items
        if item["expectation"] == "pass" and item["verdict"] != "pass"
    ]
    unsafe_passes = [item for item in items if item["verdict"] == "unsafe_pass"]
    unexpected_passes = [
        item
        for item in items
        if item["expectation"] == "xfail" and item["verdict"] == "xpass"
    ]
    if required_failures:
        return 1
    if unsafe_passes:
        return 1
    if args.strict_xfail and unexpected_passes:
        return 1
    return 0


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    result = solve_ad_hoc_question(
        question_text=str(case["question"]),
        engine_case=case.get("suggested_engine_case"),
        options=list(case.get("options") or []),
        givens=list(case.get("givens") or []),
        requested_quantity=case.get("requested_quantity"),
        diagram=case.get("diagram"),
        require_diagram_validation=bool(case.get("require_diagram_validation", False)),
    )
    result_data = dataclass_to_jsonable(result)
    checks: list[dict[str, Any]] = []
    visual_summary: dict[str, Any] = {}

    expected_engine = canonical_engine_case(case.get("expected_engine_case"))
    expected_status = case.get("expected_status", "passed")
    expectation = case.get("expectation", "pass")

    if result.status != expected_status:
        checks.append(failure("status_mismatch", f"status={result.status}, expected={expected_status}"))

    if expected_engine and result.engine_case != expected_engine:
        reason = f"engine_case={result.engine_case}, expected={expected_engine}"
        if expected_engine in SOLVERS and result.engine_case in {"unknown", None}:
            checks.append(failure("mapping_missing", reason))
        elif expected_engine in SOLVERS:
            checks.append(failure("mapping_wrong_engine", reason))
        else:
            checks.append(failure("missing_solver_family", reason))

    if case.get("expected_value") is not None:
        expected_value = float(case["expected_value"])
        tolerance = float(case.get("tolerance", 1e-6))
        if result.computed_value is None:
            checks.append(failure("answer_missing", f"expected numeric value {expected_value:g}"))
        elif not math.isfinite(result.computed_value) or abs(result.computed_value - expected_value) > tolerance:
            checks.append(
                failure(
                    "answer_mismatch",
                    f"value={result.computed_value:g}, expected={expected_value:g}, tolerance={tolerance:g}",
                )
            )

    if case.get("expected_option") is not None and result.predicted_option_letter != case.get("expected_option"):
        checks.append(
            failure("option_mismatch", f"option={result.predicted_option_letter}, expected={case.get('expected_option')}")
        )

    for needle in case.get("expected_text_contains") or []:
        if str(needle) not in (result.computed_text or ""):
            checks.append(failure("answer_text_missing", f"computed_text missing {needle!r}"))

    if result.status == "failed" and result.reason:
        checks.append(failure("solver_exception_or_failure", result.reason))

    if result.status == "passed":
        walkthrough = build_solution_walkthrough(result)
        scene = build_animation_scene_spec(
            result=result,
            question_text=str(case["question"]),
            givens=list(case.get("givens") or []),
        )
        visual_summary, visual_failures = audit_visual_contract(case, walkthrough, scene)
        checks.extend(visual_failures)
    else:
        walkthrough = None
        scene = None
        if expectation == "pass" and expected_engine in SOLVERS:
            checks.append(
                failure(
                    "supported_formula_not_reached",
                    "The expected engine case is implemented, but the ad-hoc solver did not produce a passed result.",
                )
            )

    verdict = classify_verdict(expectation, checks, result, expected_engine)
    failure_types = [check["type"] for check in checks if check["status"] == "fail"]
    return {
        "id": case["id"],
        "family": case.get("family"),
        "intent": case.get("intent"),
        "expectation": expectation,
        "verdict": verdict,
        "failure_types": failure_types,
        "checks": checks,
        "question": case["question"],
        "expected": {
            "status": expected_status,
            "engine_case": expected_engine,
            "value": case.get("expected_value"),
            "option": case.get("expected_option"),
            "xfail_reason": case.get("xfail_reason"),
        },
        "actual": {
            "status": result.status,
            "engine_case": result.engine_case,
            "computed_value": result.computed_value,
            "computed_text": result.computed_text,
            "predicted_option_letter": result.predicted_option_letter,
            "reason": result.reason,
            "template_id": result.template_id,
            "template_confidence": result.template_confidence,
            "template_warnings": result.template_warnings,
        },
        "visual_summary": visual_summary,
        "artifacts": {
            "result": result_data,
            "walkthrough": walkthrough,
            "scene": scene,
        },
    }


def audit_visual_contract(case: dict[str, Any], walkthrough: dict[str, Any], scene: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    walkthrough_steps = walkthrough.get("steps") or []
    scene_steps = scene.get("steps") or []
    storyboard = scene.get("storyboard") or []
    contract_errors = scene.get("contract_errors") or []
    signatures = visual_signatures(storyboard)
    unique_signature_count = len(set(signatures))

    min_walkthrough_steps = int(case.get("min_walkthrough_steps", 0) or 0)
    min_scene_steps = int(case.get("min_scene_steps", 0) or 0)
    min_unique_visual_signatures = int(case.get("min_unique_visual_signatures", 0) or 0)

    if min_walkthrough_steps and len(walkthrough_steps) < min_walkthrough_steps:
        failures.append(failure("walkthrough_too_short", f"steps={len(walkthrough_steps)}, expected>={min_walkthrough_steps}"))
    if min_scene_steps and len(storyboard) < min_scene_steps:
        failures.append(failure("storyboard_too_short", f"beats={len(storyboard)}, expected>={min_scene_steps}"))
    if min_unique_visual_signatures and unique_signature_count < min_unique_visual_signatures:
        failures.append(
            failure(
                "visuals_not_changing_enough",
                f"unique_visual_signatures={unique_signature_count}, expected>={min_unique_visual_signatures}",
            )
        )
    if contract_errors:
        failures.append(failure("scene_contract_errors", "; ".join(str(err) for err in contract_errors[:5])))

    for beat in storyboard:
        step_id = beat.get("step_id") or "unknown"
        visual_focus = beat.get("visual_focus") or []
        visual_plan = beat.get("visual_plan") or {}
        if not visual_focus and not (visual_plan.get("show_ids") or visual_plan.get("highlight_ids")):
            failures.append(failure("beat_missing_visual_focus", f"{step_id} has no visual focus/show/highlight ids"))

    summary = {
        "walkthrough_steps": len(walkthrough_steps),
        "scene_steps": len(scene_steps),
        "storyboard_beats": len(storyboard),
        "unique_visual_signatures": unique_signature_count,
        "contract_errors": contract_errors,
    }
    return summary, failures


def visual_signatures(storyboard: list[dict[str, Any]]) -> list[str]:
    signatures: list[str] = []
    for beat in storyboard:
        plan = beat.get("visual_plan") or {}
        signature = {
            "action": beat.get("visual_action") or plan.get("visual_action"),
            "camera": beat.get("camera") or plan.get("camera"),
            "show": sorted(str(item) for item in (plan.get("show_ids") or beat.get("visual_focus") or [])),
            "highlight": sorted(str(item) for item in (plan.get("highlight_ids") or beat.get("highlight_ids") or [])),
            "vectors": sorted(str(item) for item in (beat.get("visible_vectors") or plan.get("visible_vectors") or [])),
            "overlays": sorted(str(item) for item in (beat.get("overlays") or plan.get("overlays") or [])),
        }
        signatures.append(json.dumps(signature, sort_keys=True))
    return signatures


def classify_verdict(expectation: str, checks: list[dict[str, Any]], result: Any, expected_engine: str | None) -> str:
    has_failures = any(check["status"] == "fail" for check in checks)
    if expectation == "xfail":
        if result.status == "passed" and expected_engine in SOLVERS and result.engine_case == expected_engine:
            return "xpass"
        if result.status == "passed":
            return "unsafe_pass"
        return "expected_fail"
    return "fail" if has_failures else "pass"


def failure(kind: str, detail: str) -> dict[str, str]:
    return {"status": "fail", "type": kind, "detail": detail}


def summarize(corpus_path: Path, items: list[dict[str, Any]]) -> dict[str, Any]:
    verdicts = Counter(item["verdict"] for item in items)
    failure_types = Counter(
        failure_type
        for item in items
        if item["verdict"] in {"fail", "unsafe_pass"}
        for failure_type in item["failure_types"]
    )
    by_intent = Counter(f"{item.get('intent') or 'unknown'}:{item['verdict']}" for item in items)
    compact_items = []
    for item in items:
        compact = {key: value for key, value in item.items() if key != "artifacts"}
        compact_items.append(compact)
    return {
        "corpus": str(corpus_path),
        "total": len(items),
        "verdicts": dict(sorted(verdicts.items())),
        "failure_types": dict(sorted(failure_types.items())),
        "by_intent": dict(sorted(by_intent.items())),
        "items": compact_items,
    }


def print_summary(summary: dict[str, Any], report_path: Path) -> None:
    print("Projectile adversarial corpus")
    print(f"Cases: {summary['total']}")
    print("Verdicts: " + ", ".join(f"{key}={value}" for key, value in summary["verdicts"].items()))
    if summary["failure_types"]:
        print("Failure types: " + ", ".join(f"{key}={value}" for key, value in summary["failure_types"].items()))
    print(f"Report: {report_path}")
    print()
    for item in summary["items"]:
        marker = {
            "pass": "PASS",
            "fail": "FAIL",
            "expected_fail": "XFAIL",
            "xpass": "XPASS",
            "unsafe_pass": "UNSAFE",
        }.get(item["verdict"], item["verdict"].upper())
        actual = item["actual"]
        expected = item["expected"]
        print(
            f"{marker} {item['id']}: "
            f"{actual['status']}/{actual['engine_case']} "
            f"expected {expected['status']}/{expected['engine_case']}"
        )
        if item["failure_types"]:
            print("  " + ", ".join(item["failure_types"]))


def write_case_artifact(artifacts_dir: Path, item: dict[str, Any]) -> None:
    path = artifacts_dir / f"{safe_filename(str(item['id']))}.json"
    path.write_text(json.dumps(item, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def dataclass_to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return dataclass_to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): dataclass_to_jsonable(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [dataclass_to_jsonable(item) for item in value]
    return value


def safe_filename(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value.strip())
    return safe[:120] or "case"


if __name__ == "__main__":
    sys.exit(main())
