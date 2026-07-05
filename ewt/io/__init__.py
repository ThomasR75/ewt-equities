"""Data layer: CSV ingest, resampling, and walk-forward slicing.

This is where the no-lookahead invariant (spec §15.3) is enforced. Every path
into the engine clamps to `as_of`, so downstream stages physically cannot see
a future bar.
"""
