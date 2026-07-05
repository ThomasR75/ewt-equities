"""Canonical outcome-resolution rules (spec §18).

Single source of truth for what a frozen setup's outcome *means*, so the
in-report scorecard (§12) and the separate tester (§15) never disagree. Pure
function of (frozen_setup, continuation_bars).

State machine:
    untriggered -> active -> {won | lost | invalidated | expired}
    untriggered -> expired   (horizon elapses before fill)

Tie-break (must be fixed once, spec §18): when a single bar spans both stop and
T1, resolve **stop-first** (conservative). Exposed via `tie_break`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class OutcomeResult:
    status: str               # untriggered|active|won|lost|invalidated|expired
    triggered: bool
    resolution: Optional[str]  # won|lost|invalidated|expired (None if unresolved)
    bars_to_trigger: Optional[int]
    bars_to_resolution: Optional[int]
    pnl_r: float              # realized or marked-to-market, in R units
    mfe_r: float              # max favorable excursion (R)
    mae_r: float              # max adverse excursion (R)


def _dir_sign(direction: str) -> int:
    return 1 if direction == "long" else -1


def resolve_outcome(
    setup: dict, bars: pd.DataFrame, tie_break: str = "stop"
) -> OutcomeResult:
    """Resolve a frozen setup against the bars that follow its issue.

    `setup` needs: direction, entry, entry_type, stop, t1, invalidation_level,
    horizon_bars. `bars` is OHLC indexed by date, already restricted to rows at
    or after the issue date (the continuation). No lookahead beyond what's given.
    """
    d = _dir_sign(setup["direction"])
    entry = float(setup["entry"]); stop = float(setup["stop"])
    t1 = float(setup["t1"]); inval = float(setup.get("invalidation_level", stop))
    entry_type = setup.get("entry_type", "market")
    horizon = int(setup.get("horizon_bars", 60))
    risk = abs(entry - stop) or 1e-9

    triggered = False
    bars_to_trigger = None
    mfe = 0.0; mae = 0.0
    high = bars["high"].to_numpy(float)
    low = bars["low"].to_numpy(float)
    close = bars["close"].to_numpy(float)

    n = min(len(bars), horizon)
    for i in range(n):
        if not triggered:
            if entry_type == "market":
                triggered, bars_to_trigger = True, i
            elif entry_type == "limit":
                if (d > 0 and low[i] <= entry) or (d < 0 and high[i] >= entry):
                    triggered, bars_to_trigger = True, i
            elif entry_type == "stop":
                if (d > 0 and high[i] >= entry) or (d < 0 and low[i] <= entry):
                    triggered, bars_to_trigger = True, i
            if not triggered:
                continue

        # Active: track excursions and check resolution.
        fav = (high[i] - entry) * d if d > 0 else (entry - low[i])
        adv = (entry - low[i]) * d if d > 0 else (high[i] - entry)
        mfe = max(mfe, ((high[i] if d > 0 else low[i]) - entry) * d / risk)
        mae = min_adverse = min(mae, ((low[i] if d > 0 else high[i]) - entry) * d / risk)

        hit_stop = (d > 0 and low[i] <= stop) or (d < 0 and high[i] >= stop)
        hit_t1 = (d > 0 and high[i] >= t1) or (d < 0 and low[i] <= t1)
        hit_inval = (d > 0 and close[i] < inval) or (d < 0 and close[i] > inval)

        if hit_stop and hit_t1:
            if tie_break == "stop":
                return OutcomeResult("lost", True, "lost", bars_to_trigger, i, -1.0, mfe, mae)
            return OutcomeResult("won", True, "won", bars_to_trigger, i,
                                 abs(t1 - entry) / risk, mfe, mae)
        if hit_stop:
            return OutcomeResult("lost", True, "lost", bars_to_trigger, i, -1.0, mfe, mae)
        if hit_t1:
            return OutcomeResult("won", True, "won", bars_to_trigger, i,
                                 abs(t1 - entry) / risk, mfe, mae)
        if hit_inval:
            pnl = (close[i] - entry) * d / risk
            return OutcomeResult("invalidated", True, "invalidated", bars_to_trigger, i,
                                 round(pnl, 3), mfe, mae)

    # No resolution within available/horizon bars.
    if not triggered:
        if len(bars) >= horizon:
            return OutcomeResult("expired", False, "expired", None, None, 0.0, 0.0, 0.0)
        return OutcomeResult("untriggered", False, None, None, None, 0.0, 0.0, 0.0)

    last_close = close[n - 1]
    pnl = (last_close - entry) * d / risk
    if len(bars) >= horizon:
        return OutcomeResult("expired", True, "expired", bars_to_trigger, n - 1,
                             round(pnl, 3), mfe, mae)
    return OutcomeResult("active", True, None, bars_to_trigger, None, round(pnl, 3), mfe, mae)
