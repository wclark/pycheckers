import unittest

from pycheckers import (
    BLACK_PROMO_MASK,
    DARKS_MASK,
    WHITE_PROMO_MASK,
    apply_move,
    apply_turn,
    bitboards_from_ascii,
    bits_from_grid,
    capture_chains,
    generate_move_templates,
    grid_from_bits,
    initial_position,
    legal_moves,
    legal_turns,
    square_mask,
    validate_position,
)
from pycheckers.bitboard import (
    expand_quiet_man_states,
    explore_quiet_man_positions,
    is_quiet_man_state,
)
from pycheckers.quiet import (
    FORCED_CAPTURE,
    FORCED_CAPTURE_PROMOTION,
    PROMOTION,
    QUIET,
    QuietPositionGraph,
    decode_state_key,
    encode_state,
    inspect_game_state,
    mask32_to64,
    mask64_to32,
    pack_state32,
    run_quiet_graph,
    square32_to64,
    square64_to32,
    split_state_key,
)


class CheckersBitboardTests(unittest.TestCase):
    def test_initial_position(self):
        black, white, kings, side = initial_position()

        self.assertEqual(black, 0x0000000000AA55AA)
        self.assertEqual(white, 0x55AA550000000000)
        self.assertEqual(kings, 0)
        self.assertEqual(side, "B")
        self.assertEqual(black, 11163050)
        self.assertEqual(white, 6172839697753047040)
        self.assertTrue(validate_position(black, white, kings))
        self.assertEqual(BLACK_PROMO_MASK, 0x5500000000000000)
        self.assertEqual(WHITE_PROMO_MASK, 0x00000000000000AA)

    def test_move_template_generation(self):
        moves = generate_move_templates()
        keys = {(m["from_mask"], m["to_mask"], m["captured_mask"]) for m in moves}

        self.assertEqual(len(moves), 170)
        self.assertEqual(sum(not m["is_capture"] for m in moves), 98)
        self.assertEqual(sum(m["is_capture"] for m in moves), 72)
        self.assertEqual(len(keys), 170)

        example = [
            m
            for m in moves
            if m["from_mask"] == 2 and m["to_mask"] == 256
        ]
        self.assertEqual(len(example), 1)
        self.assertEqual(example[0]["dr"], 1)
        self.assertEqual(example[0]["dc"], -1)

    def test_initial_legal_moves(self):
        black, white, kings, side = initial_position()
        moves = legal_moves(black, white, kings, side)

        self.assertEqual(len(moves), 7)
        self.assertTrue(all(not m["is_capture"] for m in moves))

    def test_apply_opening_move_preserves_invariants(self):
        black, white, kings, side = initial_position()
        move = legal_moves(black, white, kings, side)[0]
        new_black, new_white, new_kings, new_side = apply_move(
            black,
            white,
            kings,
            side,
            move,
        )

        self.assertEqual(new_side, "W")
        self.assertEqual(new_black & new_white, 0)
        self.assertEqual(new_kings & ~(new_black | new_white), 0)
        self.assertEqual((new_black | new_white) & ~DARKS_MASK, 0)

    def test_mandatory_capture(self):
        black = square_mask(2, 1)
        white = square_mask(3, 2)
        kings = 0

        moves = legal_moves(black, white, kings, "B")

        self.assertEqual(len(moves), 1)
        self.assertTrue(moves[0]["is_capture"])
        self.assertEqual(moves[0]["from_mask"], square_mask(2, 1))
        self.assertEqual(moves[0]["to_mask"], square_mask(4, 3))
        self.assertEqual(moves[0]["captured_mask"], square_mask(3, 2))

    def test_backward_move_requires_king(self):
        black = square_mask(3, 2)
        white = 0

        man_moves = legal_moves(black, white, 0, "B")
        self.assertFalse(any(m["dr"] < 0 for m in man_moves))

        king_moves = legal_moves(black, white, black, "B")
        self.assertTrue(any(m["dr"] < 0 for m in king_moves))

    def test_captured_king_bit_is_cleared(self):
        black = square_mask(2, 1)
        white = square_mask(3, 2)
        kings = white
        move = legal_moves(black, white, kings, "B")[0]

        new_black, new_white, new_kings, new_side = apply_move(
            black,
            white,
            kings,
            "B",
            move,
        )

        self.assertEqual(new_black, square_mask(4, 3))
        self.assertEqual(new_white, 0)
        self.assertEqual(new_kings, 0)
        self.assertEqual(new_side, "W")

    def test_grid_helpers(self):
        grid = """
        01010101
        10101010
        01010101
        00000000
        00000000
        00000000
        00000000
        00000000
        """

        mask = bits_from_grid(grid)
        self.assertEqual(mask, 0x0000000000AA55AA)
        self.assertEqual(grid_from_bits(mask).splitlines()[0], "01010101")

    def test_ascii_board_helper(self):
        black, white, kings = bitboards_from_ascii(
            """
            .b.b.b.b
            b.b.b.b.
            .B.b.b.b
            ........
            ........
            w.w.w.w.
            .w.w.w.w
            W.w.w.w.
            """
        )

        self.assertTrue(black & square_mask(2, 1))
        self.assertTrue(white & square_mask(7, 0))
        self.assertEqual(kings, square_mask(2, 1) | square_mask(7, 0))

    def test_multi_jump_turn(self):
        black = square_mask(2, 1)
        white = square_mask(3, 2) | square_mask(5, 4)
        kings = 0

        turns = legal_turns(black, white, kings, "B")
        self.assertEqual(len(turns), 1)
        self.assertEqual(len(turns[0]), 2)

        new_black, new_white, new_kings, new_side = apply_turn(
            black,
            white,
            kings,
            "B",
            turns[0],
        )
        self.assertEqual(new_black, square_mask(6, 5))
        self.assertEqual(new_white, 0)
        self.assertEqual(new_kings, 0)
        self.assertEqual(new_side, "W")

    def test_promoting_man_stops_capture_chain(self):
        black = square_mask(5, 0)
        white = square_mask(6, 1) | square_mask(6, 3)
        kings = 0

        chains = capture_chains(black, white, kings, "B")
        self.assertEqual(len(chains), 1)
        self.assertEqual(len(chains[0]), 1)

        new_black, new_white, new_kings, new_side = apply_turn(
            black,
            white,
            kings,
            "B",
            chains[0],
        )
        self.assertEqual(new_black, square_mask(7, 2))
        self.assertEqual(new_white, square_mask(6, 3))
        self.assertEqual(new_kings, square_mask(7, 2))
        self.assertEqual(new_side, "W")

    def test_quiet_state_expansion_from_start(self):
        start = initial_position()
        states = {start}
        expanded = set()
        boundary_states = {}
        transitions = set()
        parents = {start: None}
        predecessors = {start: []}

        result = expand_quiet_man_states(
            states,
            frontier={start},
            expanded=expanded,
            boundary_states=boundary_states,
            transitions=transitions,
            parents=parents,
            predecessors=predecessors,
        )

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["new_states"], 7)
        self.assertEqual(result["total_states"], 8)
        self.assertEqual(result["new_transitions"], 7)
        self.assertEqual(result["total_transitions"], 7)
        self.assertEqual(len(parents), 8)
        self.assertEqual(len(predecessors), 8)
        self.assertEqual(result["boundary_moves"], 0)
        self.assertEqual(result["boundary_source_states"], 0)
        self.assertEqual(result["terminal_source_states"], 0)
        self.assertEqual(result["duplicate_states"], 0)
        self.assertEqual(len(result["next_frontier"]), 7)
        self.assertTrue(all(is_quiet_man_state(state) for state in states))

        child = next(iter(result["next_frontier"]))
        parent, move = parents[child]
        self.assertEqual(parent, start)
        self.assertFalse(move["is_capture"])

        repeated = expand_quiet_man_states(
            states,
            frontier={start},
            expanded=expanded,
            boundary_states=boundary_states,
            transitions=transitions,
            parents=parents,
            predecessors=predecessors,
        )
        self.assertEqual(repeated["processed"], 0)
        self.assertEqual(repeated["skipped_expanded"], 1)
        self.assertEqual(repeated["new_states"], 0)
        self.assertEqual(repeated["new_transitions"], 0)

        second = expand_quiet_man_states(
            states,
            frontier=result["next_frontier"],
            expanded=expanded,
            boundary_states=boundary_states,
            transitions=transitions,
            parents=parents,
            predecessors=predecessors,
        )
        self.assertEqual(second["processed"], 7)
        self.assertEqual(second["new_states"], 49)
        self.assertEqual(second["new_transitions"], 49)
        self.assertEqual(second["total_transitions"], 56)
        self.assertEqual(len(parents), len(states))
        self.assertEqual(len(predecessors), len(states))

        third = expand_quiet_man_states(
            states,
            frontier=second["next_frontier"],
            expanded=expanded,
            boundary_states=boundary_states,
            transitions=transitions,
            parents=parents,
            predecessors=predecessors,
        )
        self.assertEqual(third["processed"], 49)
        self.assertEqual(third["new_states"], 205)
        self.assertGreater(third["new_transitions"], third["new_states"])
        self.assertTrue(any(len(links) > 1 for links in predecessors.values()))

    def test_quiet_expansion_notes_capture_boundary(self):
        state = (square_mask(2, 1), square_mask(3, 2), 0, "B")
        states = {state}
        boundary_states = {}
        boundary_edges = []

        result = expand_quiet_man_states(
            states,
            frontier={state},
            expanded=set(),
            boundary_states=boundary_states,
            boundary_edges=boundary_edges,
            pieces_per_side=1,
        )

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["new_states"], 0)
        self.assertEqual(result["quiet_moves"], 0)
        self.assertEqual(result["new_transitions"], 0)
        self.assertEqual(result["boundary_moves"], 1)
        self.assertEqual(result["boundary_source_states"], 1)
        self.assertEqual(result["capture_moves"], 1)
        self.assertEqual(result["promotion_moves"], 0)
        self.assertEqual(boundary_states[state]["capture"], 1)
        self.assertEqual(boundary_states[state]["moves"], 1)
        self.assertEqual(boundary_edges[0][2], "capture")

    def test_quiet_expansion_notes_promotion_boundary(self):
        state = (square_mask(6, 1), square_mask(0, 1), 0, "B")
        states = {state}
        boundary_states = {}

        result = expand_quiet_man_states(
            states,
            frontier={state},
            expanded=set(),
            boundary_states=boundary_states,
            pieces_per_side=1,
        )

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["new_states"], 0)
        self.assertEqual(result["boundary_moves"], 2)
        self.assertEqual(result["boundary_source_states"], 1)
        self.assertEqual(result["capture_moves"], 0)
        self.assertEqual(result["promotion_moves"], 2)
        self.assertEqual(boundary_states[state]["promotion"], 2)
        self.assertEqual(boundary_states[state]["moves"], 2)

    def test_quiet_expansion_notes_terminal_state(self):
        state = (square_mask(7, 0), square_mask(0, 1), 0, "B")
        states = {state}
        terminal_states = set()

        result = expand_quiet_man_states(
            states,
            frontier={state},
            expanded=set(),
            terminal_states=terminal_states,
            pieces_per_side=1,
        )

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["new_states"], 0)
        self.assertEqual(result["terminal_source_states"], 1)
        self.assertEqual(result["terminal_states"], 1)
        self.assertEqual(terminal_states, {state})

    def test_quiet_explore_helper_respects_layer_limit(self):
        result = explore_quiet_man_positions(max_layers=1)

        self.assertEqual(len(result["states"]), 8)
        self.assertEqual(len(result["expanded"]), 1)
        self.assertEqual(len(result["frontier"]), 7)
        self.assertEqual(result["layers"][0]["new_states"], 7)

    def test_compact_state_encoding_round_trips(self):
        state = initial_position()
        state_key = encode_state(state)
        black32, white32, kings32, side = split_state_key(state_key)

        self.assertIsInstance(state_key, int)
        self.assertEqual(decode_state_key(state_key), state)
        self.assertEqual(pack_state32(black32, white32, kings32, side), state_key)
        self.assertEqual(mask32_to64(mask64_to32(state[0])), state[0])
        self.assertEqual(mask32_to64(mask64_to32(state[1])), state[1])
        self.assertEqual(square32_to64(square64_to32(square_mask(2, 1))), square_mask(2, 1))

    def test_inspect_game_state_reports_quiet_boundary_and_terminal(self):
        initial_info = inspect_game_state(initial_position())
        self.assertFalse(initial_info["forced_capture"])
        self.assertFalse(initial_info["promotion_possible"])
        self.assertFalse(initial_info["terminal"])
        self.assertEqual(len(initial_info["quiet_successors"]), 7)
        self.assertEqual(len(initial_info["metadata_successors"][QUIET]), 7)

        capture_state = (
            square_mask(2, 1),
            square_mask(3, 2),
            0,
            "B",
        )
        capture_info = inspect_game_state(capture_state, pieces_per_side=1)
        self.assertTrue(capture_info["forced_capture"])
        self.assertEqual(capture_info["quiet_successors"], set())
        self.assertEqual(len(capture_info["metadata_successors"][FORCED_CAPTURE]), 1)

        promotion_state = (
            square_mask(6, 1),
            square_mask(0, 1),
            0,
            "B",
        )
        promotion_info = inspect_game_state(promotion_state, pieces_per_side=1)
        self.assertFalse(promotion_info["forced_capture"])
        self.assertTrue(promotion_info["promotion_possible"])
        self.assertEqual(promotion_info["quiet_successors"], set())
        self.assertEqual(len(promotion_info["metadata_successors"][PROMOTION]), 2)
        self.assertTrue(
            all(split_state_key(next_key)[2] for next_key in promotion_info["metadata_successors"][PROMOTION])
        )

        terminal_state = (
            square_mask(7, 0),
            square_mask(0, 1),
            0,
            "B",
        )
        terminal_info = inspect_game_state(terminal_state, pieces_per_side=1)
        self.assertTrue(terminal_info["terminal"])
        self.assertIsNone(terminal_info["quiet_successors"])
        self.assertFalse(any(terminal_info["metadata_successors"].values()))

    def test_quiet_position_graph_transition_dataframe_indexes(self):
        graph = run_quiet_graph(max_rounds=3)

        states_df = graph.states_df()
        transitions_df = graph.transitions_df()
        predecessor_zero_df = graph.transitions_df(predecessor_index=0)
        boundary_edges_df = graph.boundary_edges_df()
        rounds_df = graph.rounds_df()

        self.assertIsInstance(graph, QuietPositionGraph)
        self.assertEqual(len(states_df), 262)
        self.assertEqual(len(transitions_df), 347)
        self.assertEqual(len(predecessor_zero_df), 7)
        self.assertIn("state_index", states_df.columns)
        self.assertIn("state_key", states_df.columns)
        self.assertIn("black32", states_df.columns)
        self.assertIn("white32", states_df.columns)
        self.assertIn("kings32", states_df.columns)
        self.assertNotIn("row_index", states_df.columns)
        self.assertNotIn("black", states_df.columns)
        self.assertNotIn("black_count", states_df.columns)
        self.assertNotIn("black_hex", states_df.columns)
        self.assertIn("from_square", transitions_df.columns)
        self.assertIn("to_square", transitions_df.columns)
        self.assertNotIn("from_mask", transitions_df.columns)
        self.assertIn("metadata", boundary_edges_df.columns)
        self.assertIn("next_state_key", boundary_edges_df.columns)
        self.assertTrue((predecessor_zero_df["predecessor_index"] == 0).all())
        self.assertEqual(len(boundary_edges_df), 11)
        self.assertEqual(len(graph.transition_map(1, QUIET)), 1)
        self.assertEqual(
            graph.metadata_maps_df()["edges"].sum(),
            len(transitions_df) + len(boundary_edges_df),
        )
        self.assertEqual(rounds_df["duplicate_transitions"].sum(), 0)
        self.assertEqual(
            rounds_df["duplicate_states"].sum(),
            rounds_df["existing_state_targets"].sum(),
        )
        self.assertEqual(
            rounds_df["duplicate_states"].sum(),
            rounds_df["same_round_state_collisions"].sum(),
        )
        self.assertEqual(rounds_df["prior_generation_state_hits"].sum(), 0)
        self.assertEqual(
            rounds_df["duplicate_states"].sum(),
            rounds_df["new_edges_to_existing_states"].sum(),
        )

        transition_pairs = set(
            zip(
                transitions_df["predecessor_index"],
                transitions_df["next_index"],
            )
        )
        self.assertEqual(len(transition_pairs), len(transitions_df))

        shared_next_index = int(
            transitions_df["next_index"].value_counts().loc[
                lambda counts: counts > 1
            ].index[0]
        )
        predecessors_df = graph.predecessors_df(shared_next_index)
        self.assertGreater(len(predecessors_df), 1)
        self.assertTrue((predecessors_df["next_index"] == shared_next_index).all())

        least_df = graph.least_path_count_states_df(limit=10)
        self.assertIn("state_index", least_df.columns)
        self.assertIn("state_key", least_df.columns)
        self.assertIn("black32", least_df.columns)
        self.assertNotIn("rank", least_df.columns)
        self.assertEqual(least_df.iloc[0]["path_count"], 1)

        boundary_df = graph.boundary_states_df()
        self.assertIn("forced_capture", boundary_df.columns)
        self.assertIn("promotion", boundary_df.columns)
        self.assertIn("forced_capture_promotion", boundary_df.columns)


if __name__ == "__main__":
    unittest.main()
