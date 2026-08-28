# Music Video Bingo

Small standalone desktop demo for selecting and playing a local video file.

## Run

Create and activate a virtual environment, then install the dependency:

```text
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

On macOS or Linux, activate the environment with the equivalent command for that shell.

Use **Choose video** or `Ctrl+O` to select a local file. Playback uses the media support available through Qt and the operating system.

## Video Edit module

The player lives in the `video_edit` package and can be launched independently:

```text
python -m video_edit
```

Another Python application can open the editor window directly:

```python
from video_edit import VideoPlayerWindow

editor_window = VideoPlayerWindow()
editor_window.show()
```

The root `main.py` remains as a compatibility launcher for the same editor.

## Saved video clips

Saving a video stores its local file path, title, artist, and selected start/end
time codes in a SQLite database at:

```text
~/.music_video_bingo/library.sqlite3
```

The original media file is never copied or uploaded. A saved clip has its own
database ID, allowing future bingo lists to reference the same clip many times
through the `bingo_list_clips` join table.

This demo does not upload, scan, identify, recommend, or download video files. It does not yet perform loudness analysis or gain normalization.

## Bingo board generation

The standalone generator builds a static set of square bingo boards from a
unique item pool. Every board has a free middle square. Rows, columns, and both
diagonals are winning lines.

The generator prioritizes quality in this order:

1. Avoid duplicate boards.
2. Avoid identical winning lines on different boards.
3. Minimize ties across simulated random call orders.
4. Make the closest pair of boards as different as possible.
5. Balance how often each item is used.
6. Balance how often each board wins.

Board difference is evaluated through content overlap, items in the same cell,
winning-line overlap, and repeated horizontal or vertical adjacencies. The
reported composite distance weights those components at 4, 2, 5, and 1. A
distance of 0% means identical for that component; 100% means no shared
structure.

### Generate from Python

Call `generate_bingo_boards` with a unique item sequence, number of boards, and
an odd board width of at least 3:

```python
from bingo_boards import generate_bingo_boards

boards = generate_bingo_boards(
    items=[f"Video {number}" for number in range(1, 76)],
    board_count=20,
    width=5,
    seed=42,
)
```

At least `width * width - 1` unique items are required. Each board is returned
as a tuple of row tuples, and `None` represents the free center. Supplying the
same seed and generation settings produces the same boards.

The optional generation controls are:

- `candidate_count`: candidate layouts considered while adding each board.
- `simulation_trials`: fixed random call orders used during optimization.
- `optimization_rounds`: item-position swaps attempted after initial creation.

Larger values search more thoroughly but take longer.

### Generate and save numbered boards

Run the module directly with exactly three positional arguments:

```text
python bingo_boards.py <entries> <board-size> <number-of-boards>
```

For example:

```text
python bingo_boards.py 75 5 20
```

This creates twenty 5-by-5 boards from entries `0` through `74`, prints the
boards and their initial quality metrics, and saves a self-contained folder
under `board_sets/`. The folder name includes the entry count, board size, board
count, generation seed, and UTC creation time.

Each saved folder contains:

- `config.json`: schema version, generation time, entry range, board dimensions,
  free-space and winning rules, resolved seed, optimizer settings, algorithm
  version, and distance weights.
- `boards.json`: consecutive board IDs and their complete cell grids. The free
  center is stored as JSON `null`.

The resolved seed makes every saved set reproducible even though no seed is
required on the command line.

The initial report includes duplicate counts, estimated tie rate, average and
maximum simultaneous winners, win-rate range, the closest board pair, component
distances, and the worst observed overlap in each category.

### Test a saved board set

The `board_testing` package loads the folder metadata and runs a requested
number of independent games. Every game shuffles the complete call pool from
`0` through `entries - 1`; all boards receive the same call order.

```text
python -m board_testing board_sets/<folder-name> 100000 --seed 42
```

The simulation seed is optional. When omitted, the tester creates and reports a
seed so the run can still be repeated exactly.

The report shows:

- Overall tie count and tie rate.
- Average number of calls before the first win.
- Ideal and actual credited win-share ranges.
- Winner-share standard deviation and largest deviation from ideal.
- Sole wins, tied wins, total winner appearances, credited wins, and credited
  win share for every board.

When several boards tie, they split one credited win equally. Credited win
shares therefore total 100% across all boards and provide the clearest measure
of whether winners are evenly distributed. Sole and tied win counts remain
separate so a balanced-looking distribution cannot hide excessive ties.
