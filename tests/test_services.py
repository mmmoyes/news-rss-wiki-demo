import sqlite3

from rsslab.db import connect, init_db
from rsslab.services import add_source, list_sources, refresh_all, remove_source

from tests.fixtures import RSS_FEED, RSS_FEED_UPDATED


class StubFetcher:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def fetch(self, url):
        self.urls.append(url)
        return self.responses.pop(0).encode("utf-8")


def rows(conn, query):
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(query).fetchall()]


def test_source_lifecycle_and_refresh_insert_articles_without_duplicates(tmp_path):
    db_path = tmp_path / "rsslab.db"
    conn = connect(db_path)
    init_db(conn)
    fetcher = StubFetcher([RSS_FEED, RSS_FEED, RSS_FEED, RSS_FEED_UPDATED])

    source = add_source(
        conn,
        "https://example.com/rss.xml",
        topic="world",
        language="en",
        trust_level="high",
        fetcher=fetcher,
    )

    assert source.id == 1
    assert list_sources(conn)[0].title == "Example World"

    first = refresh_all(conn, fetcher=fetcher)
    assert first.inserted == 2
    assert first.updated == 0
    assert len(rows(conn, "select * from articles")) == 2

    second = refresh_all(conn, fetcher=fetcher)
    assert second.inserted == 0
    assert second.updated == 2
    assert len(rows(conn, "select * from articles")) == 2

    conn.execute("update articles set is_read = 1, is_starred = 1 where guid = 'article-1'")
    conn.commit()

    third = refresh_all(conn, fetcher=fetcher)
    assert third.inserted == 0
    assert third.updated == 1
    article = rows(conn, "select * from articles where guid = 'article-1'")[0]
    assert article["title"] == "First story updated"
    assert article["summary_from_rss"] == "First summary updated"
    assert article["is_read"] == 1
    assert article["is_starred"] == 1

    remove_source(conn, source.id)
    assert list_sources(conn) == []
