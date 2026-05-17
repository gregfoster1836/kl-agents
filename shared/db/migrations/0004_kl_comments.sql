-- Migration 0004: kl_comments (Echo agent)
-- One row per comment captured by an Echo fetcher.
-- Schema selector: SET search_path TO agents_dev (or agents_prod) before running.
--
-- Each comment FK's to its parent kl_post. The orchestrator inserts kl_posts
-- first (gets {post_url: id} map back), then resolves the FK when inserting
-- kl_comments.
--
-- Dedup is enforced at the database via UNIQUE(source, comment_id). This
-- replaces Phase 1's in-Python dedup_key() function. The source prefix is
-- required because comment_id is platform-namespaced (LinkedIn URN vs
-- Facebook numeric id), and the same string could in theory appear on
-- different platforms.

create table if not exists kl_comments (
    id                    uuid primary key default gen_random_uuid(),
    run_id                uuid not null references agent_runs(id) on delete cascade,
    kl_post_id            uuid not null references kl_posts(id) on delete cascade,
    source                text not null check (source in ('li_personal', 'li_page', 'fb_page')),
    comment_id            text not null,
    commenter_name        text not null,
    commenter_profile_url text not null,
    commenter_headline    text,
    comment_text          text not null,
    reaction_count        integer not null default 0 check (reaction_count >= 0),
    captured_at           timestamptz not null,
    created_at            timestamptz not null default now(),
    unique (source, comment_id)
);

create index if not exists idx_kl_comments_run on kl_comments (run_id);
create index if not exists idx_kl_comments_post on kl_comments (kl_post_id);
create index if not exists idx_kl_comments_profile on kl_comments (commenter_profile_url);
create index if not exists idx_kl_comments_captured on kl_comments (captured_at desc);

comment on table kl_comments is
    'Comments on K&L posts. Echo agent. UNIQUE(source, comment_id) enforces dedup at DB layer.';
comment on column kl_comments.commenter_headline is
    'LI tagline or FB bio snippet. This is the input the Haiku classifier sees. May be null on FB.';
comment on column kl_comments.commenter_profile_url is
    'Indexed for the classifier cache-lookup join into kl_commenter_profiles.';
comment on column kl_comments.kl_post_id is
    'FK to the parent K&L post. ON DELETE CASCADE so deleting a post sweeps its comments.';
