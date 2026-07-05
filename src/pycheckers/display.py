"""Notebook-friendly board visualization helpers."""

from .bitboard import draw_board
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
