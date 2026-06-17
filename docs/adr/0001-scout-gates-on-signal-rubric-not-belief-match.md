# ADR 0001 — Scout gates on the signal rubric, not belief-match

**Status:** Accepted (2026-06-15, top-down grill with Greg)
**Supersedes:** the implicit "belief-match + confidence" keeper-gate in the live Scout classifier.

## Context

Scout's live keeper-gate keeps a harvested post only if it matches one of the 10 K&L false beliefs with sufficient confidence. During the top-down grill, Greg defined a *valuable signal* as **authentic operator pain + actionable for K&L + fresh/trending**, and explicitly declined to require belief-fit — a great signal that does NOT map to an existing belief is still valuable, possibly more so (it's a gap in the belief map).

These conflict: the live gate silently drops authentic/actionable/fresh signals that happen not to fit the 10 beliefs.

## Decision

Scout keeps a post when it clears the **signal rubric** (authentic + actionable + fresh). Belief slug, ICA stage, and symptom tag become **descriptive metadata** (nullable), not the filter. Belief-match is no longer the gate.

## Consequences

- **Positive:** Scout captures novel/off-map signals — the ones most likely to reveal gaps in K&L's map. Scout's behavior now matches Greg's actual definition of a good signal.
- **Cost / risk:** This is a *re-aim* of the classifier (the project's highest-risk file per `.claude/CLAUDE.md`), not an additive change. The classifier must gain a new capability it lacks today: judging authentic/actionable/fresh. Requires operator-confirmed, verifier-gated implementation.
- **Reorders the roadmap:** the provisional symptom-extension phase becomes secondary (it adds a descriptive field to a gate being replaced). The keeper-gate re-aim leads.
- **Demands ground truth:** "authentic/actionable/fresh" is a judgment the outcome-verifier must measure (human-graded sample + Codex audit) — see CONTEXT.md § Signal quality.

## Alternatives considered

- **Hybrid (keep on belief OR rubric):** lower-risk, additive, but keeps belief-match as a first-class gate that Greg said shouldn't be one. Rejected for muddying the model.
- **No change (belief-first):** simplest, but contradicts the stated rubric and drops the novel signals Greg values most. Rejected.

## Open follow-ons

- ~~How Scout operationalizes authentic/actionable/fresh~~ — **RESOLVED 2026-06-15** (see CONTEXT.md § Scout's keeper-gate operationalized): recent = timestamp (30d first / 24h daily); authentic = model-judged lean-inclusive (ambiguous→keep+flag); actionable = model-judged broad (restaurant-ops relevant, NOT playbook-fit). Plus a `theme` axis tagged for later trending.
- Belief/ICA/symptom tags become **best-effort description** (nullable), not required — confirmed, they're no longer the gate.
- **Still open (spec-level):** how `theme` vocab stays groupable-for-trending while admitting NEW outside pressures (controlled-but-extensible tension).
