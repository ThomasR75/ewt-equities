"""Cardinal-rule and classification tests on hand-built textbook patterns."""

from __future__ import annotations

import math

import pandas as pd

from ewt.schemas import Pivot
from ewt.structure.pattern import WavePattern
from ewt.structure.count import classify, build_count


def mk(idx: int, price: float, kind: str) -> Pivot:
    return Pivot(
        idx=idx,
        ts=pd.Timestamp("2020-01-01") + pd.Timedelta(days=idx),
        price=price,
        log_price=math.log(price),
        kind=kind,
    )


def wp(prices, kinds):
    return WavePattern([mk(i * 2, p, k) for i, (p, k) in enumerate(zip(prices, kinds))])


BULL_KINDS = ["L", "H", "L", "H", "L", "H"]


def test_textbook_impulse():
    # W1=20 W2=10 W3=50(longest) W4=20 W5=35 ; W4(140)>W1(120) no overlap
    p = wp([100, 120, 110, 160, 140, 175], BULL_KINDS)
    assert classify(p) == "impulse"
    c = build_count(p, "D")
    assert c is not None and c.rule_report.cardinal_pass
    assert c.score > 0.3


def test_w3_shortest_rejected():
    # W1=30 W3=10 W5=20 -> W3 strictly shortest -> illegal motive wave
    p = wp([100, 130, 115, 125, 120, 140], BULL_KINDS)
    assert classify(p) is None
    assert build_count(p, "D") is None


def test_w2_over_100pct_rejected():
    # W2 retraces below W1 start (108<100? here make P2 < P0) -> R1 fail
    p = wp([100, 120, 98, 150, 130, 165], BULL_KINDS)
    assert classify(p) is None


def test_overlap_is_diagonal():
    # P4(116) < P1(120) -> W1 territory overlapped -> diagonal, not impulse
    p = wp([100, 120, 108, 130, 116, 134], BULL_KINDS)
    assert classify(p) in ("leading_diag", "ending_diag")
    assert classify(p) != "impulse"


def test_bearish_impulse_mirror():
    # Same shape, inverted: starts at a High, motive down.
    prices = [200, 180, 190, 140, 160, 125]
    kinds = ["H", "L", "H", "L", "H", "L"]
    p = wp(prices, kinds)
    assert classify(p) == "impulse"
    assert build_count(p, "D").legs[0].dir == -1


if __name__ == "__main__":
    for fn in [
        test_textbook_impulse,
        test_w3_shortest_rejected,
        test_w2_over_100pct_rejected,
        test_overlap_is_diagonal,
        test_bearish_impulse_mirror,
    ]:
        fn()
    print("OK: rule + classification tests pass")
