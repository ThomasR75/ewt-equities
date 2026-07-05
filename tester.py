"""Prototype reliability tester (Project 2 starter).

Scores a signals.jsonl stream against the continuation bars using the engine's
SHARED outcome rules (ewt.outcome.rules.resolve_outcome), so the tester and the
generator can never disagree on what won/lost/invalidated/expired means.

Usage:
    python tester.py records/charts/TEST1/signals_v1.1.jsonl data/Test1.csv

Distinct setups are scored once (by setup id, first issuance) so a single
structure re-emitted across many bars counts as one trade, not many.
"""

from __future__ import annotations

import json
import sys
from collections import Counter

import pandas as pd

from ewt.outcome.rules import resolve_outcome


def main(signals_path: str, csv_path: str) -> None:
    recs = [json.loads(l) for l in open(signals_path) if l.strip()]

    raw = pd.read_csv(csv_path)
    raw.index = pd.to_datetime(raw["date"])
    raw = raw.sort_index()
    bars = raw[["open", "high", "low", "close"]].astype(float)

    # First issuance of each distinct setup id.
    first: dict[str, dict] = {}
    for r in recs:
        s = r.get("setup")
        if s and r.get("grade"):
            first.setdefault(s["id"], r)

    results = []
    for sid, r in first.items():
        s = r["setup"]
        cont = bars.loc[bars.index > pd.Timestamp(s["issued"])]
        res = resolve_outcome(s, cont)
        results.append({
            "id": sid, "issued": s["issued"], "dir": s["direction"],
            "grade": s["grade"], "conf": r["confidence_pct"], "rr": s["rr"],
            "status": res.status, "resolution": res.resolution,
            "pnl_r": round(res.pnl_r, 2),
        })

    print(f"distinct setups scored: {len(results)}\n")
    hdr = f"{'id':<18}{'dir':<6}{'grade':<6}{'conf%':<7}{'rr':<6}{'status':<12}{'pnl_R':<7}"
    print(hdr)
    for x in sorted(results, key=lambda z: z["issued"]):
        print(f"{x['id']:<18}{x['dir']:<6}{x['grade']:<6}{x['conf']:<7}{x['rr']:<6}"
              f"{x['status']:<12}{x['pnl_r']:<7}")

    resolved = [x for x in results if x["resolution"] in ("won", "lost", "invalidated", "expired")]
    print("\n=== aggregate ===")
    print("resolved:", len(resolved), "| outcomes:", dict(Counter(x["resolution"] for x in resolved)))
    if resolved:
        wins = [x for x in resolved if x["resolution"] == "won"]
        tot = sum(x["pnl_r"] for x in resolved)
        print(f"win rate: {100*len(wins)/len(resolved):.0f}%   "
              f"mean PnL: {tot/len(resolved):+.2f} R   total: {tot:+.2f} R")
        for g in ("A", "B"):
            gg = [x for x in resolved if x["grade"] == g]
            if gg:
                w = sum(1 for x in gg if x["resolution"] == "won")
                print(f"  grade {g}: n={len(gg)} win={w}/{len(gg)} "
                      f"({100*w/len(gg):.0f}%) meanR={sum(x['pnl_r'] for x in gg)/len(gg):+.2f}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python tester.py <signals.jsonl> <ohlcv.csv>")
        raise SystemExit(1)
    main(sys.argv[1], sys.argv[2])
