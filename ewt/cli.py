"""M1+M2 entrypoint.

    python -m ewt.cli pivots <ticker> <csv> [--as-of YYYY-MM-DD] [--out DIR]
    python -m ewt.cli count  <ticker> <csv> [--tf D|W|M] [--as-of ...] [--out DIR]
    python -m ewt.cli demo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .io.ingest import load_daily, data_hash
from .io.resample import build_all, resample
from .pivots.series import build_all as build_pivots_all
from .render.charts import plot_three_degrees


def run_pivots(ticker: str, csv: str, as_of: str | None, out: str) -> dict:
    daily = load_daily(csv, as_of=as_of)
    tf_bars = build_all(daily)
    tf_pivots = build_pivots_all(tf_bars)
    out_dir = Path(out) / ticker / str(daily.as_of.date())
    charts = plot_three_degrees(tf_bars, tf_pivots, out_dir, ticker)
    summary = {
        "engine_version": __version__,
        "ticker": ticker,
        "as_of": str(daily.as_of.date()),
        "data_hash": data_hash(daily.df),
        "last_price": daily.last_price,
        "bars": {tf: len(b) for tf, b in tf_bars.items()},
        "pivots": {tf: len(p) for tf, p in tf_pivots.items()},
        "is_partial": {tf: b.is_partial for tf, b in tf_bars.items()},
        "charts": [str(c) for c in charts],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "m1_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def run_count(ticker: str, csv: str, tf: str, as_of: str | None, out: str) -> dict:
    from .analyze import analyze_degree
    from .render.count_chart import plot_count

    daily = load_daily(csv, as_of=as_of)
    bars = daily if tf == "D" else resample(daily, tf)
    da = analyze_degree(bars)

    out_dir = Path(out) / ticker / str(daily.as_of.date())
    chart = None
    if da.lead is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        chart = plot_count(
            bars, da.lead, da.levels,
            out_dir / f"{ticker}-{daily.as_of.date()}-{tf}-count.png",
        )

    lead = None
    if da.lead is not None:
        pivots = [da.lead.legs[0].start] + [l.end for l in da.lead.legs]
        lead = {
            "structure": da.lead.structure,
            "score": da.lead.score,
            "cardinal": da.lead.rule_report.cardinal_detail,
            "scale": da.lead.rule_report.scale_used,
            "wave_pivots": [
                {"label": lab, "date": str(p.ts.date()), "price": round(p.price, 4)}
                for lab, p in zip(da.lead.labels, pivots)
            ],
        }

    summary = {
        "engine_version": __version__,
        "ticker": ticker,
        "tf": tf,
        "as_of": str(daily.as_of.date()),
        "data_hash": data_hash(daily.df),
        "n_candidates": len(da.counts),
        "lead": lead,
        "top_zones": [
            {"lo": round(z.lo, 4), "hi": round(z.hi, 4), "n": len(z.members)}
            for z in da.zones[:5]
        ],
        "chart": str(chart) if chart else None,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"m2_{tf}_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def run_nest(ticker: str, csv: str, as_of: str | None, out: str) -> dict:
    from .analyze import analyze_nested
    from .levels.fibonacci import fib_levels
    from .render.count_chart import plot_count

    daily = load_daily(csv, as_of=as_of)
    analyses, nested = analyze_nested(daily)
    out_dir = Path(out) / ticker / str(daily.as_of.date())
    out_dir.mkdir(parents=True, exist_ok=True)

    charts = {}
    if nested is not None:
        chosen = {"M": nested.monthly, "W": nested.weekly, "D": nested.daily}
        for tf, count in chosen.items():
            bars = analyses[tf].bars
            chart = plot_count(
                bars, count, fib_levels(count),
                out_dir / f"{ticker}-{daily.as_of.date()}-{tf}-nested.png",
                title=f"{ticker} {tf} — {count.structure}/{nested.degrees[tf]} "
                      f"wave {nested.current_wave[tf]} (nested)",
            )
            charts[tf] = str(chart)

    summary = {
        "engine_version": __version__,
        "ticker": ticker,
        "as_of": str(daily.as_of.date()),
        "data_hash": data_hash(daily.df),
        "nested_read": None if nested is None else {
            "note": nested.note,
            "alignment": nested.alignment,
            "degrees": nested.degrees,
            "current_wave": nested.current_wave,
            "structures": {
                "M": nested.monthly.structure,
                "W": nested.weekly.structure,
                "D": nested.daily.structure,
            },
        },
        "charts": charts,
    }
    (out_dir / "m4_nested_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def run_signal(ticker: str, csv: str, as_of: str | None, out: str) -> dict:
    from .analyze import analyze_nested
    from .export.signal import build_signal_record, append_signal_log
    from .export.schema import validate_record

    daily = load_daily(csv, as_of=as_of)
    analyses, nested = analyze_nested(daily)
    rec = build_signal_record(daily, analyses, nested, ticker=ticker, source=Path(csv).name)
    problems = validate_record(rec)

    out_dir = Path(out) / ticker / str(daily.as_of.date())
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{ticker}-{daily.as_of.date()}-signal.json").write_text(json.dumps(rec, indent=2))
    append_signal_log(rec, Path(out) / ticker / "signals.jsonl")
    return {"signal": rec["signal"], "grade": rec["grade"],
            "confidence_pct": rec["confidence_pct"],
            "schema_valid": not problems, "problems": problems,
            "record": str(out_dir / f"{ticker}-{daily.as_of.date()}-signal.json")}


def run_report(ticker: str, csv: str, as_of: str | None, out: str) -> dict:
    from .analyze import analyze_nested
    from .export.signal import build_signal_record, append_signal_log
    from .levels.fibonacci import fib_levels
    from .render.count_chart import plot_count
    from .render.report import build_report
    from .render.report_html import build_report_html
    from .signal.scorecard import scorecard

    daily = load_daily(csv, as_of=as_of)
    analyses, nested = analyze_nested(daily)
    rec = build_signal_record(daily, analyses, nested, ticker=ticker, source=Path(csv).name)

    out_dir = Path(out) / ticker / str(daily.as_of.date())
    out_dir.mkdir(parents=True, exist_ok=True)

    charts = {}
    if nested is not None:
        for tf, count in {"M": nested.monthly, "W": nested.weekly, "D": nested.daily}.items():
            chart = plot_count(
                analyses[tf].bars, count, fib_levels(count),
                out_dir / f"{ticker}-{daily.as_of.date()}-{tf}-nested.png",
                title=f"{ticker} {tf} — {count.structure}/{nested.degrees[tf]} wave {nested.current_wave[tf]}",
            )
            charts[tf] = str(chart)

    # Scorecard reads PRIOR signals before appending this run.
    sc = scorecard(Path(out) / ticker / "signals.jsonl", daily)

    (out_dir / f"{ticker}-{daily.as_of.date()}-signal.json").write_text(json.dumps(rec, indent=2))
    append_signal_log(rec, Path(out) / ticker / "signals.jsonl")
    report = build_report(ticker, rec, charts, sc, out_dir / f"{ticker}-{daily.as_of.date()}-report.md")
    report_html = build_report_html(ticker, rec, charts, sc, out_dir / f"{ticker}-{daily.as_of.date()}-report.html")

    return {"signal": rec["signal"], "grade": rec["grade"],
            "confidence_pct": rec["confidence_pct"],
            "report": str(report), "report_html": str(report_html),
            "charts": charts, "prior_setups": len(sc)}


def run_walkforward(ticker: str, csv: str, start: str, end: str | None,
                    step: str, out: str, min_bars: int = 250) -> dict:
    """Emit a stream of SignalRecords across history (spec §15.4).

    One record per step, each a pure function of bars <= that step's date, all
    appended to the per-ticker signals.jsonl — the historical signal stream the
    separate tester consumes. JSON only (no charts/report) for speed.
    """
    from .io.walkforward import iter_as_of
    from .analyze import analyze_nested
    from .export.signal import build_signal_record, append_signal_log
    from .export.schema import validate_record, record_hash

    log_path = Path(out) / ticker / "signals.jsonl"
    n = 0
    by_signal = {"long": 0, "short": 0, "none": 0}
    by_grade = {}
    first = last = None
    problems_total = 0
    for daily in iter_as_of(csv, start=start, end=end, step=step, min_bars=min_bars):
        analyses, nested = analyze_nested(daily)
        rec = build_signal_record(daily, analyses, nested, ticker=ticker, source=Path(csv).name)
        problems_total += len(validate_record(rec))
        append_signal_log(rec, log_path)
        n += 1
        by_signal[rec["signal"]] = by_signal.get(rec["signal"], 0) + 1
        g = str(rec["grade"])
        by_grade[g] = by_grade.get(g, 0) + 1
        first = first or rec["data"]["as_of"]
        last = rec["data"]["as_of"]
    return {"ticker": ticker, "signals": n, "range": [first, last],
            "by_signal": by_signal, "by_grade": by_grade,
            "schema_problems": problems_total, "log": str(log_path)}


def run_demo() -> dict:
    from .sampledata import write_sample

    csv = write_sample()
    run_pivots("SAMPLE", str(csv), as_of=None, out="records/charts")
    return {tf: run_count("SAMPLE", str(csv), tf, None, "records/charts")
            for tf in ["M", "W", "D"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ewt")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pivots")
    p.add_argument("ticker"); p.add_argument("csv")
    p.add_argument("--as-of", default=None); p.add_argument("--out", default="records/charts")

    c = sub.add_parser("count")
    c.add_argument("ticker"); c.add_argument("csv")
    c.add_argument("--tf", default="D", choices=["D", "W", "M"])
    c.add_argument("--as-of", default=None); c.add_argument("--out", default="records/charts")

    nst = sub.add_parser("nest")
    nst.add_argument("ticker"); nst.add_argument("csv")
    nst.add_argument("--as-of", default=None); nst.add_argument("--out", default="records/charts")

    sig = sub.add_parser("signal")
    sig.add_argument("ticker"); sig.add_argument("csv")
    sig.add_argument("--as-of", default=None); sig.add_argument("--out", default="records/charts")

    rpt = sub.add_parser("report")
    rpt.add_argument("ticker"); rpt.add_argument("csv")
    rpt.add_argument("--as-of", default=None); rpt.add_argument("--out", default="records/charts")

    wf = sub.add_parser("walkforward")
    wf.add_argument("ticker"); wf.add_argument("csv")
    wf.add_argument("--start", required=True); wf.add_argument("--end", default=None)
    wf.add_argument("--step", default="1W"); wf.add_argument("--out", default="records/charts")
    wf.add_argument("--min-bars", type=int, default=250)

    sub.add_parser("demo")

    args = ap.parse_args(argv)
    if args.cmd == "pivots":
        summary = run_pivots(args.ticker, args.csv, args.as_of, args.out)
    elif args.cmd == "count":
        summary = run_count(args.ticker, args.csv, args.tf, args.as_of, args.out)
    elif args.cmd == "nest":
        summary = run_nest(args.ticker, args.csv, args.as_of, args.out)
    elif args.cmd == "signal":
        summary = run_signal(args.ticker, args.csv, args.as_of, args.out)
    elif args.cmd == "report":
        summary = run_report(args.ticker, args.csv, args.as_of, args.out)
    elif args.cmd == "walkforward":
        summary = run_walkforward(args.ticker, args.csv, args.start, args.end,
                                  args.step, args.out, args.min_bars)
    else:
        summary = run_demo()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
