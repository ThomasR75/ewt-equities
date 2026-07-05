"""CSV -> Bars(daily): load, validate, clamp to as_of, add log columns.

Accepts a standard OHLCV CSV (or a DataFrame). Column names are matched
case-insensitively and a few common aliases are accepted (e.g. 'Adj Close',
'date'/'timestamp'). If a DataFrame carries the date in its index, that is
surfaced automatically.

The as_of clamp here is the first and most important line of defense for the
no-lookahead invariant: nothing with timestamp > as_of ever enters a `Bars`.
"""

from __future__ import annotations

import hashlib
from typing import Optional

import numpy as np
import pandas as pd

from ..schemas import Bars, OHLCV

_ALIASES = {
    "date": ["date", "datetime", "timestamp", "time"],
    "open": ["open", "o"],
    "high": ["high", "h"],
    "low": ["low", "l"],
    "close": ["close", "c", "adj close", "adj_close", "adjclose", "close*"],
    "volume": ["volume", "vol", "v"],
}


def _resolve_columns(df: pd.DataFrame) -> dict[str, str]:
    lower = {str(c).strip().lower(): c for c in df.columns}
    out: dict[str, str] = {}
    for canon, aliases in _ALIASES.items():
        for a in aliases:
            if a in lower:
                out[canon] = lower[a]
                break
    required = ["date", "open", "high", "low", "close"]
    missing = [c for c in required if c not in out]
    if missing:
        raise ValueError(
            f"CSV missing required column(s) {missing}. "
            f"Found columns: {list(df.columns)}"
        )
    return out


def _add_log_columns(df: pd.DataFrame) -> pd.DataFrame:
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("Non-positive price found; log scale is undefined.")
    for c in ["open", "high", "low", "close"]:
        df[f"log_{c}"] = np.log(df[c].astype(float))
    return df


def data_hash(df: pd.DataFrame) -> str:
    """Stable sha256 of the exact OHLCV bars used (spec §5.1 data_hash)."""
    canon = df[OHLCV].copy()
    canon.index = df.index.strftime("%Y-%m-%d")
    payload = canon.round(8).to_csv().encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_daily(
    path_or_df,
    as_of: Optional[str | pd.Timestamp] = None,
    *,
    is_partial: bool = False,
) -> Bars:
    """Load a daily OHLCV CSV (or DataFrame) into a clamped `Bars`."""
    if isinstance(path_or_df, pd.DataFrame):
        raw = path_or_df.copy()
        # If the date lives in a (named/Datetime) index, surface it as a column.
        if isinstance(raw.index, pd.DatetimeIndex) or (
            raw.index.name and not isinstance(raw.index, pd.RangeIndex)
        ):
            raw = raw.reset_index()
    else:
        raw = pd.read_csv(path_or_df)

    cols = _resolve_columns(raw)
    df = pd.DataFrame(
        {
            "open": raw[cols["open"]].astype(float),
            "high": raw[cols["high"]].astype(float),
            "low": raw[cols["low"]].astype(float),
            "close": raw[cols["close"]].astype(float),
        }
    )
    df["volume"] = raw[cols["volume"]].astype(float) if "volume" in cols else 0.0
    df.index = pd.to_datetime(raw[cols["date"]])
    df.index.name = "date"
    df = df[~df.index.duplicated(keep="last")].sort_index()

    # --- the no-lookahead clamp ---------------------------------------------
    as_of_ts = pd.Timestamp(as_of) if as_of is not None else df.index.max()
    df = df.loc[df.index <= as_of_ts]
    if df.empty:
        raise ValueError(f"No bars on/before as_of={as_of_ts.date()}.")

    df = _add_log_columns(df)
    # Re-clamp as_of to the last *actual* bar (a non-trading as_of date is fine).
    return Bars(tf="D", df=df, as_of=df.index.max(), is_partial=is_partial)
