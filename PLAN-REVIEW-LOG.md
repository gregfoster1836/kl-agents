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

# Plan Review Log: Light Agent Platform Contract (Bucket 3)

Plan: `PLAN.md` (Bucket 3). Act 1 = grill-with-docs, re-shaped: Claude decided mechanical branches with stated defaults; Greg decided the two judgment branches (Decision A: agent_runs core columns + JSONB metrics; Decision B: generalize where free, zero speculative code). Codex thread `019eece4-32dd-7250-86bf-70e4d07fcd21` (fresh, separate from Buckets 1+2). Read-only every round. MAX_ROUNDS=5. Adversarial target: does the extraction cut the real seam without breaking live Scout, mishandling agent_runs history, or exceeding the Q1 "unblock Validation or fix a real seam" rule.

## Round 1: Codex (thread 019eece4-32dd-7250-86bf-70e4d07fcd21)

10 findings, VERDICT: REVISE. All 10 verified against live code and accepted + applied:
- #1: slice order wrote `metrics` (3b) BEFORE the migration adding it (3c) -> "column does not exist" window. Fix: reordered - migration is now 3b, lifecycle code 3c.
- #2: fetcher-base move is NOT free - `fetchers/base.py:16` imports `agents.scout.models`, so moving to `shared/` re-introduces a `shared->agents` violation (or forces models to move, scope Validation doesn't need). Fix: DEFERRED out of Bucket 3 to the 3rd-source slice; dropped from 3d.
- #3: "grep-asserted" import invariant is noisy (matches comments/prose). Fix: AST-based test over `shared/**/*.py` rejecting import roots == `agents`.
- #4: missed non-main callers of old `finish_run` kwargs - `scripts/smoke_storage.py:183` + tests `test_orchestrator.py`/`test_storage.py`. Fix: 3c updates ALL callers + tests; no shim (we own every caller).
- #5: "cut straight to metrics" risks breaking column-level run totals; `agent_runs` is shared with Echo (migrations/README.md:9). Fix: transition mirror-write (metrics + nullable legacy counts); remove legacy writes in a later bucket after Echo+dashboard audit.
- #6: migration didn't backfill `metrics` for existing Scout history -> reports silently zero old runs. Fix: `0010` backfills metrics from the four count columns where agent_name='scout'.
- #7: `finish_run(metrics)` accepts non-JSON-safe / misleading payloads, rejected late+opaquely by JSONB. Fix: `MetricValue = str|int|float|bool|None` (flat scalars), validate before write, test rejection.
- #8: status semantics listener-biased - `0001_agent_runs.sql:30` defines `partial` as "some subreddits failed". Fix: rewrite comment agent-neutral in 3b; contract states `partial` OPTIONAL.
- #9: logging not fully agent-agnostic - formatter `logging_setup.py:58` does `getattr(record,"agent","scout")`, a second hardcoded default beyond `configure`. Fix: drop BOTH defaults; required agent name; update Scout callers.
- #10: contract's `snapshot: dict` imprecise - Scout implements it as a `@property` (`config.py:90`), Validation might use a method. Fix: contract specifies property/attribute access; enforce via `KLAgentConfig` Protocol.

Note on the resume: round-1 launch had been interrupted in a prior session (mechanics, not a plan defect - the saved prompt was sound). Re-ran as a fresh `codex exec -s read-only`. Round 2 = resume this thread.

## Round 2: Codex (resume, read-only)

Confirmed 7 round-1 fixes close (#1 ordering, #2 fetcher defer, #3 AST test, #5 mirror-write, #7 MetricValue, #8 optional partial, #10 snapshot). 6 new findings - round-1 fixes exposed follow-on breaks. VERDICT: REVISE. All 6 accepted + applied:
- #1: Goal + Decision B prose still extracted "fetcher base" while slices correctly deferred it (self-contradiction). Fix: Goal/Decision B now state the defer + the `agents.scout.models` reason; Q1 floor overrides Decision B.
- #2 (the deep one): logging fix was incomplete. `configure(agent="scout")` does NOT set `record.agent` - `getLogger(agent)` only sets `record.name`; today the `"agent"` field comes ENTIRELY from the formatter fallback. Removing the fallback (r1 #9) without another source breaks EVERY log line + `getLogger("scout")` fetcher loggers. Fix: inject agent at `JsonFormatter.__init__(agent)`, emit directly, no record lookup, no fallback.
- #3: 3d missed the 8 `configure()` call sites in `test_orchestrator.py` (+ smoke_youtube/smoke_reddit) that pass only `level=`; required-arg change breaks them. Fix: 3d lists all call sites.
- #4: deleting `storage/runs.py` breaks `storage/posts.py:27` (imports `RunHandle`), not listed. Fix: 3c repoints posts.py too; full importer set enumerated.
- #5: stale slice ref - the "all callers" bullet said 3b, but lifecycle code is now 3c. Fix: corrected to 3c.
- #6: backfill compared `metrics = '{}'` (implicit cast). Fix: `metrics = '{}'::jsonb`.

## Round 3: Codex (resume, read-only)

Confirmed all 6 round-2 fixes close (no metrics-write before 3b; formatter-injected agent covers all log paths; configure() call sites complete; deleted-module importer set complete incl. posts.py; 3c ref corrected; jsonb cast right). 1 new finding, VERDICT: REVISE:
- #1: a stale "Key decisions & tradeoffs" bullet ("Why generalize the fetcher/logging moves") still called the fetcher move "free generality / already agent-agnostic / softest deferrable" - reintroducing the round-1 false premise. Fix: split into "Why move logging" (real seam) + "Why DEFER the fetcher base" (imports agents.scout.models, not free).

## Round 4: Codex (resume, read-only)

Final whole-doc consistency sweep: fetcher-base uniformly DEFERRED everywhere (Goal, Decision B, mechanical branches, key decisions, slices, risks, out-of-scope), no residual "free/agent-agnostic/extract it" language, no regression across rounds 1-3. **VERDICT: APPROVED.** Converged in 4 rounds. Awaiting Greg final sign-off before any code. (Bucket 3 Codex thread: `019eece4-32dd-7250-86bf-70e4d07fcd21`.)
