# kl-agents

Knife & Ledger agentic OS. Each agent does one job and writes to a shared Supabase backend.

## Agents

| Agent | Job | Status |
|-------|-----|--------|
| Scout | Reads new posts in restaurant subs on Reddit, classifies them by ICA stage, writes keepers to a review queue. | v0.1 in development |

## Repo layout

```
agents/<agent_name>/    one folder per agent
shared/db/migrations/   SQL migrations, applied to Supabase in order
shared/db/client.py     supabase-py wrapper, used by every agent
shared/prompts/         classification prompts shared across agents
scripts/                one-shot runners for manual verification
tests/                  pytest suites per agent
```

## Setup

1. Python 3.12+. Confirm with `python3.12 --version`.
2. From the repo root: `make install-dev`. Installs Scout in editable mode plus dev tools.
3. Copy `.env.example` to `.env` and fill in credentials.
4. Run migrations against Supabase (instructions in `shared/db/migrations/README.md`).
5. Start with the smoke test: `make smoke`.

## Running Scout

```
make scout                                   # standard run, reads config.yaml
python -m agents.scout.main --dry-run        # fetch and classify, do not write
python -m agents.scout.main --subreddit restaurateur --limit 10
python -m agents.scout.main --config alt.yaml
```

Exit codes: `0` success, `1` partial failure (some subreddits failed), `2` total failure.

## Standards

- Python 3.12, type-checked with `mypy --strict`, linted and formatted with `ruff`.
- All log output is structured JSON to stdout. No emoji, no progress bars.
- Operator language over consultant language. No em-dashes anywhere.
