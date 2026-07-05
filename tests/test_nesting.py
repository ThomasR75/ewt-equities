"""M4 degree-nesting tests."""

from __future__ import annotations

import pandas as pd

from ewt.io.ingest import load_daily
from ewt.analyze import analyze_nested
from ewt.degree.nesting import DEGREE_ORDER
from ewt.sampledata import make_sample


def _rank(d):
    return DEGREE_ORDER.index(d)


def test_nested_read_exists_and_orders():
    _, nested = analyze_nested(load_daily(make_sample()))
    assert nested is not None
    # Degrees must nest: monthly at least as coarse as weekly >= daily.
    assert _rank(nested.degrees["M"]) <= _rank(nested.degrees["W"]) <= _rank(nested.degrees["D"])
    assert nested.alignment > 0


def test_corroboration_full_on_clean_sample():
    # On the clean synthetic, M and W describe the same advance -> strong corr.
    _, nested = analyze_nested(load_daily(make_sample()))
    assert "corr M→W 1.00" in nested.note or "corr M→W 0.8" in nested.note


def test_nesting_deterministic_and_no_lookahead():
    full = make_sample()
    cut = pd.Timestamp("2023-08-16")
    _, a = analyze_nested(load_daily(full.loc[full.index <= cut]))
    _, b = analyze_nested(load_daily(full, as_of=cut))
    assert a.note == b.note and a.alignment == b.alignment
    _, c = analyze_nested(load_daily(full, as_of=cut))
    assert b.note == c.note  # determinism


if __name__ == "__main__":
    test_nested_read_exists_and_orders()
    test_corroboration_full_on_clean_sample()
    test_nesting_deterministic_and_no_lookahead()
    print("OK: nesting tests pass")
