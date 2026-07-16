"""Re-derive Count.score from cached score_parts under a new ScoreConfig.

Reproduces the fit-time arithmetic exactly (see ewt/score_config.py) WITHOUT
re-running the sweep, so the dashboard can move the count-scoring knobs live.

Honest limitation: the candidate pool was pruned at fit time using the fit's
ScoreConfig. Re-scoring re-ranks the counts that survived; it cannot resurrect
counts the original beam pruned away. For that, re-fit (calib.precompute --score).
"""
from __future__ import annotations

from ewt import score_config as SC


def rescore_count(c, cfg):
    sp = getattr(c, "score_parts", None) or {}
    if not sp:
        return c
    if sp.get("motive"):
        gl = (c.rule_report.guideline_scores if c.rule_report else {}) or {}
        W = cfg.weights()
        tot = sum(W.values()) or 1e-9
        combined = sum(gl.get(k, 0.0) * W.get(k, 0.0) for k in W) / tot
        if c.structure != "impulse":
            combined *= cfg.diagonal_penalty
        base = round(combined, 4)                                   # build_count
        s = min(1.0, base + cfg.span_bonus * sp.get("span_frac", 0.0))   # sweep_motive
        c.score = round(s * sp.get("recency", 1.0), 4)
    else:
        from ewt.rules.corrective import analyze_corrective
        prev = SC.active(); SC.set_active(cfg)
        try:
            fit = analyze_corrective(c.legs, sp.get("scale", "auto"))
        finally:
            SC.set_active(prev)
        if fit is None or fit.score <= 0:
            c.score = 0.0
        else:
            w = cfg.corr_size_base + cfg.corr_size_range * min(
                1.0, sp.get("size_frac", 0.0) / (cfg.corr_size_sat or 1e-9))
            c.score = round(fit.score * w * sp.get("recency", 1.0), 4)
    return c


def rescore_counts(counts, cfg):
    for c in counts or []:
        rescore_count(c, cfg)
    return counts
