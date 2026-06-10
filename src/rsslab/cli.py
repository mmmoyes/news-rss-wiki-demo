from __future__ import annotations

import typer

from rsslab.collections import collect_articles, export_collection_jsonl
from rsslab.db import DEFAULT_DB_PATH, connect, init_db
from rsslab.extractor import extract_article, extract_missing
from rsslab.search import search_articles
from rsslab.services import add_source, list_sources, refresh_all, refresh_source, remove_source

app = typer.Typer(help="RSS/Atom news collection CLI with local SQLite storage and search.")
source_app = typer.Typer(help="Manage RSS/Atom sources.")
refresh_app = typer.Typer(help="Refresh RSS/Atom sources.")
extract_app = typer.Typer(help="Extract article full text.")
app.add_typer(source_app, name="source")
app.add_typer(refresh_app, name="refresh")
app.add_typer(extract_app, name="extract")


def _conn():
    conn = connect(DEFAULT_DB_PATH)
    init_db(conn)
    return conn


@source_app.command("add")
def source_add(
    feed_url: str,
    topic: str = typer.Option(..., "--topic"),
    language: str = typer.Option(..., "--language"),
    trust_level: str = typer.Option(..., "--trust-level"),
) -> None:
    conn = _conn()
    source = add_source(conn, feed_url, topic=topic, language=language, trust_level=trust_level)
    typer.echo(f"Added source {source.id}: {source.title or source.feed_url}")


@source_app.command("list")
def source_list() -> None:
    conn = _conn()
    sources = list_sources(conn)
    if not sources:
        typer.echo("No sources.")
        return
    typer.echo("id\tlanguage\ttrust\ttopics\ttitle\tfeed_url")
    for source in sources:
        typer.echo(
            f"{source.id}\t{source.language}\t{source.trust_level}\t"
            f"{source.topics}\t{source.title}\t{source.feed_url}"
        )


@source_app.command("remove")
def source_remove(source_id: int) -> None:
    conn = _conn()
    remove_source(conn, source_id)
    typer.echo(f"Removed source {source_id}.")


@refresh_app.command("all")
def refresh_all_command() -> None:
    conn = _conn()
    result = refresh_all(conn)
    typer.echo(f"Refresh complete: inserted={result.inserted} updated={result.updated}")


@refresh_app.command("source")
def refresh_source_command(source_id: int) -> None:
    conn = _conn()
    result = refresh_source(conn, source_id)
    typer.echo(f"Refresh source {source_id}: inserted={result.inserted} updated={result.updated}")


@app.command("search")
def search_command(
    query: str,
    since: str | None = typer.Option(None, "--since"),
    limit: int = typer.Option(20, "--limit"),
) -> None:
    conn = _conn()
    results = search_articles(conn, query, since=since, limit=limit)
    if not results:
        typer.echo("No articles found.")
        return
    typer.echo("id\tpublished_at\tsource\tstatus\ttitle\turl")
    for result in results:
        typer.echo(
            f"{result.id}\t{result.published_at}\t{result.source_name}\t"
            f"{result.extraction_status}\t{result.title}\t{result.url}"
        )


@app.command("collect")
def collect_command(
    query: str,
    since: str | None = typer.Option(None, "--since"),
    language: list[str] | None = typer.Option(None, "--language"),
    trust_level: list[str] | None = typer.Option(None, "--trust-level"),
    topic: list[str] | None = typer.Option(None, "--topic"),
    limit: int = typer.Option(20, "--limit", min=1),
    complete_full_text: bool = typer.Option(False, "--complete-full-text"),
) -> None:
    conn = _conn()
    job = collect_articles(
        conn,
        query=query,
        since=since,
        languages=language,
        trust_levels=trust_level,
        topics=topic,
        limit=limit,
        complete_full_text=complete_full_text,
    )
    typer.echo(f"Collection {job.id} complete: results={job.result_count}")


@app.command("export")
def export_command(
    collection_id: int,
    output: str = typer.Option(..., "--output", "-o"),
) -> None:
    conn = _conn()
    count = export_collection_jsonl(conn, collection_id, output)
    typer.echo(f"Exported {count} evidence records to {output}")


@extract_app.command("article")
def extract_article_command(article_id: int) -> None:
    conn = _conn()
    result = extract_article(conn, article_id)
    typer.echo(
        f"Extract article {article_id}: status={result.status} "
        f"content_length={len(result.content_text)}"
    )


@extract_app.command("missing")
def extract_missing_command(limit: int = typer.Option(100, "--limit")) -> None:
    conn = _conn()
    results = extract_missing(conn, limit=limit)
    typer.echo(f"Extracted {len(results)} articles.")
    for result in results:
        typer.echo(
            f"{result.article_id}\t{result.status}\tcontent_length={len(result.content_text)}"
        )


if __name__ == "__main__":
    app()
