"""Reproduce the paper's Section 4 (deterministic) and Section 7 (LLM) statistics
from a scored universe directory.

Prereq: generate the signal streams first, e.g.
    python batch_universe.py data/prices_anonymized.csv --weigher deterministic \
        --stocks 1-50 --start 1962-01-01 --step 1M --out records/universe_monthly
    python batch_universe.py data/prices_anonymized.csv --weigher ollama \
        --model qwen2.5:7b-instruct --stocks 1-50 --start 1962-01-01 --step 1M --out records/universe_monthly

Then:
    python analysis/paper_stats.py records/universe_monthly

Prints, per weigher: n, win rate (Wilson), expectancy (bootstrap + block-bootstrap
by stock), random-direction null, drift control (long/short/forced-long/buy&hold/alpha),
grade A>B (label-permutation p, block-bootstrap CI, win-rate gap) with a disjoint
split-half replication, Brier/ECE calibration, and transaction-cost sensitivity.
"""
from __future__ import annotations
import sys, json, glob, re, math
import pandas as pd, numpy as np
from ewt.outcome.rules import resolve_outcome

SPAN_K, HMIN, HMAX = 1.0, 120, 2500
RES = {"won", "lost", "invalidated", "expired"}


def horizon(rec):
    for c in rec.get("counts", []):
        if c.get("tf") == "D" and c.get("pivots"):
            ts = [pd.Timestamp(p["ts"]) for p in c["pivots"]]
            return max(HMIN, min(HMAX, int(round(SPAN_K * (max(ts) - min(ts)).days * 252 / 365))))
    return 250


def load(root, weigher):
    setups, bars = [], {}
    for p in sorted(glob.glob(f"{root}/S*/signals_{weigher}.jsonl")):
        sid = re.search(r"S(\d+)", p).group(1)
        b = pd.read_csv(f"{root}/_stocks/{sid}.csv"); b.index = pd.to_datetime(b["date"]); b = b.sort_index()
        bars[sid] = b[["open", "high", "low", "close"]].astype(float)
        first = {}
        for l in open(p):
            if l.strip():
                r = json.loads(l); st = r.get("setup")
                if st and r.get("grade"):
                    first.setdefault(st["id"], r)
        for r in first.values():
            s = dict(r["setup"]); s["horizon_bars"] = horizon(r); s["_sid"] = sid
            s["_grade"] = r["setup"]["grade"]; s["_conf"] = r["confidence_pct"]; s["_rr"] = r["setup"].get("rr", np.nan)
            setups.append(s)
    return setups, bars


def fwd(s, bars):
    b = bars[s["_sid"]]; return b.loc[b.index > pd.Timestamp(s["issued"])]


def mlong(s):
    if s["direction"] == "long": return s
    e = math.log(s["entry"]); f = dict(s); f["direction"] = "long"
    f["stop"] = math.exp(2 * e - math.log(s["stop"])); f["t1"] = math.exp(2 * e - math.log(s["t1"]))
    if s.get("invalidation_level", 0) > 0: f["invalidation_level"] = math.exp(2 * e - math.log(s["invalidation_level"]))
    return f


def bh_r(s, bars):
    fb = fwd(s, bars); H = min(int(s["horizon_bars"]), len(fb) - 1)
    if H <= 0: return np.nan
    risk = abs(float(s["entry"]) - float(s["stop"])) or 1e-9
    return (fb["close"].iloc[H] - float(s["entry"])) / risk


def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def perm_p(vals, isA, rng, n=20000):
    vals = np.asarray(vals); obs = vals[isA].mean() - vals[~isA].mean()
    k = int(isA.sum()); idx = np.arange(len(vals)); c = 0
    for _ in range(n):
        sel = rng.permutation(idx)[:k]
        if vals[sel].mean() - np.delete(vals, sel).mean() >= obs: c += 1
    return obs, c / n


def analyze(root, weigher, rng):
    setups, bars = load(root, weigher)
    rows = []
    for s in setups:
        o = resolve_outcome(s, fwd(s, bars))
        if o.resolution in RES:
            rows.append((s, o.pnl_r, o.resolution == "won"))
    n = len(rows); R = np.array([r for _, r, _ in rows]); W = np.array([w for _, _, w in rows])
    A = np.array([s["_grade"] == "A" for s, _, _ in rows]); sid = np.array([s["_sid"] for s, _, _ in rows])
    print(f"\n===== {weigher}  n={n} =====")
    wlo, whi = wilson(int(W.sum()), n)
    boot = np.array([R[rng.integers(0, n, n)].mean() for _ in range(10000)])
    print(f"win {100*W.mean():.1f}% Wilson95 [{100*wlo:.1f},{100*whi:.1f}]  "
          f"exp {R.mean():+.3f} boot95 [{np.percentile(boot,2.5):+.3f},{np.percentile(boot,97.5):+.3f}]")
    # block bootstrap by stock
    usid = np.unique(sid); bb = []
    for _ in range(10000):
        pick = rng.choice(usid, len(usid), replace=True)
        bb.append(np.concatenate([R[sid == u] for u in pick]).mean())
    print(f"block-boot95 by stock [{np.percentile(bb,2.5):+.3f},{np.percentile(bb,97.5):+.3f}]")
    # drift control
    Rl = R[[s['direction'] == 'long' for s, _, _ in rows]]; Rs = R[[s['direction'] == 'short' for s, _, _ in rows]]
    fl = np.array([resolve_outcome(mlong(s), fwd(s, bars)).pnl_r for s, _, _ in rows])
    bh = np.array([bh_r(s, bars) for s, _, _ in rows]); bh = bh[~np.isnan(bh)]
    print(f"drift: long n={len(Rl)} {Rl.mean():+.3f} | short n={len(Rs)} {Rs.mean():+.3f} | "
          f"forced-long {fl.mean():+.3f} | buy&hold {bh.mean():+.3f} | alpha {R.mean()-bh.mean():+.3f}")
    # grade A>B
    obs, pE = perm_p(R, A, rng); ga = perm_p(W.astype(float), A, rng)
    bbg = []
    for _ in range(10000):
        pick = rng.choice(usid, len(usid), replace=True)
        rr = np.concatenate([R[sid == u] for u in pick]); aa = np.concatenate([A[sid == u] for u in pick])
        if aa.any() and (~aa).any(): bbg.append(rr[aa].mean() - rr[~aa].mean())
    print(f"grade A>B: gap {obs:+.3f} perm p={pE:.3f}  block-boot95 [{np.percentile(bbg,2.5):+.3f},{np.percentile(bbg,97.5):+.3f}]  "
          f"win-rate gap {100*(W[A].mean()-W[~A].mean()):+.1f}pp p={ga[1]:.3f}")
    print(f"  R:R  A={np.nanmean([s['_rr'] for s,_,_ in rows if s['_grade']=='A']):.2f}  B={np.nanmean([s['_rr'] for s,_,_ in rows if s['_grade']!='A']):.2f}")
    for half, keep in [("even", lambda x: int(x) % 2 == 0), ("odd", lambda x: int(x) % 2 == 1)]:
        m = np.array([keep(s["_sid"]) for s, _, _ in rows])
        o2, p2 = perm_p(R[m], A[m], rng)
        print(f"  split-half {half}: gap {o2:+.3f} perm p={p2:.3f}")
    # Brier / ECE
    conf = np.array([s["_conf"] / 100 for s, _, _ in rows]); base = W.mean()
    brier = np.mean((conf - W) ** 2); brier0 = np.mean((base - W) ** 2)
    ece = sum(((conf >= lo) & (conf < hi)).sum() * abs(conf[(conf >= lo) & (conf < hi)].mean() - W[(conf >= lo) & (conf < hi)].mean())
              for lo, hi in [(0, .3), (.3, .5), (.5, .7), (.7, 1.01)] if ((conf >= lo) & (conf < hi)).any()) / n
    print(f"Brier {brier:.3f} (base {brier0:.3f})  ECE {ece:.3f}")
    print("cost sensitivity R/trade: " + "  ".join(f"{c:.2f}->{(R-c).mean():+.3f}" for c in (0, .05, .10, .20)))


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "records/universe_monthly"
    rng = np.random.default_rng(0)
    for w in ["deterministic", "ollama"]:
        if glob.glob(f"{root}/S*/signals_{w}.jsonl"):
            analyze(root, w, rng)
