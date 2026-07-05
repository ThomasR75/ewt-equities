"""Outcome resolution — canonical rules shared by scorecard and tester (spec §18)."""

from .rules import resolve_outcome, OutcomeResult

__all__ = ["resolve_outcome", "OutcomeResult"]
