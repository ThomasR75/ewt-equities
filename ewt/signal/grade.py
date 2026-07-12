"""Grading rubric + R/R gate (spec §11).

  A   premier wave position AND structural confirmation AND R/R >= floor.
  B   R/R >= floor but held back: modest conviction, a live alternate ~>=30%,
      or R/R near the 2:1 floor.
  None  fails the R/R gate -> "not a setup".

All thresholds live in CalibConfig (ewt/signal/calib.py); defaults reproduce
the frozen behaviour. Deterministic: derived from the setup's R/R, the lead
scenario weight, and whether a strong opposing alternate exists.
"""

from __future__ import annotations

from ..schemas import Scenario, Setup
from .calib import CalibConfig, DEFAULT as _DEFAULT_CFG


def grade_setup(setup: Setup, scenarios: list[Scenario],
                cfg: CalibConfig | None = None) -> Setup:
    cfg = cfg or _DEFAULT_CFG
    if setup is None:
        return setup
    if setup.rr < cfg.rr_floor:
        setup.grade = None
        return setup

    lead = max((s for s in scenarios if not s.is_residual),
               key=lambda s: s.weight, default=None)
    lead_w = lead.weight if lead else 0.0
    # Strongest alternate in the opposite direction.
    opp = max((s.weight for s in scenarios
               if not s.is_residual and s.direction == -setup_direction(setup)),
              default=0.0)

    confirmed = lead_w >= cfg.confirm_lead_w
    held_back = (lead_w < cfg.confirm_lead_w) or (opp >= cfg.opp_alt_w) or (setup.rr < cfg.rr_comfort)

    if confirmed and not held_back:
        setup.grade = "A"
    else:
        setup.grade = "B"
    setup.frozen["grade"] = setup.grade
    return setup


def setup_direction(setup: Setup) -> int:
    return 1 if setup.direction == "long" else -1
