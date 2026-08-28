"""Reusable winning-pattern definitions for bingo boards."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


RULE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class WinningPattern:
    """One named set of board cells that produces a win."""

    name: str
    cells: tuple[int, ...]


@dataclass(frozen=True)
class RuleSet:
    """All accepted winning patterns for one square board size."""

    name: str
    width: int
    patterns: tuple[WinningPattern, ...]

    def __post_init__(self) -> None:
        _validate_rule_set(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RULE_SCHEMA_VERSION,
            "type": "winning_set",
            "name": self.name,
            "board_size": self.width,
            "patterns": [
                {"name": pattern.name, "cells": list(pattern.cells)}
                for pattern in self.patterns
            ],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RuleSet":
        if value.get("schema_version", RULE_SCHEMA_VERSION) != RULE_SCHEMA_VERSION:
            raise ValueError("unsupported winning-rule schema version")
        patterns = value.get("patterns")
        if not isinstance(patterns, list):
            raise ValueError("winning rules must contain a patterns list")
        converted = []
        for pattern in patterns:
            if not isinstance(pattern, dict):
                raise ValueError("each winning pattern must be an object")
            cells = pattern.get("cells")
            if not isinstance(cells, list) or any(
                not isinstance(cell, int) for cell in cells
            ):
                raise ValueError("winning pattern cells must be integers")
            converted.append(
                WinningPattern(name=str(pattern.get("name", "")), cells=tuple(cells))
            )
        return cls(
            name=str(value.get("name", "")),
            width=value.get("board_size"),
            patterns=tuple(converted),
        )


def standard_rule_set(width: int) -> RuleSet:
    """Return rows, columns, and the two diagonals."""

    patterns = []
    for row in range(width):
        patterns.append(
            WinningPattern(
                f"Row {row + 1}",
                tuple(row * width + column for column in range(width)),
            )
        )
    for column in range(width):
        patterns.append(
            WinningPattern(
                f"Column {column + 1}",
                tuple(row * width + column for row in range(width)),
            )
        )
    patterns.extend(
        [
            WinningPattern(
                "Diagonal down", tuple(index * width + index for index in range(width))
            ),
            WinningPattern(
                "Diagonal up",
                tuple(index * width + width - index - 1 for index in range(width)),
            ),
        ]
    )
    return RuleSet("Standard lines", width, tuple(patterns))


def four_corners_rule_set(width: int) -> RuleSet:
    """Return one pattern containing the four outer corner cells."""

    return RuleSet(
        "Four corners",
        width,
        (
            WinningPattern(
                "Four corners",
                (0, width - 1, width * (width - 1), width * width - 1),
            ),
        ),
    )


def blackout_rule_set(width: int) -> RuleSet:
    """Return one pattern requiring every cell, including the free center."""

    return RuleSet(
        "Blackout",
        width,
        (WinningPattern("Blackout", tuple(range(width * width))),),
    )


def save_rule_set(rule_set: RuleSet, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(rule_set.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    return destination.resolve()


def save_pattern_to_library(
    pattern: WinningPattern,
    width: int,
    *,
    library_root: str | Path = "bingo_rules",
    overwrite: bool = False,
) -> Path:
    """Save one reusable winning pattern in the pattern library."""

    RuleSet("Pattern validation", width, (pattern,))
    destination = Path(library_root) / "patterns" / f"{safe_rule_name(pattern.name)}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.write_text(
        json.dumps(
            {
                "schema_version": RULE_SCHEMA_VERSION,
                "type": "winning_pattern",
                "name": pattern.name,
                "board_size": width,
                "cells": list(pattern.cells),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination.resolve()


def load_saved_pattern(path: str | Path) -> tuple[int, WinningPattern]:
    source = Path(path)
    value = _read_json(source, "winning-pattern")
    if value.get("schema_version", RULE_SCHEMA_VERSION) != RULE_SCHEMA_VERSION:
        raise ValueError("unsupported winning-pattern schema version")
    if value.get("type") not in (None, "winning_pattern"):
        raise ValueError("file does not contain a winning pattern")
    width = value.get("board_size")
    cells = value.get("cells")
    if not isinstance(cells, list) or any(not isinstance(cell, int) for cell in cells):
        raise ValueError("winning pattern cells must be integers")
    pattern = WinningPattern(str(value.get("name", "")), tuple(cells))
    RuleSet("Pattern validation", width, (pattern,))
    return width, pattern


def save_rule_set_to_library(
    rule_set: RuleSet,
    *,
    library_root: str | Path = "bingo_rules",
    overwrite: bool = False,
) -> Path:
    destination = Path(library_root) / "sets" / f"{safe_rule_name(rule_set.name)}.json"
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    return save_rule_set(rule_set, destination)


def list_saved_patterns(
    library_root: str | Path = "bingo_rules",
) -> list[tuple[Path, int, WinningPattern]]:
    entries = []
    for path in sorted((Path(library_root) / "patterns").glob("*.json")):
        width, pattern = load_saved_pattern(path)
        entries.append((path.resolve(), width, pattern))
    return entries


def list_saved_rule_sets(
    library_root: str | Path = "bingo_rules",
) -> list[tuple[Path, RuleSet]]:
    entries = []
    for path in sorted((Path(library_root) / "sets").glob("*.json")):
        entries.append((path.resolve(), load_rule_set(path)))
    return entries


def safe_rule_name(name: str) -> str:
    cleaned = "-".join(name.lower().split())
    return (
        "".join(
            character
            for character in cleaned
            if character.isalnum() or character == "-"
        )
        or "rules"
    )


def load_rule_set(path: str | Path) -> RuleSet:
    source = Path(path)
    value = _read_json(source, "winning-rule")
    if value.get("type") not in (None, "winning_set"):
        raise ValueError("file does not contain a winning set")
    return RuleSet.from_dict(value)


def _read_json(source: Path, description: str) -> dict[str, Any]:
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"{description} file does not exist: {source}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid {description} JSON: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{description} file must contain a JSON object")
    return value


def rule_set_from_config(config: dict[str, Any]) -> RuleSet:
    """Read custom rules, falling back for board folders from the old schema."""

    configured = config.get("winning_rules")
    if isinstance(configured, dict):
        return RuleSet.from_dict(configured)
    width = config.get("board_size")
    if not isinstance(width, int):
        raise ValueError("board config is missing a valid board_size")
    return standard_rule_set(width)


def _validate_rule_set(rule_set: RuleSet) -> None:
    if not isinstance(rule_set.width, int) or rule_set.width < 3 or rule_set.width % 2 == 0:
        raise ValueError("rule-set board size must be an odd integer of at least 3")
    if not rule_set.name.strip():
        raise ValueError("rule set must have a name")
    if not rule_set.patterns:
        raise ValueError("rule set must contain at least one winning pattern")

    maximum_cell = rule_set.width * rule_set.width
    center = maximum_cell // 2
    seen_patterns = set()
    seen_names = set()
    for pattern in rule_set.patterns:
        name = pattern.name.strip()
        if not name:
            raise ValueError("every winning pattern must have a name")
        if name.casefold() in seen_names:
            raise ValueError(f"duplicate winning-pattern name: {name}")
        seen_names.add(name.casefold())
        if not pattern.cells:
            raise ValueError(f"winning pattern '{name}' has no selected cells")
        if len(set(pattern.cells)) != len(pattern.cells):
            raise ValueError(f"winning pattern '{name}' contains duplicate cells")
        if any(not 0 <= cell < maximum_cell for cell in pattern.cells):
            raise ValueError(f"winning pattern '{name}' contains an invalid cell")
        if all(cell == center for cell in pattern.cells):
            raise ValueError(f"winning pattern '{name}' cannot be only the free center")
        signature = frozenset(pattern.cells)
        if signature in seen_patterns:
            raise ValueError(f"winning pattern '{name}' duplicates another pattern")
        seen_patterns.add(signature)
