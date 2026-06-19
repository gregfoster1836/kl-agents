# SPEC-EVAL: kl-agents evaluation criteria

Defines, UP FRONT, how each SPEC bucket is verified. Two distinct verifiers per bucket, kept separate:
- **Artifact verifier**: is the SPEC document structurally complete and correct? Mechanical, pass = 100%.
- **Outcome verifier**: does the built agent actually do the right thing against real-world data? Measured, has a numeric pass bar.

"Good enough doesn't work": these are pass/fail, not vibes. Codex runs an independent pass as a second set of eyes against a different knowledge base.

---

# Bucket 1: Scout Re-Aim

## A. Artifact verifier (mechanical, pass = 100% of checks)

Run against `SPEC.md` Bucket 1. Every check is binary.

**Structure (all 7 sections present, in order):**
- [ ] 1. Goal: exactly one paragraph, uses ubiquitous language from CONTEXT.md
- [ ] 2. The keeper-gate: a table with exactly 3 gate checks (G1 recent, G2 authentic, G3 restaurant-ops-relevant); plus a `keeper_decision` routing block mapping keep/needs_review/drop onto live `review_status`
- [ ] 3. Descriptive tags: a table; every tag declares its source vocab AND nullability
- [ ] 4. Data model changes: names `theme` as the load-bearing new field; states nullable + NO CHECK
- [ ] 5. What does NOT change: explicitly names Echo, belief-classify-retained, fetchers, dedup, scheduler, trending-not-built
- [ ] 6. Build slices: a table; every slice has a concrete checkpoint ("done =")
- [ ] 7. Risks / open questions: R1 (theme-vocab) present and marked RESOLVED via primary enum + `other`/`theme_other`; any genuinely-open risks (R2 calibration) still listed

**Content correctness:**
- [ ] Every gate check (G1-G3) states a keep-vs-drop rule; G1 states the `posted_at IS NULL` rule
- [ ] G2 is marked lean-inclusive (ambiguous then needs_review, not main queue); rubric outputs are enums + evidence span + per-gate confidence
- [ ] G3 is pure restaurant-ops-relevance (domain-filter); K&L-actionability is `kl_action_path` NON-gating metadata, explicitly OUT of the gate (no belief-fit smuggle)
- [ ] `theme` required on keep/needs_review rows (`other` + `theme_other` for novelty); columns use LIVE names (`signal_type`, not `belief_slug`)
- [ ] Belief/ICA/symptom are described as nullable description, never as the gate
- [ ] References ADR 0001 by number
- [ ] Slice 1h (the gate flip) names the operator-confirm requirement; shadow mode (1f) precedes it; R1 is marked resolved

**Mechanics:**
- [ ] Zero em-dashes in the bucket (`grep -c` returns 0), a K&L house rule
- [ ] No fabricated counts/stats; every vocab size (10 beliefs, 10 symptoms) matches canon

**Pass condition:** every box checked. Any miss triggers auto-fix + re-verify; do not ship.

## B. Outcome verifier (real-data, numeric pass bar)

Verifies the built Scout surfaces valuable signals. **Timing (Codex #5):** baseline + old-vs-new comparison runs after **1f/1g** (shadow mode produces the comparison); the post-flip gate verification runs after **1h**. Slices 1a-1e alone do not yet produce a measurable surfaced set.

**Protocol (per grading round):**
1. Run Scout live (YouTube path; Reddit when unblocked).
2. Take a sample of **20 surfaced signals** (random from the run, not cherry-picked).
3. Grade each against the 3-dimension rubric (CONTEXT.md, Signal quality):
   - Authentic operator pain? (Y/N)
   - Actionable / restaurant-ops relevant? (Y/N)
   - Fresh / recent? (Y/N)
   - **Valuable = all three Y.**
4. Score = (# valuable) / 20.

**Three graders, compared (layered measurement):**
- **Layer 1, Greg (ground truth):** Greg grades the 20. His judgment is canonical.
- **Layer 2, Codex audit (cross-check):** Codex independently grades the same 20 against the rubric. Compare to Greg's; disagreements expose classifier blind spots AND rubric ambiguity.
- **Layer 3, downstream tracking:** deferred (no closed loop today, per CONTEXT.md). Not part of this bucket's gate.

**Pass bar (PRECISION): ≥80% valuable (16 of 20 or better), graded by Greg (Layer 1).** Measured on KEPT signals (`keeper_decision = keep`). Posts routed to `needs_review` (ambiguous) are graded separately and do NOT count against the precision bar (Codex #7).

**Recall safety-net (false negatives, Codex #13):** the precision sample only sees surfaced signals, so it cannot detect valuable signals the gate DROPPED. Each round ALSO grades a random sample of **20 dropped/auto-rejected harvested posts** against the same rubric. Any "valuable" post in the dropped sample is a false negative. Target: missed-valuable rate stays low (bar set after baseline). For a re-aim whose whole point is catching novel signals, this measure is non-optional.

**Baseline rule (drift protection):** the FIRST grading round is a baseline, not a pass/fail gate. If round 1 lands below 80%, that is the calibration gap to close (tune G2/G3 prompts), not a failure verdict. The 80% bar becomes a hard gate from round 2 onward, after one baseline + tune cycle. *(Greg may convert this to hard-gate-from-round-1; flagged decision.)*

**Sample-size note (Codex #12, logged-reject):** 20 is Greg's chosen precision/effort balance for the baseline. When the bar goes hard-gate, upgrade to 50+ surfaced posts over multiple runs with Wilson confidence intervals. Not adopted at baseline (rigor matters when tuning, not at first read).

**Codex-vs-Greg agreement (secondary metric):** track how often Layer 2 agrees with Layer 1. Large divergence means the rubric itself is underspecified and needs sharpening before the % bar means anything.

## C. Codex adversarial review (this bucket's spec, before build)

Both `SPEC.md` Bucket 1 and this file go to Codex read-only. Codex hunts: schema conflicts with the live `classified_posts`, the theme-vocab groupability hole (R1), whether the rubric is actually machine-judgeable, calibration/observability gaps, simpler alternatives, and any place "actionable" smuggles belief-fit back in. Loop until `VERDICT: APPROVED` or MAX_ROUNDS. Log to `PLAN-REVIEW-LOG.md`.

---

# Bucket 2: Validation Agent (v1)

## A. Artifact verifier (mechanical, pass = 100%)

Run against `SPEC.md` Bucket 2. Binary checks.

**Structure (all 7 sections present, in order):**
- [ ] 1. Goal: one paragraph; names the theme-rank REPORT + thin ledger + human-in-loop points; states the v1 report-first scope decision
- [ ] 2. What Validation does: a step table marking automated (V0-V2 report) vs manual (V3-V5 ledger); names the v2-deferred drafter
- [ ] 3. The verdict gate: `validated`/`crickets`/`pivot`/`pending` enum with threshold logic; lifecycle is `posted`/`counted`/`archived` (no `drafted` in v1)
- [ ] 4. Data model: thin `validation_tests` ledger with columns + types, repo conventions (run_id FK, UUID PK, CHECK, created_at); report writes nothing to it
- [ ] 5. What does NOT change / out of scope: names no-LLM-drafting (v2), no-agent-drafted-rows, no-auto-count, no-auto-post, no-/kl:write-coupling, Scout/Echo untouched, no magnet-building
- [ ] 6. Build slices: table; every slice has a checkpoint; 2c is the read-only report emitter (DB-write-free)
- [ ] 7. Risks: names the hard Scout-re-aim dependency (R1), unset-thresholds (R2), and the v1-too-manual risk (R5)

**Content correctness:**
- [ ] Ranks on THEME (not symptom); states why (sparsity/belief-fit), consistent with ADR 0001
- [ ] v1 scope is report+ledger-first; LLM probe-drafting + `drafted` lifecycle explicitly DEFERRED to v2 with rationale (don't build an unvalidated agent feature before the loop surfaces one signal)
- [ ] Verdict thresholds are operator-set params; NO executable default (missing = startup error), NOT asserted as a K&L-grounded number
- [ ] Crickets/pivot structurally CANNOT emit a build-greenlight; `can_build_magnet()` is the sole buildability surface, ported onto the thin ledger
- [ ] **Ledger row integrity (CHECKs, not just can_build_magnet):** 3-state lifecycle (posted/counted/archived) coupling stated (posted then verdict=pending + count null; counted then count + thresholds + thresholds_confirmed non-null + verdict!=pending; archived RETAINS counted outcome, never reset to pending); threshold ordering `validate > crickets >= 0` (startup + row CHECK); provenance floor via `selection_source` (NOT NULL, no default; no orphaned report-backed row); the CHECK and `can_build_magnet()` cannot disagree (validated requires confirmed thresholds)
- [ ] Ranks on THEME explicitly because theme is dense/required and symptom is sparse/K&L-framed (would fragment counts + smuggle belief-fit, contra ADR 0001)
- [ ] V0 preflight checks ELIGIBLE ROWS (keep + theme non-null + rubric_version), not just column existence; excludes + COUNTS legacy-null rows in diagnostics; zero-eligible then insufficient_data not error; sufficiency gate uses MIN_ELIGIBLE_CORPUS_SIGNALS (eligible rows only, not total window)
- [ ] Demand count is manual v1; no throwaway own-scraper (one-harvest-pass principle)
- [ ] Report is read-only (writes nothing to `validation_tests`); agent only READS `classified_posts` + writes its own `agent_runs` log; Greg writes the ledger (no Scout/Echo mutation)

**Mechanics:**
- [ ] Zero em-dashes in the bucket
- [ ] No fabricated thresholds/stats asserted as real

**Pass condition:** every box checked. Miss then auto-fix + re-verify.

## B. Outcome verifier (real-data)

Validation v1 has TWO things to verify: did the REPORT surface the right thing to test, and does the gate behave.

- **Report quality (human-graded):** on a real Scout corpus, the report outputs its top-3 theme groups (with N + window) and the candidate verbatims under each. Greg judges: is the top theme actually what operators are most exercised about right now? Are the surfaced verbatims usable raw material (could Greg hand-write a postable probe from one)? Pass = Greg agrees the top pick is plausible AND at least one verbatim under it is probe-worthy. Thin-data corpora must show `insufficient_data` instead of a confident pick (R3). *(No drafted-probe grading in v1; there is no drafter.)*
- **Gate correctness (deterministic):** unit-level. Feed response_counts around the thresholds; assert validated/crickets/pivot map correctly and crickets/pivot/pending NEVER greenlight via `can_build_magnet()`. Pass = 100% (pure function once thresholds set).
- **Codex cross-check:** Codex independently ranks the same corpus by theme; compare to the report's ranking. Divergence flags ranking-logic or grouping-key ambiguity.
- **Deferred:** real demand outcome (did validated tests convert) needs the live posting loop; tracked once tests run, not a build-gate for v1. The v2 LLM drafter gets its own outcome verifier when built.

## C. Codex adversarial review (Bucket 2 spec, before build)

`SPEC.md` Bucket 2 + this section go to Codex read-only. Codex hunts: `validation_tests` schema conflicts with repo conventions, whether theme-ranking is well-defined on the real `classified_posts` shape, the null-`symptom_verbatim` fallback (R4), cold-start thin-data handling, any path where crickets/pivot could leak a build-greenlight, the dependency on Bucket 1 fields existing, **dead spec or accidental scope re-expansion** (the v1 report-first scope is LOCKED 2026-06-19; re-proposing the LLM drafter is out of bounds). Loop until `VERDICT: APPROVED` or MAX_ROUNDS. Log to `PLAN-REVIEW-LOG.md`.

---
*Bucket 1 eval drafted 2026-06-16. Pass bars set with Greg (≥80% / 20-signal sample).*
