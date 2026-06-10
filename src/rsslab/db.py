from __future__ import annotations

import os
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path(os.environ.get("RSSLAB_DB", Path(".rsslab") / "rsslab.db"))


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path is not None else DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    _migrate_articles(conn)
    _migrate_collections(conn)
    ensure_fts(conn)
    conn.commit()


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row["name"] == column for row in conn.execute(f"pragma table_info({table})").fetchall())


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute("select 1 from sqlite_master where type = 'table' and name = ?", (table,)).fetchone()
        is not None
    )


def _migrate_articles(conn: sqlite3.Connection) -> None:
    columns = {
        "content_text": "text not null default ''",
        "content_html": "text not null default ''",
        "raw_html_path": "text not null default ''",
        "extraction_status": "text not null default 'pending'",
        "extraction_error": "text not null default ''",
        "extraction_attempted_at": "text",
    }
    for column, definition in columns.items():
        if not _has_column(conn, "articles", column):
            conn.execute(f"alter table articles add column {column} {definition}")


def _migrate_collections(conn: sqlite3.Connection) -> None:
    if not _has_table(conn, "collection_jobs"):
        return
    columns = {
        "since": "text",
        "languages_json": "text not null default '[]'",
        "trust_levels_json": "text not null default '[]'",
        "topics_json": "text not null default '[]'",
        "limit_count": "integer not null default 20",
        "complete_full_text": "integer not null default 0",
        "policy_json": "text not null default '{}'",
        "status": "text not null default 'completed'",
        "result_count": "integer not null default 0",
    }
    for column, definition in columns.items():
        if not _has_column(conn, "collection_jobs", column):
            conn.execute(f"alter table collection_jobs add column {column} {definition}")


def fts5_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("create virtual table if not exists temp.rsslab_fts_probe using fts5(value)")
        conn.execute("drop table if exists temp.rsslab_fts_probe")
        return True
    except sqlite3.OperationalError:
        return False


def ensure_fts(conn: sqlite3.Connection) -> bool:
    if not fts5_available(conn):
        return False
    conn.execute(
        """
        create virtual table if not exists articles_fts using fts5(
            article_id unindexed,
            title,
            author,
            summary_from_rss,
            content_text,
            source_name
        )
        """
    )
    return True
