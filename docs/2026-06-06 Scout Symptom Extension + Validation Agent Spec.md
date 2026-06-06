# Scout Symptom Extension + Demand-Validation Agent, Spec

**Created:** 2026-06-06 (from a K&L-vault Lesson Integration session; captured here to execute in an agents-rooted session).
**Status:** SPEC, not built. No code touched yet.
**Origin:** K&L Lesson Integration item 1 ("lead-magnet demand-validation instrument / Symptom Test"). On inspection, item 1 Step 1 (harvest operator pain) is already what Scout does. The real new work is Step 2 (active demand validation), plus a small Scout classification extension so one harvest pass serves both consumers.

## The decision (locked with Greg 2026-06-06)

**One harvest pass, two consumers.** Scout stays the single harvester (Reddit + YouTube). No second scraper is ever built. Scout's classifier is EXTENDED to also emit a symptom tag + verbatim symptom phrasing, so a new sibling **Validation agent** can read Scout's output and run the demand test. This avoids a duplicate Claude-skill harvester that would scrape the same sources by hand, unscheduled.

**Belief vs. symptom (the core distinction driving the new fields):**
- A *false belief* is what the operator wrongly thinks ("labor is fixed"). Scout already classifies this (`signal_type`, one of 10 `BELIEF_SLUGS`).
- A *symptom* is what the operator feels/complains about ("I'm working 70 hours and still can't make payroll"). Step 2's fill-in-the-blank validation post is built from symptom language, NOT belief slugs.
- The two are related but not the same. A magnet is tested against a symptom; content research keys on a belief. Scout must emit both.

## Part A, Scout classifier extension (a change to a LIVE agent)

Scout is v0.2.1, running daily on launchd (07:00). Treat this as a careful change to a running system. The classifier is clean and tool-schema-driven; the change is contained to named sites.

**Two new fields on `Classification`:**
- `symptom_tag: str | None`, a controlled vocabulary of structural operational symptoms that are magnet-testable (distinct from the 10 belief slugs). Null when no clear testable symptom is present. Vocabulary TBD at build time (see Open Questions), it must be a closed enum like `BELIEF_SLUGS`, sourced from K&L's actual symptom language, not invented ad hoc.
- `symptom_verbatim: str | None`, the operator's own words expressing the symptom. The raw material for the fill-in-the-blank validation post. Distinct from `key_quote` (which shows the *belief*); `symptom_verbatim` shows the *pain*. May overlap but is selected for a different purpose.

**Code touchpoints (all in `agents/scout/`):**
1. `models.py`, add `symptom_tag` and `symptom_verbatim` to the `Classification` dataclass (after `reasoning`).
2. `classifier/ica.py`, three sites, mirroring how `signal_type` is wired:
   - A `SYMPTOM_TAGS` tuple + `_SYMPTOM_GLOSS` dict (parallel to `BELIEF_SLUGS` / `_BELIEF_GLOSS`), source-of-truth comment pointing at the K&L symptom-vocabulary file.
   - `build_prompt`, add a symptom menu + instruction ("symptom_tag must be exactly one of these or null; symptom_verbatim is the shortest verbatim span showing the pain, or null").
   - `_tool_schema`, add both fields to `input_schema.properties` and `required` (symptom_tag as `["string","null"]` enum like signal_type; symptom_verbatim as `["string","null"]`).
   - `_parse_classification`, defensive coercion (symptom_tag not in SYMPTOM_TAGS → None).
3. `storage/posts.py`, persist the two new columns on upsert.

**Data touchpoint:**
4. `shared/db/migrations/0008_symptom_classification.sql`, `alter table classified_posts add column symptom_tag text; add column symptom_verbatim text;` (nullable, no CHECK initially OR a CHECK against the final enum once the vocabulary is locked). Apply to both `agents_dev` and `agents_prod`. NO backfill needed, old rows keep null; new runs populate. Existing review-queue gate (belief-match + confidence in `storage/posts.py`) is UNCHANGED, symptom fields are additive, they do not alter what reaches the human queue.

**Test touchpoint:**
5. `tests/`, extend the classifier tests (the parse/coerce tests are the important ones, assert symptom_tag coerces to None on garbage, symptom_verbatim passes through).

**Cost note:** adding two fields to one tool call is negligible token cost. No new model invocation; same single classify call per post.

## Part B, the Validation agent (NEW sibling to Scout/Echo)

This is item 1 Step 2, the genuine new build. It is NOT listen-only (Scout's mode); it is an active demand test.

**Job:** pick a high-signal symptom from Scout's enriched `classified_posts`, run a fill-in-the-blank validation offer, measure response, gate the magnet-build decision.

**The validation method (from item 1):**
- Step 2 post template (operator-to-operator voice): "Tired of [structural operational symptom]? I put together a [checklist/teardown/cheat sheet] on [operational outcome]. Comment [keyword] and I'll send it."
- The `[structural operational symptom]` slot is filled from `symptom_verbatim` / `symptom_tag` aggregated across Scout's corpus.
- **The gate (the actual point):** build the magnet ONLY on a real demand signal. Crickets = pivot the symptom, do not build anyway.
- Voice constraint: structural/operational symptoms only. No hype. No value claimed before demonstrated.

**Likely shape (decide at build time):**
- Reads: `classified_posts` filtered to non-null `symptom_tag`, grouped/ranked by frequency × confidence (which symptom has the strongest signal worth testing).
- Writes: a new table (e.g. `validation_tests`), one row per symptom tested: symptom_tag, post copy, channel, posted_at, response_count, keyword, verdict (validated/crickets/pivot).
- Response tracking: closer to Echo's territory (engagement on K&L's own posts) than to Scout's. Echo already scrapes K&L LinkedIn/FB post comments, the validation agent may consume Echo's `kl_comments` to count keyword responses rather than building its own comment scraper. CHECK Echo's status before speccing this half.

**Reuse from Scout/Echo (do not rebuild):** fetchers pattern, classifier tool-schema pattern, Supabase schema conventions (source-agnostic, source_metadata jsonb, UNIQUE dedup), launchd scheduler + logging structure (`docs/scout-scheduler.md`).

## Open questions (resolve at build time, agents-rooted session)

1. **The symptom vocabulary.** SYMPTOM_TAGS must be a closed enum sourced from K&L's real symptom language. Candidate source: the K&L vault's false-belief map + ICA pain language + the symptom language item 1 wanted to harvest. Greg should approve the list (parallel to how the 10 beliefs came from Part VII). Do NOT invent symptoms.
2. **Does the migration add a CHECK constraint on symptom_tag?** Only after the enum is locked. Ship 0008 nullable-no-check first if the vocabulary isn't final; add the CHECK in a later migration once stable. (Mirrors how a controlled vocab usually hardens.)
3. **Validation-agent response tracking, own scraper or consume Echo?** Depends on Echo's completion. Prefer consuming Echo's `kl_comments`. Confirm Echo status first.
4. **Where does the drafted validation post get written?** The post COPY is K&L content, could be drafted via `/kl:write` in the vault, or generated by the validation agent. Decide whether the agent drafts or just selects-the-symptom-and-tracks.
5. **GSD.** Per K&L workflow rules, start this build through a GSD command in the agents repo. This spec is the input to `/gsd:plan-phase` or equivalent.

## Execution note

Build this in a session ROOTED IN `/Users/gregfoster/00-coding/active/03 KL Agents` (not the K&L vault), so the agents repo's `.claude/` rules, hooks, and GSD load, and handoffs land in the right repo. Part A (Scout extension) and Part B (Validation agent) can be separate phases, Part A is the prerequisite (Part B reads what Part A emits), but Part A ships value on its own (richer Scout classification) and is low-risk/additive. Recommend: Part A first as a small contained phase, verify a live Scout run populates the new fields, then Part B.
