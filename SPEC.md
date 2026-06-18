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

## 1. Goal

Validation reads Scout's re-aimed corpus, ranks by **theme** to find the market pressure with the strongest current signal, drafts a fill-in-the-blank demand-test probe from a real operator's `symptom_verbatim`, records the test, and (after Greg posts it and enters the response count) emits a verdict that GATES whether K&L builds a lead magnet. It is a symptom-ranker + test-drafter + decision-ledger with the human in the loop at the two judgment points (posting, counting). Crickets or pivot must NEVER trigger a build.

## 2. What Validation does (the pipeline)

| Step | Action | Automated? |
|------|--------|------------|
| V0 | **Preflight (fail closed, Codex #10):** assert the Bucket 1 columns exist (`keeper_decision`, `theme`, `theme_other`, `symptom_verbatim`) and `rubric_version >= bucket1_reaim_version`. If not, abort with a clear error. Bucket 2 cannot run on a pre-re-aim corpus. | Yes |
| V1 | Read `classified_posts` where `keeper_decision='keep'`, group by **the grouping key** `coalesce(nullif(theme_other,''), theme)` (so `theme='other'` does NOT collapse novel pressures together, Codex #3), rank by signal **count** over a recent window (count-only for v1; the old `confidence` column is belief-confidence and must not be reused, Codex #2) | Yes |
| V1b | **Sufficiency gate (Codex #7):** if top group has fewer than `MIN_THEME_SIGNALS` or corpus has fewer than `MIN_CORPUS_SIGNALS`, emit `insufficient_data` and STOP (no probe from one post) | Yes |
| V2 | Within the top group, select the strongest `symptom_verbatim` spans as probe raw material. **Fallback (R4):** if none of the top group's signals have usable verbatim, drop to the next group or flag "theme hot, no testable verbatim" | Yes |
| V3 | Draft a first-draft demand-test probe: "Tired of [pain from verbatim]? I put together a [tool] on [outcome]. Comment [keyword] and I'll send it." | Yes (draft only) |
| V4 | Record the test to `validation_tests` with `status='drafted'`, `verdict='pending'` | Yes |
| V5 | Greg refines/approves copy, posts it (`status='posted'`), later enters `response_count` (`status='counted'`) | Manual (human judgment points) |
| V6 | Compute `verdict` from `response_count` vs. operator-set thresholds; expose buildability ONLY via `can_build_magnet()` | Yes (computed), Greg confirms |

## 3. The verdict gate

Two orthogonal fields (Codex #4: do not conflate lifecycle with judgment):
- **`status`** (lifecycle): `drafted` / `posted` / `counted` / `archived`.
- **`verdict`** (judgment, valid once `status='counted'`): `pending` / `validated` / `crickets` / `pivot`.

Verdict logic:
- **validated** = `response_count >= validate_threshold` then eligible for a magnet build.
- **crickets** = `response_count <= crickets_threshold` then do NOT build; demand is not there.
- **pivot** = strictly between then framing may be off; re-draft against a different `symptom_verbatim` in the same theme, do NOT build yet.

> **Thresholds are OPERATOR-SET, with NO executable defaults (Codex #6).** `validate_threshold` and `crickets_threshold` are required config Greg sets from channel knowledge (audience size, typical engagement). **Missing thresholds are a startup ERROR, not a defaulted value** so a fabricated number can never drive a decision. Each test row persists the `validate_threshold`, `crickets_threshold`, and `thresholds_confirmed_by/at` it was judged under (audit trail).

**Hard guardrail as STRUCTURE, not prose (Codex #5):** buildability is exposed ONLY through a single function/view `can_build_magnet(test)` that returns true **iff** `status='counted'` AND `verdict='validated'` AND thresholds were confirmed. ALL downstream code must consume `can_build_magnet()`, never a raw verdict, so a `crickets`/`pivot`/`pending`/`insufficient_data` state cannot leak a greenlight.

## 4. Data model (new table `validation_tests`)

New migration `0009_validation_tests.sql`, following the repo's table conventions (run_id FK to agent_runs, UUID PK, CHECK constraints, created_at, indexes, comments, schema-selector header):

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | gen_random_uuid() |
| `run_id` | uuid FK agent_runs | the Validation run that drafted it |
| `theme` | text not null | the ranked theme being tested (matches Scout's theme vocab) |
| `symptom_tag` | text null | the symptom framing, if the verbatim mapped to one |
| `symptom_verbatim` | text null | the operator words the probe was built from |
| `source_signal_id` | uuid null references classified_posts(id) | provenance FK (Codex #8: match repo's UUID-FK convention, not a URL) |
| `probe_copy` | text not null | the demand-test post text |
| `channel` | text null check (channel in ('li_personal','li_page','fb_page')) | constrained to known v1 channels (Codex #9; mirrors kl_comments.source) |
| `keyword` | text null | the comment keyword the probe asks for |
| `posted_at` | timestamptz null | when Greg posted (null until posted) |
| `response_count` | integer null check (response_count >= 0) | Greg-entered; null until counted |
| `status` | text not null check (status in ('drafted','posted','counted','archived')) | default 'drafted' (lifecycle) |
| `verdict` | text not null check (verdict in ('pending','validated','crickets','pivot','insufficient_data')) | default 'pending' (judgment) |
| `validate_threshold` | integer null | the threshold this row was judged under (audit) |
| `crickets_threshold` | integer null | the threshold this row was judged under (audit) |
| `thresholds_confirmed_by` | text null | who confirmed the thresholds |
| `thresholds_confirmed_at` | timestamptz null | when |
| `created_at` | timestamptz not null default now() | |

## 5. What does NOT change / out of scope (v1)

- **No automated response counting** (manual until Echo exists; no throwaway own-scraper).
- **No autonomous posting** (Greg posts; the agent drafts).
- **No vault `/kl:write` coupling** (probes are disposable, not published content; escalate later only if needed).
- **Scout, Echo untouched.** Validation only READS `classified_posts` and WRITES `validation_tests`.
- **No magnet BUILDING** (Validation gates the decision; building the magnet is downstream human/other work).

## 6. Build slices

| Slice | Scope | Checkpoint (done =) |
|-------|-------|----------------------|
| 2a | Migration `0009_validation_tests` (conventions-matched: UUID PK, run_id FK, source_signal_id FK, CHECKs, indexes, comments), applied dev then prod | table exists agents_dev then agents_prod |
| 2b | Preflight (V0) + theme-ranker: assert Bucket 1 columns + rubric_version; group by `coalesce(nullif(theme_other,''),theme)`, rank by count, sufficiency gates (MIN_THEME_SIGNALS / MIN_CORPUS_SIGNALS then insufficient_data) | preflight fails closed on a pre-re-aim corpus; ranker returns top groups with N; thin-data emits insufficient_data; tests |
| 2c | Probe drafter: select verbatim from top group, generate fill-in-the-blank draft; null-verbatim fallback | draft produced from real verbatim; fallback path tested; operator voice (no hype) |
| 2d | Ledger + `can_build_magnet()`: write `validation_tests` (status/verdict split); buildability ONLY via the function | row written; `can_build_magnet()` true iff counted+validated+thresholds-confirmed; crickets/pivot/pending/insufficient_data all return false (tested) |
| 2e | Thresholds as required config (startup error if unset; persisted per row); end-to-end dry run on real Scout corpus | Greg sets + confirms thresholds; missing-threshold aborts; one full drafted test from live corpus |

## 7. Risks / open questions

- **R1, depends on Scout re-aim shipped:** Validation reads `keeper_decision='keep'` + `theme`/`theme_other` + `symptom_verbatim`, all from Bucket 1 (symptom_verbatim now confirmed in Bucket 1's migration). Bucket 2 cannot start until Bucket 1 is live; the V0 preflight enforces this (fails closed).
- **R2, thresholds unset:** verdict is meaningless until Greg sets real numbers. Resolved structurally: no executable defaults, missing thresholds abort at startup, each row records the thresholds it was judged under.
- **R3, theme sparsity at cold start:** resolved via MIN_THEME_SIGNALS / MIN_CORPUS_SIGNALS sufficiency gates that emit `insufficient_data` rather than a one-post probe; N reported with every ranking.
- **R4, symptom_verbatim may be null:** probe drafter falls back to the next group or flags "theme hot, no testable verbatim." Tested path.

---
*Bucket 2 drafted 2026-06-17 from the grill. Provisional until Codex review + Greg sign-off.*
