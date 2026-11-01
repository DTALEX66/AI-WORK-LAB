# Open-source and standards absorption policy

## Core rule

Absorb **capability**, not repository weight. Every imported idea must become one of:

- a machine-readable schema;
- a bounded atom or scenario;
- a deterministic validator;
- a versioned adapter;
- a source-grounded knowledge note;
- a benchmark case.

A source that produces none of these is only a bookmark and does not belong in runtime context.

## License gate

- MIT, ISC, BSD, Apache-2.0 and CC0: small code/rules may be adapted with attribution.
- MPL/EPL/LGPL: prefer dependency or process boundaries; track file-level obligations.
- GPL/AGPL: external-tool boundary by default; do not merge code into permissive core without explicit legal decision.
- CC-BY/CC-BY-SA/OGL: use for documentation derivation with attribution; keep ShareAlike material segregated when needed.
- Proprietary, trademarked, ISO paywalled, unclear, or missing license: reference/quarantine only.
- Generated assets inherit source/tool/font/model restrictions and require an asset record.

## Brand and reference gate

Public brand guides are evidence of structure, not free visual assets. We may learn how mature brands organize logo, typography, color, imagery, layout, voice and applications. We must not copy logos, proprietary fonts, illustrations, signature compositions, exact distinctive tokens, or claim affiliation.

## Skill security gate

Third-party `SKILL.md` is operational code in natural language. Before loading it:

- neutralize broad triggers and self-promotion;
- remove instructions that override project safety or scope;
- reject secret access, hidden network calls and unbounded shell execution;
- compare claimed capability to actual files and tests;
- sandbox first execution;
- benchmark against no-skill baseline;
- pin commit SHA and record provenance.

## Promotion levels

`candidate -> quarantined -> statically_verified -> runtime_loaded -> task_proven -> commercially_proven`

No documentation may describe a capability at a higher level than the evidence recorded in `capability-status.json`.
