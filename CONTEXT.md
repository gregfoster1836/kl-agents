# CONTEXT — kl-agents glossary

Ubiquitous language for the kl-agents platform. Glossary only — no implementation details, no spec. Terms are resolved during grill sessions and used verbatim in PLAN.md / SPEC.md.

---

## Platform

**kl-agents** — An agentic OS (platform) for Knife & Ledger. The *spine* is reusable agent infrastructure (shared Supabase backend, shared DB client, fetcher/agent conventions); individual agents are the unit of work. Scout, Echo, and Validation are the first three of many planned agents. The platform's job: let K&L act on real market knowledge instead of guessing, across content, lead magnets, and prospecting.

**Agent** — A single-job worker on the platform. Reads from one or more sources, does one job, writes to the shared backend. (The precise "what makes something a kl-agent" contract is not yet resolved — open.)

**Signal** — A relevant piece of market information worth acting on (a belief, a symptom, a trend, a piece of language). What the platform exists to surface. (Precise definition open — to be sharpened.)

**Theme** — The market-topic axis tagged on every signal: what the market is reacting to (e.g. labor, hiring, food-cost, rent, regulation). DISTINCT from belief/symptom: theme = the external/market topic; belief/symptom = how K&L frames the operator's thinking. Theme is the **groupable axis for trending** — it must exist on every stored signal from day one, or trends can't be reconstructed retroactively from free text. Vocab is controlled-but-extensible (open tension: stay groupable while admitting NEW outside pressures — spec-level open question).

**Recency** — Per-post freshness gate. First Scout run: 30-day look-back (cold-start backfill). Daily runs: "fresh" = new posts in the last ~24h (since last run). Resolved, buildable now.

**Trending** — Volume-over-time: the same theme recurring across many posts, visible only once Scout has judged enough posts to have empirical history. Signals "this is what operators face NOW" and often reflects a larger outside pressure (food prices spiking, labor regulation). NOT computed per-post; it's a corpus-level capability = the **market-intelligence** outcome. Decision (2026-06-15): **build the structure now** (store the theme axis + timestamp + source on every signal) **compute trends later** (separate capability, once empirical data accumulates).

---

## The two listeners (distinct signal sources — do not conflate)

**Scout** — The *market* listener. Goes OUT to the open market (Reddit restaurant-operator subs + YouTube) and harvests posts from operators K&L does not yet reach. Classifies each against the 10 false beliefs + 3 ICA stages + confidence; writes keepers to a review queue. Answers: "what is the market struggling with, in their words?" Status: live (YouTube path live; Reddit blocked on API access).

**Echo** — The *owned-audience* listener. Listens IN on K&L's OWN social platforms (LinkedIn, Facebook) — the comments and engagement on K&L's own published content. Answers: "how is the audience we already reach responding to us?" A different signal source than Scout, not a processing layer over Scout. Status: schema scaffolded (migrations 0003-0006: kl_posts, kl_comments, kl_commenter_profiles); not yet a running agent.

> **Resolved 2026-06-15:** "Echo sorts it" (loose phrasing in grill) does NOT mean Echo processes Scout's output. Echo is an independent listener on owned social. Sorting/prioritizing signals is Validation's territory (or a future processing agent), not Echo's.

---

## The judge

**Validation** — Decides what surfaced signal is worth acting on, and tests demand before K&L builds. Reads enriched signals, runs a demand test (e.g. fill-in-the-blank offer), and gates a build decision (validated / crickets / pivot). Answers: "of everything the listeners surfaced, what's worth addressing — and is the demand real?" Status: provisional spec only, not built.

---

## Outcomes the platform drives (Greg's words, 2026-06-15)

The listeners + judge feed four business outcomes:
1. **Content research** — write meaningful content from market knowledge, not guesses.
2. **Lead-magnet targeting** — produce magnets operators actually want.
3. **Market intelligence** — standing read on trends, language, and beliefs in the operator market.
4. **Prospecting** — surface signals K&L can pursue as outbound opportunities. (Vision only — no agent or spec yet.)

---

## Signal quality (the outcome-verifier's rubric — Greg, 2026-06-15)

A signal is **valuable** when it is all three:
1. **Authentic operator pain** — a real operator describing a real struggle in their own words. NOT a vendor, student, journalist, or hypothetical. The verbatim language is the gold.
2. **Actionable for K&L** — K&L can write a piece, build a magnet, or reach out off it. Unactionable = noise even if authentic.
3. **Fresh / trending** — reflects what operators struggle with NOW; recency and momentum count.

> **NOT a quality requirement: "fits an existing K&L belief."** Greg deliberately did not require on-belief mapping. A great signal that does NOT fit the current 10 beliefs is still valuable — possibly more so (it's a gap in the map). Belief/ICA tags are *description*, not the *quality filter*. See OPEN QUESTIONS — this contradicts Scout's current keeper-gate.

**Scout's keeper-gate, operationalized (resolved 2026-06-15):** A harvested post becomes a kept signal when ALL three hold —
1. **Recent** — within look-back. Deterministic, from post timestamp. (30d first run / ~24h daily.)
2. **Authentic operator pain** — model judges real-operator-source AND real-struggle (not vendor/student/journalist/hypothetical/promo), emitting reasoning + confidence. **Lean inclusive:** ambiguous → KEEP + flag low-confidence (recall over precision; missing a real signal costs more than skimming a borderline one).
3. **Actionable = restaurant-operations relevant** — about running a restaurant (ops, money, people, systems) and an operator could plausibly want help. **Broad by design:** K&L's *domain* is the filter, NOT K&L's current playbook/beliefs (broad keeps novel signals; narrow would re-impose the belief-fit gate ADR 0001 removed). Model-judged.

Every kept signal is then TAGGED (description, not gate; null allowed): **theme** (market-topic → trending), **belief slug / ICA stage / symptom tag** (K&L framing → content/research), plus confidence + reasoning. The model judgments (2,3) are new capability vs. today's belief-only classify call; calibration is what the human-grade + Codex-audit loop tunes.

**Measuring signal quality (layered, sequenced):**
- **Layer 1 — human-graded sample (now):** Greg/Claude grade a real sample against the rubric, precision/recall style ("of 20 surfaced, how many truly valuable? what valuable ones missed?"). Ground truth = Greg's judgment.
- **Layer 2 — Codex audit (cross-check):** Codex independently grades the same sample against the rubric; compare to catch classifier blind spots.
- **Layer 3 — downstream-outcome tracking (LATER milestone):** did a signal's content actually perform? Requires a closed loop that does NOT exist today (see below). Not near-term focus.

**The outcome loop is OPEN, not closed (Greg, 2026-06-15):** Today: signal → review queue → Greg's head / the vault. No data path records which signal drove which content or how it performed. Closing it would span repos (kl-agents ↔ vault ↔ publish/analytics). This is a future capability to BUILD, not a measurement to turn on. **Near-term verification focus: signal quality AT THE SOURCE (layers 1-2). Get the input right before instrumenting the output.**

---

## OPEN QUESTIONS (unresolved — to grill before spec locks)

1. **Scout's keeper-gate vs. the quality rubric (BIG).** Scout currently keeps posts by belief-match + confidence. But "on-belief" is NOT a quality requirement, and novel/off-map signals may be the most valuable. → Scout's core filter may discard exactly what Greg wants. Resolve: should the keeper-gate change from belief-match to something rubric-aligned (authentic + actionable + fresh)?
2. **"Agent" contract.** What formally makes something a kl-agent (so the platform spine is real, not just convention)? Unresolved.
3. **"Signal" precise definition.** Currently loose. Sharpen before it anchors schema.
4. **Prospecting agent.** Vision only. Out of near-term scope but shapes platform design — how much to design-for-later vs. ignore.

---

## K&L domain canon (lives in the sibling vault, consumed as source of truth)

**False beliefs** — The 10 wrong diagnoses operators hold (e.g. "labor is fixed"). Canon: `00 K&L Vault/.../Part VII - False Belief Map.md`. Mirrored in Scout as `BELIEF_SLUGS`.

**ICA stages** — Three operator awareness stages: Marcus (symptom chaser), Diane (pattern recognizer), Ray (structure seeker). Canon: `00 K&L Vault/.../Part II - Ideal Customer Architecture.md`.

**Symptom** — The felt operational pain ("working 70 hours, can't make payroll"), distinct from a belief (the wrong diagnosis). Closed 10-tag vocab. Canon: `00 K&L Vault/.../Symptom Map.md`.

---
*Started 2026-06-15 during top-down grill session.*
