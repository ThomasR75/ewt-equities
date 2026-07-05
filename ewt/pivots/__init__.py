"""Pivot layer: atomic swing detection and the PivotSeries container.

M1 ships a configurable zigzag detector with two thresholding modes — a
log-percentage reversal and an ATR-scaled reversal — so the §19 'spike both'
comparison can be run before committing to one. All swing sizes are measured in
log units (spec principle 2) so prominence is comparable across price decades.
"""

from .detect import detect_zigzag, DetectConfig
from .series import build_pivots, TF_PRESETS

__all__ = ["detect_zigzag", "DetectConfig", "build_pivots", "TF_PRESETS"]
