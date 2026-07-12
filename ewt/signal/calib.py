"""Calibration configuration for the setup/grade layer.

Every tunable constant that governs how a completed wave count becomes a graded
trade setup lives here, in one dataclass. The defaults reproduce the frozen
v1.2 behaviour exactly (see setup.py / grade.py history), so an un-tuned run is
bit-for-bit the same as before. The calibration platform swaps in a different
CalibConfig to explore how the gate/geometry/grade thresholds move the setups.

Tolerances and risk are expressed here as *percentages* (0.03 = 3%) because
that is how a human reasons about "how much throw-over room"; the setup code
converts them to log space at the point of use.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict, field


@dataclass
class CalibConfig:
    # --- R/R gate + grade thresholds ---------------------------------------
    rr_floor: float = 2.0          # min reward/risk to be a setup at all
    confirm_lead_w: float = 0.50   # lead-scenario weight needed to "confirm" (A)
    opp_alt_w: float = 0.30        # opposing alternate >= this holds a setup to B
    rr_comfort: float = 2.5        # R/R below this holds a setup to B

    # --- entry / stop geometry ---------------------------------------------
    entry_offset: float = 0.02     # enter ~2% off the completion pivot
    stop_extra: float = 0.01       # stop sits this far beyond the invalidation
    min_risk_pct: float = 0.02     # reject setups whose risk leg is under this

    # --- invalidation tolerance (degree-scaled throw-over room) ------------
    tol_k: float = 0.30            # room = this fraction of the final leg's log size
    min_tol_pct: float = 0.03      # ...clamped to at least this (Minor degree)
    max_tol_pct: float = 0.30      # ...and at most this (Cycle/Supercycle degree)

    # --- chase filter + targets --------------------------------------------
    near_max: float = 0.15         # skip if price has run > this past the pivot
    near_tol: float = 0.01         # allow this much past the pivot the "wrong" way
    ext_ratios: tuple = (1.272, 1.618, 2.618)  # fib extension target multiples

    # --- derived log-space helpers (not user-facing) -----------------------
    @property
    def min_risk_log(self) -> float:
        return math.log(1.0 + self.min_risk_pct)

    @property
    def min_tol_log(self) -> float:
        return math.log(1.0 + self.min_tol_pct)

    @property
    def max_tol_log(self) -> float:
        return math.log(1.0 + self.max_tol_pct)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "CalibConfig":
        if not d:
            return cls()
        base = cls()
        for k, v in d.items():
            if not hasattr(base, k) or v is None:
                continue
            if k == "ext_ratios":
                v = tuple(float(x) for x in v)
            else:
                v = float(v)
            setattr(base, k, v)
        return base


DEFAULT = CalibConfig()


# Metadata that drives the UI control panel: label, min, max, step, group.
# (key, label, min, max, step, group)
FACTOR_META = [
    ("rr_floor",       "R/R floor (gate)",           1.0, 5.0,  0.1,  "Gate & grade"),
    ("confirm_lead_w", "Confirm lead weight ≥",  0.20, 0.90, 0.01, "Gate & grade"),
    ("opp_alt_w",      "Opposing alt holds B ≥", 0.10, 0.60, 0.01, "Gate & grade"),
    ("rr_comfort",     "R/R comfort (A) ≥",      1.5, 5.0,  0.1,  "Gate & grade"),
    ("entry_offset",   "Entry offset off pivot",      0.00, 0.10, 0.005, "Entry / stop"),
    ("stop_extra",     "Stop extra beyond invalid",   0.00, 0.05, 0.005, "Entry / stop"),
    ("min_risk_pct",   "Min risk leg",                0.005, 0.10, 0.005, "Entry / stop"),
    ("tol_k",          "Invalidation room (× leg)", 0.05, 1.0,  0.05, "Invalidation"),
    ("min_tol_pct",    "Min invalidation room",       0.01, 0.15, 0.005, "Invalidation"),
    ("max_tol_pct",    "Max invalidation room",       0.05, 0.60, 0.01, "Invalidation"),
    ("near_max",       "Chase filter (max run past)", 0.02, 0.50, 0.01, "Chase / targets"),
]
