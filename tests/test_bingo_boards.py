import unittest

from bingo_boards import (
    analyze_bingo_boards,
    generate_and_save_numbered_board_set,
    generate_bingo_boards,
)
from board_storage import load_board_set
from bingo_rules import four_corners_rule_set


class GenerateBingoBoardsTests(unittest.TestCase):
    def test_generates_square_boards_with_unique_items_and_free_center(self):
        items = [f"item-{index}" for index in range(40)]
        boards = generate_bingo_boards(
            items,
            board_count=6,
            width=5,
            seed=7,
            simulation_trials=30,
            optimization_rounds=20,
        )

        self.assertEqual(len(boards), 6)
        for board in boards:
            self.assertEqual([len(row) for row in board], [5] * 5)
            self.assertIsNone(board[2][2])
            playable = [cell for row in board for cell in row if cell is not None]
            self.assertEqual(len(playable), 24)
            self.assertEqual(len(set(playable)), 24)
            self.assertTrue(set(playable) <= set(items))

    def test_seed_is_reproducible(self):
        options = dict(
            board_count=4,
            width=3,
            seed=123,
            candidate_count=12,
            simulation_trials=20,
            optimization_rounds=10,
        )
        first = generate_bingo_boards(list(range(15)), **options)
        second = generate_bingo_boards(list(range(15)), **options)
        self.assertEqual(first, second)

    def test_rejects_invalid_inputs(self):
        with self.assertRaisesRegex(ValueError, "odd"):
            generate_bingo_boards(list(range(20)), 2, 4)
        with self.assertRaisesRegex(ValueError, "unique"):
            generate_bingo_boards([0, 1, 1, 2, 3, 4, 5, 6, 7], 2, 3)
        with self.assertRaisesRegex(ValueError, "not enough"):
            generate_bingo_boards(list(range(7)), 2, 3)
        with self.assertRaisesRegex(ValueError, "reserved"):
            generate_bingo_boards([None, *range(8)], 2, 3)

    def test_metrics_identify_identical_boards_and_guaranteed_ties(self):
        board = (
            (1, 2, 3),
            (4, None, 5),
            (6, 7, 8),
        )
        metrics = analyze_bingo_boards(
            [board, board], simulation_trials=20, seed=1
        )

        self.assertEqual(metrics.duplicate_board_pairs, 1)
        self.assertEqual(metrics.estimated_tie_rate, 1.0)
        self.assertEqual(metrics.average_winners_per_game, 2.0)
        self.assertEqual(metrics.minimum_board_distance, 0.0)
        self.assertEqual(metrics.closest_board_pair, (1, 2))

    def test_generator_accepts_a_rule_set(self):
        rules = four_corners_rule_set(3)
        boards = generate_bingo_boards(
            list(range(15)),
            board_count=3,
            width=3,
            seed=4,
            rule_set=rules,
            candidate_count=8,
            simulation_trials=10,
            optimization_rounds=5,
        )

        self.assertEqual(len(boards), 3)
        with self.assertRaisesRegex(ValueError, "rule set is for"):
            generate_bingo_boards(list(range(24)), 2, 5, rule_set=rules)
        with self.assertRaisesRegex(ValueError, "not both"):
            generate_bingo_boards(
                list(range(15)),
                2,
                3,
                rule_set=rules,
                winning_patterns=[(0, 2, 6, 8)],
            )

    def test_generate_and_save_helper_embeds_selected_rule_set(self):
        import tempfile

        rules = four_corners_rule_set(3)
        with tempfile.TemporaryDirectory() as temporary_directory:
            generated = generate_and_save_numbered_board_set(
                15,
                3,
                3,
                rule_set=rules,
                seed=99,
                output_root=temporary_directory,
                candidate_count=8,
                simulation_trials=10,
                optimization_rounds=5,
            )
            config, saved_boards = load_board_set(generated.folder)

            self.assertEqual(generated.seed, 99)
            self.assertEqual(generated.rule_set, rules)
            self.assertEqual(saved_boards, generated.boards)
            self.assertEqual(config["winning_rules"], rules.to_dict())


if __name__ == "__main__":
    unittest.main()
