"""Score a CalibConfig against the cached walk-forward (reliability harness).

Faithful to aggregate_tester.py: dedupe graded setups by id (first occurrence
per stock), degree/pivot-span horizon, resolve with the shared outcome rules,
then report win rate (+Wilson95), expectancy (+bootstrap95 & p mean!=0), grade
A/B calibration, and a random-direction null (does the engine beat a coin flip).

Used by the server's /api/backtest endpoint; also runnable standalone:
    python -m calib.backtest            # scores DEFAULT config
"""
from __future__ import annotations
import os, sys, math, json, pickle, random
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from ewt.outcome.rules import resolve_outcome
from ewt.signal.setup import build_setup
from ewt.signal.grade import grade_setup
from ewt.signal.calib import CalibConfig, DEFAULT

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_PATH = os.path.join(ROOT, "calib/backtest_state.pkl")
CSV = os.path.join(ROOT, "records/live/prices_live.csv")
HMIN, HMAX, SPAN_K = 120, 2500, 1.0


def _horizon(d_pivots_ts):
    if d_pivots_ts:
        ts = [pd.Timestamp(t) for t in d_pivots_ts]
        return max(HMIN, min(HMAX, int(round(SPAN_K * (max(ts) - min(ts)).days * 252 / 365))))
    return 250


def _flip(s):
    e = math.log(s["entry"]); risk = abs(e - math.log(s["stop"])); rew = abs(math.log(s["t1"]) - e)
    d = 1 if s["direction"] == "long" else -1; nd = -d
    ns = dict(s); ns["direction"] = "long" if nd > 0 else "short"
    ns["stop"] = round(math.exp(e - nd * risk), 6)
    ns["t1"] = round(math.exp(e + nd * rew), 6)
    ns["invalidation_level"] = ns["stop"]
    return ns


def _wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n; den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0, c - h), min(1, c + h))


def state_path(label=None):
    name = f"backtest_state__{label}.pkl" if label else "backtest_state.pkl"
    return os.path.join(ROOT, "calib", name)


def load_state(label=None):
    p = state_path(label)
    if not os.path.exists(p):
        return None
    return pickle.load(open(p, "rb"))


def load_bars(ids):
    df = pd.read_csv(CSV)
    out = {}
    for sid in ids:
        b = df[df["stock_id"] == int(sid)].copy()
        b.index = pd.to_datetime(b["date"]); b = b.sort_index()
        out[str(sid)] = b[["open", "high", "low", "close"]].astype(float)
    return out


def _subset_metrics(rows, R, flip_r, idx, boot, null, rnd):
    """Full metric bundle for a subset of resolved rows (indices into `rows`)."""
    n = len(idx)
    if n == 0:
        return {"resolved": 0, "win_rate": None, "expectancy": None, "total_r": 0.0,
                "won": 0, "lost": 0, "invalidated": 0, "expired": 0, "grade": {},
                "note": "no resolved setups in this window"}
    sub = [rows[i] for i in idx]
    Rs = [R[i] for i in idx]
    fl = [flip_r[i] for i in idx]
    won = sum(1 for _, o in sub if o.resolution == "won")
    counts = {k: sum(1 for _, o in sub if o.resolution == k)
              for k in ("won", "lost", "invalidated", "expired")}
    mean = sum(Rs) / n
    wlo, whi = _wilson(won, n)

    means = []
    for _ in range(boot):
        b = [Rs[rnd.randrange(n)] for _ in range(n)]; means.append(sum(b) / n)
    means.sort()
    blo, bhi = means[int(0.025 * boot)], means[int(0.975 * boot)]
    p0 = 2 * min(sum(m >= 0 for m in means), sum(m <= 0 for m in means)) / boot

    nulls = []
    for _ in range(null):
        nulls.append(sum(Rs[j] if rnd.random() < 0.5 else fl[j] for j in range(n)) / n)
    nulls.sort()
    p_dir = sum(m >= mean for m in nulls) / null

    grade = {}
    for g in ("A", "B"):
        gg = [(s, o) for s, o in sub if s["_grade"] == g]
        if gg:
            w = sum(1 for _, o in gg if o.resolution == "won")
            grade[g] = {"n": len(gg), "win_pct": round(100 * w / len(gg), 1),
                        "mean_r": round(sum(o.pnl_r for _, o in gg) / len(gg), 3)}

    return {"resolved": n, "win_rate": round(100 * won / n, 1),
            "wilson95": [round(100 * wlo, 1), round(100 * whi, 1)],
            "expectancy": round(mean, 3), "boot95": [round(blo, 3), round(bhi, 3)],
            "p_mean_ne_0": round(p0, 3), "total_r": round(sum(Rs), 2),
            "won": counts["won"], "lost": counts["lost"],
            "invalidated": counts["invalidated"], "expired": counts["expired"],
            "null_mean": round(sum(nulls) / null, 3), "p_engine_ge_random": round(p_dir, 3),
            "grade": grade}


def score(cfg: CalibConfig, state, bars_by, boot=2000, null=1000, seed=0, cutoff=None):
    """Score a calibration on the walk-forward. `cutoff` (YYYY-MM-DD) additionally
    splits resolved setups by issue date into train (before) / holdout (on-or-after)."""
    rnd = random.Random(seed)
    setups = []
    n_snapshots = 0
    for sid, sd in state["stocks"].items():
        seen = {}
        for snap in sd["snapshots"]:
            n_snapshots += 1
            lead = snap.get("lead")
            if lead is None:
                continue
            su = build_setup(lead, snap["last_price"], snap["issued"], sd["ticker"], cfg=cfg)
            if su is None:
                continue
            su = grade_setup(su, snap.get("scen") or [], cfg=cfg)
            if su.grade is None or su.id in seen:
                continue
            seen[su.id] = True
            setups.append({
                "direction": su.direction, "entry": su.entry, "entry_type": su.entry_type,
                "stop": su.stop, "t1": su.t1, "invalidation_level": su.invalidation_level,
                "horizon_bars": _horizon(snap.get("d_pivots_ts")),
                "issued": su.issued, "_sid": str(sid), "_grade": su.grade, "_conf": snap["conf"],
            })

    def res(s):
        b = bars_by[s["_sid"]]
        return resolve_outcome(s, b.loc[b.index > pd.Timestamp(s["issued"])])

    rows = [(s, res(s)) for s in setups]
    rows = [(s, o) for s, o in rows if o.resolution in ("won", "lost", "invalidated", "expired")]
    n = len(rows)
    out = {"n_snapshots": n_snapshots, "graded_setups": len(setups), "resolved": n,
           "cfg": cfg.to_dict()}
    if n == 0:
        out.update({"win_rate": None, "expectancy": None, "total_r": 0.0,
                    "won": 0, "lost": 0, "invalidated": 0, "expired": 0,
                    "grade": {}, "note": "no resolved setups under this calibration"})
        return out

    R = [o.pnl_r for _, o in rows]
    flip_r = [res(_flip(s)).pnl_r for s, _ in rows]
    out.update(_subset_metrics(rows, R, flip_r, list(range(n)), boot, null, rnd))

    if cutoff:
        cut = pd.Timestamp(cutoff)
        tr = [i for i, (s, _) in enumerate(rows) if pd.Timestamp(s["issued"]) < cut]
        ho = [i for i, (s, _) in enumerate(rows) if pd.Timestamp(s["issued"]) >= cut]
        out["splits"] = {
            "cutoff": str(cutoff),
            "train": _subset_metrics(rows, R, flip_r, tr, boot, null, rnd),
            "holdout": _subset_metrics(rows, R, flip_r, ho, boot, null, rnd),
        }
    return out


if __name__ == "__main__":
    st = load_state()
    if st is None:
        sys.exit("no backtest_state.pkl — run: python -m calib.backtest_precompute")
    bars = load_bars(list(st["stocks"].keys()))
    r = score(DEFAULT, st, bars)
    print(json.dumps(r, indent=2))
