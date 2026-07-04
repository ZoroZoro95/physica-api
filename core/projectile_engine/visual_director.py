from __future__ import annotations

from functools import lru_cache
from typing import Any

from .models import EvaluationResult
from .visuals.registry import default_visual_family_packs
from .visuals.selector import select_visual_family_pack
from .visuals.types import BeatContext, VisualFamilyPack
from .visuals.utils import dedupe_labels, dedupe_strings


class VisualDirector:
    """Builds the semantic visual contract for each walkthrough beat.

    The director owns selection and sequencing. Family packs own the templates
    and renderer requirements. SVG and 3D renderers should consume the contract
    instead of re-classifying the step from loose overlay strings.
    """

    def __init__(self, packs: tuple[VisualFamilyPack, ...] | None = None) -> None:
        self.packs = packs or default_visual_family_packs()
        self._packs_by_family = {pack.family: pack for pack in self.packs}
        self._fallback_pack = self.packs[-1]

    def build_beat_visual_spec(
        self,
        *,
        result: EvaluationResult,
        step_id: str,
        title: str = "",
        text: str = "",
        visual_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        plan = dict(visual_plan or {})
        context = BeatContext(result=result, step_id=step_id, title=title, text=text, visual_plan=plan)
        pack, selection = select_visual_family_pack(context, self.packs)
        if selection.beat:
            plan["_visual_director_beat"] = selection.beat
            context = BeatContext(result=result, step_id=step_id, title=title, text=text, visual_plan=plan)
        spec = pack.build_spec(context)
        spec["director"] = {
            "selected_family": pack.family,
            "selection_source": selection.source,
            "warnings": list(selection.warnings),
        }
        return spec

    def apply_to_plan(
        self,
        *,
        result: EvaluationResult,
        step_id: str,
        title: str,
        text: str,
        visual_plan: dict[str, Any],
    ) -> dict[str, Any]:
        plan = dict(visual_plan)
        spec = self.build_beat_visual_spec(
            result=result,
            step_id=step_id,
            title=title,
            text=text,
            visual_plan=plan,
        )
        plan["beat_visual_spec"] = spec
        plan["visual_action"] = self.visual_action(str(plan.get("visual_action") or ""), spec)
        plan["camera"] = str((spec.get("renderer_hints") or {}).get("camera") or plan.get("camera") or "full_scene")
        plan["show_ids"] = self.visible_ids(plan.get("show_ids") or [], spec)
        plan["highlight_ids"] = self.visible_ids(plan.get("highlight_ids") or plan.get("show_ids") or [], spec)
        plan["visible_vectors"] = self.visible_vectors(plan.get("visible_vectors") or [], spec)
        plan["labels"] = self.merge_labels(plan.get("labels") or [], spec.get("labels") or [])
        plan["hide_ids"] = dedupe_strings([*(plan.get("hide_ids") or []), *(spec.get("must_not_show") or [])])
        plan["visual_state"] = self.visual_state_for_plan(plan)
        return plan

    def visible_vectors(self, existing: list[Any], spec: dict[str, Any]) -> list[str]:
        return self._pack_for_spec(spec).visible_vectors(existing, spec)

    def visible_ids(self, existing: list[Any], spec: dict[str, Any]) -> list[str]:
        return self._pack_for_spec(spec).visible_ids(existing, spec)

    def visual_action(self, existing: str, spec: dict[str, Any]) -> str:
        return self._pack_for_spec(spec).visual_action(existing, spec)

    def merge_labels(self, existing: list[Any], contract_labels: list[Any]) -> list[dict[str, Any]]:
        return dedupe_labels([*existing, *contract_labels])

    def visual_state_for_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        visible_ids = [str(item) for item in plan.get("show_ids") or [] if str(item)]
        vector_ids = [str(item) for item in plan.get("visible_vectors") or [] if str(item)]
        highlight_ids = [str(item) for item in plan.get("highlight_ids") or [] if str(item)]
        label_ids = [
            str(label.get("target_id"))
            for label in plan.get("labels") or []
            if isinstance(label, dict) and str(label.get("target_id") or "")
        ]
        return {
            "visible_ids": dedupe_strings(visible_ids),
            "visible_vectors": dedupe_strings(vector_ids),
            "highlight_ids": dedupe_strings(highlight_ids),
            "label_ids": dedupe_strings(label_ids),
            "dimmed_ids": dedupe_strings(plan.get("dimmed_ids") or []),
            "persist_until": "next_beat",
        }

    def _pack_for_spec(self, spec: dict[str, Any]) -> VisualFamilyPack:
        family = str(spec.get("family") or "")
        return self._packs_by_family.get(family, self._fallback_pack)


@lru_cache(maxsize=1)
def default_visual_director() -> VisualDirector:
    return VisualDirector()
