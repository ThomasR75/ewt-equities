"""Truthful catalog of the EWT rule engine, assembled from the LIVE code constants.

Everything here is imported from ewt/rules/* (thresholds, fib bands, weights), so
the descriptions can't drift from what the engine actually computes. Surfaced by
the dashboard's "EWT rules" button via /api/rules.
"""
from __future__ import annotations
import math

from ewt.rules.base import LOG_SPAN_THRESHOLD
from ewt.rules.cardinal import CARDINAL_RULES
from ewt.rules.guidelines import (GUIDELINE_RULES, _WEIGHTS, GUIDELINE_TOL,
                                  FIB_W2, FIB_W4, FIB_W3, EQUALITY_W5, ALTERNATION_SCALE)
from ewt.rules.corrective import (ZIGZAG_MAX_B, CORRECTIVE_TOL, ZZ_B_TARGETS, ZZ_C_TARGETS,
                                  FLAT_REGULAR_MAX, FLAT_REGULAR_B, FLAT_REGULAR_C,
                                  FLAT_RUNNING_B, FLAT_RUNNING_C, FLAT_EXPANDED_B, FLAT_EXPANDED_C,
                                  TRIANGLE_RATIOS)


def _pct(x):
    return f"{x*100:.0f}%"


def build_catalog() -> dict:
    span_pct = round((math.exp(LOG_SPAN_THRESHOLD) - 1) * 100)
    wsum = sum(_WEIGHTS.values())

    cardinal = [
        {"name": "W2 retrace", "id": "w2_retrace", "condition": "W2 < W1",
         "description": "Wave 2 retraces less than 100% of wave 1 — its magnitude is smaller than wave 1's. A hard filter: fail and the count is rejected."},
        {"name": "W3 not shortest", "id": "w3_not_shortest", "condition": "not (W3 < W1 and W3 < W5)",
         "description": "Wave 3 is not the shortest motive leg. It may be shorter than one of W1/W5 — it just cannot be shorter than both."},
        {"name": "W4 overlap", "id": "w4_overlap", "condition": "W3 > W2 + W4",
         "description": "Wave 4 does not overlap wave 1's price territory. Reported, not used to reject outright — this is the rule that separates an impulse (no overlap) from a diagonal (overlap allowed)."},
    ]

    corrective = [
        {"name": "ABC alternation (precondition)", "condition": "B.dir != A.dir and C.dir == A.dir",
         "description": "Any 3-leg correction must strictly alternate (B opposite A, C same as A: down-up-down or up-down-up), otherwise it is not analysed as a correction."},
        {"name": "Zigzag", "condition": f"B/A < {ZIGZAG_MAX_B}",
         "description": f"Sharp A-B-C where wave B retraces less than {_pct(ZIGZAG_MAX_B)} of A. Fit rewards B/A near {ZZ_B_TARGETS} and C/A near {ZZ_C_TARGETS} (tolerance {CORRECTIVE_TOL}); ×1.15 (capped at 1.0) if C makes a new extreme beyond A's end."},
        {"name": "Flat family", "condition": f"B/A >= {ZIGZAG_MAX_B}",
         "description": (f"Sideways A-B-C (deep wave B). Subtypes: regular — B/A and C/A ≤ {FLAT_REGULAR_MAX} "
                         f"(targets B{FLAT_REGULAR_B}, C{FLAT_REGULAR_C}); running — B/A > 1 and C does not exceed A's extreme "
                         f"(targets B{FLAT_RUNNING_B}, C{FLAT_RUNNING_C}); expanded — otherwise "
                         f"(targets B{FLAT_EXPANDED_B}, C{FLAT_EXPANDED_C}).")},
        {"name": "Triangle — contracting", "condition": "C < A and E < C and D < B",
         "description": f"Five legs A-B-C-D-E; each same-direction leg smaller than the last, lines converge. Fit = geometric mean of successive same-direction leg ratios near {TRIANGLE_RATIOS}."},
        {"name": "Triangle — expanding", "condition": "C > A and E > C and D > B",
         "description": f"Five legs A-B-C-D-E; each same-direction leg larger, lines diverge. Same scoring against {TRIANGLE_RATIOS}."},
    ]

    def g(gid, targets_desc):
        w = _WEIGHTS[gid]
        return {"name": gid, "id": gid, "weight": round(w, 3), "weight_pct": round(100 * w / wsum, 1),
                "description": targets_desc}

    guidelines = [
        g("w3_extension", "1.0 if wave 3 is the longest of W1/W3/W5, else W3 / longest."),
        g("fib_w2", f"W2/W1 close to {FIB_W2}."),
        g("fib_w4", f"W4/W3 close to {FIB_W4}."),
        g("fib_w3", f"W3/W1 close to {FIB_W3}."),
        g("equality_w5", f"W5/W1 close to {EQUALITY_W5} (wave 5 equals, or is 0.618 of, wave 1)."),
        g("alternation", f"min(1, |W2/W1 − W4/W3| / {ALTERNATION_SCALE}) — rewards waves 2 and 4 differing in depth."),
        g("volume_w3", "1.0 if volume peaks in wave 3 (needs 5 volume values), else 0.4; 0.5 (neutral) when volume is unavailable."),
    ]

    return {
        "scale_note": (f"Every magnitude is measured on a resolved scale: log when a pattern's total "
                       f"log-span ≥ {LOG_SPAN_THRESHOLD:.2f} (≈ a {span_pct}% / ~2× move), arithmetic otherwise."),
        "cardinal": cardinal,
        "cardinal_note": "Cardinal rules are hard filters — a single failure kills the count.",
        "corrective": corrective,
        "guidelines": guidelines,
        "guideline_note": (f"Guidelines are soft 0–1 scores (Gaussian closeness, tolerance {GUIDELINE_TOL}); "
                           f"none can reject a count. Count.score = weighted average of the {len(GUIDELINE_RULES)} "
                           f"scores (weights shown), which drives scenario weighting and beam pruning."),
        "classification": [
            {"name": "Impulse", "condition": "all three cardinal rules pass"},
            {"name": "Diagonal", "condition": "W2-retrace and W3-not-shortest pass, but W4 overlaps (W3 ≤ W2 + W4)"},
        ],
    }
