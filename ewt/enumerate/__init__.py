"""Enumeration: generate candidate motive-wave patterns from a PivotSeries.

Spec §4/§8. The search is a bounded, beam-pruned skip-tuple sweep run in both
directions, with the cardinal W2 rule applied during construction so illegal
branches die early. Deterministic: same pivots + same config => same patterns.
"""

from .sweep import sweep_motive, sweep_corrective, sweep_all, SweepConfig

__all__ = ["sweep_motive", "sweep_corrective", "sweep_all", "SweepConfig"]
