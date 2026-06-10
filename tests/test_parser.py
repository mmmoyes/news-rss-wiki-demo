from datetime import UTC, datetime

from rsslab.parser import parse_feed

from tests.fixtures import RSS_FEED


def test_parse_feed_normalizes_entries_and_drops_unusable_items():
    now = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)

    metadata, articles = parse_feed(RSS_FEED.encode("utf-8"), fetched_at=now)

    assert metadata.title == "Example World"
    assert metadata.site_url == "https://example.com/world"
    assert len(articles) == 2
    assert articles[0].title == "First story"
    assert articles[0].url == "https://example.com/news/1?utm_source=feed&gclid=abc"
    assert articles[0].canonical_url == "https://example.com/news/1"
    assert articles[0].published_at == "2026-06-01T10:00:00Z"
    assert articles[1].title == "https://example.com/news/2?utm_campaign=x"
    assert articles[1].published_at == "2026-06-02T11:59:59Z"
