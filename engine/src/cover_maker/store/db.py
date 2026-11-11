"""SQLite access with WAL and numbered migrations (``PRAGMA user_version``)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Each entry is one migration; statements are separated by semicolons.
MIGRATIONS: tuple[str, ...] = (
    # 1: assets, step cache, jobs and items, installed models.
    """
    CREATE TABLE assets (
        sha256 TEXT PRIMARY KEY,
        rel_path TEXT NOT NULL,
        kind TEXT NOT NULL,
        bytes INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE step_cache (
        step TEXT NOT NULL,
        cache_key TEXT NOT NULL,
        output_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (step, cache_key)
    );
    CREATE TABLE jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        spec_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        error TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE job_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        ordinal INTEGER NOT NULL,
        input_path TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        current_step TEXT,
        outputs_json TEXT,
        error TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX job_items_job ON job_items(job_id);
    CREATE TABLE model_installs (
        model_id TEXT PRIMARY KEY,
        filename TEXT NOT NULL,
        sha256 TEXT,
        licence_sha256 TEXT NOT NULL,
        accepted_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # 2: library collections (watched folders, video playlists, imported playlist files).
    """
    CREATE TABLE collections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        source TEXT NOT NULL,
        title TEXT NOT NULL,
        extra_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        synced_at TEXT,
        UNIQUE (kind, source)
    );
    CREATE TABLE collection_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
        key TEXT NOT NULL,
        position INTEGER NOT NULL,
        title TEXT NOT NULL,
        artist TEXT,
        duration_s REAL,
        input TEXT,
        score REAL,
        status TEXT NOT NULL,
        manual INTEGER NOT NULL DEFAULT 0,
        UNIQUE (collection_id, key)
    )
    """,
    # 3: what the preview mixer can load for each processed item.
    """
    ALTER TABLE job_items ADD COLUMN preview_json TEXT
    """,
    # 4: title and artist shown in the queue (from tags or video metadata).
    """
    ALTER TABLE job_items ADD COLUMN title TEXT;
    ALTER TABLE job_items ADD COLUMN artist TEXT
    """,
    # 5: measured separation attempts, for preset tuning (separation/tuning.py).
    """
    CREATE TABLE separation_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id TEXT NOT NULL,
        device TEXT NOT NULL,
        precision TEXT NOT NULL,
        chunk_s REAL,
        audio_s REAL NOT NULL,
        wall_s REAL,
        oom INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX separation_runs_model ON separation_runs(model_id, device)
    """,
    # 6: musical analysis (tuning, key, tempo, beat grid) and named section markers (M14).
    """
    CREATE TABLE analyses (
        cache_key TEXT PRIMARY KEY,
        mix_sha TEXT NOT NULL,
        version INTEGER NOT NULL,
        tuning_cents REAL NOT NULL,
        key TEXT NOT NULL,
        mode TEXT NOT NULL,
        key_confidence REAL NOT NULL,
        bpm REAL NOT NULL,
        beats_json TEXT NOT NULL,
        downbeats_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX analyses_mix ON analyses(mix_sha);
    CREATE TABLE markers (
        mix_sha TEXT PRIMARY KEY,
        markers_json TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
)


def connect(path: Path) -> sqlite3.Connection:
    """Open the database and apply pending migrations."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # The API and the job thread use separate connections; wait instead of failing.
    conn.execute("PRAGMA busy_timeout=10000")
    migrate(conn)
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def migrate(conn: sqlite3.Connection) -> None:
    current = schema_version(conn)
    for number, script in enumerate(MIGRATIONS, start=1):
        if number <= current:
            continue
        conn.execute("BEGIN")
        try:
            # executescript() would commit the open transaction; run statements one by one.
            for statement in script.split(";"):
                if statement.strip():
                    conn.execute(statement)
            # PRAGMA accepts no bound parameters; `number` is an int from enumerate().
            # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            conn.execute(f"PRAGMA user_version = {int(number)}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
