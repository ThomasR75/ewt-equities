"""Guideline scores (spec §7): soft 0..1 measures of how textbook a count is.

None of these can reject a count; together they form `Count.score`, which drives
scenario weighting (spec §10) and beam pruning (spec §8). All ratios are measured
on the resolved scale so a multi-decade impulse is judged on log.
"""

from __future__ import annotations

import math

from ..schemas import Leg, Scale
from .base import RuleResult, resolve_scale
from .cardinal import _impulse_log_span

GUIDELINE_RULES = [
    "w3_extension",
    "fib_w2",
    "fib_w4",
    "fib_w3",
    "equality_w5",
    "alternation",
    "volume_w3",
]

# Default weights; tuned later (§17). Sum need not be 1 (we normalize).
_WEIGHTS = {
    "w3_extension": 1.0,
    "fib_w2": 1.0,
    "fib_w4": 1.0,
    "fib_w3": 1.2,
    "equality_w5": 0.8,
    "alternation": 1.0,
    "volume_w3": 0.6,
}


def _closeness(x: float, targets: list[float], tol: float = 0.15) -> float:
    """1.0 at a target ratio, decaying gaussian away from it."""
    if x <= 0 or math.isinf(x):
        return 0.0
    return max(math.exp(-(((x - t) / tol) ** 2)) for t in targets)


def score_guidelines(
    legs: list[Leg], scale: str = "auto", volumes: list[float] | None = None
) -> tuple[float, dict[str, RuleResult]]:
    sc: Scale = resolve_scale(scale, _impulse_log_span(legs))
    w1, w2, w3, w4, w5 = (leg.mag(sc) for leg in legs)

    scores: dict[str, float] = {}

    # Wave 3 is commonly the longest and never the shortest.
    longest = max(w1, w3, w5)
    scores["w3_extension"] = 1.0 if w3 == longest and w3 > 0 else (w3 / longest if longest else 0.0)

    # Canonical retracement / extension bands.
    scores["fib_w2"] = _closeness(w2 / w1 if w1 else math.inf, [0.5, 0.618])
    scores["fib_w4"] = _closeness(w4 / w3 if w3 else math.inf, [0.236, 0.382, 0.5])
    scores["fib_w3"] = _closeness(w3 / w1 if w1 else math.inf, [1.618, 2.618])

    # Wave equality: W5 ~ W1 (esp. when W3 extends), else W5 ~ .618*W1.
    scores["equality_w5"] = _closeness(w5 / w1 if w1 else math.inf, [1.0, 0.618])

    # Alternation: W2 and W4 should differ in depth (one deep, one shallow).
    r2 = w2 / w1 if w1 else 0.0
    r4 = w4 / w3 if w3 else 0.0
    scores["alternation"] = min(1.0, abs(r2 - r4) / 0.35)

    # Volume tends to peak in W3 (only if volume data is present and non-trivial).
    if volumes and len(volumes) == 5 and sum(volumes) > 0:
        scores["volume_w3"] = 1.0 if volumes[2] == max(volumes) else 0.4
    else:
        scores["volume_w3"] = 0.5  # neutral when unknown

    total_w = sum(_WEIGHTS.values())
    combined = sum(scores[k] * _WEIGHTS[k] for k in scores) / total_w

    results = {
        k: RuleResult(k, "guideline", sc, score=v, detail=f"{v:.3f}")
        for k, v in scores.items()
    }
    return combined, results
