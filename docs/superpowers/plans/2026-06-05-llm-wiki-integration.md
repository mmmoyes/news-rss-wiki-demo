# LLM-WIKI Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前 `rsslab` 从“RSS/Atom 采集 + 本地检索 + 正文提取”扩展为 LLM-WIKI 流程的可复现证据材料输入层。

**Architecture:** `rsslab` 继续只负责采集、检索、正文提取、collection job 和 JSONL evidence bundle 导出；LLM-WIKI 生成逻辑放到独立 skill 或后续消费层中。核心边界是：SQLite 保存可追溯新闻证据，JSONL 作为跨流程契约，LLM-WIKI skill 只消费导出的 JSONL，不直接读写 `rsslab` SQLite。

**Tech Stack:** Python 3.11+、Typer、sqlite3、SQLite FTS5/LIKE、httpx、feedparser、trafilatura、pytest、Codex `skill-creator`、可选 OpenAI API/Responses API。

---

## Current State

当前项目已完成 Phase 1 和 Phase 2：

- `rsslab source add/list/remove`
- `rsslab refresh all/source`
- `rsslab search <query> --since 7d --limit 20`
- `rsslab extract article <article-id>`
- `rsslab extract missing --limit 100`
- SQLite 表：`sources`、`articles`、`articles_fts`
- 已有文章字段包括 RSS 摘要、正文、正文提取状态、正文哈希、来源、发布时间、抓取时间、去重键。

当前尚未实现：

- `collection_jobs`
- `collection_results`
- JSONL export
- `refresh due`
- ETag/Last-Modified
- LLM-WIKI skill
- Wiki 页面生成

## Recommended Boundary

推荐数据流：

```text
RSS/Atom sources
  -> rsslab refresh
  -> normalized articles in SQLite
  -> rsslab search
  -> rsslab extract / ensure full text
  -> collection_jobs + collection_results
  -> rsslab export JSONL evidence bundle
  -> rsslab-llm-wiki skill
  -> Markdown / structured Wiki pages
```

边界原则：

- `rsslab` 不直接调用 LLM。
- `rsslab` 不生成 Wiki 页面。
- `rsslab` 只导出结构化、可复现、可审计的 evidence bundle。
- LLM-WIKI skill 只消费 JSONL，不直接访问 SQLite。
- 后续更换模型、Wiki 格式或生成策略时，不影响采集层。

## Existing Skills To Reuse

### `skill-creator`

最适合直接使用。建议创建项目专用 skill：

```text
rsslab-llm-wiki
```

用途：

- 固化 JSONL 输入契约。
- 固化引用规则。
- 固化事实抽取规则。
- 固化冲突处理规则。
- 固化 Wiki 页面结构。
- 固化 Markdown/JSON 输出格式。

### `openai-docs`

用于后续接 OpenAI API 时查官方文档，尤其是：

- 选择模型。
- 设计 structured output schema。
- 设计批处理调用方式。
- 处理引用、长上下文和 JSON schema 输出。

### `documents:documents`

如果 Wiki 输出需要变成 `.docx` 报告或审阅材料，可以作为最终渲染层使用。它不应参与 RSS 采集和 evidence bundle 生成。

### `browser` / `chrome`

如果最终 Wiki 目标是 Web 系统，需要自动发布页面，可以在最后发布阶段使用。不要把浏览器自动化放进 `rsslab` 核心流程。

## JSONL Evidence Bundle Contract

每行表示一篇文章。建议结构：

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

字段要求：

- `article_id` 必须来自 SQLite。
- `url` 必须保留原文链接。
- `content` 优先使用 `content_text`，为空时使用 `summary_from_rss`。
- `extraction_status` 必须保留，用于下游判断材料质量。
- `content_hash` 必须保留，用于后续重跑和变更检测。
- `citation` 必须可直接被 LLM-WIKI 输出引用。

## LLM-WIKI Skill Contract

建议 `rsslab-llm-wiki` skill 的输入：

```text
Use $rsslab-llm-wiki to turn <bundle.jsonl> into Wiki-ready Markdown pages.
```

skill 职责：

- 读取 JSONL evidence bundle。
- 校验每条 evidence 的必填字段。
- 丢弃没有 `content` 且没有 `summary` 的材料。
- 按主题、实体、时间线或用户指定目标组织材料。
- 抽取事实陈述，并为每个事实保留 citation。
- 合并重复事实。
- 标注互相冲突的事实。
- 生成 Wiki 页面草稿。
- 输出 Markdown 或结构化 JSON。

skill 不负责：

- 拉 RSS。
- 刷新 source。
- 修改 SQLite。
- 抓正文。
- 判断 source 是否 due。
- 发布到远端 Wiki。

## Wiki Page Output Shape

建议 Markdown 页面结构：

```markdown
# Topic Title

## Summary

One concise neutral summary.

## Key Facts

- Fact sentence. [Source: Example News, 2026-06-01](https://example.com/news/1)

## Timeline

- 2026-06-01: Event sentence. [Source](https://example.com/news/1)

## Key Entities

- Entity name: role or relevance.

## Open Questions And Conflicts

- Conflicting claim or unclear detail, with citations.

## Sources

1. Example News, "Example title", 2026-06-01, https://example.com/news/1
```

## Implementation Plan

### Task 1: Add Collection Schema

**Files:**

- Modify: `src/rsslab/schema.sql`
- Modify: `src/rsslab/db.py`
- Test: `tests/test_collection.py`

- [ ] **Step 1: Write failing schema test**

```python
from rsslab.db import connect, init_db


def test_collection_tables_exist(tmp_path):
    conn = connect(tmp_path / "rsslab.db")
    init_db(conn)

    tables = {
        row["name"]
        for row in conn.execute(
            "select name from sqlite_master where type in ('table', 'view')"
        ).fetchall()
    }

    assert "collection_jobs" in tables
    assert "collection_results" in tables
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
python -m pytest tests/test_collection.py::test_collection_tables_exist -v
```

Expected: FAIL because `collection_jobs` and `collection_results` do not exist.

- [ ] **Step 3: Add tables to schema**

Add `collection_jobs`:

```sql
create table if not exists collection_jobs (
    id integer primary key autoincrement,
    name text not null default '',
    query text not null,
    filters_json text not null default '{}',
    since text,
    until text,
    limit_count integer not null,
    ensure_full_text integer not null default 0,
    status text not null default 'completed',
    created_at text not null,
    completed_at text
);
```

Add `collection_results`:

```sql
create table if not exists collection_results (
    job_id integer not null references collection_jobs(id) on delete cascade,
    article_id integer not null references articles(id) on delete cascade,
    rank integer not null,
    score real not null default 0,
    reason text not null default '',
    primary key (job_id, article_id)
);
```

- [ ] **Step 4: Run test and verify pass**

Run:

```bash
python -m pytest tests/test_collection.py::test_collection_tables_exist -v
```

Expected: PASS.

### Task 2: Implement `rsslab collect`

**Files:**

- Create: `src/rsslab/collection.py`
- Modify: `src/rsslab/cli.py`
- Test: `tests/test_collection.py`

- [ ] **Step 1: Write failing collection behavior test**

```python
from rsslab.collection import collect_articles
from rsslab.db import connect, init_db


def test_collect_articles_creates_job_and_ranked_results(tmp_path):
    conn = connect(tmp_path / "rsslab.db")
    init_db(conn)
    conn.execute(
        """
        insert into sources (
            feed_url, site_url, title, source_name, source_type,
            topics, language, trust_level, created_at, updated_at
        )
        values (
            'https://example.com/feed.xml', 'https://example.com', 'Example',
            'Example', 'rss', 'ai', 'en', 'high',
            '2026-06-01T00:00:00Z', '2026-06-01T00:00:00Z'
        )
        """
    )
    source_id = conn.execute("select id from sources").fetchone()["id"]
    conn.execute(
        """
        insert into articles (
            source_id, guid, url, canonical_url, title, author,
            published_at, fetched_at, summary_from_rss, content_text,
            raw_entry_json, content_hash, dedupe_key, extraction_status,
            created_at, updated_at
        )
        values (
            ?, 'g1', 'https://example.com/a', 'https://example.com/a',
            'AI chip export control', 'Reporter',
            '2026-06-01T10:00:00Z', '2026-06-01T10:10:00Z',
            'summary', 'full text', '{}', 'sha256:x',
            'url:https://example.com/a', 'success',
            '2026-06-01T10:10:00Z', '2026-06-01T10:10:00Z'
        )
        """,
        (source_id,),
    )
    conn.commit()

    job = collect_articles(
        conn,
        query="AI chip",
        since=None,
        limit=10,
        ensure_full_text=False,
    )

    assert job.id == 1
    assert job.query == "AI chip"
    rows = conn.execute(
        "select job_id, article_id, rank from collection_results"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["rank"] == 1
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
python -m pytest tests/test_collection.py::test_collect_articles_creates_job_and_ranked_results -v
```

Expected: FAIL because `rsslab.collection` does not exist.

- [ ] **Step 3: Implement minimal `collect_articles`**

Create `src/rsslab/collection.py` with:

```python
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from rsslab.extractor import extract_article
from rsslab.search import search_articles


@dataclass(frozen=True)
class CollectionJob:
    id: int
    query: str
    limit: int
    ensure_full_text: bool


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def collect_articles(
    conn: sqlite3.Connection,
    *,
    query: str,
    since: str | None,
    limit: int,
    ensure_full_text: bool,
) -> CollectionJob:
    created_at = _now()
    cursor = conn.execute(
        """
        insert into collection_jobs (
            name, query, filters_json, since, until, limit_count,
            ensure_full_text, status, created_at, completed_at
        )
        values (?, ?, '{}', ?, null, ?, ?, 'running', ?, null)
        """,
        (query, query, since, limit, int(ensure_full_text), created_at),
    )
    job_id = int(cursor.lastrowid)
    results = search_articles(conn, query, since=since, limit=limit)
    for index, result in enumerate(results, start=1):
        if ensure_full_text and result.extraction_status != "success":
            extract_article(conn, result.id)
        conn.execute(
            """
            insert into collection_results (job_id, article_id, rank, score, reason)
            values (?, ?, ?, ?, ?)
            """,
            (job_id, result.id, index, result.score, f"matched query: {query}"),
        )
    completed_at = _now()
    conn.execute(
        "update collection_jobs set status = 'completed', completed_at = ? where id = ?",
        (completed_at, job_id),
    )
    conn.commit()
    return CollectionJob(id=job_id, query=query, limit=limit, ensure_full_text=ensure_full_text)
```

- [ ] **Step 4: Add CLI command**

Modify `src/rsslab/cli.py`:

```python
from rsslab.collection import collect_articles


@app.command("collect")
def collect_command(
    query: str,
    since: str | None = typer.Option(None, "--since"),
    limit: int = typer.Option(30, "--limit"),
    ensure_full_text: bool = typer.Option(False, "--ensure-full-text"),
) -> None:
    conn = _conn()
    job = collect_articles(
        conn,
        query=query,
        since=since,
        limit=limit,
        ensure_full_text=ensure_full_text,
    )
    typer.echo(f"Collection {job.id}: query={job.query} limit={job.limit}")
```

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest tests/test_collection.py -v
python -m pytest
```

Expected: PASS.

### Task 3: Implement JSONL Export

**Files:**

- Create: `src/rsslab/exporter.py`
- Modify: `src/rsslab/cli.py`
- Test: `tests/test_exporter.py`

- [ ] **Step 1: Write failing export test**

```python
import json

from rsslab.db import connect, init_db
from rsslab.exporter import export_collection_jsonl


def test_export_collection_jsonl_writes_evidence_contract(tmp_path):
    conn = connect(tmp_path / "rsslab.db")
    init_db(conn)
    conn.execute(
        """
        insert into sources (
            feed_url, site_url, title, source_name, source_type,
            topics, language, trust_level, created_at, updated_at
        )
        values (
            'https://example.com/feed.xml', 'https://example.com', 'Example',
            'Example News', 'rss', 'ai,chips', 'en', 'high',
            '2026-06-01T00:00:00Z', '2026-06-01T00:00:00Z'
        )
        """
    )
    source_id = conn.execute("select id from sources").fetchone()["id"]
    conn.execute(
        """
        insert into articles (
            source_id, guid, url, canonical_url, title, author,
            published_at, fetched_at, summary_from_rss, content_text,
            raw_entry_json, content_hash, dedupe_key, extraction_status,
            created_at, updated_at
        )
        values (
            ?, 'g1', 'https://example.com/a', 'https://example.com/a',
            'Example title', 'Reporter',
            '2026-06-01T10:00:00Z', '2026-06-01T10:10:00Z',
            'summary', 'full text', '{}', 'sha256:x',
            'url:https://example.com/a', 'success',
            '2026-06-01T10:10:00Z', '2026-06-01T10:10:00Z'
        )
        """,
        (source_id,),
    )
    article_id = conn.execute("select id from articles").fetchone()["id"]
    conn.execute(
        """
        insert into collection_jobs (
            name, query, filters_json, since, until, limit_count,
            ensure_full_text, status, created_at, completed_at
        )
        values (
            'AI chip', 'AI chip', '{}', null, null, 10,
            0, 'completed', '2026-06-01T11:00:00Z', '2026-06-01T11:00:01Z'
        )
        """
    )
    job_id = conn.execute("select id from collection_jobs").fetchone()["id"]
    conn.execute(
        "insert into collection_results (job_id, article_id, rank, score, reason) values (?, ?, 1, 1.0, 'matched')",
        (job_id, article_id),
    )
    conn.commit()

    out = tmp_path / "bundle.jsonl"
    export_collection_jsonl(conn, job_id, out)

    row = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert row["article_id"] == article_id
    assert row["content"] == "full text"
    assert row["source"]["name"] == "Example News"
    assert row["citation"]["url"] == "https://example.com/a"
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
python -m pytest tests/test_exporter.py::test_export_collection_jsonl_writes_evidence_contract -v
```

Expected: FAIL because `rsslab.exporter` does not exist.

- [ ] **Step 3: Implement exporter**

Create `src/rsslab/exporter.py` with:

```python
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _topics(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def export_collection_jsonl(conn: sqlite3.Connection, collection_id: int, out_path: str | Path) -> int:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        """
        select
            a.id as article_id,
            a.title,
            a.url,
            a.canonical_url,
            a.published_at,
            a.fetched_at,
            a.author,
            a.summary_from_rss,
            a.content_text,
            a.content_hash,
            a.extraction_status,
            s.id as source_id,
            s.source_name,
            s.feed_url,
            s.site_url,
            s.trust_level,
            s.language,
            s.topics
        from collection_results cr
        join articles a on a.id = cr.article_id
        join sources s on s.id = a.source_id
        where cr.job_id = ?
        order by cr.rank asc
        """,
        (collection_id,),
    ).fetchall()
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            content = row["content_text"] or row["summary_from_rss"]
            payload = {
                "article_id": row["article_id"],
                "title": row["title"],
                "url": row["url"],
                "canonical_url": row["canonical_url"],
                "published_at": row["published_at"],
                "fetched_at": row["fetched_at"],
                "author": row["author"],
                "summary": row["summary_from_rss"],
                "content": content,
                "content_hash": row["content_hash"],
                "extraction_status": row["extraction_status"],
                "source": {
                    "id": row["source_id"],
                    "name": row["source_name"],
                    "feed_url": row["feed_url"],
                    "site_url": row["site_url"],
                    "trust_level": row["trust_level"],
                    "language": row["language"],
                    "topics": _topics(row["topics"]),
                },
                "citation": {
                    "title": row["title"],
                    "url": row["url"],
                    "source_name": row["source_name"],
                    "published_at": row["published_at"],
                    "retrieved_at": row["fetched_at"],
                },
            }
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return len(rows)
```

- [ ] **Step 4: Add CLI command**

Modify `src/rsslab/cli.py`:

```python
from pathlib import Path
from rsslab.exporter import export_collection_jsonl


@app.command("export")
def export_command(
    collection_id: int,
    format: str = typer.Option("jsonl", "--format"),
    out: Path = typer.Option(..., "--out"),
) -> None:
    if format != "jsonl":
        raise typer.BadParameter("only jsonl format is supported")
    conn = _conn()
    count = export_collection_jsonl(conn, collection_id, out)
    typer.echo(f"Exported {count} articles to {out}")
```

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest tests/test_exporter.py -v
python -m pytest
```

Expected: PASS.

### Task 4: Create `rsslab-llm-wiki` Skill

**Files:**

- Create via `skill-creator`: `.codex/skills/rsslab-llm-wiki/SKILL.md`
- Optional: `.codex/skills/rsslab-llm-wiki/references/evidence-schema.md`
- Optional: `.codex/skills/rsslab-llm-wiki/references/wiki-output.md`

- [ ] **Step 1: Scaffold skill**

Run:

```bash
python "C:\Users\mozhe.TENHAG\.codex\skills\.system\skill-creator\scripts\init_skill.py" rsslab-llm-wiki --path ".codex\skills" --resources references --interface display_name="RSSLab LLM Wiki" --interface short_description="Turn rsslab JSONL evidence bundles into citation-preserving Wiki drafts." --interface default_prompt="Use $rsslab-llm-wiki to convert an rsslab JSONL evidence bundle into Wiki-ready Markdown with citations."
```

Expected: creates `.codex/skills/rsslab-llm-wiki`.

- [ ] **Step 2: Write skill instructions**

`SKILL.md` must include:

```markdown
# RSSLab LLM Wiki

Use this skill when the user provides or references an `rsslab` JSONL evidence bundle and asks for Wiki-ready output, fact extraction, citation-preserving summaries, timelines, entity pages, or source-grounded knowledge pages.

## Input

Read a JSONL file where each line follows the `rsslab` evidence contract.

## Required Workflow

1. Validate every evidence row has `article_id`, `title`, `url`, `source`, `content`, `content_hash`, and `citation`.
2. Use `content` as the primary evidence text.
3. Preserve every citation URL.
4. Extract atomic facts with source references.
5. Merge duplicate facts only when they make the same claim.
6. Mark conflicting facts instead of silently resolving them.
7. Produce Markdown with Summary, Key Facts, Timeline, Key Entities, Conflicts, and Sources.

## Restrictions

- Do not invent facts not present in the evidence bundle.
- Do not remove citation URLs.
- Do not fetch new web pages unless the user explicitly asks.
- Do not modify the `rsslab` SQLite database.
```

- [ ] **Step 3: Verify skill exists**

Run:

```bash
Get-ChildItem .codex\skills\rsslab-llm-wiki -Recurse
```

Expected: `SKILL.md` and `references` directory exist.

### Task 5: End-to-End Local Verification

**Files:**

- Modify: `README.md`
- Optional create: `docs/llm-wiki-workflow.md`

- [ ] **Step 1: Update docs with workflow**

Add this command sequence:

```bash
rsslab refresh all
rsslab search "AI chip export control" --since 30d --limit 30
rsslab extract missing --limit 30
rsslab collect "AI chip export control" --since 30d --limit 30 --ensure-full-text
rsslab export 1 --format jsonl --out bundles/ai-chip-export-control.jsonl
```

Add the downstream instruction:

```text
Use $rsslab-llm-wiki to convert bundles/ai-chip-export-control.jsonl into a Wiki-ready Markdown page.
```

- [ ] **Step 2: Run full test suite**

Run:

```bash
python -m pytest
```

Expected: all tests pass.

- [ ] **Step 3: Run CLI smoke test**

Run:

```bash
rsslab collect "Ukraine" --limit 5 --ensure-full-text
rsslab export 1 --format jsonl --out bundles/ukraine.jsonl
```

Expected:

- `rsslab collect` prints a collection id.
- `bundles/ukraine.jsonl` exists.
- Each JSONL row has `content`, `source`, and `citation`.

## Acceptance Criteria

- `collection_jobs` and `collection_results` are initialized for new and existing SQLite databases.
- `rsslab collect` creates a stable, inspectable collection record.
- `rsslab collect --ensure-full-text` attempts to fill missing article text before recording results.
- `rsslab export <collection-id> --format jsonl --out <path>` writes one JSON object per article.
- Exported JSONL follows the evidence bundle contract in this document.
- `rsslab-llm-wiki` skill exists and documents how to turn JSONL into citation-preserving Wiki Markdown.
- `python -m pytest` passes.
- No daemon, cloud sync, GUI, or direct LLM call is added to `rsslab`.

## Open Decisions

- Whether `collection_jobs.id` alone is enough, or whether to add a deterministic `fingerprint` field based on query and filters.
- Whether `topics` should remain comma-separated text or migrate to JSON text before export.
- Whether the LLM-WIKI skill should output only Markdown or also a structured JSON page model.
- Whether final Wiki publishing belongs in a later browser automation workflow or a separate API integration.

## Recommended Next Step

Implement Task 1 through Task 3 first. After JSONL export exists and is covered by tests, create `rsslab-llm-wiki` with `skill-creator`. This keeps the core data contract stable before adding LLM-facing behavior.
