from __future__ import annotations

import importlib
import json
import os
import re
from typing import Any

from .registry import default_visual_family_packs
from .types import BeatContext, VisualFamilyPack, VisualSelection


SELECTOR_MODE_ENV = "PROJECTILE_VISUAL_SELECTOR"
SELECTOR_MODEL_ENV = "PROJECTILE_VISUAL_SELECTOR_MODEL"

VISUAL_SELECTOR_PROMPT = """You select the visual family pack and beat for a projectile walkthrough step.
Output ONLY one JSON object. Do not solve physics. Do not invent labels, coordinates, formulas, or SVG.

Choose exactly one family from FAMILY_PACKS and optionally one beat listed by that family.

JSON schema:
{
  "family": "registered_family_name",
  "beat": "registered_beat_or_null",
  "evidence": ["short reason from the step/question", "..."]
}
"""


def select_visual_family_pack(
    context: BeatContext,
    packs: tuple[VisualFamilyPack, ...] | None = None,
) -> tuple[VisualFamilyPack, VisualSelection]:
    registry = packs or default_visual_family_packs()
    mode = _selector_mode()
    rules_pack = _select_with_rules(context, registry)
    if mode == "rules":
        return rules_pack, VisualSelection(family=rules_pack.family, source="rules")

    llm_selection = _select_with_llm(context, registry)
    if llm_selection is None:
        return rules_pack, VisualSelection(family=rules_pack.family, source="rules", warnings=("llm_visual_selector_unavailable",))

    llm_pack = _pack_by_family(registry).get(llm_selection.family)
    if llm_pack is None:
        return rules_pack, VisualSelection(
            family=rules_pack.family,
            source="rules",
            warnings=(f"llm_visual_selector_invalid_family:{llm_selection.family}",),
        )
    if mode == "llm":
        return llm_pack, llm_selection

    warnings: list[str] = []
    if rules_pack.family != llm_pack.family:
        warnings.append(f"visual_selector_disagreement: rules={rules_pack.family}, llm={llm_pack.family}")
    return llm_pack, VisualSelection(
        family=llm_pack.family,
        source="hybrid",
        beat=llm_selection.beat,
        warnings=tuple(warnings),
    )


def visual_family_registry_context(packs: tuple[VisualFamilyPack, ...] | None = None) -> list[dict[str, Any]]:
    return [pack.describe() for pack in (packs or default_visual_family_packs())]


def _select_with_rules(context: BeatContext, packs: tuple[VisualFamilyPack, ...]) -> VisualFamilyPack:
    for pack in packs:
        if pack.engine_cases and pack.matches(context.result):
            return pack
    return packs[-1]


def _select_with_llm(context: BeatContext, packs: tuple[VisualFamilyPack, ...]) -> VisualSelection | None:
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        raw = _call_llm_visual_selector(api_key=api_key, context=context, packs=packs)
        parsed = _parse_json_object(raw)
        family = _clean_identifier(parsed.get("family"))
        if not family:
            return None
        beat = _clean_optional_identifier(parsed.get("beat"))
        allowed_beats = _allowed_beats_by_family(packs).get(family, ())
        if beat and allowed_beats and beat not in allowed_beats:
            beat = None
        return VisualSelection(family=family, source="llm", beat=beat)
    except Exception:
        return None


def _call_llm_visual_selector(
    *,
    api_key: str,
    context: BeatContext,
    packs: tuple[VisualFamilyPack, ...],
) -> str:
    payload = {
        "engine_case": context.result.engine_case,
        "step_id": context.step_id,
        "step_title": context.title,
        "step_text": context.text,
        "visual_plan": _compact_visual_plan(context.visual_plan),
        "family_packs": visual_family_registry_context(packs),
    }
    if api_key.startswith("gsk_"):
        groq_module = importlib.import_module("groq")
        client = groq_module.Groq(api_key=api_key)
        model = os.getenv(SELECTOR_MODEL_ENV, "meta-llama/llama-4-scout-17b-16e-instruct")
        try:
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": VISUAL_SELECTOR_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
                ],
                model=model,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
        except Exception:
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": VISUAL_SELECTOR_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
                ],
                model=model,
                temperature=0.0,
            )
        return resp.choices[0].message.content

    genai = importlib.import_module("google.generativeai")
    genai.configure(api_key=api_key)
    model_name = os.getenv(SELECTOR_MODEL_ENV, "models/gemini-1.5-flash")
    model = genai.GenerativeModel(model_name)
    resp = model.generate_content(
        [
            {
                "role": "user",
                "parts": [VISUAL_SELECTOR_PROMPT, json.dumps(payload, ensure_ascii=True)],
            }
        ],
        generation_config={"response_mime_type": "application/json", "temperature": 0.0},
    )
    return resp.text


def _selector_mode() -> str:
    explicit = os.getenv(SELECTOR_MODE_ENV)
    if explicit is None or not explicit.strip():
        environment = os.getenv("ENVIRONMENT", "").strip().lower()
        return "hybrid" if environment in {"prod", "production"} else "rules"
    mode = explicit.strip().lower()
    return mode if mode in {"rules", "llm", "hybrid"} else "rules"


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    text = re.sub(r",\s*([\]}])", r"\1", text)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("visual selector did not return a JSON object")
    return parsed


def _pack_by_family(packs: tuple[VisualFamilyPack, ...]) -> dict[str, VisualFamilyPack]:
    return {pack.family: pack for pack in packs}


def _allowed_beats_by_family(packs: tuple[VisualFamilyPack, ...]) -> dict[str, tuple[str, ...]]:
    out: dict[str, tuple[str, ...]] = {}
    for pack in packs:
        beats = pack.describe().get("beats") or ()
        out[pack.family] = tuple(str(item) for item in beats if str(item))
    return out


def _compact_visual_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        key: plan.get(key)
        for key in ("visual_action", "scene_phase", "show_ids", "hide_ids", "highlight_ids", "visible_vectors", "camera")
        if key in plan
    }


def _clean_identifier(value: Any) -> str:
    text = str(value or "").strip()
    return text if re.fullmatch(r"[a-z][a-z0-9_]*", text) else ""


def _clean_optional_identifier(value: Any) -> str | None:
    text = _clean_identifier(value)
    return text or None
