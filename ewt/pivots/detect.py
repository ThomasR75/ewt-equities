"""Zigzag swing detection (log-aware), with percentage and ATR thresholds.

A pivot is confirmed when price reverses from a running extreme by at least the
reversal threshold, measured in *log* units. Two modes:

  * mode="log" : threshold = ln(1 + pct), a scale-free percentage reversal.
  * mode="atr" : threshold = ln(1 + atr_k * ATR / close), volatility-scaled.

The detector is intentionally deterministic and side-effect-free: same bars +
same config => same pivots (spec §15.5). The final, still-forming swing is
emitted as a provisional pivot so charts and the 'active sub-structure' have an
endpoint; it carries the same shape as any other pivot.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from ..schemas import Bars, Pivot, PivotSeries

Mode = Literal["log", "atr"]


@dataclass
class DetectConfig:
    mode: Mode = "log"
    pct: float = 0.08          # used by mode="log" (and as ATR fallback): ~8% reversal
    atr_k: float = 3.0         # used by mode="atr"
    atr_period: int = 14
    min_separation: int = 1    # min bars between consecutive pivots


def _atr(high, low, close, period: int) -> np.ndarray:
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum.reduce(
        [high - low, np.abs(high - prev_close), np.abs(low - prev_close)]
    )
    # Simple rolling mean ATR (deterministic, no seeding ambiguity).
    atr = np.full_like(tr, np.nan, dtype=float)
    if len(tr) >= period:
        c = np.cumsum(np.insert(tr, 0, 0.0))
        atr[period - 1:] = (c[period:] - c[:-period]) / period
    return atr


def _threshold_log(bars: Bars, cfg: DetectConfig) -> np.ndarray:
    """Per-bar reversal threshold, in log units."""
    df = bars.df
    n = len(df)
    base = np.log1p(cfg.pct)
    if cfg.mode == "log":
        return np.full(n, base)
    # ATR mode
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    close = df["close"].to_numpy(float)
    atr = _atr(high, low, close, cfg.atr_period)
    with np.errstate(invalid="ignore"):
        thr = np.log1p(cfg.atr_k * atr / close)
    thr[np.isnan(thr)] = base  # fall back to pct where ATR undefined (early bars)
    return thr


def _prominence(pivots: list[Pivot]) -> None:
    """Assign each pivot the smaller adjacent leg size (log units), in place.

    A loose topographic prominence: how far price had to move on both sides for
    this swing to stand out. Endpoints use their single adjacent leg.
    """
    n = len(pivots)
    for i, p in enumerate(pivots):
        left = abs(p.log_price - pivots[i - 1].log_price) if i > 0 else None
        right = abs(pivots[i + 1].log_price - p.log_price) if i < n - 1 else None
        vals = [v for v in (left, right) if v is not None]
        p.prominence = float(min(vals)) if vals else 0.0


def detect_zigzag(bars: Bars, cfg: DetectConfig | None = None) -> PivotSeries:
    cfg = cfg or DetectConfig()
    df = bars.df
    n = len(df)
    if n < 3:
        return PivotSeries(tf=bars.tf, pivots=[])

    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    lhigh = df["log_high"].to_numpy(float)
    llow = df["log_low"].to_numpy(float)
    ts = df.index
    thr = _threshold_log(bars, cfg)

    raw: list[tuple[int, str]] = []  # (idx, kind) confirmed pivots, in order

    trend = 0          # +1 seeking high, -1 seeking low, 0 unseeded
    ext_idx = 0        # running extreme for the current leg
    hi_i = lo_i = 0    # running high/low while unseeded

    for i in range(1, n):
        if trend == 0:
            if high[i] > high[hi_i]:
                hi_i = i
            if low[i] < low[lo_i]:
                lo_i = i
            up = lhigh[hi_i] - llow[0]   # rise from the opening low
            dn = lhigh[0] - llow[lo_i]   # fall from the opening high
            if up >= thr[0] and up >= dn:
                raw.append((0, "L"))     # bar 0 is a swing low; now seeking a high
                trend, ext_idx = 1, hi_i
            elif dn >= thr[0]:
                raw.append((0, "H"))     # bar 0 is a swing high; now seeking a low
                trend, ext_idx = -1, lo_i
            continue

        if trend == 1:  # seeking a high; ext_idx is the running high
            if high[i] >= high[ext_idx]:
                ext_idx = i
            elif (lhigh[ext_idx] - llow[i]) >= thr[ext_idx] and (i - ext_idx) >= cfg.min_separation:
                raw.append((ext_idx, "H"))
                trend, ext_idx = -1, i
        else:           # trend == -1, seeking a low; ext_idx is the running low
            if low[i] <= low[ext_idx]:
                ext_idx = i
            elif (lhigh[i] - llow[ext_idx]) >= thr[ext_idx] and (i - ext_idx) >= cfg.min_separation:
                raw.append((ext_idx, "L"))
                trend, ext_idx = 1, i

    # Provisional final pivot: the still-forming swing's running extreme.
    if trend != 0:
        kind = "H" if trend == 1 else "L"
        if not raw or ext_idx > raw[-1][0]:
            raw.append((ext_idx, kind))

    pivots: list[Pivot] = []
    for idx, kind in raw:
        price = float(high[idx] if kind == "H" else low[idx])
        log_price = float(lhigh[idx] if kind == "H" else llow[idx])
        pivots.append(
            Pivot(idx=idx, ts=ts[idx], price=price, log_price=log_price, kind=kind)
        )
    _prominence(pivots)
    return PivotSeries(tf=bars.tf, pivots=pivots)
