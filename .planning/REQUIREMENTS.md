# Requirements: kl-agents

**Defined:** 2026-06-14
**Core Value:** One harvest pass, many consumers — Scout reliably surfaces real operator pain (beliefs + symptoms) to a Supabase corpus every downstream K&L consumer reads.

## v1 Requirements

Requirements for the current milestone. Each maps to a roadmap phase.

### Symptom Extension (Part A)

Additive enrichment of the live Scout classifier. Vocab is LOCKED (10 tags) in `00 K&L Vault/01_Core_Systems/Messaging/Symptom Map.md`. Existing review-queue gate unchanged.

- [ ] **SYMP-01**: `Classification` model carries `symptom_tag: str | None` and `symptom_verbatim: str | None` (added after `reasoning`)
- [ ] **SYMP-02**: Classifier defines `SYMPTOM_TAGS` (closed 10-tuple) + `_SYMPTOM_GLOSS` dict, with a source-of-truth comment pointing at the vault Symptom Map, mirroring how `BELIEF_SLUGS`/`_BELIEF_GLOSS` are wired
- [ ] **SYMP-03**: `build_prompt` presents the symptom menu + instruction (symptom_tag exactly one tag or null; symptom_verbatim = shortest verbatim span showing the pain, or null)
- [ ] **SYMP-04**: `_tool_schema` includes both fields in `properties` and `required` (symptom_tag as `["string","null"]` enum; symptom_verbatim as `["string","null"]`)
- [ ] **SYMP-05**: `_parse_classification` defensively coerces an out-of-vocab `symptom_tag` to `None`; `symptom_verbatim` passes through
- [ ] **SYMP-06**: Storage layer persists `symptom_tag` + `symptom_verbatim` on upsert to `classified_posts`
- [ ] **SYMP-07**: Migration `0008_symptom_classification.sql` adds both columns nullable, NO CHECK; applied to `agents_dev` then `agents_prod`
- [ ] **SYMP-08**: Classifier tests assert symptom_tag coerces to None on garbage and symptom_verbatim passes through; full suite stays green; mypy --strict clean
- [ ] **SYMP-09**: A live YouTube Scout run populates the new fields in `classified_posts` (Reddit path pending access)

### Validation Agent (Part B)

New sibling agent. Reads Scout's enriched corpus; gates a lead-magnet build on real demand. Depends on Part A.

- [ ] **VALD-01**: Agent reads `classified_posts` filtered to non-null `symptom_tag`, ranked by frequency × confidence
- [ ] **VALD-02**: Agent produces a fill-in-the-blank demand-test post from `symptom_verbatim`/`symptom_tag` (operator voice, structural symptoms only, no hype)
- [ ] **VALD-03**: Agent records each test (symptom_tag, copy, channel, posted_at, keyword, response_count, verdict) to a `validation_tests` table
- [ ] **VALD-04**: Response tracking decided — consume Echo's `kl_comments` if Echo is live, else minimal own counter (resolve at plan time)
- [ ] **VALD-05**: Verdict gate emits validated / crickets / pivot; crickets/pivot must NOT trigger a magnet build

### Reddit Access (unblock)

- [ ] **RDDT-01**: Scout's Reddit fetcher runs live against approved Data API credentials (blocked on Reddit approval; escalation paths open)

## v2 Requirements

Acknowledged, deferred beyond the current milestone.

### Echo Activation

- **ECHO-01**: Echo promoted from migrations-only to a running agent scraping K&L's own LinkedIn/FB post-comment engagement into `kl_comments`/`kl_commenter_profiles`

## Out of Scope

| Feature | Reason |
|---------|--------|
| Second/duplicate harvester | Locked 2026-06-06: one harvest pass, two consumers. Scout is the sole harvester. |
| Republishing/quoting Reddit content in K&L published material | RBP compliance — read-only research, not redistribution |
| Changing the review-queue gate during Part A | Symptom fields are strictly additive |
| DB CHECK constraint on symptom_tag in 0008 | Vocab not yet battle-tested; classifier coercion enforces it; CHECK is a later migration |
| Model training on Reddit content | RBP compliance |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SYMP-01 | Phase 1 | Pending |
| SYMP-02 | Phase 1 | Pending |
| SYMP-03 | Phase 1 | Pending |
| SYMP-04 | Phase 1 | Pending |
| SYMP-05 | Phase 1 | Pending |
| SYMP-06 | Phase 1 | Pending |
| SYMP-07 | Phase 1 | Pending |
| SYMP-08 | Phase 1 | Pending |
| SYMP-09 | Phase 1 | Pending |
| VALD-01 | Phase 2 | Pending |
| VALD-02 | Phase 2 | Pending |
| VALD-03 | Phase 2 | Pending |
| VALD-04 | Phase 2 | Pending |
| VALD-05 | Phase 2 | Pending |
| RDDT-01 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 15 total (SYMP 9, VALD 5, RDDT 1)
- Mapped to phases: 15 ✓
- Unmapped: 0

---
*Requirements defined: 2026-06-14*
*Last updated: 2026-06-15 after roadmap creation (traceability populated, 100% coverage)*
