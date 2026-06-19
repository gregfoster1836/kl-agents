# Plan Review Log: Scout Re-Aim (SPEC.md Bucket 1)

Act 1 (grill-with-docs) complete. Spec locked to `SPEC.md` Bucket 1 + `SPEC-EVAL.md` Bucket 1; CONTEXT.md glossary + ADR 0001 updated. Artifact verifier passed (7 sections, ADR ref, 0 em-dashes). MAX_ROUNDS=5.

Codex reviews SPEC.md Bucket 1, SPEC-EVAL.md Bucket 1, CONTEXT.md, and docs/adr/0001 (read-only). Adversarial target: find what breaks the Scout re-aim before any code.

## Round 1: Codex (thread 019ed158-e3a5-7073-a078-d0c62b22b487)

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

## Round 2: Codex (resume, read-only)

6 findings, all ACCEPTED (no rejects). Most are consistency gaps introduced BY the round-1 fixes. #1/#2/#6 would have caused real build-time bugs.

- #1: `needs_review` keeper_decision had no mapping onto the live `review_status` CHECK (verified: `pending|auto_rejected|approved|rejected|actioned`). Fix: map keep->pending, drop->auto_rejected, needs_review->pending + keeper_decision='needs_review' + dedicated review query. No CHECK migration needed.
- #2: rubric requires evidence spans but no column holds them (`key_quote` is belief evidence). Fix: add `authentic_evidence`, `restaurant_ops_evidence` nullable + parser tests.
- #3: theme nullable contradicts "every kept signal carries a theme." Fix: enforce in code that keep/needs_review rows have theme (use `theme='other'` + `theme_other` for novelty); nullable only for legacy/drop.
- #4: SPEC-EVAL artifact checks stale vs revised SPEC (still say slice 1d, "actionable", R1-unresolved). Fix: sync to 1h flip, restaurant-ops-relevance, R1-resolved.
- #5: outcome verifier timing said "after 1a-1e"; should be 1f/1g (shadow) + 1h (post-flip). Fix.
- #6: `posted_at` is nullable in live schema; G1 recency gate needs explicit null rule. Fix: `posted_at is null` -> drop_reason='missing_posted_at', tested in is_keeper().

## Round 3: Codex (resume, read-only)

Codex: "substantive round-2 blockers are resolved... no remaining schema/rubric blocker after [two] edits." 2 findings, both pure internal-consistency bugs (my own leftover contradictions), both ACCEPTED + fixed:
- #1: SPEC-EVAL artifact verifier self-contradicted (required R1 "unresolved" in one check, "resolved" in another) -> mechanically unsatisfiable. Fixed: R1 check now requires present + marked-resolved.
- #2: stale prose "1d ships in SHADOW mode" vs table's correct 1f. Fixed to "1f ships in SHADOW mode before 1h flips the gate."
No schema/rubric blockers remain per Codex. VERDICT: REVISE (on the 2 cosmetic edits only).

## Round 4: Codex (resume, read-only)

"Confirmed... I don't see any remaining material schema, rubric, migration-order, observability, or eval-timing blockers in Bucket 1." **VERDICT: APPROVED.** Converged in 4 rounds. Awaiting Greg sign-off before any code.

---

# Plan Review Log: Validation Agent v1 (SPEC.md Bucket 2)

Spec: `SPEC.md` Bucket 2 + `SPEC-EVAL.md` Bucket 2. Reads Bucket 1's re-aimed corpus; new sibling agent. Codex thread `019ed947-0557-76b1-8790-3a78cdda104f` (separate from Bucket 1). MAX_ROUNDS=5. Converged in 4. Adversarial target: schema conflicts, theme-ranking well-definedness, thin-data/cold-start, any crickets/pivot greenlight leak, Bucket-1 dependency, scope.

## Round 1: Codex (thread 019ed947...)

11 findings. VERDICT: REVISE. 10 accepted + applied; #11 was an open SCOPE PROPOSAL escalated to Greg (not a defect).

**Accepted (applied to the full-agent spec):**
- #1: `symptom_verbatim` is a hard Bucket-2 dependency (probe built from it) but didn't exist in Bucket 1's migration. Fix: added to Bucket 1's `0008` migration.
- #2: ranker must rank by signal COUNT, not the old `confidence` (that column is belief-confidence). 
- #3: group by `coalesce(nullif(theme_other,''),theme)` so `theme='other'` doesn't collapse novel pressures.
- #4: split lifecycle (`status`) from judgment (`verdict`): two orthogonal fields.
- #5: buildability exposed ONLY via `can_build_magnet()` (structure, not prose), so crickets/pivot can't leak a greenlight.
- #6: thresholds operator-set, NO executable defaults; missing = startup error (no fabricated number drives a decision).
- #7: sufficiency gates (MIN_THEME_SIGNALS / MIN_CORPUS_SIGNALS) emit `insufficient_data` rather than a one-post probe.
- #8: `source_signal_id` UUID FK (repo convention), not a URL.
- #9: `channel` CHECK constrained to known v1 channels (mirrors kl_comments.source).
- #10: V0 preflight fails closed on a pre-re-aim corpus.

**Escalated to Greg (scope, not a defect):**
- #11: Codex proposed v1 is too much agent before one real demand test, so ship the read-only REPORT + thin ledger first, defer the LLM probe-drafter + full schema. Greg called context-window-full before answering. **Resolved 2026-06-19: Greg ADOPTED #11 (scope A).** Bucket 2 re-scoped to report+ledger-first; drafter deferred to v2.

## Round 2: Codex (resume, read-only), post re-scope

Re-reviewed the re-scoped (report-first) Bucket 2. 8 findings, VERDICT: REVISE. The thinner schema EXPOSED integrity gaps the fat schema had hidden. All 8 accepted + applied:
- #1: SPEC-EVAL still demanded "theme-not-symptom rationale" that the re-scope dropped from SPEC. Fix: re-added the sentence to V1.
- #2: "full 17-column schema deferred" became literally false (thin ledger is 17 cols). Fix: "drafter-owned schema" deferred.
- #3+#4 (consolidated): nullable run_id/source_signal_id/symptom_verbatim could orphan a row; an insufficient-data-backed row could read as report-backed. Fix: new `selection_source` enum (`report_ranked|report_insufficient_data|off_report`) NOT NULL + provenance-floor CHECK. (Codex r3 confirmed this is sufficient without a separate provenance_note.)
- #5: ledger CHECKs let the row lie (posted+validated, counted+null-count, counted-but-pending). Fix: lifecycle/verdict/count coupling CHECK.
- #6: no threshold ordering invariant, so a count could satisfy both validated and crickets. Fix: `validate > crickets >= 0`, startup + row CHECK; pivot = open interval.
- #7 (sharpest): V0 preflight only checked column EXISTENCE; Bucket 1's no-backfill leaves legacy rows null, so a re-aimed DB full of legacy-null rows passes and produces garbage rankings. Fix: preflight restricts to ELIGIBLE rows (keep + theme non-null + rubric_version); excludes + COUNTS legacy rows in diagnostics.
- #8: SPEC-EVAL's Codex-review clause still said "simpler alternatives," reopening the locked scope. Fix: "dead spec or accidental scope re-expansion."

## Round 3: Codex (resume, read-only)

3 findings, VERDICT: REVISE. Codex confirmed the two contested r2 calls (selection_source sufficient; keep NOT NULL no default). Found that the r2 fixes interacted:
- #1: counted-row CHECK required thresholds non-null but NOT confirmed, so a row could be counted+validated while `can_build_magnet()` returned false (CHECK and gate disagree). Fix: counted-row CHECK also requires `thresholds_confirmed_by/at` non-null.
- #2: r2's coupling CHECK forced `archived` to pending/null-count, making it impossible to archive a finished test without erasing its outcome. Fix: 3-state lifecycle, archived RETAINS the counted outcome; can_build_magnet()'s status='counted' requirement denies the greenlight.
- #3: r2's V0 eligible-rows fix made `MIN_CORPUS_SIGNALS` ambiguous: 328 legacy-null rows could satisfy corpus-sufficiency while 12 eligible rows drive ranking. Fix: renamed `MIN_ELIGIBLE_CORPUS_SIGNALS`, both sufficiency counts over eligible rows only.

## Round 4: Codex (resume, read-only)

Codex walked the coupling-CHECK truth table (fresh insert, post->counted, counted->archived, direct archived insert): admits exactly the valid states, rejects exactly the lying ones, no valid operational state accidentally rejected. Confirmed archived preserves outcome AND denies greenlight without a special clause; the 3 CHECKs don't conflict; SPEC.md/SPEC-EVAL.md aligned. One non-blocking impl reminder (test `archived+validated => can_build_magnet=false`) folded into slice 2d. **VERDICT: APPROVED.** Converged in 4 rounds. Awaiting Greg final sign-off before any code.
