# World Cup Wiki Ingest Log

## 2026-06-08 RSS Refresh Update

- RSS refresh result: `inserted=25 updated=1`
- collect query: `World Cup`
- collect filters: `since=30d`, `language=en`, `trust_level=high`, `limit=20`, `complete_full_text=true`
- exported bundle: `evidence/world_cup.jsonl`
- target wiki_id: `world-cup`
- collection_id: `1`
- records ingested: `6`
- raw evidence directory: `raw/collection-1/`
- wiki language: Chinese
- source list at refresh time: [[bbc-news|BBC News]]

## Article Inventory

| rank | article_id | source | published_at | extraction_status | content_hash |
| --- | ---: | --- | --- | --- | --- |
| 1 | 61 | BBC News | 2026-06-07T23:00:27Z | failed | sha256:e3e13f108ea6b096f9e047dbb8ed0a8909fed45e77b6e07e94e5c1ed65a52796 |
| 2 | 70 | BBC News | 2026-06-07T17:53:32Z | failed | sha256:94e1250ce66ce713855ba5a371a8c04fb1020c013abf5c2a473ec0726dbebb49 |
| 3 | 52 | BBC News | 2026-06-04T08:46:23Z | failed | sha256:435c32ef55739b594d4748bed9ab9a2e38a292ea4a301ce87d762c8715b4d2e7 |
| 4 | 57 | BBC News | 2026-06-04T05:42:34Z | failed | sha256:231f87e4e9aee9c732202279a946517f063f9e51d19f62ffb1ca163eea63dcb9 |
| 5 | 25 | BBC News | 2026-06-02T05:28:25Z | success | sha256:869860fbb9eee3214c94f6d69cc5f221d504fe422f837669d8612cec57bac00e |
| 6 | 23 | BBC News | 2026-06-01T22:56:39Z | success | sha256:8db355717eb7b917d4b2278491361615d08f10d0edc021c665f2f742b0845bdf |

## Notes

- No cross-wiki links were created.
- Wiki ingest only consumed `evidence/world_cup.jsonl`; it did not refresh RSS, extract articles, or mutate rsslab SQLite.
- Four evidence rows have `extraction_status: failed`; their Wiki usage is limited to RSS summary-level claims.
- The previous `raw/collection-1` files were replaced with the current 6 exported evidence records to avoid stale evidence mixing.
