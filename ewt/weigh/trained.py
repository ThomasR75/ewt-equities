"""Trained tabular weigher (GBT / logistic) loaded from a saved model.

Not an LLM: this is a scikit-learn / LightGBM classifier trained on resolved
candidate scenarios (see train_weigher.py). At inference it emits P(scenario's
implied direction is correct) per candidate, used as the raw weight. Deterministic.
"""
from __future__ import annotations
import joblib
from .features import flat_features, FLAT_COLUMNS


class TrainedWeigher:
    name = "trained"

    def __init__(self, model_path: str):
        bundle = joblib.load(model_path)
        self.model = bundle["model"]
        self.cols = bundle.get("columns", FLAT_COLUMNS)
        self.name = "trained:" + bundle.get("kind", "model")

    def weigh(self, features: list[dict]) -> list[float]:
        # features here are the anonymized candidate dicts; recompute flat rows is
        # not possible without the Count, so the builder passes flat rows via the
        # '_flat' key when available; else fall back to fit_score.
        rows = []
        for f in features:
            flat = f.get("_flat")
            if flat is None:
                return [max(0.0, f.get("fit_score", 0.0)) for f in features]
            rows.append([flat.get(c, 0.0) for c in self.cols])
        try:
            # Named columns: matches how the model was fitted, so no
            # "X does not have valid feature names" warning, and the columns
            # are aligned by name rather than by position.
            import pandas as pd
            p = self.model.predict_proba(pd.DataFrame(rows, columns=self.cols))[:, 1]
        except Exception:
            import warnings
            import numpy as np
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                p = self.model.predict_proba(np.array(rows, dtype=float))[:, 1]
        return [float(max(0.0, x)) for x in p]
