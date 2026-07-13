"""Elliott-Wave calibration platform — local Flask server.

Serves the dashboard and:
  * live setup/grade recompute under any CalibConfig      (/api/calibrate)
  * charts on demand (keeps /api/data light for 500 names) (/api/chart/<id>)
  * run the wave FITTER from the browser: whole universe (background job with
    progress) or a single stock on click                  (/api/fit/*)
  * score a calibration on the walk-forward harness        (/api/backtest)
  * named factor presets                                    (/api/presets)

Viewing needs only flask (+pandas/numpy). Running the fitter additionally needs
the trained-weigher deps (joblib + lightgbm); those are imported lazily so the
app still runs without them.

    python -m calib.app        # http://127.0.0.1:5000
"""
from __future__ import annotations
import os, sys, json, pickle, threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from flask import Flask, jsonify, request, send_from_directory, Response

from ewt.signal.calib import CalibConfig, FACTOR_META, DEFAULT
from calib.engine_config import ENGINES, DEFAULT_ENGINE
from ewt.signal.setup import build_setup
from ewt.signal.grade import grade_setup
from calib import backtest as bt

HERE = os.path.dirname(__file__)
STATE_PATH = os.path.join(HERE, "calib_state.pkl")
PRESETS_PATH = os.path.join(HERE, "presets.json")
FIT_PROG = os.path.join(HERE, "fit_progress.json")

app = Flask(__name__, static_folder=HERE, static_url_path="")

# --- hosted (read-only, password-gated) mode --------------------------------
HOSTED = os.environ.get("EWT_HOSTED", "").lower() not in ("", "0", "false", "no")
AUTH_USER = os.environ.get("HOSTED_USER", "admin")
AUTH_PASS = os.environ.get("HOSTED_PASS")


@app.before_request
def _auth_gate():
    if not HOSTED:
        return
    if not AUTH_PASS:
        return Response("Server not configured: set the HOSTED_PASS secret.", 503)
    a = request.authorization
    if not a or a.username != AUTH_USER or a.password != AUTH_PASS:
        return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="EWT dashboard"'})


def _no_write():
    return jsonify({"error": "disabled in hosted (read-only) mode"}), 403

STATES = {}            # engine -> {records, as_of, built, n}
STATES_DIR = os.path.join(HERE, "states")
_LOCK = threading.RLock()
_FIT = {"running": False, "phase": "idle", "done": 0, "total": 0, "error": None}
_FUND = {"data": {}, "as_of": None, "updated": None}
_FUNDJOB = {"running": False, "done": 0, "total": 0, "error": None}
FUND_PATH = os.path.join(ROOT_LIVE := os.path.join(os.path.dirname(__file__), "..", "records", "live"), "fundamentals.json")


def load_fundamentals():
    global _FUND
    if os.path.exists(FUND_PATH):
        try:
            d = json.load(open(FUND_PATH))
            _FUND = {"data": {int(k): v for k, v in d.get("data", {}).items()},
                     "as_of": d.get("as_of"), "updated": d.get("updated")}
            print(f"loaded fundamentals for {len(_FUND['data'])} stocks (as_of {_FUND['as_of']})")
        except Exception as e:
            print("fundamentals load failed:", e)


def load_states():
    global STATES
    import glob
    STATES = {}
    for pth in sorted(glob.glob(os.path.join(STATES_DIR, "*.pkl"))):
        eng = os.path.basename(pth)[:-4]
        try:
            STATES[eng] = pickle.load(open(pth, "rb"))
        except Exception as e:
            print(f"state {eng} unreadable ({e})")
    # legacy single-file state -> treat as the default engine
    if os.path.exists(STATE_PATH) and DEFAULT_ENGINE not in STATES:
        try:
            st = pickle.load(open(STATE_PATH, "rb")); st.setdefault("engine", DEFAULT_ENGINE)
            STATES[st.get("engine", DEFAULT_ENGINE)] = st
        except Exception as e:
            print(f"legacy calib_state.pkl unreadable ({e})")
    if STATES:
        for eng, st in STATES.items():
            print(f"loaded engine {eng}: {st.get('n')} stocks (as_of {st.get('as_of')})")
    else:
        print("no states yet — run python -m calib.precompute")


def active_engine(name):
    if name in STATES:
        return name
    if DEFAULT_ENGINE in STATES:
        return DEFAULT_ENGINE
    return next(iter(STATES), None)


def records_for(engine):
    st = STATES.get(engine)
    return st["records"] if st else []


load_states()
load_fundamentals()

_BT = {"state": None, "bars": None, "baseline": None, "lock": threading.Lock()}


def _fitter():
    """Lazy import so the app runs without joblib/lightgbm when not fitting."""
    from calib import fitter
    return fitter


# --- setup/grade recompute -------------------------------------------------
def _setup_dict(su):
    if su is None:
        return None
    return {"id": su.id, "grade": su.grade, "direction": su.direction,
            "entry": su.entry, "stop": su.stop, "t1": su.t1, "t2": su.t2,
            "rr": su.rr, "invalidation_level": su.invalidation_level,
            "invalidation_rule": su.invalidation_rule}


def calibrate_record(rec, cfg):
    lead = rec.get("_lead_obj"); scen = rec.get("_scen_objs") or []
    out = {"stock_id": rec["stock_id"], "signal": "none", "grade": None,
           "setup": None, "setup_reason": None}
    if lead is None:
        out["setup_reason"] = "no directional structure"; return out
    su = build_setup(lead, rec["last_price"], rec["as_of"], rec["ticker"], cfg=cfg)
    if su is None:
        out["setup_reason"] = "geometry rejected (risk/chase filter)"; return out
    su = grade_setup(su, scen, cfg=cfg)
    out["setup"] = _setup_dict(su)
    if su.grade is not None:
        out["signal"] = su.direction; out["grade"] = su.grade
    else:
        out["setup_reason"] = f"R/R {su.rr} below floor {cfg.rr_floor}"
    return out


def _static_record(rec):
    return {k: v for k, v in rec.items() if not k.startswith("_") and k != "charts"}


def _grade_counts(recs):
    g = lambda k, v: sum(1 for r in recs if r["calib"].get(k) == v)
    return {"A": g("grade", "A"), "B": g("grade", "B"),
            "long": g("signal", "long"), "short": g("signal", "short"),
            "with_geometry": sum(1 for r in recs if r["calib"]["setup"] is not None),
            "total": len(recs)}


# --- routes ----------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.route("/api/factors")
def factors():
    meta = [{"key": k, "label": lb, "min": mn, "max": mx, "step": st, "group": g}
            for (k, lb, mn, mx, st, g) in FACTOR_META]
    return jsonify({"meta": meta, "defaults": DEFAULT.to_dict(), "ext_ratios": list(DEFAULT.ext_ratios)})


@app.route("/api/rules")
def rules():
    from calib.rules_catalog import build_catalog
    return jsonify(build_catalog())


@app.route("/api/config")
def config():
    return jsonify({"hosted": HOSTED, "read_only": HOSTED})


@app.route("/api/data")
def data():
    engine = active_engine(request.args.get("engine", DEFAULT_ENGINE))
    with _LOCK:
        recs = []
        for r in records_for(engine):
            d = _static_record(r); d["calib"] = calibrate_record(r, DEFAULT)
            d["fund"] = _FUND["data"].get(r["stock_id"]); recs.append(d)
        st = STATES.get(engine, {})
        return jsonify({"engine": engine, "as_of": st.get("as_of"), "built": st.get("built"),
                        "n": len(recs), "records": recs, "summary": _grade_counts(recs),
                        "fund_as_of": _FUND["as_of"], "fund_updated": _FUND["updated"]})


@app.route("/api/engines")
def engines():
    out = []
    for name, spec in ENGINES.items():
        if name in STATES:
            st = STATES[name]
            out.append({"name": name, "label": spec["label"], "as_of": st.get("as_of"),
                        "n": st.get("n"), "weigher": spec["weigher"], "pivot_mode": spec["pivot_mode"]})
    for name in STATES:  # any engine not in the known list
        if name not in ENGINES:
            st = STATES[name]
            out.append({"name": name, "label": name, "as_of": st.get("as_of"), "n": st.get("n")})
    default = DEFAULT_ENGINE if DEFAULT_ENGINE in STATES else (out[0]["name"] if out else None)
    return jsonify({"engines": out, "default": default})


@app.route("/api/chart/<int:sid>")
def chart(sid):
    engine = active_engine(request.args.get("engine", DEFAULT_ENGINE))
    with _LOCK:
        rec = next((r for r in records_for(engine) if r["stock_id"] == sid), None)
    if rec is None:
        return jsonify({"error": "unknown stock"}), 404
    return jsonify({"stock_id": sid, "ticker": rec["ticker"], "charts": rec.get("charts", {})})


@app.route("/api/calibrate", methods=["POST"])
def calibrate():
    body = request.get_json(force=True) or {}
    engine = active_engine(body.get("engine", DEFAULT_ENGINE))
    cfg = CalibConfig.from_dict(body)
    with _LOCK:
        res = {r["stock_id"]: calibrate_record(r, cfg) for r in records_for(engine)}
    summary = _grade_counts([{"calib": v} for v in res.values()])
    return jsonify({"results": res, "summary": summary})


# --- fitter ----------------------------------------------------------------
@app.route("/api/fit/status")
def fit_status():
    weigher_ok, msg = True, None
    try:
        import joblib, lightgbm  # noqa: F401
    except Exception as e:
        weigher_ok, msg = False, f"fitter needs joblib+lightgbm ({e})"
    prog = {}
    if os.path.exists(FIT_PROG):
        try:
            prog = json.load(open(FIT_PROG))
        except Exception:
            prog = {}
    return jsonify({"running": _FIT["running"], "phase": _FIT["phase"],
                    "done": _FIT["done"], "total": _FIT["total"], "error": _FIT["error"],
                    "weigher_available": weigher_ok, "weigher_msg": msg,
                    "n_loaded": sum(st.get("n", 0) for st in STATES.values()),
                    "engines_loaded": list(STATES), "progress": prog})


def _run_universe_fit(ids, engine):
    global _FIT
    try:
        fitter = _fitter()

        def on_step(done, total):
            _FIT.update(done=done, total=total, phase="fitting")
        _FIT.update(running=True, phase="fitting", done=0, total=len(ids or fitter.all_ids()), error=None)
        fitter.fit_universe(ids, on_step=on_step, engine=engine)
        load_states()
        _FIT.update(running=False, phase="done")
    except Exception as e:
        _FIT.update(running=False, phase="error", error=str(e))
        print("universe fit error:", e)


@app.route("/api/fit/universe", methods=["POST"])
def fit_universe():
    if HOSTED:
        return _no_write()
    if _FIT["running"]:
        return jsonify({"error": "a fit is already running"}), 409
    body = request.get_json(silent=True) or {}
    ids = body.get("ids")  # optional list; None = all in mapping
    engine = body.get("engine", DEFAULT_ENGINE)
    t = threading.Thread(target=_run_universe_fit, args=(ids, engine), daemon=True)
    t.start()
    return jsonify({"started": True, "engine": engine})


@app.route("/api/fit/stock", methods=["POST"])
def fit_stock():
    if HOSTED:
        return _no_write()
    body = request.get_json(force=True) or {}
    sid = body.get("stock_id")
    engine = active_engine(body.get("engine", DEFAULT_ENGINE))
    if sid is None:
        return jsonify({"error": "stock_id required"}), 400
    try:
        fitter = _fitter()
        rec = fitter.fit_one(int(sid), engine=engine)
    except Exception as e:
        return jsonify({"error": f"fit failed: {e}"}), 400
    if rec is None:
        return jsonify({"error": "not enough data to fit"}), 400
    with _LOCK:
        recs = records_for(engine)
        for i, r in enumerate(recs):
            if r["stock_id"] == int(sid):
                recs[i] = rec
                break
        else:
            recs.append(rec)
        out = _static_record(rec); out["calib"] = calibrate_record(rec, DEFAULT)
    return jsonify({"record": out})


# --- fundamentals -----------------------------------------------------------
@app.route("/api/fundamentals/status")
def fundamentals_status():
    yf_ok = True
    try:
        import yfinance  # noqa: F401
    except Exception:
        yf_ok = False
    return jsonify({"running": _FUNDJOB["running"], "done": _FUNDJOB["done"],
                    "total": _FUNDJOB["total"], "error": _FUNDJOB["error"],
                    "yfinance_available": yf_ok, "n": len(_FUND["data"]),
                    "as_of": _FUND["as_of"], "updated": _FUND["updated"]})


def _run_fund_update(resume):
    global _FUNDJOB
    try:
        from calib import fetch_fundamentals as ff
        n_total = len(json.load(open(FUND_PATH.replace("fundamentals.json", "mapping.json"))))
        _FUNDJOB.update(running=True, done=0, total=n_total, error=None)
        def on_step(i, total):
            _FUNDJOB.update(done=i, total=total)
        ff.fetch_all(on_step=on_step, resume=resume)
        load_fundamentals()
        _FUNDJOB.update(running=False)
    except Exception as e:
        _FUNDJOB.update(running=False, error=str(e))
        print("fundamentals update error:", e)


@app.route("/api/fundamentals/update", methods=["POST"])
def fundamentals_update():
    if HOSTED:
        return _no_write()
    if _FUNDJOB["running"]:
        return jsonify({"error": "an update is already running"}), 409
    resume = bool((request.get_json(silent=True) or {}).get("resume", False))
    threading.Thread(target=_run_fund_update, args=(resume,), daemon=True).start()
    return jsonify({"started": True})


# --- backtest --------------------------------------------------------------
@app.route("/api/backtest/status")
def backtest_status():
    prog = {}
    p = os.path.join(HERE, "backtest_progress.json")
    if os.path.exists(p):
        prog = json.load(open(p))
    return jsonify({"ready": os.path.exists(bt.STATE_PATH), "n_done": prog.get("n_done", 0),
                    "target": prog.get("target", 50), "built": prog.get("updated")})


@app.route("/api/backtest", methods=["POST"])
def backtest():
    if HOSTED:
        return _no_write()
    with _BT["lock"]:
        if _BT["state"] is None:
            st = bt.load_state()
            if st is None:
                return jsonify({"error": "backtest cache not built — run "
                                "python -m calib.backtest_precompute then --merge"}), 400
            _BT["state"] = st; _BT["bars"] = bt.load_bars(list(st["stocks"].keys()))
        st = _BT["state"]
        if _BT["baseline"] is None:
            _BT["baseline"] = bt.score(DEFAULT, st, _BT["bars"])
        cfg = CalibConfig.from_dict(request.get_json(force=True) or {})
        result = bt.score(cfg, st, _BT["bars"])
    return jsonify({"result": result, "baseline": _BT["baseline"],
                    "span": {"start": st.get("start"), "step": st.get("step"),
                             "n_stocks": st.get("n", len(st["stocks"]))}})


# --- presets ---------------------------------------------------------------
BUILTIN = [
    {"name": "Default (v1.2)", "builtin": True, "factors": {}},
    {"name": "Loose — explore", "builtin": True,
     "factors": {"rr_floor": 1.2, "near_max": 0.35, "tol_k": 0.5, "confirm_lead_w": 0.4, "rr_comfort": 3.5}},
    {"name": "Strict — high bar", "builtin": True,
     "factors": {"rr_floor": 3.0, "near_max": 0.08, "confirm_lead_w": 0.6, "opp_alt_w": 0.25, "rr_comfort": 3.5}},
]


def _load_presets():
    if os.path.exists(PRESETS_PATH):
        try:
            return json.load(open(PRESETS_PATH))
        except Exception:
            return []
    return []


def _save_presets(user):
    json.dump(user, open(PRESETS_PATH, "w"), indent=2)


@app.route("/api/presets", methods=["GET"])
def presets_list():
    return jsonify({"builtin": BUILTIN, "user": _load_presets(), "defaults": DEFAULT.to_dict()})


@app.route("/api/presets", methods=["POST"])
def presets_save():
    body = request.get_json(force=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    user = [p for p in _load_presets() if p["name"] != name]
    user.append({"name": name, "builtin": False, "factors": body.get("factors") or {}})
    _save_presets(user)
    return jsonify({"ok": True, "user": user})


@app.route("/api/presets/<name>", methods=["DELETE"])
def presets_delete(name):
    user = [p for p in _load_presets() if p["name"] != name]
    _save_presets(user)
    return jsonify({"ok": True, "user": user})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0" if HOSTED else "127.0.0.1", port=port, debug=False, threaded=True)
