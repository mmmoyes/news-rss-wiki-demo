from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from rsslab.db import ensure_fts


TRUST_SCORES = {"high": 3, "medium": 2, "low": 1}


@dataclass(frozen=True)
class SearchResult:
    id: int
    source_id: int
    source_name: str
    trust_level: str
    title: str
    author: str
    published_at: str
    url: str
    summary_from_rss: str
    content_text: str
    extraction_status: str
    score: float


def _duration_start(since: str | None) -> str | None:
    if not since:
        return None
    value = since.strip().lower()
    try:
        if value.endswith("d"):
            dt = datetime.now(UTC) - timedelta(days=int(value[:-1]))
        elif value.endswith("h"):
            dt = datetime.now(UTC) - timedelta(hours=int(value[:-1]))
        else:
            return value
    except ValueError:
        return None
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _row_to_result(row: sqlite3.Row) -> SearchResult:
    return SearchResult(
        id=row["id"],
        source_id=row["source_id"],
        source_name=row["source_name"],
        trust_level=row["trust_level"],
        title=row["title"],
        author=row["author"],
        published_at=row["published_at"],
        url=row["url"],
        summary_from_rss=row["summary_from_rss"],
        content_text=row["content_text"],
        extraction_status=row["extraction_status"],
        score=float(row["score"]),
    )


def rebuild_fts(conn: sqlite3.Connection) -> bool:
    if not ensure_fts(conn):
        return False
    conn.execute("delete from articles_fts")
    conn.execute(
        """
        insert into articles_fts (
            article_id, title, author, summary_from_rss, content_text, source_name
        )
        select
            a.id, a.title, a.author, a.summary_from_rss, a.content_text, s.source_name
        from articles a
        join sources s on s.id = a.source_id
        """
    )
    conn.commit()
    return True


def search_articles(
    conn: sqlite3.Connection,
    query: str,
    *,
    since: str | None = None,
    limit: int = 20,
    force_like: bool = False,
) -> list[SearchResult]:
    since_start = _duration_start(since)
    if not force_like and rebuild_fts(conn):
        try:
            return _search_fts(conn, query, since_start, limit)
        except sqlite3.OperationalError:
            pass
    return _search_like(conn, query, since_start, limit)


def _search_fts(
    conn: sqlite3.Connection,
    query: str,
    since_start: str | None,
    limit: int,
) -> list[SearchResult]:
    params: list[object] = [query]
    since_clause = ""
    if since_start:
        since_clause = "and a.published_at >= ?"
        params.append(since_start)
    params.append(limit)
    rows = conn.execute(
        f"""
        select
            a.id,
            a.source_id,
            s.source_name,
            s.trust_level,
            a.title,
            a.author,
            a.published_at,
            a.url,
            a.summary_from_rss,
            a.content_text,
            a.extraction_status,
            (-bm25(articles_fts)) as score,
            case s.trust_level when 'high' then 3 when 'medium' then 2 else 1 end as trust_score,
            case when a.content_text != '' and a.extraction_status = 'success' then 1 else 0 end as has_content
        from articles_fts
        join articles a on a.id = articles_fts.article_id
        join sources s on s.id = a.source_id
        where articles_fts match ?
        {since_clause}
        order by score desc, a.published_at desc, trust_score desc, has_content desc
        limit ?
        """,
        params,
    ).fetchall()
    return [_row_to_result(row) for row in rows]


def _search_like(
    conn: sqlite3.Connection,
    query: str,
    since_start: str | None,
    limit: int,
) -> list[SearchResult]:
    pattern = f"%{query.lower()}%"
    params: list[object] = [pattern] * 5
    since_clause = ""
    if since_start:
        since_clause = "and a.published_at >= ?"
        params.append(since_start)
    params.append(limit)
    rows = conn.execute(
        f"""
        select
            a.id,
            a.source_id,
            s.source_name,
            s.trust_level,
            a.title,
            a.author,
            a.published_at,
            a.url,
            a.summary_from_rss,
            a.content_text,
            a.extraction_status,
            0.0 as score,
            case s.trust_level when 'high' then 3 when 'medium' then 2 else 1 end as trust_score,
            case when a.content_text != '' and a.extraction_status = 'success' then 1 else 0 end as has_content
        from articles a
        join sources s on s.id = a.source_id
        where (
            lower(a.title) like ?
            or lower(a.author) like ?
            or lower(s.source_name) like ?
            or lower(a.summary_from_rss) like ?
            or lower(a.content_text) like ?
        )
        {since_clause}
        order by a.published_at desc, trust_score desc, has_content desc
        limit ?
        """,
        params,
    ).fetchall()
    return [_row_to_result(row) for row in rows]
