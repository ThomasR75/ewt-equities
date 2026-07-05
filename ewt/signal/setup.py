"""Setup synthesis + R/R gate (spec §11), v1.2 — degree-scaled risk.

Builds on v1.1 (anchored structural entry, log R/R, stable id) and adds
DEGREE-SCALED invalidation/stop: the throw-over room granted beyond the
completion pivot is a fraction of the final leg's log size (its degree),
clamped to a band. A Cycle-degree top is not voided by the same wiggle that
would void a Minor one.
"""

from __future__ import annotations

import math

from ..schemas import Scenario, Setup
from ..levels.fibonacci import fib_levels

RR_FLOOR = 2.0
ENTRY_OFFSET = 0.02       # enter ~2% off the completion pivot (confirmation nudge)
STOP_EXTRA = 0.01         # stop sits just beyond the (degree-scaled) invalidation
MIN_RISK_LOG = math.log(1.02)
TOL_K = 0.30              # invalidation room = 30% of the final leg's log size...
MIN_TOL = math.log(1.03)  # ...but at least 3% (Minor degree)
MAX_TOL = math.log(1.30)  # ...and at most 30% (Cycle/Supercycle degree)
NEAR_MAX = 0.15           # skip if price has run >15% past the pivot (chasing)
NEAR_TOL = 0.01
EXT_RATIOS = (1.272, 1.618, 2.618)


def _direction_targets(count, entry: float, direction: int, base_log: float) -> list[float]:
    le = math.log(entry)
    cand = [fl.price for fl in fib_levels(count) if fl.price > 0]
    cand += [math.exp(le + direction * k * base_log) for k in EXT_RATIOS]
    if direction > 0:
        cand = sorted(x for x in cand if x > entry * 1.005)
    else:
        cand = sorted((x for x in cand if 0 < x < entry * 0.995), reverse=True)
    out: list[float] = []
    for x in cand:
        if not out or abs(math.log(x) - math.log(out[-1])) > 0.01:
            out.append(x)
    return out


def build_setup(scenario: Scenario, last_price, as_of: str, ticker: str,
                horizon_bars: int = 60, n_prior: int = 0) -> Setup | None:
    count = scenario.primary_count
    d = scenario.direction
    if count is None or d == 0 or not last_price or last_price <= 0:
        return None

    final = count.legs[-1]
    extreme = float(final.end.price)         # the structural completion pivot
    if extreme <= 0:
        return None
    lx = math.log(extreme)

    # Degree-scaled invalidation tolerance (throw-over room beyond the pivot).
    leg_log = abs(lx - math.log(final.start.price))
    tol = min(MAX_TOL, max(MIN_TOL, TOL_K * leg_log))

    entry = extreme * math.exp(d * ENTRY_OFFSET)       # toward target, just off pivot
    invalid = extreme * math.exp(-d * tol)             # beyond pivot by degree room
    stop = invalid * math.exp(-d * STOP_EXTRA)
    le, ls, lp = math.log(entry), math.log(stop), math.log(last_price)
    risk_log = abs(le - ls)
    if risk_log < MIN_RISK_LOG:
        return None

    # Price must still be near the completion (not past pivot / not chasing).
    prog = (lp - lx) * d
    if prog < -NEAR_TOL or prog > NEAR_MAX:
        return None

    base_log = leg_log or risk_log
    targets = _direction_targets(count, entry, d, base_log)
    if not targets:
        return None
    t1 = targets[0]
    t2 = targets[1] if len(targets) > 1 else targets[0]
    reward_log = abs(math.log(t1) - le)
    if reward_log <= 0:
        return None
    rr = round(reward_log / risk_log, 2)

    dir_str = "long" if d > 0 else "short"
    # Degree-scaled horizon: give the trade about as long to resolve as the
    # structure took to form (clamped). A Cycle-degree call needs years, not
    # the flat 60 bars — otherwise it just expires unresolved.
    horizon_bars = max(120, min(2500, int(final.bars)))

    anchor = final.end.ts.strftime("%Y%m%d")
    sid = f"{ticker}-{anchor}-{'S' if d < 0 else 'L'}"
    inval_rule = (f"close {'above' if d < 0 else 'below'} {round(invalid, 6)} "
                  f"voids the {count.structure} read (degree-scaled)")
    frozen = {
        "entry": round(entry, 6), "entry_type": "limit", "stop": round(stop, 6),
        "t1": round(t1, 6), "t2": round(t2, 6), "direction": dir_str,
        "invalidation_level": round(invalid, 6), "tol_pct": round(math.exp(tol) - 1, 4),
        "rr_scale": "log",
    }
    return Setup(
        id=sid, grade=None, direction=dir_str, entry=round(entry, 6),
        entry_type="limit", stop=round(stop, 6), t1=round(t1, 6), t2=round(t2, 6),
        rr=rr, invalidation_level=round(invalid, 6), invalidation_rule=inval_rule,
        horizon_bars=horizon_bars, issued=as_of, status="untriggered", frozen=frozen,
    )
