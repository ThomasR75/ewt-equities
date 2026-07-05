"""Export layer (spec §5.1/§15): the frozen SignalRecord the tester consumes."""

from .schema import SignalRecord, SCHEMA_VERSION, validate_record
from .signal import build_signal_record, append_signal_log

__all__ = [
    "SignalRecord", "SCHEMA_VERSION", "validate_record",
    "build_signal_record", "append_signal_log",
]
