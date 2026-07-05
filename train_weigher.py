"""Train a tabular scenario weigher (logistic baseline or gradient-boosted trees)
on the table from build_training_table.py, with a date-based train/holdout split,
isotonic calibration, and Brier / AUC on the holdout.

    python train_weigher.py records\\train_table.csv --kind logistic --cutoff 2010-01-01
    python train_weigher.py records\\train_table.csv --kind gbt      --cutoff 2010-01-01

Saves records\\models\\weigher_<kind>.pkl for ewt.weigh.trained.TrainedWeigher.
Always fit logistic first as the honest baseline; only prefer gbt if it beats it
on holdout Brier.
"""
from __future__ import annotations
import argparse, os
import numpy as np
import pandas as pd
import joblib
from ewt.weigh.features import FLAT_COLUMNS
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, roc_auc_score


def make_estimator(kind):
    if kind == "logistic":
        return make_pipeline(StandardScaler(),
                             LogisticRegression(max_iter=2000, class_weight="balanced"))
    if kind == "gbt":
        try:
            from lightgbm import LGBMClassifier
            return LGBMClassifier(n_estimators=300, learning_rate=0.05, max_depth=4,
                                  class_weight="balanced", verbose=-1)
        except Exception:
            from sklearn.ensemble import HistGradientBoostingClassifier
            return HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=300)
    raise SystemExit(f"unknown kind {kind}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("table"); ap.add_argument("--kind", default="logistic", choices=["logistic", "gbt"])
    ap.add_argument("--cutoff", default="2010-01-01"); ap.add_argument("--out", default=None)
    args = ap.parse_args()

    df = pd.read_csv(args.table)
    df["issued"] = pd.to_datetime(df["issued"])
    cols = [c for c in FLAT_COLUMNS if c in df.columns]
    tr = df[df["issued"] < pd.Timestamp(args.cutoff)]
    ho = df[df["issued"] >= pd.Timestamp(args.cutoff)]
    print(f"rows: {len(df)}  train {len(tr)}  holdout {len(ho)}  base rate {df['y'].mean():.3f}")
    if len(tr) < 50 or tr["y"].nunique() < 2:
        raise SystemExit("not enough training rows / one class only")

    Xtr, ytr = tr[cols].to_numpy(float), tr["y"].to_numpy(int)
    est = make_estimator(args.kind)
    model = CalibratedClassifierCV(est, method="isotonic", cv=3)
    model.fit(Xtr, ytr)

    if len(ho) >= 20 and ho["y"].nunique() == 2:
        Xho, yho = ho[cols].to_numpy(float), ho["y"].to_numpy(int)
        p = model.predict_proba(Xho)[:, 1]
        base = np.full_like(p, ho["y"].mean(), dtype=float)
        print(f"HOLDOUT  Brier {brier_score_loss(yho, p):.4f}  (baseline {brier_score_loss(yho, base):.4f})"
              f"  AUC {roc_auc_score(yho, p):.3f}")
    else:
        print("holdout too small for metrics")

    out = args.out or f"records/models/weigher_{args.kind}.pkl"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    joblib.dump({"model": model, "columns": cols, "kind": args.kind}, out)
    print("saved", out)


if __name__ == "__main__":
    main()
