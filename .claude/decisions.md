---
tier: P1
scope: project
project: 03-kl-agents
loads_when: structural decisions or graduation observations
sensitivity: business-private
---

# 03 KL Agents Decisions

## Structural decisions

### 2026-05-09 — Operator OS install: Pattern α (clean router-only init)

**Decision:** No prior `CLAUDE.md` or `.claude/` existed. Fresh router-only init applied.

**Reason:** Project had no existing directives to preserve. Pattern γ from the build prompt was over-cautious — there was nothing to parallel-version.

**Documented:** `OPERATOR-OS-DISCOVERY-REPORT.md` §7.1 finding 9, refinement 10.3.

### 2026-05-09 — Scout classification logic stays code-side

**Decision:** Operator OS does not write rules that affect Scout's classification logic. The logic lives in Python (`../agents/scout/classifier/`) and shared prompts (`../shared/prompts/`). Operator OS provides domain context (ICA profiles via K&L Vault wiki); the agent decides classification.

**Reason:** Classification logic is high-risk and code-tested. Adding a parallel rules-based override layer would create two competing decision systems.

### 2026-06-03 — OpenCLI evaluated: rejected for Scout, candidate for Echo extraction, redundant elsewhere

**Context:** Evaluated [jackwener/OpenCLI](https://github.com/jackwener/OpenCLI) (v1.8.2, 23.4k stars, Apache-2.0) as a possible answer to the pending Reddit API approval. OpenCLI drives a logged-in Chrome session (extension + daemon + CDP) and ships 100+ site adapters (incl. Reddit, LinkedIn, Twitter) that extract via **network inspection + pattern detection rather than DOM selectors**.

**Decision 1 — NOT for Scout.** Scout's Reddit fetcher stays on the official API (PRAW). OpenCLI would scrape Reddit through the logged-in `u/SparkyMcCrinkle` session, which violates Reddit's API terms / User Agreement and risks the account AND the pending v2 application. Scout is also not blocked: it runs end-to-end on YouTube today; Reddit is one source of several, not a critical path. Trading a clean, recoverable wait for a ToS-risky scraper is a net loss.

**Decision 2 — CANDIDATE for Echo's extraction layer.** Echo (Agent 2, porting from `kl-engagement-feed`) scrapes LI Personal / LI Page / FB Page via hand-rolled DOM selectors. The engagement-feed reference doc lists "selectors drifted" / "selectors returning empty arrays" as *recurring named failure modes*. OpenCLI's network/pattern-based adapters are structurally more resilient to LinkedIn/Facebook UI redesigns, and it ships maintained LI + FB adapters — moving that maintenance burden off us onto an active project. This is the one place OpenCLI beats all current tools. Gated on a spike (`docs/spikes/2026-06-03-opencli-echo-adapter-spike.md`) that verifies its adapters return Echo's required fields (commenter handle, post URN, timestamp, comment text). Do NOT adopt before the spike passes.

**Decision 3 — REDUNDANT elsewhere.** For public-web research, `firecrawl` is purpose-built and cloud-hosted (no local browser). For in-agent ephemeral automation, the Playwright MCP is cleaner (native tool calls, no subprocess). For one-off interactive automation, `playwright-cli` is lighter. OpenCLI adds a fourth browser-automation tool to a crowded layer; it earns its place only at the Echo seam or not at all.

**Reason:** Comparison grounded in all four tools' specs (confidence: high). The unverified assumption — "OpenCLI's LI adapter returns exactly Echo's required fields" (confidence: medium) — is what the spike exists to settle.

## Maturity dismissals

(None.)

## Graduations

(None.)
