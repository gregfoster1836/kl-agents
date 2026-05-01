-- Migration 0002: classified_posts
-- One row per post Scout classified. The review queue.
-- Both above-threshold and below-threshold rows are stored. Filter by review_status downstream.
-- Schema selector: SET search_path TO agents_dev (or agents_prod) before running.
--
-- Source-agnostic: source_metadata holds whatever shape the source needs.
--   Reddit:  {"subreddit": "restaurateur"}
--   YouTube: {"channel_handle": "@RestaurantUnstoppable", "channel_id": "UC...", "video_id": "...", "video_title": "..."}
-- Adding a new source means adding a fetcher that knows how to populate this column. No schema migration needed.

create table if not exists classified_posts (
    id                uuid primary key default gen_random_uuid(),
    run_id            uuid not null references agent_runs(id) on delete cascade,
    source            text not null check (source in ('reddit', 'youtube')),
    source_metadata   jsonb not null default '{}'::jsonb,
    source_url        text not null unique,
    source_id         text not null,
    source_author     text,
    posted_at         timestamptz,
    fetched_at        timestamptz not null default now(),
    title             text,
    body              text,
    ica_stage         text not null check (ica_stage in ('1', '2', '3', 'unclear')),
    confidence        numeric(3, 2) not null check (confidence >= 0 and confidence <= 1),
    signal_type       text,
    key_quote         text,
    reasoning         text,
    review_status     text not null default 'pending'
                      check (review_status in ('pending', 'auto_rejected', 'approved', 'rejected', 'actioned')),
    reviewed_by       text,
    reviewed_at       timestamptz,
    notes             text,
    created_at        timestamptz not null default now()
);

create index if not exists idx_classified_posts_review_status
    on classified_posts (review_status, fetched_at desc);

create index if not exists idx_classified_posts_run
    on classified_posts (run_id);

create index if not exists idx_classified_posts_stage
    on classified_posts (ica_stage, confidence desc);

create index if not exists idx_classified_posts_source
    on classified_posts (source, fetched_at desc);

-- GIN index supports queries like: where source_metadata @> '{"subreddit": "restaurateur"}'
create index if not exists idx_classified_posts_source_metadata
    on classified_posts using gin (source_metadata);

comment on table classified_posts is
    'Posts Scout fetched and classified. review_status drives the human review queue.';
comment on column classified_posts.source is
    'Origin of the post. Constrained to known sources so a typo cannot silently land bad data.';
comment on column classified_posts.source_metadata is
    'Source-specific context. Reddit stores subreddit; YouTube stores channel and video info.';
comment on column classified_posts.source_url is
    'Unique key. Database enforces dedup so concurrent runs cannot insert the same URL twice.';
comment on column classified_posts.ica_stage is
    '1=Marcus (Symptom Aware), 2=Diane (Problem Aware), 3=Ray (Solution/Decision Aware), unclear=ambiguous or non-operator.';
comment on column classified_posts.confidence is
    'Classifier confidence from 0.00 to 1.00. Below the configured threshold marks review_status=auto_rejected.';
comment on column classified_posts.signal_type is
    'Optional false-belief slug from the K&L belief map (e.g. work-harder-fixes-it, inventory-is-busywork). Null for unclear classifications.';
comment on column classified_posts.review_status is
    'pending=above threshold, awaiting human review. auto_rejected=below threshold. approved/rejected/actioned set during review.';
