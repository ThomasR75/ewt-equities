"""M6: outcome rules, scorecard, and report assembly."""

from __future__ import annotations

import json
import numpy as np
import pandas as pd

from ewt.io.ingest import load_daily
from ewt.analyze import analyze_nested
from ewt.export.signal import build_signal_record
from ewt.outcome.rules import resolve_outcome
from ewt.render.report import build_report
from ewt.render.narrative import headline
from ewt.sampledata import make_sample


def _bars(seq, start="2020-01-01"):
    idx = pd.date_range(start, periods=len(seq))
    return pd.DataFrame({"open": seq, "high": [s + 1 for s in seq],
                         "low": [s - 1 for s in seq], "close": seq}, index=idx)


LONG = {"direction": "long", "entry": 100, "entry_type": "market",
        "stop": 90, "t1": 130, "invalidation_level": 90, "horizon_bars": 60}


def test_outcome_won_and_lost():
    assert resolve_outcome(LONG, _bars(list(np.linspace(100, 135, 20)))).resolution == "won"
    assert resolve_outcome(LONG, _bars(list(np.linspace(100, 84, 20)))).resolution == "lost"


def test_outcome_untriggered_limit():
    s = dict(LONG, entry_type="limit", entry=80)  # price never falls to 80
    r = resolve_outcome(s, _bars(list(np.linspace(100, 120, 10))))
    assert r.triggered is False and r.status in ("untriggered", "expired")


def test_outcome_stop_first_tiebreak():
    # A bar whose range spans both stop and t1 resolves to the stop (conservative).
    bars = _bars([100, 100])
    bars.iloc[1] = [100, 131, 89, 100]  # high>=t1 and low<=stop same bar
    assert resolve_outcome(LONG, bars, tie_break="stop").resolution == "lost"


def test_report_has_required_sections():
    b = load_daily(make_sample())
    analyses, nested = analyze_nested(b)
    rec = build_signal_record(b, analyses, nested, ticker="SAMPLE", source="x.csv")
    path = build_report("SAMPLE", rec, {}, [], "/tmp/_m6_report.md")
    txt = path.read_text()
    for section in ["# SAMPLE", "## Scenarios", "## Trade plan",
                    "The one level that matters", "Prior setups"]:
        assert section in txt
    assert "an impulse" in headline("SAMPLE", rec) or "reads as impulse" in headline("SAMPLE", rec)


def test_report_deterministic_no_lookahead():
    full = make_sample()
    cut = pd.Timestamp("2023-08-16")

    def rep(df):
        b = load_daily(df) if df is full else load_daily(df)
        analyses, nested = analyze_nested(b)
        rec = build_signal_record(b, analyses, nested, ticker="S", source="x")
        return build_report("S", rec, {}, [], "/tmp/_m6_b.md").read_text()

    a = rep(full.loc[full.index <= cut])
    bb = load_daily(full, as_of=cut)
    analyses, nested = analyze_nested(bb)
    rec = build_signal_record(bb, analyses, nested, ticker="S", source="x")
    b_txt = build_report("S", rec, {}, [], "/tmp/_m6_c.md").read_text()
    assert a == b_txt


if __name__ == "__main__":
    test_outcome_won_and_lost()
    test_outcome_untriggered_limit()
    test_outcome_stop_first_tiebreak()
    test_report_has_required_sections()
    test_report_deterministic_no_lookahead()
    print("OK: report tests pass")
