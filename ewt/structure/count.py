"""Classify a WavePattern into a motive structure and build a Count.

M2 covers the motive family: impulse and diagonal (leading/ending). Corrective
structures (zigzag/flat/triangle) arrive in M3. Classification is driven purely
by the cardinal results (spec §7):

  impulse           R1 & R2 & R3 (no overlap)
  diagonal          R1 & R2, but W1 territory overlapped (R3 fails)
                    -> ending vs leading distinguished by shape (contracting +
                       relative leg sizes); without higher-degree context we
                       default to 'ending_diag' for a contracting wedge,
                       'leading_diag' for an expanding one.
  (rejected)        R1 or R2 fails -> not a legal motive wave
"""

from __future__ import annotations

from typing import Optional

from ..schemas import Count, RuleReport
from ..rules.cardinal import check_cardinal, diagonal_valid, impulse_valid
from ..rules.guidelines import score_guidelines
from ..score_config import active as _active_score
from .pattern import WavePattern


def _is_contracting(legs) -> bool:
    """Wedge test: W3<W1 and W5<W3 (on log) => contracting diagonal."""
    w = [leg.mag_log for leg in legs]
    return w[2] < w[0] and w[4] < w[2]


def classify(wp: WavePattern, scale: str = "auto") -> Optional[str]:
    card = check_cardinal(wp.legs, scale)
    if impulse_valid(card):
        return "impulse"
    if diagonal_valid(card):
        return "ending_diag" if _is_contracting(wp.legs) else "leading_diag"
    return None


def build_count(
    wp: WavePattern,
    tf: str,
    scale: str = "auto",
    degree: str = "?",
    volumes: list[float] | None = None,
) -> Optional[Count]:
    structure = classify(wp, scale)
    if structure is None:
        return None

    card = check_cardinal(wp.legs, scale)
    combined, guide = score_guidelines(wp.legs, scale, volumes)

    # A diagonal is a slightly weaker motive read than a clean impulse.
    if structure != "impulse":
        combined *= _active_score().diagonal_penalty

    rr = RuleReport(
        cardinal_pass=True,
        cardinal_detail={k: bool(v.passed) for k, v in card.items()},
        guideline_scores={k: float(v.score) for k, v in guide.items()},
        scale_used={"cardinal": card["w2_retrace"].scale, "guideline": list(guide.values())[0].scale},
    )
    return Count(
        tf=tf,
        structure=structure,
        degree=degree,
        legs=wp.legs,
        labels=["0", "1", "2", "3", "4", "5"],
        score=round(combined, 4),
        rule_report=rr,
    )


# --- M3: corrective counts -------------------------------------------------

from ..rules.corrective import analyze_corrective  # noqa: E402

_CORR_LABELS = {4: ["0", "A", "B", "C"], 6: ["0", "A", "B", "C", "D", "E"]}


def _corr_structure_name(fit) -> str:
    if fit.structure == "flat" and fit.subtype in ("expanded", "running"):
        return f"{fit.subtype}_flat"
    if fit.structure == "triangle":
        return f"{fit.subtype}_triangle"
    return fit.structure


def build_corrective_count(pivots, tf: str, scale: str = "auto", degree: str = "?"):
    """Build a Count from 4 (A-B-C) or 6 (A-B-C-D-E) alternating pivots."""
    from ..schemas import Count, Leg, RuleReport
    n = len(pivots)
    if n not in _CORR_LABELS:
        return None
    legs = [Leg(a, b) for a, b in zip(pivots, pivots[1:])]
    fit = analyze_corrective(legs, scale)
    if fit is None or fit.score <= 0:
        return None
    rr = RuleReport(
        cardinal_pass=True,
        cardinal_detail={"corrective": True},
        guideline_scores={"fit": float(fit.score)},
        scale_used={"corrective": "log" if "[log]" in fit.detail else "lin",
                    "subtype": fit.subtype},
    )
    return Count(
        tf=tf,
        structure=_corr_structure_name(fit),
        degree=degree,
        legs=legs,
        labels=_CORR_LABELS[n],
        score=float(fit.score),
        rule_report=rr,
    )
