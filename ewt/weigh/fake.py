"""Deterministic fake weigher for offline tests (no Ollama needed).

Mimics an 'opinionated' weigher: it leans on the implied direction and fit so
that its output differs from the pure-fit deterministic weigher, exercising the
full weigher->scenario plumbing without a server.
"""

from __future__ import annotations


class FakeWeigher:
    name = "fake"

    def weigh(self, features: list[dict]) -> list[float]:
        out = []
        for f in features:
            base = max(0.05, f.get("fit_score", 0.0))
            # pretend the model distrusts shorts a bit (just to differ from default)
            if f.get("implied_direction", 0) < 0:
                base *= 0.5
            out.append(base)
        return out
