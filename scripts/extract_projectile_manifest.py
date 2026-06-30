#!/usr/bin/env python3
"""Extract top-level projectile DPP questions into a regression manifest."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader


QUESTION_RE = re.compile(r"\bQ\s*(\d+)\.")
OPTION_RE = re.compile(r"\(([a-d])\)\s*(.*?)(?=\s*\([a-d]\)\s*|$)", re.IGNORECASE)
NOISE_MARKERS = [
    "Answer Key",
    "PHYSICS LIVE",
    "Video Solution on Website",
    "Video Solution on YouTube",
    "Written Solution on Website",
    "Physicsaholics Use code",
    "https://",
]

OPTION_TEXT_FIXES = {
    ("projectilenorm", 4, "d"): "10/root(3) m/s",
}


@dataclass(frozen=True)
class PdfSpec:
    pdf_id: str
    path: Path


def normalize_text(text: str) -> str:
    replacements = {
        "\uf020": " ",
        "\uf061": "alpha",
        "\uf062": "beta",
        "\uf071": "theta",
        "\uf0b0": "deg",
        "\u00ba": "deg",
        "\u00b0": "deg",
        "\u221a": "sqrt",
        "\u2212": "-",
        "\u2264": "<=",
        "\u2265": ">=",
        "\u2032": "'",
        "\u2013": "-",
        "\u2014": "-",
        "\u00d7": "x",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return " ".join(text.split())


def strip_noise(text: str) -> str:
    for marker in NOISE_MARKERS:
        marker_index = text.find(marker)
        if marker_index >= 0:
            text = text[:marker_index]
    return text.strip()


def extract_page_texts(path: Path) -> list[str]:
    reader = PdfReader(str(path))
    return [page.extract_text() or "" for page in reader.pages]


def extract_answer_key(full_text: str) -> dict[int, str]:
    answer_key_start = full_text.find("Answer Key")
    if answer_key_start < 0:
        return {}
    answer_key_text = full_text[answer_key_start : answer_key_start + 1000]
    return {
        int(question_number): option_letter.lower()
        for question_number, option_letter in re.findall(
            r"Q\.\s*(\d+)\s*([a-d])", answer_key_text, re.IGNORECASE
        )
    }


def build_page_offsets(page_texts: list[str]) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    for text in page_texts:
        offsets.append(cursor)
        cursor += len(text) + 1
    return offsets


def page_for_offset(offsets: list[int], offset: int) -> int:
    page = 1
    for i, page_offset in enumerate(offsets, start=1):
        if page_offset <= offset:
            page = i
        else:
            break
    return page


def split_options(pdf_id: str, question_number: int, question_text: str) -> tuple[str, list[str]]:
    matches = list(OPTION_RE.finditer(question_text))
    if not matches:
        return question_text.strip(), []

    matches = matches[:4]
    first_option_start = matches[0].start()
    stem = strip_noise(question_text[:first_option_start]).strip()
    options = []
    for match in matches:
        option_letter = match.group(1).lower()
        option_text = strip_noise(match.group(2).strip())
        option_text = OPTION_TEXT_FIXES.get((pdf_id, question_number, option_letter), option_text)
        options.append(normalize_text(option_text))
    return stem, options


def detect_requires_diagram(text: str) -> bool:
    lowered = text.lower()
    diagram_markers = [
        "shown in fig",
        "shown in the fig",
        "as shown",
        "figure",
        "diagram",
        "incline of indication",
    ]
    return any(marker in lowered for marker in diagram_markers)


def classify_question_type(options: list[str], requires_diagram: bool) -> str:
    if options and requires_diagram:
        return "diagram_mcq"
    if options:
        return "mcq"
    if requires_diagram:
        return "diagram_subjective"
    return "subjective"


def extract_questions(spec: PdfSpec) -> list[dict[str, Any]]:
    page_texts = extract_page_texts(spec.path)
    offsets = build_page_offsets(page_texts)
    full_text = "\n".join(page_texts)
    answer_key = extract_answer_key(" ".join(full_text.split()))
    matches = list(QUESTION_RE.finditer(full_text))
    entries: list[dict[str, Any]] = []

    for index, match in enumerate(matches):
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(full_text)
        raw_chunk = full_text[match.start() : next_start]
        normalized_chunk = normalize_text(raw_chunk)
        question_number = int(match.group(1))
        stem, options = split_options(spec.pdf_id, question_number, normalized_chunk)
        requires_diagram = detect_requires_diagram(stem)
        page_start = page_for_offset(offsets, match.start())
        expected_option_letter = answer_key.get(question_number)
        expected_answer = None
        if expected_option_letter and options:
            option_index = ord(expected_option_letter) - ord("a")
            if 0 <= option_index < len(options):
                expected_answer = options[option_index]

        entries.append(
            {
                "pdf_id": spec.pdf_id,
                "source_pdf": str(spec.path),
                "question_number": question_number,
                "page_start": page_start,
                "question_type": classify_question_type(options, requires_diagram),
                "question_text": stem,
                "options": options,
                "expected_option_letter": expected_option_letter,
                "expected_answer": expected_answer,
                "expected_units": None,
                "requires_diagram": requires_diagram,
                "diagram_pages": [page_start] if requires_diagram else [],
                "projectile_subtype": None,
                "requested_quantity": None,
                "solver_status": "unclassified",
                "notes": "",
            }
        )

    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("questions/manifest/projectile_dpp_manifest.json"),
        help="Manifest JSON output path.",
    )
    args = parser.parse_args()

    specs = [
        PdfSpec("projectilenorm", Path("questions/projectilenorm.pdf")),
        PdfSpec("projectileinc", Path("questions/projectileinc.pdf")),
    ]

    manifest: list[dict[str, Any]] = []
    for spec in specs:
        if not spec.path.exists():
            raise FileNotFoundError(spec.path)
        manifest.extend(extract_questions(spec))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    counts: dict[str, int] = {}
    for entry in manifest:
        counts[entry["pdf_id"]] = counts.get(entry["pdf_id"], 0) + 1
    print(f"Wrote {len(manifest)} questions to {args.output}")
    for pdf_id, count in counts.items():
        print(f"{pdf_id}: {count}")


if __name__ == "__main__":
    main()
