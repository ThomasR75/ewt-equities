"""Scenario weighing (spec §10). The deferred LLM swap-in lives here.

A Weigher takes the engine's candidate interpretations (as leak-free, anonymized
relative features) and returns a raw weight per candidate. The deterministic
weigher reproduces the v1 score logic; the Ollama weigher asks a local model.
Both feed the same normalization (residual bucket, sums to 1).
"""

from .base import Weigher, normalize_weights
from .deterministic import DeterministicWeigher
from .features import candidate_features

__all__ = ["Weigher", "normalize_weights", "DeterministicWeigher", "candidate_features"]
