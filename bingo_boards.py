"""Generate diverse bingo boards with a low estimated tie rate.

The public function uses only the Python standard library.  Boards are returned
as tuples of rows and the free center is represented by ``None``.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from random import Random
from secrets import randbits
import sys
from typing import TypeVar

from board_storage import save_board_set


T = TypeVar("T")
Board = tuple[tuple[T | None, ...], ...]
DEFAULT_CANDIDATE_COUNT = 64
DEFAULT_OPTIMIZATION_TRIALS = 200
DEFAULT_OPTIMIZATION_ROUNDS = 150


@dataclass(frozen=True)
class BingoMetrics:
    """Quality measurements for a complete set of boards."""

    duplicate_board_pairs: int
    identical_winning_line_pairs: int
    estimated_tie_rate: float
    average_winners_per_game: float
    maximum_winners_in_game: int
    minimum_board_distance: float
    closest_board_pair: tuple[int, int] | None
    closest_content_distance: float
    closest_position_distance: float
    closest_winning_line_distance: float
    closest_adjacency_distance: float
    maximum_shared_items: int
    maximum_same_position_items: int
    maximum_winning_line_overlap: int
    maximum_shared_adjacencies: int
    minimum_win_rate: float
    maximum_win_rate: float


def main(argv: Sequence[str] | None = None) -> int:
    """Generate and print boards from three command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Generate diverse bingo boards with a free center."
    )
    parser.add_argument(
        "entries",
        type=int,
        help="number of unique entries in the drawing pool",
    )
    parser.add_argument(
        "board_size",
        type=int,
        help="width and height of each square board",
    )
    parser.add_argument(
        "num_boards",
        type=int,
        help="number of boards to generate",
    )
    args = parser.parse_args(argv)

    generation_seed = randbits(63)
    try:
        boards = generate_bingo_boards(
            items=list(range(args.entries)),
            board_count=args.num_boards,
            width=args.board_size,
            seed=generation_seed,
        )
    except ValueError as error:
        parser.error(str(error))

    board_folder = save_board_set(
        boards,
        {
            "entry_count": args.entries,
            "entry_range": {"start": 0, "stop_exclusive": args.entries},
            "board_size": args.board_size,
            "board_count": args.num_boards,
            "free_space": {
                "row": args.board_size // 2,
                "column": args.board_size // 2,
                "stored_value": None,
            },
            "winning_patterns": ["rows", "columns", "two_diagonals"],
            "generator": {
                "algorithm": "balanced-greedy-fixed-draw-local-swap-v1",
                "seed": generation_seed,
                "candidate_count": DEFAULT_CANDIDATE_COUNT,
                "optimization_simulation_trials": DEFAULT_OPTIMIZATION_TRIALS,
                "optimization_rounds": DEFAULT_OPTIMIZATION_ROUNDS,
                "distance_weights": {
                    "content": 4,
                    "position": 2,
                    "winning_line": 5,
                    "adjacency": 1,
                },
            },
        },
    )

    cell_width = max(4, len(str(args.entries)))
    for board_number, board in enumerate(boards, start=1):
        if board_number > 1:
            print()
        print(f"Board {board_number}")
        for row in board:
            print(
                " ".join(
                    f"{'FREE' if cell is None else cell:>{cell_width}}"
                    for cell in row
                )
            )

    metrics = analyze_bingo_boards(boards, simulation_trials=2_000, seed=0)
    print("\nMetrics")
    print(f"  Duplicate board pairs:          {metrics.duplicate_board_pairs}")
    print(
        "  Identical winning-line pairs:  "
        f"{metrics.identical_winning_line_pairs}"
    )
    print(f"  Estimated tie rate:             {metrics.estimated_tie_rate:.2%}")
    print(
        "  Average winners per game:      "
        f"{metrics.average_winners_per_game:.3f}"
    )
    print(f"  Maximum winners in one game:    {metrics.maximum_winners_in_game}")
    print(
        "  Board win-rate range:          "
        f"{metrics.minimum_win_rate:.2%} - {metrics.maximum_win_rate:.2%}"
    )
    if metrics.closest_board_pair is not None:
        left, right = metrics.closest_board_pair
        print(f"  Closest board pair:             {left} and {right}")
        print(
            "  Minimum composite distance:    "
            f"{metrics.minimum_board_distance:.2%}"
        )
        print(f"    Content distance:             {metrics.closest_content_distance:.2%}")
        print(f"    Position distance:            {metrics.closest_position_distance:.2%}")
        print(
            "    Winning-line distance:        "
            f"{metrics.closest_winning_line_distance:.2%}"
        )
        print(
            "    Adjacency distance:           "
            f"{metrics.closest_adjacency_distance:.2%}"
        )
    print(f"  Most shared items:              {metrics.maximum_shared_items}")
    print(
        "  Most same-position items:       "
        f"{metrics.maximum_same_position_items}"
    )
    print(
        "  Largest winning-line overlap:   "
        f"{metrics.maximum_winning_line_overlap}"
    )
    print(
        "  Most shared adjacencies:        "
        f"{metrics.maximum_shared_adjacencies}"
    )
    print(f"\nSaved board set: {board_folder}")

    return 0


def generate_bingo_boards(
    items: Sequence[T],
    board_count: int,
    width: int,
    *,
    seed: int | None = None,
    candidate_count: int = DEFAULT_CANDIDATE_COUNT,
    simulation_trials: int = DEFAULT_OPTIMIZATION_TRIALS,
    optimization_rounds: int = DEFAULT_OPTIMIZATION_ROUNDS,
) -> list[Board[T]]:
    """Return a reproducible set of square bingo boards.

    The center cell is always free.  Rows, columns, and the two diagonals are
    treated as winning lines.  The generator first builds boards greedily for
    content and layout diversity, then uses fixed random draw orders to reduce
    estimated ties without sacrificing the higher-priority validity rules.

    ``items`` must contain unique, non-``None`` values.  At least
    ``width * width - 1`` items are required.
    """

    values = list(items)
    _validate_inputs(
        values,
        board_count,
        width,
        candidate_count,
        simulation_trials,
        optimization_rounds,
    )

    rng = Random(seed)
    item_count = len(values)
    center = (width * width) // 2
    playable_positions = [i for i in range(width * width) if i != center]
    line_positions = _winning_lines(width)

    usage = Counter()
    position_usage = [Counter() for _ in range(width * width)]
    pair_usage = Counter()
    boards: list[list[int]] = []

    # Generate many candidates for each board, then keep the one whose closest
    # neighbour is least similar.  Integer item IDs let arbitrary values be
    # returned as long as equality can establish that the input is unique.
    for _ in range(board_count):
        candidates = [
            _candidate_board(
                item_count,
                playable_positions,
                center,
                usage,
                position_usage,
                pair_usage,
                rng,
            )
            for _ in range(candidate_count)
        ]
        board = min(
            candidates,
            key=lambda candidate: _candidate_score(
                candidate,
                boards,
                line_positions,
                usage,
                position_usage,
                item_count,
            ),
        )
        boards.append(board)
        _record_board(board, usage, position_usage, pair_usage)

    # Use the same sample draw orders for every proposed change.  That makes
    # comparisons fair and the result deterministic for a given seed.
    draw_orders = []
    for _ in range(simulation_trials):
        order = list(range(item_count))
        rng.shuffle(order)
        ranks = [0] * item_count
        for rank, item_id in enumerate(order):
            ranks[item_id] = rank
        draw_orders.append(ranks)

    current_score = _set_score(boards, line_positions, draw_orders, item_count)
    for _ in range(optimization_rounds):
        board_index = rng.randrange(board_count)
        first, second = rng.sample(playable_positions, 2)
        board = boards[board_index]
        board[first], board[second] = board[second], board[first]
        proposed_score = _set_score(
            boards, line_positions, draw_orders, item_count
        )
        if proposed_score <= current_score:
            current_score = proposed_score
        else:
            board[first], board[second] = board[second], board[first]

    return [
        tuple(
            tuple(None if item_id == -1 else values[item_id] for item_id in row)
            for row in _rows(board, width)
        )
        for board in boards
    ]


def analyze_bingo_boards(
    boards: Sequence[Sequence[Sequence[T | None]]],
    *,
    simulation_trials: int = 2_000,
    seed: int | None = None,
) -> BingoMetrics:
    """Measure diversity, structural overlap, and estimated ties.

    Distances range from zero (identical for that component) to one (no shared
    structure).  The composite distance weights content, position, winning
    lines, and adjacency by 4, 2, 5, and 1 respectively.
    """

    if not boards:
        raise ValueError("at least one board is required")
    if simulation_trials < 1:
        raise ValueError("simulation_trials must be at least 1")

    width = len(boards[0])
    if width < 3 or width % 2 == 0:
        raise ValueError("boards must have an odd width of at least 3")
    center = (width * width) // 2
    known_items: list[T] = []
    encoded_boards: list[list[int]] = []

    for board in boards:
        if len(board) != width or any(len(row) != width for row in board):
            raise ValueError("all boards must be square and the same size")
        flat = [cell for row in board for cell in row]
        if flat[center] is not None or sum(cell is None for cell in flat) != 1:
            raise ValueError("each board must have exactly one free center")
        encoded = []
        for cell in flat:
            if cell is None:
                encoded.append(-1)
                continue
            item_id = next(
                (index for index, known in enumerate(known_items) if cell == known),
                None,
            )
            if item_id is None:
                item_id = len(known_items)
                known_items.append(cell)
            encoded.append(item_id)
        encoded_boards.append(encoded)

    lines = _winning_lines(width)
    board_sets = [frozenset(board) - {-1} for board in encoded_boards]
    board_lines = [_line_sets(board, lines) for board in encoded_boards]
    board_adjacencies = [_adjacencies(board, width) for board in encoded_boards]

    duplicate_boards = 0
    duplicate_lines = 0
    minimum_distance = 1.0
    closest_pair = None
    closest_components = (1.0, 1.0, 1.0, 1.0)
    maximum_shared_items = 0
    maximum_same_positions = 0
    maximum_line_overlap = 0
    maximum_shared_adjacencies = 0

    playable_count = width * width - 1
    for left_index in range(len(encoded_boards)):
        for right_index in range(left_index + 1, len(encoded_boards)):
            shared_items = len(board_sets[left_index] & board_sets[right_index])
            same_positions = sum(
                left == right and left != -1
                for left, right in zip(
                    encoded_boards[left_index], encoded_boards[right_index]
                )
            )
            line_pairs = [
                (left, right)
                for left in board_lines[left_index]
                for right in board_lines[right_index]
            ]
            duplicate_lines += sum(left == right for left, right in line_pairs)
            line_overlap = max(
                (len(left & right) for left, right in line_pairs), default=0
            )
            line_similarity = max(
                (
                    len(left & right) / min(len(left), len(right))
                    for left, right in line_pairs
                ),
                default=0.0,
            )
            shared_adjacencies = len(
                board_adjacencies[left_index] & board_adjacencies[right_index]
            )
            adjacency_denominator = min(
                len(board_adjacencies[left_index]),
                len(board_adjacencies[right_index]),
            )

            content_distance = 1 - shared_items / playable_count
            position_distance = 1 - same_positions / playable_count
            line_distance = 1 - line_similarity
            adjacency_distance = 1 - (
                shared_adjacencies / adjacency_denominator
                if adjacency_denominator
                else 0.0
            )
            composite_distance = (
                content_distance * 4
                + position_distance * 2
                + line_distance * 5
                + adjacency_distance
            ) / 12

            duplicate_boards += board_sets[left_index] == board_sets[right_index]
            maximum_shared_items = max(maximum_shared_items, shared_items)
            maximum_same_positions = max(maximum_same_positions, same_positions)
            maximum_line_overlap = max(maximum_line_overlap, line_overlap)
            maximum_shared_adjacencies = max(
                maximum_shared_adjacencies, shared_adjacencies
            )
            if composite_distance < minimum_distance:
                minimum_distance = composite_distance
                closest_pair = (left_index + 1, right_index + 1)
                closest_components = (
                    content_distance,
                    position_distance,
                    line_distance,
                    adjacency_distance,
                )

    rng = Random(seed)
    tied_trials = 0
    total_winners = 0
    maximum_winners = 0
    wins = [0] * len(encoded_boards)
    for _ in range(simulation_trials):
        draw_order = list(range(len(known_items)))
        rng.shuffle(draw_order)
        ranks = [0] * len(known_items)
        for rank, item_id in enumerate(draw_order):
            ranks[item_id] = rank
        completion_times = [
            min(max(ranks[item] for item in line) for line in lines_for_board)
            for lines_for_board in board_lines
        ]
        winning_time = min(completion_times)
        winners = [
            index for index, time in enumerate(completion_times) if time == winning_time
        ]
        tied_trials += len(winners) > 1
        total_winners += len(winners)
        maximum_winners = max(maximum_winners, len(winners))
        for winner in winners:
            wins[winner] += 1

    content, position, winning_line, adjacency = closest_components
    win_rates = [wins_for_board / simulation_trials for wins_for_board in wins]
    return BingoMetrics(
        duplicate_board_pairs=duplicate_boards,
        identical_winning_line_pairs=duplicate_lines,
        estimated_tie_rate=tied_trials / simulation_trials,
        average_winners_per_game=total_winners / simulation_trials,
        maximum_winners_in_game=maximum_winners,
        minimum_board_distance=minimum_distance,
        closest_board_pair=closest_pair,
        closest_content_distance=content,
        closest_position_distance=position,
        closest_winning_line_distance=winning_line,
        closest_adjacency_distance=adjacency,
        maximum_shared_items=maximum_shared_items,
        maximum_same_position_items=maximum_same_positions,
        maximum_winning_line_overlap=maximum_line_overlap,
        maximum_shared_adjacencies=maximum_shared_adjacencies,
        minimum_win_rate=min(win_rates),
        maximum_win_rate=max(win_rates),
    )


def _validate_inputs(
    items: list[object],
    board_count: int,
    width: int,
    candidate_count: int,
    simulation_trials: int,
    optimization_rounds: int,
) -> None:
    if width < 3 or width % 2 == 0:
        raise ValueError("width must be an odd integer of at least 3")
    if board_count < 1:
        raise ValueError("board_count must be at least 1")
    if len(items) < width * width - 1:
        raise ValueError("not enough unique items to fill one board")
    if any(item is None for item in items):
        raise ValueError("None is reserved for the free center")
    for index, item in enumerate(items):
        if any(item == previous for previous in items[:index]):
            raise ValueError("items must be unique")
    if candidate_count < 1:
        raise ValueError("candidate_count must be at least 1")
    if simulation_trials < 1:
        raise ValueError("simulation_trials must be at least 1")
    if optimization_rounds < 0:
        raise ValueError("optimization_rounds cannot be negative")


def _candidate_board(
    item_count: int,
    positions: list[int],
    center: int,
    usage: Counter,
    position_usage: list[Counter],
    pair_usage: Counter,
    rng: Random,
) -> list[int]:
    board = [-1] * (len(positions) + 1)
    selected: list[int] = []
    shuffled_positions = positions.copy()
    rng.shuffle(shuffled_positions)

    for position in shuffled_positions:
        choices = []
        for item_id in range(item_count):
            if item_id in selected:
                continue
            shared_history = sum(
                pair_usage[_pair(item_id, other)] for other in selected
            )
            choices.append(
                (
                    usage[item_id],
                    shared_history,
                    position_usage[position][item_id],
                    rng.random(),
                    item_id,
                )
            )
        chosen = min(choices)[-1]
        board[position] = chosen
        selected.append(chosen)

    board[center] = -1
    return board


def _candidate_score(
    candidate: list[int],
    boards: list[list[int]],
    lines: list[tuple[int, ...]],
    usage: Counter,
    position_usage: list[Counter],
    item_count: int,
) -> tuple:
    candidate_set = frozenset(candidate) - {-1}
    candidate_lines = _line_sets(candidate, lines)
    duplicate_board = sum(
        candidate_set == (frozenset(board) - {-1}) for board in boards
    )
    duplicate_lines = 0
    worst_line_overlap = 0
    worst_content_overlap = 0
    worst_position_overlap = 0

    for board in boards:
        other_lines = _line_sets(board, lines)
        overlaps = [len(left & right) for left in candidate_lines for right in other_lines]
        duplicate_lines += sum(left == right for left in candidate_lines for right in other_lines)
        worst_line_overlap = max(worst_line_overlap, max(overlaps, default=0))
        worst_content_overlap = max(
            worst_content_overlap,
            len(candidate_set & (frozenset(board) - {-1})),
        )
        worst_position_overlap = max(
            worst_position_overlap,
            sum(a == b and a != -1 for a, b in zip(candidate, board)),
        )

    resulting_usage = [
        usage[item] + (item in candidate_set) for item in range(item_count)
    ]
    usage_spread = max(resulting_usage, default=0) - min(resulting_usage, default=0)
    position_repeats = sum(
        position_usage[position][item_id]
        for position, item_id in enumerate(candidate)
        if item_id != -1
    )
    return (
        duplicate_board,
        duplicate_lines,
        worst_line_overlap,
        worst_content_overlap,
        worst_position_overlap,
        usage_spread,
        position_repeats,
    )


def _set_score(
    boards: list[list[int]],
    lines: list[tuple[int, ...]],
    draw_orders: list[list[int]],
    item_count: int,
) -> tuple:
    board_sets = [frozenset(board) - {-1} for board in boards]
    board_lines = [_line_sets(board, lines) for board in boards]

    duplicate_boards = 0
    duplicate_lines = 0
    worst_similarity = 0
    total_similarity = 0
    for left_index in range(len(boards)):
        for right_index in range(left_index + 1, len(boards)):
            duplicate_boards += board_sets[left_index] == board_sets[right_index]
            line_overlaps = [
                len(left & right)
                for left in board_lines[left_index]
                for right in board_lines[right_index]
            ]
            duplicate_lines += sum(
                left == right
                for left in board_lines[left_index]
                for right in board_lines[right_index]
            )
            content_overlap = len(board_sets[left_index] & board_sets[right_index])
            position_overlap = sum(
                a == b and a != -1
                for a, b in zip(boards[left_index], boards[right_index])
            )
            line_penalty = sum(overlap**3 for overlap in line_overlaps)
            similarity = content_overlap * 20 + position_overlap * 8 + line_penalty
            worst_similarity = max(worst_similarity, similarity)
            total_similarity += similarity

    tied_trials = 0
    extra_tied_winners = 0
    wins = [0] * len(boards)
    for ranks in draw_orders:
        completion_times = [
            min(max(ranks[item] for item in line) for line in board_lines_for_one)
            for board_lines_for_one in board_lines
        ]
        winning_time = min(completion_times)
        winners = [i for i, time in enumerate(completion_times) if time == winning_time]
        tied_trials += len(winners) > 1
        extra_tied_winners += len(winners) - 1
        for winner in winners:
            wins[winner] += 1

    usage = Counter(item for board in boards for item in board if item != -1)
    usage_counts = [usage[item] for item in range(item_count)]
    usage_spread = max(usage_counts) - min(usage_counts)
    win_spread = max(wins) - min(wins)

    return (
        duplicate_boards,
        duplicate_lines,
        tied_trials,
        extra_tied_winners,
        worst_similarity,
        total_similarity,
        usage_spread,
        win_spread,
    )


def _winning_lines(width: int) -> list[tuple[int, ...]]:
    rows = [tuple(row * width + column for column in range(width)) for row in range(width)]
    columns = [tuple(row * width + column for row in range(width)) for column in range(width)]
    diagonals = [
        tuple(i * width + i for i in range(width)),
        tuple(i * width + width - i - 1 for i in range(width)),
    ]
    return rows + columns + diagonals


def _line_sets(board: list[int], lines: list[tuple[int, ...]]) -> list[frozenset[int]]:
    return [
        frozenset(board[position] for position in line if board[position] != -1)
        for line in lines
    ]


def _adjacencies(board: list[int], width: int) -> frozenset[tuple[int, int]]:
    """Return unordered horizontal and vertical item pairs, excluding free."""

    pairs = set()
    for row in range(width):
        for column in range(width):
            position = row * width + column
            if board[position] == -1:
                continue
            neighbours = []
            if column + 1 < width:
                neighbours.append(position + 1)
            if row + 1 < width:
                neighbours.append(position + width)
            for neighbour in neighbours:
                if board[neighbour] != -1:
                    pairs.add(_pair(board[position], board[neighbour]))
    return frozenset(pairs)


def _record_board(
    board: list[int],
    usage: Counter,
    position_usage: list[Counter],
    pair_usage: Counter,
) -> None:
    items = [item for item in board if item != -1]
    for position, item in enumerate(board):
        if item != -1:
            usage[item] += 1
            position_usage[position][item] += 1
    for index, left in enumerate(items):
        for right in items[index + 1 :]:
            pair_usage[_pair(left, right)] += 1


def _pair(left: int, right: int) -> tuple[int, int]:
    return (left, right) if left < right else (right, left)


def _rows(board: list[int], width: int) -> list[list[int]]:
    return [board[start : start + width] for start in range(0, len(board), width)]


if __name__ == "__main__":
    sys.exit(main())
