"""Shared wave-fitting logic for the dashboard (precompute + live re-fit).

`build_record` runs the nested wave analysis for one stock and returns the full
dashboard record (scores, technicals, D/W/M chart series, live Scenario objects).
Used by:
  * calib.precompute        (batch, whole universe -> calib_state.pkl)
  * the server's /api/fit    (universe run in background, or one stock on click)

Importing this module pulls in the trained weigher (joblib + lightgbm); the
server imports it lazily so the app still runs for *viewing* without those deps.
"""
from __future__ import annotations
import os, sys, json, glob, pickle, datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from ewt.io.walkforward import iter_as_of
from ewt.analyze import analyze_nested
from calib.technicals import compute_technicals
from calib.engine_config import get as get_engine, DEFAULT_ENGINE
from ewt import score_config as _SC

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CSV = os.path.join(ROOT, "records/live/prices_live.csv")
MODEL = os.path.join(ROOT, "records/live/models/weigher_gbt.pkl")
MAP = os.path.join(ROOT, "records/live/mapping.json")
STATE = os.path.join(ROOT, "calib/calib_state.pkl")   # legacy single-engine path
STATES_DIR = os.path.join(ROOT, "calib/states")
SPLIT = os.path.join(ROOT, "calib/price_split")
FIT_PROG = os.path.join(ROOT, "calib/fit_progress.json")
MAX_PTS = 1200

_WEIGHERS = {}


def get_weigher(engine=DEFAULT_ENGINE):
    """Weigher for an engine. GBT is lazy-imported so the ATR/deterministic
    engine runs with no joblib/lightgbm."""
    eng = get_engine(engine)
    kind = eng.get("weigher", "gbt")
    if kind not in _WEIGHERS:
        if kind == "gbt":
            from ewt.weigh.trained import TrainedWeigher
            _WEIGHERS[kind] = TrainedWeigher(MODEL)
        else:
            from ewt.weigh.deterministic import DeterministicWeigher
            _WEIGHERS[kind] = DeterministicWeigher()
    return _WEIGHERS[kind]


def state_path(engine=DEFAULT_ENGINE, label=None):
    name = f"{engine}__{label}" if label else engine
    return os.path.join(STATES_DIR, f"{name}.pkl")


def load_mapping():
    return {m["stock_id"]: m for m in json.load(open(MAP))}


def all_ids():
    return [m["stock_id"] for m in json.load(open(MAP))]


def ensure_split(force=False):
    """Split prices_live.csv into per-stock CSVs (fast per-stock reads)."""
    os.makedirs(SPLIT, exist_ok=True)
    stamp = os.path.join(SPLIT, ".stamp")
    fresh = (os.path.exists(stamp) and os.path.getmtime(stamp) >= os.path.getmtime(CSV))
    if fresh and not force:
        return
    for p in glob.glob(os.path.join(SPLIT, "*.csv")):
        os.remove(p)
    df = pd.read_csv(CSV)
    for sid, g in df.groupby("stock_id"):
        g[["date", "open", "high", "low", "close", "volume"]].to_csv(
            os.path.join(SPLIT, f"{sid}.csv"), index=False)
    open(stamp, "w").write(datetime.datetime.now().isoformat())


def load_stock(sid):
    ensure_split()
    p = os.path.join(SPLIT, f"{sid}.csv")
    if os.path.exists(p):
        sdf = pd.read_csv(p)
    else:
        df = pd.read_csv(CSV)
        sdf = df[df["stock_id"] == sid][["date", "open", "high", "low", "close", "volume"]]
    return sdf.sort_values("date").reset_index(drop=True)


def _latest_bars(sdf):
    last = None
    for b in iter_as_of(sdf, start=sdf["date"].iloc[-3], step="1D"):
        last = b
    return last


def _downsample(df, max_pts=MAX_PTS, tail=None):
    if tail:
        df = df.iloc[-tail:]
    stride = max(1, len(df) // max_pts)
    return df.iloc[::stride]


def _tf_chart(analysis, tail, degree_override=None):
    bars = analysis.bars
    dfp = _downsample(bars.df, tail=tail)
    series = [{"d": ts.strftime("%Y-%m-%d"), "c": round(float(r.close), 4),
               "o": round(float(r.open), 4), "h": round(float(r.high), 4),
               "l": round(float(r.low), 4)}
              for ts, r in dfp.iterrows()]
    lead = analysis.lead
    pivots, labels, structure, degree = [], [], None, None
    if lead is not None:
        pv = [lead.legs[0].start] + [l.end for l in lead.legs]
        pivots = [{"ts": p.ts.strftime("%Y-%m-%d"), "price": round(float(p.price), 4)} for p in pv]
        labels = list(lead.labels)
        structure, degree = lead.structure, (degree_override or lead.degree)
    return {"series": series, "pivots": pivots, "labels": labels,
            "structure": structure, "degree": degree}


def scenarios_to_json(scenarios):
    return [{"rank": s.rank, "path": s.path, "weight": round(s.weight, 4),
             "direction": s.direction, "is_residual": s.is_residual,
             "key_levels": [round(float(x), 4) for x in (s.key_levels or [])],
             "invalidation": s.invalidation} for s in scenarios]


def build_record(sid, sdf, minfo, weigher, engine=DEFAULT_ENGINE):
    """Full dashboard record for one stock (or None if too little data)."""
    if len(sdf) < 300:
        return None
    b = _latest_bars(sdf)
    eng = get_engine(engine)
    analyses, nested = analyze_nested(b, pivot_mode=eng.get("pivot_mode", "log"),
                                      atr_k=eng.get("atr_k"), pivot_scale=eng.get("pivot_scale", 1.0))
    D = analyses["D"]
    as_of = str(D.bars.as_of.date())
    last_price = float(D.bars.last_price)
    scen = build_scenarios_cached(D.counts, weigher, last_price)
    directional = [s for s in scen if not s.is_residual and s.direction != 0]
    lead = max(directional, key=lambda s: s.weight, default=None)
    long_score = sum(s.weight for s in scen if not s.is_residual and s.direction == 1)
    short_score = sum(s.weight for s in scen if not s.is_residual and s.direction == -1)
    tech = compute_technicals(sdf["close"])
    degs = (nested.degrees if nested is not None else {})
    charts = {"D": _tf_chart(analyses["D"], 1200, degs.get("D")),
              "W": _tf_chart(analyses["W"], 700, degs.get("W")),
              "M": _tf_chart(analyses["M"], None, degs.get("M"))}
    nr = None
    if nested is not None:
        nr = {"alignment": round(float(nested.alignment), 4),
              "current_wave": nested.current_wave, "degrees": nested.degrees, "note": nested.note}
    return {
        "stock_id": sid, "engine": engine, "ticker": minfo.get("ticker", f"S{sid}"),
        "name": minfo.get("name", ""), "sector": minfo.get("sector", ""),
        "as_of": as_of, "last_price": round(last_price, 4),
        "long_score": round(long_score, 4), "short_score": round(short_score, 4),
        "nested_read": nr, "d_structure": charts["D"]["structure"], "d_degree": charts["D"]["degree"],
        "scenarios_json": scenarios_to_json(scen), "technicals": tech, "charts": charts,
        "_scen_objs": scen, "_lead_obj": lead, "_counts": list(D.counts[:12]),
    }


def build_scenarios_cached(counts, weigher, last_price):
    from ewt.signal.scenario import build_scenarios
    return build_scenarios(counts, weigher=weigher, last_price=last_price)


def fit_one(sid, weigher=None, engine=DEFAULT_ENGINE):
    weigher = weigher or get_weigher(engine)
    mp = load_mapping()
    sdf = load_stock(sid)
    return build_record(sid, sdf, mp.get(sid, {}), weigher, engine)


def _write_prog(done, total, phase="fitting", engine=DEFAULT_ENGINE):
    json.dump({"phase": phase, "engine": engine, "done": done, "total": total,
               "updated": datetime.datetime.now().isoformat(timespec="seconds")},
              open(FIT_PROG, "w"))


def fit_universe(ids=None, on_step=None, engine=DEFAULT_ENGINE, label=None):
    """Fit every stock under `engine`, write calib/states/<engine>.pkl."""
    weigher = get_weigher(engine)
    mp = load_mapping()
    ids = ids or all_ids()
    ensure_split()
    os.makedirs(STATES_DIR, exist_ok=True)
    records = []
    total = len(ids)
    for i, sid in enumerate(ids, 1):
        try:
            rec = build_record(sid, load_stock(sid), mp.get(sid, {}), weigher, engine)
        except Exception as e:
            rec = None
            print(f"  {sid}: fit error {e}")
        if rec is not None:
            records.append(rec)
        _write_prog(i, total, engine=engine)
        if on_step:
            on_step(i, total)
    as_of = max((r["as_of"] for r in records), default=None)
    eng_label = get_engine(engine).get("label", engine)
    state = {"engine": engine, "label": (f"{eng_label} · {label}" if label else eng_label),
             "score_config": _SC.active().to_dict(),
             "built": datetime.datetime.now().isoformat(timespec="seconds"),
             "as_of": as_of, "n": len(records), "records": records}
    pickle.dump(state, open(state_path(engine, label), "wb"))
    _write_prog(total, total, phase="done", engine=engine)
    return state
