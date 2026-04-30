-- Migration 0001: agent_runs
-- One row per agent invocation. Records what ran, when, what it saw, what it kept.
-- Schema selector: SET search_path TO agents_dev (or agents_prod) before running.

create extension if not exists "pgcrypto";

create table if not exists agent_runs (
    id                    uuid primary key default gen_random_uuid(),
    agent_name            text not null,
    started_at            timestamptz not null default now(),
    finished_at           timestamptz,
    status                text not null check (status in ('running', 'success', 'partial', 'failed')),
    config_snapshot       jsonb not null,
    posts_fetched         integer not null default 0,
    posts_dedup_skipped   integer not null default 0,
    posts_classified      integer not null default 0,
    posts_queued          integer not null default 0,
    error_summary         text,
    created_at            timestamptz not null default now()
);

create index if not exists idx_agent_runs_agent_name_started
    on agent_runs (agent_name, started_at desc);

comment on table agent_runs is
    'One row per agent invocation. Scout writes here at run start and updates at run end.';
comment on column agent_runs.config_snapshot is
    'Full config.yaml at the time of the run, captured for reproducibility.';
comment on column agent_runs.status is
    'running while in progress, success on clean completion, partial when some subreddits failed, failed on hard error.';
