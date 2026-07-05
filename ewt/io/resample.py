"""Daily Bars -> Weekly / Monthly Bars.

Derived bars are built ONLY from daily bars <= as_of (spec §15.3). The final
weekly/monthly bucket is usually still forming at as_of, so it is marked
`is_partial`: it aggregates whatever daily bars exist so far in that period and
nothing from the future.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..schemas import Bars, TF

# Period anchors: weekly buckets end Friday; monthly buckets end month-end.
_RULE = {"W": "W-FRI", "M": "ME"}

_AGG = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
}


def _is_period_partial(daily_index: pd.DatetimeIndex, tf: TF, as_of: pd.Timestamp) -> bool:
    """True if the bucket containing as_of has not closed yet.

    We can only know this from the daily data itself (no calendar lookahead):
    the last bucket is 'partial' unless as_of lands exactly on the period
    boundary (Friday for W, month-end for M). Treating it as partial when in
    doubt is the safe choice — it never invents future data.
    """
    if tf == "W":
        return as_of.weekday() != 4  # 4 = Friday
    if tf == "M":
        return as_of != (as_of + pd.offsets.MonthEnd(0))
    return False


def resample(daily: Bars, tf: TF) -> Bars:
    if daily.tf != "D":
        raise ValueError("resample expects daily Bars as input.")
    if tf not in _RULE:
        raise ValueError(f"Unsupported timeframe: {tf}")

    src = daily.df[["open", "high", "low", "close", "volume"]]
    agg = src.resample(_RULE[tf], label="right", closed="right").agg(_AGG)
    agg = agg.dropna(subset=["open", "high", "low", "close"])

    # Recompute log columns from the aggregated OHLC (not by summing logs).
    for c in ["open", "high", "low", "close"]:
        agg[f"log_{c}"] = np.log(agg[c].astype(float))

    # Clamp: a resample bucket's label can sit *after* as_of (e.g. a Friday
    # label for a Wednesday as_of). Pin the label of the final, still-forming
    # bucket back to as_of so the Bars invariant (no index > as_of) holds and
    # the period is correctly flagged partial.
    is_partial = _is_period_partial(daily.df.index, tf, daily.as_of)
    if len(agg) and agg.index[-1] > daily.as_of:
        agg = agg.rename(index={agg.index[-1]: daily.as_of})

    return Bars(tf=tf, df=agg, as_of=daily.as_of, is_partial=is_partial)


def build_all(daily: Bars) -> dict[TF, Bars]:
    """Convenience: the three nested timeframes from one daily file."""
    return {"D": daily, "W": resample(daily, "W"), "M": resample(daily, "M")}
