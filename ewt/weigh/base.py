"""Weigher protocol + shared normalization into scenarios (spec §10)."""

from __future__ import annotations

from typing import Protocol


class Weigher(Protocol):
    name: str
    def weigh(self, features: list[dict]) -> list[float]:
        """Return one raw, non-negative weight per candidate (need not sum to 1)."""
        ...


def normalize_weights(raw: list[float], best_fit: float) -> tuple[list[float], float]:
    """Normalize raw candidate weights and append a residual 'no clean structure'
    bucket that grows when the best fit is weak (spec §10). Returns (weights,
    residual_weight) all summing to 1.0."""
    raw = [max(0.0, w) for w in raw]
    residual_raw = (1.0 - max(0.0, min(1.0, best_fit))) * 0.6 + 0.05
    total = sum(raw) + residual_raw
    if total <= 0:
        n = len(raw)
        return ([0.0] * n, 1.0)
    return ([w / total for w in raw], residual_raw / total)
