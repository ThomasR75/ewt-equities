"""In-report scorecard (spec §12) — point-in-time status of prior setups.

Reads the per-ticker signals.jsonl, and for every previously issued setup
re-evaluates its status against bars <= as_of using the *canonical* outcome
rules (spec §18). This is display only: it never looks past as_of and computes
no aggregate reliability stats — that is the separate tester's job.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..outcome.rules import resolve_outcome


def load_prior_setups(signals_path: str | Path, before: str) -> list[dict]:
    """Prior records (issued strictly before `before`) that carried a setup."""
    p = Path(signals_path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        setup = rec.get("setup")
        if setup and rec["data"]["as_of"] < before:
            out.append(rec)
    return out


def scorecard(signals_path: str | Path, daily_bars) -> list[dict]:
    """Status rows for prior setups, evaluated against bars <= as_of."""
    as_of = str(daily_bars.as_of.date())
    rows = []
    for rec in load_prior_setups(signals_path, as_of):
        setup = rec["setup"]
        issued = setup["issued"]
        cont = daily_bars.df.loc[daily_bars.df.index >= pd.Timestamp(issued)]
        res = resolve_outcome(setup, cont)
        rows.append({
            "id": setup["id"],
            "issued": issued,
            "direction": setup["direction"],
            "grade": setup.get("grade"),
            "status": res.status,
            "pnl_r": res.pnl_r,
        })
    return rows
