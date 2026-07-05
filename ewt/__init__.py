"""Elliott Wave Signal Generator.

Deterministic, point-in-time Elliott Wave analysis engine.
See EWT_Signal_Generator_Spec_v2.md for the full design.

Milestone M1: data layer (ingest + resample with as_of clamp), pivot layer,
and 3-timeframe pivot rendering. No lookahead: every output is a pure function
of bars with timestamp <= as_of.
"""

__version__ = "0.7.0-m7"
