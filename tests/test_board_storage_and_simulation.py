import tempfile
import unittest
from pathlib import Path

from board_storage import load_board_set, save_board_set
from board_testing import simulate_board_folder


class BoardStorageAndSimulationTests(unittest.TestCase):
    def setUp(self):
        self.board = (
            (0, 1, 2),
            (3, None, 4),
            (5, 6, 7),
        )
        self.config = {
            "entry_count": 10,
            "entry_range": {"start": 0, "stop_exclusive": 10},
            "board_size": 3,
            "board_count": 2,
            "free_space": {"row": 1, "column": 1, "stored_value": None},
            "winning_patterns": ["rows", "columns", "two_diagonals"],
            "generator": {"seed": 123},
        }

    def test_saved_board_set_round_trips(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            folder = save_board_set(
                [self.board, self.board],
                self.config,
                output_root=temporary_directory,
            )
            loaded_config, loaded_boards = load_board_set(folder)

            self.assertEqual(loaded_config["generator"]["seed"], 123)
            self.assertEqual(loaded_boards, [self.board, self.board])
            self.assertTrue((Path(folder) / "config.json").is_file())
            self.assertTrue((Path(folder) / "boards.json").is_file())

    def test_identical_boards_split_every_simulated_win(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            folder = save_board_set(
                [self.board, self.board],
                self.config,
                output_root=temporary_directory,
            )
            report = simulate_board_folder(folder, 50, seed=9)

            self.assertEqual(report.seed, 9)
            self.assertEqual(report.tie_games, 50)
            self.assertEqual(report.tie_rate, 1.0)
            for board in report.boards:
                self.assertEqual(board.sole_wins, 0)
                self.assertEqual(board.tied_wins, 50)
                self.assertEqual(board.credited_wins, 25.0)
                self.assertEqual(board.credited_win_rate, 0.5)


if __name__ == "__main__":
    unittest.main()
