"""Sweep the pivot swing-sensitivity switch (pivot_scale) with a TRAIN/HOLDOUT
split, so we iterate toward a good value WITHOUT fitting the test set.

    python sweep_sensitivity.py data\\prices_anonymized.csv --stocks 1-12 \
        --scales 0.6,0.8,1.0,1.3,1.7 --start 1975-01-01 --step 12M --cutoff 2010-01-01

For each scale it runs the walk-forward once, scores every distinct setup, then
partitions setups by ISSUE DATE: train = issued before --cutoff, holdout = on/
after. It picks the best scale on TRAIN expectancy and reports that scale's
HOLDOUT numbers untouched. The useful output is the whole table: an edge that
survives only at one hand-picked scale is not real.
"""
from __future__ import annotations
import argparse, glob, json, math, os
import pandas as pd
from ewt.io.walkforward import iter_as_of
from ewt.analyze import analyze_nested
from ewt.export.signal import build_signal_record
from ewt.outcome.rules import resolve_outcome

SPAN_K, HMIN, HMAX = 1.0, 120, 2500


def parse_ids(spec):
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-"); out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def split_stocks(multi_csv, ids, split_dir):
    os.makedirs(split_dir, exist_ok=True)
    need = [s for s in ids if not os.path.exists(os.path.join(split_dir, f"{s}.csv"))]
    if need:
        df = pd.read_csv(multi_csv)
        for sid in need:
            s = df[df["stock_id"] == sid][["date", "open", "high", "low", "close", "volume"]].sort_values("date")
            if len(s):
                s.to_csv(os.path.join(split_dir, f"{sid}.csv"), index=False)


def horizon(rec):
    for c in rec.get("counts", []):
        if c.get("tf") == "D" and c.get("pivots"):
            ts = [pd.Timestamp(p["ts"]) for p in c["pivots"]]
            return max(HMIN, min(HMAX, int(round(SPAN_K * (max(ts) - min(ts)).days * 252 / 365))))
    return 250


def score(setups, bars_by):
    def res(s):
        b = bars_by[s["_sid"]]; return resolve_outcome(s, b.loc[b.index > pd.Timestamp(s["issued"])])
    rows = [(s, res(s)) for s in setups]
    rows = [(s, o) for s, o in rows if o.resolution in ("won", "lost", "invalidated", "expired")]
    if not rows:
        return (0, 0.0, 0.0)
    n = len(rows); won = sum(1 for _, o in rows if o.resolution == "won")
    exp = sum(o.pnl_r for _, o in rows) / n
    return (n, won / n, exp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv"); ap.add_argument("--stocks", default="1-12")
    ap.add_argument("--scales", default="0.6,0.8,1.0,1.3,1.7",
                    help="log mode: pivot_scale multipliers; atr mode: atr_k values")
    ap.add_argument("--pivot-mode", default="log", choices=["log", "atr"],
                    help="atr = structural, volatility-proportional threshold")
    ap.add_argument("--start", default="1975-01-01"); ap.add_argument("--step", default="12M")
    ap.add_argument("--cutoff", default="2010-01-01"); ap.add_argument("--out", default="records/sweep")
    args = ap.parse_args()
    ids = parse_ids(args.stocks); scales = [float(x) for x in args.scales.split(",")]
    split_dir = os.path.join(args.out, "_stocks"); split_stocks(args.csv, ids, split_dir)
    bars_by = {}
    for sid in ids:
        p = os.path.join(split_dir, f"{sid}.csv")
        if os.path.exists(p):
            b = pd.read_csv(p); b.index = pd.to_datetime(b["date"]); b = b.sort_index()
            bars_by[str(sid)] = b[["open", "high", "low", "close"]].astype(float)

    cutoff = pd.Timestamp(args.cutoff)
    print(f"{'scale':>6} | {'train_n':>7} {'train_win':>9} {'train_exp':>9} | {'hold_n':>6} {'hold_win':>8} {'hold_exp':>8}")
    results = {}
    for scale in scales:
        setups = []
        for sid in ids:
            p = os.path.join(split_dir, f"{sid}.csv")
            if not os.path.exists(p):
                continue
            for b in iter_as_of(p, start=args.start, step=args.step):
                if args.pivot_mode == "atr":
                    a, n = analyze_nested(b, pivot_mode="atr", atr_k=scale)
                else:
                    a, n = analyze_nested(b, pivot_scale=scale)
                rec = build_signal_record(b, a, n, ticker=f"S{sid}", source=f"{sid}.csv")
                s = rec.get("setup")
                if s and rec.get("grade"):
                    s = dict(s); s["horizon_bars"] = horizon(rec); s["_sid"] = str(sid); setups.append(s)
        # dedupe by id, keep first
        seen = {};
        for s in setups:
            seen.setdefault(s["id"], s)
        setups = list(seen.values())
        train = [s for s in setups if pd.Timestamp(s["issued"]) < cutoff]
        hold = [s for s in setups if pd.Timestamp(s["issued"]) >= cutoff]
        tn, tw, te = score(train, bars_by); hn, hw, he = score(hold, bars_by)
        results[scale] = (tn, tw, te, hn, hw, he)
        print(f"{scale:>6} | {tn:>7} {100*tw:>8.0f}% {te:>+9.3f} | {hn:>6} {100*hw:>7.0f}% {he:>+8.3f}")

    best = max(results, key=lambda k: results[k][2] if results[k][0] >= 3 else -9)
    tn, tw, te, hn, hw, he = results[best]
    print(f"\nbest scale on TRAIN expectancy: {best}  (train exp {te:+.3f}, n={tn})")
    print(f"  -> HOLDOUT at that scale: exp {he:+.3f}, win {100*hw:.0f}%, n={hn}")
    print("  Judge robustness across the whole band above, not just the best cell.")


if __name__ == "__main__":
    main()
