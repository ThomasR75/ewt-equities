"""Signal layer (spec §10/§11): scenarios, setup, grade — the % and the signal."""

from .scenario import build_scenarios, implied_next
from .setup import build_setup
from .grade import grade_setup

__all__ = ["build_scenarios", "implied_next", "build_setup", "grade_setup"]
