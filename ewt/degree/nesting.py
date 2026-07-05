"""Cross-timeframe reconciliation (spec §9).

The three timeframes are resampled from one daily file, so a monthly swing is
also present (more finely) on weekly and daily. Reconciliation picks the
(monthly, weekly, daily) triple of counts whose boundaries corroborate each
other: every higher-degree pivot should be echoed by a pivot in the lower
timeframe's field, and degrees must nest (monthly ≥ weekly ≥ daily).

This is what resolves the single-degree ambiguity from M2/M3 — the monthly
impulse constrains which daily reading is admissible — and yields the
"daily Minor 5 ⊂ weekly Primary [A] ⊂ monthly Cycle II" style read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from ..schemas import Count, Pivot, PivotSeries

# Coarsest -> finest. Index gives a total order for the nesting check.
DEGREE_ORDER = [
    "Supercycle", "Cycle", "Primary", "Intermediate", "Minor", "Minute", "Subminuette",
]

# Lower bound on a count's full log-span for each degree (heuristic; spec §17).
_DEGREE_SPAN = [
    ("Supercycle", 2.3),
    ("Cycle", 1.5),
    ("Primary", 0.95),
    ("Intermediate", 0.55),
    ("Minor", 0.3),
    ("Minute", 0.15),
    ("Subminuette", 0.0),
]


def _count_span_log(count: Count) -> float:
    lps = [count.legs[0].start.log_price] + [l.end.log_price for l in count.legs]
    return max(lps) - min(lps)


def assign_degree(count: Count) -> str:
    span = _count_span_log(count)
    for name, lo in _DEGREE_SPAN:
        if span >= lo:
            return name
    return "Subminuette"


def _count_pivots(count: Count) -> list[Pivot]:
    return [count.legs[0].start] + [l.end for l in count.legs]


def corroboration(
    hi: Count, lo_field: PivotSeries, tol_days: int, price_tol: float = 0.06
) -> float:
    """Fraction of `hi` count pivots echoed by a same-kind pivot in `lo_field`."""
    hp = _count_pivots(hi)
    if not hp:
        return 0.0
    matched = 0
    for p in hp:
        best = None
        for q in lo_field.pivots:
            if q.kind != p.kind:
                continue
            dd = abs((q.ts - p.ts).days)
            if dd <= tol_days and abs(q.price / p.price - 1.0) <= price_tol:
                best = dd if best is None else min(best, dd)
        if best is not None:
            matched += 1
    return matched / len(hp)


def _degree_rank(name: str) -> int:
    return DEGREE_ORDER.index(name) if name in DEGREE_ORDER else len(DEGREE_ORDER)


@dataclass
class NestedRead:
    monthly: Count
    weekly: Count
    daily: Count
    degrees: dict = field(default_factory=dict)        # tf -> degree name
    current_wave: dict = field(default_factory=dict)   # tf -> label of latest leg
    alignment: float = 0.0
    note: str = ""


def _latest_wave_label(count: Count) -> str:
    return count.labels[-1] if count.labels else "?"


def reconcile(
    analyses: dict, top_k: int = 4, mw_tol_days: int = 31, wd_tol_days: int = 12
) -> Optional[NestedRead]:
    """Choose the best-aligned (monthly, weekly, daily) triple.

    `analyses` maps "M"/"W"/"D" -> DegreeAnalysis (has .counts and .pivots).
    Score = corroboration(M->W field) * corroboration(W->D field)
            * mean(count scores) * nesting_ok.
    """
    M, W, D = analyses.get("M"), analyses.get("W"), analyses.get("D")
    if not (M and W and D) or not (M.counts and W.counts and D.counts):
        return None

    best: Optional[NestedRead] = None
    best_score = -1.0
    for mc in M.counts[:top_k]:
        for wc in W.counts[:top_k]:
            cor_mw = corroboration(mc, W.pivots, mw_tol_days)
            for dc in D.counts[:top_k]:
                cor_wd = corroboration(wc, D.pivots, wd_tol_days)
                degs = {"M": assign_degree(mc), "W": assign_degree(wc), "D": assign_degree(dc)}
                # Nesting: monthly degree at least as coarse as weekly >= daily.
                nesting_ok = (
                    _degree_rank(degs["M"]) <= _degree_rank(degs["W"]) <= _degree_rank(degs["D"])
                )
                mean_score = (mc.score + wc.score + dc.score) / 3
                score = cor_mw * cor_wd * mean_score * (1.0 if nesting_ok else 0.25)
                if score > best_score:
                    best_score = score
                    best = NestedRead(
                        monthly=mc, weekly=wc, daily=dc,
                        degrees=degs,
                        current_wave={
                            "M": _latest_wave_label(mc),
                            "W": _latest_wave_label(wc),
                            "D": _latest_wave_label(dc),
                        },
                        alignment=round(score, 4),
                        note=(f"M:{mc.structure}/{degs['M']} wave {_latest_wave_label(mc)} "
                              f"⊃ W:{wc.structure}/{degs['W']} wave {_latest_wave_label(wc)} "
                              f"⊃ D:{dc.structure}/{degs['D']} wave {_latest_wave_label(dc)} "
                              f"(corr M→W {cor_mw:.2f}, W→D {cor_wd:.2f})"),
                    )
    return best
