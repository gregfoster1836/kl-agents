# Scout Scheduler

The last unbuilt Scout piece. Classifier, storage, orchestrator, and the
YouTube/Reddit fetchers are all done; this is the cron layer that runs Scout
on its own.

**Mechanism:** macOS `launchd` (user LaunchAgent). First scheduler in the
kl-agents codebase. Mirrors the Echo / kl-engagement-feed launchd design
(`K&L Vault:docs/superpowers/specs/2026-05-14-kl-engagement-feed-phase2-design.md`,
Task 9), with two deliberate divergences (below).

## Decisions (locked 2026-06-03)

| Decision | Choice | Why |
|---|---|---|
| Cadence | Daily 07:00 local, when-awake catch-up | Mirrors Echo. A daily sweep of new restaurant-sub / channel posts is enough for a review-queue feeder; tighter cadences add Claude cost without proportional signal. |
| Sources | `--source youtube` (for now) | Intent was `--source all`, but Scout's config **fatals (exit 2)** on `all` when `REDDIT_CLIENT_ID` is absent — it refuses to start before any source runs, so YouTube never gets a turn. youtube-only runs clean today. One-word wrapper flip to `all` when Reddit creds land; no code change. |
| Secrets | In-repo `.env` (status quo) | Scout's `config.py` already calls `load_dotenv()` against the repo `.env`. One source of truth, already gitignored. The wrapper does NOT source secrets. |
| Catch-up | `RunAtLoad=false` + `StartCalendarInterval` | If the Mac is asleep at 7am, launchd runs on next wake. No double-fire on login. |

### Divergences from the Echo precedent

1. **No env-sourcing in the wrapper.** Echo's wrapper `source`s a home-dir
   `~/.kl-engagement-feed.env`. Scout instead lets Python load the in-repo
   `.env` via `load_dotenv()` — so the wrapper only sets PATH + cwd and calls
   the venv python. Fewer moving parts, no key duplication.
2. **No Chrome pre-flight.** Echo scrapes via an isolated Chrome at `:9222` and
   pre-flights it. Scout hits HTTP APIs (Reddit / YouTube / Anthropic); there is
   no browser to check. The only implicit pre-flight is the venv-python
   existence check in the wrapper.

## Artifacts

| File | Role | Tracked |
|---|---|---|
| `scripts/run_scout.sh` | launchd entry point — PATH + cd + venv python + run-log | yes |
| `deploy/com.knifeledger.scout.plist` | canonical LaunchAgent definition | yes |
| `~/Library/LaunchAgents/com.knifeledger.scout.plist` | installed copy launchd reads | no (system) |
| `~/Library/Logs/kl-scout/stdout.log` · `stderr.log` | launchd-captured Scout output | no (logs) |
| `~/Library/Logs/kl-scout/runs.log` | one JSON line per run (ts, exit, status) | no (logs) |

## Install

```bash
# 1. wrapper must be executable
chmod +x "/Users/gregfoster/00-coding/active/03 KL Agents/scripts/run_scout.sh"

# 2. copy the canonical plist into LaunchAgents
cp "/Users/gregfoster/00-coding/active/03 KL Agents/deploy/com.knifeledger.scout.plist" \
   "$HOME/Library/LaunchAgents/com.knifeledger.scout.plist"

# 3. load it (modern launchctl; gui/$UID is the per-user domain)
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.knifeledger.scout.plist"
```

## Verify

```bash
# is it registered?
launchctl print "gui/$(id -u)/com.knifeledger.scout" | head -30

# fire it once NOW, out of schedule, to confirm the whole chain works:
launchctl kickstart -k "gui/$(id -u)/com.knifeledger.scout"

# then check the run log + captured output
tail -5 "$HOME/Library/Logs/kl-scout/runs.log"
tail -20 "$HOME/Library/Logs/kl-scout/stderr.log"
```

A manual `kickstart` should log `{"exit":0,"status":"success"}` (youtube-only
run completes clean). If you flip the wrapper to `--source all` before Reddit
creds work, it will instead log `{"exit":2,"status":"fatal"}` — config refuses
to start without `REDDIT_CLIENT_ID`. That is why the wrapper stays youtube-only
until approval lands.

## Uninstall

```bash
launchctl bootout "gui/$(id -u)/com.knifeledger.scout"
rm "$HOME/Library/LaunchAgents/com.knifeledger.scout.plist"
```

## When Reddit approval lands

1. Fill `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` / `REDDIT_USER_AGENT` in `.env`.
2. In `scripts/run_scout.sh`, change `--source youtube` → `--source all`.
3. `launchctl kickstart -k "gui/$(id -u)/com.knifeledger.scout"` and confirm
   `runs.log` shows `exit 0` (or `exit 1` partial if a source has a transient
   failure — that is fine; only `exit 2` means config refused to start).

## Known blockers (env/infra, NOT scheduler defects)

The scheduler chain is verified end-to-end: launchd → `run_scout.sh` → cd →
venv python → Scout → live YouTube fetch → first DB write. It currently stops at
two pre-existing environment gaps that block ANY live Scout run, however
triggered:

1. **`ANTHROPIC_API_KEY` empty in `.env`.** The classify step can't build a
   client. (Also blocks `scripts/smoke_classify.py`.) Fix: paste the key.
2. ~~Supabase schema `agents_dev` not exposed to PostgREST.~~ **RESOLVED
   2026-06-03.** A live run was failing at `start_run` with `PGRST106: Invalid
   schema: agents_dev`. Fixed by exposing `agents_dev` + `agents_prod` to
   PostgREST and granting the API roles their privileges — now tracked as
   `shared/db/migrations/0007_expose_schemas.sql` so a project reset can't
   silently revert it. Verified against the live DB (`authenticator` role config
   shows all four schemas; a real run wrote 48 rows to
   `agents_dev.classified_posts`).

Blocker 1 (the key) was also resolved 2026-06-03. A full `kickstart` now logs
`exit 0` — verified: run `d24d6810` fetched + classified + inserted 48 posts,
6 queued for review.

## Open / future

- **Cost guardrail.** Echo has a `$0.05/day` classifier cost ceiling. Scout has
  none yet. With daily cadence over ~18 YouTube channels the spend is bounded,
  but a guardrail belongs in the classifier, not the scheduler.
- **Failure alerting.** `runs.log` is pull-only (you have to look). Echo plays a
  sound + writes a vault `_alerts.log` on failure. If Scout's daily run failing
  silently for days is a real risk, add a shell-level alert on `exit==2` in
  `run_scout.sh`.
- **Classifier model.** `config.yaml` pins `claude-sonnet-4-5`; Sonnet 4.6 is
  the current tier. Separate decision from scheduling — flagged here so it isn't
  lost.
