"""Batch-fit the whole universe -> calib/calib_state.pkl (one pass).

Universe-agnostic: fits every stock listed in records/live/mapping.json (works
for 50 or 500). Thin wrapper over calib.fitter; the dashboard's Run-fit button
calls the same code.

    python -m calib.precompute            # all stocks in the mapping
    python -m calib.precompute 1-50       # a range (optional)
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from calib import fitter


def main(ids):
    t0 = time.time()
    def step(done, total):
        if done % 25 == 0 or done == total:
            print(f"  fitted {done}/{total}  ({time.time()-t0:.0f}s)")
    state = fitter.fit_universe(ids, on_step=step)
    print(f"wrote {fitter.STATE}  ({state['n']} stocks, as_of {state['as_of']}, {time.time()-t0:.0f}s)")


if __name__ == "__main__":
    ids = None
    if len(sys.argv) > 1 and "-" in sys.argv[1]:
        a, z = sys.argv[1].split("-"); ids = list(range(int(a), int(z) + 1))
    main(ids)
