"""Assemble the full human report (spec §2/§14): header, thesis, scorecard,
charts, scenario table, trade plan, and 'the one level that matters'.

Built from the same objects as the SignalRecord, so the report and the JSON can
never disagree.
"""

from __future__ import annotations

from pathlib import Path

from .narrative import headline


def _scenario_table(scenarios: list[dict]) -> str:
    rows = ["| # | Path | Weight | Invalidation |", "|---|---|---|---|"]
    for s in scenarios:
        rows.append(f"| {s['rank']} | {s['path']} | {s['weight']*100:.0f}% | "
                    f"{s.get('invalidation','') or '—'} |")
    return "\n".join(rows)


def _trade_plan(rec: dict) -> str:
    s = rec["setup"]
    if s is None or rec["grade"] is None:
        reason = ("no directional structure" if s is None
                  else f"R/R {s['rr']} below the 2.0 floor")
        return f"**No setup** — {reason}. A read, not a trade."
    rows = [
        "| ID | Grade | Dir | Entry | Stop | T1 | T2 | R/R |",
        "|---|---|---|---|---|---|---|---|",
        f"| {s['id']} | {s['grade']} | {s['direction']} | {s['entry']} "
        f"({s['entry_type']}) | {s['stop']} | {s['t1']} | {s['t2']} | {s['rr']} |",
    ]
    return "\n".join(rows)


def _scorecard_table(rows: list[dict]) -> str:
    if not rows:
        return "_No prior setups — first record for this ticker._"
    out = ["| ID | Issued | Dir | Grade | Status | PnL (R) |",
           "|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['id']} | {r['issued']} | {r['direction']} | "
                   f"{r['grade'] or '—'} | {r['status']} | {r['pnl_r']} |")
    return "\n".join(out)


def build_report(ticker: str, rec: dict, charts: dict, scorecard_rows: list[dict],
                 out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    d = rec["data"]
    nr = rec.get("nested_read")

    parts = []
    parts.append(f"# {ticker} — Elliott Wave analysis "
                 f"(as of {d['as_of']}, last {d['last_price']})")
    parts.append(f"\n**Headline.** {headline(ticker, rec)}")

    if nr:
        parts.append(f"\n**Nested structure.** {nr['note']} "
                     f"(alignment {nr['alignment']}).")

    parts.append("\n## Scenarios\n")
    parts.append(_scenario_table(rec["scenarios"]))

    parts.append("\n## Trade plan\n")
    parts.append(_trade_plan(rec))

    pl = rec.get("pivot_level")
    parts.append("\n## The one level that matters next\n")
    parts.append(f"**{pl}** — the highest-confluence level; it gates the lead "
                 f"scenario and the trade trigger." if pl is not None
                 else "No single decisive level identified.")

    parts.append("\n## Prior setups (scorecard)\n")
    parts.append(_scorecard_table(scorecard_rows))

    if charts:
        parts.append("\n## Charts\n")
        for tf in ["M", "W", "D"]:
            if tf in charts:
                rel = Path(charts[tf]).name
                parts.append(f"### {tf}\n\n![{tf} chart]({rel})\n")

    parts.append(f"\n---\n_engine {rec['engine_version']} · data_hash "
                 f"{d['data_hash'][:12]}… · schema v{rec['schema_version']}_")

    text = "\n".join(parts) + "\n"
    out_path.write_text(text, encoding="utf-8")
    return out_path
