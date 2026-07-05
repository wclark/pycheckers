import unittest

import matplotlib.pyplot as plt

from pycheckers import (
    MASK32,
    Board,
    Conditions,
    Effects,
    Rule,
    Ruleset,
    Turn,
    as_board,
    as_turn,
    is_playable_square,
    playable_squares,
    show_board,
    show_ruleset_rows,
    show_turn,
    square_coords32,
    square_from_mask32,
    square_index32,
    square_mask32,
)


class NativeApiTests(unittest.TestCase):
    def test_square_encoding_is_native_32_bit(self):
        self.assertEqual(len(playable_squares()), 32)
        self.assertTrue(is_playable_square(0, 1))
        self.assertFalse(is_playable_square(0, 0))
        self.assertEqual(square_index32(0, 1), 0)
        self.assertEqual(square_index32(7, 6), 31)
        self.assertEqual(square_coords32(0), (0, 1))
        self.assertEqual(square_coords32(31), (7, 6))
        self.assertEqual(square_from_mask32(square_mask32(3, 4)), (3, 4))
        with self.assertRaises(ValueError):
            square_index32(8, 1)
        with self.assertRaises(ValueError):
            square_coords32(32)
        with self.assertRaises(ValueError):
            square_from_mask32(0)
        with self.assertRaises(ValueError):
            square_from_mask32(3)
        with self.assertRaises(ValueError):
            square_from_mask32(1 << 32)

    def test_board_and_turn_are_hashable_native_records(self):
        board = Board.initial()
        turn = Turn.initial()
        metadata_turn = Turn(board, "white", {"round": 3, "kind": "demo"})

        self.assertEqual(board.as_tuple(), (0x00000FFF, 0xFFF00000, 0))
        self.assertEqual(board.key, board.as_tuple())
        self.assertEqual(board.maps, {"black": 0x00000FFF, "white": 0xFFF00000, "kings": 0})
        self.assertEqual(board.occupied, 0xFFF00FFF)
        self.assertEqual(board.empty, MASK32 ^ 0xFFF00FFF)
        self.assertEqual(turn.as_tuple(), (0x00000FFF, 0xFFF00000, 0, 1))
        self.assertEqual(turn.key, turn.as_tuple())
        self.assertEqual(turn.maps, turn.as_dict())
        self.assertEqual(turn.occupied, board.occupied)
        self.assertEqual(turn.empty, board.empty)
        self.assertEqual(turn.side, "black")
        self.assertEqual(metadata_turn.side, "white")
        self.assertEqual(dict(metadata_turn.metadata), {"kind": "demo", "round": 3})
        self.assertEqual(as_board(board.as_dict()), board)
        self.assertEqual(as_turn(turn.as_dict()), turn)
        self.assertEqual(Turn.from_tuple((*board.as_tuple(), 0)).side, "white")
        self.assertEqual(Turn.from_tuple((*board.as_tuple(), 1, {"x": 1})).metadata, (("x", 1),))

        with self.assertRaises(ValueError):
            Board(1, 1, 0)
        with self.assertRaises(ValueError):
            Board(1, 0, 2)
        with self.assertRaises(ValueError):
            Board(1 << 32, 0, 0)
        with self.assertRaises(ValueError):
            Board.from_tuple((1, 2))
        with self.assertRaises(ValueError):
            Turn.from_tuple((1, 2, 3))
        with self.assertRaises(ValueError):
            Turn(Board(0, 0, 0), "red")

    def test_ruleset_geometry_and_native_indexes(self):
        ruleset = Ruleset.american()
        dataframe = ruleset.to_dataframe()

        self.assertIs(ruleset, Ruleset.american())
        self.assertEqual(len(ruleset), 510)
        self.assertEqual(dataframe.shape, (510, 10))
        self.assertEqual(len(ruleset.records), 510)
        self.assertEqual(len(ruleset.record_map), 510)
        self.assertEqual(len(ruleset.rule_set), 510)
        self.assertEqual(len(ruleset.condition_tuples), 510)
        self.assertEqual(len(ruleset.effect_tuples), 510)
        self.assertEqual(len(ruleset.rules_by_side[1]), 255)
        self.assertEqual(len(ruleset.rules_by_side[0]), 255)
        self.assertEqual(dataframe["black_to_move"].sum(), 255)
        self.assertEqual(dataframe["king"].sum(), 340)
        self.assertEqual(dataframe["promotion"].sum(), 26)
        self.assertEqual(dataframe["capture"].sum(), 216)
        self.assertEqual(len(ruleset.indices_for(black_to_move=1, king=0, promotion=0, capture=0)), 42)
        self.assertEqual(len(ruleset.indices_for(capture=1)), 216)
        self.assertEqual(len(ruleset.indices_for(king=1, promotion=1)), 0)
        self.assertEqual(len(Ruleset.american("black")), 255)
        self.assertEqual(len(Ruleset.american("white")), 255)
        self.assertEqual(len(Ruleset.from_board_geometry(side=None)), 510)
        self.assertIs(next(iter(ruleset)), ruleset[0])

        first = ruleset.record(0)
        self.assertEqual(first["is_black"], square_mask32(0, 1))
        self.assertEqual(first["is_white"], 0)
        self.assertEqual(first["is_empty"], square_mask32(1, 0))
        self.assertEqual(first["be_black"], square_mask32(1, 0))
        self.assertEqual(first["black_to_move"], 1)
        self.assertEqual(first["king"], 0)
        self.assertEqual(first["promotion"], 0)
        self.assertEqual(first["capture"], 0)

        with self.assertRaises(IndexError):
            ruleset.record(-1)
        with self.assertRaises(IndexError):
            _ = ruleset[9999]
        with self.assertRaises(ValueError):
            Ruleset.american("red")

    def test_rule_conditions_effects_and_records(self):
        rule = Rule(
            Conditions(square_mask32(2, 1), 0, square_mask32(3, 0), 1, 0),
            Effects(square_mask32(3, 0), 0, square_mask32(2, 1), 0, 0),
        )
        turn = Turn.from_masks(square_mask32(2, 1), 0, 0, 1)
        next_turn = rule.apply(turn)

        self.assertTrue(rule.applies(turn))
        self.assertFalse(rule.applies(Turn.from_masks(square_mask32(2, 1), 0, square_mask32(2, 1), 1)))
        self.assertEqual(rule.conditions.as_tuple[0], square_mask32(2, 1))
        self.assertEqual(rule.effects.as_tuple[0], square_mask32(3, 0))
        self.assertEqual(rule.flags, 1)
        self.assertEqual(rule.move_record()["to_mask"], square_mask32(3, 0))
        self.assertEqual(next_turn.black, square_mask32(3, 0))
        self.assertEqual(next_turn.black_to_move, 0)

        copied = Rule.from_record(rule.as_dict)
        nested = Rule(rule.conditions.as_dict, rule.effects.as_dict)
        white_rule = Rule(
            Conditions(0, square_mask32(5, 0), square_mask32(4, 1), "W", 0),
            Effects(0, square_mask32(4, 1), square_mask32(5, 0), 0, 0),
        )
        self.assertEqual(copied.as_tuple, rule.as_tuple)
        self.assertEqual(nested.as_tuple, rule.as_tuple)
        self.assertEqual(white_rule.conditions.mover, square_mask32(5, 0))
        self.assertEqual(white_rule.mover_effect, square_mask32(4, 1))
        with self.assertRaises(ValueError):
            rule.apply(Turn.from_masks(0, 0, 0, 1))

    def test_initial_legal_moves_are_compact(self):
        ruleset = Ruleset.american()
        turn = Turn.initial()
        moves = ruleset.legal_moves(turn)
        successors = ruleset.successors(turn)
        successor_map = ruleset.successor_map(turn)

        self.assertEqual(len(moves), 7)
        self.assertEqual(len(successors), 7)
        self.assertEqual(len(successor_map), 7)
        self.assertTrue(all(move["from_mask"] <= MASK32 for move in moves))
        self.assertTrue(all(not move["capture"] for move in moves))
        self.assertEqual(ruleset.legal_rule_indices(turn), ruleset.matching_rule_indices(turn))
        self.assertEqual(len(ruleset.matching_rules(turn)), 7)
        self.assertEqual(len(ruleset.legal_rules(turn, from_mask=square_mask32(2, 1))), 2)

    def test_forced_capture_suppresses_quiet_moves(self):
        ruleset = Ruleset.american()
        turn = Turn.from_masks(square_mask32(2, 1), square_mask32(3, 2), 0, 1)
        moves = ruleset.legal_moves(turn)
        next_turn = ruleset.successors(turn)[0]

        self.assertEqual(len(moves), 1)
        self.assertTrue(moves[0]["capture"])
        self.assertTrue(ruleset.matching_rule_indices(turn, captures_only=True))
        self.assertEqual(moves[0]["from_mask"], square_mask32(2, 1))
        self.assertEqual(moves[0]["to_mask"], square_mask32(4, 3))
        self.assertEqual(moves[0]["captured_mask"], square_mask32(3, 2))
        self.assertEqual(next_turn.black, square_mask32(4, 3))
        self.assertEqual(next_turn.white, 0)
        self.assertEqual(next_turn.black_to_move, 0)

    def test_king_and_promotion_semantics(self):
        ruleset = Ruleset.american()
        king_turn = Turn.from_masks(square_mask32(2, 1), 0, square_mask32(2, 1), 1)
        promotion_turn = Turn.from_masks(square_mask32(6, 1), 0, 0, 1)

        king_moves = ruleset.legal_moves(king_turn)
        promotion_indexes = ruleset.legal_rule_indices(promotion_turn)
        promotion_successors = ruleset.successors(promotion_turn)

        self.assertEqual(len(king_moves), 4)
        self.assertTrue(any(move["dr"] < 0 for move in king_moves))
        self.assertEqual(len(promotion_indexes), 2)
        self.assertTrue(all(ruleset[index].effects.promotion for index in promotion_indexes))
        self.assertTrue(all(successor.kings & successor.black for successor in promotion_successors))
        self.assertTrue(any(ruleset[index].flags & 0b1111 for index in promotion_indexes))

    def test_ruleset_record_inputs_and_selection(self):
        ruleset = Ruleset.american()
        dataframe_ruleset = Ruleset.from_records(ruleset.to_dataframe().iloc[:2])
        rule_ruleset = Ruleset.from_records(ruleset[0])
        dict_ruleset = Ruleset.from_records(ruleset.record(0))
        copied_ruleset = Ruleset.from_records(dataframe_ruleset)

        self.assertEqual(len(dataframe_ruleset), 2)
        self.assertEqual(len(rule_ruleset), 1)
        self.assertEqual(len(dict_ruleset), 1)
        self.assertEqual(len(copied_ruleset), 2)
        self.assertEqual(len(Ruleset.from_records(ruleset.to_dataframe().iloc[0])), 1)
        self.assertEqual(len(ruleset.select_records(None)), 510)
        self.assertEqual(ruleset.select_records(0)[0]["rule_index"], 0)
        self.assertEqual(len(ruleset.select_records(slice(0, 2))), 2)
        self.assertEqual(ruleset.select_records([0, 1])[0]["rule_index"], 0)
        self.assertEqual(ruleset.select_records([ruleset[0]])[0]["is_black"], ruleset.record(0)["is_black"])
        self.assertEqual(as_board(Board.initial()), Board.initial())
        self.assertEqual(as_board(Board.initial().as_tuple()), Board.initial())
        self.assertEqual(as_turn(Turn.initial()), Turn.initial())

    def test_display_helpers_return_figures(self):
        ruleset = Ruleset.american()
        promotion_index = ruleset.indices_for(promotion=1)[0]
        board_fig, _board_ax = show_board(Board.initial(), size=1, show=False)
        turn_fig, _turn_ax = show_turn(Turn.initial(), size=1, show=False)
        indexed_rule_rows = ruleset.plot(rules=[0], size=1, show=False)
        promotion_rule_rows = ruleset.plot(rules=[promotion_index], size=1, show=False)
        dataframe_rule_rows = show_ruleset_rows(ruleset, rules=ruleset.to_dataframe().iloc[:1], size=1, show=False)
        direct_rule_rows = show_ruleset_rows([ruleset[0]], size=1, title="direct", show=False)

        self.assertIsNotNone(board_fig)
        self.assertIsNotNone(turn_fig)
        self.assertEqual(len(indexed_rule_rows), 1)
        self.assertEqual(len(promotion_rule_rows), 1)
        self.assertEqual(len(dataframe_rule_rows), 1)
        self.assertEqual(len(direct_rule_rows), 1)
        self.assertEqual(indexed_rule_rows[0][1].shape, (3,))
        self.assertIn("capture:", indexed_rule_rows[0][1][2].texts[0].get_text())
        with self.assertRaises(ValueError):
            show_ruleset_rows(ruleset, rules=[], show=False)

        plt.close(board_fig)
        plt.close(turn_fig)
        for fig, _axes in [*indexed_rule_rows, *promotion_rule_rows, *dataframe_rule_rows, *direct_rule_rows]:
            plt.close(fig)


if __name__ == "__main__":
    unittest.main()
