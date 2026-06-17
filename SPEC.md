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
- **Retained, unchanged:** `signal_type` (belief slug, now description), `ica_stage` (+ its CHECK), `confidence` (signal_type certainty, NOT reused for the rubric), `key_quote`, `reasoning`, `review_status`. `symptom_tag` is also added new (it does not exist in the live table).
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
*Bucket 1 drafted 2026-06-16 from the top-down grill. Provisional until Codex review + Greg sign-off.*
