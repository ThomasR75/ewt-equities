"""Corrective-structure rules (spec §7, M3): zigzag, flat, triangle.

Corrections are where wave counting earns its keep. The decisive split is depth
of wave B, exactly as in the reference reports ("[B] retraces 90.2% on log — too
deep for a zigzag, so flat-family"):

  3-leg A-B-C
    zigzag (5-3-5)   sharp; B retraces < ~81% of A; C makes a new extreme.
    flat (3-3-5)     sideways; B retraces >= ~81% of A.
        regular      B ~100% of A, C ~100% of A
        expanded     B  >100% of A, C  >100% of A   (most common)
        running      B  >100% of A, C truncated (< A end)

  5-leg A-B-C-D-E
    contracting triangle   each same-direction leg smaller; lines converge
    expanding triangle     each same-direction leg larger; lines diverge

All ratios are measured on the resolved scale (log for large moves). Hard
feasibility decides the family; soft fib-band closeness scores the fit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..schemas import Leg, Scale
from .base import resolve_scale
from ..score_config import active as _active_score

# Depth of wave B that separates a (sharp) zigzag from a (sideways) flat.
ZIGZAG_MAX_B = 0.81
CORRECTIVE_TOL = 0.18
ZZ_B_TARGETS = [0.5, 0.618, 0.786]
ZZ_C_TARGETS = [0.618, 1.0, 1.618]
FLAT_REGULAR_MAX = 1.05
FLAT_REGULAR_B, FLAT_REGULAR_C = [1.0], [1.0]
FLAT_RUNNING_B, FLAT_RUNNING_C = [1.1, 1.236, 1.382], [0.6, 0.8]
FLAT_EXPANDED_B, FLAT_EXPANDED_C = [1.1, 1.236, 1.382], [1.0, 1.236, 1.618]
TRIANGLE_RATIOS = [0.618, 0.786]


@dataclass
class CorrectiveFit:
    structure: str          # zigzag | flat | (expanded_flat etc. via subtype) | triangle...
    subtype: str            # "", regular/expanded/running, contracting/expanding
    score: float            # 0..1 fit
    detail: str = ""


def _closeness(x: float, targets, tol: float | None = None) -> float:
    tol = _active_score().corr_tol if tol is None else tol
    if x <= 0 or math.isinf(x):
        return 0.0
    return max(math.exp(-(((x - t) / tol) ** 2)) for t in targets)


def _span_log(legs: list[Leg]) -> float:
    lps = [legs[0].start.log_price] + [l.end.log_price for l in legs]
    return max(lps) - min(lps)


def _extends_beyond(a_start, a_end, c_end, direction: int) -> bool:
    """Does C terminate beyond A's terminus (a new corrective extreme)?"""
    if direction < 0:   # A is down -> new low means lower
        return c_end.price < a_end.price
    return c_end.price > a_end.price


def analyze_abc(legs: list[Leg], scale: str = "auto") -> CorrectiveFit | None:
    if len(legs) != 3:
        return None
    sc: Scale = resolve_scale(scale, _span_log(legs))
    A, B, C = legs
    a, b, c = A.mag(sc), B.mag(sc), C.mag(sc)
    if a <= 0 or c <= 0:
        return None

    direction = A.dir
    # B and C must be counter to / with the correction appropriately:
    if B.dir == A.dir or C.dir != A.dir:
        return None  # A,B,C must alternate down-up-down (or up-down-up)

    br = b / a
    cr = c / a
    extends = _extends_beyond(A.start, A.end, C.end, direction)

    if br < ZIGZAG_MAX_B:
        # Zigzag: needs C to make progress (>= ~0.618 A) and ideally a new extreme.
        score = _closeness(br, ZZ_B_TARGETS) * _closeness(cr, ZZ_C_TARGETS)
        if extends:
            score = min(1.0, score * 1.15)
        return CorrectiveFit("zigzag", "", round(score, 4),
                             f"B/A={br:.3f} C/A={cr:.3f} extends={extends} [{sc}]")

    # Flat family (deep B).
    if br <= FLAT_REGULAR_MAX and cr <= FLAT_REGULAR_MAX:
        subtype, sc_b, sc_c = "regular", FLAT_REGULAR_B, FLAT_REGULAR_C
    elif br > 1.0 and not extends:
        subtype, sc_b, sc_c = "running", FLAT_RUNNING_B, FLAT_RUNNING_C
    else:
        subtype, sc_b, sc_c = "expanded", FLAT_EXPANDED_B, FLAT_EXPANDED_C
    score = _closeness(br, sc_b) * _closeness(cr, sc_c)
    return CorrectiveFit("flat", subtype, round(score, 4),
                         f"B/A={br:.3f} C/A={cr:.3f} extends={extends} [{sc}]")


def analyze_triangle(legs: list[Leg], scale: str = "auto") -> CorrectiveFit | None:
    if len(legs) != 5:
        return None
    sc: Scale = resolve_scale(scale, _span_log(legs))
    a, b, c, d, e = (l.mag(sc) for l in legs)
    if min(a, b, c, d, e) <= 0:
        return None
    # Same-direction legs are (A,C,E) and (B,D).
    contracting = (c < a) and (e < c) and (d < b)
    expanding = (c > a) and (e > c) and (d > b)
    if not (contracting or expanding):
        return None
    subtype = "contracting" if contracting else "expanding"
    if contracting:
        # Each leg ~0.618 of the prior same-direction leg in the ideal case.
        score = (
            _closeness(c / a, TRIANGLE_RATIOS)
            * _closeness(e / c, TRIANGLE_RATIOS)
            * _closeness(d / b, TRIANGLE_RATIOS)
        ) ** (1 / 3)
    else:
        score = (
            _closeness(a / c, TRIANGLE_RATIOS)
            * _closeness(c / e, TRIANGLE_RATIOS)
            * _closeness(b / d, TRIANGLE_RATIOS)
        ) ** (1 / 3)
    return CorrectiveFit("triangle", subtype, round(score, 4),
                         f"legs={a:.3f},{b:.3f},{c:.3f},{d:.3f},{e:.3f} [{sc}]")


def analyze_corrective(legs: list[Leg], scale: str = "auto") -> CorrectiveFit | None:
    if len(legs) == 3:
        return analyze_abc(legs, scale)
    if len(legs) == 5:
        return analyze_triangle(legs, scale)
    return None
