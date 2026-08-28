"""Simulate randomized games against a saved board set."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from random import Random
from secrets import randbits
from statistics import pstdev

from board_storage import load_board_set


@dataclass(frozen=True)
class BoardWinMetrics:
    board_id: int
    sole_wins: int
    tied_wins: int
    winner_appearances: int
    credited_wins: float
    credited_win_rate: float


@dataclass(frozen=True)
class SimulationReport:
    simulations: int
    seed: int
    entry_count: int
    board_size: int
    board_count: int
    tie_games: int
    tie_rate: float
    average_calls_to_win: float
    minimum_credited_win_rate: float
    maximum_credited_win_rate: float
    winner_rate_standard_deviation: float
    maximum_deviation_from_ideal: float
    boards: tuple[BoardWinMetrics, ...]


def simulate_board_folder(
    folder: str | Path,
    simulations: int,
    *,
    seed: int | None = None,
) -> SimulationReport:
    """Load a board folder and simulate ``simulations`` random call orders."""

    if simulations < 1:
        raise ValueError("simulations must be at least 1")
    config, boards = load_board_set(folder)
    entry_count = config.get("entry_count")
    width = config.get("board_size")
    if not isinstance(entry_count, int) or entry_count < 1:
        raise ValueError("config entry_count must be a positive integer")
    if not isinstance(width, int) or width < 3 or width % 2 == 0:
        raise ValueError("config board_size must be an odd integer of at least 3")
    if not boards:
        raise ValueError("board set must contain at least one board")

    winning_positions = _winning_lines(width)
    winning_lines = []
    for board_id, board in enumerate(boards, start=1):
        flat = [cell for row in board for cell in row]
        center = width * width // 2
        if flat[center] is not None or sum(cell is None for cell in flat) != 1:
            raise ValueError(f"board {board_id} must have exactly one free center")
        playable = [cell for cell in flat if cell is not None]
        if any(not isinstance(cell, int) or not 0 <= cell < entry_count for cell in playable):
            raise ValueError(
                f"board {board_id} contains an entry outside 0-{entry_count - 1}"
            )
        if len(set(playable)) != len(playable):
            raise ValueError(f"board {board_id} contains duplicate entries")
        winning_lines.append(
            [
                tuple(flat[position] for position in line if flat[position] is not None)
                for line in winning_positions
            ]
        )

    resolved_seed = randbits(63) if seed is None else seed
    rng = Random(resolved_seed)
    sole_wins = [0] * len(boards)
    tied_wins = [0] * len(boards)
    appearances = [0] * len(boards)
    credits = [0.0] * len(boards)
    tie_games = 0
    total_calls_to_win = 0

    for _ in range(simulations):
        call_order = list(range(entry_count))
        rng.shuffle(call_order)
        ranks = [0] * entry_count
        for rank, entry in enumerate(call_order, start=1):
            ranks[entry] = rank
        completion_times = [
            min(max(ranks[entry] for entry in line) for line in lines_for_board)
            for lines_for_board in winning_lines
        ]
        winning_time = min(completion_times)
        winners = [
            index for index, time in enumerate(completion_times) if time == winning_time
        ]
        total_calls_to_win += winning_time
        if len(winners) > 1:
            tie_games += 1
        credit = 1 / len(winners)
        for winner in winners:
            appearances[winner] += 1
            credits[winner] += credit
            if len(winners) == 1:
                sole_wins[winner] += 1
            else:
                tied_wins[winner] += 1

    rates = [credit / simulations for credit in credits]
    ideal_rate = 1 / len(boards)
    per_board = tuple(
        BoardWinMetrics(
            board_id=index + 1,
            sole_wins=sole_wins[index],
            tied_wins=tied_wins[index],
            winner_appearances=appearances[index],
            credited_wins=credits[index],
            credited_win_rate=rates[index],
        )
        for index in range(len(boards))
    )
    return SimulationReport(
        simulations=simulations,
        seed=resolved_seed,
        entry_count=entry_count,
        board_size=width,
        board_count=len(boards),
        tie_games=tie_games,
        tie_rate=tie_games / simulations,
        average_calls_to_win=total_calls_to_win / simulations,
        minimum_credited_win_rate=min(rates),
        maximum_credited_win_rate=max(rates),
        winner_rate_standard_deviation=pstdev(rates),
        maximum_deviation_from_ideal=max(abs(rate - ideal_rate) for rate in rates),
        boards=per_board,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Simulate random calls for a saved bingo board set."
    )
    parser.add_argument("board_folder", help="folder containing config.json and boards.json")
    parser.add_argument("simulations", type=int, help="number of games to simulate")
    parser.add_argument("--seed", type=int, default=None, help="optional simulation seed")
    args = parser.parse_args(argv)

    try:
        report = simulate_board_folder(
            args.board_folder, args.simulations, seed=args.seed
        )
    except ValueError as error:
        parser.error(str(error))

    ideal = 1 / report.board_count
    print("Board-set simulation")
    print(f"  Folder:                    {Path(args.board_folder).resolve()}")
    print(f"  Entries:                   {report.entry_count} (0-{report.entry_count - 1})")
    print(f"  Board size:                {report.board_size}x{report.board_size}")
    print(f"  Boards:                    {report.board_count}")
    print(f"  Simulated games:           {report.simulations:,}")
    print(f"  Simulation seed:           {report.seed}")
    print(f"  Tie games:                 {report.tie_games:,} ({report.tie_rate:.2%})")
    print(f"  Average calls to win:      {report.average_calls_to_win:.2f}")
    print(f"  Ideal win share:           {ideal:.2%}")
    print(
        "  Actual win-share range:    "
        f"{report.minimum_credited_win_rate:.2%} - "
        f"{report.maximum_credited_win_rate:.2%}"
    )
    print(
        "  Win-share std. deviation:  "
        f"{report.winner_rate_standard_deviation:.3%}"
    )
    print(
        "  Largest ideal deviation:   "
        f"{report.maximum_deviation_from_ideal:.3%}"
    )
    print("\nPer-board results")
    print("  Board       Sole       Tied  Appearances  Credited wins   Win share")
    for board in report.boards:
        print(
            f"  {board.board_id:>5} "
            f"{board.sole_wins:>10,} "
            f"{board.tied_wins:>10,} "
            f"{board.winner_appearances:>12,} "
            f"{board.credited_wins:>14,.2f} "
            f"{board.credited_win_rate:>10.2%}"
        )
    return 0


def _winning_lines(width: int) -> list[tuple[int, ...]]:
    rows = [tuple(row * width + column for column in range(width)) for row in range(width)]
    columns = [tuple(row * width + column for row in range(width)) for column in range(width)]
    diagonals = [
        tuple(i * width + i for i in range(width)),
        tuple(i * width + width - i - 1 for i in range(width)),
    ]
    return rows + columns + diagonals
