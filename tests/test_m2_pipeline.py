"""M2 pipeline: sweep finds legal counts, is deterministic, and no-lookahead."""

from __future__ import annotations

import pandas as pd

from ewt.io.ingest import load_daily
from ewt.io.resample import resample
from ewt.analyze import analyze_degree
from ewt.sampledata import make_sample


def _counts_fingerprint(da):
    return [
        (c.structure, c.score, tuple(l.start.idx for l in c.legs))
        for c in da.counts
    ]


def test_sweep_finds_legal_motive():
    bars = resample(load_daily(make_sample()), "W")
    da = analyze_degree(bars)
    assert da.lead is not None, "no motive count found on weekly sample"
    assert da.lead.rule_report.cardinal_pass
    assert da.lead.structure in ("impulse", "leading_diag", "ending_diag")
    assert da.levels and da.zones  # fib levels + confluence produced


def test_sweep_deterministic():
    bars = resample(load_daily(make_sample()), "W")
    a = _counts_fingerprint(analyze_degree(bars))
    b = _counts_fingerprint(analyze_degree(bars))
    assert a == b, "sweep is non-deterministic"


def test_sweep_no_lookahead():
    full = make_sample()
    cut = pd.Timestamp("2023-08-16")
    a = _counts_fingerprint(analyze_degree(resample(load_daily(full.loc[full.index <= cut]), "W")))
    b = _counts_fingerprint(analyze_degree(resample(load_daily(full, as_of=cut), "W")))
    assert a == b, "sweep output depends on future bars"


if __name__ == "__main__":
    test_sweep_finds_legal_motive()
    test_sweep_deterministic()
    test_sweep_no_lookahead()
    print("OK: M2 pipeline tests pass")
