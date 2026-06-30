#!/usr/bin/env python3
"""Build review sheets and a verifier queue for rendered projectile beat visuals."""

from __future__ import annotations

import argparse
import json
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("visual_index", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--thumb-width", type=int, default=360)
    args = parser.parse_args()

    index_path = args.visual_index.resolve()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(index_path.read_text(encoding="utf-8"))
    visuals = [item for item in data.get("visuals") or [] if item.get("screenshotPath")]
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in visuals:
        by_case[str(item.get("caseId") or "case")].append(item)

    queue_cases = []
    for case_id in sorted(by_case):
        items = by_case[case_id]
        sheet_path = out_dir / f"{case_id}.png"
        make_contact_sheet(items, sheet_path, thumb_width=args.thumb_width)
        queue_cases.append({
            "case_id": case_id,
            "engine_case": items[0].get("engineCase") or "",
            "answer": items[0].get("answer") or "",
            "contact_sheet": str(sheet_path),
            "beats": [
                {
                    "step_id": item.get("stepId") or "",
                    "title": item.get("title") or "",
                    "visual_action": item.get("visualAction") or "",
                    "template_kind": item.get("templateKind") or "",
                    "screenshot": item.get("screenshotPath") or "",
                    "svg": item.get("svgPath") or "",
                    "learner_message": item.get("learnerMessage") or "",
                    "beat_visual": item.get("beatVisual") or "",
                    "screenshot_hash": item.get("screenshotHash") or "",
                }
                for item in items
            ],
        })

    review_queue = {
        "visual_index": str(index_path),
        "total_cases": len(queue_cases),
        "total_beats": len(visuals),
        "rubric": {
            "quality": [
                "labels do not overlap labels, arrows, curves, points, or markers",
                "labels are close enough to read but offset enough to breathe",
                "arrows have useful length and orientation for the concept",
                "diagram is textbook-clean, with no red helper lines or decorative clutter",
                "layout remains legible at the small teaching-window size",
            ],
            "relevance": [
                "the beat visual changes when the walkthrough concept changes",
                "the shown template matches the question world and current beat",
                "given, component, range, time, height, incline, collision, or final-answer beats emphasize different geometry",
                "full-lifecycle animation is separate from beat-local teaching boards",
            ],
            "verdicts": ["pass", "needs_template", "needs_label_layout", "wrong_visual", "missing_svg", "unreadable"],
        },
        "cases": queue_cases,
    }
    (out_dir / "review_queue.json").write_text(json.dumps(review_queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "README.md").write_text(render_readme(review_queue), encoding="utf-8")
    print(f"review_queue={out_dir / 'review_queue.json'}")
    print(f"cases={len(queue_cases)} beats={len(visuals)}")
    return 0


def make_contact_sheet(items: list[dict[str, Any]], out_path: Path, *, thumb_width: int) -> None:
    font = ImageFont.load_default()
    title_font = ImageFont.load_default()
    cards = []
    card_padding = 12
    text_height = 90
    card_width = thumb_width + card_padding * 2
    for index, item in enumerate(items, start=1):
        image_path = Path(str(item.get("screenshotPath") or ""))
        try:
            image = Image.open(image_path).convert("RGB")
        except Exception:
            image = Image.new("RGB", (thumb_width, 200), "white")
        scale = thumb_width / max(1, image.width)
        thumb_height = max(1, int(image.height * scale))
        image = image.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        card = Image.new("RGB", (card_width, thumb_height + text_height + card_padding * 2), "#f8fafc")
        draw = ImageDraw.Draw(card)
        draw.rectangle((0, 0, card.width - 1, card.height - 1), outline="#cbd5e1")
        header = f"{index}. {item.get('stepId') or ''} | {item.get('visualAction') or ''}"
        template = f"template: {item.get('templateKind') or '-'}"
        title = str(item.get("title") or "")
        draw.text((card_padding, 8), header[:78], fill="#0f172a", font=title_font)
        draw.text((card_padding, 24), template[:78], fill="#334155", font=font)
        for line_index, line in enumerate(wrap(title, 68)[:2]):
            draw.text((card_padding, 40 + line_index * 14), line, fill="#334155", font=font)
        card.paste(image, (card_padding, text_height + card_padding))
        cards.append(card)

    columns = 2 if len(cards) > 1 else 1
    gap = 14
    rows = (len(cards) + columns - 1) // columns
    row_heights = []
    for row in range(rows):
        row_cards = cards[row * columns:(row + 1) * columns]
        row_heights.append(max(card.height for card in row_cards))
    width = columns * card_width + (columns - 1) * gap
    height = sum(row_heights) + max(0, rows - 1) * gap
    sheet = Image.new("RGB", (width, height), "white")
    y = 0
    for row in range(rows):
        x = 0
        for card in cards[row * columns:(row + 1) * columns]:
            sheet.paste(card, (x, y))
            x += card_width + gap
        y += row_heights[row] + gap
    sheet.save(out_path)


def wrap(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width) or [""]


def render_readme(queue: dict[str, Any]) -> str:
    lines = [
        "# Projectile Visual Review Queue",
        "",
        f"- Cases: `{queue['total_cases']}`",
        f"- Beats: `{queue['total_beats']}`",
        "",
        "Use `review_queue.json` as the verifier input. Each case has a contact sheet plus the source SVG/PNG paths for every beat.",
        "",
        "## Cases",
        "",
    ]
    for item in queue["cases"]:
        lines.append(f"- `{item['case_id']}`: `{item['engine_case']}` -> `{item['contact_sheet']}`")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
