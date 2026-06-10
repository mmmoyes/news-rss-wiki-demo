from rsslab.db import connect, init_db
from rsslab.search import search_articles


def seed_article(conn, *, title="Policy update", summary="RSS summary", content="", trust="medium"):
    conn.execute(
        """
        insert into sources (
            feed_url, site_url, title, source_name, source_type, topics,
            language, trust_level, created_at, updated_at
        )
        values ('https://example.com/feed.xml', 'https://example.com', 'Example', 'Example',
                'rss', 'world', 'en', ?, '2026-06-01T00:00:00Z', '2026-06-01T00:00:00Z')
        """,
        (trust,),
    )
    source_id = conn.execute("select id from sources").fetchone()["id"]
    conn.execute(
        """
        insert into articles (
            source_id, guid, url, canonical_url, title, author, published_at,
            fetched_at, summary_from_rss, raw_entry_json, content_text,
            content_hash, dedupe_key, extraction_status, created_at, updated_at
        )
        values (?, 'g1', 'https://example.com/a', 'https://example.com/a', ?, 'Reporter',
                '2026-06-01T10:00:00Z', '2026-06-01T10:10:00Z', ?, '{}', ?,
                'sha256:x', 'url:https://example.com/a', 'pending',
                '2026-06-01T10:10:00Z', '2026-06-01T10:10:00Z')
        """,
        (source_id, title, summary, content),
    )
    conn.commit()


def test_search_uses_fts_when_available(tmp_path):
    conn = connect(tmp_path / "rsslab.db")
    init_db(conn)
    seed_article(conn, title="Ukraine latest", summary="No match")

    results = search_articles(conn, "Ukraine", limit=10)

    assert len(results) == 1
    assert results[0].title == "Ukraine latest"


def test_search_falls_back_to_like_when_fts_unavailable(tmp_path):
    conn = connect(tmp_path / "rsslab.db")
    init_db(conn)
    seed_article(conn, title="No match", summary="Ukraine update")

    results = search_articles(conn, "Ukraine", limit=10, force_like=True)

    assert len(results) == 1
    assert results[0].summary_from_rss == "Ukraine update"


def test_search_covers_extracted_content_text(tmp_path):
    conn = connect(tmp_path / "rsslab.db")
    init_db(conn)
    seed_article(conn, title="No match", summary="No match", content="Semiconductor export controls")

    results = search_articles(conn, "Semiconductor", limit=10)

    assert len(results) == 1
    assert results[0].content_text == "Semiconductor export controls"
