# RSS 新闻采集与 LLM Wiki 输入层设计方案

## 1. 背景

当前目标不是实现一个传统 RSS 阅读器，而是实现一个面向后续 LLM Wiki 流程的新闻采集层。RSS 订阅只是入口，核心价值在于按需检索新闻、获取可用正文、保留可追溯来源，并导出结构化材料包供 LLM 继续处理。

参考 RSS Guard 当前项目后，可以复用其核心业务思想：

- 将 Feed 与文章 Message 分离建模。
- 订阅源刷新后统一解析为标准文章对象。
- 本地数据库保存订阅源、文章正文、状态和检索字段。
- 使用文章 GUID、URL、标题、作者、正文变化判断新增或更新。
- 将正文提取设计成独立能力，而不是耦合在 RSS 解析中。
- 将检索抽象为对本地文章库的过滤和查询。

本方案会保留这些边界，但不照搬 RSS Guard 的 GUI、插件、多账号、标签、回收站和复杂同步体系。

## 2. 目标

第一版实现一个 Python CLI 工具，用于从 RSS/Atom 源采集新闻并为 LLM Wiki 流程准备输入材料。

核心目标：

- 管理 RSS/Atom 新闻源。
- 手动或按计划刷新新闻源。
- 解析并规范化文章元数据。
- 对命中文章按需提取正文。
- 使用 SQLite 本地持久化。
- 支持本地全文检索。
- 导出结构化 JSONL 材料包。
- 保留来源、抓取时间、正文快照和内容哈希，支持后续引用、审计和重跑。

非目标：

- 不实现 GUI。
- 不实现 RSS 阅读器式交互体验。
- 不实现云同步。
- 不实现多用户账号系统。
- 不实现复杂插件系统。
- 第一版不强依赖常驻后台服务。

## 3. 用户工作流

### 3.1 添加新闻源

用户可以直接添加 RSS/Atom URL：

```bash
rsslab source add https://example.com/feed.xml --topic ai --trust-level high --language en
```

工具会拉取 Feed 元数据并保存：

- 源名称
- Feed URL
- 站点 URL
- 主题标签
- 语言
- 来源质量等级
- 刷新间隔

### 3.2 发现新闻源

用户也可以输入网站首页，由工具发现可订阅 Feed：

```bash
rsslab source discover https://example.com
```

发现策略：

- 解析 HTML 中的 `link rel="alternate"` RSS/Atom 链接。
- 尝试常见路径：`/feed`、`/rss`、`/atom.xml`、`/feed.xml`、`/rss.xml`。
- 对候选源进行轻量解析，展示标题、URL、格式和最近文章数。

### 3.3 刷新采集

用户手动刷新全部或部分来源：

```bash
rsslab refresh all
rsslab refresh due
rsslab refresh source 12
```

`refresh all` 刷新全部源。

`refresh due` 只刷新达到 `refresh_interval` 的源，适合被 cron 或 Windows Task Scheduler 定时调用。

刷新时默认只拉 RSS/Atom 并保存摘要，不强制抓取每篇文章网页正文。这样可以降低网络请求量和被目标站点限制的概率。

### 3.4 按需检索

用户按主题检索本地已采集新闻：

```bash
rsslab search "AI chip export control" --since 30d --language en --topic chips
```

搜索范围包括：

- 标题
- 作者
- 来源名称
- RSS 摘要
- 已提取正文

第一版优先使用 SQLite FTS5；如果环境不支持 FTS5，则回退到 `LIKE` 查询。

### 3.5 构建 LLM 材料包

用户将检索命中的新闻收集成一次可复现任务：

```bash
rsslab collect "AI chip export control" --since 30d --limit 30 --ensure-full-text
```

`--ensure-full-text` 表示对命中文章补充正文提取。提取失败时回退 RSS 摘要，但会记录失败状态和错误信息。

采集任务会生成 `collection_jobs` 记录，保存查询词、过滤条件、时间范围、创建时间和结果排序。

### 3.6 导出给 LLM Wiki

用户导出材料包：

```bash
rsslab export <collection-id> --format jsonl --out bundles/ai-chip-export-control.jsonl
```

每行 JSON 包含文章正文、来源信息和引用元数据，后续 LLM Wiki 流程可以直接消费。

## 4. 系统架构

整体架构分为六层：

```text
CLI 命令层
  -> 应用服务层
    -> RSS 拉取层
    -> Feed 解析层
    -> 正文提取层
    -> 检索与采集任务层
    -> SQLite 存储层
```

### 4.1 CLI 命令层

职责：

- 解析命令行参数。
- 调用应用服务。
- 输出表格、文本或 JSONL。
- 不直接操作数据库细节。

建议使用 Typer。

### 4.2 应用服务层

职责：

- 编排订阅、刷新、检索、正文提取和导出。
- 处理业务规则，例如去重、更新保留状态、采集任务生成。
- 作为 CLI 与底层模块之间的稳定接口。

### 4.3 RSS 拉取层

职责：

- 使用 HTTP 拉取 RSS/Atom 文档。
- 支持超时、重试、User-Agent。
- 保存并使用 `ETag` 和 `Last-Modified`。
- 服务端返回 `304 Not Modified` 时跳过解析。

### 4.4 Feed 解析层

职责：

- 将 RSS/Atom 统一解析为内部 `ArticleCandidate`。
- 规范化字段：
  - `title`
  - `url`
  - `canonical_url`
  - `author`
  - `published_at`
  - `summary`
  - `guid`
  - `raw_entry_json`

参考 RSS Guard 的修正规则：

- 无标题但有 URL 时，用 URL 作为标题。
- 无发布时间时，用当前 UTC 时间。
- 对同一个 Feed 中缺失时间的多篇文章，时间可按秒递减以保持排序稳定。
- URL 去除换行和制表符。
- 空标题且无 URL 的条目丢弃。

### 4.5 正文提取层

职责：

- 从文章 URL 抓取网页。
- 提取正文文本和可选清洗 HTML。
- 支持从已有 RSS HTML 摘要中提取正文。
- 失败时回退 RSS 摘要。
- 保存提取状态，避免反复无效重试。

建议第一版使用 `trafilatura`。如果后续遇到站点适配问题，可增加 `readability-lxml` 作为备用。

### 4.6 检索与采集任务层

职责：

- 执行文章搜索。
- 根据过滤条件筛选来源、主题、语言、时间范围。
- 生成可复现的 `collection_job`。
- 对命中文章按需补全文本。
- 记录每条结果的排名和命中原因。

### 4.7 SQLite 存储层

职责：

- 管理 schema 初始化和迁移。
- 封装增删改查。
- 维护全文索引。
- 保证写入去重和状态保留。

## 5. 数据模型

### 5.1 sources

RSS/Atom 新闻源。

字段：

- `id`
- `feed_url`
- `site_url`
- `title`
- `description`
- `source_name`
- `source_type`
- `topics`
- `language`
- `region`
- `trust_level`
- `refresh_interval_seconds`
- `last_fetched_at`
- `etag`
- `last_modified`
- `last_error`
- `created_at`
- `updated_at`

### 5.2 articles

标准化文章表。

字段：

- `id`
- `source_id`
- `guid`
- `url`
- `canonical_url`
- `title`
- `author`
- `published_at`
- `fetched_at`
- `summary_from_rss`
- `content_text`
- `content_html`
- `raw_entry_json`
- `raw_html_path`
- `language`
- `site_name`
- `content_hash`
- `dedupe_key`
- `extraction_status`
- `extraction_error`
- `is_read`
- `is_starred`
- `created_at`
- `updated_at`

### 5.3 collection_jobs

一次按需新闻采集任务。

字段：

- `id`
- `name`
- `query`
- `filters_json`
- `since`
- `until`
- `limit`
- `ensure_full_text`
- `status`
- `created_at`
- `completed_at`

### 5.4 collection_results

采集任务命中的文章。

字段：

- `job_id`
- `article_id`
- `rank`
- `score`
- `reason`

### 5.5 articles_fts

SQLite FTS5 索引表。

索引字段：

- `title`
- `author`
- `summary_from_rss`
- `content_text`
- `source_name`

## 6. 去重与更新策略

### 6.1 去重优先级

生成 `dedupe_key` 时按以下优先级：

1. `canonical_url`
2. 规范化后的 URL
3. Feed 内 `guid`
4. `sha256(title + published_at + summary)`

URL 规范化应移除常见 tracking 参数：

- `utm_source`
- `utm_medium`
- `utm_campaign`
- `utm_term`
- `utm_content`
- `fbclid`
- `gclid`

### 6.2 更新规则

如果文章已存在：

- 标题变化则更新标题。
- 作者变化则更新作者。
- 发布时间变化则更新发布时间。
- RSS 摘要变化则更新摘要。
- 正文变化则更新正文和 `content_hash`。
- 保留 `is_read` 和 `is_starred`。

如果文章不存在：

- 插入新文章。
- 默认 `is_read = false`。
- 默认 `is_starred = false`。

## 7. 正文提取策略

第一版采用按需提取，而不是刷新时对所有文章提取。

触发方式：

- `rsslab collect ... --ensure-full-text`
- `rsslab extract article <article-id>`
- `rsslab extract missing --limit 100`

提取流程：

1. 如果文章无 URL，直接使用 RSS 摘要，状态记为 `fallback_summary`。
2. 如果文章有 URL，下载 HTML。
3. 保存可选原始 HTML 快照。
4. 使用正文提取器生成 `content_text`。
5. 如果正文为空，回退 RSS 摘要。
6. 写入 `content_hash`。
7. 记录 `extraction_status`。

状态建议：

- `pending`
- `success`
- `fallback_summary`
- `failed`
- `skipped_no_url`

## 8. 检索策略

第一版支持本地检索，不直接搜索外部互联网。

搜索命令：

```bash
rsslab search <query> --since 7d --until 2026-06-01 --source reuters --topic ai --language en --limit 20
```

排序规则：

1. FTS 相关性。
2. 发布时间新旧。
3. 来源质量等级。
4. 是否已有完整正文。

注意：

本地检索只能覆盖已采集入库的文章。RSS 源没有暴露的历史文章无法通过本地检索获得。若要扩大新闻覆盖面，应通过 `source discover` 或后续的关键词源发现能力增加订阅源。

## 9. CLI 设计

第一版命令：

```bash
rsslab source add <feed-url> [--topic TOPIC] [--language LANG] [--trust-level LEVEL]
rsslab source discover <site-url>
rsslab source list
rsslab source remove <source-id>

rsslab refresh all
rsslab refresh due
rsslab refresh source <source-id>

rsslab search <query> [--since DURATION] [--limit N]
rsslab collect <query> [--since DURATION] [--limit N] [--ensure-full-text]
rsslab export <collection-id> --format jsonl --out <path>

rsslab show <article-id>
rsslab extract article <article-id>
rsslab extract missing [--limit N]
```

第二阶段命令：

```bash
rsslab daemon --interval 15m
rsslab source recommend --keyword <keyword>
rsslab clean --older-than 180d --keep-starred
```

## 10. 后台调度策略

第一版不强制实现常驻后台服务，但要设计成可被系统调度器调用。

推荐第一版支持：

```bash
rsslab refresh due
```

用户可以通过 cron、systemd timer 或 Windows Task Scheduler 周期性执行。

第二阶段再实现：

```bash
rsslab daemon --interval 15m
```

后台调度可扩展能力：

- 按 Feed 刷新间隔自动刷新。
- 基于失败次数退避重试。
- 自动补提取正文。
- 发现新文章后执行 hook。
- 定期清理旧文章。

## 11. LLM Wiki 输出契约

导出 JSONL 每行代表一篇文章，建议结构：

```json
{
  "article_id": 123,
  "title": "Example title",
  "url": "https://example.com/news/1",
  "canonical_url": "https://example.com/news/1",
  "source": {
    "id": 5,
    "name": "Example News",
    "feed_url": "https://example.com/feed.xml",
    "site_url": "https://example.com",
    "trust_level": "high",
    "language": "en",
    "topics": ["ai", "chips"]
  },
  "published_at": "2026-06-01T10:00:00Z",
  "fetched_at": "2026-06-01T10:15:00Z",
  "author": "Reporter Name",
  "summary": "Summary from RSS",
  "content": "Extracted full article text",
  "content_hash": "sha256:...",
  "extraction_status": "success",
  "citation": {
    "title": "Example title",
    "url": "https://example.com/news/1",
    "source_name": "Example News",
    "published_at": "2026-06-01T10:00:00Z",
    "retrieved_at": "2026-06-01T10:15:00Z"
  }
}
```

这个契约的重点是让 LLM Wiki 流程能够：

- 使用正文生成结构化知识。
- 回溯每条材料来源。
- 区分发布时间和抓取时间。
- 基于 `content_hash` 判断内容是否变化。
- 在后续重新生成 Wiki 时复用相同材料包。

## 12. 技术选型

建议：

- Python 3.11+
- Typer：CLI 框架
- httpx：HTTP 客户端
- feedparser：RSS/Atom 解析
- trafilatura：正文提取
- beautifulsoup4：Feed 发现与 HTML 辅助解析
- sqlite3 或 SQLAlchemy Core：本地存储
- pytest：测试

第一版可以优先使用标准库 `sqlite3`，减少抽象层复杂度。若后续 schema 和查询复杂度上升，再迁移到 SQLAlchemy Core。

## 13. 测试策略

必须覆盖：

- 添加 Source。
- HTML Feed 发现。
- RSS/Atom 解析。
- 无标题、无发布时间、异常 URL 的字段修正。
- 去重插入。
- 已有文章更新且保留 `is_read`、`is_starred`。
- FTS 检索。
- FTS 不可用时 LIKE 回退。
- 正文提取成功。
- 正文提取失败回退摘要。
- `collect` 生成可复现任务。
- JSONL 导出结构符合契约。

## 14. 分阶段实施建议

### 阶段 1：本地采集闭环

- 建立 CLI 项目骨架。
- 初始化 SQLite schema。
- 实现 `source add/list/remove`。
- 实现 `refresh all/source`。
- 实现文章解析、规范化、去重和更新。

验收标准：

- 可以添加 RSS 源。
- 可以刷新并入库文章。
- 重复刷新不会重复插入。

### 阶段 2：检索与正文提取

- 实现 FTS/LIKE 检索。
- 实现正文提取。
- 实现 `extract article` 和 `extract missing`。

验收标准：

- 可以按关键词检索文章。
- 可以为指定文章补全文。
- 提取失败有明确状态和回退内容。

### 阶段 3：LLM 材料包

- 实现 `collect`。
- 实现 `collection_jobs` 与 `collection_results`。
- 实现 JSONL 导出。

验收标准：

- 一次查询可以生成稳定 collection id。
- 导出的 JSONL 可直接交给 LLM Wiki 流程。

### 阶段 4：调度友好

- 实现 `refresh due`。
- 支持每个 Source 的刷新间隔。
- 记录刷新错误和最后刷新时间。

验收标准：

- 可以由系统计划任务周期性调用。
- 未到期 Source 不会被重复刷新。

## 15. 风险与取舍

### RSS 历史覆盖有限

RSS 源通常只暴露最近若干篇文章。没有后台刷新时，本地库只能覆盖每次刷新时 Feed 中仍存在的文章。

缓解：

- 支持 `refresh due` 方便系统调度。
- 对高频源设置更短刷新间隔。
- 后续增加新闻源发现和补充采集能力。

### 正文提取不稳定

不同网站页面结构差异大，正文提取可能失败或提取不完整。

缓解：

- 保存 RSS 摘要作为回退。
- 保存原始 HTML 快照用于重跑。
- 记录 `extraction_status` 和错误。
- 后续允许按域名配置提取策略。

### 重复新闻较多

同一新闻可能被多个源转载或以不同 URL 出现。

缓解：

- 使用 canonical URL、规范化 URL 和内容哈希去重。
- 后续增加标题相似度和时间窗口去重。

### LLM 输入污染

广告、导航、免责声明可能进入正文，影响后续 Wiki 质量。

缓解：

- 优先使用成熟正文提取库。
- 保留原始数据，允许重新提取。
- 在导出阶段提供最小长度、语言、来源质量过滤。

## 16. 结论

RSS 订阅部分应设计为新闻采集与证据入库层，而不是阅读器。第一版重点是稳定采集、可检索、可追溯、可导出。

最终数据流：

```text
RSS/Atom Source
  -> refresh
  -> normalized article
  -> SQLite storage + FTS
  -> search / collect
  -> ensure full text
  -> JSONL evidence bundle
  -> LLM Wiki pipeline
```

这个边界能够满足当前目标，同时保留后续扩展后台调度、新闻源发现、来源质量评分和更复杂去重策略的空间。
