from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import feedparser

from rsslab.dedupe import clean_url_text, compute_dedupe_key, content_hash, is_http_url, normalize_url
from rsslab.models import ArticleCandidate, FeedMetadata


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso_z(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _entry_datetime(entry) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime(*parsed[:6], tzinfo=UTC)
    text = entry.get("published") or entry.get("updated")
    if text:
        try:
            parsed_dt = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
        if parsed_dt.tzinfo is None:
            parsed_dt = parsed_dt.replace(tzinfo=UTC)
        return parsed_dt.astimezone(UTC)
    return None


def _summary(entry) -> str:
    return (entry.get("summary") or entry.get("description") or "").strip()


def parse_feed(content: bytes, fetched_at: datetime | None = None) -> tuple[FeedMetadata, list[ArticleCandidate]]:
    fetched = fetched_at or utc_now()
    parsed = feedparser.parse(content)
    feed = parsed.feed
    metadata = FeedMetadata(
        title=(feed.get("title") or "").strip(),
        site_url=clean_url_text(feed.get("link")),
        description=(feed.get("description") or feed.get("subtitle") or "").strip(),
        source_type="atom" if parsed.version.lower().startswith("atom") else "rss",
    )

    articles: list[ArticleCandidate] = []
    missing_time_count = 0
    for entry in parsed.entries:
        url = clean_url_text(entry.get("link"))
        if not is_http_url(url):
            url = ""
        title = (entry.get("title") or "").strip()
        if not title and url:
            title = url
        if not title and not url:
            continue

        published_dt = _entry_datetime(entry)
        if published_dt is None:
            missing_time_count += 1
            published_dt = fetched - timedelta(seconds=missing_time_count)

        summary = _summary(entry)
        canonical_url = normalize_url(url)
        raw_entry_json = json.dumps(dict(entry), ensure_ascii=False, default=str, sort_keys=True)
        published_at = iso_z(published_dt)
        fetched_at_text = iso_z(fetched)
        content_hash_value = content_hash(summary)
        dedupe_key = compute_dedupe_key(
            canonical_url=canonical_url,
            url=url,
            guid=entry.get("id") or entry.get("guid"),
            title=title,
            published_at=published_at,
            summary=summary,
        )
        articles.append(
            ArticleCandidate(
                guid=(entry.get("id") or entry.get("guid") or "").strip(),
                url=url,
                canonical_url=canonical_url,
                title=title,
                author=(entry.get("author") or "").strip(),
                published_at=published_at,
                fetched_at=fetched_at_text,
                summary_from_rss=summary,
                raw_entry_json=raw_entry_json,
                content_hash=content_hash_value,
                dedupe_key=dedupe_key,
            )
        )
    return metadata, articles
