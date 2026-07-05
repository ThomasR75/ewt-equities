"""Cluster nearby Fibonacci levels into confluence zones (spec §4 levels/).

Where several independent fib levels stack within a tight band, that band is a
higher-significance decision zone — the raw material for 'the one level that
matters' and for setup targets in later milestones. Proximity is measured in log
space so the tolerance is scale-consistent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..schemas import FibLevel


@dataclass
class ConfluenceZone:
    lo: float
    hi: float
    members: list[FibLevel] = field(default_factory=list)
    significance: float = 0.0

    @property
    def mid(self) -> float:
        return math.exp((math.log(self.lo) + math.log(self.hi)) / 2)


def cluster(levels: list[FibLevel], tol: float = 0.02) -> list[ConfluenceZone]:
    """Group levels whose prices fall within `tol` (fractional, log) of a band.

    `tol=0.02` ~ a 2% band. Zones are returned strongest-first.
    """
    if not levels:
        return []
    items = sorted([fl for fl in levels if fl.price > 0], key=lambda fl: fl.price)
    if not items:
        return []
    zones: list[ConfluenceZone] = []
    cur = [items[0]]
    for fl in items[1:]:
        if abs(math.log(fl.price) - math.log(cur[-1].price)) <= tol:
            cur.append(fl)
        else:
            zones.append(_make_zone(cur))
            cur = [fl]
    zones.append(_make_zone(cur))
    zones.sort(key=lambda z: (-z.significance, z.mid))
    return zones


def _make_zone(members: list[FibLevel]) -> ConfluenceZone:
    prices = [m.price for m in members]
    # Significance: count, with projections weighted slightly above retraces.
    sig = sum(1.2 if m.kind == "projection" else 1.0 for m in members)
    return ConfluenceZone(lo=min(prices), hi=max(prices), members=members, significance=sig)
