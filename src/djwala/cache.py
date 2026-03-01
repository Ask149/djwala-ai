"""SQLite cache for track analysis results."""

from __future__ import annotations

import dataclasses
import json
import sqlite3

import numpy as np

from djwala.models import TrackAnalysis


class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types from librosa analysis."""

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


class AnalysisCache:
    """Simple SQLite-backed cache for TrackAnalysis objects."""

    def __init__(self, db_path: str = "djwala_cache.db"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS track_analysis (
                video_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def store(self, analysis: TrackAnalysis) -> None:
        data = json.dumps(dataclasses.asdict(analysis), cls=_NumpyEncoder)
        self._conn.execute(
            "INSERT OR REPLACE INTO track_analysis (video_id, data) VALUES (?, ?)",
            (analysis.video_id, data),
        )
        self._conn.commit()

    def get(self, video_id: str) -> TrackAnalysis | None:
        row = self._conn.execute(
            "SELECT data FROM track_analysis WHERE video_id = ?",
            (video_id,),
        ).fetchone()
        if row is None:
            return None
        d = json.loads(row["data"])
        return TrackAnalysis(**d)

    def has(self, video_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM track_analysis WHERE video_id = ? LIMIT 1",
            (video_id,),
        ).fetchone()
        return row is not None

    def close(self):
        self._conn.close()
