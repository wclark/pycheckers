"""Native 32-bit boards, turns, rules, and rulesets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .encoding import MASK32, is_playable_square, square_from_mask32, square_mask32

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

INITIAL_BLACK = 0x00000FFF
INITIAL_WHITE = 0xFFF00000


@dataclass(frozen=True, slots=True)
class Board:
    """A checkers board stored as black, white, and king 32-bit masks."""

    black: int
    white: int
    kings: int = 0

    def __post_init__(self):
        black = _mask32(self.black, "black")
        white = _mask32(self.white, "white")
        kings = _mask32(self.kings, "kings")
        if black & white:
            raise ValueError("black and white masks overlap")
        if kings & ~(black | white):
            raise ValueError("kings must be a subset of occupied squares")
        object.__setattr__(self, "black", black)
        object.__setattr__(self, "white", white)
        object.__setattr__(self, "kings", kings)

    @classmethod
    def initial(cls):
        """Return the standard starting board."""

        return cls(INITIAL_BLACK, INITIAL_WHITE, 0)

    @classmethod
    def from_tuple(cls, values):
        """Create a board from ``(black, white, kings)``."""

        if len(values) != 3:
            raise ValueError("board tuple must have three fields")
        return cls(*values)

    @property
    def occupied(self):
        """Return the occupied-square mask."""

        return self.black | self.white

    @property
    def empty(self):
        """Return the empty playable-square mask."""

        return (~self.occupied) & MASK32

    @property
    def key(self):
        """Return a hashable native tuple key."""

        return self.as_tuple()

    @property
    def maps(self):
        """Return a plain dict of the board masks."""

        return self.as_dict()

    def as_tuple(self):
        """Return ``(black, white, kings)``."""

        return self.black, self.white, self.kings

    def as_dict(self):
        """Return a plain dict of 32-bit masks."""

        return {"black": self.black, "white": self.white, "kings": self.kings}

    def display(self, size=3, title=None, show=True):
        """Render this board with matplotlib and return ``(figure, axis)``."""

        from .display import show_board

        return show_board(self, size=size, title=title, show=show)


@dataclass(frozen=True, slots=True)
class Turn:
    """A board plus side to move and optional hashable metadata."""

    board: Board
    black_to_move: int = 1
    metadata: tuple = ()

    def __post_init__(self):
        board = self.board if isinstance(self.board, Board) else Board.from_tuple(self.board)
        black_to_move = _turn_bit(self.black_to_move)
        metadata = _metadata_tuple(self.metadata)
        object.__setattr__(self, "board", board)
        object.__setattr__(self, "black_to_move", black_to_move)
        object.__setattr__(self, "metadata", metadata)

    @classmethod
    def initial(cls):
        """Return the standard starting turn."""

        return cls(Board.initial(), 1)

    @classmethod
    def from_masks(cls, black, white, kings=0, black_to_move=1, metadata=()):
        """Create a turn from board masks and side to move."""

        return cls(Board(black, white, kings), black_to_move, metadata)

    @classmethod
    def from_tuple(cls, values):
        """Create a turn from ``(black, white, kings, black_to_move[, metadata])``."""

        if len(values) == 4:
            return cls.from_masks(*values)
        if len(values) == 5:
            return cls.from_masks(*values)
        raise ValueError("turn tuple must have four or five fields")

    @property
    def black(self):
        return self.board.black

    @property
    def white(self):
        return self.board.white

    @property
    def kings(self):
        return self.board.kings

    @property
    def occupied(self):
        return self.board.occupied

    @property
    def empty(self):
        return self.board.empty

    @property
    def side(self):
        """Return ``"black"`` or ``"white"`` for the side to move."""

        return "black" if self.black_to_move else "white"

    @property
    def key(self):
        """Return a hashable native tuple key."""

        return self.as_tuple()

    @property
    def maps(self):
        """Return a plain dict of board and turn masks."""

        return self.as_dict()

    def as_tuple(self):
        """Return ``(black, white, kings, black_to_move)`` plus metadata if present."""

        base = (*self.board.as_tuple(), self.black_to_move)
        if self.metadata:
            return (*base, self.metadata)
        return base

    def as_dict(self):
        """Return a plain dict for dataframe or ad hoc analysis use."""

        record = {**self.board.as_dict(), "black_to_move": self.black_to_move}
        if self.metadata:
            record["metadata"] = dict(self.metadata)
        return record

    def display(self, size=3, title=None, show=True):
        """Render this turn with matplotlib and return ``(figure, axis)``."""

        from .display import show_turn

        return show_turn(self, size=size, title=title, show=show)


@dataclass(frozen=True, slots=True)
class Conditions:
    """Bit conditions a rule checks against a turn."""

    is_black: int
    is_white: int
    is_empty: int
    black_to_move: int
    king: int = 0

    def __post_init__(self):
        object.__setattr__(self, "is_black", _mask32(self.is_black, "is_black"))
        object.__setattr__(self, "is_white", _mask32(self.is_white, "is_white"))
        object.__setattr__(self, "is_empty", _mask32(self.is_empty, "is_empty"))
        object.__setattr__(self, "black_to_move", _turn_bit(self.black_to_move))
        object.__setattr__(self, "king", int(bool(self.king)))

    @property
    def mover(self):
        """Return the required mover-square mask."""

        return self.is_black if self.black_to_move else self.is_white

    @property
    def as_tuple(self):
        """Return a hashable condition tuple."""

        return self.is_black, self.is_white, self.is_empty, self.black_to_move, self.king

    @property
    def as_dict(self):
        """Return a plain dict of condition fields."""

        return {
            "is_black": self.is_black,
            "is_white": self.is_white,
            "is_empty": self.is_empty,
            "black_to_move": self.black_to_move,
            "king": self.king,
        }


@dataclass(frozen=True, slots=True)
class Effects:
    """Bit effects a rule applies to a turn."""

    be_black: int
    be_white: int
    be_empty: int
    promotion: int = 0
    capture: int = 0

    def __post_init__(self):
        object.__setattr__(self, "be_black", _mask32(self.be_black, "be_black"))
        object.__setattr__(self, "be_white", _mask32(self.be_white, "be_white"))
        object.__setattr__(self, "be_empty", _mask32(self.be_empty, "be_empty"))
        object.__setattr__(self, "promotion", int(bool(self.promotion)))
        object.__setattr__(self, "capture", int(bool(self.capture)))

    @property
    def as_tuple(self):
        """Return a hashable effect tuple."""

        return self.be_black, self.be_white, self.be_empty, self.promotion, self.capture

    @property
    def as_dict(self):
        """Return a plain dict of effect fields."""

        return {
            "be_black": self.be_black,
            "be_white": self.be_white,
            "be_empty": self.be_empty,
            "promotion": self.promotion,
            "capture": self.capture,
        }


@dataclass(frozen=True, slots=True)
class Rule:
    """A primitive rule made of conditions and effects."""

    conditions: Conditions
    effects: Effects

    def __post_init__(self):
        conditions = self.conditions if isinstance(self.conditions, Conditions) else Conditions(**self.conditions)
        effects = self.effects if isinstance(self.effects, Effects) else Effects(**self.effects)
        object.__setattr__(self, "conditions", conditions)
        object.__setattr__(self, "effects", effects)

    @classmethod
    def from_record(cls, record):
        """Create a rule from a flat rule record."""

        return cls(
            Conditions(
                record["is_black"],
                record["is_white"],
                record["is_empty"],
                record["black_to_move"],
                record["king"],
            ),
            Effects(
                record["be_black"],
                record["be_white"],
                record["be_empty"],
                record["promotion"],
                record["capture"],
            ),
        )

    @property
    def as_tuple(self):
        """Return a hashable tuple representation."""

        return (*self.conditions.as_tuple, *self.effects.as_tuple)

    @property
    def as_dict(self):
        """Return a plain flat rule record without an index."""

        return {**self.conditions.as_dict, **self.effects.as_dict}

    @property
    def flags(self):
        """Return packed rule metadata flags."""

        flags = 0
        if self.conditions.black_to_move:
            flags |= FLAG_BLACK_TO_MOVE
        if self.conditions.king:
            flags |= FLAG_KING
        if self.effects.promotion:
            flags |= FLAG_PROMOTION
        if self.effects.capture:
            flags |= FLAG_CAPTURE
        return flags

    @property
    def mover_effect(self):
        """Return the square where the moving piece is placed."""

        return self.effects.be_black if self.conditions.black_to_move else self.effects.be_white

    @property
    def captured_mask(self):
        """Return the captured piece mask, or zero for quiet moves."""

        if not self.effects.capture:
            return 0
        return self.effects.be_empty & ~self.conditions.mover

    def applies(self, turn):
        """Return whether this rule's conditions match a turn."""

        turn = as_turn(turn)
        conditions = self.conditions
        if conditions.black_to_move != turn.black_to_move:
            return False
        if (turn.black & conditions.is_black) != conditions.is_black:
            return False
        if (turn.white & conditions.is_white) != conditions.is_white:
            return False
        if (turn.empty & conditions.is_empty) != conditions.is_empty:
            return False
        mover_is_king = (turn.kings & conditions.mover) == conditions.mover
        return mover_is_king if conditions.king else not mover_is_king

    def apply(self, turn, switch_side=True):
        """Apply this rule to a matching turn."""

        turn = as_turn(turn)
        if not self.applies(turn):
            raise ValueError("rule conditions are not satisfied by the turn")

        effects = self.effects
        next_black = ((turn.black & ~effects.be_empty) | effects.be_black) & MASK32
        next_white = ((turn.white & ~effects.be_empty) | effects.be_white) & MASK32
        next_kings = (turn.kings & ~effects.be_empty) & MASK32
        if self.conditions.king or effects.promotion:
            next_kings |= self.mover_effect

        next_side = 1 - turn.black_to_move if switch_side else turn.black_to_move
        return Turn(Board(next_black, next_white, next_kings), next_side, turn.metadata)

    def move_record(self):
        """Return a compact move dictionary using 32-bit masks."""

        from_row, from_col = square_from_mask32(self.conditions.mover)
        to_row, to_col = square_from_mask32(self.mover_effect)
        return {
            "from_mask": self.conditions.mover,
            "to_mask": self.mover_effect,
            "captured_mask": self.captured_mask,
            "dr": to_row - from_row,
            "dc": to_col - from_col,
            "capture": bool(self.effects.capture),
            "promotion": bool(self.effects.promotion),
            "king": bool(self.conditions.king),
        }

    def display(self, size=3.2, title=None, show=True):
        """Render this primitive rule and return ``(figure, axes)``."""

        from .display import show_ruleset_rows

        return show_ruleset_rows([self], size=size, title=title, show=show)[0]


class Ruleset:
    """A collection of primitive rules with native Python indexes and records."""

    __slots__ = (
        "rules",
        "records",
        "record_map",
        "rule_set",
        "condition_tuples",
        "effect_tuples",
        "rules_by_side",
        "rules_by_metadata",
    )

    def __init__(self, rules):
        rule_tuple = tuple(_coerce_rule(rule) for rule in rules)
        self.rules = rule_tuple
        self.records = tuple(_indexed_record(index, rule) for index, rule in enumerate(rule_tuple))
        self.record_map = {index: record for index, record in enumerate(self.records)}
        self.rule_set = {rule.as_tuple for rule in rule_tuple}
        self.condition_tuples = tuple(rule.conditions.as_tuple for rule in rule_tuple)
        self.effect_tuples = tuple(rule.effects.as_tuple for rule in rule_tuple)
        self.rules_by_side = _rules_by_side(rule_tuple)
        self.rules_by_metadata = _rules_by_metadata(rule_tuple)

    @classmethod
    def american(cls, side="both"):
        """Return the standard American checkers primitive ruleset."""

        if side is None or str(side).lower() in ("both", "all"):
            return american_ruleset()
        return cls.from_board_geometry(side=side)

    @classmethod
    def from_board_geometry(cls, side="both"):
        """Build rules directly from the 32 playable-square board geometry."""

        rules = []
        for black_to_move in _runtime_sides(side):
            for template in _compact_move_templates():
                if not _template_requires_king(black_to_move, template):
                    rules.append(_rule_from_template(template, black_to_move, king=0))
                rules.append(_rule_from_template(template, black_to_move, king=1))
        return cls(rules)

    @classmethod
    def from_records(cls, records):
        """Build a ruleset from flat records, rule objects, or a dataframe."""

        return cls(_records_from_any(records))

    def __len__(self):
        return len(self.rules)

    def __iter__(self):
        return iter(self.rules)

    def __getitem__(self, rule_index):
        return self.rules[self._check_index(rule_index)]

    def record(self, rule_index):
        """Return one rule as a plain dictionary."""

        return dict(self.record_map[self._check_index(rule_index)])

    def to_dataframe(self):
        """Return the compact ruleset table as a pandas dataframe."""

        import pandas as pd

        df = pd.DataFrame.from_records(self.records, columns=("rule_index", *RULE_COLUMNS))
        return df.set_index("rule_index").rename_axis(None)

    def select_records(self, rules=None):
        """Return selected rule records from indexes, slices, dataframes, or records."""

        if rules is None:
            return [dict(record) for record in self.records]
        if isinstance(rules, int):
            return [self.record(rules)]
        if isinstance(rules, slice):
            return [self.record(index) for index in range(len(self))[rules]]
        if hasattr(rules, "to_dict") and hasattr(rules, "columns"):
            rows = []
            for index, record in rules.to_dict("index").items():
                record = dict(record)
                record.setdefault("rule_index", index)
                rows.append(record)
            return rows
        values = list(rules)
        if all(isinstance(value, int) for value in values):
            return [self.record(index) for index in values]
        return [dict(value.as_dict if isinstance(value, Rule) else value) for value in values]

    def plot(self, rules=None, size=3.2, title=None, show=True):
        """Plot selected rules with condition, effect, and summary boards."""

        from .display import show_ruleset_rows

        return show_ruleset_rows(self, rules=rules, size=size, title=title, show=show)

    def display(self, rules=None, size=3.2, title=None, show=True):
        """Render selected rules with condition, effect, and summary boards."""

        return self.plot(rules=rules, size=size, title=title, show=show)

    def indices_for(self, black_to_move=None, king=None, promotion=None, capture=None):
        """Return rule indexes matching metadata filters."""

        if all(value is not None for value in (black_to_move, king, promotion, capture)):
            key = (
                int(bool(black_to_move)),
                int(bool(king)),
                int(bool(promotion)),
                int(bool(capture)),
            )
            return list(self.rules_by_metadata.get(key, ()))

        indexes = range(len(self))
        return [
            index for index in indexes if _metadata_matches(self.rules[index], black_to_move, king, promotion, capture)
        ]

    def matching_rule_indices(self, turn, captures_only=False, from_mask=None):
        """Return primitive rule indexes whose conditions match a turn."""

        turn = as_turn(turn)
        indexes = self.rules_by_side[turn.black_to_move]
        if captures_only:
            indexes = [index for index in indexes if self.rules[index].effects.capture]
        if from_mask is not None:
            from_mask = _mask32(from_mask, "from_mask")
            indexes = [index for index in indexes if self.rules[index].conditions.mover == from_mask]
        return [index for index in indexes if self.rules[index].applies(turn)]

    def matching_rules(self, turn, captures_only=False, from_mask=None):
        """Return matching rule objects."""

        return tuple(self.rules[index] for index in self.matching_rule_indices(turn, captures_only, from_mask))

    def legal_rule_indices(self, turn, from_mask=None):
        """Return legal primitive rule indexes, applying mandatory capture."""

        matches = self.matching_rule_indices(turn, from_mask=from_mask)
        captures = [index for index in matches if self.rules[index].effects.capture]
        return captures if captures else matches

    def legal_rules(self, turn, from_mask=None):
        """Return legal primitive rule objects."""

        return tuple(self.rules[index] for index in self.legal_rule_indices(turn, from_mask=from_mask))

    def legal_moves(self, turn, from_mask=None):
        """Return legal primitive moves as plain dictionaries of 32-bit masks."""

        return tuple(rule.move_record() for rule in self.legal_rules(turn, from_mask=from_mask))

    def apply_rule(self, turn, rule_index, switch_side=True):
        """Apply one satisfied primitive rule to a turn."""

        return self.rules[self._check_index(rule_index)].apply(turn, switch_side=switch_side)

    def successors(self, turn):
        """Return successor turns for each legal primitive rule."""

        return tuple(self.apply_rule(turn, index) for index in self.legal_rule_indices(turn))

    def successor_map(self, turn):
        """Return ``{rule_index: successor_turn}`` for legal rules."""

        return {index: self.apply_rule(turn, index) for index in self.legal_rule_indices(turn)}

    def _check_index(self, rule_index):
        index = int(rule_index)
        if not (0 <= index < len(self.rules)):
            raise IndexError(f"rule index out of range: {rule_index!r}")
        return index


def as_board(board):
    """Coerce a board-like object into :class:`Board`."""

    if isinstance(board, Board):
        return board
    if isinstance(board, Mapping):
        return Board(board["black"], board["white"], board.get("kings", 0))
    return Board.from_tuple(board)


def as_turn(turn):
    """Coerce a turn-like object into :class:`Turn`."""

    if isinstance(turn, Turn):
        return turn
    if isinstance(turn, Mapping):
        return Turn.from_masks(
            turn["black"],
            turn["white"],
            turn.get("kings", 0),
            turn.get("black_to_move", 1),
            turn.get("metadata", ()),
        )
    return Turn.from_tuple(turn)


def american_ruleset():
    """Return the shared default American checkers ruleset."""

    global _DEFAULT_AMERICAN_RULESET
    if _DEFAULT_AMERICAN_RULESET is None:
        _DEFAULT_AMERICAN_RULESET = Ruleset.from_board_geometry()
    return _DEFAULT_AMERICAN_RULESET


def _indexed_record(index, rule):
    return {"rule_index": index, **rule.as_dict}


def _coerce_rule(rule):
    if isinstance(rule, Rule):
        return rule
    return Rule.from_record(rule)


def _records_from_any(records):
    if isinstance(records, Ruleset):
        return records.rules
    if isinstance(records, Rule):
        return (records,)
    if isinstance(records, Mapping):
        return (records,)
    if hasattr(records, "to_dict") and hasattr(records, "columns"):
        return tuple(records.to_dict("records"))
    if hasattr(records, "to_dict") and not isinstance(records, Mapping):
        return (records.to_dict(),)
    return records


def _rules_by_side(rules):
    indexes = {0: [], 1: []}
    for index, rule in enumerate(rules):
        indexes[rule.conditions.black_to_move].append(index)
    return {side: tuple(side_indexes) for side, side_indexes in indexes.items()}


def _rules_by_metadata(rules):
    indexes = {}
    for index, rule in enumerate(rules):
        key = (
            rule.conditions.black_to_move,
            rule.conditions.king,
            rule.effects.promotion,
            rule.effects.capture,
        )
        indexes.setdefault(key, []).append(index)
    return {key: tuple(value) for key, value in indexes.items()}


def _metadata_matches(rule, black_to_move, king, promotion, capture):
    return (
        _match_flag(rule.conditions.black_to_move, black_to_move)
        and _match_flag(rule.conditions.king, king)
        and _match_flag(rule.effects.promotion, promotion)
        and _match_flag(rule.effects.capture, capture)
    )


def _match_flag(value, requested):
    return requested is None or bool(value) == bool(requested)


_DIRECTIONS = ((-1, -1), (-1, 1), (1, -1), (1, 1))


def _runtime_sides(side):
    if side is None or str(side).lower() in ("both", "all"):
        return (1, 0)
    return (_turn_bit(side),)


def _compact_move_templates():
    templates = []
    seen = set()
    for row in range(8):
        for col in range(8):
            if not is_playable_square(row, col):
                continue
            from_mask = square_mask32(row, col)
            for dr, dc in _DIRECTIONS:
                to_row = row + dr
                to_col = col + dc
                if is_playable_square(to_row, to_col):
                    _add_template(templates, seen, from_mask, square_mask32(to_row, to_col), 0, dr, dc)

                jump_row = row + 2 * dr
                jump_col = col + 2 * dc
                captured_row = row + dr
                captured_col = col + dc
                if is_playable_square(jump_row, jump_col):
                    _add_template(
                        templates,
                        seen,
                        from_mask,
                        square_mask32(jump_row, jump_col),
                        square_mask32(captured_row, captured_col),
                        2 * dr,
                        2 * dc,
                    )
    return templates


def _add_template(templates, seen, from_mask, to_mask, captured_mask, dr, dc):
    key = (from_mask, to_mask, captured_mask)
    if key in seen:
        return
    seen.add(key)
    templates.append(
        {
            "from_mask": from_mask,
            "to_mask": to_mask,
            "captured_mask": captured_mask,
            "dr": dr,
            "dc": dc,
        }
    )


def _template_requires_king(black_to_move, template):
    dr = int(template["dr"])
    return (black_to_move and dr < 0) or (not black_to_move and dr > 0)


def _rule_from_template(template, black_to_move, king):
    from_mask = int(template["from_mask"])
    to_mask = int(template["to_mask"])
    captured_mask = int(template["captured_mask"])
    to_row, _ = square_from_mask32(to_mask)
    promotion = not king and _promotion_row(black_to_move, to_row)

    if black_to_move:
        conditions = Conditions(from_mask, captured_mask, to_mask, 1, king)
        effects = Effects(to_mask, 0, from_mask | captured_mask, promotion, bool(captured_mask))
    else:
        conditions = Conditions(captured_mask, from_mask, to_mask, 0, king)
        effects = Effects(0, to_mask, from_mask | captured_mask, promotion, bool(captured_mask))
    return Rule(conditions, effects)


def _promotion_row(black_to_move, row):
    return (black_to_move and row == 7) or (not black_to_move and row == 0)


def _mask32(value, name):
    value = int(value)
    if value < 0 or value & ~MASK32:
        raise ValueError(f"{name} must fit in a 32-bit playable-square bitmap")
    return value


def _turn_bit(value):
    if value in ("B", "black", "Black"):
        return 1
    if value in ("W", "white", "White"):
        return 0
    if value in (0, 1, False, True):
        return int(bool(value))
    raise ValueError("side to move must be 0, 1, 'black', or 'white'")


def _metadata_tuple(metadata):
    if metadata in (None, ()):
        return ()
    if isinstance(metadata, Mapping):
        return tuple(sorted(metadata.items()))
    return tuple(metadata)


_DEFAULT_AMERICAN_RULESET = None
