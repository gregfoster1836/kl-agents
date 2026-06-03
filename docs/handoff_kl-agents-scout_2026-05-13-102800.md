# Handoff: kl-agents / Scout (Agent 1)

**Date:** 2026-05-01 (late afternoon, ~17:00 PT)
**Session arc today:** Multi-source refactor → SQL re-migration → YouTube API setup → YouTube fetcher build → live channel validation against API → live end-to-end smoke
**Session outcome:** YouTube fetcher live and verified (real comments fetched and parsed). Reddit fetcher built but still gated on API approval. Storage layer + classifier + orchestrator are next.

## State of the world

**Repo:** `/Users/gregfoster/00-coding/active/03 KL Agents/` (separate from the vault, separate from the operator platform). Local-only, no GitHub remote yet.

**Branch:** `main`. **8 commits** as of 2026-05-13:

| SHA | Title |
|---|---|
| `c0ec0b0` | scaffold (directory tree, configs, no logic) |
| `b4c6d7a` | initial migrations (later edited in place) |
| `f930eb2` | Reddit fetcher, config loader, JSON logging, smoke script |
| `4f965c7` | 11 fetcher unit tests, fixed logger swallowing extras |
| `19286f6` | multi-source refactor: schema, models, config, Fetcher protocol |
| `345422c` | YouTube fetcher with 16-test suite, validated channel list, live smoke |
| `d8027ea` | **storage: supabase client singleton, agent_runs writer, classified_posts writer (16 new tests)** |
| `38210d6` | **config: drop r/smallbusiness from scout subreddits (ahead of Reddit v2 submission)** |

**Quality gates:** all four green
- `ruff check`: clean
- `ruff format`: 20 files clean
- `mypy --strict`: 14 source files, no issues
- `pytest`: 28 passed (12 Reddit + 16 YouTube)

## What was built today

### Multi-source refactor (commit 19286f6)
- Schema: `source_subreddit text` replaced with `source_metadata jsonb` plus a CHECK constraint on `source` ('reddit', 'youtube'). GIN index on the jsonb column. SQL migrations re-run against both `agents_dev` and `agents_prod` schemas. Drop-and-recreate path documented since no production data yet.
- Code: `Source` StrEnum, `Fetcher` Protocol in `fetchers/base.py`, per-source config blocks under `sources:`, `_as_int` / `_as_float` helpers replacing scattered `# type: ignore`. New `load_youtube_only()` mirrors `load_reddit_only()`.

### YouTube fetcher (commit 345422c)
- `agents/scout/fetchers/youtube.py` — handle-to-channel-ID resolution, recent video listing with `publishedAfter` cutoff, top-level comment fetching with comments-disabled handling, `_comment_to_fetched_post` returning None for unusable items, `fetch_channel` honoring per-channel overrides.
- `scripts/smoke_youtube_fetch.py` — standalone runner with `--handle`, `--videos`, `--comments` flags.
- `tests/scout/test_youtube_fetcher.py` — 16 tests, all pass. Mocked API client.
- `pyproject.toml` — added `google-api-python-client>=2.140.0`, mypy override for `googleapiclient.*`.

### Channel list validation (config.yaml)
- All proposed handles validated against the live API on 2026-05-01.
- Three handles broke: `@TheRestaurantCoach` resolved to dormant 24-sub "Howard Tinker" channel (replaced with `@Therestaurantboss`), `@7shifts` did not resolve (replaced with `@7shiftsinc`), `@chefwilyeung` did not resolve under any case variant (removed entirely).
- Final list: **18 channels**.

### Live smoke verification
- Hit `@DrewTalbert` end-to-end. 5 comments returned. All `FetchedPost` fields populated correctly. `source: "youtube"`, `source_metadata` includes channel_handle, channel_id, video_id, video_title. Real author handles, real timestamps, real comment text.

## Channel list (18 final)

**Tier 1 — operator-voice + trade press:**
1. `@RestaurantUnstoppable` (Eric Cacciatore)
2. `@Therestaurantboss` (Ryan Gromfin, 144k subs)
3. `@MakingDoughShow` (Hengam Stanfield)
4. `@RestaurantRockstars` (Roger Beaudoin)
5. `@RestaurantBusinessOnline` (A Deeper Dive)
6. `@NationsRestaurantNews`
7. `@andrewscott9329` (OwnerShift, K&L direct competitor)
8. `@DavidScottPeters`
9. `@mikeybausch` (Andolini's Pizzeria operator)
10. `@WilsonKLee` (How to open a restaurant, 211k subs)
11. `@owner-com`

**Tier 2 — platform vendors and adjacent:**
12. `@7shiftsinc`
13. `@Restaurant365`
14. `@toasttab`
15. `@DaveAllredTheRealBarman` (Bar Patrol)
16. `@hospitalitybroadcast`

**Tier 2 (limited capture):**
17. `@DrewTalbert` — `videos_per_run: 1, comments_per_video: 25`
18. `@waitertheresmore` — same limits

**Skipped after evaluation (audience-fit wrong):** `@theschoolofhardknocks`, `@InsiderFood`, `@square`, `@hotelmanagementguru4162`, `@RestaurantKeysConsultancy`. See in-conversation analysis for reasoning.

## Important live observation

Most operator-coaching channels (`@RestaurantUnstoppable`, `@Therestaurantboss`, `@DavidScottPeters`) returned **zero comments** on recent videos. Likely comments disabled or heavily moderated to manage spam. **Operator-voice signal will come primarily from:**
- Reddit (when approved)
- Platform vendor channels (Toast/Restaurant365/7shifts) where operators ask questions
- Trade press (Restaurant Business, NRN) where operators sometimes weigh in
- Drew Talbert / Waiter There's More — high-volume comments, mostly noise but with rare operator gems (hence the limited-capture caps)

Don't be surprised when the coaching-channel rows in `classified_posts` come back near-empty.

## Code that exists

- `agents/scout/models.py` — `FetchedPost`, `Classification`, `Source` StrEnum
- `agents/scout/config.py` — typed Config, `load()` / `load_reddit_only()` / `load_youtube_only()`, `_as_int`/`_as_float` helpers
- `agents/scout/logging_setup.py` — JSON formatter
- `agents/scout/fetchers/base.py` — `Fetcher` Protocol, `FetchError` base class
- `agents/scout/fetchers/reddit.py` — PRAW read-only, populates `source_metadata`
- `agents/scout/fetchers/youtube.py` — Google API client, all helpers exposed for testability
- `agents/scout/main.py` — stub. Real orchestration lands when storage and classifier exist.
- `scripts/smoke_reddit_fetch.py` — gated on Reddit API approval
- `scripts/smoke_youtube_fetch.py` — live verified
- `tests/scout/test_reddit_fetcher.py` — 12 tests
- `tests/scout/test_youtube_fetcher.py` — 16 tests

## Code NOT yet built

- `agents/scout/classifier/ica.py` — Claude API call. Will lock the canonical `signal_type` slug list when the prompt is written.
- `agents/scout/storage/runs.py` and `agents/scout/storage/posts.py` — Supabase writers
- `shared/db/client.py` — supabase-py singleton
- Real orchestration in `agents/scout/main.py`

## Credentials state

All in `/Users/gregfoster/00-coding/active/03 KL Agents/.env` (gitignored, local-only).

| Var | Filled? | Notes |
|---|---|---|
| `SUPABASE_URL` | yes | |
| `SUPABASE_SERVICE_ROLE_KEY` | yes (post-rotation) | NEVER paste into chat or `.env.example` |
| `SUPABASE_SCHEMA` | yes (`agents_dev`) | |
| `REDDIT_CLIENT_ID` | empty | After Reddit approval email |
| `REDDIT_CLIENT_SECRET` | empty | After Reddit approval email |
| `REDDIT_USER_AGENT` | yes | `kl-scout/0.1 by u/SparkyMcCrinkle` |
| `YOUTUBE_API_KEY` | **yes, validated live 2026-05-01** | Google Cloud project `kl-agents`, key named `kl-scout-youtube` |
| `ANTHROPIC_API_KEY` | empty | Used by classifier session |

## Reddit approval is the only live blocker

- Account: `u/SparkyMcCrinkle`
- **v1 submitted 2026-04-30, denied 2026-05-02** with boilerplate
- **v2 submitted 2026-05-11** via `ticket_form_id=14868593862164` (Bot/App Developer path, with revised Block D + Block F that explicitly state the blog is written by hand, Claude only classifies). Confirmation page shown, no ticket number yet captured. Awaiting email at `gfloss381@gmail.com`; expect 5-10 business days
- Full submission record: `09_Session_Summaries/2026-05-11 Reddit API v2 Submitted.md`
- Paste-ready blocks and submission guide: `memory/reference_reddit_api_application.md`
- Once approved: register a "script" type app at https://www.reddit.com/prefs/apps, redirect URI `http://localhost:8080`, name `kl-scout`. Get client_id and client_secret. Paste into `.env`. Run `python scripts/smoke_reddit_fetch.py --subreddit restaurateur --limit 5`.

## Open / deferred

- **Reddit API approval** — wait for the email
- **Storage layer** — supabase-py writers for `agent_runs` and `classified_posts`. Should be straightforward given the schema is locked.
- **Classifier prompt** — write the ICA classification prompt. Lock canonical `signal_type` slug list (drawn from 10 false beliefs in K&L messaging Part VII).
- **Orchestration in `main.py`** — iterate enabled sources, call each fetcher, feed classifier, write storage. Honor a `--source` CLI flag.
- **Cron / scheduling** — deferred until end-to-end works.
- **Channel-ID resolution caching for YouTube** — config has `channel_id: null` placeholders. Future improvement: write resolved IDs back to YAML on first run so we skip the resolve call on subsequent runs.

## How to resume

```bash
cd /Users/gregfoster/00-coding/active/03 KL Agents
source .venv/bin/activate
git log --oneline -8     # confirm at 38210d6 or later
.venv/bin/pytest          # confirm 28 still pass
.venv/bin/mypy            # confirm 14 source files clean
```

Then **branch on what's available**:

1. **If Reddit API approval email has arrived** (`gfloss381@gmail.com`): walk app registration, paste creds, run `python scripts/smoke_reddit_fetch.py --subreddit restaurateur --limit 5`. First live Reddit verification. Capture exit code and a sample of JSON output.
2. **If Reddit still pending:** build the storage layer and classifier in parallel since both unblock the orchestrator. Storage layer first (smaller surface): `shared/db/client.py`, `agents/scout/storage/runs.py`, `agents/scout/storage/posts.py`. Then classifier.
3. **Quick-win option:** start the orchestrator scaffold in `main.py` with a `--dry-run` flag that calls fetchers and prints (no DB write, no classifier). This makes the multi-source flow visible end-to-end before storage and classifier exist.

## Files Greg should NOT change without me

- `/Users/gregfoster/00-coding/active/03 KL Agents/.env` — credentials only, no other edits
- `/Users/gregfoster/00-coding/active/03 KL Agents/.env.example` — template, must stay blank (paste victim once already)
- `/Users/gregfoster/00-coding/active/03 KL Agents/shared/db/migrations/*.sql` — already applied. While no production data exists, drop-and-recreate is acceptable. Once data exists, every change is a new numbered migration.

## Continuation prompt for next session

```
Resume Scout work in /Users/gregfoster/00-coding/active/03 KL Agents/.

Context: Agent 1 of K&L agentic OS, multi-source (Reddit + YouTube).
As of 2026-05-13 (commit 38210d6): 8 git commits on main, 44 pytest
tests passing, mypy --strict clean over 17 source files. Supabase
kl-agents (zbokrrcexjecrkpogjqv) has multi-source schema applied to
both agents_dev and agents_prod. YouTube fetcher live and verified
(5 real comments from @DrewTalbert). Reddit fetcher built; **Reddit
API v2 submitted 2026-05-11, awaiting reviewer response at
gfloss381@gmail.com (5-10 business day window).** Storage layer is
done (shared/db/client.py + storage/runs.py + storage/posts.py with
16 tests).

Read these first:
- memory/handoff_kl-agents-scout.md (this file): full session state
- memory/reference_reddit_api_application.md: v2 submission record
- 09_Session_Summaries/2026-05-11 Reddit API v2 Submitted.md: what
  was actually submitted, three response paths

Branch on what's available:
1. Reddit reviewer response arrived (gfloss381@gmail.com)?
   - Approved → register script app at reddit.com/prefs/apps (name
     kl-scout, redirect http://localhost:8080), paste creds into
     .env, run python scripts/smoke_reddit_fetch.py --subreddit
     restaurateur --limit 5
   - Specific denial → address feedback, draft v3
   - Boilerplate denial again → reply to ticket asking for specific
     feedback, do not blind-resubmit
2. Else, build the classifier next: agents/scout/classifier/ica.py.
   NOTE: .claude/CLAUDE.md router for kl-agents flags classifier as
   the highest-risk piece. Confirm scope with Greg before starting.
3. Quick-win: scaffold the orchestrator in agents/scout/main.py
   with --source and --dry-run flags so the multi-source flow is
   visible end-to-end (fetcher -> storage) before classifier work.

Standing K&L rules apply: no em-dashes, operator language, push after
commit, K&L voice in any prose.
```

---

**Last verified state:** working tree clean. `git log --oneline -1` returns `38210d6 config: drop r/smallbusiness from scout subreddits`. `.venv` at `/Users/gregfoster/00-coding/active/03 KL Agents/.venv/` (rebuilt 2026-05-11 against `/usr/local/bin/python3.12` after path consolidation broke the old shebangs).
