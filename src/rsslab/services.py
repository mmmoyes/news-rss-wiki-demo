from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from rsslab.models import ArticleCandidate, RefreshResult, Source
from rsslab.parser import iso_z, parse_feed
from rsslab.rss import HttpFetcher


def _now() -> str:
    return iso_z(datetime.now(UTC))


def _source_from_row(row: sqlite3.Row) -> Source:
    return Source(
        id=row["id"],
        feed_url=row["feed_url"],
        site_url=row["site_url"],
        title=row["title"],
        description=row["description"],
        source_name=row["source_name"],
        source_type=row["source_type"],
        topics=row["topics"],
        language=row["language"],
        trust_level=row["trust_level"],
    )


def add_source(
    conn: sqlite3.Connection,
    feed_url: str,
    topic: str,
    language: str,
    trust_level: str,
    fetcher=None,
) -> Source:
    fetcher = fetcher or HttpFetcher()
    content = fetcher.fetch(feed_url)
    metadata, _ = parse_feed(content)
    now = _now()
    cursor = conn.execute(
        """
        insert into sources (
            feed_url, site_url, title, description, source_name, source_type,
            topics, language, trust_level, created_at, updated_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(feed_url) do update set
            site_url = excluded.site_url,
            title = excluded.title,
            description = excluded.description,
            source_name = excluded.source_name,
            source_type = excluded.source_type,
            topics = excluded.topics,
            language = excluded.language,
            trust_level = excluded.trust_level,
            updated_at = excluded.updated_at
        """,
        (
            feed_url,
            metadata.site_url,
            metadata.title,
            metadata.description,
            metadata.title,
            metadata.source_type,
            topic,
            language,
            trust_level,
            now,
            now,
        ),
    )
    conn.commit()
    source_id = cursor.lastrowid
    if not source_id:
        source_id = conn.execute("select id from sources where feed_url = ?", (feed_url,)).fetchone()["id"]
    return get_source(conn, int(source_id))


def get_source(conn: sqlite3.Connection, source_id: int) -> Source:
    row = conn.execute("select * from sources where id = ?", (source_id,)).fetchone()
    if row is None:
        raise ValueError(f"source not found: {source_id}")
    return _source_from_row(row)


def list_sources(conn: sqlite3.Connection) -> list[Source]:
    return [_source_from_row(row) for row in conn.execute("select * from sources order by id").fetchall()]


def remove_source(conn: sqlite3.Connection, source_id: int) -> None:
    conn.execute("delete from sources where id = ?", (source_id,))
    conn.commit()


def _upsert_article(conn: sqlite3.Connection, source_id: int, article: ArticleCandidate) -> str:
    now = _now()
    existing = conn.execute("select id from articles where dedupe_key = ?", (article.dedupe_key,)).fetchone()
    if existing:
        conn.execute(
            """
            update articles set
                source_id = ?,
                guid = ?,
                url = ?,
                canonical_url = ?,
                title = ?,
                author = ?,
                published_at = ?,
                fetched_at = ?,
                summary_from_rss = ?,
                raw_entry_json = ?,
                content_hash = ?,
                updated_at = ?
            where dedupe_key = ?
            """,
            (
                source_id,
                article.guid,
                article.url,
                article.canonical_url,
                article.title,
                article.author,
                article.published_at,
                article.fetched_at,
                article.summary_from_rss,
                article.raw_entry_json,
                article.content_hash,
                now,
                article.dedupe_key,
            ),
        )
        return "updated"
    conn.execute(
        """
        insert into articles (
            source_id, guid, url, canonical_url, title, author, published_at,
            fetched_at, summary_from_rss, raw_entry_json, content_hash,
            dedupe_key, is_read, is_starred, created_at, updated_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
        """,
        (
            source_id,
            article.guid,
            article.url,
            article.canonical_url,
            article.title,
            article.author,
            article.published_at,
            article.fetched_at,
            article.summary_from_rss,
            article.raw_entry_json,
            article.content_hash,
            article.dedupe_key,
            now,
            now,
        ),
    )
    return "inserted"


def refresh_source(conn: sqlite3.Connection, source_id: int, fetcher=None) -> RefreshResult:
    fetcher = fetcher or HttpFetcher()
    source = get_source(conn, source_id)
    inserted = 0
    updated = 0
    try:
        content = fetcher.fetch(source.feed_url)
        metadata, articles = parse_feed(content)
        for article in articles:
            result = _upsert_article(conn, source.id, article)
            if result == "inserted":
                inserted += 1
            else:
                updated += 1
        now = _now()
        conn.execute(
            """
            update sources set
                site_url = ?,
                title = ?,
                description = ?,
                source_name = ?,
                source_type = ?,
                last_fetched_at = ?,
                last_error = null,
                updated_at = ?
            where id = ?
            """,
            (
                metadata.site_url,
                metadata.title,
                metadata.description,
                metadata.title,
                metadata.source_type,
                now,
                now,
                source.id,
            ),
        )
        conn.commit()
        return RefreshResult(source_id=source.id, inserted=inserted, updated=updated)
    except Exception as exc:
        conn.execute(
            "update sources set last_error = ?, updated_at = ? where id = ?",
            (str(exc), _now(), source.id),
        )
        conn.commit()
        raise


def refresh_all(conn: sqlite3.Connection, fetcher=None) -> RefreshResult:
    total = RefreshResult(source_id=None, inserted=0, updated=0)
    for source in list_sources(conn):
        result = refresh_source(conn, source.id, fetcher=fetcher)
        total = RefreshResult(
            source_id=None,
            inserted=total.inserted + result.inserted,
            updated=total.updated + result.updated,
            errors=total.errors + result.errors,
        )
    return total
