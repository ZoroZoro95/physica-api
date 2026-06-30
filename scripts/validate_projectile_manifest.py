#!/usr/bin/env python3
"""Validate the projectile DPP regression manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "pdf_id",
    "source_pdf",
    "question_number",
    "page_start",
    "question_type",
    "question_text",
    "options",
    "expected_option_letter",
    "expected_answer",
    "expected_units",
    "requires_diagram",
    "diagram_pages",
    "projectile_subtype",
    "requested_quantity",
    "knowns",
    "unknowns",
    "constraints",
    "needs_symbolic_solver",
    "needs_diagram_geometry",
    "engine_case",
    "current_engine_status",
    "solver_status",
    "notes",
}

ALLOWED_TYPES = {"mcq", "subjective", "diagram_mcq", "diagram_subjective"}
ALLOWED_STATUSES = {"unclassified", "unsupported", "failed", "passed"}
ALLOWED_ENGINE_STATUSES = {"unclassified", "partial", "unsupported", "supported"}
EXPECTED_COUNTS = {"projectilenorm": 13, "projectileinc": 14}


def fail(message: str) -> None:
    raise SystemExit(f"manifest validation failed: {message}")


def validate_entry(entry: dict[str, Any], index: int) -> None:
    missing = REQUIRED_FIELDS - set(entry)
    if missing:
        fail(f"entry {index} missing fields: {sorted(missing)}")

    pdf_id = entry["pdf_id"]
    qn = entry["question_number"]
    label = f"{pdf_id} Q{qn}"

    if not isinstance(pdf_id, str) or not pdf_id:
        fail(f"entry {index} has invalid pdf_id")
    if not isinstance(qn, int) or qn < 1:
        fail(f"{label} has invalid question_number")
    if not isinstance(entry["page_start"], int) or entry["page_start"] < 1:
        fail(f"{label} has invalid page_start")
    if entry["question_type"] not in ALLOWED_TYPES:
        fail(f"{label} has invalid question_type {entry['question_type']!r}")
    if entry["solver_status"] not in ALLOWED_STATUSES:
        fail(f"{label} has invalid solver_status {entry['solver_status']!r}")
    if entry["current_engine_status"] not in ALLOWED_ENGINE_STATUSES:
        fail(f"{label} has invalid current_engine_status {entry['current_engine_status']!r}")
    if not isinstance(entry["question_text"], str) or len(entry["question_text"].strip()) < 20:
        fail(f"{label} has suspiciously short question_text")
    if not isinstance(entry["options"], list):
        fail(f"{label} options must be a list")

    is_mcq = entry["question_type"] in {"mcq", "diagram_mcq"}
    if is_mcq and len(entry["options"]) != 4:
        fail(f"{label} is MCQ but has {len(entry['options'])} options")
    if is_mcq and entry["expected_option_letter"] not in {"a", "b", "c", "d"}:
        fail(f"{label} is MCQ but has invalid expected_option_letter")
    if is_mcq and not entry["expected_answer"]:
        fail(f"{label} is MCQ but has no expected_answer")
    if not is_mcq and entry["options"]:
        fail(f"{label} is subjective but has options")

    requires_diagram = entry["requires_diagram"]
    if not isinstance(requires_diagram, bool):
        fail(f"{label} requires_diagram must be boolean")
    if requires_diagram and not entry["diagram_pages"]:
        fail(f"{label} requires diagram but has no diagram_pages")
    if not entry["engine_case"]:
        fail(f"{label} has no engine_case")
    if not entry["projectile_subtype"]:
        fail(f"{label} has no projectile_subtype")
    if not entry["requested_quantity"]:
        fail(f"{label} has no requested_quantity")
    if not isinstance(entry["constraints"], list) or not entry["constraints"]:
        fail(f"{label} has no constraints")
    if not isinstance(entry["knowns"], list):
        fail(f"{label} knowns must be a list")
    if not isinstance(entry["unknowns"], list):
        fail(f"{label} unknowns must be a list")
    if not isinstance(entry["needs_symbolic_solver"], bool):
        fail(f"{label} needs_symbolic_solver must be boolean")
    if not isinstance(entry["needs_diagram_geometry"], bool):
        fail(f"{label} needs_diagram_geometry must be boolean")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=Path("questions/manifest/projectile_dpp_manifest.json"),
    )
    args = parser.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        fail("top-level manifest must be a list")

    seen: set[tuple[str, int]] = set()
    counts: dict[str, int] = {}
    for index, entry in enumerate(data):
        validate_entry(entry, index)
        key = (entry["pdf_id"], entry["question_number"])
        if key in seen:
            fail(f"duplicate question key {key}")
        seen.add(key)
        counts[entry["pdf_id"]] = counts.get(entry["pdf_id"], 0) + 1

    for pdf_id, expected_count in EXPECTED_COUNTS.items():
        actual = counts.get(pdf_id, 0)
        if actual != expected_count:
            fail(f"{pdf_id} expected {expected_count} questions, found {actual}")

    print(f"Manifest OK: {len(data)} questions")
    for pdf_id in sorted(counts):
        print(f"{pdf_id}: {counts[pdf_id]}")


if __name__ == "__main__":
    main()
