from typer.testing import CliRunner

import rsslab.cli as cli
from rsslab.db import connect, init_db


runner = CliRunner()


def seed_article(db_path):
    conn = connect(db_path)
    init_db(conn)
    conn.execute(
        """
        insert into sources (
            feed_url, site_url, title, source_name, source_type, topics,
            language, trust_level, created_at, updated_at
        )
        values ('https://example.com/feed.xml', 'https://example.com', 'Example News',
                'Example News', 'rss', 'ai,chips', 'en', 'high',
                '2026-06-01T00:00:00Z', '2026-06-01T00:00:00Z')
        """
    )
    source_id = conn.execute("select id from sources").fetchone()["id"]
    conn.execute(
        """
        insert into articles (
            source_id, guid, url, canonical_url, title, author, published_at,
            fetched_at, summary_from_rss, raw_entry_json, content_text,
            content_hash, dedupe_key, extraction_status, created_at, updated_at
        )
        values (?, 'g1', 'https://example.com/a', 'https://example.com/a',
                'AI chip export control', 'Reporter', '2026-06-01T10:00:00Z',
                '2026-06-01T10:10:00Z', 'RSS summary', '{}', 'Full text',
                'sha256:x', 'url:https://example.com/a', 'success',
                '2026-06-01T10:10:00Z', '2026-06-01T10:10:00Z')
        """,
        (source_id,),
    )
    conn.commit()


def test_source_list_uses_configured_database(tmp_path, monkeypatch):
    db_path = tmp_path / "rsslab.db"
    monkeypatch.setattr(cli, "DEFAULT_DB_PATH", db_path)

    result = runner.invoke(cli.app, ["source", "list"])

    assert result.exit_code == 0
    assert "No sources." in result.stdout


def test_refresh_all_command_reports_empty_refresh(tmp_path, monkeypatch):
    db_path = tmp_path / "rsslab.db"
    monkeypatch.setattr(cli, "DEFAULT_DB_PATH", db_path)

    result = runner.invoke(cli.app, ["refresh", "all"])

    assert result.exit_code == 0
    assert "inserted=0 updated=0" in result.stdout


def test_search_command_runs_against_empty_database(tmp_path, monkeypatch):
    db_path = tmp_path / "rsslab.db"
    monkeypatch.setattr(cli, "DEFAULT_DB_PATH", db_path)

    result = runner.invoke(cli.app, ["search", "Ukraine", "--limit", "10"])

    assert result.exit_code == 0
    assert "No articles found." in result.stdout


def test_extract_missing_command_runs_against_empty_database(tmp_path, monkeypatch):
    db_path = tmp_path / "rsslab.db"
    monkeypatch.setattr(cli, "DEFAULT_DB_PATH", db_path)

    result = runner.invoke(cli.app, ["extract", "missing", "--limit", "10"])

    assert result.exit_code == 0
    assert "Extracted 0 articles." in result.stdout


def test_collect_command_creates_collection_job(tmp_path, monkeypatch):
    db_path = tmp_path / "rsslab.db"
    seed_article(db_path)
    monkeypatch.setattr(cli, "DEFAULT_DB_PATH", db_path)

    result = runner.invoke(
        cli.app,
        [
            "collect",
            "AI chip",
            "--since",
            "30d",
            "--language",
            "en",
            "--trust-level",
            "high",
            "--topic",
            "chips",
            "--limit",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert "Collection 1 complete: results=1" in result.stdout


def test_export_command_writes_collection_jsonl(tmp_path, monkeypatch):
    db_path = tmp_path / "rsslab.db"
    output_path = tmp_path / "bundle.jsonl"
    seed_article(db_path)
    monkeypatch.setattr(cli, "DEFAULT_DB_PATH", db_path)
    collect_result = runner.invoke(cli.app, ["collect", "AI chip", "--limit", "5"])
    assert collect_result.exit_code == 0

    result = runner.invoke(cli.app, ["export", "1", "--output", str(output_path)])

    assert result.exit_code == 0
    assert "Exported 1 evidence records" in result.stdout
    assert output_path.read_text(encoding="utf-8").count("\n") == 1
