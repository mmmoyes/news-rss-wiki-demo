import json

from rsslab.collections import collect_articles, export_collection_jsonl
from rsslab.db import connect, init_db


class StubFetcher:
    def fetch(self, url):
        return b"<html><body><article>Full article body</article></body></html>"


def seed_article(
    conn,
    *,
    title="AI chip export control",
    summary="RSS summary about AI chips",
    content="",
    language="en",
    trust="high",
    topics="ai,chips",
    status="pending",
):
    conn.execute(
        """
        insert into sources (
            feed_url, site_url, title, source_name, source_type, topics,
            language, trust_level, created_at, updated_at
        )
        values ('https://example.com/feed.xml', 'https://example.com', 'Example News',
                'Example News', 'rss', ?, ?, ?, '2026-06-01T00:00:00Z',
                '2026-06-01T00:00:00Z')
        """,
        (topics, language, trust),
    )
    source_id = conn.execute("select id from sources").fetchone()["id"]
    conn.execute(
        """
        insert into articles (
            source_id, guid, url, canonical_url, title, author, published_at,
            fetched_at, summary_from_rss, raw_entry_json, content_text,
            content_hash, dedupe_key, extraction_status, created_at, updated_at
        )
        values (?, 'g1', 'https://example.com/a', 'https://example.com/a', ?,
                'Reporter', '2026-06-01T10:00:00Z', '2026-06-01T10:10:00Z',
                ?, '{}', ?, 'sha256:old', 'url:https://example.com/a', ?,
                '2026-06-01T10:10:00Z', '2026-06-01T10:10:00Z')
        """,
        (source_id, title, summary, content, status),
    )
    conn.commit()
    return conn.execute("select id from articles").fetchone()["id"]


def test_collect_articles_persists_policy_and_ranked_results(tmp_path):
    conn = connect(tmp_path / "rsslab.db")
    init_db(conn)
    article_id = seed_article(conn)

    job = collect_articles(
        conn,
        query="AI chip",
        since="30d",
        languages=["en"],
        trust_levels=["high"],
        topics=["chips"],
        limit=10,
        force_like=True,
    )

    job_row = conn.execute("select * from collection_jobs where id = ?", (job.id,)).fetchone()
    results = conn.execute("select * from collection_results where collection_job_id = ?", (job.id,)).fetchall()
    policy = json.loads(job_row["policy_json"])

    assert job.result_count == 1
    assert job_row["query"] == "AI chip"
    assert policy["languages"] == ["en"]
    assert policy["trust_levels"] == ["high"]
    assert policy["topics"] == ["chips"]
    assert results[0]["article_id"] == article_id
    assert results[0]["rank"] == 1
    assert results[0]["selection_reason"] == "matched query and filters"


def test_collect_articles_can_complete_full_text_before_selection(tmp_path):
    conn = connect(tmp_path / "rsslab.db")
    init_db(conn)
    article_id = seed_article(conn)

    collect_articles(
        conn,
        query="AI chip",
        limit=5,
        complete_full_text=True,
        fetcher=StubFetcher(),
        extractor=lambda html, url: "Extracted full article body",
        force_like=True,
    )

    row = conn.execute("select * from articles where id = ?", (article_id,)).fetchone()
    result = conn.execute("select * from collection_results").fetchone()

    assert row["content_text"] == "Extracted full article body"
    assert row["extraction_status"] == "success"
    assert result["extraction_status_at_collection"] == "success"


def test_export_collection_jsonl_preserves_article_citation_contract(tmp_path):
    conn = connect(tmp_path / "rsslab.db")
    init_db(conn)
    article_id = seed_article(conn, content="Full text", status="success")
    job = collect_articles(conn, query="AI chip", limit=5, force_like=True)
    output_path = tmp_path / "bundle.jsonl"

    count = export_collection_jsonl(conn, job.id, output_path)

    lines = output_path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    assert count == 1
    assert record["collection_id"] == job.id
    assert record["article_id"] == article_id
    assert record["content"] == "Full text"
    assert record["source"]["trust_level"] == "high"
    assert record["source"]["topics"] == ["ai", "chips"]
    assert record["citation"] == {
        "title": "AI chip export control",
        "url": "https://example.com/a",
        "source_name": "Example News",
        "published_at": "2026-06-01T10:00:00Z",
        "retrieved_at": "2026-06-01T10:10:00Z",
    }
