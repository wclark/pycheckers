"""Rule-inspection helpers built around :class:`pycheckers.BoardState`."""

from .bitboard import square_from_mask
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


def _mask_hex(mask):
    return f"0x{mask & ((1 << 64) - 1):016x}"
