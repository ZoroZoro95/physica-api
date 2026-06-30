#!/usr/bin/env python3
"""Build and audit projectile coverage by world, unknown, and constraints."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.projectile_engine.cases import SOLVERS
from core.projectile_engine.coverage import BASE_COVERAGE_ROWS, CoverageRow, merge_coverage_rows
from core.projectile_engine.mapper import map_projectile_problem


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("questions/manifest/projectile_dpp_manifest.json"),
        help="DPP manifest used only to discover observed problem families.",
    )
    parser.add_argument(
        "--write",
        type=Path,
        default=None,
        help="Write matrix JSON to this path.",
    )
    parser.add_argument("--show-missing", action="store_true")
    args = parser.parse_args()

    rows = list(BASE_COVERAGE_ROWS)
    rows.extend(_rows_from_manifest(args.manifest))
    matrix = merge_coverage_rows(rows)
    _validate_engine_cases(matrix)

    counts = Counter(row.status for row in matrix)
    print("Projectile coverage matrix")
    print(f"Rows: {len(matrix)}")
    print(f"Solved: {counts['solved']} · Partial: {counts['partial']} · Missing: {counts['missing']}")
    print()

    by_world = Counter(row.world for row in matrix)
    for world, count in sorted(by_world.items()):
        statuses = Counter(row.status for row in matrix if row.world == world)
        print(f"{world}: {count} rows ({statuses['solved']} solved, {statuses['partial']} partial, {statuses['missing']} missing)")

    if args.show_missing:
        print()
        print("Missing / partial rows")
        for row in matrix:
            if row.status in {"missing", "partial"}:
                constraints = ",".join(row.constraints) or "-"
                engine = row.engine_case or "-"
                print(f"- {row.status}: {row.world} / {row.unknown} / {constraints} / {engine}")
                if row.notes:
                    print(f"  {row.notes}")

    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(
            json.dumps([row.to_dict() for row in matrix], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print()
        print(f"Wrote {args.write}")


def _rows_from_manifest(path: Path) -> list[CoverageRow]:
    if not path.exists():
        return []
    entries = json.loads(path.read_text(encoding="utf-8"))
    rows: list[CoverageRow] = []
    for entry in entries:
        spec = map_projectile_problem(entry.get("question_text", ""))
        engine_case = entry.get("engine_case") or spec.engine_case
        constraints = tuple(sorted(spec.constraints))
        if spec.world == "unknown" and spec.unknown == "unknown" and not engine_case:
            continue
        rows.append(
            CoverageRow(
                world=spec.world,
                unknown=spec.unknown,
                constraints=constraints,
                engine_case=engine_case,
                status="solved" if engine_case in SOLVERS else "missing",
                source=("dpp", "mapper"),
                needs_diagram=bool(entry.get("requires_diagram")),
                notes=f"{entry.get('pdf_id', 'dpp')} Q{int(entry.get('question_number', 0)):02d}",
            )
        )
    return rows


def _validate_engine_cases(matrix: list[CoverageRow]) -> None:
    unknown = sorted({row.engine_case for row in matrix if row.engine_case and row.engine_case not in SOLVERS})
    if unknown:
        raise SystemExit(f"coverage matrix references unimplemented engine cases: {', '.join(unknown)}")


if __name__ == "__main__":
    main()
