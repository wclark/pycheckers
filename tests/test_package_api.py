import unittest

import matplotlib.pyplot as plt

from pycheckers import (
    BoardState,
    applicable_primitive_rules,
    apply_primitive_rule,
    legal_successors,
    moves_df,
    primitive_move_catalog_df,
    primitive_move_records,
    primitive_rule_applies,
    primitive_rule_catalog_df,
    primitive_rule_records,
    primitive_rule_requires_king,
    primitive_rule_runtime_catalog_df,
    primitive_rule_runtime_record,
    primitive_rule_state,
    show_move_rows,
    show_primitive_rule_rows,
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

    def test_primitive_move_catalog_lists_mask_rules(self):
        records = primitive_rule_records()
        df = primitive_rule_catalog_df()

        self.assertEqual(len(records), 170)
        self.assertEqual(len(primitive_move_records()), 170)
        self.assertEqual(len(df), 170)
        self.assertEqual(len(primitive_move_catalog_df()), 170)
        self.assertEqual(
            list(df.columns),
            [
                "from_mask",
                "to_mask",
                "captured_mask",
                "is_capture",
            ],
        )
        self.assertEqual(df["is_capture"].sum(), 72)
        self.assertEqual((~df["is_capture"]).sum(), 98)
        self.assertTrue((df.loc[~df["is_capture"], "captured_mask"] == 0).all())
        self.assertTrue((df.loc[df["is_capture"], "captured_mask"] != 0).all())
        self.assertFalse(
            {"rule_id", "side", "piece_type", "is_king", "required_king_mask", "dr", "dc"} & set(df.columns)
        )
        self.assertEqual(len(df[["from_mask", "to_mask", "captured_mask"]].drop_duplicates()), 170)
        self.assertEqual(list(df.index[:3]), [0, 1, 2])

    def test_primitive_rule_runtime_catalog_lists_preconditions_and_effects(self):
        runtime = primitive_rule_runtime_catalog_df()

        self.assertEqual(len(runtime), 510)
        self.assertEqual(list(runtime.index[:3]), [0, 1, 2])
        self.assertEqual(
            list(runtime.columns),
            [
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
            ],
        )
        self.assertTrue((runtime["is_empty"] != 0).all())
        self.assertTrue((runtime["be_empty"] != 0).all())
        self.assertEqual(runtime["black_to_move"].sum(), 255)
        self.assertEqual(runtime["king"].sum(), 340)
        self.assertEqual(runtime["promotion"].sum(), 26)
        self.assertEqual(runtime["capture"].sum(), 216)
        self.assertFalse(
            {
                "after_black",
                "after_white",
                "after_kings",
                "after_side",
                "applies",
                "captured_mask",
                "dr",
                "dc",
                "from_mask",
                "be_king",
                "is_capture",
                "is_king",
                "king_required",
                "black_to_move_mask",
                "require_black_mask",
                "require_white_mask",
                "require_king_mask",
                "make_position_side",
                "make_king_mask",
                "make_empty_mask",
                "make_position_mask",
                "needs_king",
                "promote_mask",
                "promotes",
                "required_empty_mask",
                "required_king_mask",
                "rule_id",
                "side",
                "to_mask",
            }
            & set(runtime.columns)
        )

        first = runtime.iloc[0]
        self.assertEqual(first["is_black"], square_mask(0, 1))
        self.assertEqual(first["is_white"], 0)
        self.assertEqual(first["is_empty"], square_mask(1, 0))
        self.assertEqual(first["be_black"], square_mask(1, 0))
        self.assertEqual(first["black_to_move"], 1)
        self.assertEqual(first["king"], 0)
        self.assertEqual(first["promotion"], 0)
        self.assertEqual(first["capture"], 0)

        first_white = runtime.loc[runtime["black_to_move"] == 0].iloc[0]
        self.assertEqual(first_white["is_black"], 0)
        self.assertNotEqual(first_white["is_white"], 0)
        self.assertEqual(first_white["be_black"], 0)
        self.assertNotEqual(first_white["be_white"], 0)

    def test_primitive_rules_apply_with_bitmask_conditions(self):
        state = BoardState.initial()
        matching_rules = applicable_primitive_rules(state)
        matching_forced_rules = applicable_primitive_rules(state, mandatory_capture=True)
        legal = state.legal_moves()

        self.assertEqual(len(matching_rules), len(legal))
        self.assertEqual(len(matching_forced_rules), len(legal))
        self.assertEqual(
            {(rule["from_mask"], rule["to_mask"], rule["captured_mask"]) for rule in matching_rules},
            {(move["from_mask"], move["to_mask"], move["captured_mask"]) for move in legal},
        )

        for side in ("B", "W"):
            for rule in primitive_rule_records():
                minimal_state = primitive_rule_state(rule, side=side)
                self.assertTrue(primitive_rule_applies(minimal_state, rule))
                self.assertEqual(
                    bool(minimal_state.kings & rule["from_mask"]),
                    primitive_rule_requires_king(side, rule),
                )
                next_state = apply_primitive_rule(minimal_state, rule)
                self.assertEqual(next_state.side, "W" if minimal_state.side == "B" else "B")

        king_state = BoardState(square_mask(2, 1), 0, square_mask(2, 1), "B")
        forward_rule = next(
            rule
            for rule in applicable_primitive_rules(king_state)
            if not primitive_rule_requires_king("B", rule) and rule["to_mask"] == square_mask(3, 0)
        )
        next_king_state = apply_primitive_rule(king_state, forward_rule)
        self.assertEqual(next_king_state.kings, square_mask(3, 0))
        self.assertEqual(primitive_rule_runtime_record(king_state, forward_rule)["king"], 1)

        capture_state = BoardState(square_mask(2, 1), square_mask(3, 2), 0, "B")
        forced_rules = applicable_primitive_rules(capture_state, mandatory_capture=True)
        self.assertEqual(len(forced_rules), 1)
        self.assertTrue(forced_rules[0]["is_capture"])

    def test_display_helpers_return_figures(self):
        state = BoardState.initial()
        turn = state.legal_turns()[0]

        fig, _ax = show_state(state, size=1, show=False)
        turn_fig, _axes = show_turn(state, turn, size=1, show=False)
        move_rows_fig, _move_axes = show_move_rows(state, state.legal_moves()[:1], size=1, show=False)
        turn_rows_fig, _turn_axes = show_turn_rows(state, turn, size=1, show=False)
        rule_rows = show_primitive_rule_rows(primitive_rule_records()[:1], side="B", size=1, show=False)
        runtime_rule_rows = show_primitive_rule_rows(
            primitive_rule_runtime_catalog_df().iloc[:1],
            size=1,
            show=False,
        )

        self.assertIsNotNone(fig)
        self.assertIsNotNone(turn_fig)
        self.assertIsNotNone(move_rows_fig)
        self.assertIsNotNone(turn_rows_fig)
        self.assertEqual(len(rule_rows), 2)
        self.assertEqual(len(runtime_rule_rows), 1)
        self.assertEqual(rule_rows[0][0]._suptitle.get_text(), "rule 0")
        self.assertEqual(rule_rows[1][0]._suptitle.get_text(), "rule 1")
        self.assertEqual(rule_rows[0][0].get_size_inches().tolist(), rule_rows[1][0].get_size_inches().tolist())
        for rule_fig, rule_axes in [*rule_rows, *runtime_rule_rows]:
            self.assertIsNotNone(rule_fig)
            self.assertEqual(rule_axes.shape, (3,))
            summary = rule_axes[2].texts[0].get_text()
            self.assertIn("capture:", summary)
            self.assertIn("promotion:", summary)
            self.assertNotIn("move:", summary)
            self.assertNotIn("rule_index", summary)
        plt.close(fig)
        plt.close(turn_fig)
        plt.close(move_rows_fig)
        plt.close(turn_rows_fig)
        for rule_fig, _rule_axes in [*rule_rows, *runtime_rule_rows]:
            plt.close(rule_fig)


if __name__ == "__main__":
    unittest.main()
