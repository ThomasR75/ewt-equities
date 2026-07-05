"""Score a universe of per-stock signal streams and report calibration WITH
statistics: Wilson CI on win rate, bootstrap CI on expectancy, a two-sided test
that mean R != 0, and a random-direction permutation null (does the wave-count
direction beat a coin flip?).

    python aggregate_tester.py records\\universe --weigher deterministic
    python aggregate_tester.py records\\universe --weigher ollama

Reads <dir>/S<id>/signals_<weigher>.jsonl and <dir>/_stocks/<id>.csv. Uses the
shared outcome rules with a degree-scaled horizon. Run it for both weighers and
compare point estimates AND their confidence intervals.
"""
from __future__ import annotations
import argparse, glob, json, math, os, random, re
from collections import Counter
import pandas as pd
from ewt.outcome.rules import resolve_outcome

SPAN_K, HMIN, HMAX = 1.0, 120, 2500
random.seed(0)


def horizon(rec):
    for c in rec.get("counts", []):
        if c.get("tf") == "D" and c.get("pivots"):
            ts = [pd.Timestamp(p["ts"]) for p in c["pivots"]]
            return max(HMIN, min(HMAX, int(round(SPAN_K * (max(ts) - min(ts)).days * 252 / 365))))
    return 250


def flip(s):
    """Mirror a setup to the opposite direction, same log R and reward."""
    e = math.log(s["entry"]); risk = abs(e - math.log(s["stop"])); rew = abs(math.log(s["t1"]) - e)
    d = 1 if s["direction"] == "long" else -1; nd = -d
    ns = dict(s); ns["direction"] = "long" if nd > 0 else "short"
    ns["stop"] = round(math.exp(e - nd * risk), 6)
    ns["t1"] = round(math.exp(e + nd * rew), 6)
    ns["invalidation_level"] = ns["stop"]
    return ns


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n; den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0, c - h), min(1, c + h))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir"); ap.add_argument("--weigher", default="deterministic")
    ap.add_argument("--boot", type=int, default=5000); ap.add_argument("--null", type=int, default=2000)
    args = ap.parse_args()
    split = os.path.join(args.dir, "_stocks")

    setups, bars_by = [], {}
    n_records = 0
    for path in sorted(glob.glob(os.path.join(args.dir, "S*", f"signals_{args.weigher}.jsonl"))):
        sid = re.search(r"S(\d+)", path).group(1)
        csv = os.path.join(split, f"{sid}.csv")
        if not os.path.exists(csv):
            continue
        b = pd.read_csv(csv); b.index = pd.to_datetime(b["date"]); b = b.sort_index()
        bars_by[sid] = b[["open", "high", "low", "close"]].astype(float)
        recs = [json.loads(l) for l in open(path) if l.strip()]; n_records += len(recs)
        first = {}
        for r in recs:
            s = r.get("setup")
            if s and r.get("grade"):
                first.setdefault(s["id"], r)
        for r in first.values():
            s = dict(r["setup"]); s["horizon_bars"] = horizon(r); s["_sid"] = sid
            s["_grade"] = r["setup"]["grade"]; s["_conf"] = r["confidence_pct"]
            setups.append(s)

    def res(s):
        b = bars_by[s["_sid"]]; return resolve_outcome(s, b.loc[b.index > pd.Timestamp(s["issued"])])

    rows = [(s, res(s)) for s in setups]
    rows = [(s, o) for s, o in rows if o.resolution in ("won", "lost", "invalidated", "expired")]
    n = len(rows)
    print(f"weigher={args.weigher}  records={n_records}  resolved setups={n}")
    if n == 0:
        return
    R = [o.pnl_r for _, o in rows]
    won = sum(1 for _, o in rows if o.resolution == "won")
    mean = sum(R) / n
    lo, hi = wilson(won, n)
    print(f"win rate {100*won/n:.1f}%  Wilson95 [{100*lo:.1f}, {100*hi:.1f}]%")

    means = []
    for _ in range(args.boot):
        s = [R[random.randrange(n)] for _ in range(n)]; means.append(sum(s) / n)
    means.sort()
    blo, bhi = means[int(0.025 * args.boot)], means[int(0.975 * args.boot)]
    p0 = 2 * min(sum(m >= 0 for m in means), sum(m <= 0 for m in means)) / args.boot
    print(f"expectancy {mean:+.3f} R  bootstrap95 [{blo:+.3f}, {bhi:+.3f}]  (2-sided p mean!=0 ~ {p0:.2f})")

    flip_r = [res(flip(s)).pnl_r for s, _ in rows]
    nulls = []
    for _ in range(args.null):
        nulls.append(sum(R[i] if random.random() < 0.5 else flip_r[i] for i in range(n)) / n)
    nulls.sort()
    p_dir = sum(m >= mean for m in nulls) / args.null
    print(f"random-direction null mean {sum(nulls)/args.null:+.3f}  "
          f"5-95% [{nulls[int(0.05*args.null)]:+.3f}, {nulls[int(0.95*args.null)]:+.3f}]  "
          f"one-sided p(engine>=random) {p_dir:.2f}")
    print(f"anti-portfolio (all flipped) mean {sum(flip_r)/n:+.3f}")

    print("calibration by grade:")
    for g in ("A", "B"):
        gg = [(s, o) for s, o in rows if s["_grade"] == g]
        if gg:
            w = sum(1 for _, o in gg if o.resolution == "won")
            print(f"  {g}: n={len(gg)} win {100*w/len(gg):.0f}% meanR {sum(o.pnl_r for _,o in gg)/len(gg):+.2f}")
    print("calibration by confidence:")
    for a, b in [(0, 30), (30, 50), (50, 101)]:
        gg = [(s, o) for s, o in rows if a <= s["_conf"] < b]
        if gg:
            w = sum(1 for _, o in gg if o.resolution == "won")
            print(f"  {a}-{b}%: n={len(gg)} win {100*w/len(gg):.0f}% meanR {sum(o.pnl_r for _,o in gg)/len(gg):+.2f}")


if __name__ == "__main__":
    main()
