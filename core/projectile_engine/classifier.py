from __future__ import annotations

import importlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from .cases import SOLVERS, canonical_engine_case
from .intent import choose_engine_case_for_requested_quantity
from .templates import PROJECTILE_TEMPLATES, TEMPLATE_BY_ENGINE_CASE
from .text_parser import infer_engine_case_and_givens


CLASSIFIER_MODE_ENV = "PROJECTILE_CLASSIFIER"
LLM_MODEL_ENV = "PROJECTILE_CLASSIFIER_MODEL"


@dataclass(frozen=True)
class ProjectileClassification:
    engine_case: str | None
    requested_quantity: str | None
    givens: list[str]
    source: str
    unsupported: bool = False
    unsupported_reason: str = ""
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rule_engine_case: str | None = None
    llm_engine_case: str | None = None


@dataclass(frozen=True)
class LLMClassificationVerdict:
    classification: ProjectileClassification | None
    warnings: list[str] = field(default_factory=list)


PROJECTILE_CLASSIFIER_PROMPT = """You classify projectile-motion questions for a deterministic solver.
Output ONLY one JSON object. Do not solve the physics. Do not invent formulas.

Choose exactly one registered engine_case from ENGINE_CASE_REGISTRY, or set unsupported=true.
Use unsupported=true for quantitative models outside the registry, such as quadratic drag,
Magnus force, Coriolis/non-inertial motion, or moving wedge/incline questions unless the
registry explicitly contains that exact case.

JSON schema:
{
  "engine_case": "registered_engine_case_or_null",
  "requested_quantity": "short_snake_case_quantity_or_null",
  "givens": ["key=value unit", "..."],
  "evidence": ["short quote from the question", "..."],
  "unsupported": false,
  "unsupported_reason": null
}

Rules:
- engine_case must be copied exactly from the registry.
- If unsupported is true, engine_case must be null.
- givens must contain only values stated or directly visible in the question; do not compute answers.
- requested_quantity should describe what is being asked, not the final answer.
- evidence should quote or closely copy wording that justifies the case.
"""


def classify_projectile_question(
    *,
    question_text: str,
    suggested_engine_case: str | None,
    givens: list[str],
    requested_quantity: str | None,
) -> ProjectileClassification:
    """Classify question intent using rules by default, with optional LLM/hybrid mode."""
    mode = _classifier_mode()
    rules = classify_with_rules(
        question_text=question_text,
        suggested_engine_case=suggested_engine_case,
        givens=givens,
        requested_quantity=requested_quantity,
    )
    if mode == "rules":
        return rules

    verdict = classify_with_llm(
        question_text=question_text,
        suggested_engine_case=suggested_engine_case,
        givens=givens,
        requested_quantity=requested_quantity,
    )
    if verdict.classification is None:
        return _with_warnings(rules, [f"llm_classifier_unavailable: {warning}" for warning in verdict.warnings])

    llm = verdict.classification
    if mode == "llm":
        if llm.unsupported:
            return llm
        return _merge_classifications(primary=llm, secondary=rules, source="llm", warnings=verdict.warnings)

    # Hybrid uses the LLM to repair/override brittle rule intent, while keeping
    # deterministic rule givens as a backup for numeric extraction.
    warnings = list(verdict.warnings)
    if rules.engine_case and llm.engine_case and rules.engine_case != llm.engine_case:
        warnings.append(f"classifier_disagreement: rules={rules.engine_case}, llm={llm.engine_case}")
    if llm.unsupported:
        return _with_warnings(llm, warnings)
    if llm.engine_case:
        return _merge_classifications(primary=llm, secondary=rules, source="hybrid", warnings=warnings)
    return _with_warnings(rules, warnings)


def classify_with_rules(
    *,
    question_text: str,
    suggested_engine_case: str | None,
    givens: list[str],
    requested_quantity: str | None,
) -> ProjectileClassification:
    engine_case, inferred_givens = infer_engine_case_and_givens(
        question_text=question_text,
        suggested_engine_case=suggested_engine_case,
        givens=givens,
    )
    engine_case = canonical_engine_case(engine_case)
    engine_case, intent_reason = choose_engine_case_for_requested_quantity(
        question_text=question_text,
        engine_case=engine_case,
        requested_quantity=requested_quantity,
    )
    warnings = [intent_reason] if intent_reason else []
    return ProjectileClassification(
        engine_case=engine_case,
        requested_quantity=requested_quantity,
        givens=_dedupe_givens(inferred_givens),
        source="rules",
        warnings=warnings,
        rule_engine_case=engine_case,
    )


def classify_with_llm(
    *,
    question_text: str,
    suggested_engine_case: str | None,
    givens: list[str],
    requested_quantity: str | None,
) -> LLMClassificationVerdict:
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return LLMClassificationVerdict(None, ["missing provider key"])
    try:
        raw = _call_llm_classifier(
            api_key=api_key,
            question_text=question_text,
            suggested_engine_case=suggested_engine_case,
            givens=givens,
            requested_quantity=requested_quantity,
        )
        parsed = _parse_json_object(raw)
        return validate_llm_classification(
            parsed,
            original_givens=givens,
            requested_quantity=requested_quantity,
        )
    except Exception as exc:  # noqa: BLE001 - classifier fallback should be non-fatal.
        return LLMClassificationVerdict(None, [f"{type(exc).__name__}: {exc}"])


def validate_llm_classification(
    raw: dict[str, Any],
    *,
    original_givens: list[str],
    requested_quantity: str | None,
) -> LLMClassificationVerdict:
    warnings: list[str] = []
    unsupported = bool(raw.get("unsupported", False))
    unsupported_reason = str(raw.get("unsupported_reason") or "").strip()
    engine_case = canonical_engine_case(_clean_optional_string(raw.get("engine_case")))
    llm_requested_quantity = _clean_optional_string(raw.get("requested_quantity")) or requested_quantity
    evidence = _clean_string_list(raw.get("evidence"))
    givens = _dedupe_givens([*original_givens, *_clean_givens(raw.get("givens"))])

    if unsupported:
        return LLMClassificationVerdict(
            ProjectileClassification(
                engine_case=None,
                requested_quantity=llm_requested_quantity,
                givens=givens,
                source="llm",
                unsupported=True,
                unsupported_reason=unsupported_reason or "LLM classifier marked the question unsupported.",
                evidence=evidence,
                warnings=warnings,
                llm_engine_case=None,
            ),
            warnings,
        )

    if not engine_case:
        return LLMClassificationVerdict(None, ["LLM classifier returned no engine_case"])
    if engine_case not in SOLVERS:
        return LLMClassificationVerdict(None, [f"LLM classifier returned unregistered engine_case={engine_case}"])

    template = TEMPLATE_BY_ENGINE_CASE.get(engine_case)
    if template is None:
        warnings.append(f"engine_case={engine_case} has no registered template")
    if not evidence:
        warnings.append("LLM classifier returned no evidence")

    return LLMClassificationVerdict(
        ProjectileClassification(
            engine_case=engine_case,
            requested_quantity=llm_requested_quantity,
            givens=givens,
            source="llm",
            evidence=evidence,
            warnings=warnings,
            llm_engine_case=engine_case,
        ),
        warnings,
    )


def llm_engine_case_registry() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for template in PROJECTILE_TEMPLATES:
        for engine_case in sorted(template.engine_cases):
            rows.append(
                {
                    "engine_case": engine_case,
                    "template_id": template.id,
                    "family": template.family,
                    "when_to_use": template.title,
                    "requested_quantities": sorted(template.accepted_quantities),
                    "known_keys": sorted(template.required_known_keys | template.optional_known_keys),
                    "solve_strategy": template.solve_strategy,
                }
            )
    return rows


def projectile_classifier_mode() -> str:
    return _classifier_mode()


def _call_llm_classifier(
    *,
    api_key: str,
    question_text: str,
    suggested_engine_case: str | None,
    givens: list[str],
    requested_quantity: str | None,
) -> str:
    payload = {
        "question_text": question_text,
        "suggested_engine_case": suggested_engine_case,
        "requested_quantity": requested_quantity,
        "givens_already_extracted": givens,
        "engine_case_registry": llm_engine_case_registry(),
    }
    if api_key.startswith("gsk_"):
        groq_module = importlib.import_module("groq")
        client = groq_module.Groq(api_key=api_key)
        model = os.getenv(LLM_MODEL_ENV, "meta-llama/llama-4-scout-17b-16e-instruct")
        try:
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": PROJECTILE_CLASSIFIER_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
                ],
                model=model,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
        except Exception:
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": PROJECTILE_CLASSIFIER_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
                ],
                model=model,
                temperature=0.0,
            )
        return resp.choices[0].message.content

    genai = importlib.import_module("google.generativeai")
    genai.configure(api_key=api_key)
    model_name = os.getenv(LLM_MODEL_ENV, "models/gemini-1.5-flash")
    model = genai.GenerativeModel(model_name)
    resp = model.generate_content(
        [
            {
                "role": "user",
                "parts": [PROJECTILE_CLASSIFIER_PROMPT, json.dumps(payload, ensure_ascii=True)],
            }
        ],
        generation_config={"response_mime_type": "application/json", "temperature": 0.0},
    )
    return resp.text


def _classifier_mode() -> str:
    explicit = os.getenv(CLASSIFIER_MODE_ENV)
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
        raise ValueError("LLM classifier did not return a JSON object")
    return parsed


def _merge_classifications(
    *,
    primary: ProjectileClassification,
    secondary: ProjectileClassification,
    source: str,
    warnings: list[str],
) -> ProjectileClassification:
    return ProjectileClassification(
        engine_case=primary.engine_case,
        requested_quantity=primary.requested_quantity or secondary.requested_quantity,
        givens=_dedupe_givens([*secondary.givens, *primary.givens]),
        source=source,
        unsupported=primary.unsupported,
        unsupported_reason=primary.unsupported_reason,
        evidence=primary.evidence,
        warnings=_dedupe_text([*secondary.warnings, *primary.warnings, *warnings]),
        rule_engine_case=secondary.rule_engine_case or secondary.engine_case,
        llm_engine_case=primary.llm_engine_case or primary.engine_case,
    )


def _with_warnings(classification: ProjectileClassification, warnings: list[str]) -> ProjectileClassification:
    return ProjectileClassification(
        engine_case=classification.engine_case,
        requested_quantity=classification.requested_quantity,
        givens=classification.givens,
        source=classification.source,
        unsupported=classification.unsupported,
        unsupported_reason=classification.unsupported_reason,
        evidence=classification.evidence,
        warnings=_dedupe_text([*classification.warnings, *warnings]),
        rule_engine_case=classification.rule_engine_case,
        llm_engine_case=classification.llm_engine_case,
    )


def _clean_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "unsupported"}:
        return None
    return text


def _clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _clean_givens(value: Any) -> list[str]:
    givens = []
    for item in _clean_string_list(value):
        if "=" not in item:
            continue
        key, raw_value = item.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if key and raw_value:
            givens.append(f"{key}={raw_value}")
    return givens


def _dedupe_givens(givens: list[str]) -> list[str]:
    keyed: dict[str, str] = {}
    passthrough: list[str] = []
    for given in givens:
        if "=" not in given:
            if given not in passthrough:
                passthrough.append(given)
            continue
        key, value = given.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            keyed[key] = f"{key}={value}"
    return list(keyed.values()) + passthrough


def _dedupe_text(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in deduped:
            deduped.append(text)
    return deduped
