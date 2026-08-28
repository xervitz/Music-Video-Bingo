import tempfile
import unittest
from pathlib import Path

from bingo_rules import (
    RuleSet,
    WinningPattern,
    blackout_rule_set,
    four_corners_rule_set,
    list_saved_patterns,
    list_saved_rule_sets,
    load_rule_set,
    load_saved_pattern,
    save_pattern_to_library,
    save_rule_set,
    save_rule_set_to_library,
    standard_rule_set,
)


class BingoRuleTests(unittest.TestCase):
    def test_presets_create_expected_patterns(self):
        standard = standard_rule_set(5)
        corners = four_corners_rule_set(5)
        blackout = blackout_rule_set(5)

        self.assertEqual(len(standard.patterns), 12)
        self.assertEqual(corners.patterns[0].cells, (0, 4, 20, 24))
        self.assertEqual(len(blackout.patterns[0].cells), 25)

    def test_custom_rule_set_round_trips_as_json(self):
        rules = RuleSet(
            "Postage stamp",
            5,
            (WinningPattern("Upper left square", (0, 1, 5, 6)),),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "rules.json"
            save_rule_set(rules, path)
            self.assertEqual(load_rule_set(path), rules)

    def test_rejects_a_pattern_containing_only_the_free_center(self):
        with self.assertRaisesRegex(ValueError, "free center"):
            RuleSet("Invalid", 5, (WinningPattern("Instant win", (12,)),))

    def test_pattern_and_set_libraries_are_separate_and_listable(self):
        pattern = WinningPattern("Upper left square", (0, 1, 5, 6))
        rule_set = RuleSet("Corner options", 5, (pattern,))
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = save_pattern_to_library(
                pattern, 5, library_root=temporary_directory
            )
            set_path = save_rule_set_to_library(
                rule_set, library_root=temporary_directory
            )

            self.assertEqual(load_saved_pattern(pattern_path), (5, pattern))
            self.assertEqual(list_saved_patterns(temporary_directory)[0][2], pattern)
            self.assertEqual(list_saved_rule_sets(temporary_directory)[0][1], rule_set)
            self.assertEqual(pattern_path.parent.name, "patterns")
            self.assertEqual(set_path.parent.name, "sets")

            with self.assertRaises(FileExistsError):
                save_pattern_to_library(pattern, 5, library_root=temporary_directory)


if __name__ == "__main__":
    unittest.main()
