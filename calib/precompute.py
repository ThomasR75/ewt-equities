"""Batch-fit the universe into per-engine (and optionally custom-scored) states.

    python -m calib.precompute                       # both engines, default scoring
    python -m calib.precompute --engine atr_det      # one engine (no ML deps)
    python -m calib.precompute --engine atr_det --label loosecorr \
        --score corr_size_base=0.2,w_fib_w3=1.6      # a faithful custom-scored re-fit

A --label writes calib/states/<engine>__<label>.pkl, which shows up as its own
selectable read in the dashboard's engine dropdown — so you can compare a tuned
scoring set against the baseline side by side.

--score keys: see ewt/score_config.py (guideline weights w_*, diagonal_penalty,
span_bonus, recency_tau_frac, corr_size_base/range/sat, corr_tol).
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from calib import fitter
from calib.engine_config import names as engine_names
from ewt import score_config as SC


def _parse_score(arg):
    if not arg:
        return None
    d = {}
    for tok in arg.split(","):
        if "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        d[k.strip()] = float(v)
    return SC.ScoreConfig.from_dict(d)


def build(engine, ids, label):
    t0 = time.time()
    def step(done, total):
        if done % 25 == 0 or done == total:
            print(f"  [{engine}{'/'+label if label else ''}] fitted {done}/{total}  ({time.time()-t0:.0f}s)")
    state = fitter.fit_universe(ids, on_step=step, engine=engine, label=label)
    print(f"[{engine}] wrote {fitter.state_path(engine, label)}  "
          f"({state['n']} stocks, as_of {state['as_of']}, {time.time()-t0:.0f}s)")


def main():
    args = sys.argv[1:]
    engine, ids, label, score = "both", None, None, None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--engine":
            engine = args[i + 1]; i += 2; continue
        if a == "--label":
            label = args[i + 1]; i += 2; continue
        if a == "--score":
            score = args[i + 1]; i += 2; continue
        if "-" in a and a[0].isdigit():
            lo, hi = a.split("-"); ids = list(range(int(lo), int(hi) + 1))
        i += 1

    cfg = _parse_score(score)
    if cfg is not None:
        SC.set_active(cfg)
        print("custom scoring:", {k: v for k, v in cfg.to_dict().items()
                                  if v != getattr(SC.DEFAULT, k)})
    engines = engine_names() if engine == "both" else [engine]
    for eng in engines:
        build(eng, ids, label)
    SC.set_active(None)


if __name__ == "__main__":
    main()
