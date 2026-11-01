# MiniMax Design adapter evidence

**Current level: E0 (DECLARED). This directory intentionally contains no runtime evidence.**

Nothing has been launched, nothing has been exported, and no artifact exists.
The directory is present so that a future, authorised POC has an obvious place to
land — not as a claim that one happened.

## What a real record must contain

A future file here (for example `E2-<date>-controlled-fixture.md` or
`E3-<date>-editable-delivery.md`) is only valid when it carries:

- the exact host build string and the exact DESIGN-LAB `subject_sha`;
- the Windows version and the path **alias** used (never a raw user path in a
  tracked file);
- an ordered, replayable description of every action;
- the exported artifact path, `sha256:<64 hex>` and byte size;
- the reopen readback digest and what was compared;
- any error text seen, plus how it was resolved;
- the rollback actually performed;
- the four axes (`implementation`, `unit`, `host_live`, `delivery`) recorded
  separately, with anything not exercised left as `NOT_VERIFIED` / `PARTIAL`.

## What must never appear here

- Screenshots presented as evidence of a working capability.
- "The UI looked correct" as an acceptance signal.
- A reused digest, a historical artifact, or another tool's result filed under
  this adapter's name.
- Any session transcript, credential, client asset or personal library path.
