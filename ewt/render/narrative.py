"""Headline-thesis template (spec §2). Deterministic fill; LLM swap-in deferred.

Produces the one-paragraph 'Headline.' from the nested read + signal — the same
slot the reference reports open with. The `NarrativeWriter` seam stays mechanical
in v1 (no model calls).
"""

from __future__ import annotations


def headline(ticker: str, rec: dict) -> str:
    nr = rec.get("nested_read")
    sig = rec["signal"]
    conf = rec["confidence_pct"]
    last = rec["data"]["last_price"]
    if nr is None:
        return (f"{ticker} — no clean multi-degree structure as of "
                f"{rec['data']['as_of']} (last {last}). Conviction is low; "
                f"weight sits in the residual bucket.")
    degs, cw = nr["degrees"], nr["current_wave"]
    base = (f"{ticker} reads as {nr['note'].split(' ⊃ ')[0].split(':',1)[1]} "
            f"at {degs['M']} degree, with the daily completing a "
            f"{cw['D']}-wave at {degs['D']} degree (last {last}).")
    if sig == "none":
        tail = (f" The lead interpretation carries {conf}% weight, but no trade "
                f"clears the reward/risk floor — this is a read, not a setup.")
    else:
        s = rec["setup"]
        tail = (f" Lead weight {conf}%; a grade-{rec['grade']} {sig} triggers at "
                f"{s['entry']} (stop {s['stop']}, T1 {s['t1']}, R/R {s['rr']}).")
    return base + tail
