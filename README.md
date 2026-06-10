# rsslab

[中文介绍](README.zh-CN.md)

`rsslab` is a Python 3.11+ CLI for the RSS news collection plan. It manages RSS/Atom sources, refreshes feeds, normalizes article metadata, and stores sources and articles in local SQLite.
Phase 2 adds local article search and on-demand full-text extraction. Phase 3 adds reproducible collection jobs and JSONL evidence-bundle export for downstream LLM-Wiki workflows.

It is not an RSS reader, GUI app, daemon, cloud sync service, multi-user system, LLM summarizer, or Wiki generator. RSS refresh and extraction do not call LLMs.

## Install

From the project root:

```bash
python -m pip install -e .[test]
```

Run tests:

```bash
python -m pytest
```

## Database Location

By default the SQLite database is stored at:

```text
.rsslab/rsslab.db
```

Set `RSSLAB_DB` to use a different file:

```bash
$env:RSSLAB_DB=".rsslab\dev.db"
```

## Implemented Commands

```bash
rsslab source add <feed-url> --topic <topic> --language <lang> --trust-level <level>
rsslab source list
rsslab source remove <source-id>

rsslab refresh all
rsslab refresh source <source-id>

rsslab search <query> --since 7d --limit 20

rsslab extract article <article-id>
rsslab extract missing --limit 100

rsslab collect <query> --since 30d --language en --trust-level high --topic chips --limit 50
rsslab collect <query> --limit 20 --complete-full-text
rsslab export <collection-id> --output evidence.jsonl
```

## Examples

Add BBC World:

```bash
rsslab source add https://feeds.bbci.co.uk/news/world/rss.xml --topic world --language en --trust-level high
```

Refresh all sources:

```bash
rsslab refresh all
```

List sources:

```bash
rsslab source list
```

Refresh one source:

```bash
rsslab refresh source 1
```

Search local articles:

```bash
rsslab search "Ukraine" --limit 10
```

Extract full text for one article:

```bash
rsslab extract article 1
```

Extract missing full text in batches:

```bash
rsslab extract missing --limit 10
```

Create a reproducible collection job:

```bash
rsslab collect "AI chip export control" --since 30d --language en --trust-level high --topic chips --limit 50
```

Export that collection as a JSONL evidence bundle:

```bash
rsslab export 1 --output evidence/ai-chips.jsonl
```

## Phase 1 Complete

- Python package and Typer CLI project structure.
- SQLite schema for `sources` and `articles`.
- Source add/list/remove.
- RSS/Atom fetching with `httpx`.
- RSS/Atom parsing with `feedparser`.
- Article normalization for title, URL, author, published time, summary, raw entry JSON, content hash, and dedupe key.
- URL normalization that removes common tracking parameters.
- Feed entry repair for missing titles, missing published times, and control characters in URLs.
- Duplicate refresh protection through `dedupe_key`.
- Existing article updates preserve `is_read` and `is_starred`.

## Phase 2 Complete

- SQLite migration for `content_text`, `content_html`, `raw_html_path`, `extraction_status`, `extraction_error`, and `extraction_attempted_at`.
- Optional `articles_fts` virtual table using SQLite FTS5.
- Automatic LIKE search fallback when FTS5 is unavailable.
- Local search over title, author, source name, RSS summary, and extracted `content_text`.
- Search ordering considers FTS relevance, published time, source trust level, and whether full text exists.
- On-demand full-text extraction with `trafilatura`.
- Extraction fallback to RSS summary when no URL, fetch failure, or empty extracted content occurs.
- Extraction status values: `pending`, `success`, `fallback_summary`, `failed`, `skipped_no_url`.
- Short retry suppression for recently failed articles in `extract missing`.

## Phase 3 Complete

- SQLite tables for `collection_jobs` and `collection_results`.
- `rsslab collect` with explicit query, time window, language, trust-level, topic, and limit filters.
- Optional `--complete-full-text` collection mode that reuses the existing extractor only when explicitly requested.
- Persistent collection policy snapshots for audit and rerun.
- `rsslab export` JSONL evidence bundles with article metadata, source metadata, content hash, extraction status, and citation fields.
- Project-local `.codex/skills/rsslab-llm-wiki` scaffold for downstream JSONL-only Wiki ingestion.

## Evidence Bundle Contract

Each exported JSONL line represents one selected article and includes:

- `collection_id`, `article_id`, `rank`, `score`
- title, URL, canonical URL, author, publication time, fetched time, summary, content, content hash, extraction status
- source metadata: source ID, source name, feed URL, site URL, trust level, language, topics
- citation metadata: title, URL, source name, publication time, retrieved time

The downstream LLM-Wiki workflow must consume exported JSONL bundles only and preserve source citations. Knowledge bases are isolated by `wiki_id`; cross-Wiki writes or links must be explicit.

## Not Implemented Yet

Later items remain intentionally out of scope here:

- `refresh due`.
- ETag or Last-Modified conditional requests.
- Daemon/background scheduler.
- LLM summarization or Wiki generation.
