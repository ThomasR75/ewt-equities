"""Versioned SignalRecord schema + validation (spec §5.1).

Self-contained: a tester needs only this JSON plus the continuation bars to
score the call. `data_hash` + `engine_version` make every reliability number
reproducible and attributable.
"""

from __future__ import annotations

SCHEMA_VERSION = 1

# Required top-level keys and required sub-keys of `data`.
_REQUIRED = ["schema_version", "engine_version", "generated_at", "data",
             "signal", "grade", "confidence_pct", "setup", "scenarios",
             "pivot_level", "counts"]
_REQUIRED_DATA = ["ticker", "source", "data_hash", "timeframe_base", "as_of",
                  "as_of_is_partial", "first_bar", "bar_count", "last_price"]


class SignalRecord(dict):
    """A plain dict subclass so it serializes directly to JSON."""


def validate_record(rec: dict) -> list[str]:
    """Return a list of problems; empty means schema-valid."""
    errs = []
    for k in _REQUIRED:
        if k not in rec:
            errs.append(f"missing top-level key: {k}")
    if "data" in rec:
        for k in _REQUIRED_DATA:
            if k not in rec["data"]:
                errs.append(f"missing data.{k}")
    if rec.get("signal") not in ("long", "short", "none"):
        errs.append(f"bad signal: {rec.get('signal')}")
    if rec.get("grade") not in ("A+", "A", "B", None):
        errs.append(f"bad grade: {rec.get('grade')}")
    sc = rec.get("scenarios")
    if isinstance(sc, list) and sc:
        total = round(sum(s.get("weight", 0) for s in sc), 3)
        if abs(total - 1.0) > 0.02:
            errs.append(f"scenario weights sum to {total}, not 1.0")
    cp = rec.get("confidence_pct")
    if cp is not None and not (0 <= cp <= 100):
        errs.append(f"confidence_pct out of range: {cp}")
    return errs


import hashlib as _hashlib
import json as _json


def canonical_record(rec: dict) -> dict:
    """The record minus the human-only `generated_at` field (spec §15.5).

    Two runs on identical input + engine_version produce identical canonical
    records, which is what makes any reliability number reproducible.
    """
    r = dict(rec)
    r.pop("generated_at", None)
    return r


def record_hash(rec: dict) -> str:
    """Stable sha256 of the canonical record (sorted keys)."""
    payload = _json.dumps(canonical_record(rec), sort_keys=True,
                          separators=(",", ":")).encode("utf-8")
    return _hashlib.sha256(payload).hexdigest()
