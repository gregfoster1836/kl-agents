-- Migration 0008: agent_runs metrics column (+ relax listener-shaped counts)
-- Schema selector: SET search_path TO agents_dev (or agents_prod) before running.
--
-- Why: agent_runs (0001) hardcodes four LISTENER counts
-- (posts_fetched, posts_dedup_skipped, posts_classified, posts_queued, all
-- NOT NULL DEFAULT 0). Scout fills them; a non-listener agent (Validation
-- fetches/classifies nothing) would write permanent zeros - a meaningful-
-- looking lie. The agent platform contract (Bucket 3) owns the UNIVERSAL
-- columns; each agent writes its own work-specific numbers into `metrics`.
--
-- This migration is ADDITIVE + RELAXING - no data loss:
--   1. add `metrics jsonb not null default '{}'`
--   2. relax the four count columns to nullable (drop NOT NULL + default),
--      mark them deprecated. Existing Scout rows keep their real values.
--   3. backfill `metrics` for existing Scout rows from their count columns so
--      a metrics-based report does not silently zero historical run totals.
--   4. rewrite the listener-biased `status` comment to be agent-neutral.
-- Physically dropping the deprecated columns happens in a LATER migration,
-- once Echo + any dashboards no longer read them.

-- 1. The universal per-agent metrics bag.
alter table agent_runs
    add column if not exists metrics jsonb not null default '{}';

comment on column agent_runs.metrics is
    'Per-agent work metrics as flat JSONB scalars (e.g. Scout: posts_fetched/posts_dedup_skipped/posts_classified/posts_queued). The contract owns the universal columns; each agent owns its own metrics here. Replaces the deprecated posts_* count columns.';

-- 2. Relax the four listener counts: nullable, no default, deprecated. A
--    non-listener agent simply leaves them null instead of writing fake zeros.
alter table agent_runs alter column posts_fetched       drop not null;
alter table agent_runs alter column posts_fetched       drop default;
alter table agent_runs alter column posts_dedup_skipped drop not null;
alter table agent_runs alter column posts_dedup_skipped drop default;
alter table agent_runs alter column posts_classified    drop not null;
alter table agent_runs alter column posts_classified    drop default;
alter table agent_runs alter column posts_queued        drop not null;
alter table agent_runs alter column posts_queued        drop default;

comment on column agent_runs.posts_fetched is
    'DEPRECATED (migration 0008): Scout-shaped listener count. Use metrics->>''posts_fetched''. Kept nullable for history + transition mirror-write; dropped in a later migration.';
comment on column agent_runs.posts_dedup_skipped is
    'DEPRECATED (migration 0008): use metrics->>''posts_dedup_skipped''.';
comment on column agent_runs.posts_classified is
    'DEPRECATED (migration 0008): use metrics->>''posts_classified''.';
comment on column agent_runs.posts_queued is
    'DEPRECATED (migration 0008): use metrics->>''posts_queued''.';

-- 3. Backfill metrics for existing Scout rows from their count columns, so any
--    new metrics-based report retains historical run totals. Only rows that
--    have not already been given a metrics payload (metrics = '{}'::jsonb) and
--    that actually have counts recorded.
update agent_runs
set metrics = jsonb_build_object(
        'posts_fetched',       posts_fetched,
        'posts_dedup_skipped', posts_dedup_skipped,
        'posts_classified',    posts_classified,
        'posts_queued',        posts_queued
    )
where agent_name = 'scout'
  and metrics = '{}'::jsonb
  and posts_fetched is not null;

-- 4. The status semantics are no longer listener-specific.
comment on column agent_runs.status is
    'running while in progress, success on clean completion, partial when useful work completed but >=1 non-fatal unit failed (agents that cannot partially fail never emit it), failed on hard error.';
