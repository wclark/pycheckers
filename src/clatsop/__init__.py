"""Clatsop: native 32-bit American checkers rules and board states."""

from .display import draw_board, show_board, show_ruleset_rows, show_turn
from .encoding import (
    MASK32,
    is_playable_square,
    playable_squares,
    square_coords32,
    square_from_mask32,
    square_index32,
    square_mask32,
)
from .ruleset import (
    Board,
    Conditions,
    Effects,
    Rule,
    Ruleset,
    Transition,
    Turn,
    american_ruleset,
    as_board,
    as_turn,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Board",
    "Conditions",
    "Effects",
    "MASK32",
    "Rule",
    "Ruleset",
    "Transition",
    "Turn",
    "american_ruleset",
    "as_board",
    "as_turn",
    "draw_board",
    "is_playable_square",
    "playable_squares",
    "show_board",
    "show_ruleset_rows",
    "show_turn",
    "square_coords32",
    "square_from_mask32",
    "square_index32",
    "square_mask32",
]
