# Migrations

SQL migrations for the kl-agents Supabase project. Apply in numeric order.

## Files

| File | Purpose |
|------|---------|
| `0001_agent_runs.sql` | One row per agent invocation. Scout AND Echo write here at run start and update at run end (filtered by `agent_name`). |
| `0002_classified_posts.sql` | One row per classified post. Scout's review queue. Source-agnostic via `source_metadata` jsonb. |
| `0003_kl_posts.sql` | Echo: one row per K&L post (LI Personal, LI Page, FB Page) that comments hang from. |
| `0004_kl_comments.sql` | Echo: one row per comment on a K&L post. UNIQUE(source, comment_id) enforces dedup. |
| `0005_kl_commenter_profiles.sql` | Echo: classifier cache. One row per distinct commenter profile_url. Partial index on `retry_next_run`. |
| `0006_echo_rls.sql` | Echo: enable RLS on the three Echo tables to match Scout's posture. service_role bypasses by default; anon/authenticated get zero rows. |
| `0007_expose_schemas.sql` | **Project-global (NOT per-schema).** Adds `agents_dev` + `agents_prod` to PostgREST's exposed-schema list and grants the API roles USAGE + service_role table/sequence privileges (incl. default privileges for future tables). Without it, REST calls fail `PGRST106: Invalid schema`. Apply ONCE for the whole project — do not wrap in `set search_path`. |
| `0008_agent_runs_metrics.sql` | Per-schema. Adds `metrics jsonb not null default '{}'` to `agent_runs`; relaxes the four Scout-shaped count columns (`posts_*`) to nullable + deprecated; backfills `metrics` from those counts for existing Scout rows; rewrites the `status` comment agent-neutral. The agent-platform contract (Bucket 3) owns the universal columns; each agent writes its own metrics into `metrics`. Applied to agents_dev + agents_prod 2026-06-22. Physically dropping the deprecated `posts_*` columns is a later migration, after Echo + dashboards stop reading them. |

## How to apply

Two schemas live in one Supabase project: `agents_dev` for development and
`agents_prod` for scheduled runs. Apply each migration to both schemas.

### Setup (one time, on a fresh project)

In the Supabase SQL editor, create both schemas:

```sql
create schema if not exists agents_dev;
create schema if not exists agents_prod;
```

### Apply a migration

For each schema, run:

```sql
set search_path to agents_dev;  -- or agents_prod
-- paste the contents of the migration file here
```

The `gen_random_uuid()` calls require the `pgcrypto` extension. Migration 0001
creates it if missing.

### Project-global migrations (0007+)

Some migrations configure the project as a whole, not a single schema.
`0007_expose_schemas.sql` is the first of these. Run it **once, with no
`search_path` set** — its statements (`alter role authenticator`, schema-level
grants, `notify pgrst`) apply project-wide. Running it under a per-schema
`search_path` is harmless but unnecessary. On a fresh project, apply it after
the per-schema table migrations (0001–0006) so the grant-on-all-tables
statements actually find tables to grant on.

## Re-applying after a schema change (when no production data exists)

While the project has no real data, schema changes can be applied by dropping
and recreating the tables. This is faster than writing ALTER migrations and
keeps the migration history clean.

For each schema:

```sql
set search_path to agents_dev;  -- or agents_prod
drop table if exists kl_commenter_profiles cascade;
drop table if exists kl_comments cascade;
drop table if exists kl_posts cascade;
drop table if exists classified_posts cascade;
drop table if exists agent_runs cascade;
-- then paste 0001 → 0002 → 0003 → 0004 → 0005 in order
```

Order matters: 0002 FK's to 0001; 0003 FK's to 0001; 0004 FK's to both 0001 and 0003. 0005 stands alone (natural key, no FKs).

Once production data exists, every change must be a new numbered migration.

## Verifying

After applying all migrations, this query should return ten rows total
(five tables in each schema):

```sql
select schemaname, tablename
from pg_tables
where schemaname in ('agents_dev', 'agents_prod')
  and tablename in ('agent_runs', 'classified_posts', 'kl_posts', 'kl_comments', 'kl_commenter_profiles')
order by schemaname, tablename;
```

For a deeper check including indexes:

```sql
select schemaname, tablename, indexname
from pg_indexes
where schemaname in ('agents_dev', 'agents_prod')
  and tablename in ('agent_runs', 'classified_posts', 'kl_posts', 'kl_comments', 'kl_commenter_profiles')
order by schemaname, tablename, indexname;
```

Each schema should have:
- 1 index on `agent_runs` (idx_agent_runs_agent_name_started)
- 5 indexes on `classified_posts` (review_status, run, stage, source, source_metadata GIN)
- 2 indexes on `kl_posts` (run, source+captured)
- 4 indexes on `kl_comments` (run, post, profile, captured)
- 2 indexes on `kl_commenter_profiles` (class, partial on retry_next_run)
- Plus the implicit primary-key indexes on each table
