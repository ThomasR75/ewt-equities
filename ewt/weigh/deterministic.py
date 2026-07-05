"""Deterministic weigher: the v1 score-derived weights (spec §10 default)."""

from __future__ import annotations


class DeterministicWeigher:
    name = "deterministic"

    def __init__(self, gamma: float = 1.5):
        self.gamma = gamma

    def weigh(self, features: list[dict]) -> list[float]:
        return [max(0.0, f.get("fit_score", 0.0)) ** self.gamma for f in features]
