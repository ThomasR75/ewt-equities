"""Scale-aware Fibonacci retracements and projections (spec §4 levels/).

Every level is computed on the scale the count was validated on, so a level
quoted for a multi-decade move is a log retracement (the recurring correction
in the reference reports). A FibLevel records its anchor and a human label so
the chart and the report can explain where the number comes from.
"""

from __future__ import annotations

from ..schemas import FibLevel, Leg, Pivot, Scale, Count

RETRACE_RATIOS = [0.236, 0.382, 0.5, 0.618, 0.786]
PROJECT_RATIOS = [1.0, 1.272, 1.618, 2.618]


def _price_at(a: Pivot, b: Pivot, ratio: float, scale: Scale) -> float:
    """Level `ratio` of the a->b move measured back from b (retrace) or
    beyond b (projection if ratio>1, extending the a->b move from b)."""
    if scale == "log":
        lp = b.log_price - ratio * (b.log_price - a.log_price)
        return float(__import__("math").exp(lp))
    return float(b.price - ratio * (b.price - a.price))


def retrace_levels(
    a: Pivot, b: Pivot, scale: Scale, ratios=None, label_prefix="retr"
) -> list[FibLevel]:
    ratios = ratios or RETRACE_RATIOS
    out = []
    for r in ratios:
        out.append(
            FibLevel(
                ratio=r,
                kind="retrace",
                scale=scale,
                anchor_legs=[Leg(a, b)],
                price=_price_at(a, b, r, scale),
                label=f"{label_prefix} {r:.3f}",
            )
        )
    return out


def projection_levels(
    a: Pivot, b: Pivot, origin: Pivot, scale: Scale, ratios=None, label_prefix="proj"
) -> list[FibLevel]:
    """Project the a->b length from `origin` (e.g. W3 = 1.618*W1 off W2 low)."""
    ratios = ratios or PROJECT_RATIOS
    import math

    out = []
    for r in ratios:
        if scale == "log":
            length = (b.log_price - a.log_price) * r
            price = math.exp(origin.log_price + length)
        else:
            length = (b.price - a.price) * r
            price = origin.price + length
        out.append(
            FibLevel(
                ratio=r,
                kind="projection",
                scale=scale,
                anchor_legs=[Leg(a, b)],
                price=float(price),
                label=f"{label_prefix} {r:.3f}",
            )
        )
    return out


def fib_levels(count: Count) -> list[FibLevel]:
    """Decision-relevant levels, dispatched by structure (spec §4 levels/)."""
    legs = count.legs
    scale: Scale = count.rule_report.scale_used.get("cardinal",
                   count.rule_report.scale_used.get("corrective", "log"))  # type: ignore

    # Motive: impulse / diagonal (>=5 legs).
    if len(legs) == 5 and count.structure in ("impulse", "leading_diag", "ending_diag"):
        p0 = legs[0].start; p1 = legs[0].end; p2 = legs[1].end
        p4 = legs[3].end; p5 = legs[4].end
        out: list[FibLevel] = []
        out += retrace_levels(p0, p5, scale, label_prefix="impulse retr")
        out += projection_levels(p0, p1, p2, scale, ratios=[1.618, 2.618], label_prefix="W3=xW1")
        out += projection_levels(p0, p1, p4, scale, ratios=[0.618, 1.0], label_prefix="W5=xW1")
        return out

    # Corrective ABC (3 legs): retraces of the whole correction + C=xA targets.
    if len(legs) == 3:
        a0 = legs[0].start; aE = legs[0].end; bE = legs[1].end; cE = legs[2].end
        out = []
        out += retrace_levels(a0, cE, scale, label_prefix="corr retr")
        out += projection_levels(a0, aE, bE, scale, ratios=[0.618, 1.0, 1.618],
                                 label_prefix="C=xA")
        return out

    # Triangle (5 legs): thrust target = widest leg projected from E.
    if len(legs) == 5:
        a0 = legs[0].start; aE = legs[0].end; eE = legs[4].end
        out = retrace_levels(legs[0].start, eE, scale, label_prefix="tri retr")
        out += projection_levels(a0, aE, eE, scale, ratios=[0.618, 1.0],
                                 label_prefix="thrust")
        return out

    return []
