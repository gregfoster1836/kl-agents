-- Migration 0006: enable RLS on Echo tables
-- Schema selector: SET search_path TO agents_dev (or agents_prod) before running.
--
-- Scout's tables (agent_runs, classified_posts) have RLS enabled by Supabase
-- default. Echo's three tables were created without it, producing a Supabase
-- security advisory. This migration brings Echo's posture in line with Scout's.
--
-- No CREATE POLICY statements are needed. The agent code uses the
-- service_role key, which has the BYPASSRLS attribute by default in Supabase.
-- Anon and authenticated roles get zero rows back from any query against
-- these tables, which is the intended behavior: Echo data is never meant
-- to be exposed via client-side Supabase libraries.
--
-- See shared/db/client.py: "RLS is bypassed; this code only runs from the
-- agent's own controlled environment, never from anywhere user-facing."

alter table kl_posts enable row level security;
alter table kl_comments enable row level security;
alter table kl_commenter_profiles enable row level security;
