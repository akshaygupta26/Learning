"""SQLite connection handling and schema initialisation."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a connection with sane defaults for a local analytical store."""
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL lets a notebook read while an ingest is writing.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


@contextmanager
def session(db_path: Path | None = None):
    """Connection as a context manager, committing on clean exit."""
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema(conn: sqlite3.Connection) -> None:
    """Apply schema.sql. Safe to re-run — every statement is IF NOT EXISTS."""
    conn.executescript(config.SCHEMA_PATH.read_text())
    conn.commit()


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Row counts per table, for status output."""
    tables = [
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
