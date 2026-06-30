#!/usr/bin/env python3
"""Audit projectile manifest coverage by reusable problem templates."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.projectile_engine import evaluate_manifest_entry
from core.projectile_engine.cases import SOLVERS
from core.projectile_engine.templates import all_engine_cases_covered


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=Path("questions/manifest/projectile_dpp_manifest.json"),
    )
    parser.add_argument("--show-warnings", action="store_true")
    args = parser.parse_args()

    entries = json.loads(args.manifest.read_text(encoding="utf-8"))
    results = [evaluate_manifest_entry(entry) for entry in entries]
    counts = Counter(result.template_id or "unmatched" for result in results)
    by_template: dict[str, list[str]] = defaultdict(list)
    warnings_by_label: dict[str, list[str]] = {}

    for result in results:
        by_template[result.template_id or "unmatched"].append(f"{result.label}:{result.engine_case}")
        if result.template_warnings:
            warnings_by_label[result.label] = result.template_warnings

    covered, missing = all_engine_cases_covered(set(SOLVERS))
    print("Projectile template audit")
    print(f"Engine cases covered by templates: {'yes' if covered else 'no'}")
    if missing:
        print("Missing engine cases: " + ", ".join(sorted(missing)))
    print()

    for template_id, count in sorted(counts.items()):
        print(f"{template_id}: {count}")
        for label in by_template[template_id]:
            print(f"  - {label}")
    print()

    if args.show_warnings:
        print("Template warnings")
        if not warnings_by_label:
            print("  none")
        for label, warnings in warnings_by_label.items():
            print(f"  {label}")
            for warning in warnings:
                print(f"    - {warning}")
    else:
        print(f"Entries with template warnings: {len(warnings_by_label)}")


if __name__ == "__main__":
    main()
