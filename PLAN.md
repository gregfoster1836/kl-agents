# Plan: Bucket 3 — Light Agent Platform Contract
_Locked via grill-with-docs (re-shaped: mechanical branches decided by Claude with stated defaults; Greg decided the two judgment branches). Terms per CONTEXT.md. Extracted against Scout (Bucket 1) AND Validation (Bucket 2), per locked decision: Validation is NOT a listener._

## Goal

Make the kl-agents platform spine REAL instead of convention: extract the shared agent infrastructure (DB client, run lifecycle, fetcher base, structured logging, config surface) into `shared/` so it does not depend on any single agent, and write a thin "what makes a kl-agent" contract doc that the next agent (Validation) is built on. Light contract: a small, documented, enforced surface — NOT a base class or framework. The deliverable proves itself by Validation building cleanly on it with zero copy-paste of Scout internals and zero `shared/ → agents/` imports.

## Grill decisions (what was settled, and by whom)

**Q1 — Contract scope (Claude, Greg confirmed the governing rule):** Doc + minimal extraction. **"Minimal" = a code move is in scope ONLY if it (a) unblocks Validation or (b) fixes a real seam.** No refactor-for-elegance, no renames, no speculative abstraction. Every move below is justified against this test.

**Decision A — agent_runs over-fit (Greg):** Core columns + JSONB `metrics`. The shared `agent_runs` table currently hardcodes four LISTENER counts (`posts_fetched`, `posts_dedup_skipped`, `posts_classified`, `posts_queued`, all NOT NULL DEFAULT 0). Validation fetches/classifies nothing, so those would be permanent zeros — a meaningful-looking lie. Fix: the contract owns the UNIVERSAL columns; each agent owns its own work-specific metrics in a JSONB column. No fake zeros, no per-agent column sprawl.

**Decision B — scope horizon (Greg):** Generalize where free, no speculative code. Extract against Scout+Validation as locked; where a choice is equally easy either way, pick the one that obviously generalizes (JSONB metrics, agent-agnostic fetcher base). Write ZERO code for hypothetical agent #4 (prospecting, new sources). Generality is a tiebreaker, never added surface.

**Mechanical branches (Claude, stated defaults — Codex's job to attack):**
- **The seam (Q2):** `StorageConfig` is 3 fields (`supabase_url`, `service_role_key`, `schema`), nothing Scout-specific — mislocated, not mis-designed. Move it to `shared/config.py`. Both `shared/db/client.py` and Scout's `Config` import it from `shared/`. Rejected: a Protocol (over-machinery for a 3-field bag) and moving the whole config loader (pulls more than Validation needs — violates the Q1 rule; logging/env sharing is justified separately below, the rest is not).
- **Run lifecycle:** Extract `RunHandle`, `start_run`, `finish_run`, the `_finish_safely` "a bookkeeping failure must not mask the real error" pattern, and the `status → exit-code (success=0 / partial=1 / failed=2)` mapping into `shared/runs.py`. Generalize `finish_run`'s signature from fixed count kwargs to `status` + `metrics: dict[str, Any]` + `error_summary` (follows Decision A). `_finish_safely` becomes a documented contract step.
- **Config surface (the contract's config requirement):** every kl-agent's config object MUST expose `agent_name: str`, `agent_version: str`, `snapshot: dict` (secrets stripped), and `storage: StorageConfig`. This is already latent — `shared/runs.py` reads exactly these, and config.yaml already carries `agent.name`/`agent.version` at the top level for every agent. The doc makes it explicit; no enforcement machinery beyond the structural requirement.
- **Logging:** `logging_setup.py` is already agent-agnostic (`configure(level, agent=...)`, formatter reads `record.agent`). Move to `shared/logging_setup.py`; make `agent` a required argument (drop the `"scout"` default so no agent silently mislabels its logs). Justified independently: Validation needs identical structured logging — a real shared seam, not creep.
- **Fetcher base:** `fetchers/base.py` (the `Fetcher` Protocol + `FetchError`) is already source-agnostic. Move to `shared/fetchers/base.py` so adding a source (future: HN, etc.) stays drop-in. NOTE: Validation has no fetchers — this move is justified by Decision B (generalize where free) + the existing protocol's drop-in promise, NOT by Validation. If Codex judges this as out-of-scope-for-Validation, it is defensible to DEFER this one move to whenever a 3rd source lands; flagged as the softest move in the plan.

## Approach (build slices, each independently shippable + checkpointed)

Ordered so the dependency seam is cut before anything builds on it. Migration before code that writes new columns (the Bucket-1 lesson).

| Slice | Scope | Checkpoint (done =) |
|-------|-------|----------------------|
| 3a | **Cut the seam.** Create `shared/config.py` with `StorageConfig`. Repoint `shared/db/client.py` and `agents/scout/config.py` to import it from `shared/`. | `shared/` imports nothing from `agents/` (grep-asserted); Scout still runs; mypy clean; tests green |
| 3b | **Extract the run lifecycle.** Create `shared/runs.py` (`RunHandle`, `start_run`, `finish_run(status, metrics, error_summary)`, `finish_safely`, `status_to_exit_code`). Scout's `agents/scout/storage/runs.py` becomes a thin re-export OR is deleted with imports repointed. Scout's `main.py` passes its counts as `metrics={...}`. | one lifecycle implementation; Scout writes its counts via `metrics`; tests green; mypy clean |
| 3c | **Migration 0010: agent_runs metrics.** Add `metrics jsonb not null default '{}'`. The four count columns: make nullable (drop NOT NULL/default) and mark deprecated in a comment; Scout's existing rows keep their values (no backfill needed — they are real for Scout). New Scout rows write metrics; the four columns are written-but-deprecated during a transition OR cut straight to metrics (default: cut straight to metrics, columns nullable for history). | migration applied agents_dev then agents_prod; Scout run writes metrics; old rows intact |
| 3d | **Move logging + fetcher base.** `shared/logging_setup.py` (agent required arg); `shared/fetchers/base.py`. Repoint Scout imports. (3d-fetcher is the soft move — may defer per the flag above.) | Scout uses shared logging with `agent="scout"`; fetcher base importable from `shared/`; tests green |
| 3e | **Write the contract doc** `docs/agent-contract.md`: the 5 requirements a module must satisfy to be a kl-agent (run lifecycle via shared/runs; config surface; structured logging; status→exit-code; writes to the shared backend, reads what it needs). Plus the ONE hard invariant: `shared/` never imports from `agents/`. | doc exists, lists the 5 requirements + the invariant; references the shared modules by path |
| 3f | **Enforcement check.** A test (or CI grep) asserting the import-direction invariant (`shared/ → agents/` = zero matches) and that an agent module exposes the contract entry points. | invariant is a failing-if-violated check, not just prose |

## Key decisions & tradeoffs

- **Why extract code at all (not doc-only):** `shared/db/client.py:16` imports `agents.scout.config` — the shared foundation depends on the agent built on it. A doc cannot fix a Python import. Validation would inherit the tangle. (Q1.)
- **Why not a base class:** three agents do not justify an inheritance framework; CONTEXT.md locked "NOT a heavy framework." Convention + a thin enforced invariant is lighter and sufficient.
- **Why JSONB metrics over fixed columns:** non-listener agents make the listener counts meaningless; JSONB lets each agent record true metrics without schema churn or fake zeros. (Decision A.)
- **Why generalize the fetcher/logging moves:** they were ALREADY agent-agnostic in design, only Scout-located. Moving them is free generality (Decision B), not new surface. The fetcher move is the softest (Validation doesn't fetch) and is explicitly deferrable.
- **No ADR proposed:** these are reversible, unsurprising extractions of an existing pattern; they fail the "hard to reverse + surprising + genuine trade-off" ADR test. The contract doc + this plan are the record.

## Risks / open questions

- **R1 — Scout regression during extraction.** Scout is live (YouTube path). Every slice keeps Scout running and green; 3a-3b are behavior-preserving moves (same logic, new location). Mitigation: tests green at every checkpoint; mypy clean; a real Scout run before declaring done.
- **R2 — migration 0010 on a live table.** `agent_runs` has real Scout history. Plan: additive `metrics` column + relax (not drop) the count columns. No data loss; old rows stay valid. The deprecated columns can be physically dropped in a LATER migration once nothing reads them (out of this bucket).
- **R3 — the fetcher-base move may exceed "unblock Validation."** Flagged in-plan; deferrable to first 3rd source if Codex or Greg judges it premature. Does not block any other slice.
- **R4 — `_finish_safely` / exit-code semantics are currently Scout's partial-failure model (success/partial/failed).** Validation has no "sources" to partially fail. Confirm the same 3-state model fits a non-listener (likely: success / failed, with partial unused) — the contract should state partial is OPTIONAL, agents that can't partially fail just never emit it.

## Out of scope

- Any change to Scout's keeper-gate, classifier, or `classified_posts` (Bucket 1's territory; `storage/posts.py` stays Scout-specific).
- Any change to Validation's logic (Bucket 2); Bucket 3 only provides the spine Validation will build on.
- Echo (sequenced last).
- A base class, plugin system, or agent registry.
- Physically dropping the deprecated count columns (later migration).
- Any code for agent #4 / prospecting / new fetcher sources (Decision B: zero speculative code).
