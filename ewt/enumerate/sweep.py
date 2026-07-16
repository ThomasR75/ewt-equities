"""Multi-anchor, bidirectional sweep -> ranked counts (spec §4/§6).

Runs the bounded enumerator for both directions, for motive (6-pivot) and
corrective (4- and 6-pivot) patterns, classifies/scores each, dedups by
pivot-set, and returns the top counts. This is the 'write' layer wrapping the
otherwise one-anchor, up-only, impulse-only upstream search.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas import Bars, Count, PivotSeries
from ..structure.pattern import WavePattern
from ..structure.count import build_count, build_corrective_count
from ..score_config import active as _active_score
from .options import OptionsConfig, generate, generate_k


@dataclass
class SweepConfig:
    options: OptionsConfig = None  # type: ignore[assignment]
    scale: str = "auto"
    top_n: int = 25
    span_bonus: float = 0.05
    include_corrective: bool = True

    def __post_init__(self):
        if self.options is None:
            self.options = OptionsConfig()


def _recency(bars, count) -> float:
    """Prefer structures completing near as_of: a count ending at the last bar
    scores 1.0, older ones decay. This keeps the *active* structure as the lead
    rather than a high-fit but stale historical one (spec §9/§11)."""
    import math
    total = max(1, len(bars) - 1)
    end_idx = count.legs[-1].end.idx
    tau = max(1.0, _active_score().recency_tau_frac * total)
    return math.exp(-(total - end_idx) / tau)


def _wave_volumes(bars: Bars, wp: WavePattern) -> list[float]:
    vols = bars.df["volume"].to_numpy(float)
    out = []
    for leg in wp.legs:
        seg = vols[leg.start.idx : leg.end.idx + 1]
        out.append(float(seg.mean()) if len(seg) else 0.0)
    return out


def sweep_motive(bars: Bars, pivots: PivotSeries, cfg: SweepConfig | None = None) -> list[Count]:
    cfg = cfg or SweepConfig()
    pv = pivots.pivots
    if len(pv) < 6:
        return []
    total_bars = max(1, len(bars) - 1)
    seen: set[tuple[int, ...]] = set()
    counts: list[Count] = []
    for direction in (1, -1):
        for seq in generate(pv, direction, cfg.options):
            key = ("M",) + tuple(pv[i].idx for i in seq)
            if key in seen:
                continue
            seen.add(key)
            wp = WavePattern([pv[i] for i in seq])
            count = build_count(wp, bars.tf, cfg.scale, volumes=_wave_volumes(bars, wp))
            if count is None:
                continue
            span_frac = wp.span_bars / total_bars
            rec = _recency(bars, count)
            count.score = min(1.0, count.score + _active_score().span_bonus * span_frac)
            count.score = round(count.score * rec, 4)
            count.score_parts = {"motive": True, "span_frac": round(span_frac, 6),
                                 "recency": round(rec, 6), "scale": cfg.scale}
            counts.append(count)
    counts.sort(key=lambda c: (-c.score, c.legs[0].start.idx))
    return counts[: cfg.top_n]


def sweep_corrective(bars: Bars, pivots: PivotSeries, cfg: SweepConfig | None = None) -> list[Count]:
    cfg = cfg or SweepConfig()
    pv = pivots.pivots
    counts: list[Count] = []
    seen: set[tuple[int, ...]] = set()
    for n_pivots in (4, 6):
        if len(pv) < n_pivots:
            continue
        for direction in (1, -1):
            for seq in generate_k(pv, direction, n_pivots, cfg.options, motive=False):
                key = ("C",) + tuple(pv[i].idx for i in seq)
                if key in seen:
                    continue
                seen.add(key)
                count = build_corrective_count([pv[i] for i in seq], bars.tf, cfg.scale)
                if count is not None:
                    # Size weighting: a structure that spans a real fraction of
                    # the chart's range is worth more than a textbook-but-tiny one.
                    import numpy as _np
                    lp = bars.df["log_close"].to_numpy(float)
                    data_range = float(lp.max() - lp.min()) or 1e-9
                    pat_lp = [count.legs[0].start.log_price] + [l.end.log_price for l in count.legs]
                    size_frac = (max(pat_lp) - min(pat_lp)) / data_range
                    _sc = _active_score()
                    weight = _sc.corr_size_base + _sc.corr_size_range * min(1.0, size_frac / _sc.corr_size_sat)
                    rec = _recency(bars, count)
                    count.score = round(count.score * weight * rec, 4)
                    count.score_parts = {"motive": False, "size_frac": round(size_frac, 6),
                                         "recency": round(rec, 6), "scale": cfg.scale}
                    counts.append(count)
    counts.sort(key=lambda c: (-c.score, c.legs[0].start.idx))
    return counts[: cfg.top_n]


def sweep_all(bars: Bars, pivots: PivotSeries, cfg: SweepConfig | None = None) -> list[Count]:
    cfg = cfg or SweepConfig()
    counts = sweep_motive(bars, pivots, cfg)
    if cfg.include_corrective:
        counts = counts + sweep_corrective(bars, pivots, cfg)
    counts.sort(key=lambda c: (-c.score, c.legs[0].start.idx))
    return counts[: cfg.top_n]
