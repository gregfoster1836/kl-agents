-- Migration 0007: expose agents_dev + agents_prod to PostgREST
--
-- PROJECT-GLOBAL migration — NOT per-schema. Do NOT wrap this in
-- `set search_path to agents_dev`. Every statement below is applied ONCE for
-- the whole Supabase project, not once per schema.
--
-- Why this exists: the agent code (Scout, Echo) reaches Supabase through the
-- PostgREST REST API with `Accept-Profile: agents_dev` (see shared/db/client.py
-- + SUPABASE_SCHEMA in .env). By default PostgREST only exposes `public` and
-- `graphql_public`, so any REST call against agents_dev/agents_prod fails with:
--
--     PGRST106: Invalid schema: agents_dev
--     hint: Only the following schemas are exposed: public, graphql_public
--
-- The tables existed the whole time; they just weren't routable. This migration
-- adds both agent schemas to PostgREST's exposed-schema list and grants the API
-- roles the privileges they need to use them. Captured 2026-06-03 after a live
-- Scout run hit PGRST106 at start_run; applied live to fix it, then recorded
-- here so a project reset / config churn can't silently revert it.
--
-- NOTE: Supabase also surfaces "Exposed schemas" as a dashboard toggle
-- (Settings → API). This migration is the SQL-of-record equivalent so the
-- setting is durable and reproducible. If the dashboard list is ever reset,
-- re-running this migration restores it.

-- 1. Add both agent schemas to PostgREST's exposed-schema list. PostgREST reads
--    this from the `authenticator` role's pgrst.db_schemas setting. Keep the
--    defaults (public, graphql_public) so existing routes keep working.
alter role authenticator set pgrst.db_schemas = 'public, graphql_public, agents_dev, agents_prod';

-- 2. The API roles must be able to USE the schemas for PostgREST to route to
--    them. service_role (used by the agents) also needs table/sequence
--    privileges. anon/authenticated get USAGE only; row visibility is still
--    governed by RLS (see migration 0006 — service_role bypasses, others see
--    zero rows).
grant usage on schema agents_dev  to anon, authenticated, service_role;
grant usage on schema agents_prod to anon, authenticated, service_role;

grant all on all tables    in schema agents_dev  to service_role;
grant all on all sequences in schema agents_dev  to service_role;
grant all on all tables    in schema agents_prod to service_role;
grant all on all sequences in schema agents_prod to service_role;

-- 3. Future tables created in these schemas should inherit the same grant so a
--    later migration doesn't silently lock service_role out.
alter default privileges in schema agents_dev  grant all on tables    to service_role;
alter default privileges in schema agents_dev  grant all on sequences to service_role;
alter default privileges in schema agents_prod grant all on tables    to service_role;
alter default privileges in schema agents_prod grant all on sequences to service_role;

-- 4. Reload PostgREST so the new exposed-schema list takes effect immediately
--    (otherwise it applies on the next PostgREST restart).
notify pgrst, 'reload config';
notify pgrst, 'reload schema';
