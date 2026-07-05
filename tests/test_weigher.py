"""Weigher plumbing: deterministic == default, fake differs, weights sum to 1."""
from __future__ import annotations
from ewt.io.ingest import load_daily
from ewt.analyze import analyze_nested
from ewt.export.signal import build_signal_record
from ewt.export.schema import validate_record
from ewt.weigh.deterministic import DeterministicWeigher
from ewt.weigh.fake import FakeWeigher
from ewt.sampledata import make_sample


def _rec(w):
    b = load_daily(make_sample())
    a, n = analyze_nested(b)
    return build_signal_record(b, a, n, ticker="X", source="x", weigher=w)


def test_default_equals_deterministic():
    a = _rec(None); b = _rec(DeterministicWeigher())
    assert [s["weight"] for s in a["scenarios"]] == [s["weight"] for s in b["scenarios"]]
    assert a["weigher"] == "deterministic" and b["weigher"] == "deterministic"


def test_weights_sum_to_one_all_weighers():
    for w in (None, DeterministicWeigher(), FakeWeigher()):
        rec = _rec(w)
        assert validate_record(rec) == []
        assert abs(sum(s["weight"] for s in rec["scenarios"]) - 1.0) <= 0.02


def test_fake_weigher_is_deterministic_and_tagged():
    a = _rec(FakeWeigher()); b = _rec(FakeWeigher())
    assert [s["weight"] for s in a["scenarios"]] == [s["weight"] for s in b["scenarios"]]
    assert a["weigher"] == "fake"


if __name__ == "__main__":
    test_default_equals_deterministic()
    test_weights_sum_to_one_all_weighers()
    test_fake_weigher_is_deterministic_and_tagged()
    print("OK: weigher tests pass")
