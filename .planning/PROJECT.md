# kl-agents

## What This Is

Knife & Ledger's agentic OS: a Python 3.12 multi-agent system where each agent does one job and writes to a shared Supabase backend. The live agent, Scout, harvests new posts from restaurant-operator subreddits and YouTube, classifies each against K&L's 10 false beliefs and 3 ICA awareness stages, and writes keepers to a review queue that informs K&L's educational content. Built and operated by Knife & Ledger LLC; the human reads the queue and writes content by hand.

## Core Value

One harvest pass, many consumers: Scout reliably surfaces real operator pain (beliefs + symptoms) to a Supabase corpus that every downstream K&L consumer reads. If everything else fails, the daily classify-and-store loop must keep working.

## Requirements

### Validated

<!-- Inferred from existing code, traced live 2026-06-11. Shipped and relied upon. -->

- ✓ Multi-source fetcher contract (Reddit via PRAW read-only, YouTube) with a shared base — existing (`agents/scout/fetchers/`)
- ✓ ICA classifier: classifies each post against 10 `BELIEF_SLUGS` + ICA stage + confidence, tool-schema-driven, on Haiku 4.5 — existing (`agents/scout/classifier/ica.py`)
- ✓ Multi-source orchestrator with `--source`, `--dry-run`, `--limit`, exit codes 0/1/2 — existing (`agents/scout/main.py`)
- ✓ Supabase storage layer with dedup by permalink + review-queue gate (belief-match + confidence) — existing (`agents/scout/storage/`, `shared/db/client.py`)
- ✓ Migrations 0001-0007 applied (agent_runs, classified_posts, Echo's kl_posts/kl_comments/kl_commenter_profiles + RLS, schema exposure) — existing (`shared/db/migrations/`)
- ✓ launchd daily-07:00 scheduler — existing (`deploy/com.knifeledger.scout.plist`)
- ✓ Test + quality bar: 77 pytest passing, mypy --strict clean, ruff, structured JSON logs, no em-dashes — existing

### Active

<!-- Current scope. Hypotheses until shipped + validated. -->

- [ ] **Scout symptom extension (Part A):** classifier additionally emits `symptom_tag` (closed 10-tag K&L vocab) + `symptom_verbatim` (operator's own pain words), persisted to `classified_posts`. Additive, nullable, existing review-queue gate unchanged. (Spec: `docs/2026-06-06 Scout Symptom Extension + Validation Agent Spec.md` Part A)
- [ ] **Validation agent (Part B):** new sibling agent that reads Scout's enriched corpus, ranks symptoms by frequency × confidence, runs a fill-in-the-blank demand test, and gates a lead-magnet build (validated / crickets / pivot). (Spec Part B)
- [ ] **Reddit Data API access:** unblock Scout's Reddit path (v2 submitted 2026-05-11, no response; YouTube path works live in the meantime).
- [ ] **Echo activation:** promote Echo from migrations-only groundwork to a running agent that scrapes K&L's own LinkedIn/FB post-comment engagement.

### Out of Scope

- A second/duplicate harvester — locked decision (2026-06-06): one harvest pass, two consumers. Scout stays the sole harvester; never build a parallel scraper.
- Republishing/quoting Reddit content in K&L published material — RBP compliance; Scout is read-only research, not redistribution.
- Changing the existing review-queue gate logic during Part A — symptom fields are strictly additive.
- Model training on Reddit content — RBP compliance.

## Context

- **Symptom vocabulary is LOCKED (10 tags), sourced from K&L canon**, authored to the vault: `00 K&L Vault/01_Core_Systems/Messaging/Symptom Map.md`. Tags: busy-but-broke, owner-is-bottleneck, payroll-squeeze, food-cost-bleed, staff-wont-stick, nothing-sticks, always-firefighting, flying-blind, no-time-no-life, growth-more-stress. Provenance discipline: new tags authored in the vault first, then mirrored into the classifier — never the reverse.
- **Belief vs. symptom:** a belief is the wrong diagnosis (the 10 `BELIEF_SLUGS`); a symptom is the felt pain. Content research keys on belief; lead-magnet demand-testing keys on symptom. Scout must emit both.
- **Supabase:** project `zbokrrcexjecrkpogjqv`, two DBs (`agents_dev`, `agents_prod`). Migrations applied to both, dev first.
- **Reddit blocker:** v2 application submitted 2026-05-11, no ticket number captured (confirmation likely no-reply), reply to confirmation got no response. Live escalation paths: fresh ticket referencing prior, or r/redditdev. Does not block YouTube-path work.
- The wider K&L messaging canon lives in the sibling vault (`00 K&L Vault`); this repo consumes it as the source of truth for ICA, beliefs, and symptoms.

## Constraints

- **Tech stack**: Python 3.12, mypy --strict, ruff, supabase-py. No deviation without explicit decision.
- **Risk zone**: `agents/scout/classifier/ica.py` is the highest-risk file (per `.claude/CLAUDE.md`). Any change requires operator confirmation. Confirmed for Part A (2026-06-11).
- **Voice**: operator language, structured JSON logs, no emoji, no em-dashes anywhere.
- **Reddit**: read-only, sequential, ~2 requests/day, under 60/min, RBP-compliant. Access pending.
- **Additive-only for Part A**: new classifier fields must not alter what reaches the human review queue.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| One harvest pass, two consumers (2026-06-06) | Avoid a duplicate unscheduled scraper; Scout already harvests the sources Part B needs | ✓ Good |
| Symptom vocab = closed 10-tag enum from K&L canon, not invented | Mirrors how the 10 belief slugs derive from Part VII; prevents ad-hoc drift | ✓ Good |
| Merge 2 near-pairs → 10 tags (2026-06-11) | owner-bottleneck absorbs team-needs-everything; nothing-sticks absorbs same-problems-repeat — tighter vocab, no felt-pain range lost | — Pending |
| Migration 0008 nullable, NO CHECK | Vocab not yet battle-tested on live runs; classifier code enforces enum via coercion; add DB CHECK in a later migration once stable | — Pending |
| Initialize GSD over the existing repo (2026-06-13) | Sets up GSD discipline for Part B + Echo + future agents, not just Part A | — Pending |
| Classifier stays code-side (not a DB function) | Established pattern; tool-schema-driven, testable | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-14 after initialization*
