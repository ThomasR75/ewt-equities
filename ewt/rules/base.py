"""Rule abstractions (spec §7).

A motive-wave pattern is judged by two kinds of rule:

  * cardinal  — hard, inviolable filters; a single failure kills the count.
  * guideline — soft 0..1 scores; they shape `Count.score`, never reject.

Each rule declares the scale it validates on. `scale="auto"` resolves to log
when the move spans more than `LOG_SPAN_THRESHOLD` in log units (a multi-fold
move), arithmetic otherwise — the discipline the reference reviewer kept
enforcing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..schemas import Scale

# A move whose log span exceeds this is judged on log scale under scale="auto".
# ln(2) ~ 0.69 => anything bigger than a ~2x move is "big" and goes log.
LOG_SPAN_THRESHOLD = 0.69


@dataclass
class RuleResult:
    name: str
    kind: Literal["cardinal", "guideline"]
    scale: Scale
    passed: bool | None = None   # cardinal
    score: float | None = None   # guideline
    detail: str = ""


def resolve_scale(declared: str, log_span: float) -> Scale:
    if declared in ("lin", "log"):
        return declared  # type: ignore[return-value]
    return "log" if log_span >= LOG_SPAN_THRESHOLD else "lin"
