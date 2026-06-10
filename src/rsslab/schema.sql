create table if not exists sources (
    id integer primary key autoincrement,
    feed_url text not null unique,
    site_url text not null default '',
    title text not null default '',
    description text not null default '',
    source_name text not null default '',
    source_type text not null default '',
    topics text not null default '',
    language text not null default '',
    trust_level text not null default '',
    refresh_interval_seconds integer not null default 3600,
    last_fetched_at text,
    etag text,
    last_modified text,
    last_error text,
    created_at text not null,
    updated_at text not null
);

create table if not exists articles (
    id integer primary key autoincrement,
    source_id integer not null references sources(id) on delete cascade,
    guid text not null default '',
    url text not null default '',
    canonical_url text not null default '',
    title text not null default '',
    author text not null default '',
    published_at text not null,
    fetched_at text not null,
    summary_from_rss text not null default '',
    content_text text not null default '',
    content_html text not null default '',
    raw_entry_json text not null default '',
    raw_html_path text not null default '',
    content_hash text not null default '',
    dedupe_key text not null unique,
    extraction_status text not null default 'pending',
    extraction_error text not null default '',
    extraction_attempted_at text,
    is_read integer not null default 0,
    is_starred integer not null default 0,
    created_at text not null,
    updated_at text not null
);

create index if not exists idx_articles_source_id on articles(source_id);
create index if not exists idx_articles_published_at on articles(published_at);

create table if not exists collection_jobs (
    id integer primary key autoincrement,
    query text not null,
    since text,
    languages_json text not null default '[]',
    trust_levels_json text not null default '[]',
    topics_json text not null default '[]',
    limit_count integer not null,
    complete_full_text integer not null default 0,
    policy_json text not null,
    status text not null default 'completed',
    result_count integer not null default 0,
    created_at text not null,
    updated_at text not null
);

create table if not exists collection_results (
    id integer primary key autoincrement,
    collection_job_id integer not null references collection_jobs(id) on delete cascade,
    article_id integer not null references articles(id) on delete cascade,
    rank integer not null,
    score real not null default 0.0,
    selection_reason text not null default '',
    content_hash_at_collection text not null default '',
    extraction_status_at_collection text not null default '',
    created_at text not null,
    unique(collection_job_id, article_id)
);

create index if not exists idx_collection_results_job_id on collection_results(collection_job_id);
create index if not exists idx_collection_results_article_id on collection_results(article_id);
