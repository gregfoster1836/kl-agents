-- Migration 0005: kl_commenter_profiles (Echo agent classifier cache)
-- One row per distinct commenter profile_url across all sources.
-- Schema selector: SET search_path TO agents_dev (or agents_prod) before running.
--
-- The Haiku 4.5 classifier sees a commenter's headline (LI tagline / FB bio
-- snippet) and emits one of five classes: operator, vendor, consultant, peer,
-- unknown. We cache that classification keyed by profile_url, with the
-- headline_hash recorded so a future run can detect when the headline drifted
-- and trigger reclassification.
--
-- retry_next_run is set when a classifier API call failed transiently
-- (rate limit, timeout). A partial index on the column makes "find the
-- retries" instant; the orchestrator picks them up at the start of each
-- run.

create table if not exists kl_commenter_profiles (
    profile_url        text primary key,
    commenter_class    text not null check (commenter_class in ('operator', 'vendor', 'consultant', 'peer', 'unknown')),
    headline_hash      text not null,
    headline_excerpt   text,
    rationale          text,
    model_id           text not null,
    classified_at      timestamptz not null default now(),
    retry_next_run     boolean not null default false,
    cost_usd           numeric(10, 6) not null default 0
);

create index if not exists idx_kl_commenter_profiles_class on kl_commenter_profiles (commenter_class);
create index if not exists idx_kl_commenter_profiles_retry on kl_commenter_profiles (retry_next_run) where retry_next_run = true;

comment on table kl_commenter_profiles is
    'Classifier cache. One row per unique profile_url. Reclassification triggered by headline_hash drift.';
comment on column kl_commenter_profiles.profile_url is
    'Natural primary key. One row per LinkedIn or Facebook profile we have ever classified.';
comment on column kl_commenter_profiles.commenter_class is
    'operator=hands-on restaurant owner/GM. vendor=sells to restaurants. consultant=advises restaurants. peer=industry but not above. unknown=cannot tell from headline.';
comment on column kl_commenter_profiles.headline_hash is
    'SHA-256 of normalized (lowercased, whitespace-collapsed) headline. Drift triggers reclassification.';
comment on column kl_commenter_profiles.retry_next_run is
    'True when the classifier failed transiently. Next run picks these up via the partial index and retries.';
comment on column kl_commenter_profiles.cost_usd is
    'One-call cost for audit. Sum across today to enforce the daily cost guardrail.';
