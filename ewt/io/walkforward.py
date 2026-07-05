"""Walk-forward as_of iterator (spec §15.4).

Yields a clamped daily `Bars` for each step date so the (separate) tester can
obtain a time-series of historical signals from one CSV. Each yielded `Bars`
is a pure function of rows <= that step's date; there is no shared mutable
state between steps, so a signal at step T cannot be contaminated by step T+1.
"""

from __future__ import annotations

from typing import Iterator, Optional

import pandas as pd

from ..schemas import Bars
from .ingest import load_daily


def iter_as_of(
    path_or_df,
    start: str | pd.Timestamp,
    end: Optional[str | pd.Timestamp] = None,
    step: str = "1D",
    *,
    min_bars: int = 250,
) -> Iterator[Bars]:
    """Iterate clamped daily Bars from `start` to `end` at `step` cadence.

    `step` accepts a pandas offset alias ('1D', '1W', '5D', ...). Steps whose
    clamped history has fewer than `min_bars` daily bars are skipped (an EW read
    on a handful of bars is meaningless).
    """
    full = load_daily(path_or_df)  # unclamped, to know the available range
    idx = full.df.index
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) if end is not None else idx.max()

    # Step over *trading* dates so we never emit an as_of with no new bar.
    # Newer pandas dropped the bare 'M'/'Y'/'Q' offsets in favour of 'ME'/'YE'/'QE';
    # normalize any '<n>M' -> '<n>ME' etc. so '12M' (annual) works everywhere.
    freq = str(step).strip().upper()
    if freq and freq[-1] in ("M", "Y", "Q") and not freq.endswith("E"):
        freq = freq + "E"
    grid = pd.date_range(start_ts, end_ts, freq=freq)
    for g in grid:
        trading = idx[idx <= g]
        if len(trading) < min_bars:
            continue
        as_of = trading.max()
        yield load_daily(full.df, as_of=as_of)
