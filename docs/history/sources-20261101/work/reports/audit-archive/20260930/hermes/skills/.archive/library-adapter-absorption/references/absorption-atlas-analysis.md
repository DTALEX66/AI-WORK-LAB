# Absorption Atlas Analysis Workflow

Use when given a master atlas of open-source candidates (369+, 57 curated, etc.) and asked to
produce real absorption decisions — NOT just registration or indexing.

## Trigger

- User provides a master atlas / absorption audit document
- User says "分析这些开源清单，写入吸收文档，不要再只登记和索引了"
- An existing absorption ledger or matrix needs upgrading from "catalogue" to "decisions"

## Pattern

### 1. Read the master atlas thoroughly
Extract: product boundary, disposition labels, licence corrections, upstream archive
status, per-component decisions, recommended minimum stack.

### 2. Produce three documents (not one catalogue)

**SUPPLY_CHAIN_LEDGER.json (v2+)**: Structured machine-readable decisions.
Each component entry carries:
- `code_license` AND `model_license` (NEVER merge them)
- `disposition` in {CURRENT, ADOPT, EVALUATE, SIDECAR, REFERENCE, DEFER, REVIEW-BLOCK, REJECT-CORE}
- `qualification` tier: [source, installed, release]
- `decision` rationale (why this disposition)
- `upstream_note` for corrections (e.g. "Marker code Apache-2.0, NOT GPL-3.0")

Disposition labels and their semantics:
- CURRENT: already integrated — source/binary evidence exists
- ADOPT: recommended primary choice — requires exact-revision RDR before integration
- EVALUATE: bake-off candidate — compare against peers with fixed fixtures
- SIDECAR: isolated, removable, not a default core dependency
- REFERENCE: UX/contract/algorithm reference only, not a dependency
- DEFER: valuable for later horizons (H6+), not for H0-H5 core
- REVIEW-BLOCK: licence/model/security gate not passed — default disabled
- REJECT-CORE: incompatible with product scope — historical record only

**ABSORPTION_EXECUTION_MATRIX (v2+)**: Correct historical drift.
- Replace outdated numeric claims ("implemented=8") with current facts
- Update stage sequences (old R0->A0->H->I... -> new H0->H1->H2->H3...)
- List documentation drift explicitly (which files still claim stale state)
- Include upstream licence correction table (old record -> new verified fact)

**THIRD_PARTY_NOTICES**: Append an "upstream licence corrections" section.
For each component where the old record was wrong, list: old record -> new verified
fact. This is NOT a full licence audit — it is a targeted correction.

### 3. Enforce product boundary
The atlas defines what the product IS and IS NOT. Components that fall outside the
boundary (e.g. Agent/coding/memory/workflow/security-lab for a learning workspace)
must be labelled REJECT-CORE or DEFER, not just left as "pending".

### 4. Do not inflate numbers
Historical sources (369 / 101 / 103 / 57 / 8) may overlap heavily. Never add them
together. The ledger v2 should list only components that received a real decision.

### 5. Agency-level rules enforced by the atlas
- Default path targets zero LLM token cost
- Recognition quality and fact verification remain decoupled
- CER/WER only computed when truth/prediction pairs exist
- Engine confidence never equals accuracy
- Multi-engine agreement never equals factual correctness
- LLM is not assumed more accurate just because it is more expensive
- A full file is never sequentially fed through "local -> LLM assist -> full LLM"
- Unverifiable content (private notes, subjective opinion, OCR noise) is never sent to the web

## Pitfalls

- **Registering without deciding**: A ledger that just lists names and licences with
  no disposition is a catalogue, not absorption. User WILL call this out.
- **Stale numbers**: Old "implemented=8" or "101 items" must be explicitly retired when
  replaced by ledger v2. Do not let both coexist as truth.
- **Licence over-summarization**: "MIT" for LiteLLM hides that enterprise/ is
  separately licensed. Always check directory-level licences (enterprise/, ee/, xl-* packages).
- **Missing archive/rename**: Kùzu archived 2025-10-10, but old documents may still list
  it as an active candidate. Must be marked upstream-archived.
- **Code vs model/weight licence must stay separate**: Marker code is Apache-2.0 (NOT GPL-3.0
  as old records claimed) but weights are modified OpenRAIL-M. FunASR code is MIT but model
  has custom modifiable protocol. Never write a single licence field for a component that
  has both code and model/weight assets.
- **Document-only PR CI lint loop**: Repository convention checks (check_repository_conventions.py)
  will fail a doc PR for crlf (JSON written with CRLF), missing-final-newline, and
  trailing-whitespace. Fix all three in one pass before pushing — use Python to
  normalize line endings (replace CRLF with LF + append trailing LF) and rstrip() each
  line of markdown files. Then git commit --amend + --force-with-lease (branch is new, safe).
  Do NOT open a PR until the conventions check passes locally.
- **Force-push on a fresh branch is safe**: When the branch was just created and has
  no other writers, --force-with-lease after an amend is the correct workflow.
  Never force-push to main or a shared branch.
- **Patch failure on router files**: When adding a Pydantic model between two existing
  BaseModel classes in a FastAPI router, the old_string must match EXACT characters
  including trailing whitespace. Re-read the file with read_file before every patch
  attempt — do not retry with guessed whitespace variations. After 3 failures on the
  same region, switch to write_file for the whole file.

## Concrete session example (2026-08-11)

Input: ArcheAxis_Workspace_Project_History_and_OSS_Absorption_Master_Atlas_v1.md
(369+ candidates, 57 curated, 15 categories, 12 currently integrated, 10 licence corrections).

Output:
- SUPPLY_CHAIN_LEDGER.json v2 -> 46 components with disposition decisions
- ABSORPTION_EXECUTION_MATRIX.md v2 -> corrected stage sequence, retired 8-count drift
- THIRD_PARTY_NOTICES.md -> appended 10-item licence correction table

Disposition summary: 12 CURRENT / 13 ADOPT / 9 EVALUATE / 2 SIDECAR / 9 REVIEW-BLOCK / 1 REJECT-CORE.
Key corrections: Marker code GPL-3.0 -> Apache-2.0, H5P MIT -> GPL-3.0, Phoenix OSS -> ELv2,
tldraw OSS -> commercial-required, Kuzu active -> archived, LiteLLM/Langfuse MIT -> core-MIT+enterprise-separate,
MinerU plain-Apache-2.0 -> Apache-2.0+additional-conditions.
