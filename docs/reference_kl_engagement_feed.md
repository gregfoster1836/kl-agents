---
name: reference-kl-engagement-feed
description: How to run the daily K&L engagement-feed extraction (LI Personal + LI Page + FB Page). FROZEN 2026-05-17 — see migration banner below.
metadata:
  type: reference
---

> **⚠️ MIGRATION IN PROGRESS — 2026-05-17 onward**
>
> This reference describes the **standalone** `kl-engagement-feed` repo, which was the Phase 1 architecture proof. As of 2026-05-17 the functionality is being **ported into kl-agents as Agent 2 "Echo"**.
>
> **Do not modify the standalone repo** during the port. It is frozen until Echo hits the Phase 1 baseline (≥36 comments) in Supabase, at which point this file gets superseded by `memory/reference_kl_agents_echo.md`.
>
> Architecture migration artifacts:
> - Spec: `docs/superpowers/specs/2026-05-17-kl-agents-echo-design.md`
> - Plan: `docs/superpowers/plans/2026-05-17-kl-agents-echo-rendering.md`
> - Live repo (Echo target): `/Users/gregfoster/00-coding/active/03 KL Agents/`
>
> Use the procedures below only if you need to re-run the standalone Phase 1 system before Echo is ready (e.g., to refresh the 2026-05-14 baseline for the port verification).

# K&L Engagement Feed — operational reference (standalone Phase 1, frozen)

External repo: `~/00-coding/active/kl-engagement-feed/`
Data output: `05_Internal-Research/engagement-feed/data/{YYYY-MM-DD}.json` + `_rolling-history.jsonl` + `_state.json`

## Run it manually

```bash
export PATH="$HOME/.local/bin:$PATH"
export BU_CDP_URL=http://127.0.0.1:9222
cd ~/00-coding/active/kl-engagement-feed
PYTHONPATH=src uv run python -m kl_engagement_feed.run_extraction
```

Note: `PYTHONPATH=src` is required. The pyproject declares `pythonpath = ["src"]` for pytest but not for module invocation, and no build-system is wired up, so `uv run -m` would otherwise fail with `ModuleNotFoundError`. Phase 2 should add a `[build-system]` section so the package is installed editably.

Pre-flight requirements:
1. Isolated Chrome must be running: `curl -s http://127.0.0.1:9222/json/version`
2. The isolated Chrome must be logged into LinkedIn AND Facebook. Sessions persist in `~/.browser-harness-profile`.

## Run it one source at a time (for debugging)

```bash
cd ~/00-coding/active/kl-engagement-feed
PYTHONPATH=src python -c "from kl_engagement_feed.scrape_li_personal import BROWSER_SCRIPT; print(BROWSER_SCRIPT)" | browser-harness
PYTHONPATH=src python -c "from kl_engagement_feed.scrape_li_page import BROWSER_SCRIPT; print(BROWSER_SCRIPT)" | browser-harness
PYTHONPATH=src python -c "from kl_engagement_feed.scrape_fb_page import BROWSER_SCRIPT; print(BROWSER_SCRIPT)" | browser-harness
```

## Failure modes and fixes

| Symptom | Cause | Fix |
|---|---|---|
| `AUTH_WALL` for a source | Session expired in isolated Chrome | Open `~/.browser-harness-profile` Chrome, navigate to the platform, log in once, rerun |
| `no result block in scraper stdout` | browser-harness errored, or scraper crashed mid-run | Check stderr in the run-summary; rerun with `--headed` for the affected source |
| `validate_comment` raises in orchestrator | Selectors drifted; scraper returned bad records | Update the affected scraper + the matching `agent-workspace/domain-skills/` markdown in browser-harness |
| `new_comments` always 0 even on first run | Selectors returning empty arrays | Run the discovery checkpoint from Task 5/8 in the Phase 1 plan |
| `subprocess.run timeout` after 600s | Chrome hung, or a scroll loop didn't terminate | Restart the daemon: `browser-harness <<<'restart_daemon()'` |
| `ModuleNotFoundError: No module named 'kl_engagement_feed'` | Missing PYTHONPATH=src prefix | Add `PYTHONPATH=src` before `uv run python -m ...` (see above) |

## Same-day re-run behavior (delta path)

Re-running on the same day overwrites the dated JSON with the latest run's summary. The ledger (`_rolling-history.jsonl`) is the durable record and is append-only. Dedup key: `(source, post_url, commenter_handle, timestamp_iso)`. Verified 2026-05-14: second-run output had `new_comments: 0` for all three sources while still sweeping the same post counts (10 / 7 / 6).

## Architecture notes

- **Model A (detail-page direct-nav)** for both LI scrapers. Navigates to `/feed/update/urn:li:activity:{ID}/` for each post URN, scrapes comments off the detail page. Anchored on `div[componentkey^="replaceableComment_urn:li:comment"]` (React-framework-derived, stable across admin/public views).
- Some K&L Page posts use `ugcPost:` URN prefix instead of `activity:` — the regex in `scrape_li_page.py` accepts either.
- **FB K&L Page** uses admin-view-specific selectors: `[data-ad-comet-preview="message"]` and `aria-label="Leave a comment"` (English-locale). Non-admin sweep is a Phase 2 concern.

## Adding a new source

Adding a 4th source (e.g., Reddit, Instagram) is a Phase 3+ task. Pattern: a new `scrape_<source>.py` with a `BROWSER_SCRIPT` + `parse_response`, plus a new entry in `config.SOURCES`. Update this reference when that happens.

## Related files

- `docs/superpowers/plans/2026-05-13-kl-engagement-feed-phase1-extraction.md` — the plan that built this
- `~/00-coding/active/browser-harness/agent-workspace/domain-skills/linkedin/personal-engagement.md`
- `~/00-coding/active/browser-harness/agent-workspace/domain-skills/linkedin/company-page-engagement.md`
- `~/00-coding/active/browser-harness/agent-workspace/domain-skills/facebook/pages.md`
- `memory/handoff_main.md` — Phase 1 9-of-11 build session
