# Migrations

SQL migrations for the kl-agents Supabase project. Apply in numeric order.

## Files

| File | Purpose |
|------|---------|
| `0001_agent_runs.sql` | One row per agent invocation. Scout writes here at run start and updates at run end. |
| `0002_classified_posts.sql` | One row per classified post. The review queue. |

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

## Verifying

After applying both migrations, this query should return four rows in each schema:

```sql
select schemaname, tablename, indexname
from pg_indexes
where schemaname in ('agents_dev', 'agents_prod')
  and tablename in ('agent_runs', 'classified_posts')
order by schemaname, tablename, indexname;
```

Three indexes on `classified_posts` plus one on `agent_runs` per schema.
