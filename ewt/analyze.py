"""M2 single-degree analysis pipeline: pivots -> sweep -> lead count -> levels.

Ties the M2 layers together for one timeframe. Returns the ranked counts and the
fib levels / confluence zones of the lead count. Higher milestones add degree
nesting (M4) and the signal layer (M5); the seams are deliberately clean.
"""

from __future__ import annotations

from dataclasses import dataclass

from .schemas import Bars, Count, FibLevel, PivotSeries
from .pivots.series import build_pivots
from .enumerate.sweep import sweep_all, SweepConfig
from .levels.fibonacci import fib_levels
from .levels.confluence import cluster, ConfluenceZone


@dataclass
class DegreeAnalysis:
    tf: str
    bars: Bars
    pivots: PivotSeries
    counts: list[Count]
    lead: Count | None
    levels: list[FibLevel]
    zones: list[ConfluenceZone]


def analyze_degree(bars: Bars, sweep_cfg: SweepConfig | None = None,
                   pivot_scale: float = 1.0, pivot_mode: str = "log",
                   atr_k: float | None = None) -> DegreeAnalysis:
    pivots = build_pivots(bars, pivot_scale=pivot_scale, pivot_mode=pivot_mode, atr_k=atr_k)
    counts = sweep_all(bars, pivots, sweep_cfg)
    lead = counts[0] if counts else None
    levels = fib_levels(lead) if lead else []
    zones = cluster(levels) if levels else []
    return DegreeAnalysis(
        tf=bars.tf,
        bars=bars,
        pivots=pivots,
        counts=counts,
        lead=lead,
        levels=levels,
        zones=zones,
    )


# --- M4: multi-degree nested analysis --------------------------------------

def analyze_nested(daily_bars, sweep_cfg=None, pivot_scale: float = 1.0,
                   pivot_mode: str = "log", atr_k: float | None = None):
    """Analyze all three timeframes and reconcile into a nested read (spec §9).

    Sensitivity switch: pivot_mode="log" (percentage) or "atr" (structural,
    volatility-proportional). See build_pivots.
    Returns (analyses: dict[tf->DegreeAnalysis], NestedRead | None).
    """
    from .io.resample import build_all
    from .degree.nesting import reconcile

    tf_bars = build_all(daily_bars)
    analyses = {tf: analyze_degree(b, sweep_cfg, pivot_scale=pivot_scale,
                                   pivot_mode=pivot_mode, atr_k=atr_k)
                for tf, b in tf_bars.items()}
    nested = reconcile(analyses)
    return analyses, nested
