from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeedMetadata:
    title: str
    site_url: str
    description: str
    source_type: str


@dataclass(frozen=True)
class ArticleCandidate:
    guid: str
    url: str
    canonical_url: str
    title: str
    author: str
    published_at: str
    fetched_at: str
    summary_from_rss: str
    raw_entry_json: str
    content_hash: str
    dedupe_key: str


@dataclass(frozen=True)
class Source:
    id: int
    feed_url: str
    site_url: str
    title: str
    description: str
    source_name: str
    source_type: str
    topics: str
    language: str
    trust_level: str


@dataclass(frozen=True)
class RefreshResult:
    source_id: int | None
    inserted: int
    updated: int
    errors: int = 0


@dataclass(frozen=True)
class CollectionJob:
    id: int
    query: str
    since: str | None
    limit: int
    complete_full_text: bool
    result_count: int
    status: str
