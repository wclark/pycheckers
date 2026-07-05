"""Tablebase-facing aliases for the quiet position graph."""

from .quiet import (
    FORCED_CAPTURE,
    FORCED_CAPTURE_PROMOTION,
    PROMOTION,
    QUIET,
    TRANSITION_METADATA_KEYS,
    QuietPositionGraph,
    inspect_game_state,
    run_quiet_graph,
)

QuietTablebase = QuietPositionGraph

__all__ = [
    "FORCED_CAPTURE",
    "FORCED_CAPTURE_PROMOTION",
    "PROMOTION",
    "QUIET",
    "TRANSITION_METADATA_KEYS",
    "QuietPositionGraph",
    "QuietTablebase",
    "inspect_game_state",
    "run_quiet_graph",
]
