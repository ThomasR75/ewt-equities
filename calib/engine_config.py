"""Engine selection for the equity dashboard.

Two interchangeable reads of the same names, chosen at fit time and switchable
live in the dashboard:

  gbt_log  — fixed-percentage (log) pivots + the GBT-trained scenario weigher.
             The canonical/default engine (needs joblib + lightgbm to FIT).
  atr_det  — ATR (volatility-proportional) pivots + the deterministic weigher.
             Volatility-normalised structure detection; needs NO ML deps.

Each state is fit into calib/states/<engine>.pkl. The wave engine is otherwise
identical; only pivot sensitivity and the weigher differ.
"""
from __future__ import annotations

ENGINES = {
    "gbt_log": {"label": "GBT · log pivots", "pivot_mode": "log",
                "pivot_scale": 1.0, "atr_k": None, "weigher": "gbt"},
    "atr_det": {"label": "Deterministic · ATR pivots", "pivot_mode": "atr",
                "pivot_scale": 1.0, "atr_k": 4.0, "weigher": "deterministic"},
}
DEFAULT_ENGINE = "gbt_log"


def get(name: str) -> dict:
    return ENGINES.get(name, ENGINES[DEFAULT_ENGINE])


def names() -> list[str]:
    return list(ENGINES)
