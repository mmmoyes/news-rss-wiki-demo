# rsslab 项目状态与后续计划

日期：2026-06-07

## 1. 项目定位

`rsslab` 是一个本地优先的 RSS/Atom 新闻证据采集工具。它负责把新闻源、文章元数据、正文提取结果、检索结果、collection job 和 JSONL evidence bundle 保存在本地 SQLite 与文件系统中，为后续 LLM-Wiki 工作流提供可追溯、可复现的证据输入。

项目边界：

- `rsslab` 不调用 LLM。
- `rsslab` 不生成 Wiki 页面。
- `rsslab` 不发布 Wiki。
- `rsslab` 不维护长期 Wiki 知识状态。
- LLM-Wiki 只消费 `rsslab export` 导出的 JSONL evidence bundle。
- 下游 Wiki 必须保留原始来源 citation。
- 多个知识库通过 `wiki_id` 隔离，跨 Wiki 链接或写入必须显式指定。

推荐流程：

```text
RSS/Atom sources
  -> rsslab refresh
  -> local SQLite articles
  -> rsslab search
  -> rsslab collect
  -> rsslab export JSONL
  -> rsslab-llm-wiki ingest
  -> isolated Markdown Wiki
```

## 2. 当前架构

### 2.1 核心模块

当前 Python 包位于 `src/rsslab/`：

```text
src/rsslab/
  cli.py          Typer CLI 入口
  db.py           SQLite 连接、初始化、轻量迁移、FTS 初始化
  schema.sql      SQLite schema
  services.py     source 管理和 refresh 编排
  rss.py          HTTP 抓取
  parser.py       RSS/Atom 解析和文章规范化
  dedupe.py       URL 规范化、内容 hash、dedupe key
  search.py       本地文章检索，优先 FTS5，失败回退 LIKE
  extractor.py    文章正文提取
  collections.py  collection job、collection result、JSONL export
  models.py       数据模型
```

### 2.2 SQLite 数据层

主要表：

- `sources`：RSS/Atom 源配置、来源元数据、语言、topic、trust level、刷新状态。
- `articles`：规范化文章、URL、标题、作者、发布时间、RSS 摘要、正文、hash、提取状态。
- `articles_fts`：可选 FTS5 虚拟表，用于全文检索。
- `collection_jobs`：一次可复现证据选择任务，保存 query、filters、limit、policy snapshot、状态和结果数。
- `collection_results`：collection 中被选中的文章、rank、score、selection reason、collection 时刻的 hash 和 extraction status。

### 2.3 Evidence Bundle 合同

`rsslab export` 输出 JSONL，每行代表一条被选中的文章证据。

每行包含：

- `collection_id`
- `article_id`
- `rank`
- `score`
- `title`
- `url`
- `canonical_url`
- `published_at`
- `fetched_at`
- `author`
- `summary`
- `content`
- `content_hash`
- `extraction_status`
- `source`
- `citation`

其中 `citation` 是下游 Wiki 必须保留的来源引用，不允许用 collection 本身替代原始来源。

示例结构：

```json
{
  "collection_id": 1,
  "article_id": 1,
  "title": "Example title",
  "url": "https://example.com/news/1",
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

### 2.4 LLM-Wiki Skill Scaffold

项目内已有 skill scaffold：

```text
.codex/skills/rsslab-llm-wiki/
  SKILL.md
  agents/openai.yaml
```

当前它定义了下游 ingest 的边界和规则：

- 输入只接受 `rsslab` JSONL evidence bundle。
- 不读取或修改 `rsslab` SQLite。
- 不调用 `rsslab refresh` 或 `rsslab extract`。
- 每个事实必须保留 citation。
- 每次 ingest 只写入一个 `wiki_id` 对应的知识库目录。
- 默认禁止跨 Wiki 写入和跨 Wiki 链接。

该 skill 目前仍是 scaffold，尚未实现可执行 ingest/lint 脚本。

## 3. 使用方式

### 3.1 安装

从项目根目录安装：

```bash
python -m pip install -e .[test]
```

运行测试：

```bash
python -m pytest
```

### 3.2 数据库位置

默认数据库：

```text
.rsslab/rsslab.db
```

可以通过环境变量指定：

```powershell
$env:RSSLAB_DB=".rsslab\dev.db"
```

### 3.3 管理 RSS 源

添加来源：

```bash
rsslab source add https://feeds.bbci.co.uk/news/world/rss.xml --topic world --language en --trust-level high
```

列出来源：

```bash
rsslab source list
```

删除来源：

```bash
rsslab source remove <source-id>
```

### 3.4 刷新文章

刷新所有来源：

```bash
rsslab refresh all
```

刷新指定来源：

```bash
rsslab refresh source <source-id>
```

### 3.5 本地搜索

```bash
rsslab search "AI chip export control" --since 30d --limit 20
```

搜索范围包括：

- 标题
- 作者
- source name
- RSS summary
- 已提取正文 `content_text`

### 3.6 正文提取

提取单篇文章：

```bash
rsslab extract article <article-id>
```

批量提取未完成正文的文章：

```bash
rsslab extract missing --limit 100
```

正文提取状态：

- `pending`
- `success`
- `fallback_summary`
- `failed`
- `skipped_no_url`

### 3.7 创建 Collection

创建一个可复现 evidence selection：

```bash
rsslab collect "AI chip export control" --since 30d --language en --trust-level high --topic chips --limit 50
```

如果需要在 collection 阶段显式补全文本：

```bash
rsslab collect "AI chip export control" --since 30d --language en --trust-level high --topic chips --limit 50 --complete-full-text
```

注意：`--complete-full-text` 是显式开关。默认 collection 不做额外正文提取。

### 3.8 导出 JSONL Evidence Bundle

```bash
rsslab export <collection-id> --output evidence/ai-chips.jsonl
```

导出的 JSONL 是 LLM-Wiki 的唯一输入边界。下游不应直接读取 SQLite 或重新搜索 live RSS。

## 4. 可使用案例

### 4.1 AI 芯片出口管制 Wiki 输入

目标：为 `ai-chips` 知识库准备近期高信任度英文新闻证据。

```bash
rsslab collect "AI chip export control" --since 30d --language en --trust-level high --topic chips --limit 50 --complete-full-text
rsslab export 1 --output evidence/ai-chip-export-control.jsonl
```

后续由 `rsslab-llm-wiki` 消费：

```text
bundle_path: evidence/ai-chip-export-control.jsonl
wiki_id: ai-chips
knowledge_base_root: knowledge_bases
```

预期产物：

```text
knowledge_bases/ai-chips/
  raw/
  wiki/
  index.md
  log.md
  manifest.yaml
```

### 4.2 地缘政治新闻追踪

目标：为某个长期主题 Wiki 定期准备新闻证据。

```bash
rsslab collect "Ukraine ceasefire negotiations" --since 7d --language en --trust-level high --limit 40
rsslab export 2 --output evidence/ukraine-ceasefire-2026-06-07.jsonl
```

适合用于：

- 时间线更新
- 关键人物和机构页面
- 冲突声明记录
- 后续事实核查

### 4.3 多语言主题材料收集

目标：收集中英文报道，但仍通过 collection 固化选择结果。

```bash
rsslab collect "semiconductor supply chain" --since 30d --language en --language zh --trust-level high --trust-level medium --topic semiconductors --limit 80
rsslab export 3 --output evidence/semiconductor-supply-chain.jsonl
```

适合用于：

- 比较不同地区报道
- 记录同一事件的多来源说法
- 在 Wiki 中显式标注冲突或未确认信息

### 4.4 离线审计和复跑

collection job 会保存 query、filters、limit 和 policy snapshot。导出文件保留 article ID、collection ID、content hash 和 citation。

适合用于：

- 审计某次 Wiki 更新基于哪些文章
- 复查某条 claim 的原始来源
- 比较同一 article 在不同时间的 content hash 是否变化
- 将 evidence bundle 交给不同下游工具处理

## 5. 当前测试和验证状态

当前测试覆盖：

- RSS/Atom parser
- URL dedupe
- source/refresh services
- search
- extractor
- collection jobs
- JSONL export
- CLI 基本路径

最近一次验证结果：

```text
python -m pytest -q
20 passed
```

skill scaffold 验证：

```text
quick_validate.py .codex\skills\rsslab-llm-wiki
Skill is valid!
```

## 6. 后续待实现计划

### 6.1 高优先级

#### 6.1.1 Collection 可复现性增强

当前 `collection_jobs` 保存了 `policy_json`，但还可以加入：

- deterministic `fingerprint`
- search strategy version
- FTS/LIKE mode
- candidate pool size
- ranking policy version
- rsslab package version
- created/exported schema version

目标：同一 collection 的选择过程更容易审计、比较和复跑。

#### 6.1.2 Collection 失败状态

当前 collection job 会先写入 `running`，成功后更新为 `completed`。后续应补充：

- `failed` 状态
- `error_message`
- `completed_at`
- partial result 记录策略
- collection 中途 extract 失败时的明确处理

#### 6.1.3 Export Bundle Manifest

当前 JSONL 每行都有 evidence，但缺 bundle 级 manifest。建议支持：

```text
evidence/
  ai-chips.jsonl
  ai-chips.manifest.json
```

manifest 应包括：

- bundle schema version
- export timestamp
- collection IDs
- policy snapshot
- row count
- rsslab version
- source/trust/extraction status 统计

#### 6.1.4 rsslab-llm-wiki 最小 ingest + lint

当前只有 skill 规则，下一步应实现：

```text
.codex/skills/rsslab-llm-wiki/scripts/
  ingest_bundle.py
  lint_wiki.py
```

最小 ingest：

- 校验 JSONL 必需字段。
- 校验 `wiki_id`，防止路径穿越。
- 只写入 `knowledge_bases/<wiki_id>/`。
- 写 raw evidence JSON。
- 创建或更新 `manifest.yaml`。
- 创建 `wiki/evidence.md`。
- 更新 `index.md` 和 `log.md`。

最小 lint：

- 检查 Markdown evidence 是否保留 citation URL。
- 检查 raw JSON 是否保留 `collection_id`、`article_id`、`content_hash`、`source.trust_level`、`extraction_status`。
- 检查 `manifest.yaml` 的 `wiki_id` 与目录一致。
- 检查默认无跨 Wiki 链接。
- 检查 content hash 变化是否记录到 log。

### 6.2 中优先级

#### 6.2.1 `refresh due`

`sources.refresh_interval_seconds` 已存在，但还没有按到期时间刷新来源的命令。

建议新增：

```bash
rsslab refresh due
```

支持：

- 只刷新到期 source
- limit
- topic/language/trust filter
- dry run

#### 6.2.2 HTTP 条件请求

当前 `rss.py` 使用普通 GET。后续可支持：

- ETag
- Last-Modified
- 304 Not Modified
- 每个 source 保存 conditional request metadata

目标：减少重复拉取，提高 refresh 效率。

#### 6.2.3 更强 Collection Filter

可增加：

- source ID filter
- source name filter
- exact date range
- extraction status filter
- require full text
- include/exclude low trust
- dedupe mode
- incremental/full rebuild mode

#### 6.2.4 Schema Migration 体系

当前迁移是轻量 `_migrate_*`。随着表结构增长，建议引入：

- `schema_migrations` table
- migration version
- migration tests
- downgrade/rollback 策略可选

### 6.3 工程清理

#### 6.3.1 清理生成物

当前工作区可能存在：

- `tmp_tests/`
- `__pycache__/`
- `.pytest_cache/`
- `src/rsslab.egg-info/`

建议确认 `.gitignore` 并清理不应入库的运行产物。

#### 6.3.2 中文 README 编码修复

`README.zh-CN.md` 当前存在明显乱码，应重新保存为 UTF-8 或重写。

#### 6.3.3 旧计划文档状态更新

`docs/superpowers/plans/2026-06-05-llm-wiki-integration.md` 仍包含部分过期“尚未实现”内容，建议更新状态或归档。

## 7. 推荐下一阶段里程碑

### Milestone A：Evidence Bundle 可审计增强

范围：

- collection fingerprint
- failed/error 状态
- export manifest
- schema version

完成标准：

- 每个 bundle 可解释“为什么这些文章被选中”。
- collection 出错时不会留下误导性的 `running` 状态。
- 下游可通过 manifest 理解 bundle 来源和版本。

### Milestone B：rsslab-llm-wiki MVP

范围：

- `ingest_bundle.py`
- `lint_wiki.py`
- raw evidence 写入
- `manifest.yaml`
- `wiki/evidence.md`
- `index.md`
- `log.md`
- 单元测试和本地 smoke workflow

完成标准：

```text
rsslab export -> bundle.jsonl
rsslab-llm-wiki ingest -> knowledge_bases/<wiki_id>/...
rsslab-llm-wiki lint -> PASS/FAIL with actionable errors
```

### Milestone C：Refresh 效率和调度基础

范围：

- `refresh due`
- ETag / Last-Modified
- dry-run refresh
- refresh result auditing

完成标准：

- 可以长期维护多个 RSS 源。
- 避免不必要的全量刷新。
- refresh 行为可解释、可追踪。

## 8. 结论

截至 2026-06-07，`rsslab` 已经具备作为 LLM-Wiki evidence layer 的核心能力：本地 RSS 采集、文章规范化、正文提取、搜索、collection 固化和 JSONL evidence export。

下一步最关键的是把“可用”推进到“可审计、可复跑、可 lint”：先增强 collection/export 的审计元数据，再实现 `rsslab-llm-wiki` 的最小 ingest + lint 闭环，最后补齐 refresh 调度和 HTTP 条件请求。
