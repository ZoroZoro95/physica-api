"""Generalized projectile DPP evaluator."""

from .evaluator import evaluate_manifest_entry, solve_ad_hoc_question
from .models import EvaluationResult, ManifestEntry
from .mapper import ProjectileProblemSpec, map_projectile_problem
from .walkthrough import build_solution_walkthrough

__all__ = [
    "EvaluationResult",
    "ManifestEntry",
    "ProjectileProblemSpec",
    "build_solution_walkthrough",
    "evaluate_manifest_entry",
    "map_projectile_problem",
    "solve_ad_hoc_question",
]
