---
name: skill-slimming
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/skill-slimming/SKILL.md
---

---
name: skill-slimming
description: "Slim a SKILL.md below budget without losing content."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [skills, authoring, slimming, references, provenance, budget]
    related_skills: [hermes-agent-skill-authoring, skill-library-curation]
---

# Slimming Skills Below Budget (Move, Don't Delete)

## When to Use

When a skill's `SKILL.md` has grown past its size budget — e.g. a repo/governance
baseline of ~10KB per SKILL.md body (or the `hermes-agent-skill-authoring`
guideline of 8–14k chars, split to `references/` past 20k) — and must be reduced
without losing any of the accumulated knowledge. Never cut content; the goal is
to move bulky detail behind pointers so the always-loaded body stays small.

## Step 0 — Measure the split first

The budget applies to the **SKILL.md body** (what gets injected into context),
NOT the whole skill directory. Before slimming, measure both separately:

- `SKILL.md` bytes (the always-loaded payload) — this is what must go under budget.
- auxiliary bytes (everything else in the skill dir: `references/`, `scripts/`,
  `templates/`) — these load on demand and may legitimately be large.

A skill with a 5KB SKILL.md and a 50KB `references/` file is *healthy*, not
bloated. Only the SKILL.md body counts against the budget. Re-measure after the
split to confirm the body dropped below threshold while the directory total may
actually grow slightly (index + section anchors add a little).

Run `scripts/measure_skill_sizes.py <skills_root> [--budget 10240]` to get a
read-only JSON breakdown of every skill's body vs auxiliary bytes plus the
over-budget list — do not hand-count or eyeball sizes.

## Step 1 — "Move, don't delete" pattern

Split a fat SKILL.md into:

1. **SKILL.md (kept lean)** — frontmatter + title + `## When to Use` + a short
   `## Global disciplines` list (the 2–4 rules that apply to *every* case) + a
   **symptom→cause→ref index table** + a `## Verification Checklist`. Each index
   row is one line: the symptom, a one-line root cause, and a `§N` pointer.
2. **`references/<topic>.md` (bulk detail)** — every pitfall/case/recipe moved
   verbatim, each under a `## §N <original title>` heading so the index anchors
   resolve. Preserve WRONG/RIGHT code, dates, PR numbers, and evidence — nothing
   is paraphrased away. Sub-entries keep `### §N.M` numbering.

Verification of zero-loss: count the original `## ` headings and confirm the
reference file carries the same count under `§N` (plus sub-entries). The index
table must have one row per section, pointing at the matching `§N`.

## Step 2 — Recomputed provenance hashes use CRLF-normalized bytes

Skills tracked by a provenance manifest carry a `source_sha256` that a gate
re-verifies. **The hash is almost never a raw-bytes sha256.** Gate checkers
(e.g. WORK-LAB `check_skill_provenance.py`) canonicalize line endings first so
Windows CRLF and Linux LF agree:

```python
data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
sha = hashlib.sha256(data).hexdigest()
```

If you compute `hashlib.sha256(open(path,'rb').read()).hexdigest()` on raw bytes,
a CRLF working tree produces a *different* digest than the gate expects and the
gate fails with `source SHA drift`. Always recompute using the gate's exact
canonicalization (read the checker's `sha256()` function — do not assume). Also
bump the entry's `version` field when the body meaningfully changes.

## Step 3 — Verify

- Re-run the provenance checker and confirm `SKILL_PROVENANCE_PASS` (or the
  local equivalent gate) — this proves the manifest hash matches the new body.
- Re-measure the SKILL.md body and confirm it is now under budget.
- Confirm `references/` files do NOT need separate manifest registration —
  checkers typically hash only the `source` SKILL.md; the `discover` pass must
  still cover every skill, but auxiliary files ride along under the skill entry.
- Re-run any content-integrity count (heading count vs `§N` count).
- Re-run the repo's contract/governance tests that assert on the skill body
  (e.g. `python tests/test_workflow_governance.py`), not just the provenance
  gate — slimming can silently rewrite an `assertIn`-locked safety marker.

## Pitfalls

1. **Hashing raw bytes instead of CRLF-normalized bytes** — the #1 failure.
   Symptom: gate passes locally (LF tree) but reports `source SHA drift` on a
   CRLF checkout, or vice versa. Always mirror the checker's `sha256()`.
2. **Deleting instead of moving** — a slimming that drops detail is data loss.
   The reference file must grow by roughly the amount the SKILL.md shrinks.
3. **Splitting the wrong way** — keep trigger conditions, main flow, and fatal
   pitfalls in the SKILL.md (always visible); only bulky examples, long lists,
   and dated case studies go to `references/`. Moving a must-always-see rule
   behind a pointer degrades the agent's behavior.
4. **Forgetting the version bump** — provenance entries carry a `version`; a
   meaningful body change without a bump hides the change from audit.
5. **Treating the whole directory size as the budget** — auxiliary files are
   on-demand and don't count; only the SKILL.md body is the always-paid cost.
6. **Rewriting contract-locked safety markers** — a repo's governance/contract
   tests may pin exact strings in a SKILL.md body with `assertIn(marker, body)`.
   Example (WORK-LAB `test_workflow_governance.py`) locks
   "PowerShell selection policy" and "Do not assume `python` and `python3`
   resolve to the same interpreter." in the windows skill to enforce the
   provider/credential boundary and explicit interpreter selection. Slimming
   that rephrases or compresses those markers fails CI even though the *meaning*
   survived. Before slimming, grep the test suite for `assertIn(` assertions
   against the skill body and keep those exact strings verbatim. After the
   split, run the contract tests directly — a green provenance gate is NOT
   proof the contract markers survived.
