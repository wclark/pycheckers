"""Notebook-friendly board visualization helpers."""

from .bitboard import draw_board
from .rules import move_record
from .state import as_state


def show_state(state, dots=0, size=3, title=None, show=True):
    import matplotlib.pyplot as plt

    state = as_state(state)
    board_size = {1: 2.5, 2: 3.25, 3: 4}.get(size, 4)
    fig, ax = plt.subplots(1, 1, figsize=(board_size, board_size))
    draw_board(
        ax,
        state.black,
        state.white,
        state.kings,
        dots=dots,
        title=title or f"{state.side} to move",
    )
    if show:
        plt.show()
    return fig, ax


def show_turn(state, turn, size=2, show=True):
    import matplotlib.pyplot as plt

    states = as_state(state).turn_states(turn)
    board_size = {1: 2.5, 2: 3.25, 3: 4}.get(size, 3.25)
    fig, axes = plt.subplots(1, len(states), figsize=(board_size * len(states), board_size))
    if len(states) == 1:
        axes = [axes]
    for index, (ax, board_state) in enumerate(zip(axes, states)):
        title = "start" if index == 0 else f"step {index}"
        draw_board(ax, board_state.black, board_state.white, board_state.kings, title=title)
    if show:
        plt.show()
    return fig, axes


def show_move_rows(state, moves=None, size=2.4, title=None, show=True):
    state = as_state(state)
    moves = state.legal_moves() if moves is None else list(moves)
    rows = []
    for move in moves:
        after = state.apply_move(move)
        rows.append((state, move, after))
    return _show_rows(rows, size=size, title=title, show=show)


def show_turn_rows(state, turn, size=2.4, title=None, show=True):
    state = as_state(state)
    rows = []
    current = state
    for move in turn:
        after_move = current.apply_move(move, switch_side=False)
        rows.append((current, move, after_move))
        current = after_move
    if rows:
        before, move, after_move = rows[-1]
        rows[-1] = (before, move, state.apply_turn(turn))
    return _show_rows(rows, size=size, title=title, show=show)


def _show_rows(rows, size=2.1, title=None, show=True):
    import matplotlib.pyplot as plt

    if not rows:
        raise ValueError("at least one move row is required")

    fig, axes = plt.subplots(
        len(rows),
        4,
        figsize=(size * 6.2, size * len(rows)),
        gridspec_kw={"width_ratios": [1.55, 1, 1, 1]},
        squeeze=False,
    )
    if title:
        fig.suptitle(title)

    for index, (before, move, after) in enumerate(rows):
        metadata_ax, move_ax, before_ax, after_ax = axes[index]
        _draw_metadata(metadata_ax, before, move, index)
        draw_move_diagram(move_ax, before, move, title="move")
        draw_board(before_ax, before.black, before.white, before.kings, title="before")
        draw_board(after_ax, after.black, after.white, after.kings, title="after")

    fig.subplots_adjust(
        left=0.02,
        right=0.99,
        bottom=0.03,
        top=0.94 if title else 0.98,
        wspace=0.08,
        hspace=0.32,
    )
    if show:
        plt.show()
    return fig, axes


def draw_move_diagram(ax, state, move, title=None):
    from matplotlib.patches import FancyArrowPatch

    state = as_state(state)
    draw_board(ax, state.black, state.white, state.kings, title=title)
    from_r, from_c = _square_from_bit(move["from_mask"])
    to_r, to_c = _square_from_bit(move["to_mask"])

    _outline_square(ax, from_r, from_c, "#1f77b4", lw=3)
    _outline_square(ax, to_r, to_c, "#2ca02c", lw=3)
    if move["captured_mask"]:
        captured_r, captured_c = _square_from_bit(move["captured_mask"])
        _outline_square(ax, captured_r, captured_c, "#d62728", lw=3)

    arrow = FancyArrowPatch(
        _center(from_r, from_c),
        _center(to_r, to_c),
        arrowstyle="->",
        mutation_scale=15,
        linewidth=2.2,
        color="#1f77b4",
        shrinkA=12,
        shrinkB=12,
    )
    ax.add_patch(arrow)
    return ax


def _draw_metadata(ax, state, move, index):
    ax.axis("off")
    row = move_record(move, state=state, step=index + 1, turn_index=0)
    captured = (
        "-"
        if row["captured_r"] is None
        else f"({row['captured_r']}, {row['captured_c']})"
    )
    lines = [
        f"row {index + 1}",
        f"side: {row['side']}",
        f"from: ({row['from_r']}, {row['from_c']})",
        f"to:   ({row['to_r']}, {row['to_c']})",
        f"capture: {row['is_capture']}",
        f"captured: {captured}",
        f"promotion: {row['promotes']}",
        f"king move: {row['is_king']}",
        "",
        f"from_mask: {row['from_mask_hex']}",
        f"to_mask:   {row['to_mask_hex']}",
        f"cap_mask:  {row['captured_mask_hex']}",
        "",
        f"before.black: {row['before_black_hex']}",
        f"before.white: {row['before_white_hex']}",
        f"before.kings: {row['before_kings_hex']}",
        f"after.black:  {row['after_move_black_hex']}",
        f"after.white:  {row['after_move_white_hex']}",
        f"after.kings:  {row['after_move_kings_hex']}",
    ]
    ax.text(
        0,
        1,
        "\n".join(lines),
        va="top",
        ha="left",
        family="monospace",
        fontsize=7.2,
    )


def _outline_square(ax, row, col, color, lw=2):
    from matplotlib.patches import Rectangle

    ax.add_patch(
        Rectangle(
            (col + 0.05, 7 - row + 0.05),
            0.9,
            0.9,
            fill=False,
            ec=color,
            lw=lw,
            clip_on=False,
        )
    )


def _square_from_bit(mask):
    from .bitboard import square_from_mask

    return square_from_mask(mask)


def _center(row, col):
    return col + 0.5, 7 - row + 0.5
