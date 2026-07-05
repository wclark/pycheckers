"""Python tools for checkers board states, rules, and validation."""

from .bitboard import (
    BLACK_PROMO_MASK,
    DARKS_MASK,
    WHITE_PROMO_MASK,
    apply_move,
    apply_turn,
    bitboards_from_ascii,
    bits_from_grid,
    capture_chains,
    draw_board,
    generate_move_templates,
    grid_from_bits,
    initial_position,
    is_dark,
    legal_moves,
    legal_turns,
    show_board,
    square_from_mask,
    square_mask,
    validate_position,
)
from .display import show_state, show_turn
from .rules import legal_successors, move_record, moves_df, turns_df
from .state import BoardState, as_state

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "BLACK_PROMO_MASK",
    "BoardState",
    "DARKS_MASK",
    "WHITE_PROMO_MASK",
    "apply_move",
    "apply_turn",
    "as_state",
    "bitboards_from_ascii",
    "bits_from_grid",
    "capture_chains",
    "draw_board",
    "generate_move_templates",
    "grid_from_bits",
    "initial_position",
    "is_dark",
    "legal_moves",
    "legal_successors",
    "legal_turns",
    "move_record",
    "moves_df",
    "show_board",
    "show_state",
    "show_turn",
    "square_from_mask",
    "square_mask",
    "turns_df",
    "validate_position",
]
