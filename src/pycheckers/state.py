"""General board-state representation for American checkers."""

from dataclasses import dataclass

from .bitboard import (
    MASK64,
    apply_move,
    apply_turn,
    bitboards_from_ascii,
    capture_chains,
    initial_position,
    legal_moves,
    legal_turns,
    show_board,
    validate_position,
)


@dataclass(frozen=True, slots=True)
class BoardState:
    """Immutable 8x8 checkers position using three bitboards and side to move."""

    black: int
    white: int
    kings: int = 0
    side: str = "B"

    def __post_init__(self):
        object.__setattr__(self, "black", self.black & MASK64)
        object.__setattr__(self, "white", self.white & MASK64)
        object.__setattr__(self, "kings", self.kings & MASK64)
        if self.side not in ("B", "W"):
            raise ValueError("side must be 'B' or 'W'")
        validate_position(self.black, self.white, self.kings)

    @classmethod
    def initial(cls):
        return cls(*initial_position())

    @classmethod
    def from_ascii(cls, board, side="B"):
        return cls(*bitboards_from_ascii(board), side)

    @classmethod
    def from_tuple(cls, state):
        return cls(*state)

    def as_tuple(self):
        return self.black, self.white, self.kings, self.side

    @property
    def occupied(self):
        return self.black | self.white

    @property
    def black_count(self):
        return self.black.bit_count()

    @property
    def white_count(self):
        return self.white.bit_count()

    @property
    def king_count(self):
        return self.kings.bit_count()

    def legal_moves(self):
        return legal_moves(*self.as_tuple())

    def capture_chains(self):
        return capture_chains(*self.as_tuple())

    def legal_turns(self):
        return legal_turns(*self.as_tuple())

    def apply_move(self, move, switch_side=True):
        return type(self)(*apply_move(*self.as_tuple(), move, switch_side=switch_side))

    def apply_turn(self, turn):
        return type(self)(*apply_turn(*self.as_tuple(), turn))

    def turn_states(self, turn):
        states = [self]
        current = self
        for move in turn:
            current = current.apply_move(move, switch_side=False)
            states.append(current)
        if len(states) > 1:
            final = states[-1]
            states[-1] = type(self)(
                final.black,
                final.white,
                final.kings,
                "W" if self.side == "B" else "B",
            )
        return states

    def show(self, dots=0, other=None, size=3):
        other_tuple = other.as_tuple()[:3] if isinstance(other, BoardState) else other
        return show_board(
            self.black,
            self.white,
            self.kings,
            dots=dots,
            other=other_tuple,
            size=size,
        )


def as_state(state):
    if isinstance(state, BoardState):
        return state
    return BoardState.from_tuple(state)
