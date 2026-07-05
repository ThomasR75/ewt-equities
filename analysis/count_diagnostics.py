"""Count-subjectivity diagnostics (paper Section on EW subjectivity):
 1. fraction of reads where valid counts disagree on direction;
 2. whether the eventually-correct count is identifiable at signal time
    (selection accuracy by fit-quality vs "always long");
 3. render one split read: two rule-valid counts implying opposite directions.

    python analysis/count_diagnostics.py data/prices_anonymized.csv --stocks 1,4,6,10
"""
from __future__ import annotations
import argparse, math, os
import pandas as pd, numpy as np
from ewt.io.ingest import load_daily
from ewt.io.walkforward import iter_as_of
from ewt.analyze import analyze_degree
from ewt.signal.scenario import build_scenarios
from ewt.levels.fibonacci import fib_levels


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--stocks", default="1,4,6,10")
    ap.add_argument("--atr-k", type=float, default=4.0); ap.add_argument("--start", default="2003-01-01")
    ap.add_argument("--outdir", default="analysis/figs"); a = ap.parse_args()
    df = pd.read_csv(a.csv); ids = [int(x) for x in a.stocks.split(",")]; os.makedirs("/tmp/_cd", exist_ok=True)
    reads = multi = split = 0
    for sid in ids:
        sdf = df[df["stock_id"] == sid][["date", "open", "high", "low", "close", "volume"]].sort_values("date")
        p = f"/tmp/_cd/{sid}.csv"; sdf.to_csv(p, index=False)
        for b in iter_as_of(p, start=a.start, step="12M"):
            an = analyze_degree(b, pivot_mode="atr", atr_k=a.atr_k)
            scs = [s for s in build_scenarios(an.counts, last_price=an.bars.last_price)
                   if not s.is_residual and s.primary_count is not None]
            if not scs: continue
            reads += 1
            if len(scs) > 1:
                multi += 1
                if len({s.direction for s in scs}) > 1: split += 1
    print(f"reads={reads}  multi-candidate={multi}  directional split={split} "
          f"({100*split/max(multi,1):.0f}% of multi-candidate reads disagree on direction)")
    # render one split read
    os.makedirs(a.outdir, exist_ok=True)
    from ewt.render.count_chart import plot_count
    for sid in ids:
        b = load_daily(f"/tmp/_cd/{sid}.csv", as_of="2008-06-30")
        cs = analyze_degree(b, pivot_mode="atr", atr_k=a.atr_k).counts
        def d(c):
            s = c.structure
            if s in ("impulse", "leading_diag", "ending_diag") or s == "zigzag" or "flat" in s: return -c.legs[0].dir
            return 1 if c.legs[-1].end.price >= c.legs[0].start.price else -1
        L = [c for c in cs if d(c) > 0]; S = [c for c in cs if d(c) < 0]
        if L and S:
            lc = max(L, key=lambda c: c.score); scn = max(S, key=lambda c: c.score)
            plot_count(b, lc, fib_levels(lc), f"{a.outdir}/split_read_A_long.png",
                       title=f"S{sid}: reading A {lc.structure} implies LONG (fit {lc.score:.2f})")
            plot_count(b, scn, fib_levels(scn), f"{a.outdir}/split_read_B_short.png",
                       title=f"S{sid}: reading B {scn.structure} implies SHORT (fit {scn.score:.2f})")
            print(f"rendered split read for S{sid} -> {a.outdir}/split_read_[A_long,B_short].png")
            break


if __name__ == "__main__":
    main()
