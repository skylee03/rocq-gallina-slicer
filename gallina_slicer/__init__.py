"""Rocq + MetaRocq + Gallina-subset proof slicer."""

from .slicer import (
    Block,
    SlicerError,
    exact_slice,
    line_count,
    parse_signature,
    render,
    run_rocq_check,
    type_slice,
)
from .meta_trace import MetaTrace, collect_meta_trace, parse_meta_output

__version__ = "0.1.0"

__all__ = [
    "Block",
    "MetaTrace",
    "SlicerError",
    "collect_meta_trace",
    "exact_slice",
    "line_count",
    "parse_meta_output",
    "parse_signature",
    "render",
    "run_rocq_check",
    "type_slice",
]
