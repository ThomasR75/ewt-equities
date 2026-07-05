"""Bounded, beam-pruned generation of k-pivot patterns (spec §8).

A pattern is an increasing, H/L-alternating run of `n_pivots` pivots drawn from
the PivotSeries. Each wave may 'absorb' intermediate pivots, bounded by
`max_advance`. For motive (6-pivot) patterns the cardinal W2 rule is applied
during construction so dead branches never grow. Correctives (4 or 6 pivots) use
the same machine without the motive prune. Survivors are beam-limited each stage
by a cheap partial score. Deterministic throughout.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas import Pivot


@dataclass
class OptionsConfig:
    max_advance: int = 16   # max pivot-positions a boundary may jump
    beam: int = 400         # partial patterns kept per stage
    min_span: int = 0       # min bar span of the full pattern (filter at end)


def _mag_log(pivots: list[Pivot], i: int, j: int) -> float:
    return abs(pivots[j].log_price - pivots[i].log_price)


def _motive_ok(pivots: list[Pivot], seq: list[int]) -> bool:
    """Cardinal W2 < W1 feasibility once two legs exist."""
    if len(seq) >= 3:
        w1 = _mag_log(pivots, seq[0], seq[1])
        w2 = _mag_log(pivots, seq[1], seq[2])
        if not (w2 < w1):
            return False
    return True


def _partial_score(pivots: list[Pivot], seq: list[int]) -> float:
    """Cheap beam bias: prefer real moves; reward an extended 3rd leg."""
    score = 0.0
    if len(seq) >= 2:
        score += _mag_log(pivots, seq[0], seq[1])
    if len(seq) >= 4:
        w1 = _mag_log(pivots, seq[0], seq[1]) or 1e-9
        w3 = _mag_log(pivots, seq[2], seq[3])
        score += min(w3 / w1, 3.0) * 0.5
    return score


def generate_k(
    pivots: list[Pivot],
    direction: int,
    n_pivots: int,
    cfg: OptionsConfig | None = None,
    motive: bool = False,
) -> list[list[int]]:
    cfg = cfg or OptionsConfig()
    n = len(pivots)
    start_kind = "L" if direction > 0 else "H"
    partials: list[list[int]] = [[i] for i, p in enumerate(pivots) if p.kind == start_kind]

    for _stage in range(n_pivots - 1):
        nxt: list[list[int]] = []
        for seq in partials:
            last = seq[-1]
            hi = min(n, last + 1 + cfg.max_advance)
            for j in range(last + 1, hi):
                if pivots[j].kind == pivots[last].kind:
                    continue
                cand = seq + [j]
                if motive and not _motive_ok(pivots, cand):
                    continue
                nxt.append(cand)
        nxt.sort(key=lambda s: (-_partial_score(pivots, s), s))
        partials = nxt[: cfg.beam]

    return [s for s in partials
            if (pivots[s[-1]].idx - pivots[s[0]].idx) >= cfg.min_span]


def generate(pivots: list[Pivot], direction: int, cfg: OptionsConfig | None = None) -> list[list[int]]:
    """Motive (6-pivot) enumeration — back-compatible M2 entrypoint."""
    return generate_k(pivots, direction, 6, cfg, motive=True)
