from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

import trafilatura

from rsslab.dedupe import content_hash
from rsslab.rss import HttpFetcher


@dataclass(frozen=True)
class ExtractionResult:
    article_id: int
    status: str
    content_text: str
    error: str = ""


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _default_extract(html: bytes, url: str) -> str:
    extracted = trafilatura.extract(html, url=url, include_comments=False, include_tables=False)
    return (extracted or "").strip()


def _write_extraction(
    conn: sqlite3.Connection,
    article_id: int,
    *,
    content_text: str,
    status: str,
    error: str,
    html: bytes | None = None,
    attempted_at: str | None = None,
) -> None:
    html_text = ""
    if html is not None:
        html_text = html.decode("utf-8", errors="replace")
    now_text = attempted_at or _iso(_now())
    conn.execute(
        """
        update articles set
            content_text = ?,
            content_html = ?,
            content_hash = ?,
            extraction_status = ?,
            extraction_error = ?,
            extraction_attempted_at = ?,
            updated_at = ?
        where id = ?
        """,
        (
            content_text,
            html_text,
            content_hash(content_text),
            status,
            error,
            now_text,
            now_text,
            article_id,
        ),
    )
    conn.commit()


def extract_article(
    conn: sqlite3.Connection,
    article_id: int,
    *,
    fetcher=None,
    extractor=None,
    now_text: str | None = None,
) -> ExtractionResult:
    row = conn.execute("select * from articles where id = ?", (article_id,)).fetchone()
    if row is None:
        raise ValueError(f"article not found: {article_id}")

    summary = row["summary_from_rss"] or ""
    url = row["url"] or ""
    if not url:
        _write_extraction(
            conn,
            article_id,
            content_text=summary,
            status="skipped_no_url",
            error="article has no URL; used RSS summary",
            attempted_at=now_text,
        )
        return ExtractionResult(article_id=article_id, status="skipped_no_url", content_text=summary)

    fetcher = fetcher or HttpFetcher()
    extract_fn = extractor or _default_extract
    html: bytes | None = None
    try:
        html = fetcher.fetch(url)
        extracted = (extract_fn(html, url) or "").strip()
        if extracted:
            _write_extraction(
                conn,
                article_id,
                content_text=extracted,
                status="success",
                error="",
                html=html,
                attempted_at=now_text,
            )
            return ExtractionResult(article_id=article_id, status="success", content_text=extracted)
        error = "trafilatura returned empty content; used RSS summary"
        _write_extraction(
            conn,
            article_id,
            content_text=summary,
            status="fallback_summary",
            error=error,
            html=html,
            attempted_at=now_text,
        )
        return ExtractionResult(article_id=article_id, status="fallback_summary", content_text=summary, error=error)
    except Exception as exc:
        error = str(exc)
        _write_extraction(
            conn,
            article_id,
            content_text=summary,
            status="failed",
            error=error,
            html=html,
            attempted_at=now_text,
        )
        return ExtractionResult(article_id=article_id, status="failed", content_text=summary, error=error)


def _eligible_missing_rows(
    conn: sqlite3.Connection,
    *,
    limit: int,
    now_text: str,
    retry_after_seconds: int,
) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        select *
        from articles
        where content_text = ''
           or extraction_status in ('pending', 'failed', 'fallback_summary', 'skipped_no_url')
        order by published_at desc
        """
    ).fetchall()
    now_dt = datetime.fromisoformat(now_text.replace("Z", "+00:00"))
    eligible: list[sqlite3.Row] = []
    for row in rows:
        if row["extraction_status"] == "failed" and row["extraction_attempted_at"]:
            attempted = datetime.fromisoformat(row["extraction_attempted_at"].replace("Z", "+00:00"))
            if (now_dt - attempted).total_seconds() < retry_after_seconds:
                continue
        eligible.append(row)
        if len(eligible) >= limit:
            break
    return eligible


def extract_missing(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
    fetcher=None,
    extractor=None,
    now_text: str | None = None,
    retry_after_seconds: int = 3600,
) -> list[ExtractionResult]:
    now_value = now_text or _iso(_now())
    rows = _eligible_missing_rows(
        conn,
        limit=limit,
        now_text=now_value,
        retry_after_seconds=retry_after_seconds,
    )
    return [
        extract_article(conn, row["id"], fetcher=fetcher, extractor=extractor, now_text=now_value)
        for row in rows
    ]
