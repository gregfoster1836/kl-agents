# Operator OS Router — 03 KL Agents

This router is a fresh router-only init (Pattern α). The project did not have a prior `CLAUDE.md` or `.claude/` directory before Operator OS install.

## Project declaration

- **Domain:** kl
- **Role in K&L family:** code-project (agent OS, contains Scout)
- **Sensitivity:** business-private

## Project overview

Per `../README.md`: "Knife & Ledger agentic OS. Each agent does one job and writes to a shared Supabase backend."

**Active agent:** Scout — reads new posts in restaurant subs on Reddit, classifies them by ICA stage, writes keepers to a review queue. (v0.1 in development.)

## Read order

1. **Always:** `../README.md` (project overview, setup, running Scout)
2. **For agent code:** `../agents/scout/{main,config,models,logging_setup}.py`, `../agents/scout/fetchers/`, `../agents/scout/classifier/`, `../agents/scout/storage/`
3. **For shared infrastructure:** `../shared/db/`, `../shared/prompts/`
4. **For domain rules:** `~/.claude/operator-os/domains/kl/voice.md`, `domains/kl/standards.md`
5. **For ICA classification context:** K&L Vault `wiki/ica-profiles.md` (Marcus S1, Diane S2, Ray S3 — Scout uses these)

## What Operator OS adds (light)

- This `.claude/CLAUDE.md` router
- `.claude/corrections.md` and `.claude/decisions.md`

## What Operator OS does NOT do here

- Modify Scout's classification logic, prompts, or fetchers
- Modify Supabase migrations or db client
- Modify `pyproject.toml`, `Makefile`, `.env*`, or test suites
- Insert itself into the agent's exit-code or partial-failure handling

## Operating notes

The agent's classification logic is the highest-risk piece in this project. If you find yourself about to modify anything in `../agents/scout/classifier/` or `../shared/prompts/`, confirm with operator first.
