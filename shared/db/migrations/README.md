# Migrations

SQL migrations for the kl-agents Supabase project. Apply in numeric order.

## Files

| File | Purpose |
|------|---------|
| `0001_agent_runs.sql` | One row per agent invocation. Scout writes here at run start and updates at run end. |
| `0002_classified_posts.sql` | One row per classified post. The review queue. Source-agnostic via `source_metadata` jsonb. |

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

## Re-applying after a schema change (when no production data exists)

While the project has no real data, schema changes can be applied by dropping
and recreating the tables. This is faster than writing ALTER migrations and
keeps the migration history clean.

For each schema:

```sql
set search_path to agents_dev;  -- or agents_prod
drop table if exists classified_posts cascade;
drop table if exists agent_runs cascade;
-- then paste 0001 followed by 0002
```

Once production data exists, every change must be a new numbered migration.

## Verifying

After applying both migrations, this query should return four rows total
(two tables in each schema):

```sql
select schemaname, tablename
from pg_tables
where schemaname in ('agents_dev', 'agents_prod')
  and tablename in ('agent_runs', 'classified_posts')
order by schemaname, tablename;
```

For a deeper check including indexes:

```sql
select schemaname, tablename, indexname
from pg_indexes
where schemaname in ('agents_dev', 'agents_prod')
  and tablename in ('agent_runs', 'classified_posts')
order by schemaname, tablename, indexname;
```

Each schema should have:
- 1 index on `agent_runs` (idx_agent_runs_agent_name_started)
- 5 indexes on `classified_posts` (review_status, run, stage, source, source_metadata GIN)
- Plus the implicit primary-key indexes on each table
