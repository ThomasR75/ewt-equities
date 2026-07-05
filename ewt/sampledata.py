"""Deterministic synthetic daily OHLCV for M1 development/demo.

Builds ~9 years of business-day bars whose log-price follows an imposed
multi-degree wave skeleton (a 5-wave Cycle advance, then an A-B-C correction)
plus seeded noise, so pivots are meaningful on daily, weekly and monthly. This
is a stand-in until a real CSV is provided; the engine treats it like any input.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _wave_path(n: int, seed: int = 7) -> np.ndarray:
    """Piecewise log-drift skeleton + AR(1) noise -> log price of length n."""
    rng = np.random.default_rng(seed)
    # (fraction_of_series, total_log_move) for each leg of a 5-up + ABC-down count.
    legs = [
        (0.10, 0.45),   # 1 up
        (0.06, -0.20),  # 2 down
        (0.22, 0.95),   # 3 up (extended)
        (0.06, -0.25),  # 4 down
        (0.14, 0.55),   # 5 up  -> Cycle top
        (0.14, -0.55),  # A down
        (0.08, 0.28),   # B up
        (0.20, -0.70),  # C down
    ]
    drift = np.zeros(n)
    start = 0
    level = np.log(20.0)
    for frac, move in legs:
        span = max(1, int(round(frac * n)))
        end = min(n, start + span)
        drift[start:end] = np.linspace(level, level + move, end - start)
        level += move
        start = end
    if start < n:
        drift[start:] = level

    # AR(1) noise for realistic intraday wiggle.
    noise = np.zeros(n)
    eps = rng.normal(0, 0.012, n)
    for i in range(1, n):
        noise[i] = 0.85 * noise[i - 1] + eps[i]
    return drift + noise


def make_sample(seed: int = 7) -> pd.DataFrame:
    idx = pd.bdate_range("2017-01-02", periods=2300)  # ~9 years of weekdays
    n = len(idx)
    logp = _wave_path(n, seed)
    close = np.exp(logp)
    rng = np.random.default_rng(seed + 1)
    intrabar = close * rng.uniform(0.004, 0.018, n)
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) + intrabar
    low = np.minimum(open_, close) - intrabar
    low = np.maximum(low, 0.01)
    volume = (rng.uniform(0.5, 1.5, n) * 1_000_000).round()
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    ).rename_axis("date")


def write_sample(path: str | Path = "data/SAMPLE_daily.csv", seed: int = 7) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    make_sample(seed).to_csv(path)
    return path
