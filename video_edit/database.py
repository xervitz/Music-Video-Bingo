import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoClip:
    id: int
    file_path: str
    title: str
    artist: str
    start_ms: int
    end_ms: int


class VideoLibrary:
    def __init__(self, database_path=None):
        if database_path is None:
            database_path = Path.home() / ".music_video_bingo" / "library.sqlite3"
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self):
        self.connection.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS video_clips (
                id INTEGER PRIMARY KEY,
                file_path TEXT NOT NULL,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                start_ms INTEGER NOT NULL CHECK (start_ms >= 0),
                end_ms INTEGER NOT NULL CHECK (end_ms > start_ms),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_video_clips_artist_title
                ON video_clips (artist, title);

            CREATE TABLE IF NOT EXISTS bingo_lists (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS bingo_list_clips (
                list_id INTEGER NOT NULL REFERENCES bingo_lists(id) ON DELETE CASCADE,
                clip_id INTEGER NOT NULL REFERENCES video_clips(id) ON DELETE CASCADE,
                position INTEGER,
                PRIMARY KEY (list_id, clip_id)
            );
            """
        )
        self.connection.commit()

    def add_clip(self, file_path, title, artist, start_ms, end_ms):
        cursor = self.connection.execute(
            """
            INSERT INTO video_clips (file_path, title, artist, start_ms, end_ms)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(file_path), title.strip(), artist.strip(), start_ms, end_ms),
        )
        self.connection.commit()
        return cursor.lastrowid

    def list_clips(self):
        rows = self.connection.execute(
            """
            SELECT id, file_path, title, artist, start_ms, end_ms
            FROM video_clips
            ORDER BY artist COLLATE NOCASE, title COLLATE NOCASE, id
            """
        ).fetchall()
        return [VideoClip(**dict(row)) for row in rows]

    def create_list(self, name):
        cursor = self.connection.execute(
            "INSERT INTO bingo_lists (name) VALUES (?)",
            (name.strip(),),
        )
        self.connection.commit()
        return cursor.lastrowid

    def add_clip_to_list(self, list_id, clip_id, position=None):
        self.connection.execute(
            """
            INSERT OR IGNORE INTO bingo_list_clips (list_id, clip_id, position)
            VALUES (?, ?, ?)
            """,
            (list_id, clip_id, position),
        )
        self.connection.commit()

    def close(self):
        self.connection.close()
