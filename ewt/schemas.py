"""Core data schemas — the contracts between pipeline stages.

These are plain dataclasses (spec §5). Everything carries both arithmetic and
log magnitude so that downstream rules can be scale-aware (spec principle 2),
and every `Bars` knows its `as_of` cutoff so no stage can peek past it
(spec principle 3 / §15.3).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, Optional

import pandas as pd

TF = Literal["D", "W", "M"]
Kind = Literal["H", "L"]
Scale = Literal["lin", "log"]

# Canonical OHLCV column names used throughout the engine.
OHLCV = ["open", "high", "low", "close", "volume"]
LOG_COLS = ["log_open", "log_high", "log_low", "log_close"]


@dataclass
class Bars:
    """A timeframe's worth of bars, clamped to `as_of`.

    Invariant (enforced by io.ingest / io.resample): no row has index > as_of.
    The final bar may be still-forming, in which case `is_partial` is True.
    `df` carries log_* columns alongside the raw OHLCV so legs can be measured
    on either scale without recomputation.
    """

    tf: TF
    df: pd.DataFrame  # index: DatetimeIndex; cols: OHLCV + LOG_COLS
    as_of: pd.Timestamp
    is_partial: bool = False

    def __post_init__(self) -> None:
        missing = [c for c in OHLCV + LOG_COLS if c not in self.df.columns]
        if missing:
            raise ValueError(f"Bars[{self.tf}] missing columns: {missing}")
        if len(self.df) and self.df.index.max() > self.as_of:
            raise ValueError(
                f"Bars[{self.tf}] contains a bar ({self.df.index.max()}) "
                f"after as_of ({self.as_of}) — lookahead violation."
            )

    @property
    def first_bar(self) -> Optional[pd.Timestamp]:
        return self.df.index.min() if len(self.df) else None

    @property
    def last_bar(self) -> Optional[pd.Timestamp]:
        return self.df.index.max() if len(self.df) else None

    @property
    def last_price(self) -> Optional[float]:
        return float(self.df["close"].iloc[-1]) if len(self.df) else None

    def __len__(self) -> int:
        return len(self.df)


@dataclass
class Pivot:
    """A confirmed swing high or low on one timeframe.

    `prominence` is the scale-aware swing size used both to rank pivots for
    beam pruning (spec §8) and to assign wave degree (spec §9). Measured in
    log units so it is comparable across decades of price.
    """

    idx: int  # positional index into the owning Bars.df
    ts: pd.Timestamp
    price: float
    log_price: float
    kind: Kind
    prominence: float = 0.0


@dataclass
class PivotSeries:
    """Strictly alternating H/L pivots for one timeframe."""

    tf: TF
    pivots: list[Pivot] = field(default_factory=list)

    def __post_init__(self) -> None:
        for a, b in zip(self.pivots, self.pivots[1:]):
            if a.kind == b.kind:
                raise ValueError(
                    f"PivotSeries[{self.tf}] not alternating at idx {a.idx}->{b.idx}"
                )

    def __len__(self) -> int:
        return len(self.pivots)

    def legs(self) -> list["Leg"]:
        """Directed moves between consecutive pivots — the unit rules see."""
        return [Leg(start=a, end=b) for a, b in zip(self.pivots, self.pivots[1:])]


@dataclass
class Leg:
    """A directed move between two pivots.

    Carries magnitude on both scales; `retrace_of` / `ext_of` take an explicit
    scale so each rule declares the basis it validates on (spec §7).
    """

    start: Pivot
    end: Pivot

    @property
    def dir(self) -> int:
        return 1 if self.end.price >= self.start.price else -1

    @property
    def mag_lin(self) -> float:
        return abs(self.end.price - self.start.price)

    @property
    def mag_log(self) -> float:
        return abs(self.end.log_price - self.start.log_price)

    @property
    def bars(self) -> int:
        return self.end.idx - self.start.idx

    def mag(self, scale: Scale) -> float:
        return self.mag_log if scale == "log" else self.mag_lin

    def retrace_of(self, other: "Leg", scale: Scale = "log") -> float:
        """This leg's size as a fraction of `other` (e.g. 0.618)."""
        denom = other.mag(scale)
        return self.mag(scale) / denom if denom else math.inf

    def ext_of(self, other: "Leg", scale: Scale = "log") -> float:
        """Alias of retrace_of, named for projection/extension contexts."""
        return self.retrace_of(other, scale)


# --- M2: structure, rules, levels -----------------------------------------

Structure = Literal[
    "impulse", "leading_diag", "ending_diag",
    "zigzag", "flat", "triangle", "combination",
]


@dataclass
class RuleReport:
    cardinal_pass: bool
    cardinal_detail: dict[str, bool] = field(default_factory=dict)
    guideline_scores: dict[str, float] = field(default_factory=dict)
    scale_used: dict[str, str] = field(default_factory=dict)


@dataclass
class Count:
    tf: TF
    structure: str
    degree: str
    legs: list[Leg]
    labels: list[str]
    score: float = 0.0
    rule_report: Optional[RuleReport] = None
    score_parts: dict = field(default_factory=dict)


@dataclass
class FibLevel:
    ratio: float
    kind: Literal["retrace", "projection"]
    scale: Scale
    anchor_legs: list[Leg]
    price: float
    label: str


# --- M5: scenarios & setups ------------------------------------------------

@dataclass
class Scenario:
    rank: int
    path: str
    weight: float                     # 0..1; scenarios sum to 1 incl. residual
    direction: int = 0                # +1 long-implied, -1 short-implied, 0 none
    key_levels: list = field(default_factory=list)
    invalidation: str = ""
    is_residual: bool = False
    primary_count: Optional[Count] = None


@dataclass
class Setup:
    id: str
    grade: Optional[str]              # "A+"|"A"|"B"|None ("not a setup")
    direction: str                   # "long"|"short"
    entry: float
    entry_type: str                  # "limit"|"stop"|"market"
    stop: float
    t1: float
    t2: float
    rr: float
    invalidation_level: float
    invalidation_rule: str
    horizon_bars: int
    issued: str
    status: str = "untriggered"
    frozen: dict = field(default_factory=dict)
