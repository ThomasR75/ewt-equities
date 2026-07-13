"""Batch-fit the universe into per-engine states.

    python -m calib.precompute                    # build BOTH engines (default)
    python -m calib.precompute --engine atr_det   # just the ATR/deterministic read (no ML deps)
    python -m calib.precompute --engine gbt_log 1-50

Writes calib/states/<engine>.pkl. gbt_log needs joblib+lightgbm+sklearn (the
trained weigher); atr_det needs none.
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from calib import fitter
from calib.engine_config import names as engine_names


def build(engine, ids):
    t0 = time.time()
    def step(done, total):
        if done % 25 == 0 or done == total:
            print(f"  [{engine}] fitted {done}/{total}  ({time.time()-t0:.0f}s)")
    state = fitter.fit_universe(ids, on_step=step, engine=engine)
    print(f"[{engine}] wrote {fitter.state_path(engine)}  "
          f"({state['n']} stocks, as_of {state['as_of']}, {time.time()-t0:.0f}s)")


def main():
    args = sys.argv[1:]
    engine = "both"
    ids = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--engine":
            engine = args[i + 1]; i += 2; continue
        if "-" in a and a[0].isdigit():
            lo, hi = a.split("-"); ids = list(range(int(lo), int(hi) + 1))
        i += 1
    engines = engine_names() if engine == "both" else [engine]
    for eng in engines:
        build(eng, ids)


if __name__ == "__main__":
    main()
