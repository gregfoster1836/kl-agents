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
*Bucket 1 eval drafted 2026-06-16. Pass bars set with Greg (≥80% / 20-signal sample).*
