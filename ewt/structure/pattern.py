"""WavePattern — a 6-pivot / 5-leg motive-wave hypothesis.

The atomic unit the rules and classifier see. Built from a strictly increasing,
alternating run of pivots taken from a PivotSeries by the enumerator (spec §4).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas import Leg, Pivot


@dataclass
class WavePattern:
    pivots: list[Pivot]  # exactly 6: P0..P5

    def __post_init__(self) -> None:
        if len(self.pivots) != 6:
            raise ValueError("WavePattern needs exactly 6 pivots (5 waves)")
        for a, b in zip(self.pivots, self.pivots[1:]):
            if a.kind == b.kind:
                raise ValueError("WavePattern pivots must alternate H/L")

    @property
    def legs(self) -> list[Leg]:
        return [Leg(a, b) for a, b in zip(self.pivots, self.pivots[1:])]

    @property
    def direction(self) -> int:
        """+1 bullish (W1 up), -1 bearish."""
        return self.legs[0].dir

    @property
    def start_idx(self) -> int:
        return self.pivots[0].idx

    @property
    def end_idx(self) -> int:
        return self.pivots[-1].idx

    @property
    def span_bars(self) -> int:
        return self.end_idx - self.start_idx

    def label_map(self, motive: bool = True) -> dict[str, Pivot]:
        names = ["0", "1", "2", "3", "4", "5"]
        return dict(zip(names, self.pivots))
