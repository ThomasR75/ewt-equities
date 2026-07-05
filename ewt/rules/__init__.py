"""Rule engine: scale-aware cardinal filters and guideline scores (spec §7)."""

from .base import RuleResult
from .cardinal import check_cardinal, CARDINAL_RULES
from .guidelines import score_guidelines, GUIDELINE_RULES

__all__ = [
    "RuleResult",
    "check_cardinal",
    "CARDINAL_RULES",
    "score_guidelines",
    "GUIDELINE_RULES",
]
