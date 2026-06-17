# Plan Review Log: Scout Re-Aim (SPEC.md Bucket 1)

Act 1 (grill-with-docs) complete. Spec locked to `SPEC.md` Bucket 1 + `SPEC-EVAL.md` Bucket 1; CONTEXT.md glossary + ADR 0001 updated. Artifact verifier passed (7 sections, ADR ref, 0 em-dashes). MAX_ROUNDS=5.

Codex reviews SPEC.md Bucket 1, SPEC-EVAL.md Bucket 1, CONTEXT.md, and docs/adr/0001 (read-only). Adversarial target: find what breaks the Scout re-aim before any code.

## Round 1 — Codex (thread 019ed158-e3a5-7073-a078-d0c62b22b487)

16 findings. VERDICT: REVISE. Codex read the live migrations and code; several findings are real defects verified against source.

**Accepted (real defects, fixed in revision):**
- #1 CRITICAL: spec named columns that don't exist. Live `classified_posts` has `signal_type` (not `belief_slug`), `ica_stage` (CHECK), single `confidence`, `key_quote`; NO `belief_slug`, NO `symptom_tag`. Verified directly against 0002_classified_posts.sql. Spec must use real column names.
- #2: migration (1e) must precede storage writes of new fields, else Supabase rejects unknown columns. Reordered slices.
- #3: keeper rule duplicated in main.py (posts_queued) + posts.py (review_status). Add one shared `is_keeper()`.
- #4: dedup (`source_url` unique + `ignore_duplicates=True`) blocks old rows from getting new fields. Must state legacy-null vs. backfill.
- #6: rubric judgments must be enums + evidence span + per-gate confidence, not free text.
- #11: "operator could plausibly want help" re-imposes belief-fit (the exact trap flagged in grill Q8). Gate = restaurant-ops problem present only; K&L-actionability becomes non-gating metadata.
- #13 IMPORTANT: outcome verifier grades only surfaced signals; cannot detect dropped valuable signals (false negatives). For a re-aim about catching novel signals, this is a real hole. Add a random-rejected-sample recall measure.
- #16: shadow-mode rollout (run new rubric beside old gate, compare, then flip). Right de-risking for the highest-risk file.

**Partially accepted (spirit, detail deferred to slice design):**
- #5/#14: per-gate confidence + drop_reason/keeper_decision observability. Accept shape; full column list is slice detail.
- #8/#9: theme = primary canonical enum + `theme_other` for novel pressures (resolves open R1); version/index are slice-1e detail.
- #10: split G3 into gate (`restaurant_ops_relevant`) + `kl_action_path` enum (content|magnet|outreach|none) as metadata.

**Rejected (logged reason):**
- #7: "ambiguous-keep vs 80% bar conflict" dissolves once ambiguous routes to a flagged bucket + precision/recall measured separately (#13 fix). Folded into #13, not separate.
- #12: 50-100 sample + Wilson intervals. Greg explicitly chose 20 as precision/effort balance; round 1 is a baseline, not a gate. Statistical rigor is a "when the bar goes hard-gate" upgrade, noted in SPEC-EVAL, not adopted now. Claude is final arbiter; not overriding Greg's sample-size decision on Codex's say-so.

## Round 2 — Codex (resume, read-only)

6 findings, all ACCEPTED (no rejects). Most are consistency gaps introduced BY the round-1 fixes. #1/#2/#6 would have caused real build-time bugs.

- #1: `needs_review` keeper_decision had no mapping onto the live `review_status` CHECK (verified: `pending|auto_rejected|approved|rejected|actioned`). Fix: map keep->pending, drop->auto_rejected, needs_review->pending + keeper_decision='needs_review' + dedicated review query. No CHECK migration needed.
- #2: rubric requires evidence spans but no column holds them (`key_quote` is belief evidence). Fix: add `authentic_evidence`, `restaurant_ops_evidence` nullable + parser tests.
- #3: theme nullable contradicts "every kept signal carries a theme." Fix: enforce in code that keep/needs_review rows have theme (use `theme='other'` + `theme_other` for novelty); nullable only for legacy/drop.
- #4: SPEC-EVAL artifact checks stale vs revised SPEC (still say slice 1d, "actionable", R1-unresolved). Fix: sync to 1h flip, restaurant-ops-relevance, R1-resolved.
- #5: outcome verifier timing said "after 1a-1e"; should be 1f/1g (shadow) + 1h (post-flip). Fix.
- #6: `posted_at` is nullable in live schema; G1 recency gate needs explicit null rule. Fix: `posted_at is null` -> drop_reason='missing_posted_at', tested in is_keeper().

## Round 3 — Codex (resume, read-only)

Codex: "substantive round-2 blockers are resolved... no remaining schema/rubric blocker after [two] edits." 2 findings, both pure internal-consistency bugs (my own leftover contradictions), both ACCEPTED + fixed:
- #1: SPEC-EVAL artifact verifier self-contradicted (required R1 "unresolved" in one check, "resolved" in another) -> mechanically unsatisfiable. Fixed: R1 check now requires present + marked-resolved.
- #2: stale prose "1d ships in SHADOW mode" vs table's correct 1f. Fixed to "1f ships in SHADOW mode before 1h flips the gate."
No schema/rubric blockers remain per Codex. VERDICT: REVISE (on the 2 cosmetic edits only).

## Round 4 — Codex (resume, read-only)

"Confirmed... I don't see any remaining material schema, rubric, migration-order, observability, or eval-timing blockers in Bucket 1." **VERDICT: APPROVED.** Converged in 4 rounds. Awaiting Greg sign-off before any code.
