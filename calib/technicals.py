"""Historic technical measures for the calibration dashboard.

Pure functions of a stock's close series (point-in-time; only bars <= as_of are
passed in). Everything here is descriptive context shown/sortable in the table;
none of it feeds the wave engine or the setup gate.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

MA_WINDOWS = (20, 50, 100, 200)
Z_WINDOWS = (20, 50, 100)


def _rsi(close: pd.Series, n: int = 14) -> float:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    val = 100 - 100 / (1 + rs)
    v = val.iloc[-1]
    return None if pd.isna(v) else round(float(v), 1)


def compute_technicals(close: pd.Series) -> dict:
    close = pd.Series(close).astype(float).reset_index(drop=True)
    c = float(close.iloc[-1])
    out = {"last": round(c, 4), "ma": {}, "z": {}}

    for w in MA_WINDOWS:
        if len(close) >= w:
            sma = float(close.iloc[-w:].mean())
            out["ma"][str(w)] = {
                "sma": round(sma, 4),
                "dist_pct": round((c / sma - 1) * 100, 2),   # +above / -below
                "above": bool(c >= sma),
            }
        else:
            out["ma"][str(w)] = None

    for w in Z_WINDOWS:
        if len(close) >= w:
            seg = close.iloc[-w:]
            mu, sd = float(seg.mean()), float(seg.std(ddof=0))
            out["z"][str(w)] = round((c - mu) / sd, 2) if sd > 0 else 0.0
        else:
            out["z"][str(w)] = None

    # 52-week (252 bar) range position 0..1
    win = close.iloc[-252:] if len(close) >= 30 else close
    lo, hi = float(win.min()), float(win.max())
    out["pos52"] = round((c - lo) / (hi - lo), 3) if hi > lo else None

    # RSI(14)
    out["rsi14"] = _rsi(close, 14)

    # 50d MA slope: % change of the 50d SMA over the last ~1 month
    if len(close) >= 71:
        sma50 = close.rolling(50).mean()
        s_now, s_prev = float(sma50.iloc[-1]), float(sma50.iloc[-21])
        out["slope50"] = round((s_now / s_prev - 1) * 100, 2) if s_prev > 0 else None
    else:
        out["slope50"] = None

    # Realized volatility (annualised %), 20d and 60d
    lr = np.log(close / close.shift(1)).dropna()
    for w, key in ((20, "vol20"), (60, "vol60")):
        out[key] = round(float(lr.iloc[-w:].std(ddof=0)) * (252 ** 0.5) * 100, 1) if len(lr) >= w else None

    return out
