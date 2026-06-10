from rsslab.db import connect, init_db
from rsslab.extractor import extract_article, extract_missing


class StubFetcher:
    def __init__(self, html=b"<html><body><article>Full body</article></body></html>"):
        self.html = html
        self.calls = 0

    def fetch(self, url):
        self.calls += 1
        return self.html


def seed(conn, *, url="https://example.com/a", status="pending"):
    conn.execute(
        """
        insert into sources (
            feed_url, site_url, title, source_name, source_type, topics,
            language, trust_level, created_at, updated_at
        )
        values ('https://example.com/feed.xml', 'https://example.com', 'Example', 'Example',
                'rss', 'world', 'en', 'high', '2026-06-01T00:00:00Z', '2026-06-01T00:00:00Z')
        """
    )
    source_id = conn.execute("select id from sources").fetchone()["id"]
    conn.execute(
        """
        insert into articles (
            source_id, guid, url, canonical_url, title, author, published_at,
            fetched_at, summary_from_rss, raw_entry_json, content_hash,
            dedupe_key, extraction_status, created_at, updated_at
        )
        values (?, 'g1', ?, ?, 'Title', 'Reporter', '2026-06-01T10:00:00Z',
                '2026-06-01T10:10:00Z', 'RSS summary', '{}',
                'sha256:old', 'url:https://example.com/a', ?,
                '2026-06-01T10:10:00Z', '2026-06-01T10:10:00Z')
        """,
        (source_id, url, url, status),
    )
    conn.commit()
    return conn.execute("select id from articles").fetchone()["id"]


def get_article(conn, article_id):
    return conn.execute("select * from articles where id = ?", (article_id,)).fetchone()


def test_extract_article_success_writes_content_text_and_status(tmp_path):
    conn = connect(tmp_path / "rsslab.db")
    init_db(conn)
    article_id = seed(conn)

    result = extract_article(
        conn,
        article_id,
        fetcher=StubFetcher(),
        extractor=lambda html, url: "Extracted full text",
    )

    article = get_article(conn, article_id)
    assert result.status == "success"
    assert article["content_text"] == "Extracted full text"
    assert article["extraction_status"] == "success"
    assert article["content_hash"].startswith("sha256:")


def test_extract_article_failure_falls_back_to_summary(tmp_path):
    conn = connect(tmp_path / "rsslab.db")
    init_db(conn)
    article_id = seed(conn)

    result = extract_article(
        conn,
        article_id,
        fetcher=StubFetcher(),
        extractor=lambda html, url: "",
    )

    article = get_article(conn, article_id)
    assert result.status == "fallback_summary"
    assert article["content_text"] == "RSS summary"
    assert article["summary_from_rss"] == "RSS summary"
    assert article["extraction_error"]


def test_extract_article_without_url_skips_network_and_uses_summary(tmp_path):
    conn = connect(tmp_path / "rsslab.db")
    init_db(conn)
    article_id = seed(conn, url="")
    fetcher = StubFetcher()

    result = extract_article(conn, article_id, fetcher=fetcher)

    article = get_article(conn, article_id)
    assert result.status == "skipped_no_url"
    assert fetcher.calls == 0
    assert article["content_text"] == "RSS summary"


def test_extract_missing_skips_recent_failed_articles(tmp_path):
    conn = connect(tmp_path / "rsslab.db")
    init_db(conn)
    article_id = seed(conn, status="failed")
    conn.execute(
        "update articles set extraction_attempted_at = '2026-06-01T10:00:00Z' where id = ?",
        (article_id,),
    )
    conn.commit()

    results = extract_missing(
        conn,
        limit=10,
        now_text="2026-06-01T10:30:00Z",
        retry_after_seconds=3600,
        fetcher=StubFetcher(),
    )

    assert results == []
