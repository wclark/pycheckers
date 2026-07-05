"""Rule-inspection helpers built around :class:`pycheckers.BoardState`."""

from .bitboard import (
    BLACK_PROMO_MASK,
    WHITE_PROMO_MASK,
    generate_move_templates,
    square_from_mask,
)
from .state import BoardState, as_state


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


def primitive_rule_records():
    return [primitive_rule_record(template) for template in generate_move_templates()]


def primitive_move_records():
    return primitive_rule_records()


def primitive_rule_record(move):
    return {
        "from_mask": int(move["from_mask"]),
        "to_mask": int(move["to_mask"]),
        "captured_mask": int(move.get("captured_mask", 0)),
        "is_capture": bool(move["is_capture"]),
    }


def primitive_move_record(move):
    return primitive_rule_record(move)


def primitive_rule_catalog_df():
    import pandas as pd

    columns = ["from_mask", "to_mask", "captured_mask", "is_capture"]
    return pd.DataFrame.from_records(primitive_rule_records(), columns=columns)


def primitive_move_catalog_df():
    return primitive_rule_catalog_df()


def primitive_rule_requires_king(side, rule):
    _validate_side(side)
    dr = _row_delta(rule)
    return (side == "B" and dr < 0) or (side == "W" and dr > 0)


def primitive_rule_promotes(state, rule):
    state = as_state(state)
    from_mask = int(rule["from_mask"])
    if state.kings & from_mask:
        return False
    promo_mask = BLACK_PROMO_MASK if state.side == "B" else WHITE_PROMO_MASK
    return bool(int(rule["to_mask"]) & promo_mask)


def primitive_rule_applies(state, rule):
    state = as_state(state)
    mine = state.black if state.side == "B" else state.white
    theirs = state.white if state.side == "B" else state.black
    occupied = state.black | state.white

    from_mask = int(rule["from_mask"])
    to_mask = int(rule["to_mask"])
    captured_mask = int(rule["captured_mask"])

    return (
        (mine & from_mask) == from_mask
        and (occupied & to_mask) == 0
        and (captured_mask == 0 or (theirs & captured_mask) == captured_mask)
        and (not primitive_rule_requires_king(state.side, rule) or (state.kings & from_mask) == from_mask)
    )


def applicable_primitive_rules(state, rules=None, mandatory_capture=False, captures_only=False, from_mask=None):
    matches = []
    for rule in _rule_records(rules):
        if captures_only and not rule["is_capture"]:
            continue
        if from_mask is not None and int(rule["from_mask"]) != int(from_mask):
            continue
        if primitive_rule_applies(state, rule):
            matches.append(rule)

    if mandatory_capture:
        captures = [rule for rule in matches if rule["is_capture"]]
        return captures if captures else matches
    return matches


def apply_primitive_rule(state, rule, switch_side=True):
    state = as_state(state)
    if not primitive_rule_applies(state, rule):
        raise ValueError("rule conditions are not satisfied by the state")
    return state.apply_move(primitive_rule_move(rule), switch_side=switch_side)


def primitive_rule_state(rule, side="B"):
    _validate_side(side)
    from_mask = int(rule["from_mask"])
    captured_mask = int(rule["captured_mask"])
    needs_king = primitive_rule_requires_king(side, rule)

    if side == "B":
        black = from_mask
        white = captured_mask
    else:
        black = captured_mask
        white = from_mask

    kings = from_mask if needs_king else 0
    return BoardState(black, white, kings, side)


def primitive_rule_move(rule):
    return {
        "from_mask": int(rule["from_mask"]),
        "to_mask": int(rule["to_mask"]),
        "captured_mask": int(rule["captured_mask"]),
        "is_capture": bool(rule["is_capture"]),
    }


def primitive_rule_runtime_record(state, rule, rule_index=None):
    state = as_state(state)
    from_mask = int(rule["from_mask"])
    to_mask = int(rule["to_mask"])
    captured_mask = int(rule["captured_mask"])
    king = int(bool(state.kings & from_mask))
    promotion = int(primitive_rule_promotes(state, rule))
    capture = int(bool(captured_mask))

    if state.side == "B":
        is_black = from_mask
        is_white = captured_mask
        be_black = to_mask
        be_white = 0
    else:
        is_white = from_mask
        is_black = captured_mask
        be_black = 0
        be_white = to_mask

    be_empty = from_mask | captured_mask

    return {
        "rule_index": _rule_index(rule, rule_index),
        "is_black": is_black,
        "is_white": is_white,
        "is_empty": to_mask,
        "be_black": be_black,
        "be_white": be_white,
        "be_empty": be_empty,
        "black_to_move": 1 if state.side == "B" else 0,
        "king": king,
        "promotion": promotion,
        "capture": capture,
    }


def primitive_rule_runtime_records(side="both", rules=None):
    rule_rows = _rule_records(rules)
    records = []
    for runtime_side in _runtime_sides(side):
        for rule in rule_rows:
            if not primitive_rule_requires_king(runtime_side, rule):
                man_state = primitive_rule_state(rule, side=runtime_side)
                records.append(primitive_rule_runtime_record(man_state, rule, rule_index=len(records)))

            king_state = primitive_rule_state(rule, side=runtime_side)
            king_state = BoardState(
                king_state.black,
                king_state.white,
                king_state.kings | int(rule["from_mask"]),
                runtime_side,
            )
            records.append(primitive_rule_runtime_record(king_state, rule, rule_index=len(records)))
    return records


def primitive_rule_runtime_catalog_df(side="both", rules=None):
    import pandas as pd

    columns = [
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
    ]
    records = primitive_rule_runtime_records(side=side, rules=rules)
    df = pd.DataFrame.from_records(records, columns=["rule_index", *columns])
    return df.set_index("rule_index").rename_axis(None)


def moves_df(state, moves=None):
    import pandas as pd

    state = as_state(state)
    moves = state.legal_moves() if moves is None else moves
    return pd.DataFrame.from_records(
        move_record(move, state=state, step=1, turn_index=index) for index, move in enumerate(moves)
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


def _validate_side(side):
    if side not in ("B", "W"):
        raise ValueError("side must be 'B' or 'W'")


def _runtime_sides(side):
    if side is None or str(side).lower() in ("both", "all"):
        return ("B", "W")
    _validate_side(side)
    return (side,)


def _row_delta(rule):
    from_row, _ = square_from_mask(int(rule["from_mask"]))
    to_row, _ = square_from_mask(int(rule["to_mask"]))
    return to_row - from_row


def _rule_index(rule, fallback=None):
    if "__rule_index" in rule:
        return rule["__rule_index"]
    return fallback


def _rule_records(rules):
    if rules is None:
        return primitive_rule_records()
    if isinstance(rules, dict):
        return [rules]
    if hasattr(rules, "to_dict") and hasattr(rules, "columns"):
        rows = []
        for index, record in rules.to_dict("index").items():
            record["__rule_index"] = index
            rows.append(record)
        return rows
    if hasattr(rules, "to_dict") and not isinstance(rules, dict):
        record = rules.to_dict()
        if getattr(rules, "name", None) is not None:
            record["__rule_index"] = rules.name
        return [record]
    return list(rules)


def _mask_hex(mask):
    return f"0x{int(mask) & ((1 << 64) - 1):016x}"
