---
date: 2026-05-08
session_type: Agentic OS infrastructure
asset: Scout (Agent 1) — kl-agents repo
status: YouTube fetcher live and verified. Reddit fetcher built but blocked on API approval (resubmission queued for 2026-05-09).
related: kl-agents repo at https://github.com/gregfoster1836/kl-agents, Supabase project kl-agents (zbokrrcexjecrkpogjqv)
---

# Session Summary — Scout (Agent 1) Build + Reddit API Path

## What we did this session

Built Agent 1 of the K&L agentic OS from blank slate to "live YouTube data flowing, Reddit gated on API approval." Spans 2026-04-30 through 2026-05-08 across multiple sit-downs.

**Agent purpose:** Scout monitors public posts and comments from restaurant operators on Reddit and YouTube, classifies each one against the K&L ICA framework (Marcus / Diane / Ray + unclear), and writes the keepers to a Supabase review queue. The first agent in a longer pipeline. It does not do outreach or publish anything. Its only job is to populate the review queue Greg uses to inform the K&L blog.

## Architecture decisions locked

- **New standalone repo** at `/Users/gregfoster/00-coding/active/03 KL Agents/` (separate from vault, separate from operator platform). Public on GitHub at https://github.com/gregfoster1836/kl-agents as of 2026-05-06.
- **New Supabase project** `kl-agents` (project ref `zbokrrcexjecrkpogjqv`), West US, free tier. NOT shared with the operator platform's customer database.
- **Two schemas** in one project: `agents_dev` and `agents_prod`.
- **Source-agnostic schema** via `source_metadata jsonb` column. Reddit stores `{"subreddit": ...}`, YouTube stores `{"channel_handle, channel_id, video_id, video_title}`. Adding source #3 later means a new fetcher and a config block, not a schema migration.
- **Python 3.12** with ruff, mypy --strict, pytest. PRAW for Reddit, google-api-python-client for YouTube.
- **Threshold 0.6** for classifier confidence (next session). Below-threshold rows kept in DB with `review_status='auto_rejected'` so the corpus exists for prompt tuning.
- **Dedup forever** by `source_url`.
- **Skip removed/deleted posts.** `max_age_days: 30` filter on every source.

## What got built

**Repo (6 commits on main):**
1. `c0ec0b0` — scaffold (directory tree, configs, no logic)
2. `b4c6d7a` — initial migrations (later edited in place)
3. `f930eb2` — Reddit fetcher, config loader, JSON logging, smoke script
4. `4f965c7` — 11 fetcher unit tests, fixed logger swallowing extras
5. `19286f6` — multi-source refactor: schema, models, config, Fetcher protocol
6. `345422c` — YouTube fetcher with 16-test suite, validated channel list, live smoke

**Code:**
- `agents/scout/models.py` — `FetchedPost`, `Classification` dataclasses, `Source` StrEnum
- `agents/scout/config.py` — typed Config, `load()` / `load_reddit_only()` / `load_youtube_only()`
- `agents/scout/logging_setup.py` — JSON formatter, structured stdout logging
- `agents/scout/fetchers/base.py` — `Fetcher` Protocol and `FetchError` base class
- `agents/scout/fetchers/reddit.py` — PRAW read-only client, filters removed/deleted/old/empty
- `agents/scout/fetchers/youtube.py` — Google API client, channel-handle resolution, video listing, comment fetching with comments-disabled handling
- `scripts/smoke_reddit_fetch.py` — gated on Reddit API approval
- `scripts/smoke_youtube_fetch.py` — verified live
- `tests/scout/test_reddit_fetcher.py` — 12 tests, all green
- `tests/scout/test_youtube_fetcher.py` — 16 tests, all green

**Database:** SQL migrations applied to both `agents_dev` and `agents_prod`. Tables `agent_runs` and `classified_posts` confirmed via `pg_tables` query.

**Quality gates:** ruff clean, ruff format clean (20 files), mypy --strict clean (14 source files), pytest 28/28.

## Channel list — validated against live YouTube API on 2026-05-01

18 final channels after live validation surfaced three broken handles in initial config. Three handles changed:

| Original | Replaced with | Why |
|---|---|---|
| `@TheRestaurantCoach` | `@Therestaurantboss` | Original resolved to dormant 24-sub "Howard Tinker" channel. The actual Ryan Gromfin channel has 144k subs. |
| `@7shifts` | `@7shiftsinc` | Original did not resolve. |
| `@chefwilyeung` | removed entirely | Did not resolve under any case variant (`@chefwilyeung`, `@ChefWilYeung`, `@WilYeung`). |

Full list: 11 Tier 1 (operator-voice + trade press), 5 Tier 2 (platform vendors and adjacent), 2 Tier 2 limited capture (Drew Talbert and Waiter There's More with 1 video × 25 comments per run to cap noise).

## Live observation — operator-coaching channels mostly have comments disabled

Hit `@RestaurantUnstoppable`, `@Therestaurantboss`, `@DavidScottPeters` live. All returned **zero comments** on recent videos. Likely comments disabled or heavily moderated. This isn't a bug, it's the actual landscape.

What this means for Scout's signal sources:
- Reddit (when approved) will be the primary operator-voice channel
- Platform vendors (Toast, Restaurant365, 7shifts) where operators come to ask questions
- Trade press (Restaurant Business, NRN) where operators sometimes weigh in
- High-volume comedy channels (Drew Talbert, Waiter There's More) for the rare operator gem in the noise

End-to-end YouTube smoke succeeded against `@DrewTalbert`: 5 real comments fetched, parsed, all `FetchedPost` fields populated correctly. Confirmed the fetcher and the API integration work end-to-end.

## Reddit — denied once, resubmission queued

**First submission 2026-04-30** under `u/SparkyMcCrinkle`. Denied 2026-05-02 with the standard non-detailed boilerplate ("not in compliance with Responsible Builder Policy and/or lacks necessary details"). Per public reports, this denial language is the new normal for small/personal projects under Reddit's 2025 RBP regime.

**Probable rejection reasons (no specific feedback provided):**
- Use case framed as "research bot for blog content" reads as commercial scraping
- Private repo with no public verification surface
- Three subreddits including `r/smallbusiness` (3M+ members, frequent rejection trigger)
- No registered-business framing

**Resubmission ready for 2026-05-09** (7-day cooldown observed). Stronger application:
- Knife & Ledger LLC framing with public website and blog
- Source code now public at https://github.com/gregfoster1836/kl-agents (made public 2026-05-06 after security check confirmed `.env` was never tracked)
- Two subreddits: r/restaurateur, r/KitchenConfidential. Dropped r/smallbusiness.
- Volume spelled out: 100 reads/day total, one sequential pass, no concurrent requests
- Use case: "content research for our publicly-published educational blog" not "research bot"
- Read-only PRAW with app-only OAuth. No user account credentials.
- Estimated odds of approval: ~70% based on patterns of approved resubmissions

## Security incident and recovery

During Supabase setup on 2026-04-30, Greg pasted the service-role key into `.env.example` (the public template) instead of `.env` (the gitignored real file). Caught before any commit. Reverted the file to its blank template state, copied the real values into `.env`, and rotated the Supabase service-role key out of caution. New key never exposed.

**Lesson baked in:** the `.env.example` file must stay blank. Real secrets live in `.env` which is gitignored. Greg's `.env` now has a `.example` suffix on the template only, and the project follows the rule that any credential touching a chat transcript or a tracked file is rotated.

## External resources set up

- **Supabase project** `kl-agents` at `zbokrrcexjecrkpogjqv.supabase.co` — both schemas, all four tables, GIN index on `source_metadata`
- **Google Cloud project** `kl-agents` — YouTube Data API v3 enabled, API key `kl-scout-youtube` validated live
- **Public GitHub repo** at https://github.com/gregfoster1836/kl-agents
- **Reddit script app** — pending. Will register at https://www.reddit.com/prefs/apps once API access is approved.

## Files Greg should not change without me

- `/Users/gregfoster/00-coding/active/03 KL Agents/.env` — credentials only, no other edits
- `/Users/gregfoster/00-coding/active/03 KL Agents/.env.example` — template, must stay blank
- `/Users/gregfoster/00-coding/active/03 KL Agents/shared/db/migrations/*.sql` — already applied. While no production data exists, drop-and-recreate is fine. Once data exists, every change is a NEW numbered migration.

## Open / pending — next session resumes here

**Three branches based on what unblocks first:**

1. **If Reddit API approval arrives** (Greg resubmits 2026-05-09, response ~7 days): walk through script app registration at reddit.com/prefs/apps, paste credentials into `.env`, run `python scripts/smoke_reddit_fetch.py --subreddit restaurateur --limit 5`. First end-to-end Reddit verification.

2. **Storage layer** (no external blocker): build `shared/db/client.py` (supabase-py singleton), `agents/scout/storage/runs.py`, `agents/scout/storage/posts.py`. Schema is locked, this is straightforward.

3. **Classifier** (no external blocker): write `agents/scout/classifier/ica.py`. Claude API call against `claude-sonnet-4-5`. Lock the canonical `signal_type` slug list (drawn from the 10 false beliefs in K&L messaging Part VII). Output schema matches `Classification` dataclass.

**Then the orchestrator:** `agents/scout/main.py` glue that iterates enabled sources, calls each fetcher, feeds the classifier, writes to storage. CLI flags for `--source`, `--dry-run`, `--limit`.

**Decision deferred:** cron / scheduling. Skip until end-to-end is verified. Then decide between launchd, GitHub Actions, or Vercel Cron.

## Persistence

Reference card lives at `~/.claude/projects/-Users-gregfoster-Desktop-K-L-Vault/memory/reference_scout.md` (auto-memory, indexed in MEMORY.md). Full handoff at `/Users/gregfoster/00-coding/active/00 K&L Vault/memory/handoff_kl-agents-scout.md`. Both kept current as of end-of-session 2026-05-08.

## Continuation prompt for next session

```
Resume Scout work in /Users/gregfoster/00-coding/active/03 KL Agents/.

Context: Agent 1 of K&L agentic OS, multi-source (Reddit + YouTube).
6 git commits on main. 28 pytest tests passing. mypy --strict clean
over 14 source files. Supabase kl-agents (zbokrrcexjecrkpogjqv) has
multi-source schema in both agents_dev and agents_prod. YouTube
fetcher live and verified. Repo public at
https://github.com/gregfoster1836/kl-agents.

Reddit: first request denied 2026-05-02. Resubmission queued for
2026-05-09 with stronger application (registered-business framing,
public source code, fewer subs). ~7-day response window.

Read these first:
- memory/reference_scout.md (auto-memory): commands, credentials, status
- memory/handoff_kl-agents-scout.md (vault memory/): full session state

Branch on what's available:
1. Reddit approval email arrived (gfloss381@gmail.com)?
   → Walk app registration, paste creds, run smoke_reddit_fetch.py
2. Else, build the storage layer (shared/db/client.py +
   agents/scout/storage/runs.py + agents/scout/storage/posts.py)
3. Then the classifier (agents/scout/classifier/ica.py)
4. Then the orchestrator wiring in main.py

Standing K&L rules apply: no em-dashes, operator language, push after
commit, K&L voice in any prose.
```
