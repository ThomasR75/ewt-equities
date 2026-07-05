"""Local-LLM weigher via Ollama (spec §10 swap-in).

Calls a local Ollama server (default http://localhost:11434) at temperature 0
with JSON output, and CACHES every response keyed by sha256(model + prompt). The
cache makes the backtest (a) reproducible and (b) cheap on re-runs — identical
anonymized features return the identical cached weights without re-calling the model.

The model only ever sees leak-free relative features (ewt.weigh.features), never
ticker/date/price — so it cannot use training-data lookahead.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

SYSTEM = (
    "You are a probability weigher for Elliott Wave scenario candidates. "
    "You receive a list of candidate wave interpretations described ONLY by "
    "anonymized, relative structural features (no ticker, date, or price). For "
    "each candidate, output a single non-negative weight reflecting how likely "
    "that interpretation's implied next move is correct. Consider structure "
    "type, degree, leg proportions, Fibonacci fit, and where price sits. Return "
    "STRICT JSON: {\"weights\": [w1, w2, ...]} with exactly one number per "
    "candidate, in order. No prose."
)


class OllamaWeigher:
    name = "ollama"

    def __init__(self, model: str = "qwen2.5:14b-instruct",
                 url: str = "http://localhost:11434",
                 cache_dir: str = "records/llm_cache", timeout: float = 120.0):
        self.model = model
        self.url = url.rstrip("/")
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout

    def _key(self, prompt: str) -> str:
        return hashlib.sha256((self.model + "\x00" + prompt).encode()).hexdigest()

    def _cached(self, key: str):
        p = self.cache / f"{key}.json"
        if p.exists():
            return json.loads(p.read_text())
        return None

    def _store(self, key: str, val) -> None:
        (self.cache / f"{key}.json").write_text(json.dumps(val))

    def weigh(self, features: list[dict]) -> list[float]:
        n = len(features)
        if n == 0:
            return []
        clean = [{k: v for k, v in f.items() if not k.startswith("_")} for f in features]
        prompt = json.dumps({"candidates": clean}, sort_keys=True, separators=(",", ":"))
        key = self._key(prompt)
        cached = self._cached(key)
        if cached is not None:
            return self._coerce(cached, n)

        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "seed": 0},
        }
        req = urllib.request.Request(
            f"{self.url}/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            resp = json.loads(r.read().decode())
        content = resp["message"]["content"]
        try:
            weights = json.loads(content).get("weights", [])
        except Exception:
            weights = []
        self._store(key, weights)
        return self._coerce(weights, n)

    @staticmethod
    def _coerce(weights, n: int) -> list[float]:
        out = []
        for i in range(n):
            try:
                out.append(max(0.0, float(weights[i])))
            except Exception:
                out.append(0.0)
        return out if any(out) else [1.0] * n  # fall back to uniform if model failed
