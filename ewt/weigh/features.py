"""Leak-free, anonymized, RELATIVE features for the weigher (spec §15.3).

Critically: NO ticker, NO absolute dates, NO absolute prices. Only structural
ratios and positions, so an LLM cannot recall what actually happened. This is
what keeps an LLM weigher from cheating via training-data lookahead.
"""

from __future__ import annotations

import math


def candidate_features(count, last_price) -> dict:
    legs = count.legs
    sc = "log"
    mags = [leg.mag(sc) for leg in legs]
    total = sum(mags) or 1e-9
    last = legs[-1]
    # implied next direction (same logic as scenario.implied_next, kept local)
    s = count.structure
    if s in ("impulse", "leading_diag", "ending_diag"):
        nxt = -legs[0].dir
    elif s == "zigzag" or "flat" in s:
        nxt = -legs[0].dir
    elif "triangle" in s:
        nxt = 1 if legs[-1].end.price >= legs[0].start.price else -1
    else:
        nxt = 1 if legs[-1].end.price >= legs[0].start.price else -1
    # where last price sits within the final leg (0=at start pivot, 1=at extreme)
    a, b = last.start.log_price, last.end.log_price
    pos = (math.log(last_price) - a) / (b - a) if b != a else 0.5
    gl = (count.rule_report.guideline_scores if count.rule_report else {}) or {}
    return {
        "structure": s,
        "degree": count.degree,
        "n_legs": len(legs),
        "leg_fractions": [round(m / total, 3) for m in mags],   # relative leg sizes
        "implied_direction": int(nxt),                          # +1 long / -1 short
        "final_leg_frac_of_struct": round(mags[-1] / total, 3),
        "price_pos_in_final_leg": round(pos, 3),
        "fit_score": round(count.score, 3),
        "guideline_scores": {k: round(v, 3) for k, v in gl.items()},
        "scale": (count.rule_report.scale_used if count.rule_report else {}),
    }


# --- flat, fixed-schema features for tabular models (GBT / logistic) ---------

_STRUCTS = ["impulse", "leading_diag", "ending_diag", "zigzag", "flat",
            "expanded_flat", "running_flat", "contracting_triangle", "expanding_triangle"]
_DEGREES = ["Subminuette", "Minute", "Minor", "Intermediate", "Primary", "Cycle", "Supercycle"]
_GLKEYS = ["w3_extension", "fib_w2", "fib_w4", "fib_w3", "equality_w5", "alternation", "volume_w3"]

FLAT_COLUMNS = (["n_legs", "implied_direction", "final_leg_frac", "price_pos", "fit_score", "degree_rank",
                 "min_leg_frac", "leg_frac_cv", "total_span_log", "mean_leg_span_log"]
                + [f"struct_{s}" for s in _STRUCTS] + [f"gl_{k}" for k in _GLKEYS])


def _seg_features(count) -> dict:
    """Segmentation-geometry features that expose over-fine pivot sensitivity.

    All derived from leg magnitudes (log-return) alone, so they're scale-free
    and leak-safe. A too-fine sweep promotes noise wiggles to waves, leaving a
    tell: a tiny runt leg (low min_leg_frac), lopsided sizes (high cv), or a
    whole pattern spanning a trivial move (low total/mean span). These let a
    tabular model down-weight counts born from over-segmentation.
    """
    mags = [leg.mag("log") for leg in count.legs]
    n = len(mags)
    total = sum(mags)
    if n == 0 or total <= 0:
        return {"min_leg_frac": 0.0, "leg_frac_cv": 0.0,
                "total_span_log": 0.0, "mean_leg_span_log": 0.0}
    fracs = [m / total for m in mags]
    mean_f = sum(fracs) / n
    var_f = sum((x - mean_f) ** 2 for x in fracs) / n
    cv = (var_f ** 0.5) / mean_f if mean_f > 0 else 0.0
    return {
        "min_leg_frac": round(min(fracs), 4),
        "leg_frac_cv": round(cv, 4),
        "total_span_log": round(total, 4),
        "mean_leg_span_log": round(total / n, 4),
    }


def flat_features(count, last_price) -> dict:
    """Fixed-schema numeric feature row for a candidate count (for GBT/logistic)."""
    f = candidate_features(count, last_price)
    gl = f.get("guideline_scores", {}) or {}
    row = {
        "n_legs": f["n_legs"],
        "implied_direction": f["implied_direction"],
        "final_leg_frac": f["final_leg_frac_of_struct"],
        "price_pos": f["price_pos_in_final_leg"],
        "fit_score": f["fit_score"],
        "degree_rank": (_DEGREES.index(count.degree) if count.degree in _DEGREES else -1),
    }
    row.update(_seg_features(count))
    for s in _STRUCTS:
        row[f"struct_{s}"] = 1 if count.structure == s else 0
    for k in _GLKEYS:
        row[f"gl_{k}"] = float(gl.get(k, 0.0))
    return row
