# Roadmap: kl-agents

## Overview

This milestone delivers "one harvest pass, two consumers" against an existing, live system. Scout already harvests Reddit + YouTube, classifies posts against the 10 K&L false beliefs, and writes keepers to a review queue. This roadmap extends that single harvest pass to also emit operator *symptom* language (Phase 1), stands up a new sibling Validation agent that reads the enriched corpus and gates a lead-magnet build on real demand (Phase 2), and tracks the external unblock of Scout's Reddit Data API access (Phase 3). The build is agent-by-agent vertical slices: Phase 1 ships standalone value (richer Scout classification) and is the prerequisite for Phase 2; Phase 3 is an external-dependency phase that does not gate the build because the YouTube path carries Phases 1 and 2 live in the meantime.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Scout Symptom Extension (Part A)** - Scout's live classifier additionally emits `symptom_tag` + `symptom_verbatim`, persisted and proven on a live YouTube run
- [ ] **Phase 2: Validation Agent (Part B)** - New sibling agent ranks symptoms, runs a fill-in-the-blank demand test, and gates the lead-magnet build on real signal
- [ ] **Phase 3: Reddit Data API Access (Unblock)** - Scout's Reddit fetcher runs live against approved Data API credentials

## Phase Details

### Phase 1: Scout Symptom Extension (Part A)
**Goal**: Scout's single classify pass additionally captures magnet-testable operator symptoms (a closed 10-tag vocab + the operator's own pain words), persisted additively to `classified_posts`, with the existing review-queue gate untouched and a live YouTube run proving the new fields populate.
**Mode:** mvp
**Depends on**: Nothing (first phase; additive change to the live agent)
**Requirements**: SYMP-01, SYMP-02, SYMP-03, SYMP-04, SYMP-05, SYMP-06, SYMP-07, SYMP-08, SYMP-09
**Success Criteria** (what must be TRUE):
  1. Running Scout against YouTube populates non-null `symptom_tag` and `symptom_verbatim` on new `classified_posts` rows, with tags drawn only from the locked 10-tag vocab (SYMP-09 — live proof, since Reddit is blocked)
  2. An out-of-vocab `symptom_tag` from the model coerces to `None` and `symptom_verbatim` passes through unchanged, asserted by tests; the full suite stays green and `mypy --strict` is clean (SYMP-05, SYMP-08)
  3. What reaches the human review queue is byte-for-byte unchanged from before Part A — symptom fields are strictly additive and do not alter the belief-match + confidence gate (constraint)
  4. Migration `0008_symptom_classification.sql` adds both columns nullable with NO CHECK, applied to `agents_dev` then `agents_prod`; old rows stay null, new runs populate (SYMP-07)
**Plans**: TBD

Plans:
- [ ] 01-XX: TBD during plan-phase

### Phase 2: Validation Agent (Part B)
**Goal**: A new sibling agent reads Scout's enriched corpus, picks the highest-signal symptom, runs an operator-voice fill-in-the-blank demand test, records the test, and emits a verdict that gates whether a lead-magnet gets built — crickets and pivot must never trigger a build.
**Mode:** mvp
**Depends on**: Phase 1 (reads the `symptom_tag` / `symptom_verbatim` fields Part A emits)
**Requirements**: VALD-01, VALD-02, VALD-03, VALD-04, VALD-05
**Success Criteria** (what must be TRUE):
  1. The agent reads `classified_posts` filtered to non-null `symptom_tag` and surfaces the symptom ranked highest by frequency × confidence (VALD-01)
  2. The agent produces a fill-in-the-blank demand-test post built from `symptom_verbatim` / `symptom_tag` in operator voice — structural symptoms only, no hype, no value claimed before demonstrated (VALD-02)
  3. Each test is recorded to a `validation_tests` table with symptom_tag, copy, channel, posted_at, keyword, response_count, and verdict (VALD-03)
  4. The verdict gate emits exactly one of validated / crickets / pivot, and a crickets or pivot verdict does NOT trigger a magnet build (VALD-05)
  5. Response tracking is resolved at plan time — consume Echo's `kl_comments` if Echo is live, otherwise a minimal own counter (VALD-04)
**Plans**: TBD

Plans:
- [ ] 02-XX: TBD during plan-phase

### Phase 3: Reddit Data API Access (Unblock)
**Goal**: Scout's Reddit fetcher runs live against approved Reddit Data API credentials, restoring the Reddit harvest path alongside the working YouTube path.
**Mode:** mvp
**Depends on**: Nothing technically (external blocker; does not gate Phase 1 or Phase 2, which run live on the YouTube path). Sequenced last because it is escalation/admin work, not a code build.
**Requirements**: RDDT-01
**Success Criteria** (what must be TRUE):
  1. Approved Reddit Data API credentials exist and are configured for Scout's read-only, sequential, RBP-compliant fetcher (RDDT-01)
  2. A live Scout run against Reddit fetches new posts and writes classified rows (including the Phase 1 symptom fields) without tripping rate limits (~2 req/day, under 60/min)
  3. The escalation path that produced access is recorded (fresh ticket referencing prior, or r/redditdev) so the unblock is reproducible if revoked
**Plans**: TBD

Plans:
- [ ] 03-XX: TBD during plan-phase

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Scout Symptom Extension (Part A) | 0/TBD | Not started | - |
| 2. Validation Agent (Part B) | 0/TBD | Not started | - |
| 3. Reddit Data API Access (Unblock) | 0/TBD | Not started | - |
