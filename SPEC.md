# SPEC: kl-agents

Living build spec. Terms per `CONTEXT.md`; locked decisions per `docs/adr/`. Each section is a tight, independently-shippable bucket with its own eval criteria in `SPEC-EVAL.md`. Drift protection: every assumption is flagged; every key decision was explicitly verified with Greg during the top-down grill (2026-06-15/16).

**Buckets:**
1. Scout Re-Aim: keeper-gate flips from belief-match to the signal rubric (THIS bucket, below).
2. *(pending grill)* Build sequence across agents.
3. *(pending grill)* The "agent" platform contract.
4. *(pending grill)* Echo activation / Validation agent specs.

---

# Bucket 1: Scout Re-Aim

> Implements **ADR 0001** (Scout gates on the signal rubric, not belief-match). This is a re-aim of the live classifier (the project's highest-risk file per `.claude/CLAUDE.md`), not an additive change. Operator-confirmed; verifier-gated.

## 1. Goal

Scout's daily classify pass keeps a harvested post as a **signal** when it clears the **signal rubric** (recent, authentic operator pain, and actionable in the sense of restaurant-operations relevant) instead of when it matches one of the 10 K&L false beliefs. Belief slug, ICA stage, and symptom tag become best-effort **descriptive tags** (nullable), not the filter. Every kept signal also carries a **theme** tag (the market-topic axis) so trending can be computed later. The result: Scout captures authentic, current, restaurant-relevant operator signals, including novel ones that fit no existing belief, which are exactly the signals K&L most wants and today's gate silently drops.

## 2. The keeper-gate (the filter)

A harvested post becomes a kept signal when **ALL THREE** hold:

| # | Check | What it checks | How judged (enum output) | Keep-vs-drop rule |
|---|-------|----------------|--------------------------|-------------------|
| G1 | **Recent** | Post is within the look-back window | Deterministic, from `posted_at`. First Scout run: 30-day backfill. Daily runs: new since last run (~24h). | Outside window then DROP. No model call. |
| G2 | **Authentic operator pain** | (a) real-operator source, not vendor/student/journalist/bot; (b) real struggle, not a neutral question or promo | `authentic_judgment` enum: `authentic` / `ambiguous` / `inauthentic`, plus `authentic_confidence` (0-1) and an evidence span | **Lean inclusive:** `inauthentic` then DROP; `authentic` then KEEP; `ambiguous` then KEEP but route to `needs_review` (see G-route). Recall over precision. |
| G3 | **Restaurant-ops relevant** (the gate) | A restaurant operation problem or decision is present (ops, money, people, systems). NOTHING about K&L's offer. | `restaurant_ops_relevant` enum: `relevant` / `not_relevant`, plus confidence | `not_relevant` then DROP; `relevant` then KEEP. |

> **G3 is purely domain-relevance. It must NOT judge "could K&L help" or "would an operator want help"** (Codex #11: that phrasing smuggled the belief-fit/playbook-fit gate ADR 0001 removed). K&L-actionability is captured separately as NON-gating metadata: `kl_action_path` enum (`content` / `magnet` / `outreach` / `none`), nullable, never affects keep/drop.

**Routing (replaces a single keep/drop boolean, Codex #6/#7):** the gate emits `keeper_decision` ∈ `{keep, needs_review, drop}` with a `drop_reason`. `keep` = G1 pass and G2 `authentic` and G3 `relevant`. `needs_review` = G2 `ambiguous` (else passing). `drop` = any hard fail, with reason (`stale` / `inauthentic` / `not_relevant` / `missing_posted_at`).

**Mapping onto the live `review_status` CHECK (Codex #1; live values are `pending|auto_rejected|approved|rejected|actioned`, verified):** `keep` then `review_status='pending'`; `drop` then `review_status='auto_rejected'`; `needs_review` then `review_status='pending'` AND `keeper_decision='needs_review'`, surfaced by a DEDICATED review query (not mixed into the main keep queue). No CHECK migration needed; `keeper_decision` carries the distinction.

**G1 null-timestamp rule (Codex #6):** `posted_at` is nullable in the live schema. If `posted_at IS NULL`, G1 cannot judge recency then `drop` with `drop_reason='missing_posted_at'`. Covered by an `is_keeper()` test.

This separates precision (keep) from recall safety-net (needs_review) so the 80% bar and lean-inclusive gate stop conflicting.

G1 runs first (cheap, no tokens). G2 and G3 are evaluated in one classify call per surviving post. **One shared `is_keeper(classification, post, run_window)` function computes `keeper_decision`** and is used BOTH for the stored row status and for run metrics in `main.py` (Codex #3: today the rule is duplicated in `main.py` and `storage/posts.py`).

## 3. Descriptive tags (metadata, NOT gate)

Applied to every kept signal. All nullable; a signal is never dropped for lacking these.

> Column names below are the LIVE `classified_posts` names (verified against `0002_classified_posts.sql`, Codex #1). The belief slug is stored in the existing `signal_type` column, NOT a new `belief_slug`. `symptom_tag` does NOT exist yet and is added by this bucket.

| Tag (column) | Source vocab | Required? | Purpose |
|-----|--------------|-----------|---------|
| `theme` (new) | **primary canonical enum** (labor, hiring, food-cost, rent, regulation, ..., plus `other`) + `theme_other` (text) naming a novel pressure when `theme='other'` | **REQUIRED on keep/needs_review rows** (Codex #3); nullable only on legacy/drop rows | **Groupable axis for trending**: every kept signal has a groupable theme; novel pressures use `theme='other'` + `theme_other` so they still group instead of fragmenting (Codex #3/#8). Enforced in code, not DB CHECK. |
| `signal_type` (existing) | `BELIEF_SLUGS` (10), canon Part VII | best-effort, nullable | K&L content framing. Was the gate; now description. |
| `ica_stage` (existing) | 1 / 2 / 3 / unclear (existing CHECK) | best-effort | K&L targeting |
| `symptom_tag` (new) | `SYMPTOM_TAGS` (10), canon Symptom Map | best-effort, nullable | demand-validation (Validation agent) |
| `kl_action_path` (new) | `content` / `magnet` / `outreach` / `none` | nullable, NON-gating | K&L-actionability metadata (Codex #10), kept OUT of the gate |
| `key_quote`, `reasoning` (existing) | model output | retained | audit trail |
| per-gate confidences (new) | `authentic_confidence`, `actionable_confidence` | required on judged posts | calibration + human/Codex audit (Codex #5: the existing single `confidence` is signal_type certainty; do not overload it) |

## 4. Data model changes

Additive to the live `classified_posts` table. New nullable columns (migration `0008`):
- `theme TEXT NULL` + `theme_other TEXT NULL`: **the load-bearing trending axis**; impossible to reconstruct retroactively without it.
- `authentic_judgment TEXT NULL`, `authentic_confidence NUMERIC(3,2) NULL`, `authentic_evidence TEXT NULL`: G2 enum + score + the verbatim span that justifies the judgment (Codex #2; distinct from `key_quote`, which is belief evidence).
- `restaurant_ops_relevant TEXT NULL`, `actionable_confidence NUMERIC(3,2) NULL`, `restaurant_ops_evidence TEXT NULL`: G3 enum + score + evidence span.
- `kl_action_path TEXT NULL`: non-gating K&L-actionability metadata.
- `keeper_decision TEXT NULL` (`keep`/`needs_review`/`drop`), `drop_reason TEXT NULL`, `rubric_version TEXT NULL`: observability + run-over-run comparison (Codex #9/#14).
- `symptom_tag TEXT NULL` and `symptom_verbatim TEXT NULL`: both added new (neither exists in the live table). `symptom_tag` is the closed-vocab framing; `symptom_verbatim` is the operator's own pain words. **`symptom_verbatim` is a hard dependency of Bucket 2 (Validation builds the probe from it), so it MUST ship in this migration** (Codex Bucket-2 #1).
- **Retained, unchanged:** `signal_type` (belief slug, now description), `ica_stage` (+ its CHECK), `confidence` (signal_type certainty, NOT reused for the rubric), `key_quote`, `reasoning`, `review_status`.
- All new columns **nullable, NO CHECK** (vocab not battle-tested; classifier coercion enforces enums in code). DB CHECK is a later migration once stable.

**Existing rows / dedup (Codex #4):** storage dedups on unique `source_url` with `ignore_duplicates=True`, so old rows will NOT gain the new fields on rerun. **Decision: old rows stay legacy-null** (no backfill). The new gate applies to newly-harvested posts only; historical rows keep their belief-era classification. *(A backfill, if ever wanted, is an explicit upsert-update path, out of this bucket.)*

## 5. What does NOT change (guardrails)

- **Echo**: untouched. It is the owned-audience listener; this bucket is Scout-only.
- **The existing belief classify capability**: retained as a tag producer, not removed. Belief slugs still get emitted; they just no longer gate.
- **Fetchers** (Reddit/YouTube, base contract): unchanged. This is a classifier+storage change.
- **Storage dedup** (by permalink): unchanged.
- **Scheduler** (launchd 07:00): unchanged.
- **Trending computation**: explicitly NOT built here. Only the structure (theme axis) is laid down.

## 6. Build slices (tight sub-buckets, each independently shippable + checkpointed)

Migration comes FIRST (Codex #2: storage cannot write new columns before they exist). 1f ships in SHADOW mode before 1h flips the gate (Codex #16).

| Slice | Scope | Checkpoint (done =) |
|-------|-------|----------------------|
| 1a | Migration `0008`: all new nullable columns, NO CHECK, applied dev then prod | columns exist in agents_dev then agents_prod; old rows legacy-null |
| 1b | `theme` primary-enum vocab (locked in vault canon) + `theme_other`; classify-call emits theme | theme vocab in canon, classifier emits theme/theme_other, tests green |
| 1c | G2 authentic judgment (enum + evidence + confidence, lean-inclusive) | classify emits authentic_judgment enum + authentic_confidence; coercion + tests; mypy clean |
| 1d | G3 restaurant-ops-relevant (gate) + `kl_action_path` (non-gating metadata) | classify emits both, kl_action_path never affects keep/drop; tests |
| 1e | Shared `is_keeper()` computing `keeper_decision` + `drop_reason`; used by storage AND main.py metrics | single function; main.py/posts.py no longer duplicate the rule; tests |
| 1f | **Shadow mode:** new rubric runs BESIDE old belief gate; both decisions stored, neither changes `review_status` yet | a run stores old-gate + new-rubric decisions on the same posts for comparison |
| 1g | Baseline grade + compare (SPEC-EVAL outcome verifier) on shadow output | 20-signal Greg grade + Codex audit + old-vs-new pending diff recorded |
| 1h | **Flip the gate** (operator-confirmed): `review_status` driven by `keeper_decision` | belief now pure description; review-queue consumers verified against `signal_type IS NULL` pending rows (Codex #15) |

1a-1f are non-destructive (additive columns + shadow). 1h is the actual re-aim and the only step that changes live queue behavior; the operator-confirm gate applies specifically to 1h, after 1g's measured agreement.

## 7. Risks / open questions

- **R1, `theme` vocab tension (RESOLVED via Codex #8):** primary canonical enum keeps trends groupable; `theme_other` admits novel pressures without fragmenting counts. Enum content locked in slice 1b against vault canon.
- **R2, calibration:** G2/G3 are new model judgments; first live run is a baseline, not a pass/fail. The human-grade + Codex-audit loop (SPEC-EVAL) closes the gap.
- **R3, classifier is highest-risk file:** slice 1h (the flip) requires operator confirmation before merge; everything prior is non-destructive.
- **R4, recall vs. reading time:** lean-inclusive G2 routes ambiguous posts to `needs_review` (not the main queue), so precision and recall are measured separately (Codex #7/#13). The ≥80% bar governs precision; the false-negative sample governs recall.
- **R5, review-queue consumer compat (Codex #15):** before the flip, enumerate every consumer/query of `review_status='pending'`; confirm none assume non-null `signal_type`. Acceptance check in slice 1h.

---
*Bucket 1 drafted 2026-06-16 from the top-down grill. Codex-APPROVED (4 rounds, PLAN-REVIEW-LOG.md). Greg signed off 2026-06-17.*

---

# Bucket 2: Validation Agent (v1)

> The second build (after Scout re-aim). Completes one full value loop: market signal then validated opportunity. A NEW sibling agent; does not touch Scout or Echo. Terms per CONTEXT.md (The judge).
>
> **Scope decision (2026-06-19, Greg, closing Codex Bucket-2 #11):** v1 is the **read-only half**: a theme-rank REPORT (top pressures + candidate verbatims) plus a THIN decision-ledger Greg fills by hand. LLM probe-drafting and the drafter-owned `validation_tests` schema (the `drafted` lifecycle + probe-generation columns) are DEFERRED to v2, after the loop has been run manually enough times to know what the probe and the schema should be. Rationale: Validation exists to test demand before building; auto-drafting probes is itself an unvalidated agent feature, so it must not be built before the loop has surfaced one real signal. The leverage is in ranking a corpus a human can't eyeball; the probe copy is hand-tuned the first several times anyway. The one structural property kept from the full design is `can_build_magnet()` (the safety gate), ported onto the thin ledger.

## 1. Goal

Validation reads Scout's re-aimed corpus and produces a **theme-rank report**: the market pressures with the strongest current signal, each with N (signal count) and the candidate operator verbatims under it. Greg reads the report, hand-writes a demand-test probe, posts it, and records the test + later the response count in a THIN ledger. Buildability is gated by `can_build_magnet()` over that ledger: crickets or pivot can NEVER greenlight a build. v1 is a **theme-ranker + verbatim-surfacer + decision-ledger**: the human owns both judgment points (writing/posting the probe, counting responses) AND the probe copy itself. No LLM drafting in v1.

## 2. What Validation does (the pipeline)

Two surfaces: a **read-only report run** (V0-V2, fully automated) and a **manual ledger** Greg drives (V3-V5). No LLM call in v1.

| Step | Action | Automated? |
|------|--------|------------|
| V0 | **Preflight (fail closed, Codex #10 + r2 #7):** (a) assert the Bucket 1 columns exist (`keeper_decision`, `theme`, `theme_other`, `symptom_verbatim`); if not, abort. (b) **Column existence is necessary but NOT sufficient.** Bucket 1 leaves these nullable and explicitly does NOT backfill legacy rows, so a re-aimed DB can be full of legacy-null rows that would pass a column check and produce garbage rankings. So the ranker operates ONLY on **eligible rows**: `keeper_decision='keep'` AND `theme IS NOT NULL` AND `rubric_version >= bucket1_reaim_version`, within the recent window. (c) Legacy/ineligible rows are EXCLUDED and **counted in the report diagnostics** (so "ranked on 12 of 340 rows; 328 pre-re-aim legacy-null" is visible, never silent). (d) If zero eligible rows in window, that is an `insufficient_data` report, not an error. | Yes |
| V1 | Read `classified_posts` where `keeper_decision='keep'`, group by **the grouping key** `coalesce(nullif(theme_other,''), theme)` (so `theme='other'` does NOT collapse novel pressures together, Codex #3), rank by signal **count** over a recent window (count-only for v1; the old `confidence` column is belief-confidence and must not be reused, Codex #2). **Rank on THEME, not symptom (Codex r2 #1):** theme is the dense market-pressure axis required on every kept signal, so counts are meaningful; `symptom_tag` is sparse + K&L-framed (best-effort, nullable) and would fragment counts and smuggle belief-fit back into ranking (contra ADR 0001). Symptom appears as descriptive material UNDER a ranked theme, never as the ranking key. | Yes |
| V1b | **Sufficiency gate (Codex #7, r3 #3):** if top group has fewer than `MIN_THEME_SIGNALS` or the **eligible** corpus has fewer than `MIN_ELIGIBLE_CORPUS_SIGNALS`, mark the report `insufficient_data` and surface that instead of a confident ranking (no one-post pick). **Both counts are over V0-eligible rows only** (keep + theme non-null + rubric_version), NOT total window rows (else legacy-null rows could satisfy corpus-sufficiency while a handful of eligible rows actually drive the ranking). | Yes |
| V2 | **Emit the theme-rank REPORT:** top groups, each with its count N, the recent window, and the candidate `symptom_verbatim` spans under it (the raw material Greg writes the probe from). **Fallback (R4):** a group whose signals have no usable verbatim is flagged "theme hot, no testable verbatim" rather than dropped. Report is read-only output (stdout + persisted artifact); writes NOTHING to the ledger. | Yes |
| V3 | Greg reads the report, hand-writes a demand-test probe from a chosen verbatim, and records the test in the ledger (`status='posted'`, with the probe copy, theme, source_signal_id, channel, keyword, posted_at) | Manual (human owns the probe copy) |
| V4 | Greg later enters `response_count` (`status='counted'`) | Manual (judgment point) |
| V5 | Compute `verdict` from `response_count` vs. operator-set thresholds; expose buildability ONLY via `can_build_magnet()` | Yes (computed), Greg confirms |

> **What's DEFERRED to v2 (was V2/V3 in the full design):** the LLM probe-drafter (auto-generating "Tired of [pain]? Comment [keyword]...") and the agent writing a `drafted` row. In v1 the agent never drafts and never writes a test row; Greg writes the probe and creates the row at `posted`. The drafter graduates to v2 once 3-5 hand-written probes show what good copy looks like.

## 3. The verdict gate

Two orthogonal fields (Codex #4: do not conflate lifecycle with judgment):
- **`status`** (lifecycle): `posted` / `counted` / `archived`. *(No `drafted` in v1: the agent never drafts; Greg creates the row at `posted`. `drafted` returns in v2 with the LLM drafter.)*
- **`verdict`** (judgment, valid once `status='counted'`): `pending` / `validated` / `crickets` / `pivot`.

Verdict logic:
- **validated** = `response_count >= validate_threshold` then eligible for a magnet build.
- **crickets** = `response_count <= crickets_threshold` then do NOT build; demand is not there.
- **pivot** = strictly between then framing may be off; re-draft against a different `symptom_verbatim` in the same theme, do NOT build yet.

> **Thresholds are OPERATOR-SET, with NO executable defaults (Codex #6).** `validate_threshold` and `crickets_threshold` are required config Greg sets from channel knowledge (audience size, typical engagement). **Missing thresholds are a startup ERROR, not a defaulted value** so a fabricated number can never drive a decision. Each test row persists the `validate_threshold`, `crickets_threshold`, and `thresholds_confirmed_by/at` it was judged under (audit trail).
>
> **Ordering invariant (Codex r2 #6):** `validate_threshold > crickets_threshold >= 0` MUST hold, else a single `response_count` satisfies both the validated (`>= validate`) and crickets (`<= crickets`) branches and the verdict is ambiguous. Enforced two ways: a **startup check** on the config (abort if violated), and a **row CHECK** on the persisted per-row thresholds (`validate_threshold > crickets_threshold AND crickets_threshold >= 0`, applied when both are non-null). With the invariant held, `pivot` is exactly the open interval `crickets_threshold < count < validate_threshold`.

**Hard guardrail as STRUCTURE, not prose (Codex #5):** buildability is exposed ONLY through a single function/view `can_build_magnet(test)` that returns true **iff** `status='counted'` AND `verdict='validated'` AND thresholds were confirmed. ALL downstream code must consume `can_build_magnet()`, never a raw verdict, so a `crickets`/`pivot`/`pending` state cannot leak a greenlight. This is the one structural property carried over from the full design; it lives on the thin ledger.

## 4. Data model

Two pieces. The **report** (V0-V2) is read-only and writes nothing to the DB; it emits stdout + a persisted run artifact (and an `agent_runs` row per the repo's run-logging convention). Only the **thin ledger** is a new table.

New migration `0009_validation_tests.sql`, repo conventions (UUID PK, run_id FK to agent_runs, CHECKs, created_at, indexes, comments, schema-selector header). **Thinner than the full design (no `probe_copy` generation columns, no `drafted` lifecycle; Greg creates the row at `posted`):**

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | gen_random_uuid() |
| `run_id` | uuid null FK agent_runs | the report run that surfaced the theme (nullable: Greg may log a test from an off-report hunch) |
| `theme` | text not null | the theme being tested (matches Scout's theme vocab) |
| `symptom_verbatim` | text null | the operator words Greg built the probe from |
| `source_signal_id` | uuid null references classified_posts(id) | provenance FK (Codex #8: UUID-FK convention, not a URL) |
| `selection_source` | text not null check (selection_source in ('report_ranked','report_insufficient_data','off_report')) | how this test was chosen (Codex r2 #3/#4): `report_ranked` = picked from a confident report ranking; `report_insufficient_data` = logged despite the report flagging thin data; `off_report` = Greg's own hunch, no report backing. Makes provenance honest so a thin-data or hunch test never reads as report-backed. |
| `probe_copy` | text not null | the demand-test post text Greg wrote and posted |
| `channel` | text null check (channel in ('li_personal','li_page','fb_page')) | known v1 channels (Codex #9; mirrors kl_comments.source) |
| `keyword` | text null | the comment keyword the probe asks for |
| `posted_at` | timestamptz null | when Greg posted |
| `response_count` | integer null check (response_count >= 0) | Greg-entered; null until counted |
| `status` | text not null check (status in ('posted','counted','archived')) | default 'posted' (lifecycle; no `drafted` in v1) |
| `verdict` | text not null check (verdict in ('pending','validated','crickets','pivot')) | default 'pending' (judgment) |
| `validate_threshold` | integer null | the threshold this row was judged under (audit) |
| `crickets_threshold` | integer null | the threshold this row was judged under (audit) |
| `thresholds_confirmed_by` | text null | who confirmed the thresholds |
| `thresholds_confirmed_at` | timestamptz null | when |
| `created_at` | timestamptz not null default now() | |

> Dropped vs. full design: `symptom_tag` (report can show it; not needed on the ledger row in v1), the `drafted` status, and `insufficient_data` as a *verdict* (it is a property of the REPORT, not of a posted test, so it lives in the report artifact, not the ledger CHECK). These return in v2 if the LLM drafter needs them.

**Row integrity (table CHECKs, Codex r2 #5/#4, r3 #1/#2): the ledger must not be able to lie, independent of `can_build_magnet()`.**

Lifecycle has THREE meanings, not a counted/non-counted binary (Codex r3 #2: `archived` is a finished test filed away, NOT a pre-count state, so it must retain its outcome):
- **`posted`** (awaiting count): `verdict='pending'` AND `response_count IS NULL`.
- **`counted`** (judged, live): `response_count IS NOT NULL` AND both per-row thresholds non-null AND `thresholds_confirmed_by/at` non-null (Codex r3 #1: a row cannot claim `validated` unless thresholds were confirmed, so the CHECK and `can_build_magnet()` never disagree) AND `verdict != 'pending'`.
- **`archived`** (done, filed): a previously-`counted` row retains its `response_count`/`verdict`/thresholds; it is NOT reset to pending. `can_build_magnet()` returns false for `status='archived'` (it requires `status='counted'`), so archiving structurally removes the greenlight without erasing the result.

Coupling CHECK: `(status='posted' AND verdict='pending' AND response_count IS NULL) OR (status IN ('counted','archived') AND response_count IS NOT NULL AND validate_threshold IS NOT NULL AND crickets_threshold IS NOT NULL AND thresholds_confirmed_by IS NOT NULL AND thresholds_confirmed_at IS NOT NULL AND verdict != 'pending')`. So `posted`+`validated`, `counted`+null-count, counted-but-`pending`, validated-without-confirmed-thresholds, and archived-with-erased-outcome are all unrepresentable.

- **Threshold ordering:** `validate_threshold IS NULL OR crickets_threshold IS NULL OR (validate_threshold > crickets_threshold AND crickets_threshold >= 0)` (the row half of the invariant above).
- **Provenance floor:** at least one of `run_id`, `source_signal_id`, `symptom_verbatim` is non-null when `selection_source != 'off_report'`; an `off_report` row is the only fully-manual case and is self-labelled as such. No silently-orphaned report-backed row.
- These are DB CHECKs (deterministic, not classifier-coerced), appropriate here because the vocab is small and fixed, unlike Bucket 1's still-settling enums.

## 5. What does NOT change / out of scope (v1)

- **No LLM probe-drafting** (deferred to v2; Greg writes probe copy by hand from the report's verbatims).
- **No agent-written `drafted` rows** (the agent only produces the read-only report; Greg creates ledger rows at `posted`).
- **No automated response counting** (manual until Echo exists; no throwaway own-scraper).
- **No autonomous posting** (Greg posts).
- **No vault `/kl:write` coupling** (probes are disposable, not published content).
- **Scout, Echo untouched.** Validation only READS `classified_posts`; the only thing it WRITES is `agent_runs` (its own run log) + the report artifact. Greg writes `validation_tests`.
- **No magnet BUILDING** (Validation gates the decision; building is downstream).

## 6. Build slices

| Slice | Scope | Checkpoint (done =) |
|-------|-------|----------------------|
| 2a | Migration `0009_validation_tests` (thin ledger: UUID PK, nullable run_id FK, source_signal_id FK, `selection_source` enum, CHECKs incl. status/verdict, lifecycle/count coupling, threshold ordering, provenance floor; indexes, comments), applied dev then prod | table exists agents_dev then agents_prod; integrity CHECKs reject the lying-row cases (posted+validated, counted+null-count, validate<=crickets) in a migration test |
| 2b | Preflight (V0, eligible-rows) + theme-ranker: assert Bucket 1 columns; restrict to eligible rows (keep + theme non-null + rubric_version); group by `coalesce(nullif(theme_other,''),theme)`, rank by count; sufficiency gates over ELIGIBLE counts (MIN_THEME_SIGNALS / MIN_ELIGIBLE_CORPUS_SIGNALS then `insufficient_data` report state) | preflight fails closed on a pre-re-aim corpus; legacy-null rows excluded + counted in diagnostics; ranker returns top groups with N; thin eligible-data marks the report insufficient_data; tests |
| 2c | **Report emitter (read-only):** top groups + N + window + candidate verbatims under each; null-verbatim group flagged "hot, no testable verbatim"; persisted artifact + agent_runs row; writes NOTHING to validation_tests | report runs on real corpus, surfaces ranked themes with verbatims, fallback path tested, DB-write-free verified |
| 2d | Thin ledger + `can_build_magnet()`: Greg-entered row (status/verdict split, no drafted; `selection_source` set); buildability ONLY via the function | row writable at `posted`; `can_build_magnet()` true iff counted+validated+thresholds-confirmed; crickets/pivot/pending all return false; **archived+validated returns false** (Codex r4 reminder); integrity CHECKs reject lying rows (tested) |
| 2e | Thresholds as required config (startup error if unset; persisted per row); end-to-end dry run: report on live Scout corpus then one hand-logged test row through to a computed verdict | Greg sets + confirms thresholds; missing-threshold aborts; one full report-to-verdict loop on live corpus |

## 7. Risks / open questions

- **R1, depends on Scout re-aim shipped:** Validation reads `keeper_decision='keep'` + `theme`/`theme_other` + `symptom_verbatim`, all from Bucket 1 (symptom_verbatim now confirmed in Bucket 1's migration). Bucket 2 cannot start until Bucket 1 is live; the V0 preflight enforces this (fails closed).
- **R2, thresholds unset:** verdict is meaningless until Greg sets real numbers. Resolved structurally: no executable defaults, missing thresholds abort at startup, each row records the thresholds it was judged under.
- **R3, theme sparsity at cold start:** resolved via MIN_THEME_SIGNALS / MIN_ELIGIBLE_CORPUS_SIGNALS sufficiency gates (over V0-eligible rows only, Codex r3 #3) that emit `insufficient_data` rather than a one-post probe; eligible-N reported with every ranking.
- **R4, symptom_verbatim may be null:** the report flags a group "hot, no testable verbatim" rather than dropping it; Greg sees the hot theme and can hunt a verbatim manually. Tested path.
- **R5 (v1 scope, new):** v1 deliberately omits LLM drafting and the `drafted` lifecycle. The risk is that the report-then-hand-write loop is too manual to sustain. Mitigation: that is the point of v1. Run it 3-5 times, and the friction observed is the spec for v2's drafter. If it is NOT too manual, the drafter may never be needed.

---
*Bucket 2 drafted 2026-06-17 from the grill. Re-scoped 2026-06-19 to report+ledger-first (Greg, closing Codex #11). Codex-APPROVED 2026-06-19 (4 rounds, PLAN-REVIEW-LOG.md). Awaiting Greg final sign-off.*
