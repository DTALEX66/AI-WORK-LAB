---
name: workflow-assistance-verification-hardening
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: codex
archived_at: 2026-08-21
source_path: D:/All projects/WORK-LAB/10-workflow/workflow-assistance/codex-assets/skills/workflow-assistance-verification-hardening/SKILL.md
---

---
name: workflow-assistance-verification-hardening
description: "Use when adding hallucination verification, upgrade safety, or approval-adaptation to an agent runtime."
---

# Verification & runtime hardening

Hardening patterns for agent runtimes (Hermes hooks / workflow gates), inspired
by community plugin approaches but implemented client-neutral and secret-free.
These are METHOD skills: they describe what to build and how to verify it, not
a copy of any specific plugin's code. License note: external plugin code (e.g.
CC BY-NC 4.0 licensed) must not be copied verbatim; re-implement the pattern.

## 1. Hallucination verification (transform_llm_output hook)

Add a free-first, paid-only-when-needed verification layer for high-risk
responses:

1. **Hook point**: `transform_llm_output` (fires after a reply is generated,
   before it is shown). At this point the turn is over — do NOT retry or
   block; only annotate/warn. A verification failure must never block the
   reply (fail-open by design; it is a review layer, not a safety gate).
2. **Tier gate**: only verify high-risk tiers (deep/critical). Low tiers skip
   the paid call entirely.
3. **Free rule pre-check first** (no model call):
   - empty reply → "回复为空"
   - short reply (< ~200 chars) containing refusal patterns
     (我不能/无法帮助/无法提供/i cannot/i'm unable to) → "疑似拒答"
   - short reply containing uncertainty patterns
     (不确定/不知道/无法判断/i don't know/i'm not sure) → "疑似不确定"
   These catch the obvious failures for free. A clean pre-check does NOT mean
   no hallucination — the paid semantic check still runs for high tiers.
4. **Paid cross-check (high tiers only)**: one independent auxiliary-model call
   with a strict verifier prompt: "judge whether key claims are fabricated,
   unsupported, or overconfident; reply ISSUE: <one line> or OK". The verifier
   uses a DIFFERENT model/provider than the main one (independent channel).
5. **Degradation**: if the verify channel is unavailable (no client, network
   error), return None (pass through) — never block the user on a review
   layer failure.
6. **Verification of the verifier**: assert (a) low tier → no paid call,
   (b) pre-check catches refusal/uncertainty on crafted samples, (c) verify
   channel down → None returned, (d) response shown even when verify fails.

## 2. Upgrade watch (auto-backup on agent upgrade)

When the agent runtime (Hermes/Codex) upgrades, configuration drift is the #1
silent breakage source. Add an upgrade-safety pattern:

1. **Detect version change**: record the runtime version at session start
   (e.g. `hermes --version`); persist it in a small state file.
2. **On change**: immediately snapshot the user config that the workflow
   manages (config.yaml / config.toml) to a timestamped backup, before any
   new-version code touches it.
3. **Watch window**: for ~30 minutes after the upgrade, archive any anomaly
   (hook errors, config parse failures, skill load failures) to an upgrade
   log with the before/after version.
4. **Rollback path**: the backup is the rollback; document the exact restore
   command in the log.
5. **Verification**: simulate a version bump in a temp HOME and assert the
   backup is created before anything else runs, and that anomalies inside the
   window are archived.

## 3. Adaptive approval (optional)

Reduce confirmation fatigue for SAFE repeated operations without weakening
permanent-high-risk gates:

1. Track approval history per operation class (success = granted, failure =
   denied).
2. After 3 consecutive grants of the same class, suppress the repeat
   confirmation for that class (not for permanent-high-risk categories).
3. A single denial resets that class to confirmed-always.
4. Permanent high-risk classes (E:\, credentials, global config, force-push,
   destructive ops) are NEVER subject to adaptation.
5. **Verification**: assert 3 grants → suppressed; 1 denial → reset; permanent
   classes never suppressed.

## Verification checklist

- The verification layer is fail-open (never blocks on its own failure).
- Paid cross-check uses an independent channel from the main model.
- Upgrade backup is created BEFORE new-version code runs.
- Adaptive approval never touches permanent-high-risk classes.
- No secrets, credentials, prompt/response bodies, or private memory are
  read, copied, or logged by any hardening hook.
