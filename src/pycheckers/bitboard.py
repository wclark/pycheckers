MASK64 = (1 << 64) - 1
DARKS_MASK = 0x55AA55AA55AA55AA
BLACK_PROMO_MASK = 0x5500000000000000
WHITE_PROMO_MASK = 0x00000000000000AA
_MOVE_TEMPLATES = None


def is_dark(r, c):
    return (r + c) % 2 == 1


def square_mask(r, c):
    if not (0 <= r < 8 and 0 <= c < 8):
        raise ValueError(f"square out of range: {(r, c)}")
    return 1 << (8 * r + c)


def square_from_mask(mask):
    if mask <= 0 or mask & (mask - 1):
        raise ValueError("mask must contain exactly one bit")
    idx = mask.bit_length() - 1
    if idx >= 64:
        raise ValueError("mask is outside the 8x8 board")
    return divmod(idx, 8)


def initial_position():
    black = 0x0000000000AA55AA
    white = 0x55AA550000000000
    kings = 0
    side = "B"
    return black, white, kings, side


def validate_position(black, white, kings):
    black &= MASK64
    white &= MASK64
    kings &= MASK64
    occ = black | white

    if black & white:
        raise ValueError("black and white bitboards overlap")
    if kings & ~occ:
        raise ValueError("kings must be a subset of occupied squares")
    if occ & ~DARKS_MASK:
        raise ValueError("all pieces must be on dark squares")
    return True


def generate_move_templates():
    return [dict(move) for move in _move_templates()]


def _move_templates():
    global _MOVE_TEMPLATES
    if _MOVE_TEMPLATES is None:
        _MOVE_TEMPLATES = tuple(_build_move_templates())
    return _MOVE_TEMPLATES


def _build_move_templates():
    templates = []
    seen = set()

    for r in range(8):
        for c in range(8):
            if not is_dark(r, c):
                continue

            from_mask = square_mask(r, c)
            for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                tr = r + dr
                tc = c + dc
                if 0 <= tr < 8 and 0 <= tc < 8:
                    to_mask = square_mask(tr, tc)
                    _add_template(
                        templates,
                        seen,
                        from_mask,
                        to_mask,
                        0,
                        dr,
                        dc,
                        False,
                    )

                tr = r + 2 * dr
                tc = c + 2 * dc
                mr = r + dr
                mc = c + dc
                if 0 <= tr < 8 and 0 <= tc < 8:
                    to_mask = square_mask(tr, tc)
                    captured_mask = square_mask(mr, mc)
                    _add_template(
                        templates,
                        seen,
                        from_mask,
                        to_mask,
                        captured_mask,
                        2 * dr,
                        2 * dc,
                        True,
                    )

    return templates


def _add_template(
    templates,
    seen,
    from_mask,
    to_mask,
    captured_mask,
    dr,
    dc,
    is_capture,
):
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
            "is_capture": is_capture,
        }
    )


def legal_moves(black, white, kings, side):
    candidates = _applicable_moves(black, white, kings, side)
    captures = [move for move in candidates if move["is_capture"]]
    return captures if captures else candidates


def capture_chains(black, white, kings, side, from_mask=None):
    captures = _applicable_moves(
        black,
        white,
        kings,
        side,
        captures_only=True,
        from_mask=from_mask,
    )

    chains = []
    for move in captures:
        mover_was_king = bool(kings & move["from_mask"])
        promotes = _move_promotes(kings, side, move)
        nb, nw, nk, _ = apply_move(
            black,
            white,
            kings,
            side,
            move,
            switch_side=False,
        )

        # In American checkers, a man that crowns during a jump stops there.
        if promotes and not mover_was_king:
            chains.append([move])
            continue

        tails = capture_chains(nb, nw, nk, side, from_mask=move["to_mask"])
        if tails:
            chains.extend([[move] + tail for tail in tails])
        else:
            chains.append([move])

    return chains


def legal_turns(black, white, kings, side):
    chains = capture_chains(black, white, kings, side)
    if chains:
        return chains
    return [[move] for move in legal_moves(black, white, kings, side)]


def apply_move(black, white, kings, side, move, switch_side=True):
    black &= MASK64
    white &= MASK64
    kings &= MASK64
    validate_position(black, white, kings)
    _validate_side(side)

    from_mask = move["from_mask"]
    to_mask = move["to_mask"]
    captured_mask = move["captured_mask"]

    if side == "B":
        new_black = ((black & ~from_mask) | to_mask) & MASK64
        new_white = white & ~captured_mask & MASK64
    else:
        new_white = ((white & ~from_mask) | to_mask) & MASK64
        new_black = black & ~captured_mask & MASK64

    mover_was_king = bool(kings & from_mask)
    promotes = _move_promotes(kings, side, move)

    new_kings = (
        (kings & ~from_mask)
        | (to_mask if mover_was_king else 0)
        | (to_mask if promotes else 0)
    ) & (new_black | new_white) & MASK64

    new_side = _other_side(side) if switch_side else side
    validate_position(new_black, new_white, new_kings)
    return new_black, new_white, new_kings, new_side


def apply_turn(black, white, kings, side, turn):
    if not turn:
        raise ValueError("turn must contain at least one primitive move")

    current_side = side
    for move in turn:
        black, white, kings, current_side = apply_move(
            black,
            white,
            kings,
            current_side,
            move,
            switch_side=False,
        )

    return black, white, kings, _other_side(side)


def is_quiet_man_state(state, pieces_per_side=12):
    black, white, kings, side = state
    try:
        validate_position(black, white, kings)
        _validate_side(side)
    except ValueError:
        return False
    return (
        kings == 0
        and black.bit_count() == pieces_per_side
        and white.bit_count() == pieces_per_side
    )


def quiet_man_exit_reason(state, move):
    black, white, kings, side = state
    reasons = []
    if move["is_capture"]:
        reasons.append("capture")
    if _move_promotes(kings, side, move):
        reasons.append("promotion")
    return "+".join(reasons) if reasons else None


def expand_quiet_man_states(
    states,
    frontier=None,
    expanded=None,
    boundary_states=None,
    boundary_edges=None,
    terminal_states=None,
    transitions=None,
    parents=None,
    predecessors=None,
    pieces_per_side=12,
    max_processed=None,
):
    """Expand one layer of non-capturing, non-promoting man-only states.

    `states` is mutated in place. `expanded` prevents recomputing states that
    were already considered. `boundary_states`, when provided, is updated with
    states that have a legal capture or promotion transition out of this set.
    """
    if expanded is None:
        expanded = set()
    if boundary_states is None:
        boundary_states = {}
    if terminal_states is None:
        terminal_states = set()
    if transitions is None:
        transitions = set()
    if parents is None:
        parents = {}
    if predecessors is None:
        predecessors = {}
    if frontier is None:
        frontier = [state for state in states if state not in expanded]

    next_frontier = set()
    processed = 0
    skipped_expanded = 0
    new_states = 0
    duplicate_states = 0
    new_transitions = 0
    duplicate_transitions = 0
    quiet_moves = 0
    boundary_moves = 0
    boundary_source_states = 0
    terminal_source_states = 0
    capture_moves = 0
    promotion_moves = 0
    capture_promotion_moves = 0

    for state in frontier:
        if state in expanded:
            skipped_expanded += 1
            continue
        if max_processed is not None and processed >= max_processed:
            next_frontier.add(state)
            continue
        if not is_quiet_man_state(state, pieces_per_side=pieces_per_side):
            raise ValueError(f"not a quiet {pieces_per_side}-man state: {state!r}")

        black, white, kings, side = state
        expanded.add(state)
        processed += 1
        moves = legal_moves(black, white, kings, side)

        if not moves:
            terminal_states.add(state)
            terminal_source_states += 1
            continue

        state_had_boundary = False
        for move in moves:
            reason = quiet_man_exit_reason(state, move)
            if reason:
                state_had_boundary = True
                boundary_moves += 1
                if reason == "capture":
                    capture_moves += 1
                elif reason == "promotion":
                    promotion_moves += 1
                elif reason == "capture+promotion":
                    capture_promotion_moves += 1
                _record_boundary_state(boundary_states, state, reason)
                if boundary_edges is not None:
                    boundary_edges.append((state, move, reason))
                continue

            next_state = apply_move(black, white, kings, side, move)
            if not is_quiet_man_state(next_state, pieces_per_side=pieces_per_side):
                raise ValueError(f"quiet move left the quiet state set: {move!r}")

            quiet_moves += 1
            transition = (state, next_state)
            if transition not in transitions:
                transitions.add(transition)
                predecessors.setdefault(next_state, []).append((state, move))
                new_transitions += 1
            else:
                duplicate_transitions += 1

            if next_state not in states:
                states.add(next_state)
                next_frontier.add(next_state)
                new_states += 1
                parents.setdefault(next_state, (state, move))
            else:
                duplicate_states += 1
                parents.setdefault(next_state, (state, move))

        if state_had_boundary:
            boundary_source_states += 1

    return {
        "processed": processed,
        "skipped_expanded": skipped_expanded,
        "new_states": new_states,
        "duplicate_states": duplicate_states,
        "new_transitions": new_transitions,
        "duplicate_transitions": duplicate_transitions,
        "total_transitions": len(transitions),
        "total_states": len(states),
        "quiet_moves": quiet_moves,
        "boundary_moves": boundary_moves,
        "boundary_source_states": boundary_source_states,
        "terminal_source_states": terminal_source_states,
        "capture_moves": capture_moves,
        "promotion_moves": promotion_moves,
        "capture_promotion_moves": capture_promotion_moves,
        "boundary_states": len(boundary_states),
        "terminal_states": len(terminal_states),
        "next_frontier": next_frontier,
        "expanded": expanded,
        "boundary_state_map": boundary_states,
        "terminal_state_set": terminal_states,
        "transition_set": transitions,
        "parent_map": parents,
        "predecessor_map": predecessors,
    }


def explore_quiet_man_positions(
    start_state=None,
    pieces_per_side=12,
    max_layers=None,
    max_processed_per_layer=None,
):
    if start_state is None:
        start_state = initial_position()

    states = {start_state}
    frontier = {start_state}
    expanded = set()
    boundary_states = {}
    terminal_states = set()
    transitions = set()
    parents = {start_state: None}
    predecessors = {start_state: []}
    layers = []

    while frontier and (max_layers is None or len(layers) < max_layers):
        result = expand_quiet_man_states(
            states,
            frontier=frontier,
            expanded=expanded,
            boundary_states=boundary_states,
            terminal_states=terminal_states,
            transitions=transitions,
            parents=parents,
            predecessors=predecessors,
            pieces_per_side=pieces_per_side,
            max_processed=max_processed_per_layer,
        )
        layers.append(
            {
                key: value
                for key, value in result.items()
                if key
                not in (
                    "next_frontier",
                    "expanded",
                    "boundary_state_map",
                    "terminal_state_set",
                    "transition_set",
                    "parent_map",
                    "predecessor_map",
                )
            }
        )
        frontier = result["next_frontier"]

    return {
        "states": states,
        "frontier": frontier,
        "expanded": expanded,
        "boundary_states": boundary_states,
        "terminal_states": terminal_states,
        "transitions": transitions,
        "parents": parents,
        "predecessors": predecessors,
        "layers": layers,
    }


def bits_from_grid(grid):
    lines = _clean_board_lines(grid)
    mask = 0
    for r, line in enumerate(lines):
        for c, char in enumerate(line):
            bit = square_mask(r, c)
            if char in "1xX":
                mask |= bit
            elif char in "0._":
                pass
            else:
                raise ValueError(f"invalid grid character: {char!r}")
    return mask


def grid_from_bits(mask):
    mask &= MASK64
    rows = []
    for r in range(8):
        row = []
        for c in range(8):
            row.append("1" if mask & square_mask(r, c) else "0")
        rows.append("".join(row))
    return "\n".join(rows)


def bitboards_from_ascii(board):
    lines = _clean_board_lines(board)
    black = 0
    white = 0
    kings = 0

    for r, line in enumerate(lines):
        for c, char in enumerate(line):
            bit = square_mask(r, c)
            if char == "b":
                black |= bit
            elif char == "B":
                black |= bit
                kings |= bit
            elif char == "w":
                white |= bit
            elif char == "W":
                white |= bit
                kings |= bit
            elif char in "0._":
                pass
            else:
                raise ValueError(f"invalid board character: {char!r}")

    validate_position(black, white, kings)
    return black, white, kings


def show_board(black, white, kings, dots=0, other=None, size=3):
    import matplotlib.pyplot as plt

    n = 2 if other is not None else 1
    board_size = {1: 2.5, 2: 3.25, 3: 4}.get(size, 4)
    fig, axes = plt.subplots(1, n, figsize=(board_size * n, board_size))
    if n == 1:
        axes = [axes]

    boards = [(black, white, kings, dots)]
    if other is not None:
        if len(other) == 3:
            ob, ow, ok = other
            od = 0
        elif len(other) == 4:
            ob, ow, ok, od = other
        else:
            raise ValueError("other must be (black, white, kings) or include dots")
        boards.append((ob, ow, ok, od))

    for ax, (bmask, wmask, kmask, dmask) in zip(axes, boards):
        draw_board(ax, bmask, wmask, kmask, dots=dmask)

    plt.show()
    return fig, axes


def draw_board(ax, black, white, kings, dots=0, title=None):
    from matplotlib.patches import Circle, Rectangle

    black &= MASK64
    white &= MASK64
    kings &= MASK64
    dots &= MASK64
    ax.set_xlim(-0.02, 8.02)
    ax.set_ylim(-0.02, 8.02)
    ax.set_aspect("equal")
    ax.axis("off")

    for r in range(8):
        for c in range(8):
            y = 7 - r
            bit = square_mask(r, c)
            fill = "#dddddd" if is_dark(r, c) else "white"
            ax.add_patch(Rectangle((c, y), 1, 1, fc=fill, ec="black", lw=1))

            if (black | white) & bit:
                is_black_piece = bool(black & bit)
                piece_fill = "black" if is_black_piece else "white"
                edge = "white" if is_black_piece else "black"
                ax.add_patch(
                    Circle(
                        (c + 0.5, y + 0.5),
                        0.38,
                        fc=piece_fill,
                        ec=edge,
                        lw=1.2,
                    )
                )
                if kings & bit:
                    ax.text(
                        c + 0.5,
                        y + 0.5,
                        "K",
                        ha="center",
                        va="center",
                        fontsize=11,
                        color=edge,
                        weight="bold",
                    )
            elif dots & bit:
                ax.add_patch(
                    Circle(
                        (c + 0.5, y + 0.5),
                        0.34,
                        fill=False,
                        ec="black",
                        lw=1,
                        ls=":",
                    )
                )

    ax.add_patch(Rectangle((0, 0), 8, 8, fill=False, ec="black", lw=1.5, clip_on=False))
    if title:
        ax.set_title(title)
    return ax


def _applicable_moves(
    black,
    white,
    kings,
    side,
    captures_only=False,
    from_mask=None,
):
    black &= MASK64
    white &= MASK64
    kings &= MASK64
    validate_position(black, white, kings)
    _validate_side(side)

    mine = black if side == "B" else white
    theirs = white if side == "B" else black
    occ = black | white
    moves = []

    for move in _move_templates():
        if captures_only and not move["is_capture"]:
            continue
        if from_mask is not None and move["from_mask"] != from_mask:
            continue

        if not (mine & move["from_mask"]):
            continue
        if occ & move["to_mask"]:
            continue
        if move["captured_mask"] and not (theirs & move["captured_mask"]):
            continue
        if _need_king(side, move["dr"]) and not (kings & move["from_mask"]):
            continue

        moves.append(move)

    return moves


def _need_king(side, dr):
    return (side == "B" and dr < 0) or (side == "W" and dr > 0)


def _move_promotes(kings, side, move):
    if kings & move["from_mask"]:
        return False
    promo_mask = BLACK_PROMO_MASK if side == "B" else WHITE_PROMO_MASK
    return bool(move["to_mask"] & promo_mask)


def _record_boundary_state(boundary_states, state, reason):
    info = boundary_states.setdefault(
        state,
        {"capture": 0, "promotion": 0, "capture+promotion": 0, "moves": 0},
    )
    if reason not in info:
        info[reason] = 0
    info[reason] += 1
    info["moves"] += 1


def _other_side(side):
    _validate_side(side)
    return "W" if side == "B" else "B"


def _validate_side(side):
    if side not in ("B", "W"):
        raise ValueError("side must be 'B' or 'W'")


def _clean_board_lines(board):
    lines = [line.replace(" ", "") for line in str(board).strip().splitlines()]
    if len(lines) != 8 or any(len(line) != 8 for line in lines):
        raise ValueError("board text must have exactly 8 rows of 8 characters")
    return lines
