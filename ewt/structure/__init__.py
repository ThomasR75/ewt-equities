"""Structure layer: motive-wave patterns and their classification (spec §4)."""

from .pattern import WavePattern
from .count import classify, build_count

__all__ = ["WavePattern", "classify", "build_count"]
