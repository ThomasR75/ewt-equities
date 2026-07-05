"""M7: walk-forward stream + determinism / golden-record guards (spec §15.4/§15.5)."""

from __future__ import annotations

import pandas as pd

from ewt.io.ingest import load_daily
from ewt.io.walkforward import iter_as_of
from ewt.analyze import analyze_nested
from ewt.export.signal import build_signal_record
from ewt.export.schema import validate_record, record_hash
from ewt.sampledata import write_sample

CSV = str(write_sample())

# Golden record hash for SAMPLE @ 2025-10-24 (spec §15.5). If a *deliberate*
# logic change moves this, recompute and update — that is the guard working.
GOLDEN_HASH = "df5e0035651b13d98ee402097c6d6932eab34f0751cd62f9e82ffd536ec6e217"
SAMPLE_DATA_HASH = "be6719da27bcb202657605da276619ec20ac56f210f2757b368fd156fd5cb251"


def _rec_at(as_of):
    b = load_daily(CSV, as_of=as_of)
    a, n = analyze_nested(b)
    return build_signal_record(b, a, n, ticker="SAMPLE", source="SAMPLE_daily.csv")


def test_golden_record_stable():
    rec = _rec_at("2025-10-24")
    assert validate_record(rec) == []
    # The synthetic sample's bytes depend on the local numpy build, so only
    # enforce the literal golden when the fixture matches the reference env.
    # Determinism (below) is the environment-independent guarantee.
    if rec["data"]["data_hash"] == SAMPLE_DATA_HASH:
        assert record_hash(rec) == GOLDEN_HASH, "record drifted — recompute golden if intended"


def test_record_hash_deterministic():
    assert record_hash(_rec_at("2024-06-28")) == record_hash(_rec_at("2024-06-28"))


def test_walkforward_equals_pointintime():
    # A walk-forward record at as_of T must equal a single run at T (no leakage).
    steps = list(iter_as_of(CSV, start="2024-03-31", end="2024-12-31", step="1M"))
    assert len(steps) >= 3
    for b in steps:
        a, n = analyze_nested(b)
        wf = build_signal_record(b, a, n, ticker="SAMPLE", source="SAMPLE_daily.csv")
        single = _rec_at(str(b.as_of.date()))
        assert record_hash(wf) == record_hash(single)


def test_walkforward_stream_valid_and_increasing():
    recs = []
    for b in iter_as_of(CSV, start="2024-01-31", end="2025-06-30", step="1M"):
        a, n = analyze_nested(b)
        recs.append(build_signal_record(b, a, n, ticker="SAMPLE", source="x"))
    assert recs and all(validate_record(r) == [] for r in recs)
    dates = [r["data"]["as_of"] for r in recs]
    assert dates == sorted(dates) and len(set(dates)) 