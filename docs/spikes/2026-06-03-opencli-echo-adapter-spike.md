# Spike — OpenCLI as Echo's extraction layer

**Status:** PROPOSED (not started)
**Created:** 2026-06-03
**Decision record:** `.claude/decisions.md` § 2026-06-03 OpenCLI evaluated
**Owner:** TBD
**Timebox:** 1 working session (~3-4 hrs). If the core question is not answered in that window, stop and record findings; do not let it sprawl.

## The question this spike answers

Does [OpenCLI](https://github.com/jackwener/OpenCLI)'s LinkedIn and Facebook adapters return the comment data Echo requires, reliably enough to replace Echo's hand-rolled DOM selectors?

This is a GO/NO-GO probe, not an implementation. We are buying down ONE risk: the unverified assumption that OpenCLI's network/pattern-based adapters surface Echo's exact field contract. Everything else about adopting OpenCLI is already decided (see decision record).

## Why this spike exists

Echo (Agent 2, porting from `~/00-coding/active/kl-engagement-feed/`) scrapes LI Personal / LI Page / FB Page engagement using DOM selectors anchored on framework-derived attributes (`div[componentkey^="replaceableComment_urn:li:comment"]`, `[data-ad-comet-preview="message"]`). The engagement-feed reference doc lists selector drift as a *recurring named failure mode*:

- "selectors drifted; scraper returned bad records"
- "selectors returning empty arrays" → `new_comments` always 0

OpenCLI extracts via network inspection + pattern detection (SPA/token/streaming) rather than DOM selectors, and ships maintained LI + FB adapters (v1.8.2, active project). IF its adapters return Echo's fields, we trade self-maintained selectors for a maintained adapter library — directly attacking the drift failure mode. The "IF" is what this spike tests.

## The contract OpenCLI must satisfy (Echo's REQUIRED_FIELDS)

From `kl-engagement-feed/src/kl_engagement_feed/_common.py` `REQUIRED_FIELDS` — every comment record Echo accepts MUST carry these 9 fields, non-None:

| Field | What it is | OpenCLI must provide? |
|---|---|---|
| `comment_id` | stable unique id for the comment | ☐ |
| `source` | one of VALID_SOURCES (li_personal / li_page / fb_page) | ☐ (we set this; adapter must let us distinguish) |
| `post_id` | the post the comment belongs to (LI activity/ugcPost URN, FB post id) | ☐ |
| `post_url` | canonical URL of the post | ☐ |
| `commenter_name` | display name | ☐ |
| `commenter_profile_url` | the commenter's profile URL (feeds `kl_commenter_profiles`) | ☐ |
| `comment_text` | the comment body | ☐ |
| `reaction_count` | non-negative int (likes/reactions on the comment) | ☐ |
| `captured_at_iso` | capture timestamp (we set this) | ☐ (we set this) |

Plus, for the downstream Haiku commenter classifier (`kl_commenter_profiles`): a `headline` per commenter is desirable (the classifier hashes `(profile_url, headline)`). Note whether OpenCLI surfaces the commenter headline.

Dedup key is `(source, post_url, commenter_handle, timestamp_iso)` — so `post_url` + a stable commenter identifier + a timestamp are the load-bearing trio. If OpenCLI can't give a stable `commenter_profile_url` and a per-comment timestamp, dedup breaks and the spike is a NO-GO regardless of the other fields.

## Method

Run against the SAME inputs Echo's Phase 1 baseline used, so results are directly comparable:

1. **Install + connect.** `npx skills add jackwener/opencli`, install the Chrome extension, start the daemon (port 19825). Log the isolated Chrome profile into LinkedIn AND Facebook (reuse `~/.browser-harness-profile` if compatible, or a fresh profile — note which).
2. **LI Personal.** Point OpenCLI's LinkedIn adapter at a recent Greg LI Personal post (one from the 2026-05-14 baseline window if still live). Capture raw `--format json` output for its comments.
3. **LI Page.** Same against a K&L Page post (note: some Page posts use `ugcPost:` URN, not `activity:` — confirm OpenCLI handles both).
4. **FB Page.** Same against a K&L FB Page post (admin view).
5. **Field-map.** For each source, map OpenCLI's output keys onto the 9 REQUIRED_FIELDS. Mark each present / absent / derivable.
6. **Run the real validator.** Transform one OpenCLI comment per source into Echo's record shape and run `validate_comment()` on it (import from the standalone repo or the ported `agents/echo/_common.py`). Green = the contract holds.
7. **Resilience note (qualitative).** Record whether extraction relied on anything that looks UI-version-specific. The whole point is resilience over selectors; note if OpenCLI's adapter itself looks brittle.

## Acceptance criteria (GO / NO-GO)

**GO** (worth a full Echo-adapter port) requires ALL of:
- [ ] All 9 REQUIRED_FIELDS present or cleanly derivable for **all three sources**
- [ ] `commenter_profile_url` is stable and real (not a redirect/tracking URL that breaks dedup)
- [ ] A per-comment timestamp is available (for the dedup key)
- [ ] `validate_comment()` passes on a transformed OpenCLI record for each source
- [ ] Comment **count** for a baseline post is within ~10% of what Echo's scraper returned for the same post (no silent truncation)
- [ ] `commenter_headline` available OR an acceptable substitute for the Haiku classifier

**NO-GO** if any of: a load-bearing dedup field (post_url / profile_url / timestamp) is missing or unstable; FB admin-view comments are unreachable; counts are materially short; or setup proves more fragile than the current CDP+selector path.

**PARTIAL** (record and decide case-by-case): LI works cleanly but FB does not (Echo could run OpenCLI for LI, keep selectors for FB) — note this as a viable hybrid.

## Out of scope (do NOT do in this spike)

- Any production wiring into `agents/echo/`
- Replacing the working selectors before GO is confirmed
- Anything touching Scout or the Reddit fetcher (decided: official API only)
- Scheduling / cron

## Output

Write findings to the bottom of THIS file under a `## Findings (YYYY-MM-DD)` heading: the field-map table per source, the validate_comment result, the count comparison, and a one-line GO / NO-GO / PARTIAL verdict. Update the decision record's Decision 2 with the verdict. If GO, the follow-on is a real Echo-adapter implementation plan (separate doc).

## Related
- `.claude/decisions.md` § 2026-06-03 OpenCLI evaluated
- Echo design spec: `~/00-coding/active/00 K&L Vault/docs/superpowers/specs/2026-05-17-kl-agents-echo-design.md`
- Engagement-feed reference (selector failure modes): `~/00-coding/active/00 K&L Vault/memory/reference_kl_engagement_feed.md`
