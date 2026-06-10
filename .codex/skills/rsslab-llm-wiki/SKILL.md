---
name: rsslab-llm-wiki
description: Use when ingesting rsslab JSONL evidence bundles into an isolated Markdown/Obsidian-style LLM-Wiki knowledge base, preserving citations, internal wiki links, external source links, collection metadata, article IDs, source trust, extraction status, and content hashes. Do not use for RSS fetching, rsslab database mutation, live web collection, or uncited Wiki generation.
---

# RSSLab LLM-Wiki

## Core Boundary

Use only exported `rsslab` JSONL evidence bundles as input. Do not call `rsslab refresh`, `rsslab extract`, live web search, or LLM-based collection from this skill.

Every fact written to the Wiki must retain a source citation from the evidence row. Wiki pages should also build useful internal links between entities, topics, events, timelines, sources, and claims. Do not invent facts, URLs, publication dates, source names, or cross-Wiki links.

## Required Inputs

- `bundle_path`: path to an `rsslab export` JSONL bundle.
- `wiki_id`: target knowledge base identifier.
- `knowledge_base_root`: directory containing isolated knowledge bases.

Expected layout:

```text
knowledge_bases/
  <wiki_id>/
    raw/
    wiki/
    index.md
    log.md
    manifest.yaml
```

Create missing files only inside the selected `wiki_id` directory. Cross-Wiki writes are forbidden unless the user explicitly names the target Wiki and requested link/write behavior.

## Evidence Contract

Each JSONL row should contain:

- `collection_id`, `article_id`, `content_hash`, `extraction_status`
- article fields: `title`, `url`, `canonical_url`, `published_at`, `fetched_at`, `author`, `summary`, `content`
- `source`: `id`, `name`, `feed_url`, `site_url`, `trust_level`, `language`, `topics`
- `citation`: `title`, `url`, `source_name`, `published_at`, `retrieved_at`

If required citation fields are missing, stop and report the invalid row numbers instead of writing Wiki content.

## Workflow

1. Validate that `bundle_path` exists and is newline-delimited JSON.
2. Validate every row has citation URL, source name, article ID, collection ID, and content hash.
3. Load or create `knowledge_bases/<wiki_id>/manifest.yaml`.
4. Write raw evidence records under `raw/collection-<collection_id>/article-<article_id>.json`.
5. Update Markdown pages under `wiki/` using only facts supported by the bundle.
6. Add citations inline or footnoted using the original URL and source metadata.
7. Mark conflicts explicitly instead of silently resolving inconsistent evidence.
8. Update `index.md` and `log.md` with collection IDs, article IDs, content hashes, and timestamps.

## Link Rules

Generate Wiki pages as navigable Markdown suitable for Obsidian-style browsing.

Use internal links for reusable concepts inside the same `wiki_id`:

- Link important topics: `[[票价争议]]`, `[[签证争议]]`, `[[赛事技术]]`.
- Link entities: `[[FIFA]]`, `[[BBC News]]`, `[[The Guardian]]`, `[[Cristiano Ronaldo]]`.
- Link event pages or timeline anchors when useful: `[[2026 年世界杯时间线]]`.
- Link related pages from summaries, topic pages, entity pages, `index.md`, and timeline pages.
- Keep internal links inside the same `wiki_id`. Do not create cross-Wiki links unless the user explicitly requests them.

Use external links only for evidence citations and source references:

- External links must point to the original `citation.url` or another URL already present in the evidence row.
- Do not replace external citation links with raw JSON paths, collection IDs, or local files.
- When a sentence makes a factual claim, include either a nearby source link or a citation footnote that links to the original article.
- Prefer concise citation text: `[BBC News, 2026-06-07](https://...)`.
- If multiple evidence rows support the same claim, cite the strongest or most direct rows and preserve all relevant URLs in the page notes or source section.

When creating pages, include backlink-friendly sections such as:

```markdown
## Related

- [[票价争议]]
- [[FIFA]]
- [[2026 年世界杯时间线]]
```

## Citation Rules

- Prefer the article URL from `citation.url`.
- Include source name and publication date near the cited claim.
- Preserve `content_hash` in raw evidence and ingest logs.
- Keep `extraction_status`; do not hide fallback summaries or failed extraction status.
- Do not cite a collection as a source. Cite the original article.
- Internal links never replace external citations. `[[FIFA]]` is navigation; `[BBC News, 2026-06-07](https://...)` is evidence.

## Isolation Rules

- One ingest targets exactly one `wiki_id`.
- Do not write outside `knowledge_bases/<wiki_id>/`.
- Do not add cross-Wiki links unless explicitly requested by the user.
- If evidence appears relevant to another Wiki, record that as a note in the current ingest log only when the user asked for cross-Wiki consideration.

## Lint Expectations

Before completion, check:

- Every nontrivial claim has a citation.
- Important recurring entities/topics have internal `[[...]]` links.
- External links used as citations point to evidence-row URLs, preferably `citation.url`.
- Internal links stay within the selected `wiki_id`.
- Raw evidence files include `collection_id`, `article_id`, and `content_hash`.
- Markdown links do not point to another Wiki unless explicitly allowed.
- `manifest.yaml` wiki scope is consistent with the bundle topics.
- Changed content hashes are logged as updates, not silently overwritten.
