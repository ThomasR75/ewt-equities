"""Walk-forward analysis cache for the calibration backtest.

Reproduces the reliability study's walk-forward (step 12M) but caches the live
Scenario objects at each as_of, so any CalibConfig can be *scored* afterward in
under a second — without re-running the wave engine.

Writes one shard per stock (calib/bt_shards/{sid}.pkl) so it is fully resumable
and parallel-safe. Merge the shards into calib/backtest_state.pkl when done.

    python -m calib.backtest_precompute 1-25      # worker A
    python -m calib.backtest_precompute 26-50     # worker B  (run concurrently)
    python -m calib.backtest_precompute --merge   # build backtest_state.pkl
"""
from __future__ import annotations
import os, sys, glob, json, pickle, datetime, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from ewt.io.walkforward import iter_as_of
from ewt.analyze import analyze_nested
from ewt.weigh.trained import TrainedWeigher
from ewt import score_config as SC
from ewt.signal.scenario import build_scenarios

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CSV = os.path.join(ROOT, "records/live/prices_live.csv")
MODEL = os.path.join(ROOT, "records/live/models/weigher_gbt.pkl")
MAP = os.path.join(ROOT, "records/live/mapping.json")
SHARDS = os.path.join(ROOT, "calib/bt_shards")
OUT = os.path.join(ROOT, "calib/backtest_state.pkl")
LABEL = None
PROG = os.path.join(ROOT, "calib/backtest_progress.json")
START, STEP = "1998-01-01", "12M"


def _dpivots(analysis):
    lead = analysis.lead
    if lead is None:
        return []
    pv = [lead.legs[0].start] + [l.end for l in lead.legs]
    return [p.ts.strftime("%Y-%m-%d") for p in pv]


def _universe_size():
    try:
        return len(json.load(open(MAP)))
    except Exception:
        return 0


def _write_progress():
    done = sorted(int(os.path.basename(p)[:-4]) for p in glob.glob(os.path.join(SHARDS, "*.pkl")))
    json.dump({"done": done, "n_done": len(done), "target": _universe_size(),
               "updated": datetime.datetime.now().isoformat(timespec="seconds")},
              open(PROG, "w"))
    return len(done)


def merge():
    stocks = {}
    for p in sorted(glob.glob(os.path.join(SHARDS, "*.pkl"))):
        sid = os.path.basename(p)[:-4]
        stocks[sid] = pickle.load(open(p, "rb"))
    state = {"built": datetime.datetime.now().isoformat(timespec="seconds"),
             "start": START, "step": STEP, "n": len(stocks), "stocks": stocks}
    pickle.dump(state, open(OUT, "wb"))
    print(f"merged {len(stocks)} stocks -> {OUT}")


def main(ids):
    os.makedirs(SHARDS, exist_ok=True)
    mp = {m["stock_id"]: m["ticker"] for m in json.load(open(MAP))}
    weigher = TrainedWeigher(MODEL)
    for sid in ids:
        shard = os.path.join(SHARDS, f"{sid}.pkl")
        if os.path.exists(shard):
            print("skip", sid); continue
        pf = os.path.join(ROOT, "calib/bt_prices", f"{sid}.csv")
        src = pf if os.path.exists(pf) else CSV
        sdf = pd.read_csv(src)
        if "stock_id" in sdf.columns:
            sdf = sdf[sdf["stock_id"] == sid]
        sdf = sdf[["date", "open", "high", "low", "close", "volume"]].sort_values("date").reset_index(drop=True)
        if len(sdf) < 300:
            continue
        snaps = []
        t0 = time.time()
        for b in iter_as_of(sdf, start=START, step=STEP):
            analyses, nested = analyze_nested(b)
            D = analyses["D"]
            scen = build_scenarios(D.counts, weigher=weigher, last_price=float(D.bars.last_price))
            directional = [s for s in scen if not s.is_residual and s.direction != 0]
            lead = max(directional, key=lambda s: s.weight, default=None)
            conf = round((lead.weight * 100) if lead else 0.0, 2)
            snaps.append({"issued": str(D.bars.as_of.date()), "last_price": float(D.bars.last_price),
                          "conf": conf, "d_pivots_ts": _dpivots(D), "scen": scen, "lead": lead})
        pickle.dump({"ticker": mp.get(sid, f"S{sid}"), "snapshots": snaps}, open(shard, "wb"))
        n = _write_progress()
        print(f"{sid} {mp.get(sid)}: {len(snaps)} snapshots in {time.time()-t0:.1f}s ({n}/50 shards)")


def _apply_label(label, score):
    """Point the shard dir + output at a labelled walk-forward cache, and set
    the scoring knobs the sweep will run under."""
    global SHARDS, OUT, LABEL
    LABEL = label
    if label:
        SHARDS = os.path.join(ROOT, f"calib/bt_shards__{label}")
        OUT = os.path.join(ROOT, f"calib/backtest_state__{label}.pkl")
    if score:
        d = {}
        for tok in score.split(","):
            if "=" in tok:
                k, v = tok.split("=", 1); d[k.strip()] = float(v)
        cfg = SC.ScoreConfig.from_dict(d)
        SC.set_active(cfg)
        print("custom scoring:", {k: v for k, v in cfg.to_dict().items()
                                  if v != getattr(SC.DEFAULT, k)})


if __name__ == "__main__":
    argv = sys.argv[1:]
    label = score = None
    rng = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--label":
            label = argv[i + 1]; i += 2; continue
        if a == "--score":
            score = argv[i + 1]; i += 2; continue
        if "-" in a and a[0].isdigit():
            rng = a
        i += 1
    _apply_label(label, score)
    if "--merge" in argv:
        merge()
    elif rng:
        a, z = rng.split("-"); main(list(range(int(a), int(z) + 1)))
    else:
        print("usage: python -m calib.backtest_precompute 1-60 [--label X --score k=v,...]  |  --merge [--label X]")
