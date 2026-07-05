import unittest

import matplotlib.pyplot as plt

from pycheckers import (
    BoardState,
    legal_successors,
    moves_df,
    show_move_rows,
    show_state,
    show_turn,
    show_turn_rows,
    square_mask,
    turns_df,
)


class PackageApiTests(unittest.TestCase):
    def test_board_state_wraps_initial_position(self):
        state = BoardState.initial()

        self.assertEqual(state.black_count, 12)
        self.assertEqual(state.white_count, 12)
        self.assertEqual(state.king_count, 0)
        self.assertEqual(state.side, "B")
        self.assertEqual(len(state.legal_moves()), 7)

    def test_board_state_rejects_invalid_positions(self):
        with self.assertRaises(ValueError):
            BoardState(square_mask(0, 0), 0, 0, "B")
        with self.assertRaises(ValueError):
            BoardState(square_mask(2, 1), square_mask(2, 1), 0, "B")
        with self.assertRaises(ValueError):
            BoardState(square_mask(2, 1), 0, square_mask(3, 2), "B")
        with self.assertRaises(ValueError):
            BoardState(square_mask(2, 1), 0, 0, "red")

    def test_forced_capture_suppresses_quiet_moves(self):
        state = BoardState(square_mask(2, 1), square_mask(3, 2), 0, "B")
        moves = state.legal_moves()
        df = moves_df(state)

        self.assertEqual(len(moves), 1)
        self.assertTrue(moves[0]["is_capture"])
        self.assertTrue(df.iloc[0]["is_capture"])
        self.assertEqual((df.iloc[0]["from_r"], df.iloc[0]["from_c"]), (2, 1))
        self.assertEqual((df.iloc[0]["to_r"], df.iloc[0]["to_c"]), (4, 3))
        self.assertEqual(df.iloc[0]["from_mask_hex"], "0x0000000000020000")
        self.assertEqual(df.iloc[0]["captured_mask_hex"], "0x0000000004000000")

    def test_multi_jump_turn_states_keep_side_until_turn_ends(self):
        state = BoardState(
            square_mask(2, 1),
            square_mask(3, 2) | square_mask(5, 4),
            0,
            "B",
        )
        turns = state.legal_turns()
        states = state.turn_states(turns[0])
        df = turns_df(state, turns)

        self.assertEqual(len(turns), 1)
        self.assertEqual(len(turns[0]), 2)
        self.assertEqual(len(states), 3)
        self.assertEqual(states[1].side, "B")
        self.assertEqual(states[2].side, "W")
        self.assertEqual(states[2].black, square_mask(6, 5))
        self.assertEqual(states[2].white, 0)
        self.assertEqual(len(df), 2)
        self.assertTrue(df["is_capture"].all())

    def test_promotion_is_visible_in_move_dataframe(self):
        state = BoardState(square_mask(6, 1), square_mask(0, 1), 0, "B")
        df = moves_df(state)
        successors = legal_successors(state)

        self.assertEqual(len(df), 2)
        self.assertTrue(df["promotes"].all())
        self.assertTrue(all(successor.king_count == 1 for successor in successors))
        self.assertTrue(all(successor.side == "W" for successor in successors))

    def test_display_helpers_return_figures(self):
        state = BoardState.initial()
        turn = state.legal_turns()[0]

        fig, _ax = show_state(state, size=1, show=False)
        turn_fig, _axes = show_turn(state, turn, size=1, show=False)
        move_rows_fig, _move_axes = show_move_rows(state, state.legal_moves()[:1], size=1, show=False)
        turn_rows_fig, _turn_axes = show_turn_rows(state, turn, size=1, show=False)

        self.assertIsNotNone(fig)
        self.assertIsNotNone(turn_fig)
        self.assertIsNotNone(move_rows_fig)
        self.assertIsNotNone(turn_rows_fig)
        plt.close(fig)
        plt.close(turn_fig)
        plt.close(move_rows_fig)
        plt.close(turn_rows_fig)


if __name__ == "__main__":
    unittest.main()
