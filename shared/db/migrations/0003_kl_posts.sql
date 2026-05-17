-- Migration 0003: kl_posts (Echo agent)
-- One row per K&L post (LI Personal, LI Page, FB Page) that comments hang from.
-- Schema selector: SET search_path TO agents_dev (or agents_prod) before running.
--
-- Echo (Agent 2) is the K&L engagement-feed: it scrapes Greg's own LinkedIn and
-- Facebook posts plus the comments on them. kl_posts is the substrate; the
-- comments themselves live in kl_comments and FK back here.
--
-- Dedup is enforced at the database via UNIQUE(post_url). Re-running the same
-- day returns the existing row's id rather than inserting a duplicate.

create table if not exists kl_posts (
    id                uuid primary key default gen_random_uuid(),
    run_id            uuid not null references agent_runs(id) on delete cascade,
    source            text not null check (source in ('li_personal', 'li_page', 'fb_page')),
    post_url          text not null unique,
    post_id           text not null,
    author_name       text,
    headline_excerpt  text,
    posted_at         timestamptz,
    captured_at       timestamptz not null default now(),
    created_at        timestamptz not null default now()
);

create index if not exists idx_kl_posts_run on kl_posts (run_id);
create index if not exists idx_kl_posts_source_captured on kl_posts (source, captured_at desc);

comment on table kl_posts is
    'K&L posts (substrate). Echo agent. One row per LI Personal, LI Page, or FB Page post.';
comment on column kl_posts.post_url is
    'Unique key. UPSERT on conflict returns existing id so re-runs do not duplicate posts.';
comment on column kl_posts.headline_excerpt is
    'First ~80 chars of the post body. Stored so the brief renderer does not need to re-scrape.';
comment on column kl_posts.source is
    'Where this post lives. Constrained so a typo cannot silently land bad data.';
