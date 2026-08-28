import tempfile
import unittest
from pathlib import Path

from board_printing import generate_board_pdfs
from board_storage import save_board_set


class BoardPrintingTests(unittest.TestCase):
    def test_creates_individual_and_combined_pdfs(self):
        board = (
            (0, 1, 2),
            (3, None, 4),
            (5, 6, 7),
        )
        config = {
            "entry_count": 10,
            "entry_range": {"start": 0, "stop_exclusive": 10},
            "board_size": 3,
            "board_count": 2,
            "free_space": {"row": 1, "column": 1, "stored_value": None},
            "winning_patterns": ["rows", "columns", "two_diagonals"],
            "generator": {"seed": 123},
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            board_folder = save_board_set(
                [board, board], config, output_root=root / "sets"
            )
            paths = generate_board_pdfs(
                board_folder, output_directory=root / "pdfs"
            )

            self.assertEqual([path.name for path in paths], [
                "board-001.pdf",
                "board-002.pdf",
                "all-boards.pdf",
            ])
            for path in paths:
                self.assertTrue(path.is_file())
                self.assertEqual(path.read_bytes()[:5], b"%PDF-")


if __name__ == "__main__":
    unittest.main()
