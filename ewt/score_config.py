"""Count-scoring configuration — every knob that shapes `Count.score`.

Count.score decides which counts survive beam pruning AND (via the deterministic
weigher / the GBT's fit_score feature) how scenarios get weighted. Two separate
paths feed it:

  motive (impulse/diagonal):
      combined = weighted average of the 7 guideline scores  (w_* below)
      if not impulse: combined *= diagonal_penalty
      score = min(1, combined + span_bonus * span_frac)
      score = score * recency          # exp decay, tau = recency_tau_frac * history

  corrective (zigzag/flat/triangle):
      score = analyze_corrective(...).score        # uses corr_tol
      weight = corr_size_base + corr_size_range * min(1, size_frac / corr_size_sat)
      score = score * weight * recency

Note the guideline weights touch ONLY the motive path — corrective counts are
scored entirely by the corrective fit + size weight + recency.

Defaults reproduce the frozen engine exactly. `set_active()` swaps them for a
fit (calib.precompute --score ...); the dashboard can also re-derive scores
live from cached counts.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict


@dataclass
class ScoreConfig:
    # --- guideline weights (motive counts only) ---
    w_w3_extension: float = 1.0
    w_fib_w2: float = 1.0
    w_fib_w4: float = 1.0
    w_fib_w3: float = 1.2
    w_equality_w5: float = 0.8
    w_alternation: float = 1.0
    w_volume_w3: float = 0.6
    # --- motive modifiers ---
    diagonal_penalty: float = 0.85
    span_bonus: float = 0.05
    recency_tau_frac: float = 0.4
    # --- corrective path ---
    corr_size_base: float = 0.4
    corr_size_range: float = 0.6
    corr_size_sat: float = 0.3
    corr_tol: float = 0.18

    def weights(self) -> dict:
        return {"w3_extension": self.w_w3_extension, "fib_w2": self.w_fib_w2,
                "fib_w4": self.w_fib_w4, "fib_w3": self.w_fib_w3,
                "equality_w5": self.w_equality_w5, "alternation": self.w_alternation,
                "volume_w3": self.w_volume_w3}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "ScoreConfig":
        base = cls()
        for k, v in (d or {}).items():
            if hasattr(base, k) and v is not None:
                try:
                    setattr(base, k, float(v))
                except (TypeError, ValueError):
                    pass
        return base


DEFAULT = ScoreConfig()
_ACTIVE = DEFAULT


def active() -> ScoreConfig:
    return _ACTIVE


def set_active(cfg: ScoreConfig | None) -> None:
    global _ACTIVE
    _ACTIVE = cfg or DEFAULT


# (key, label, min, max, step, group) — drives the dashboard's scoring panel
FACTOR_META = [
    ("w_w3_extension", "W3 extension",        0.0, 3.0, 0.1, "Guideline weights (motive)"),
    ("w_fib_w2",       "Fib W2",              0.0, 3.0, 0.1, "Guideline weights (motive)"),
    ("w_fib_w4",       "Fib W4",              0.0, 3.0, 0.1, "Guideline weights (motive)"),
    ("w_fib_w3",       "Fib W3",              0.0, 3.0, 0.1, "Guideline weights (motive)"),
    ("w_equality_w5",  "Equality W5",         0.0, 3.0, 0.1, "Guideline weights (motive)"),
    ("w_alternation",  "Alternation",         0.0, 3.0, 0.1, "Guideline weights (motive)"),
    ("w_volume_w3",    "Volume W3",           0.0, 3.0, 0.1, "Guideline weights (motive)"),
    ("diagonal_penalty", "Diagonal penalty",  0.5, 1.0, 0.01, "Motive modifiers"),
    ("span_bonus",     "Span bonus",          0.0, 0.3, 0.01, "Motive modifiers"),
    ("recency_tau_frac", "Recency tau (×history)", 0.05, 2.0, 0.05, "Motive & corrective"),
    ("corr_size_base", "Corrective size base", 0.0, 1.0, 0.05, "Corrective path"),
    ("corr_size_range", "Corrective size range", 0.0, 1.0, 0.05, "Corrective path"),
    ("corr_size_sat",  "Corrective size saturation", 0.05, 1.0, 0.05, "Corrective path"),
    ("corr_tol",       "Corrective tolerance", 0.05, 0.5, 0.01, "Corrective path"),
]
