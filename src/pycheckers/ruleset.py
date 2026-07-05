"""Compact ruleset storage and matching for American checkers."""

from __future__ import annotations

from array import array
from dataclasses import dataclass

from .bitboard import (
    BLACK_PROMO_MASK,
    WHITE_PROMO_MASK,
    generate_move_templates,
    square_from_mask,
    validate_position,
)
from .encoding import MASK32, mask32_to64, mask64_to32, square_mask32_from64
from .state import BoardState

FLAG_BLACK_TO_MOVE = 1 << 0
FLAG_KING = 1 << 1
FLAG_PROMOTION = 1 << 2
FLAG_CAPTURE = 1 << 3

RULE_COLUMNS = (
    "is_black",
    "is_white",
    "is_empty",
    "be_black",
    "be_white",
    "be_empty",
    "black_to_move",
    "king",
    "promotion",
    "capture",
)


@dataclass(frozen=True, slots=True)
class TurnState:
    """A side-to-move checkers position using 32-bit playable-square masks."""

    black: int
    white: int
    kings: int = 0
    black_to_move: int = 1

    def __post_init__(self):
        black = int(self.black) & MASK32
        white = int(self.white) & MASK32
        kings = int(self.kings) & MASK32
        black_to_move = _black_to_move_bit(self.black_to_move)

        if black & white:
            raise ValueError("black and white bitboards overlap")
        if kings & ~(black | white):
            raise ValueError("kings must be a subset of occupied squares")

        object.__setattr__(self, "black", black)
        object.__setattr__(self, "white", white)
        object.__setattr__(self, "kings", kings)
        object.__setattr__(self, "black_to_move", black_to_move)

    @classmethod
    def from_board_state(cls, state):
        """Convert a :class:`pycheckers.BoardState` into a 32-bit turn state."""

        if not isinstance(state, BoardState):
            state = BoardState.from_tuple(state)
        return cls(
            mask64_to32(state.black),
            mask64_to32(state.white),
            mask64_to32(state.kings),
            state.side == "B",
        )

    @classmethod
    def from_tuple(cls, state):
        """Create a turn state from ``(black32, white32, kings32, black_to_move)``."""

        return cls(*state)

    @property
    def side(self):
        """Return ``"B"`` or ``"W"`` for the side to move."""

        return "B" if self.black_to_move else "W"

    @property
    def occupied(self):
        """Return the 32-bit mask of occupied playable squares."""

        return self.black | self.white

    @property
    def empty(self):
        """Return the 32-bit mask of empty playable squares."""

        return (~self.occupied) & MASK32

    def as_tuple(self):
        """Return ``(black32, white32, kings32, black_to_move)``."""

        return self.black, self.white, self.kings, self.black_to_move

    def as_board_state(self):
        """Expand this state into the public 8x8 :class:`pycheckers.BoardState`."""

        return BoardState(
            mask32_to64(self.black),
            mask32_to64(self.white),
            mask32_to64(self.kings),
            self.side,
        )


class Ruleset:
    """A compact, indexed table of primitive checkers rules.

    Masks are stored as unsigned 32-bit playable-square bitmaps. Metadata is
    stored as one byte per rule using the black-to-move, king, promotion, and
    capture flag bits.
    """

    __slots__ = (
        "is_black",
        "is_white",
        "is_empty",
        "be_black",
        "be_white",
        "be_empty",
        "flags",
        "_indices_by_side",
        "_indices_by_metadata",
    )

    def __init__(
        self,
        is_black,
        is_white,
        is_empty,
        be_black,
        be_white,
        be_empty,
        flags,
    ):
        self.is_black = _uint32_array(is_black)
        self.is_white = _uint32_array(is_white)
        self.is_empty = _uint32_array(is_empty)
        self.be_black = _uint32_array(be_black)
        self.be_white = _uint32_array(be_white)
        self.be_empty = _uint32_array(be_empty)
        self.flags = _uint8_array(flags)
        self._validate_lengths()
        self._indices_by_side = self._build_side_index()
        self._indices_by_metadata = self._build_metadata_index()

    @classmethod
    def american(cls, side="both"):
        """Return the standard American checkers primitive ruleset."""

        if side is None or str(side).lower() in ("both", "all"):
            return american_ruleset()
        return cls.from_geometric_templates(side=side)

    @classmethod
    def from_geometric_templates(cls, side="both", templates=None):
        """Build compact runtime rules from geometric move templates."""

        templates = generate_move_templates() if templates is None else list(templates)
        rows = []
        for runtime_side in _runtime_sides(side):
            for template in templates:
                if not _template_requires_king(runtime_side, template):
                    rows.append(_runtime_row_from_template(template, runtime_side, king=False))
                rows.append(_runtime_row_from_template(template, runtime_side, king=True))
        return cls.from_records(rows)

    @classmethod
    def from_records(cls, records):
        """Build a ruleset from records containing :data:`RULE_COLUMNS`."""

        rows = list(_records_from_any(records))
        return cls(
            (row["is_black"] for row in rows),
            (row["is_white"] for row in rows),
            (row["is_empty"] for row in rows),
            (row["be_black"] for row in rows),
            (row["be_white"] for row in rows),
            (row["be_empty"] for row in rows),
            (_flags_from_row(row) for row in rows),
        )

    def __len__(self):
        return len(self.flags)

    def __iter__(self):
        return iter(range(len(self)))

    def record(self, rule_index):
        """Return one rule as a plain dictionary."""

        index = self._check_index(rule_index)
        flags = self.flags[index]
        return {
            "rule_index": index,
            "is_black": int(self.is_black[index]),
            "is_white": int(self.is_white[index]),
            "is_empty": int(self.is_empty[index]),
            "be_black": int(self.be_black[index]),
            "be_white": int(self.be_white[index]),
            "be_empty": int(self.be_empty[index]),
            "black_to_move": 1 if flags & FLAG_BLACK_TO_MOVE else 0,
            "king": 1 if flags & FLAG_KING else 0,
            "promotion": 1 if flags & FLAG_PROMOTION else 0,
            "capture": 1 if flags & FLAG_CAPTURE else 0,
        }

    def records(self):
        """Return all rules as dictionaries."""

        return [self.record(index) for index in range(len(self))]

    def to_dataframe(self):
        """Return the compact ruleset table as a pandas dataframe."""

        import pandas as pd

        df = pd.DataFrame.from_records(self.records(), columns=("rule_index", *RULE_COLUMNS))
        return df.set_index("rule_index").rename_axis(None)

    def plot(self, rules=None, size=3.2, title=None, show=True):
        """Plot rules with condition, effect, and summary boards."""

        from .display import show_ruleset_rows

        return show_ruleset_rows(self, rules=self.select_records(rules), size=size, title=title, show=show)

    def select_records(self, rules=None):
        """Return rule records selected by indexes, slices, dataframes, or records."""

        if rules is None:
            return self.records()
        if isinstance(rules, int):
            return [self.record(rules)]
        if isinstance(rules, slice):
            return [self.record(index) for index in range(len(self))[rules]]
        if hasattr(rules, "to_dict") and hasattr(rules, "columns"):
            return list(rules.to_dict("index").values())
        values = list(rules)
        if all(isinstance(value, int) for value in values):
            return [self.record(index) for index in values]
        return values

    def indices_for(self, black_to_move=None, king=None, promotion=None, capture=None):
        """Return rule indexes matching metadata filters."""

        if all(value is not None for value in (black_to_move, king, promotion, capture)):
            key = (
                int(bool(black_to_move)),
                int(bool(king)),
                int(bool(promotion)),
                int(bool(capture)),
            )
            return list(self._indices_by_metadata.get(key, ()))

        indexes = range(len(self))
        return [
            index
            for index in indexes
            if _flag_matches(self.flags[index], FLAG_BLACK_TO_MOVE, black_to_move)
            and _flag_matches(self.flags[index], FLAG_KING, king)
            and _flag_matches(self.flags[index], FLAG_PROMOTION, promotion)
            and _flag_matches(self.flags[index], FLAG_CAPTURE, capture)
        ]

    def rule_applies(self, state, rule_index):
        """Return whether a rule's bit conditions are satisfied by a state."""

        state = as_turn_state(state)
        index = self._check_index(rule_index)
        if bool(self.flags[index] & FLAG_BLACK_TO_MOVE) != bool(state.black_to_move):
            return False
        if (state.black & self.is_black[index]) != self.is_black[index]:
            return False
        if (state.white & self.is_white[index]) != self.is_white[index]:
            return False
        if (state.empty & self.is_empty[index]) != self.is_empty[index]:
            return False

        mover = self._mover_condition_mask(index)
        mover_is_king = (state.kings & mover) == mover
        return mover_is_king if self.flags[index] & FLAG_KING else not mover_is_king

    def matching_rule_indices(self, state, captures_only=False, from_mask=None):
        """Return all primitive rule indexes whose conditions match a state."""

        state = as_turn_state(state)
        indexes = self._indices_by_side[state.black_to_move]
        if captures_only:
            indexes = [index for index in indexes if self.flags[index] & FLAG_CAPTURE]
        if from_mask is not None:
            from_mask = _coerce_mask32(from_mask)
            indexes = [index for index in indexes if self._mover_condition_mask(index) == from_mask]
        return [index for index in indexes if self.rule_applies(state, index)]

    def legal_rule_indices(self, state, from_mask=None):
        """Return legal primitive rule indexes, applying mandatory capture."""

        matches = self.matching_rule_indices(state, from_mask=from_mask)
        captures = [index for index in matches if self.flags[index] & FLAG_CAPTURE]
        return captures if captures else matches

    def legal_moves(self, state, from_mask=None):
        """Return legal primitive moves as 8x8 masks for compatibility."""

        return [self.rule_move(index) for index in self.legal_rule_indices(state, from_mask=from_mask)]

    def successors(self, state):
        """Return successor turn states for each legal primitive rule."""

        return [self.apply_rule(state, index) for index in self.legal_rule_indices(state)]

    def apply_rule(self, state, rule_index, switch_side=True):
        """Apply one satisfied primitive rule to a 32-bit turn state."""

        state = as_turn_state(state)
        index = self._check_index(rule_index)
        if not self.rule_applies(state, index):
            raise ValueError("rule conditions are not satisfied by the state")

        next_black = ((state.black & ~self.be_empty[index]) | self.be_black[index]) & MASK32
        next_white = ((state.white & ~self.be_empty[index]) | self.be_white[index]) & MASK32
        next_kings = state.kings & ~self.be_empty[index] & MASK32
        if self.flags[index] & (FLAG_KING | FLAG_PROMOTION):
            next_kings |= self._mover_effect_mask(index)

        next_side = 1 - state.black_to_move if switch_side else state.black_to_move
        return TurnState(next_black, next_white, next_kings, next_side)

    def apply_rule_to_board(self, state, rule_index, switch_side=True):
        """Apply a primitive rule and return an 8x8 :class:`pycheckers.BoardState`."""

        return self.apply_rule(state, rule_index, switch_side=switch_side).as_board_state()

    def rule_move(self, rule_index):
        """Return a compact rule as a move dictionary using 8x8 masks."""

        index = self._check_index(rule_index)
        from_mask = mask32_to64(self._mover_condition_mask(index))
        to_mask = mask32_to64(self._mover_effect_mask(index))
        captured32 = self.be_empty[index] & ~self._mover_condition_mask(index)
        captured_mask = mask32_to64(captured32) if self.flags[index] & FLAG_CAPTURE else 0
        from_row, from_col = square_from_mask(from_mask)
        to_row, to_col = square_from_mask(to_mask)
        return {
            "from_mask": from_mask,
            "to_mask": to_mask,
            "captured_mask": captured_mask,
            "dr": to_row - from_row,
            "dc": to_col - from_col,
            "is_capture": bool(self.flags[index] & FLAG_CAPTURE),
        }

    def _mover_condition_mask(self, index):
        return self.is_black[index] if self.flags[index] & FLAG_BLACK_TO_MOVE else self.is_white[index]

    def _mover_effect_mask(self, index):
        return self.be_black[index] if self.flags[index] & FLAG_BLACK_TO_MOVE else self.be_white[index]

    def _check_index(self, rule_index):
        index = int(rule_index)
        if not (0 <= index < len(self)):
            raise IndexError(f"rule index out of range: {rule_index!r}")
        return index

    def _validate_lengths(self):
        length = len(self.flags)
        lengths = {
            len(self.is_black),
            len(self.is_white),
            len(self.is_empty),
            len(self.be_black),
            len(self.be_white),
            len(self.be_empty),
            length,
        }
        if len(lengths) != 1:
            raise ValueError("all rule arrays must have the same length")

    def _build_side_index(self):
        indexes = {0: [], 1: []}
        for index, flags in enumerate(self.flags):
            indexes[1 if flags & FLAG_BLACK_TO_MOVE else 0].append(index)
        return {side: tuple(side_indexes) for side, side_indexes in indexes.items()}

    def _build_metadata_index(self):
        indexes = {}
        for index, flags in enumerate(self.flags):
            key = (
                1 if flags & FLAG_BLACK_TO_MOVE else 0,
                1 if flags & FLAG_KING else 0,
                1 if flags & FLAG_PROMOTION else 0,
                1 if flags & FLAG_CAPTURE else 0,
            )
            indexes.setdefault(key, []).append(index)
        return {key: tuple(value) for key, value in indexes.items()}


def as_turn_state(state):
    """Coerce a board-like object into :class:`TurnState`."""

    if isinstance(state, TurnState):
        return state
    if isinstance(state, BoardState):
        return TurnState.from_board_state(state)
    if len(state) != 4:
        raise ValueError("state must have four fields")
    if state[3] in ("B", "W"):
        return TurnState.from_board_state(state)
    return TurnState.from_tuple(state)


def american_ruleset():
    """Return the shared default American checkers ruleset."""

    global _DEFAULT_AMERICAN_RULESET
    if _DEFAULT_AMERICAN_RULESET is None:
        _DEFAULT_AMERICAN_RULESET = Ruleset.from_geometric_templates()
    return _DEFAULT_AMERICAN_RULESET


def _runtime_sides(side):
    if side is None or str(side).lower() in ("both", "all"):
        return ("B", "W")
    if side not in ("B", "W"):
        raise ValueError("side must be 'B', 'W', or 'both'")
    return (side,)


def _template_requires_king(side, template):
    dr = _row_delta(template)
    return (side == "B" and dr < 0) or (side == "W" and dr > 0)


def _runtime_row_from_template(template, side, king):
    from_mask = int(template["from_mask"])
    to_mask = int(template["to_mask"])
    captured_mask = int(template.get("captured_mask", 0))
    from32 = square_mask32_from64(from_mask)
    to32 = square_mask32_from64(to_mask)
    captured32 = square_mask32_from64(captured_mask)
    promotion = not king and bool(to_mask & (BLACK_PROMO_MASK if side == "B" else WHITE_PROMO_MASK))

    if side == "B":
        is_black = from32
        is_white = captured32
        be_black = to32
        be_white = 0
    else:
        is_black = captured32
        is_white = from32
        be_black = 0
        be_white = to32

    return {
        "is_black": is_black,
        "is_white": is_white,
        "is_empty": to32,
        "be_black": be_black,
        "be_white": be_white,
        "be_empty": from32 | captured32,
        "black_to_move": 1 if side == "B" else 0,
        "king": int(bool(king)),
        "promotion": int(promotion),
        "capture": int(bool(captured_mask)),
    }


def _row_delta(template):
    from_row, _ = square_from_mask(int(template["from_mask"]))
    to_row, _ = square_from_mask(int(template["to_mask"]))
    return to_row - from_row


def _uint32_array(values):
    return array("I", (int(value) & MASK32 for value in values))


def _uint8_array(values):
    return array("B", (int(value) & 0xFF for value in values))


def _records_from_any(records):
    if isinstance(records, Ruleset):
        return records.records()
    if isinstance(records, dict):
        return [records]
    if hasattr(records, "to_dict") and hasattr(records, "columns"):
        return list(records.to_dict("index").values())
    if hasattr(records, "to_dict") and not isinstance(records, dict):
        return [records.to_dict()]
    return records


def _flags_from_row(row):
    flags = 0
    if row["black_to_move"]:
        flags |= FLAG_BLACK_TO_MOVE
    if row["king"]:
        flags |= FLAG_KING
    if row["promotion"]:
        flags |= FLAG_PROMOTION
    if row["capture"]:
        flags |= FLAG_CAPTURE
    return flags


def _flag_matches(flags, flag, requested):
    return requested is None or bool(flags & flag) == bool(requested)


def _coerce_mask32(mask):
    mask = int(mask)
    if mask & ~MASK32:
        validate_position(mask, 0, 0)
        return mask64_to32(mask)
    return mask & MASK32


def _black_to_move_bit(value):
    if value in ("B", "black"):
        return 1
    if value in ("W", "white"):
        return 0
    if value in (0, 1, False, True):
        return int(bool(value))
    raise ValueError("black_to_move must be 0, 1, 'B', or 'W'")


_DEFAULT_AMERICAN_RULESET = None
