"""Read and write self-describing bingo board-set folders."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def save_board_set(
    boards: list[tuple[tuple[int | None, ...], ...]],
    config: dict[str, Any],
    *,
    output_root: str | Path = "board_sets",
) -> Path:
    """Save boards and their complete generation configuration."""

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc)
    seed = config.get("generator", {}).get("seed", "unknown")
    base_name = (
        f"entries-{config['entry_count']}_size-{config['board_size']}_"
        f"boards-{config['board_count']}_seed-{seed}_"
        f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}"
    )
    folder = root / base_name
    suffix = 2
    while folder.exists():
        folder = root / f"{base_name}-{suffix}"
        suffix += 1
    folder.mkdir()

    stored_config = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": timestamp.isoformat(),
        **config,
    }
    board_data = {
        "schema_version": SCHEMA_VERSION,
        "boards": [
            {
                "id": board_number,
                "cells": [list(row) for row in board],
            }
            for board_number, board in enumerate(boards, start=1)
        ],
    }
    _write_json(folder / "config.json", stored_config)
    _write_json(folder / "boards.json", board_data)
    return folder.resolve()


def load_board_set(
    folder: str | Path,
) -> tuple[dict[str, Any], list[tuple[tuple[int | None, ...], ...]]]:
    """Load and validate a folder previously created by ``save_board_set``."""

    path = Path(folder)
    if not path.is_dir():
        raise ValueError(f"board folder does not exist: {path}")
    config = _read_json(path / "config.json")
    board_data = _read_json(path / "boards.json")
    if config.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported config schema version")
    if board_data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported boards schema version")

    width = config.get("board_size")
    expected_count = config.get("board_count")
    entries = board_data.get("boards")
    if not isinstance(width, int) or not isinstance(entries, list):
        raise ValueError("invalid board-set metadata")
    if len(entries) != expected_count:
        raise ValueError("board count does not match config.json")

    boards = []
    for expected_id, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or entry.get("id") != expected_id:
            raise ValueError("board IDs must be consecutive and start at 1")
        cells = entry.get("cells")
        if (
            not isinstance(cells, list)
            or len(cells) != width
            or any(not isinstance(row, list) or len(row) != width for row in cells)
        ):
            raise ValueError(f"board {expected_id} has invalid dimensions")
        boards.append(tuple(tuple(cell for cell in row) for row in cells))
    return config, boards


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing required file: {path.name}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value
