#!/usr/bin/env python3
"""Probe VLM diagram extraction on a single image.

This script is intentionally separate from the app solve flow. It lets us
iterate on the image prompt and inspect exactly what the VLM returns.

Usage:
  python scripts/probe_vlm_diagram_extraction.py /path/to/question.png --mode graph
  python scripts/probe_vlm_diagram_extraction.py /path/to/question.png --mode current --out /tmp/vlm.json
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.prompt_engine import IMAGE_QUESTION_EXTRACTION_PROMPT


GEOMETRY_GRAPH_PROMPT = """
You extract physics question text and diagram geometry from an uploaded image.
Do NOT solve the problem.
Do NOT assume labels like O, A, B, P, Q are fixed. Labels are only visual text.
You must distinguish three things:
1. What is explicitly written in the text.
2. What is explicitly labeled in the diagram.
3. What is only visually suggested by the drawing.

Never convert a symbolic angle such as theta, α, β, φ, or "angle theta" into a numeric degree.
Never estimate an exact numeric angle from the drawing unless a numeric angle label is printed.
Never mark two objects perpendicular unless a visible right-angle marker exists or the text explicitly says perpendicular/right angle/normal.
Never change the reference of an angle. If text says angle theta is with an inclined plane, the relation is between the vector and that surface, not between the vector and horizontal.
Never use Unicode math glyphs in `question_text_solver` or `options`; write sqrt(), theta, alpha, beta.

Return ONLY valid JSON matching this schema:
{
  "question_text_raw": "closest OCR transcription",
  "question_text_solver": "ASCII solver-ready text using sqrt(), deg, theta/alpha/beta",
  "options": ["ASCII option text in order using sqrt(), empty if absent"],
  "diagram": {
    "present": true,
    "type": "none|basic_projectile|incline|staircase|target|wall|multi_surface|3d_axes|other",
    "primitives": {
      "points": [
        {
          "id": "point_1",
          "label": "P",
          "role": "launch_point|impact_point|intersection_point|target_point|unknown",
          "description": "what this point appears to be",
          "confidence": 0.0
        }
      ],
      "surfaces": [
        {
          "id": "surface_1",
          "label": "OA",
          "kind": "line|ray|segment|inclined_plane|ground|wall|stair_face",
          "orientation_deg_from_positive_x": 150,
          "qualitative_orientation": "rises_right|rises_left|vertical|horizontal|unknown",
          "inclination_deg_with_horizontal": 30,
          "orientation_source": "explicit_label|text|unknown",
          "description": "left inclined plane",
          "confidence": 0.0
        }
      ],
      "vectors": [
        {
          "id": "vector_1",
          "label": "u",
          "kind": "initial_velocity|final_velocity|component|acceleration|unknown",
          "tail_point": "point_1",
          "direction_deg_from_positive_x": 60,
          "qualitative_direction": "up_right|up_left|down_right|down_left|horizontal|vertical|unknown",
          "direction_source": "explicit_label|text|unknown",
          "description": "initial velocity arrow",
          "confidence": 0.0
        }
      ],
      "angles": [
        {
          "id": "angle_1",
          "label": "30deg",
          "value": 30,
          "value_symbol": null,
          "unit": "deg",
          "between": ["surface_1", "horizontal"],
          "source": "explicit_label|text|unknown",
          "description": "inclination of surface_1",
          "confidence": 0.0
        }
      ],
      "distances": [
        {
          "id": "distance_1",
          "label": "h",
          "value": null,
          "unit": null,
          "between": ["point_1", "ground"],
          "description": "vertical height marker",
          "confidence": 0.0
        }
      ]
    },
    "relations": [
      {
        "type": "lies_on|intersects|perpendicular|parallel|angle_between|distance_between|starts_at|ends_at|points_to",
        "a": "vector_1",
        "b": "surface_1",
        "value": null,
        "unit": null,
        "evidence": "right angle marker at launch point",
        "confidence": 0.0
      }
    ],
    "role_bindings": {
      "launch_point": "point_1",
      "impact_point": "point_2",
      "launch_surface": "surface_1",
      "impact_surface": "surface_2",
      "initial_velocity": "vector_1",
      "target_point": null
    },
    "ambiguities": [
      "surface_1 orientation is inferred from diagram, not explicitly stated"
    ],
    "confidence": 0.0
  },
  "givens": ["u=10sqrt(3) m/s", "g=10 m/s^2"],
  "requested_quantity": "velocity_at_impact",
  "suggested_engine_case": "two_inclines_perpendicular_launch_impact",
  "warnings": []
}

Extraction rules:
- Prefer generic ids like point_1, surface_1, vector_1. Put visible letters in `label`.
- Infer semantic roles from geometry and text, not from fixed letters.
- If a role is unclear, set role="unknown" and add an ambiguity.
- If explicit question text defines an angle reference, text wins over visual guesswork.
- If text says "angle theta with an inclined plane", "theta with incline", or "angle of projection with plane", theta MUST be between the initial velocity vector and the inclined surface.
- If text says the plane makes angle beta/alpha with horizontal, beta/alpha MUST be between the inclined surface and horizontal.
- Do not rewrite options in LaTeX or Unicode math. Use ASCII like `u/sqrt(2)`, `2u/sqrt(3)`, `sqrt(2)u/3`, `10/sqrt(3)`.
- Wrong option text: `u/√2`, `\\frac{u}{\\sqrt{2}}`. Correct option text: `u/sqrt(2)`.
- For symbolic angles:
  - set `value` to null
  - set `value_symbol` to "theta", "alpha", "beta", etc.
  - preserve the actual two objects it is between.
- For numeric angles:
  - set `value` only when the number is printed in text or diagram.
  - set `source` to "explicit_label" or "text".
- For inclined surfaces:
  - set `inclination_deg_with_horizontal` only if a numeric angle is printed.
  - otherwise set it to null and add an angle primitive with `value_symbol` if symbolic.
  - set `orientation_deg_from_positive_x` only if it follows from a printed numeric angle and an unambiguous direction.
  - otherwise set `orientation_deg_from_positive_x` to null and use only `qualitative_orientation` for rough visual direction.
- For vectors:
  - set `direction_deg_from_positive_x` only if a numeric direction is printed or directly implied by printed numeric geometry.
  - otherwise set `direction_deg_from_positive_x` to null and use only `qualitative_direction`.
- For right-angle marks, add a `perpendicular` relation only if a right-angle box/marker is visible or text says perpendicular/right angle.
- If a vector is described as making angle theta with a surface, add an `angle_between` relation between vector and surface. Do not add perpendicular.
- For arrows, identify tail point if visible; otherwise set tail_point=null.
- Keep confidence honest. Do not invent values that are not visible or stated.

Bad extraction examples:
- Text says "angle theta with inclined plane"; wrong: between ["vector_1","horizontal"]. Correct: between ["vector_1","surface_1"].
- Diagram has symbolic beta at incline; wrong: value=45. Correct: value=null, value_symbol="beta".
- Incline visually appears close to 45deg but has no printed numeric value; wrong: orientation_deg_from_positive_x=45. Correct: orientation_deg_from_positive_x=null, qualitative_orientation="rises_right" or "rises_left".
- Vector looks almost normal to plane; wrong: perpendicular relation. Correct: add ambiguity unless right-angle marker/text proves it.

Engine-case rule:
- `suggested_engine_case` must be either `unknown` or exactly one of these known cases:
  - `inclined_plane_max_normal_distance_velocity_component`
  - `two_inclines_perpendicular_launch_impact`
  - `staircase_collision`
  - `wall_clearance_condition`
  - `target_launch_angle_fixed_speed`
  - `level_ground_range`
  - `level_ground_max_height`
  - `level_ground_time_of_flight`
  - `level_ground_position_at_time`
  - `projectile_velocity_change`
  - `two_projectile_collision_time`
- For "component of velocity at maximum distance from incline", use `inclined_plane_max_normal_distance_velocity_component`.
- Do not invent shorter or alternate engine case names.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe VLM diagram extraction on one image.")
    parser.add_argument("image", type=Path, help="Path to question image.")
    parser.add_argument("--mode", choices=["graph", "current"], default="graph")
    parser.add_argument("--hint", default="", help="Optional extra instruction appended to the user prompt.")
    parser.add_argument("--out", type=Path, help="Optional path to write parsed JSON.")
    parser.add_argument("--raw-out", type=Path, help="Optional path to write raw model text.")
    parser.add_argument("--api-key", default=None, help="Override API key. Otherwise reads GROQ_API_KEY/GOOGLE_API_KEY from env/.env.")
    args = parser.parse_args()

    image_path = args.image.expanduser().resolve()
    if not image_path.exists():
        raise SystemExit(f"Image not found: {image_path}")

    load_dotenv(ROOT / ".env")
    api_key = args.api_key or os.getenv("GROQ_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit("Set GROQ_API_KEY or GOOGLE_API_KEY, or pass --api-key.")

    image_bytes = image_path.read_bytes()
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    prompt = GEOMETRY_GRAPH_PROMPT if args.mode == "graph" else IMAGE_QUESTION_EXTRACTION_PROMPT
    user_text = "Extract the physics question and diagram facts from this image."
    if args.hint:
        user_text += f"\n\nExtra instruction: {args.hint}"

    raw = call_vlm(api_key=api_key, system_prompt=prompt, user_text=user_text, image_bytes=image_bytes, mime_type=mime_type)
    parsed = parse_json_object(raw)

    if args.raw_out:
        args.raw_out.write_text(raw, encoding="utf-8")
    if args.out:
        args.out.write_text(json.dumps(parsed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(parsed, indent=2, ensure_ascii=False))


def call_vlm(*, api_key: str, system_prompt: str, user_text: str, image_bytes: bytes, mime_type: str) -> str:
    if api_key.startswith("gsk_"):
        from groq import Groq

        b64 = base64.b64encode(image_bytes).decode("ascii")
        client = Groq(api_key=api_key)
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                ],
            },
        ]
        request = dict(
            messages=messages,
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            temperature=0.0,
        )
        try:
            response = client.chat.completions.create(
                **request,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            message = str(exc)
            if "json_validate_failed" not in message and "Failed to generate JSON" not in message:
                raise
            response = client.chat.completions.create(**request)
        return response.choices[0].message.content or "{}"

    import importlib

    genai = importlib.import_module("google.generativeai")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("models/gemini-1.5-flash")
    response = model.generate_content(
        [{"role": "user", "parts": [system_prompt, user_text, {"mime_type": mime_type, "data": image_bytes}]}],
        generation_config={"response_mime_type": "application/json", "temperature": 0.0},
    )
    return response.text


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    text = re.sub(r",\s*([\]}])", r"\1", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"parse_error": str(exc), "raw": raw}
    return parsed if isinstance(parsed, dict) else {"raw_json": parsed}


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    main()
