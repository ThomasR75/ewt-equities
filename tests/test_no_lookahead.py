"""The leakage tripwire (spec §15.3).

Core guarantee: a signal as of date T is a pure function of bars <= T. We test
the strongest operational form of that: truncating the input at T and running,
versus handing the full file and clamping with as_of=T, must produce identical
bars, identical pivots, and an identical data_hash on every timeframe.

If any stage ever peeks past as_of, one of these assertions breaks.
"""

from __future__ import annotations

import pandas as pd

from ewt.io.ingest import load_daily, data_hash
from ewt.io.resample import build_all
from ewt.pivots.series import build_all as build_pivots_all
from ewt.sampledata import make_sample


def _fingerprint(daily):
    tf_bars = build_all(daily)
    tf_pivots = build_pivots_all(tf_bars)
    return {
        "hash": {tf: data_hash(b.df) for tf, b in tf_bars.items()},
        "pivots": {
            tf: [(p.idx, p.kind, round(p.price, 6)) for p in ps.pivots]
            for tf, ps in tf_pivots.items()
        },
        "partial": {tf: b.is_partial for tf, b in tf_bars.items()},
    }


def test_truncate_equals_clamp():
    full = make_sample()
    cut = pd.Timestamp("2023-08-16")  # an arbitrary mid-series Wednesday

    # (a) physically truncated input
    truncated = full.loc[full.index <= cut]
    fa = _fingerprint(load_daily(truncated))

    # (b) full input, clamped via as_of
    fb = _fingerprint(load_daily(full, as_of=cut))

    assert fa["hash"] == fb["hash"], "data_hash differs: future bars leaked in"
    assert fa["pivots"] == fb["pivots"], "pivots differ: detection saw the future"
    assert fa["partial"] == fb["partial"], "partial-bar flag differs"


def test_no_bar_after_as_of():
    full = make_sample()
    cut = pd.Timestamp("2022-03-09")
    for tf, b in build_all(load_daily(full, as_of=cut)).items():
        assert b.df.index.max() <= cut, f"{tf} has a bar after as_of"


def test_determinism_repeat():
    full = make_sample()
    a = _fingerprint(load_daily(full, as_of="2024-01-15"))
    b = _fingerprint(load_daily(full, as_of="2024-01-15"))
    assert a == b, "non-deterministic output on identical input"


if __name__ == "__main__":
    test_truncate_equals_clamp()
    test_no_bar_after_as_of()
    test_determinism_repeat()
    print("OK: no-lookahead, clamp, and determinism tests pass")
