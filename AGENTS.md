# Project Instructions

## Collaboration workflow

- The user runs the application from the terminal and reports visual or runtime behavior.
- Do not run routine compile, lint, diagnostic, or launch checks after every edit unless the user asks for them or a concrete reported failure requires one.
- Prefer making the focused change, explaining what changed, and giving the user the command to run it.
- Use the project-local environment at `.venv\Scripts\python.exe` when a Python command is necessary.
- Do not repeatedly reinstall packages or investigate global Python environments unless the user reports a dependency problem.
- Treat the user's visual testing and runtime reports as the primary validation signal for this interactive application.

## Application context

- This is a standalone, cross-platform, local-only music video bingo desktop application.
- The current prototype is a PySide6 video player in `video_edit/app.py`, with `main.py` retained as a compatibility launcher.
- The user selects a local video file and previews a start/end range using two handles on one shared timeline.
- The video and future bingo overlays should remain in the same stable display container.
- Future audio work will analyze stereo-preserving audio with integrated LUFS and apply gain only; the target should be configurable with a quieter default.
- Saved clips live in SQLite and contain the local path, title, artist, and selected time range; future bingo lists should reference clip IDs through a join table.
- Do not add video acquisition, downloading, source identification, recommendation, upload, or network features.

## Current player behavior

- The player uses Qt multimedia and `QVideoWidget` for playback.
- Playback waits for media loading before starting.
- Dragging the range handles updates the timestamps without seeking; when a handle is released, the player seeks to that final position and briefly plays before pausing so Qt can render the selected frame.
- The left handle selects the start; the right handle selects the end; handles must never cross.
