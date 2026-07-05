"""Notebook-friendly board visualization helpers."""

from .bitboard import MASK64, draw_board, is_dark, square_mask
from .rules import (
    move_record,
    primitive_rule_records,
    primitive_rule_runtime_records,
)
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
    for index, (ax, board_state) in enumerate(zip(axes, states, strict=True)):
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


def show_primitive_rule_rows(
    rules=None,
    side="both",
    size=3.2,
    title=None,
    show=True,
):
    rows = _runtime_rule_records(rules, side)
    if not rows:
        raise ValueError("at least one rule row is required")

    figures = []
    for rule in rows:
        row_title = _rule_row_title(rule, title)
        fig, axes = _show_rule_row(rule, size=size, title=row_title)
        figures.append((fig, axes))
        if show:
            _display_figure(fig)
            _close_figure(fig)
    return figures


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


def _show_rule_row(rule, size=3.2, title=None):
    import matplotlib.pyplot as plt

    columns = ["conditions", "effects", "summary"]
    fig, axes = plt.subplots(
        1,
        len(columns),
        figsize=(size * 3.5, size),
        gridspec_kw={"width_ratios": [1, 1, 0.9]},
        squeeze=True,
    )
    if title:
        fig.suptitle(title, y=0.985, fontsize=9)

    for ax, column in zip(axes, columns, strict=True):
        ax.set_title(column)

    _draw_conditions_board(axes[0], rule)
    _draw_effects_board(axes[1], rule)
    _draw_rule_info(axes[2], rule)

    fig.subplots_adjust(
        left=0.02,
        right=0.99,
        bottom=0.08,
        top=0.76,
        wspace=0.08,
    )
    return fig, axes


def _display_figure(fig):
    try:
        from IPython.display import display
    except ImportError:
        import matplotlib.pyplot as plt

        plt.show()
    else:
        display(fig)


def _close_figure(fig):
    import matplotlib.pyplot as plt

    plt.close(fig)


def draw_move_diagram(ax, state, move, title=None):
    from matplotlib.patches import FancyArrowPatch

    state = as_state(state)
    draw_board(ax, state.black, state.white, state.kings, title=title)
    from_r, from_c = _square_from_bit(move["from_mask"])
    to_r, to_c = _square_from_bit(move["to_mask"])

    _outline_square(ax, from_r, from_c, "#1f77b4", lw=1.6)
    _outline_square(ax, to_r, to_c, "#2ca02c", lw=1.6)
    if move["captured_mask"]:
        captured_r, captured_c = _square_from_bit(move["captured_mask"])
        _outline_square(ax, captured_r, captured_c, "#d62728", lw=1.6)

    arrow = FancyArrowPatch(
        _center(from_r, from_c),
        _center(to_r, to_c),
        arrowstyle="->",
        mutation_scale=12,
        linewidth=1.4,
        color="#1f77b4",
        shrinkA=12,
        shrinkB=12,
    )
    ax.add_patch(arrow)
    return ax


def _draw_metadata(ax, state, move, index):
    ax.axis("off")
    row = move_record(move, state=state, step=index + 1, turn_index=0)
    captured = "-" if row["captured_r"] is None else f"({row['captured_r']}, {row['captured_c']})"
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


def _draw_conditions_board(ax, rule):
    _draw_base_rule_board(ax)

    _draw_mask_markers(ax, rule["is_empty"], "empty")
    _draw_mask_markers(ax, rule["is_white"], "white")
    _draw_mask_markers(ax, rule["is_black"], "black")
    if rule["king"]:
        _draw_mask_markers(ax, _mover_condition_mask(rule), "king_overlay")


def _draw_effects_board(ax, rule):
    _draw_base_rule_board(ax)
    _draw_mask_markers(ax, rule["be_empty"], "empty")
    _draw_mask_markers(ax, rule["be_white"], "white")
    _draw_mask_markers(ax, rule["be_black"], "black")
    if rule["king"] or rule["promotion"]:
        _draw_mask_markers(ax, _mover_effect_mask(rule), "king_overlay")


def _draw_rule_info(ax, rule):
    ax.axis("off")
    lines = [
        f"side: {_side_label(rule)}",
        f"king: {int(rule['king'])}",
        f"capture: {int(rule['capture'])}",
        f"promotion: {int(rule['promotion'])}",
    ]
    ax.text(
        0,
        0.96,
        "\n".join(lines),
        va="top",
        ha="left",
        family="monospace",
        fontsize=8.6,
    )


def _draw_base_rule_board(ax):
    from matplotlib.patches import Rectangle

    ax.set_xlim(-0.02, 8.02)
    ax.set_ylim(-0.02, 8.02)
    ax.set_aspect("equal")
    ax.axis("off")

    for row in range(8):
        for col in range(8):
            y = 7 - row
            fill = "#dddddd" if is_dark(row, col) else "white"
            ax.add_patch(Rectangle((col, y), 1, 1, fc=fill, ec="#333333", lw=0.5))

    ax.add_patch(Rectangle((0, 0), 8, 8, fill=False, ec="#222222", lw=1.1, clip_on=False))


def _draw_mask_markers(ax, mask, kind):
    mask = int(mask) & MASK64
    for row in range(8):
        for col in range(8):
            if mask & square_mask(row, col):
                _draw_mask_marker(ax, col, 7 - row, kind)


def _draw_mask_marker(ax, col, y, kind):
    from matplotlib.patches import Circle

    if kind == "white":
        ax.add_patch(
            Circle(
                (col + 0.5, y + 0.5),
                0.43,
                fc="#fafafa",
                ec="#111111",
                lw=1.15,
                zorder=3,
            )
        )
    elif kind == "black":
        ax.add_patch(
            Circle(
                (col + 0.5, y + 0.5),
                0.43,
                fc="#111111",
                ec="#111111",
                lw=1.15,
                zorder=3,
            )
        )
    elif kind == "king_overlay":
        _draw_king_overlay(ax, col, y)
    else:
        ax.add_patch(Circle((col + 0.5, y + 0.5), 0.35, fill=False, ec="#111111", lw=1.05, ls=":", zorder=3))


def _draw_king_overlay(ax, col, y):
    import matplotlib.patheffects as path_effects
    from matplotlib.font_manager import FontProperties
    from matplotlib.patches import PathPatch
    from matplotlib.textpath import TextPath
    from matplotlib.transforms import Affine2D

    path = TextPath(
        (0, 0),
        "K",
        size=1,
        prop=FontProperties(family="DejaVu Sans", weight="bold"),
    )
    bbox = path.get_extents()
    scale = 0.48 / bbox.height
    transform = (
        Affine2D()
        .translate(-(bbox.x0 + bbox.width / 2), -(bbox.y0 + bbox.height / 2))
        .scale(scale)
        .translate(col + 0.5, y + 0.5)
        + ax.transData
    )
    patch = PathPatch(path, fc="#f2c84b", ec="none", transform=transform, zorder=4)
    patch.set_path_effects([path_effects.withStroke(linewidth=1.15, foreground="#111111")])
    ax.add_patch(patch)


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


def _rule_row_title(rule, title=None):
    rule_title = f"rule {rule['rule_index']}"
    return f"{title}: {rule_title}" if title else rule_title


def _mover_condition_mask(rule):
    return rule["is_black"] if int(rule["black_to_move"]) else rule["is_white"]


def _mover_effect_mask(rule):
    return rule["be_black"] if int(rule["black_to_move"]) else rule["be_white"]


def _side_label(rule):
    return "black" if int(rule["black_to_move"]) else "white"


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


def _runtime_rule_records(rules, side):
    rows = _rule_records(rules)
    if rules is None:
        rows = primitive_rule_records()

    runtime_rows = []
    for row in rows:
        if _has_runtime_masks(row):
            runtime = dict(row)
            runtime["rule_index"] = runtime.get("rule_index", runtime.get("__rule_index", len(runtime_rows)))
            runtime_rows.append(runtime)
            continue

        for runtime in primitive_rule_runtime_records(side=side, rules=[row]):
            runtime["rule_index"] = len(runtime_rows)
            runtime_rows.append(runtime)
    return runtime_rows


def _has_runtime_masks(rule):
    return {
        "black_to_move",
        "is_black",
        "is_white",
        "is_empty",
        "be_black",
        "be_white",
        "be_empty",
        "king",
        "promotion",
        "capture",
    } <= set(rule)
