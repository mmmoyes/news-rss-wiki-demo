# rsslab 中文介绍

`rsslab` 是一个面向 RSS/Atom 新闻采集的 Python 3.11+ 命令行工具。它用于管理新闻源、刷新订阅、规范化文章元数据、在本地 SQLite 中保存文章，并支持本地搜索和按需正文提取。

这个项目的定位不是传统 RSS 阅读器，也不是图形界面应用、后台守护进程、云同步服务、多用户系统、LLM 摘要工具或导出流水线。当前实现重点是为后续新闻研究、资料整理或 LLM Wiki 输入流程准备可追溯的本地新闻数据。

## 当前能力

- 管理 RSS/Atom 新闻源：添加、列出、删除。
- 刷新全部新闻源或指定新闻源。
- 解析 RSS/Atom 条目，并规范化标题、URL、作者、发布时间、摘要、原始条目 JSON、内容哈希和去重键。
- 对常见跟踪参数做 URL 规范化，减少重复入库。
- 修复缺失标题、缺失发布时间、URL 控制字符等 Feed 条目问题。
- 使用本地 SQLite 保存新闻源和文章。
- 对重复文章执行更新，同时保留 `is_read` 和 `is_starred` 状态。
- 支持本地文章搜索，搜索范围包含标题、作者、来源名称、RSS 摘要和已提取正文。
- 优先使用 SQLite FTS5 全文检索；环境不支持 FTS5 时自动回退到 `LIKE` 查询。
- 使用 `trafilatura` 按需提取文章正文。
- 正文提取失败或无正文时回退到 RSS 摘要，并记录提取状态和错误信息。

## 安装

在项目根目录执行：

```bash
python -m pip install -e .[test]
```

运行测试：

```bash
python -m pytest
```

## 数据库位置

默认 SQLite 数据库路径：

```text
.rsslab/rsslab.db
```

可以通过 `RSSLAB_DB` 指定其他数据库文件。例如在 PowerShell 中：

```powershell
$env:RSSLAB_DB=".rsslab\dev.db"
```

## 命令列表

```bash
rsslab source add <feed-url> --topic <topic> --language <lang> --trust-level <level>
rsslab source list
rsslab source remove <source-id>

rsslab refresh all
rsslab refresh source <source-id>

rsslab search <query> --since 7d --limit 20

rsslab extract article <article-id>
rsslab extract missing --limit 100
```

## 使用示例

添加 BBC World 新闻源：

```bash
rsslab source add https://feeds.bbci.co.uk/news/world/rss.xml --topic world --language en --trust-level high
```

刷新全部新闻源：

```bash
rsslab refresh all
```

查看已添加的新闻源：

```bash
rsslab source list
```

刷新指定新闻源：

```bash
rsslab refresh source 1
```

搜索本地文章：

```bash
rsslab search "Ukraine" --limit 10
```

提取单篇文章正文：

```bash
rsslab extract article 1
```

批量提取尚未提取正文的文章：

```bash
rsslab extract missing --limit 10
```

## 正文提取状态

文章正文提取会写入 `articles` 表的相关字段，包括 `content_text`、`content_html`、`content_hash`、`extraction_status`、`extraction_error` 和 `extraction_attempted_at`。

当前状态值包括：

- `pending`：尚未尝试提取。
- `success`：正文提取成功。
- `fallback_summary`：正文为空，已回退到 RSS 摘要。
- `failed`：抓取或提取失败，已记录错误并回退到 RSS 摘要。
- `skipped_no_url`：文章没有 URL，直接使用 RSS 摘要。

`extract missing` 会跳过近期失败的文章，避免短时间内重复无效重试。

## 项目结构

```text
src/rsslab/
  cli.py        Typer 命令行入口
  services.py   新闻源管理与刷新编排
  rss.py        HTTP 拉取逻辑
  parser.py     RSS/Atom 解析与条目规范化
  dedupe.py     URL 规范化、内容哈希和去重键
  db.py         SQLite 连接、初始化和 FTS 支持
  search.py     本地搜索
  extractor.py  正文提取
  schema.sql    数据库 schema

tests/          单元测试与 CLI 测试
```

## 已完成阶段

### Phase 1

- Python 包结构和 Typer CLI。
- SQLite `sources` 和 `articles` 表。
- 新闻源添加、列表和删除。
- RSS/Atom 拉取、解析和文章规范化。
- URL 规范化与文章去重。
- 刷新时新增或更新文章。

### Phase 2

- 正文相关字段和提取状态字段。
- SQLite FTS5 搜索及 `LIKE` 回退。
- 本地文章搜索。
- 单篇和批量正文提取。
- 提取失败时回退到 RSS 摘要。
- 对近期失败提取任务做短期重试抑制。

## 尚未实现

后续阶段目前仍在范围外：

- `collect` 采集任务。
- JSONL 导出。
- `refresh due`。
- ETag / Last-Modified 条件请求。
- 后台守护进程或调度器。
- LLM 摘要或 Wiki 生成。
