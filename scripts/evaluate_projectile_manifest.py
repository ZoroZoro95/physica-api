#!/usr/bin/env python3
"""Evaluate projectile DPP manifest entries against deterministic engine cases."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.projectile_engine import evaluate_manifest_entry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=Path("questions/manifest/projectile_dpp_manifest.json"),
    )
    parser.add_argument("--show-trace", action="store_true", help="Print solution traces for implemented cases.")
    args = parser.parse_args()

    entries = json.loads(args.manifest.read_text(encoding="utf-8"))
    results = [evaluate_manifest_entry(entry) for entry in entries]
    counts = Counter(result.status for result in results)

    for result in results:
        expected = result.expected_option_letter or "-"
        predicted = result.predicted_option_letter or "-"
        detail = result.reason or result.computed_text or ""
        print(
            f"{result.label} {result.engine_case}: "
            f"{result.status} expected={expected} got={predicted} {detail}".rstrip()
        )
        if args.show_trace and result.trace:
            for step in result.trace:
                print(f"  - {step}")

    print()
    print(
        "Summary: "
        f"{counts['passed']} passed / "
        f"{counts['failed']} failed / "
        f"{counts['unsupported']} unsupported / "
        f"{len(results)} total"
    )


if __name__ == "__main__":
    main()
