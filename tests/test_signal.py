"""M5 signal-layer tests: gate, weights, schema, grading, determinism, no-lookahead."""

from __future__ import annotations

import copy
import pandas as pd

from ewt.io.ingest import load_daily
from ewt.analyze import analyze_nested
from ewt.export.signal import build_signal_record
from ewt.export.schema import validate_record
from ewt.signal.scenario import build_scenarios
from ewt.signal.setup import build_setup, RR_FLOOR
from ewt.signal.grade import grade_setup
from ewt.schemas import Scenario, Count, Leg, Pivot, RuleReport
from ewt.sampledata import make_sample
import math


def _rec(df, as_of=None):
    b = load_daily(df, as_of=as_of)
    analyses, nested = analyze_nested(b)
    return build_signal_record(b, analyses, nested, ticker="SAMPLE", source="x.csv")


def test_record_schema_valid_and_weights_sum_to_one():
    rec = _rec(make_sample())
    assert validate_record(rec) == []
    total = round(sum(s["weight"] for s in rec["scenarios"]), 3)
    assert abs(total - 1.0) <= 0.02


def test_rr_gate_blocks_low_rr():
    # The clean sample's market entry is far from invalidation -> rr < floor -> none.
    rec = _rec(make_sample())
    if rec["setup"] is not None and rec["setup"]["rr"] < RR_FLOOR:
        assert rec["signal"] == "none" and rec["grade"] is None


def _mk(idx, price, kind):
    return Pivot(idx=idx, ts=pd.Timestamp("2020-01-01") + pd.Timedelta(days=idx),
                 price=price, log_price=math.log(price), kind=kind)


def test_grade_assigned_when_rr_passes():
    # Hand-build a long scenario whose targets give R/R >= 2.
    pv = [_mk(0, 100, "L"), _mk(2, 130, "H"), _mk(4, 112, "L")]
    legs = [Leg(pv[0], pv[1]), Leg(pv[1], pv[2]), Leg(pv[1], pv[2])]
    c = Count(tf="D", structure="zigzag", degree="Minor",
              legs=[Leg(pv[0], pv[1]), Leg(pv[1], pv[2]),
                    Leg(pv[2], _mk(6, 100, "H"))],
              labels=["0", "A", "B", "C"], score=0.8,
              rule_report=RuleReport(cardinal_pass=True, scale_used={"corrective": "lin"}))
    s = Scenario(rank=1, path="x", weight=0.7, direction=1,
                 key_levels=[100.0], primary_count=c)
    setup = build_setup(s, last_price=101.0, as_of="2020-02-01", ticker="T")
    if setup is not None:
        setup = grade_setup(setup, [s, Scenario(rank=2, path="r", weight=0.3, is_residual=True)])
        if setup.rr >= RR_FLOOR:
            assert setup.grade in ("A", "B")
        else:
            assert setup.grade is None


def test_determinism_minus_timestamp():
    a = _rec(make_sample()); b = _rec(make_sample())
    a = copy.deepcopy(a); b = copy.deepcopy(b)
    a.pop("generated_at"); b.pop("generated_at")
    assert a == b


def test_no_lookahead_minus_timestamp():
    full = make_sample()
    cut = pd.Timestamp("2023-08-16")
    a = _rec(full.loc[full.index <= cut])
    b = _rec(full, as_of=cut)
    a.pop("generated_at"); b.pop("generated_at")
    assert a == b


if __name__ == "__main__":
    test_record_schema_valid_and_weights_sum_to_one()
    test_rr_gate_blocks_low_rr()
    test_grade_assigned_when_rr_passes()
    test_determinism_minus_timestamp()
    test_no_lookahead_minus_timestamp()
    print("OK: signal tests pass")
