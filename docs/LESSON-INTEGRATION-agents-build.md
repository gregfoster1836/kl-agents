# Lesson Integration — Agents-Repo Build Items

Source review: K&L Vault `03_Projects/Lesson Integration/` (item-by-item review 2026-06-07/08 with Greg). These items were carved out of the vault build queue because they execute HERE, in the `03 KL Agents` Python repo (separate Supabase, own GSD/.claude), not the vault. Root any session for these in this repo.

Rank/context lives in the vault's `Lesson Integration.md`. This doc is the execution pointer for the agents-repo slice only.

## Item 1 — Scout symptom extension (Part A) + Validation agent (Part B)
- **Decided architecture (Greg, 2026-06-06): one harvest pass, two consumers.** Scout stays the sole harvester. Its classifier is EXTENDED to also emit `symptom_tag` + `symptom_verbatim` (a magnet-testable symptom, distinct from the 10 false-belief slugs). A NEW sibling Validation agent reads Scout's enriched output and runs the fill-in-the-blank demand test that gates a lead-magnet build.
- **Full spec (authoritative):** `03 KL Agents/docs/2026-06-06 Scout Symptom Extension + Validation Agent Spec.md`.
- **Part A** = Scout symptom-field extension (additive, low-risk). **Part B** = the Validation agent.
- **Supabase:** Agents DB `zbokrrcexjecrkpogjqv`.
- **Status:** fully scoped, waiting on an agents-rooted execution session. Nothing left to decide.
- **Wire-in:** Scout's enriched corpus feeds the Validation agent AND the vault's item-5a story index (validated operator language). The corpus is the database; both consume it.

## Item 10 (partial) — A/B-test verification agent
- The vault builds two LOGS (A/B content-test log + conversational-reaction log) in Obsidian. The A/B log MAY warrant a verification agent that validates A/B results, that agent, if built, lives HERE (same pattern as item 1: vault artifact + agents-repo verifier).
- **Status:** candidate, not yet scoped. Confirm the A/B log exists and has data worth verifying before building.

## Notes
- These items pair a vault artifact with an agent; keep the artifact in the vault and the agent here. Do not duplicate the data store.
- Per the vault's nothing-ships-orphaned rule: each agent here names its consumer + trigger.
