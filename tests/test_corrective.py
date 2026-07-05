"""Corrective classification tests on hand-built textbook structures (M3)."""

from __future__ import annotations

import math
import pandas as pd

from ewt.schemas import Pivot
from ewt.structure.count import build_corrective_count


def mk(idx, price, kind):
    return Pivot(idx=idx, ts=pd.Timestamp("2020-01-01") + pd.Timedelta(days=idx),
                 price=price, log_price=math.log(price), kind=kind)


def pivots(prices, kinds):
    return [mk(i * 3, p, k) for i, (p, k) in enumerate(zip(prices, kinds))]


HLHL = ["H", "L", "H", "L"]


def test_zigzag():
    # A=-40 B=+20(0.5) C=-40(1.0), C extends below A low -> sharp zigzag
    c = build_corrective_count(pivots([200, 160, 180, 140], HLHL), "D")
    assert c is not None and c.structure == "zigzag"


def test_deep_B_is_flat_not_zigzag():
    # B retraces 90% of A -> too deep for a zigzag; must be flat-family
    c = build_corrective_count(pivots([200, 160, 196, 158], HLHL), "D")
    assert c is not None
    assert c.structure != "zigzag"
    assert "flat" in c.structure


def test_expanded_flat():
    # B=+40 (133% of A, beyond A start) C beyond A end -> expanded flat
    c = build_corrective_count(pivots([200, 170, 210, 165], HLHL), "D")
    assert c is not None and c.structure == "expanded_flat"


def test_contracting_triangle():
    c = build_corrective_count(
        pivots([200, 160, 190, 170, 185, 177], ["H", "L", "H", "L", "H", "L"]), "D"
    )
    assert c is not None and c.structure == "contracting_triangle"


def test_corrective_no_lookahead_and_determinism():
    import pandas as pd
    from ewt.io.ingest import load_daily
    from ewt.io.resample import resample
    from ewt.enumerate.sweep import sweep_all
    from ewt.pivots.series import build_pivots
    from ewt.sampledata import make_sample

    def fp(df):
        b = resample(load_daily(df), "W")
        cs = sweep_all(b, build_pivots(b))
        return [(c.structure, c.score, c.legs[0].start.idx) for c in cs]

    full = make_sample()
    cut = pd.Timestamp("2023-08-16")
    assert fp(full.loc[full.index <= cut]) == fp(load_daily(full, as_of=cut).df)
    assert fp(full) == fp(full)  # determinism


if __name__ == "__main__":
    test_zigzag()
    test_deep_B_is_flat_not_zigzag()
    test_expanded_flat()
    test_contracting_triangle()
    test_corrective_no_lookahead_and_determinism()
    print("OK: corrective tests pass")
