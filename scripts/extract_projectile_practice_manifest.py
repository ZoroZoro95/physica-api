#!/usr/bin/env python3
"""Extract the 60-question projectile practice PDF into an ordered manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_PDF = Path("questions/projectile_motion_practice_60_questions.pdf")
DEFAULT_OUTPUT = Path("testdata/projectile/practice_60_manifest.json")
QUESTION_RE = re.compile(r"(?m)^\s*(\d{1,3})\.\s+")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    manifest = extract_manifest(args.pdf)
    if len(manifest) != 60:
        raise SystemExit(f"expected 60 questions, extracted {len(manifest)}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(manifest)} questions to {args.output}")


def extract_manifest(pdf_path: Path) -> list[dict[str, Any]]:
    full_text = "\n".join(extract_page_texts(pdf_path))
    matches = list(QUESTION_RE.finditer(full_text))
    entries: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        question_number = int(match.group(1))
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(full_text)
        raw_question = full_text[match.end() : next_start]
        question_text = normalize_question_text(raw_question)
        entries.append(
            {
                "pdf_id": "projectile_practice_60",
                "source_pdf": pdf_path.name,
                "question_number": question_number,
                "question_text": question_text,
                "options": [],
                "expected_option_letter": None,
                "expected_answer": None,
                "requested_quantity": None,
                "suggested_engine_case": None,
                "givens": [],
                "requires_diagram": False,
            }
        )
    entries.sort(key=lambda item: int(item["question_number"]))
    return entries


def extract_page_texts(pdf_path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "pypdf is required. Run this with the project runtime that has requirements installed."
        ) from exc

    reader = PdfReader(str(pdf_path))
    return [page.extract_text() or "" for page in reader.pages]


def normalize_question_text(text: str) -> str:
    replacements = {
        "\u2212": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u00b0": " degrees",
        "\u221a": "sqrt",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r"\bPage\s+\d+\b", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


if __name__ == "__main__":
    if str(Path.cwd()) not in sys.path:
        sys.path.insert(0, str(Path.cwd()))
    main()
