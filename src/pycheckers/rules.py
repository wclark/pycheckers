"""Rule-inspection helpers built around :class:`pycheckers.BoardState`."""

from .bitboard import (
    BLACK_PROMO_MASK,
    WHITE_PROMO_MASK,
    generate_move_templates,
    square_from_mask,
)
from .state import as_state


def move_record(move, state=None, step=None, turn_index=None):
    from_r, from_c = square_from_mask(move["from_mask"])
    to_r, to_c = square_from_mask(move["to_mask"])
    captured = move.get("captured_mask", 0)
    captured_r = captured_c = None
    if captured:
        captured_r, captured_c = square_from_mask(captured)

    record = {
        "turn_index": turn_index,
        "step": step,
        "from_r": from_r,
        "from_c": from_c,
        "to_r": to_r,
        "to_c": to_c,
        "dr": move["dr"],
        "dc": move["dc"],
        "is_capture": bool(move["is_capture"]),
        "captured_r": captured_r,
        "captured_c": captured_c,
        "from_mask": move["from_mask"],
        "from_mask_hex": _mask_hex(move["from_mask"]),
        "to_mask": move["to_mask"],
        "to_mask_hex": _mask_hex(move["to_mask"]),
        "captured_mask": captured,
        "captured_mask_hex": _mask_hex(captured),
    }
    if state is not None:
        state = as_state(state)
        record["side"] = state.side
        record["is_king"] = bool(state.kings & move["from_mask"])
        record["promotes"] = _move_promotes_for_state(state, move)
        record.update(state_record(state, prefix="before_"))
        record.update(state_record(state.apply_move(move, switch_side=False), prefix="after_move_"))
    return record


def state_record(state, prefix=""):
    state = as_state(state)
    return {
        f"{prefix}black": state.black,
        f"{prefix}black_hex": _mask_hex(state.black),
        f"{prefix}white": state.white,
        f"{prefix}white_hex": _mask_hex(state.white),
        f"{prefix}kings": state.kings,
        f"{prefix}kings_hex": _mask_hex(state.kings),
        f"{prefix}side": state.side,
        f"{prefix}black_count": state.black_count,
        f"{prefix}white_count": state.white_count,
        f"{prefix}king_count": state.king_count,
    }


def primitive_move_records():
    rows = []
    move_id = 0
    for side in ("B", "W"):
        for piece_type in ("man", "king"):
            for template in generate_move_templates():
                if not _piece_can_use_template(side, piece_type, template):
                    continue
                rows.append(primitive_move_record(template, side, piece_type, move_id))
                move_id += 1
    return rows


def primitive_move_record(move, side, piece_type, move_id=None):
    record = move_record(move)
    record.update(
        {
            "move_id": move_id,
            "side": side,
            "piece_type": piece_type,
            "is_king": piece_type == "king",
            "promotes": _template_promotes(side, piece_type, move),
            "from_square": _square_index(move["from_mask"]),
            "to_square": _square_index(move["to_mask"]),
            "captured_square": (
                None if not move["captured_mask"] else _square_index(move["captured_mask"])
            ),
        }
    )
    return record


def primitive_move_catalog_df():
    import pandas as pd

    columns = [
        "move_id",
        "side",
        "piece_type",
        "is_king",
        "is_capture",
        "promotes",
        "from_square",
        "from_r",
        "from_c",
        "to_square",
        "to_r",
        "to_c",
        "captured_square",
        "captured_r",
        "captured_c",
        "dr",
        "dc",
        "from_mask",
        "from_mask_hex",
        "to_mask",
        "to_mask_hex",
        "captured_mask",
        "captured_mask_hex",
    ]
    return pd.DataFrame.from_records(primitive_move_records(), columns=columns)


def moves_df(state, moves=None):
    import pandas as pd

    state = as_state(state)
    moves = state.legal_moves() if moves is None else moves
    return pd.DataFrame.from_records(
        move_record(move, state=state, step=1, turn_index=index)
        for index, move in enumerate(moves)
    )


def turns_df(state, turns=None):
    import pandas as pd

    state = as_state(state)
    turns = state.legal_turns() if turns is None else turns
    rows = []
    for turn_index, turn in enumerate(turns):
        current = state
        for step, move in enumerate(turn, start=1):
            rows.append(move_record(move, state=current, step=step, turn_index=turn_index))
            current = current.apply_move(move, switch_side=False)
    return pd.DataFrame.from_records(rows)


def legal_successors(state):
    state = as_state(state)
    return [state.apply_turn(turn) for turn in state.legal_turns()]


def _move_promotes_for_state(state, move):
    next_state = state.apply_move(move, switch_side=False)
    return bool(next_state.kings & move["to_mask"] and not state.kings & move["from_mask"])


def _piece_can_use_template(side, piece_type, move):
    if piece_type == "king":
        return True
    if side == "B":
        return move["dr"] > 0
    if side == "W":
        return move["dr"] < 0
    raise ValueError("side must be 'B' or 'W'")


def _template_promotes(side, piece_type, move):
    if piece_type == "king":
        return False
    promo_mask = BLACK_PROMO_MASK if side == "B" else WHITE_PROMO_MASK
    return bool(move["to_mask"] & promo_mask)


def _square_index(mask):
    return mask.bit_length() - 1


def _mask_hex(mask):
    return f"0x{mask & ((1 << 64) - 1):016x}"
