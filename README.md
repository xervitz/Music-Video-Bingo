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