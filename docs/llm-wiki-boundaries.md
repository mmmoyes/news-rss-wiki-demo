# RSSLab And LLM-Wiki Boundary Notes

## Purpose

This document records the current boundary decisions for integrating `rsslab` with an LLM-Wiki workflow.

The main goal is to keep `rsslab` as a reproducible evidence-bundle layer, while keeping LLM-based knowledge organization in a separate skill or downstream workflow.

## Core Boundary

`rsslab` is responsible for collecting, normalizing, searching, extracting, selecting, and exporting news evidence.

`rsslab` is not responsible for:

- Calling LLMs.
- Generating Wiki pages.
- Publishing Wiki pages.
- Deciding final knowledge claims.
- Maintaining long-lived Wiki state.

The LLM-Wiki skill is responsible for consuming exported evidence bundles and maintaining Wiki-ready Markdown knowledge pages with citations.

The LLM-Wiki skill is not responsible for:

- Fetching RSS feeds.
- Refreshing sources.
- Extracting article full text.
- Mutating the `rsslab` SQLite database.
- Inventing facts outside the evidence bundle.

## Layering

Recommended flow:

```text
RSS/Atom sources
  -> rsslab refresh
  -> normalized articles in SQLite
  -> rsslab search
  -> rsslab collect
  -> rsslab export JSONL evidence bundle
  -> rsslab-llm-wiki ingest
  -> Wiki Markdown pages
```

Recommended responsibility split:

```text
RSS layer
  source / refresh / parse / normalize / extract
  answers: what articles exist locally?

Collection layer
  search + filters + ranked article ids + policy snapshot
  answers: which articles are selected for this evidence bundle?

LLM-Wiki skill layer
  ingest + fact extraction + conflict marking + Markdown update
  answers: how should the selected evidence update the knowledge base?
```

## Collection Boundary

The collection concept should not be part of the RSS fetch layer.

RSS fetching should not know about a research task, a Wiki scope, or a target knowledge base. It should only know about sources, feed entries, articles, fetch metadata, extraction status, and deduplication.

The collection concept also should not exist only inside the LLM-Wiki skill. If article selection is performed only by the skill at runtime, the selection becomes hard to audit and reproduce.

Therefore, collection belongs to the `rsslab` evidence selection and export layer.

Planned collection artifacts:

- `collection_jobs`: stores query, filters, time window, limit, policy snapshot, status, and timestamps.
- `collection_results`: stores ranked article ids, scores, and selection reasons.
- `rsslab collect`: creates a persistent collection.
- `rsslab export`: exports a collection as a JSONL evidence bundle.

The LLM-Wiki skill should consume a concrete exported bundle, not an implicit live search.

## Article Selection Policy

Each LLM-Wiki ingest should start from an explicit collection policy.

Example:

```yaml
collection_policy:
  query: "AI chip export control"
  since: "30d"
  limit: 50
  languages: ["en", "zh"]
  trust_levels: ["high", "medium"]
  require_full_text: true
  include_existing_articles: true
  dedupe_by: "canonical_url_or_content_hash"
  freshness_mode: "incremental"
```

Policy rules:

- `query` should be supplied by the user or a higher-level workflow, not freely expanded by the LLM.
- `since` should have a default time window for news topics, such as `7d` or `30d`.
- `limit` must always be bounded.
- Low-trust sources should not enter a formal Wiki by default.
- Full text should be preferred for formal Wiki updates.
- Articles with extraction fallback may still be exported, but must keep `extraction_status`.
- Incremental updates and full rebuilds should be explicit modes.

## JSONL Evidence Bundle

A JSONL evidence bundle is the handoff format from `rsslab` to LLM-Wiki.

It is a newline-delimited JSON file where each line represents one selected article. It is intended for machine consumption and reproducible downstream processing.

Each row should include enough information for citation, audit, and rerun:

```json
{
  "article_id": 1,
  "title": "Example title",
  "url": "https://example.com/news/1",
  "canonical_url": "https://example.com/news/1",
  "published_at": "2026-06-01T10:00:00Z",
  "fetched_at": "2026-06-01T10:15:00Z",
  "author": "Reporter Name",
  "summary": "RSS summary",
  "content": "Extracted full text or RSS summary fallback",
  "content_hash": "sha256:...",
  "extraction_status": "success",
  "source": {
    "id": 5,
    "name": "Example News",
    "feed_url": "https://example.com/feed.xml",
    "site_url": "https://example.com",
    "trust_level": "high",
    "language": "en",
    "topics": ["ai", "chips"]
  },
  "citation": {
    "title": "Example title",
    "url": "https://example.com/news/1",
    "source_name": "Example News",
    "published_at": "2026-06-01T10:00:00Z",
    "retrieved_at": "2026-06-01T10:15:00Z"
  }
}
```

Current project status:

- RSS source management exists.
- Feed refresh exists.
- Article normalization exists.
- Local search exists.
- On-demand extraction exists.
- Collection tables and `rsslab collect` exist.
- JSONL evidence bundle export exists through `rsslab export`.
- Project-local LLM-Wiki ingest skill scaffold exists at `.codex/skills/rsslab-llm-wiki/SKILL.md`.

## Knowledge Base Isolation

The project should support multiple isolated knowledge bases.

Recommended layout:

```text
knowledge_bases/
  ai-chips/
    raw/
    wiki/
    index.md
    log.md
    manifest.yaml

  ukraine-war/
    raw/
    wiki/
    index.md
    log.md
    manifest.yaml
```

Each knowledge base should have a `wiki_id` and a manifest.

Example:

```yaml
wiki_id: ai-chips
scope: "AI chips, export controls, semiconductor supply chain"
allowed_topics: ["ai", "chips", "export-control", "semiconductors"]
default_collection_policy:
  since: "30d"
  limit: 50
  trust_levels: ["high", "medium"]
cross_wiki_links: "allowed_with_explicit_reference"
```

Isolation rules:

- Default behavior is no cross-Wiki writes.
- One collection ingest targets one `wiki_id`.
- Cross-Wiki links are allowed only when explicit.
- A single article may be selected into multiple collections, but each target Wiki should record its own ingest.
- Each Wiki maintains its own index, log, conflicts, and source references.

Recommended isolation granularity:

- Prefer long-lived topic or domain Wikis, such as `ai-chips` or `ukraine-war`.
- Treat short research tasks as collection jobs inside an existing Wiki when possible.

## Adapting `karpathy-llm-wiki`

The LLM-Wiki logic can be based on `karpathy-llm-wiki`, but should be adapted into a project-specific `rsslab-llm-wiki` skill.

Reusable concepts:

- `raw/` and `wiki/` separation.
- Ingest updates raw material and Wiki pages together.
- Query reads the Wiki, not all raw evidence.
- Lint checks index, links, source references, conflicts, and stale material.
- `index.md` and `log.md` maintain navigability and history.

Required adaptations:

- Input is an `rsslab` JSONL evidence bundle, not arbitrary URL/file/text.
- Raw metadata must preserve `collection_id`, `article_id`, `content_hash`, `source.trust_level`, and `extraction_status`.
- Every extracted fact must preserve citation URLs.
- Conflicts should be marked instead of silently resolved.
- Lint should check missing citations, changed content hashes, out-of-scope evidence, and newer articles that may supersede older claims.

## Goal Usage

Codex goal should be used as a concise session-level objective, not as a replacement for this document.

The goal should include:

- The final outcome.
- The most important architecture boundaries.
- Non-negotiable restrictions.

The goal should not include:

- Full JSONL schema.
- Full CLI design.
- Every lint rule.
- Every implementation step.

Those details belong in design docs, implementation plans, skill instructions, and Wiki manifests.

## Suggested `/goal` Prompt

```text
Design and implement rsslab as a reproducible evidence-bundle layer for an llm-wiki workflow.

Non-negotiable boundaries:
- RSS/refresh/extract must not call LLMs or generate Wiki pages.
- Collection belongs to rsslab's evidence selection/export layer, not RSS fetching and not temporary llm-wiki state.
- llm-wiki consumes exported JSONL evidence bundles only and must preserve source citations.
- Knowledge bases are isolated by wiki_id; cross-wiki links or writes must be explicit.
- Keep rsslab focused on local SQLite evidence, collection jobs, JSONL export, tests, and docs.

Initial deliverables:
- Define and implement collection_jobs and collection_results.
- Add rsslab collect with explicit query, filters, limit, and optional full-text completion.
- Add rsslab export JSONL following the evidence bundle contract.
- Draft or scaffold rsslab-llm-wiki skill based on the karpathy-llm-wiki workflow, adapted for rsslab JSONL input.
- Verify with tests and a local CLI smoke workflow.
```
