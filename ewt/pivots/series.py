"""Per-timeframe pivot construction with degree-tuned sensitivity.

Higher timeframes use a coarser reversal threshold so each degree surfaces
swings appropriate to it (spec §9: daily Minor ⊂ weekly Primary ⊂ monthly
Cycle). These presets are M1 starting points; §8/§17 tuning happens later.
"""

from __future__ import annotations

from ..schemas import Bars, PivotSeries, TF
from .detect import DetectConfig, detect_zigzag

# Default reversal sensitivity per timeframe (mode="log", pct = fractional move).
TF_PRESETS: dict[TF, DetectConfig] = {
    "D": DetectConfig(mode="log", pct=0.06),
    "W": DetectConfig(mode="log", pct=0.12),
    "M": DetectConfig(mode="log", pct=0.20),
}

# Structural (ATR-proportional) sensitivity: threshold = ln(1 + atr_k*ATR/close).
# ATR is measured on each timeframe's own bars, so a SINGLE atr_k yields a
# volatility-appropriate, degree-scaled threshold automatically (weekly/monthly
# ATR is larger than daily) — the switch becomes data-determined rather than a
# hand-picked percentage. This is the "structural fit" of the sensitivity knob.
ATR_K_DEFAULT = 4.0


def build_pivots(bars: Bars, cfg: DetectConfig | None = None,
                 pivot_scale: float = 1.0, pivot_mode: str = "log",
                 atr_k: float | None = None, atr_period: int = 14) -> PivotSeries:
    """Detect pivots for one timeframe.

    Two ways to set the swing-sensitivity switch:
      * pivot_mode="log" (default): a fixed percentage reversal per timeframe,
        scaled by `pivot_scale` (<1 more sensitive, >1 coarser).
      * pivot_mode="atr" (structural): the threshold is `atr_k * ATR/close`, so it
        auto-adapts to each instrument's and each degree's volatility. `atr_k`
        (default 4.0) times `pivot_scale` is the single dimensionless coefficient
        — the same value behaves sensibly across quiet and volatile names.

    Either way, tune the switch on a train fold and lock it before the holdout.
    """
    if cfg is None:
        if pivot_mode == "atr":
            k = (atr_k if atr_k is not None else ATR_K_DEFAULT) * pivot_scale
            cfg = DetectConfig(mode="atr", atr_k=k, atr_period=atr_period)
        else:
            base = TF_PRESETS.get(bars.tf, DetectConfig())
            cfg = DetectConfig(mode=base.mode, pct=base.pct * pivot_scale,
                               atr_k=base.atr_k, atr_period=base.atr_period,
                               min_separation=base.min_separation)
    return detect_zigzag(bars, cfg)


def build_all(tf_bars: dict[TF, Bars]) -> dict[TF, PivotSeries]:
    return {tf: build_pivots(b) for tf, b in tf_bars.items()}
