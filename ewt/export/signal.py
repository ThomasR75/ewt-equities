"""Build the frozen SignalRecord from a nested analysis (spec §5.1/§15).

Pure function of bars <= as_of. `generated_at` is recorded for humans but never
enters logic, so two runs on identical input + engine_version produce identical
records (minus that timestamp) — the determinism contract (spec §15.5).
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from .. import __version__
from ..io.ingest import data_hash
from ..signal.scenario import build_scenarios
from ..signal.setup import build_setup
from ..signal.grade import grade_setup
from .schema import SCHEMA_VERSION, SignalRecord


def _count_audit(count) -> dict:
    pivots = [count.legs[0].start] + [l.end for l in count.legs]
    return {
        "tf": count.tf,
        "structure": count.structure,
        "degree": count.degree,
        "labels": count.labels,
        "score": count.score,
        "scale_used": (count.rule_report.scale_used if count.rule_report else {}),
        "pivots": [{"ts": str(p.ts.date()), "price": round(p.price, 4), "kind": p.kind}
                   for p in pivots],
    }


def _audit_nested_counts(nested) -> list:
    if nested is None:
        return []
    pairs = [("M", nested.monthly), ("W", nested.weekly), ("D", nested.daily)]
    out = []
    for tf, c in pairs:
        c.degree = nested.degrees.get(tf, c.degree)
        out.append(_count_audit(c))
    return out


def build_signal_record(daily_bars, analyses, nested, *, ticker: str, source: str, weigher=None) -> SignalRecord:
    as_of = str(daily_bars.as_of.date())
    da = analyses["D"]                       # trade timeframe
    scenarios = build_scenarios(da.counts, weigher=weigher, last_price=da.bars.last_price)

    # Lead directional scenario (skip residual / non-directional).
    directional = [s for s in scenarios if not s.is_residual and s.direction != 0]
    lead = max(directional, key=lambda s: s.weight, default=None)

    setup = None
    if lead is not None:
        setup = build_setup(lead, da.bars.last_price, as_of, ticker)
        if setup is not None:
            setup = grade_setup(setup, scenarios)

    # Signal/grade: a setup that fails the R/R gate (grade None) is "no setup".
    if setup is not None and setup.grade is not None:
        signal = setup.direction
        grade = setup.grade
    else:
        signal = "none"
        grade = None

    confidence_pct = round((lead.weight * 100) if lead else 0.0, 2)

    # "The one level that matters": strongest confluence midpoint, else lead pivot.
    pivot_level = None
    if da.zones:
        pivot_level = round(da.zones[0].mid, 4)
    elif lead is not None and lead.key_levels:
        pivot_level = lead.key_levels[0]

    rec = SignalRecord({
        "schema_version": SCHEMA_VERSION,
        "engine_version": __version__,
        "weigher": getattr(weigher, "name", "deterministic"),
        "generated_at": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "data": {
            "ticker": ticker,
            "source": source,
            "data_hash": data_hash(daily_bars.df),
            "timeframe_base": "D",
            "as_of": as_of,
            "as_of_is_partial": bool(daily_bars.is_partial),
            "first_bar": str(daily_bars.first_bar.date()),
            "bar_count": len(daily_bars),
            "last_price": round(daily_bars.last_price, 4),
        },
        "signal": signal,
        "grade": grade,
        "confidence_pct": confidence_pct,
        "setup": None if setup is None else {
            "id": setup.id, "direction": setup.direction, "entry": setup.entry,
            "entry_type": setup.entry_type, "stop": setup.stop, "t1": setup.t1,
            "t2": setup.t2, "rr": setup.rr,
            "invalidation_level": setup.invalidation_level,
            "invalidation_rule": setup.invalidation_rule,
            "horizon_bars": setup.horizon_bars, "issued": setup.issued,
            "grade": setup.grade,
        },
        "scenarios": [{
            "rank": s.rank, "path": s.path, "weight": s.weight,
            "direction": s.direction, "key_levels": s.key_levels,
            "invalidation": s.invalidation, "is_residual": s.is_residual,
        } for s in scenarios],
        "pivot_level": pivot_level,
        "nested_read": None if nested is None else {
            "note": nested.note, "alignment": nested.alignment,
            "degrees": nested.degrees, "current_wave": nested.current_wave,
        },
        "counts": _audit_nested_counts(nested),
    })
    return rec


def append_signal_log(rec: SignalRecord, path: str | Path) -> Path:
    """Append one SignalRecord as a line to a per-ticker signals.jsonl."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(rec, separators=(",", ":")) + "\n")
    return path
