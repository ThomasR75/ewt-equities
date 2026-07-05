"""Section 5.2: does a learned weigher find signal the deterministic engine lacks?
Builds a per-candidate feature table on one random half of the tickers and tests
once on the other, then decomposes the held-out AUC to show it is drift (the
direction sign), not wave structure.

    python analysis/gbt_feature_test.py data/prices_anonymized.csv --atr-k 4 --horizon 252
"""
from __future__ import annotations
import argparse, math
import pandas as pd, numpy as np
from ewt.io.walkforward import iter_as_of
from ewt.analyze import analyze_nested
from ewt.signal.scenario import build_scenarios
from ewt.weigh.features import FLAT_COLUMNS, flat_features
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score


def table(df, ids, K, H, start):
    rows = []
    for sid in ids:
        sdf = df[df["stock_id"] == sid][["date", "open", "high", "low", "close", "volume"]].sort_values("date")
        if len(sdf) < 300: continue
        full = sdf.copy(); full.index = pd.to_datetime(full["date"]); close = full["close"].astype(float)
        for b in iter_as_of(sdf, start=start, step="12M"):
            an, _ = analyze_nested(b, pivot_mode="atr", atr_k=K); lp = an["D"].bars.last_price
            pos = close.index.get_indexer([b.as_of], method="pad")[0]
            if pos < 0 or pos + H >= len(close): continue
            fwd = math.copysign(1, close.iloc[pos + H] - close.iloc[pos])
            for sc in build_scenarios(an["D"].counts, last_price=lp):
                if sc.is_residual or sc.primary_count is None: continue
                f = flat_features(sc.primary_count, sc.primary_count.legs[-1].end.price)
                rows.append([1 if sc.direction == fwd else 0] + [f.get(c, 0.0) for c in FLAT_COLUMNS])
    return pd.DataFrame(rows, columns=["y"] + FLAT_COLUMNS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--atr-k", type=float, default=4.0)
    ap.add_argument("--horizon", type=int, default=252); ap.add_argument("--start", default="1998-01-01"); a = ap.parse_args()
    df = pd.read_csv(a.csv); ids = sorted(df["stock_id"].unique())
    tr = table(df, [i for i in ids if i % 2 == 0], a.atr_k, a.horizon, a.start)
    te = table(df, [i for i in ids if i % 2 == 1], a.atr_k, a.horizon, a.start)
    feat = FLAT_COLUMNS; sfeat = [c for c in feat if c != "implied_direction"]
    def auc(cols, tr, te):
        m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=400,
            min_samples_leaf=30, early_stopping=True, random_state=0).fit(tr[cols].values, tr["y"].values)
        return roc_auc_score(te["y"].values, m.predict_proba(te[cols].values)[:, 1])
    print(f"train rows {len(tr)} (base {tr['y'].mean():.3f})  test rows {len(te)} (base {te['y'].mean():.3f})")
    print(f"GBT all features            held-out AUC = {auc(feat, tr, te):.3f}")
    sc = (te['implied_direction'] > 0).astype(float)
    print(f"implied-direction sign alone           AUC = {roc_auc_score(te['y'], sc):.3f}")
    print(f"GBT structure only (no direction)      AUC = {auc(sfeat, tr, te):.3f}")
    ml = te['implied_direction'] > 0; mlt = tr['implied_direction'] > 0
    print(f"GBT structure only, long setups        AUC = {auc(sfeat, tr[mlt], te[ml]):.3f}")
