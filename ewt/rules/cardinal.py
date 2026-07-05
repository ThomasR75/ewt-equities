"""The three cardinal rules (spec §7), as scale-aware inequalities on legs.

Because consecutive pivots alternate H/L, the directional checks reduce to clean
magnitude inequalities that hold for both bullish and bearish motive waves:

  legs = [w1, w2, w3, w4, w5]   (w2, w4 are the counter-trend legs)

  R1  W2 retraces < 100% of W1        ->  w2 < w1
  R2  W3 is not the shortest motive   ->  not (w3 < w1 and w3 < w5)
  R3  W4 does not overlap W1          ->  w3 > w2 + w4   (no price overlap)

R3 is what separates an impulse (must hold) from a diagonal (overlap allowed),
so it is reported, not used to reject outright — the classifier decides.
"""

from __future__ import annotations

from ..schemas import Leg, Scale
from .base import RuleResult, resolve_scale

CARDINAL_RULES = ["w2_retrace", "w3_not_shortest", "w4_overlap"]


def _impulse_log_span(legs: list[Leg]) -> float:
    return abs(legs[4].end.log_price - legs[0].start.log_price)


def check_cardinal(legs: list[Leg], scale: str = "auto") -> dict[str, RuleResult]:
    if len(legs) != 5:
        raise ValueError("cardinal rules expect exactly 5 legs")
    sc: Scale = resolve_scale(scale, _impulse_log_span(legs))
    w1, w2, w3, w4, w5 = (leg.mag(sc) for leg in legs)

    r1 = RuleResult(
        "w2_retrace", "cardinal", sc, passed=(w2 < w1),
        detail=f"W2/W1={w2/w1:.3f}" if w1 else "W1=0",
    )
    r2 = RuleResult(
        "w3_not_shortest", "cardinal", sc, passed=not (w3 < w1 and w3 < w5),
        detail=f"W1={w1:.4f} W3={w3:.4f} W5={w5:.4f}",
    )
    no_overlap = w3 > (w2 + w4)
    r3 = RuleResult(
        "w4_overlap", "cardinal", sc, passed=no_overlap,
        detail=f"W3={w3:.4f} vs W2+W4={(w2 + w4):.4f} "
               f"({'no overlap' if no_overlap else 'OVERLAP'})",
    )
    return {"w2_retrace": r1, "w3_not_shortest": r2, "w4_overlap": r3}


def impulse_valid(card: dict[str, RuleResult]) -> bool:
    """All three pass -> a legal impulse."""
    return all(card[k].passed for k in CARDINAL_RULES)


def diagonal_valid(card: dict[str, RuleResult]) -> bool:
    """R1 and R2 pass but W1 territory is overlapped -> a (legal) diagonal."""
    return (
        card["w2_retrace"].passed
        and card["w3_not_shortest"].passed
        and not card["w4_overlap"].passed
    )
