from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from rsslab.extractor import extract_article
from rsslab.models import CollectionJob
from rsslab.parser import iso_z
from rsslab.search import search_articles


def _now() -> str:
    return iso_z(datetime.now(UTC))


def _as_list(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    return [value.strip() for value in values if value and value.strip()]


def _split_topics(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _matches_filters(
    row: sqlite3.Row,
    *,
    languages: list[str],
    trust_levels: list[str],
    topics: list[str],
) -> bool:
    if languages and row["language"] not in languages:
        return False
    if trust_levels and row["trust_level"] not in trust_levels:
        return False
    if topics:
        source_topics = set(_split_topics(row["topics"]))
        if not source_topics.intersection(topics):
            return False
    return True


def _article_row(conn: sqlite3.Connection, article_id: int) -> sqlite3.Row:
    row = conn.execute(
        """
        select
            a.*,
            s.feed_url,
            s.site_url,
            s.source_name,
            s.trust_level,
            s.language,
            s.topics
        from articles a
        join sources s on s.id = a.source_id
        where a.id = ?
        """,
        (article_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"article not found: {article_id}")
    return row


def _job_from_row(row: sqlite3.Row) -> CollectionJob:
    return CollectionJob(
        id=row["id"],
        query=row["query"],
        since=row["since"],
        limit=row["limit_count"],
        complete_full_text=bool(row["complete_full_text"]),
        result_count=row["result_count"],
        status=row["status"],
    )


def collect_articles(
    conn: sqlite3.Connection,
    *,
    query: str,
    since: str | None = None,
    languages: Iterable[str] | None = None,
    trust_levels: Iterable[str] | None = None,
    topics: Iterable[str] | None = None,
    limit: int = 20,
    complete_full_text: bool = False,
    fetcher=None,
    extractor=None,
    force_like: bool = False,
) -> CollectionJob:
    if not query.strip():
        raise ValueError("query is required")
    if limit < 1:
        raise ValueError("limit must be greater than zero")

    language_list = _as_list(languages)
    trust_level_list = _as_list(trust_levels)
    topic_list = _as_list(topics)
    policy = {
        "query": query,
        "since": since,
        "languages": language_list,
        "trust_levels": trust_level_list,
        "topics": topic_list,
        "limit": limit,
        "complete_full_text": complete_full_text,
    }
    now = _now()
    cursor = conn.execute(
        """
        insert into collection_jobs (
            query, since, languages_json, trust_levels_json, topics_json,
            limit_count, complete_full_text, policy_json, status, result_count,
            created_at, updated_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, 'running', 0, ?, ?)
        """,
        (
            query,
            since,
            json.dumps(language_list),
            json.dumps(trust_level_list),
            json.dumps(topic_list),
            limit,
            int(complete_full_text),
            json.dumps(policy, sort_keys=True),
            now,
            now,
        ),
    )
    job_id = int(cursor.lastrowid)

    search_limit = max(limit * 5, limit)
    candidates = search_articles(conn, query, since=since, limit=search_limit, force_like=force_like)
    selected: list[tuple[sqlite3.Row, float]] = []
    for candidate in candidates:
        row = _article_row(conn, candidate.id)
        if not _matches_filters(row, languages=language_list, trust_levels=trust_level_list, topics=topic_list):
            continue
        if complete_full_text and (not row["content_text"] or row["extraction_status"] != "success"):
            extract_article(conn, row["id"], fetcher=fetcher, extractor=extractor)
            row = _article_row(conn, candidate.id)
        selected.append((row, candidate.score))
        if len(selected) >= limit:
            break

    for index, (row, score) in enumerate(selected, start=1):
        conn.execute(
            """
            insert into collection_results (
                collection_job_id, article_id, rank, score, selection_reason,
                content_hash_at_collection, extraction_status_at_collection,
                created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                row["id"],
                index,
                score,
                "matched query and filters",
                row["content_hash"],
                row["extraction_status"],
                now,
            ),
        )
    conn.execute(
        """
        update collection_jobs
        set status = 'completed', result_count = ?, updated_at = ?
        where id = ?
        """,
        (len(selected), _now(), job_id),
    )
    conn.commit()
    row = conn.execute("select * from collection_jobs where id = ?", (job_id,)).fetchone()
    return _job_from_row(row)


def get_collection_job(conn: sqlite3.Connection, collection_id: int) -> CollectionJob:
    row = conn.execute("select * from collection_jobs where id = ?", (collection_id,)).fetchone()
    if row is None:
        raise ValueError(f"collection not found: {collection_id}")
    return _job_from_row(row)


def _export_row(row: sqlite3.Row) -> dict:
    content = row["content_text"] or row["summary_from_rss"]
    return {
        "collection_id": row["collection_job_id"],
        "article_id": row["article_id"],
        "rank": row["rank"],
        "score": row["score"],
        "title": row["title"],
        "url": row["url"],
        "canonical_url": row["canonical_url"],
        "published_at": row["published_at"],
        "fetched_at": row["fetched_at"],
        "author": row["author"],
        "summary": row["summary_from_rss"],
        "content": content,
        "content_hash": row["content_hash"],
        "extraction_status": row["extraction_status"],
        "source": {
            "id": row["source_id"],
            "name": row["source_name"],
            "feed_url": row["feed_url"],
            "site_url": row["site_url"],
            "trust_level": row["trust_level"],
            "language": row["language"],
            "topics": _split_topics(row["topics"]),
        },
        "citation": {
            "title": row["title"],
            "url": row["url"],
            "source_name": row["source_name"],
            "published_at": row["published_at"],
            "retrieved_at": row["fetched_at"],
        },
    }


def export_collection_jsonl(
    conn: sqlite3.Connection,
    collection_id: int,
    output_path: str | Path,
) -> int:
    get_collection_job(conn, collection_id)
    rows = conn.execute(
        """
        select
            cr.collection_job_id,
            cr.article_id,
            cr.rank,
            cr.score,
            a.source_id,
            a.title,
            a.url,
            a.canonical_url,
            a.published_at,
            a.fetched_at,
            a.author,
            a.summary_from_rss,
            a.content_text,
            a.content_hash,
            a.extraction_status,
            s.source_name,
            s.feed_url,
            s.site_url,
            s.trust_level,
            s.language,
            s.topics
        from collection_results cr
        join articles a on a.id = cr.article_id
        join sources s on s.id = a.source_id
        where cr.collection_job_id = ?
        order by cr.rank
        """,
        (collection_id,),
    ).fetchall()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(_export_row(row), ensure_ascii=False, sort_keys=True) + "\n")
    return len(rows)
