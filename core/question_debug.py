from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from .projectile_engine.intent import requested_quantity_case


REPORT_ROOT = Path(__file__).resolve().parents[1] / "questions" / "debug_reports"


def create_image_report(
    *,
    image_bytes: bytes,
    image_mime_type: str,
    image_filename: str,
    hint: str,
) -> str:
    report_id = _new_report_id()
    report_dir = _report_dir(report_id)
    report_dir.mkdir(parents=True, exist_ok=True)

    suffix = _image_suffix(image_mime_type, image_filename)
    (report_dir / f"question{suffix}").write_bytes(image_bytes)
    _write_json(
        report_dir / "input.json",
        {
            "report_id": report_id,
            "created_at": _now(),
            "image_filename": image_filename,
            "image_mime_type": image_mime_type,
            "hint": hint,
        },
    )
    _write_markdown(report_id)
    return report_id


def record_extraction(report_id: str | None, extraction: BaseModel | dict | None = None, error: str = "") -> None:
    if not report_id:
        return
    payload = _model_payload(extraction) if extraction is not None else {}
    if error:
        payload["error"] = error
    _write_json(_report_dir(report_id) / "extraction.json", payload)
    _write_markdown(report_id)


def record_solve(
    *,
    report_id: str | None,
    request: BaseModel | dict,
    response: BaseModel | dict | None = None,
    error: str = "",
) -> None:
    if not report_id:
        return
    payload = {
        "request": _model_payload(request),
        "response": _model_payload(response) if response is not None else None,
        "error": error,
    }
    _write_json(_report_dir(report_id) / "solve.json", payload)
    _write_markdown(report_id)


def report_path(report_id: str | None) -> str:
    return str(_report_dir(report_id)) if report_id else ""


def _write_markdown(report_id: str) -> None:
    report_dir = _report_dir(report_id)
    input_payload = _read_json(report_dir / "input.json")
    extraction = _read_json(report_dir / "extraction.json")
    solve = _read_json(report_dir / "solve.json")

    lines = [
        f"# Question Debug Report {report_id}",
        "",
        "## Input",
        "",
        f"- Created: `{input_payload.get('created_at', '')}`",
        f"- Image: `{input_payload.get('image_filename', '')}`",
        f"- MIME: `{input_payload.get('image_mime_type', '')}`",
        f"- Hint: `{input_payload.get('hint', '')}`",
        "",
    ]

    if extraction:
        lines.extend(
            [
                "## Extraction",
                "",
                f"- Projectile: `{extraction.get('is_projectile_question', '')}`",
                f"- Type: `{extraction.get('question_type', '')}`",
                f"- Confidence: `{extraction.get('confidence', '')}`",
                f"- Engine case: `{extraction.get('suggested_engine_case', '')}`",
                f"- Givens: `{', '.join(extraction.get('givens') or [])}`",
                f"- Warnings: `{'; '.join(extraction.get('warnings') or [])}`",
                "",
                "```text",
                extraction.get("question_text_solver") or extraction.get("cleaned_prompt") or extraction.get("question_text_raw") or "",
                "```",
                "",
            ]
        )
        diagram = extraction.get("diagram") or {}
        entities = diagram.get("entities") or []
        if entities:
            lines.extend(["### Diagram Entities", ""])
            for entity in entities:
                lines.append(
                    f"- `{entity.get('kind', '')}` `{entity.get('label_solver') or entity.get('label') or ''}` "
                    f"`{entity.get('value') or ''} {entity.get('unit') or ''}` - {entity.get('description') or ''}"
                )
            lines.append("")

    if solve:
        response = solve.get("response") or {}
        request = solve.get("request") or {}
        lines.extend(
            [
                "## Solve",
                "",
                f"- Status: `{response.get('status', '')}`",
                f"- Engine case: `{response.get('engine_case') or request.get('suggested_engine_case') or ''}`",
                f"- Answer: `{response.get('answer', '')}`",
                f"- Option: `{response.get('matched_option', '')}`",
                f"- Reason: `{response.get('reason') or solve.get('error') or ''}`",
                "",
            ]
        )

    lines.extend(["## Likely Code Work", ""])
    lines.extend(_diagnose(extraction, solve))
    lines.append("")
    (report_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def _diagnose(extraction: dict, solve: dict) -> list[str]:
    items: list[str] = []
    response = (solve or {}).get("response") or {}
    request = (solve or {}).get("request") or {}
    status = response.get("status")
    reason = response.get("reason") or (solve or {}).get("error") or ""
    engine_case = response.get("engine_case") or extraction.get("suggested_engine_case") or ""
    requested_quantity = request.get("requested_quantity") or extraction.get("requested_quantity")
    requested_case = requested_quantity_case(requested_quantity, request.get("question_text_solver") or "")
    diagram = extraction.get("diagram") or {}

    if extraction.get("error"):
        items.append("- Fix image extraction or provider handling; extraction failed before solver input existed.")
    if extraction and extraction.get("confidence", 1) < 0.75:
        items.append("- Improve OCR/extraction prompt or add normalization; extraction confidence is low.")
    if diagram.get("present") and not (diagram.get("entities") or []):
        items.append("- Improve diagram entity extraction; a diagram was detected but no usable entities were produced.")
    if status == "unsupported":
        items.append(f"- Implement or alias engine case `{engine_case or 'unknown'}` in `core/projectile_engine/cases.py`.")
    if status == "failed" and "missing known" in reason:
        items.append("- Improve `core/projectile_engine/text_parser.py`; the engine case exists but required givens were not inferred.")
    if status == "failed" and "no match" in reason:
        items.append("- Improve option normalization/matching in `core/projectile_engine/cases.py`; computed answer did not match MCQ options.")
    if status == "passed" and requested_case and requested_case != engine_case:
        items.append(
            f"- Wrong pass: requested quantity maps to `{requested_case}`, but solver used `{engine_case}`. "
            "Do not generate animation from this result."
        )
    if status == "passed":
        items.append("- Solver passed. If animation is wrong, inspect `/generate` scene construction, not the deterministic solver.")
    if not items:
        items.append("- Inspect `extraction.json` and `solve.json`; this failure does not match a known diagnosis yet.")
    return items


def _new_report_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid4().hex[:8]}"


def _report_dir(report_id: str | None) -> Path:
    if not report_id:
        return REPORT_ROOT / "unknown"
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", report_id)
    return REPORT_ROOT / safe


def _image_suffix(image_mime_type: str, image_filename: str) -> str:
    suffix = Path(image_filename).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return suffix
    return {
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(image_mime_type, ".jpg")


def _model_payload(value: BaseModel | dict | None) -> dict:
    if value is None:
        return {}
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
