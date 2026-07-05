import unittest

from pycheckers import (
    FORCED_CAPTURE,
    PROMOTION,
    QUIET,
    QuietTablebase,
    apply_turn,
    capture_chains,
    initial_position,
    inspect_game_state,
    legal_moves,
    pack_state32,
    split_state_key,
    square_mask,
)


class PackageApiTests(unittest.TestCase):
    def test_public_rule_api_generates_legal_moves(self):
        black, white, kings, side = initial_position()
        moves = legal_moves(black, white, kings, side)

        self.assertEqual(len(moves), 7)
        self.assertTrue(all(not move["is_capture"] for move in moves))

    def test_public_rule_api_handles_multi_jump_turn(self):
        black = square_mask(2, 1)
        white = square_mask(3, 2) | square_mask(5, 4)
        kings = 0

        chains = capture_chains(black, white, kings, "B")
        self.assertEqual(len(chains), 1)
        self.assertEqual(len(chains[0]), 2)

        new_black, new_white, new_kings, new_side = apply_turn(
            black,
            white,
            kings,
            "B",
            chains[0],
        )
        self.assertEqual(new_black, square_mask(6, 5))
        self.assertEqual(new_white, 0)
        self.assertEqual(new_kings, 0)
        self.assertEqual(new_side, "W")

    def test_inspect_game_state_separates_quiet_capture_and_promotion(self):
        initial_info = inspect_game_state(initial_position())
        self.assertEqual(len(initial_info["metadata_successors"][QUIET]), 7)
        self.assertFalse(initial_info["forced_capture"])
        self.assertFalse(initial_info["promotion_possible"])
        self.assertFalse(initial_info["terminal"])

        capture_info = inspect_game_state(
            (square_mask(2, 1), square_mask(3, 2), 0, "B"),
            pieces_per_side=1,
        )
        self.assertEqual(capture_info["quiet_successors"], set())
        self.assertTrue(capture_info["forced_capture"])
        self.assertEqual(len(capture_info["metadata_successors"][FORCED_CAPTURE]), 1)

        promotion_info = inspect_game_state(
            (square_mask(6, 1), square_mask(0, 1), 0, "B"),
            pieces_per_side=1,
        )
        self.assertEqual(promotion_info["quiet_successors"], set())
        self.assertTrue(promotion_info["promotion_possible"])
        self.assertEqual(len(promotion_info["metadata_successors"][PROMOTION]), 2)
        self.assertTrue(
            all(
                split_state_key(next_key)[2]
                for next_key in promotion_info["metadata_successors"][PROMOTION]
            )
        )

    def test_pack_state32_round_trips_through_public_api(self):
        info = inspect_game_state(initial_position())
        state_key = info["state_key"]
        black32, white32, kings32, side = split_state_key(state_key)

        self.assertEqual(pack_state32(black32, white32, kings32, side), state_key)

    def test_quiet_tablebase_exposes_hash_maps_and_dataframes(self):
        tablebase = QuietTablebase().run(max_rounds=3)

        self.assertEqual(tablebase.summary()["total_states"], 262)
        self.assertEqual(tablebase.summary()["transitions"], 347)
        self.assertEqual(len(tablebase.transition_map(1, QUIET)), 1)

        round_three_captures = tablebase.transition_map(3, FORCED_CAPTURE)
        self.assertEqual(sum(len(targets) for targets in round_three_captures.values()), 11)

        metadata_df = tablebase.metadata_maps_df()
        states_df = tablebase.states_df()
        boundary_edges_df = tablebase.boundary_edges_df()

        self.assertIn("metadata", metadata_df.columns)
        self.assertIn("state_key", states_df.columns)
        self.assertIn("next_state_key", boundary_edges_df.columns)
        self.assertEqual(
            metadata_df["edges"].sum(),
            len(tablebase.transitions_df()) + len(boundary_edges_df),
        )


if __name__ == "__main__":
    unittest.main()
