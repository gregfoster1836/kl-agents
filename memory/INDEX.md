# Domain Index — KL Agents (project scope)

> **Routing only. No content.** Maps each selectable DOMAIN → the source-classes that load for that work.
> Governed by `00 K&L Vault/.claude/rules/compounding-memory-doctrine.md` § The DOMAIN INDEX. Derived artifact: mirrors `.claude/retrieval-registry.json`.
>
> **Source-classes per domain:** `lessons:` (how to do it right), `facts:` (the domain truth — the front-gate enforcement list), `craft:` (technique).
> **The FRONT GATE** (`~/.claude/hooks/retrieval-gate.js`) enforces that a domain's `facts:` were Read this session before the first domain-artifact write. The `facts:` lines below mirror `.claude/retrieval-registry.json` — keep them in sync.
> **Cross-scope:** `[global]` = lives in `~/.claude/`. See `~/.claude/memory/INDEX.md`.

---

## code
lessons: .claude/decisions.md (locked structural decisions — classifier stays code-side) · .claude/CLAUDE.md (router, read order, risk zones) · [global] feedback_adversarial_review_parallel_claude_plus_codex.md
facts:   README.md · .claude/decisions.md · config.yaml · pyproject.toml · .claude/CLAUDE.md
craft:   build -> docs/handoff_kl-agents-scout_2026-05-13-102800.md + docs/scout-scheduler.md
load-when: authoring/modifying agent source — fetchers, classifier, storage, shared db
content-type: scout|echo|fetcher|classifier|scheduler = build

## tooling
lessons: .claude/reference_reddit_api_application.md (Reddit Data API v2 application + policy compliance) · docs/reference_kl_engagement_feed.md (engagement extraction port to Echo)
facts:   .claude/reference_reddit_api_application.md · docs/reference_kl_engagement_feed.md · config.yaml
craft:   reddit -> docs/2026-05-11 Reddit API v2 Submitted.md
load-when: external API integration / reference work — Reddit Data API, engagement-feed extraction port
content-type: reddit|praw|oauth|subreddit = reddit
