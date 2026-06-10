# rsslab 分层抽象与增量 Wiki 更新策略

日期：2026-06-09

## 1. 这份文档解决什么问题

当前项目包含多层抽象：

- SQLite 数据库
- RSS source
- article
- extraction
- search
- collection
- JSONL evidence bundle
- wiki_id
- raw evidence
- Markdown Wiki
- Wiki query / lint

这些层的粒度不同，变更频率不同，对下游的影响也不同。本文按“持续追踪某个新闻主题，并增量更新 Wiki”的使用场景，梳理每一层的职责、粒度、边界和相互影响。

核心结论：

```text
数据库是新闻证据仓库
collection 是一次可审计的证据选择
JSONL 是跨层交接合同
wiki_id 是长期知识库边界
raw evidence 是 Wiki 的审计底座
Markdown Wiki 是面向阅读和检索的知识组织层
```

## 2. 总体架构

推荐流程：

```text
RSS source
  -> refresh
  -> articles in SQLite
  -> extract content
  -> search
  -> collect
  -> export JSONL
  -> ingest into wiki_id
  -> raw evidence + Markdown Wiki
  -> lint / query
```

对应责任：

```text
rsslab 数据层
  负责本地事实材料和元数据

rsslab collection/export 层
  负责把一次主题查询固化成 evidence bundle

rsslab-llm-wiki 层
  负责把 evidence bundle 增量合并到长期 Wiki

Wiki query 层
  负责基于 Wiki 回答问题，并回溯 citation
```

## 3. 各层抽象的粒度

### 3.1 SQLite 数据库

粒度：一个本地 evidence 仓库。

典型文件：

```text
.rsslab/rsslab.db
.rsslab/world-cup.db
.rsslab/ai-chips.db
```

职责：

- 保存 RSS sources。
- 保存 normalized articles。
- 保存正文提取结果。
- 保存 collection jobs 和 collection results。
- 提供本地 search。

影响范围：

- 换一个 SQLite 文件，就换了一个独立 evidence 仓库。
- 同一个数据库内的所有 source、article、collection 可以互相检索和复用。
- 不同数据库之间默认没有关系。

适合粒度：

- 一个长期新闻项目一个数据库。
- 或者一个团队共享一个综合新闻数据库。
- 如果不同主题完全无关，可以拆成多个数据库。

示例：

```powershell
$env:RSSLAB_DB=".rsslab\world-cup.db"
```

这表示之后的 `rsslab source add`、`rsslab refresh`、`rsslab collect` 都写入 `world-cup.db`。

### 3.2 RSS Source

粒度：一个 RSS/Atom feed。

数据库表：

```text
sources
```

职责：

- 描述新闻来源。
- 保存 feed URL、source name、language、topics、trust_level。
- 作为 refresh 的输入。

影响范围：

- 增加 source 会扩大后续 refresh 的文章池。
- source 的 `topics` 和 `trust_level` 会影响 collect filter。
- `rsslab refresh all` 会刷新当前数据库里的所有 source。

适合粒度：

```text
BBC World RSS
BBC Technology RSS
The Guardian Football RSS
```

如果持续追踪一个主题，建议 source 不是越多越好，而是优先选择：

- 信任度高
- 主题相关
- 更新稳定
- RSS 条目质量好

### 3.3 Article

粒度：一篇新闻文章。

数据库表：

```text
articles
```

职责：

- 保存标题、URL、作者、发布时间、抓取时间、RSS summary。
- 保存正文 `content_text`。
- 保存 `content_hash`、`dedupe_key`、`extraction_status`。

影响范围：

- article 是后续 search、collect、export、Wiki citation 的基本证据单位。
- 同一 article 可以出现在多个 collection 中。
- 如果同一 article 的 content hash 变化，Wiki ingest 应记录变更，而不是静默覆盖。

### 3.4 Extraction

粒度：针对某篇 article URL 的正文提取结果。

相关字段：

```text
articles.content_text
articles.content_html
articles.content_hash
articles.extraction_status
articles.extraction_error
articles.extraction_attempted_at
```

职责：

- 把 RSS summary 升级为网页正文。
- 在失败时保留 fallback summary 和失败状态。

影响范围：

- `rsslab search` 可以搜索已提取正文。
- `rsslab export` 会把正文写入 JSONL 的 `content` 字段。
- Wiki ingest 只能使用 JSONL 里已有的 `content`，不会回头拉正文。

关键边界：

```text
正文提取发生在 export 之前。
Wiki ingest 阶段不触发正文获取。
```

推荐策略：

- 主题明确时，用 `rsslab collect --complete-full-text`。
- 如果要提升全库检索质量，用 `rsslab extract missing`。

### 3.5 Search

粒度：一次临时本地查询。

职责：

- 从 SQLite 中查找相关 article。
- 可使用 FTS5，失败时回退 LIKE。

影响范围：

- search 本身不持久化。
- search 是 collect 的候选选择基础。
- 临时搜索适合探索，不适合作为长期审计记录。

### 3.6 Collection

粒度：一次可审计的 evidence selection。

数据库表：

```text
collection_jobs
collection_results
```

职责：

- 固化 query、filters、limit、policy snapshot。
- 保存被选中的 article IDs、rank、score、selection reason。
- 记录 collection 时刻的 `content_hash` 和 `extraction_status`。

影响范围：

- collection 是从“临时搜索”到“可复现证据包”的关键抽象。
- 多个 collection 可以进入同一个 Wiki。
- collection 不等于 Wiki；collection 是一次证据批次。

适合粒度：

```text
collection-1: World Cup
collection-2: World Cup visa restrictions
collection-3: World Cup Mexico security
collection-4: World Cup ticket prices
```

这些都可以进入同一个 `world-cup` Wiki。

不适合的粒度：

- 把 collection 当作一个知识库。
- 每次 collection 都重建整个 Wiki。
- 用 collection ID 替代原始 article citation。

### 3.7 JSONL Evidence Bundle

粒度：一次 collection 的可交换证据文件。

示例：

```text
evidence/world_cup_2026-06-09.jsonl
evidence/world_cup_collection-2.jsonl
```

职责：

- 作为 `rsslab` 与 `rsslab-llm-wiki` 的边界合同。
- 每行保存一条 article evidence。
- 保留 citation、source、content_hash、extraction_status。

影响范围：

- Wiki ingest 只消费 JSONL，不读 SQLite。
- JSONL 文件应该保留，不建议长期覆盖同一个文件名。
- 如果需要复盘某次 Wiki 更新，JSONL 是最直接的输入证据。

推荐命名：

```text
evidence/world_cup_2026-06-09.jsonl
evidence/world_cup_collection-2.jsonl
```

不推荐长期只用：

```text
evidence/world_cup.jsonl
```

因为它容易被覆盖，降低审计能力。

### 3.8 wiki_id

粒度：一个长期知识域。

示例：

```text
world-cup
ai-chips
ukraine-war
```

职责：

- 定义一个知识库边界。
- 隔离 raw evidence、Markdown pages、manifest、log。
- 决定是否允许跨 Wiki 链接。

影响范围：

- 一个 `wiki_id` 可以吸收多个 collection。
- 不同 `wiki_id` 默认互不写入。
- cross-wiki link 必须显式指定。

适合粒度：

```text
world-cup = 长期追踪世界杯相关议题
ai-chips = 长期追踪 AI 芯片出口管制与供应链
```

不适合粒度：

```text
world-cup-2026-06-09 = 只代表一次 collection
```

除非这是一次短期研究，不计划持续维护。

### 3.9 Raw Evidence

粒度：Wiki 内的一条或一批原始 evidence 副本。

当前结构：

```text
knowledge_bases/<wiki_id>/raw/collection-<collection_id>/article-<article_id>.json
```

职责：

- 保存进入 Wiki 的原始 evidence。
- 支持审计、回溯、hash 对比。
- 让 Wiki 查询或 lint 可以回到原始记录。

影响范围：

- raw 不应该被随意删除。
- 增量 ingest 时应追加，而不是覆盖。
- 如果同一 article 新 hash 出现，应保留版本或记录 hash 变化。

更适合增量的结构：

```text
raw/
  ingest-2026-06-09-001/
    collection-1/
      article-61.json
  ingest-2026-06-10-001/
    collection-2/
      article-61.json
      article-88.json
```

这样可以避免不同数据库或不同时间里的 `collection_id=1` 冲突。

### 3.10 Markdown Wiki

粒度：面向人和 LLM 查询的长期知识页面。

典型结构：

```text
knowledge_bases/world-cup/
  index.md
  log.md
  manifest.yaml
  raw/
  wiki/
    evidence.md
    timeline.md
    travel-and-visas.md
    mexico-host-cities.md
    bbc-news.md
```

职责：

- 把 evidence 整理成主题页、实体页、时间线。
- 通过 Obsidian 风格内链形成知识网络。
- 通过外链 citation 保持事实可追溯。

影响范围：

- Wiki 页面是后续 query 的主要检索对象。
- Markdown 页面可以吸收多个 collection 的事实。
- Wiki 页面不应该被某次 collection 全量覆盖，除非显式 rebuild。

## 4. 各层之间如何互相影响

### 4.1 Source 影响 Article

新增 source 后，refresh 会带来新的 article。

```text
source add -> refresh -> articles 增加
```

如果 source 质量低，会影响 search 和 collection 的噪声。

### 4.2 Article 影响 Collection

article 的标题、summary、content_text、source trust、language、topic 会影响 collection 命中和排序。

```text
articles -> search -> collect results
```

正文越完整，search 和 collection 越可能命中深层信息。

### 4.3 Extraction 影响 Search 和 Export

正文提取成功：

- `search` 可以命中正文。
- `export` 的 `content` 更完整。
- Wiki 可总结的事实更丰富。

正文提取失败：

- `export` 仍可导出 summary fallback。
- Wiki 必须标记 `extraction_status`，不能伪装成完整正文。

### 4.4 Collection 影响 JSONL

JSONL 是 collection 的快照。

```text
collection_jobs + collection_results -> export JSONL
```

collection policy 决定了哪些文章进入 Wiki 输入。

### 4.5 JSONL 影响 Wiki

Wiki ingest 只看 JSONL。

```text
JSONL -> raw evidence -> Markdown pages
```

如果 JSONL 缺 citation，Wiki 不应该写入事实。

如果 JSONL 只有 summary，Wiki 只能基于 summary 生成较保守的知识。

### 4.6 Wiki 不反向影响 rsslab

Wiki 是消费层，不应该回写 SQLite。

```text
Wiki 不修改 sources
Wiki 不修改 articles
Wiki 不触发 refresh
Wiki 不触发 extract
```

如果 Wiki 发现证据不足，应回到 rsslab 层重新 collect 或 extract，而不是在 Wiki 阶段联网补资料。

## 5. 持续追踪某个主题时怎么做

假设持续追踪：

```text
wiki_id: world-cup
```

推荐操作模型：

```text
长期维护一个 world-cup Wiki
周期性创建新的 collection
每次 export 一个新的 JSONL bundle
每次 ingest 以增量方式合并到同一个 wiki_id
```

### 5.1 初始建库

```powershell
$env:RSSLAB_DB=".rsslab\world-cup.db"

rsslab source add https://feeds.bbci.co.uk/news/world/rss.xml --topic world --language en --trust-level high
rsslab refresh all
rsslab collect "World Cup" --since 30d --language en --trust-level high --limit 50 --complete-full-text
rsslab export 1 --output evidence\world_cup_collection-1.jsonl
```

然后 ingest 到：

```text
knowledge_bases/world-cup/
```

### 5.2 后续每日或每周更新

```powershell
$env:RSSLAB_DB=".rsslab\world-cup.db"

rsslab refresh all
rsslab collect "World Cup" --since 7d --language en --trust-level high --limit 50 --complete-full-text
rsslab export <new-collection-id> --output evidence\world_cup_2026-06-09.jsonl
```

然后增量 ingest：

```text
bundle: evidence/world_cup_2026-06-09.jsonl
wiki_id: world-cup
mode: incremental
```

### 5.3 子主题专项更新

同一个 Wiki 可以吸收不同 collection：

```powershell
rsslab collect "World Cup visa restrictions" --since 14d --language en --trust-level high --limit 30 --complete-full-text
rsslab export 2 --output evidence\world_cup_visa_restrictions_2026-06-09.jsonl

rsslab collect "World Cup host city security" --since 14d --language en --trust-level high --limit 30 --complete-full-text
rsslab export 3 --output evidence\world_cup_security_2026-06-09.jsonl
```

这两个 collection 都应进入：

```text
knowledge_bases/world-cup/
```

而不是创建两个新的 Wiki。

## 6. 增量更新的推荐规则

### 6.1 raw evidence 追加

不要删除旧 raw。

推荐：

```text
raw/
  ingest-2026-06-09-001/
  ingest-2026-06-10-001/
```

或者至少：

```text
raw/
  collection-1/
  collection-2/
  collection-3/
```

### 6.2 log.md 追加

`log.md` 记录每次 ingest：

```markdown
## 2026-06-09 Ingest

- bundle: evidence/world_cup_2026-06-09.jsonl
- collection_id: 2
- added_articles: 4
- unchanged_articles: 12
- changed_hash_articles: 1
- updated_pages:
  - wiki/travel-and-visas.md
  - wiki/timeline.md
```

### 6.3 Markdown 页面合并

已有页面：

```text
wiki/travel-and-visas.md
```

遇到新 evidence 时追加到：

```markdown
## Updates

### 2026-06-09

- 新证据...
```

不要整页覆盖，除非显式 rebuild。

### 6.4 去重规则

优先级：

```text
canonical_url
citation.url
article_id
content_hash
```

建议策略：

```text
same citation.url + same content_hash
  -> unchanged，跳过重复写入

same citation.url + different content_hash
  -> changed，保留新 raw，log 记录 hash 变化，更新相关页面

new citation.url
  -> added，追加 raw 和 Wiki 条目
```

### 6.5 外链和内链规则

内部链接：

```markdown
[[travel-and-visas|旅行与签证限制]]
[[mexico-host-cities|墨西哥主办城市]]
[[bbc-news|BBC News]]
```

外部 citation：

```markdown
[BBC News, 2026-06-07](https://www.bbc.com/...)
```

原则：

```text
内链负责知识导航
外链负责事实依据
内链不能替代 citation
```

## 7. 哪些层应该稳定，哪些层可以频繁变化

### 7.1 应该稳定

- `wiki_id`
- Wiki 目录结构
- manifest scope
- 主题页命名
- citation 保留规则
- raw evidence 保存规则

这些决定长期可维护性。

### 7.2 可以频繁变化

- collection query
- collection since window
- collection limit
- 新增 sources
- 新的 evidence bundle
- 新的主题页
- timeline 新条目

这些是持续追踪时的自然变化。

### 7.3 需要谨慎变化

- SQLite 数据库文件选择
- source trust_level
- dedupe 规则
- collection ranking 策略
- Wiki rebuild 策略
- cross-wiki link 策略

这些变化会影响审计和可复现性。

## 8. 当前项目还缺什么自动化

当前已经有：

```text
rsslab refresh
rsslab extract
rsslab collect
rsslab export
rsslab-llm-wiki skill rules
```

还缺正式脚本：

```text
rsslab-llm-wiki ingest --mode incremental
rsslab-llm-wiki lint
rsslab-llm-wiki query
```

建议后续实现：

```text
.codex/skills/rsslab-llm-wiki/scripts/ingest_bundle.py
.codex/skills/rsslab-llm-wiki/scripts/lint_wiki.py
.codex/skills/rsslab-llm-wiki/scripts/query_wiki.py
```

其中最重要的是：

```text
ingest_bundle.py --mode incremental
```

它应该负责：

- 校验 JSONL。
- 写 raw evidence。
- 对比旧 raw。
- 检测 duplicate / changed hash。
- 追加 log。
- 合并 Wiki 页面。
- 保留内链和外链。
- 禁止跨 wiki 写入。

## 9. 推荐长期工作流

### 9.1 每次更新时

```powershell
$env:RSSLAB_DB=".rsslab\world-cup.db"

rsslab refresh all
rsslab collect "World Cup" --since 7d --language en --trust-level high --limit 50 --complete-full-text
rsslab export <collection-id> --output evidence\world_cup_<date>_collection-<id>.jsonl
```

然后：

```text
Use $rsslab-llm-wiki to incrementally ingest evidence\world_cup_<date>_collection-<id>.jsonl into wiki_id world-cup under knowledge_bases, preserving internal links and external citations.
```

### 9.2 每次 ingest 后

检查：

- raw 是否追加。
- log 是否追加。
- 新 facts 是否有 citation。
- 主题页是否合并而不是覆盖。
- 重要概念是否有内链。
- 是否没有跨 Wiki 链接。

### 9.3 查询时

优先查：

```text
knowledge_bases/world-cup/wiki/*.md
```

必要时回溯：

```text
knowledge_bases/world-cup/raw/**/article-*.json
```

不要直接回到 SQLite 或 live RSS，除非用户明确要重新采集。

## 10. 一句话总结

如果持续追踪某个主题：

```text
数据库负责积累新闻材料
collection 负责固化每次选材
JSONL 负责交接证据
wiki_id 负责长期知识边界
raw evidence 负责审计
Markdown Wiki 负责阅读、内链和检索
log 负责增量历史
```

正确的增量模式不是“每次覆盖 Wiki”，而是：

```text
每次新增 collection
每次保留 bundle
每次追加 raw
每次追加 log
每次合并主题页
每次保留 citation
```
