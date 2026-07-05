"""Scenario synthesis with a residual bucket (spec §10).

The engine never claims *the* count. It groups the top admissible
interpretations by the move they imply next, weights them by fit score, and
always keeps a residual "no clean structure" bucket that absorbs ambiguity —
so weights sum to 1 and a weak field degrades into low conviction rather than
false confidence.

v1 weigher is deterministic (score-derived). The interface is the documented
swap-in point for a learned/LLM weigher (spec §10), which stays OFF here.
"""

from __future__ import annotations

from ..schemas import Count, Scenario
from ..weigh import DeterministicWeigher, candidate_features, normalize_weights
from ..weigh.features import flat_features


def implied_next(count: Count) -> tuple[int, str]:
    """Direction of the move a completed structure implies next.

    impulse/diagonal complete -> correction against the impulse.
    zigzag/flat complete       -> the larger trend resumes (against the
                                  correction's net direction).
    triangle complete          -> thrust in the triangle's net drift direction.
    """
    legs = count.legs
    s = count.structure
    net_dir = 1 if legs[-1].end.price >= legs[0].start.price else -1
    if s in ("impulse", "leading_diag", "ending_diag"):
        impulse_dir = legs[0].dir
        return -impulse_dir, "post-impulse correction"
    if s in ("zigzag",) or "flat" in s:
        corr_dir = legs[0].dir          # A leg direction
        return -corr_dir, "trend resumes after correction"
    if "triangle" in s:
        return net_dir, "post-triangle thrust"
    return net_dir, "continuation"


def _sharpen(x: float, gamma: float = 1.5) -> float:
    return max(0.0, x) ** gamma


def build_scenarios(counts: list[Count], top_k: int = 6, weigher=None,
                    last_price: float | None = None) -> list[Scenario]:
    """Top distinct interpretations -> weighted scenarios + residual.

    Distinct = best count per implied-next direction (and structure family), so
    we surface genuinely different futures rather than near-duplicates.
    """
    if not counts:
        return [Scenario(rank=1, path="No clean structure", weight=1.0,
                         is_residual=True)]

    # Pick the best count per (direction, family) signature.
    chosen: dict[tuple, Count] = {}
    for c in counts[:top_k * 2]:
        d, _ = implied_next(c)
        fam = "motive" if c.structure in ("impulse", "leading_diag", "ending_diag") else "corrective"
        key = (d, fam)
        if key not in chosen or c.score > chosen[key].score:
            chosen[key] = c
    picks = sorted(chosen.values(), key=lambda c: -c.score)[:top_k]

    # Weigher decides the raw weights (deterministic by default; LLM swap-in).
    weigher = weigher or DeterministicWeigher()
    lp = last_price if last_price is not None else picks[0].legs[-1].end.price
    feats = [{**candidate_features(c, lp), "_flat": flat_features(c, lp)} for c in picks]
    raw = weigher.weigh(feats)
    if not raw or len(raw) != len(picks):
        raw = [max(0.0, c.score) ** 1.5 for c in picks]
    weights, residual_w = normalize_weights(raw, best_fit=picks[0].score)

    scenarios: list[Scenario] = []
    for i, (c, w) in enumerate(zip(picks, weights), start=1):
        d, basis = implied_next(c)
        last = c.legs[-1].end
        scenarios.append(
            Scenario(
                rank=i,
                path=f"{c.structure} (wave {c.labels[-1]} @ {last.price:.2f}) -> {basis}",
                weight=round(w, 4),
                direction=d,
                key_levels=[round(last.price, 4)],
                invalidation=f"{'above' if d < 0 else 'below'} {last.price:.2f} voids this read",
                primary_count=c,
            )
        )
    scenarios.append(
        Scenario(rank=len(scenarios) + 1, path="No clean structure / other",
                 weight=round(residual_w, 4), is_residual=True)
    )
    # Numerical tidy so weights sum to exactly 1.0.
    drift = round(1.0 - sum(s.weight for s in scenarios), 4)
    scenarios[0].weight = round(scenarios[0].weight + drift, 4)
    return scenarios
