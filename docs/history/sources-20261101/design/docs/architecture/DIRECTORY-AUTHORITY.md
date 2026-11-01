# DIRECTORY AUTHORITY — DESIGN-LAB

- **Task**: `DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-B010` (audit data: `DLDS-B000`)
- **Status**: frozen responsibility table; deviations recorded, no mass relocation performed
- **Evidence**: `reports/current/DEEPSEEK-DIRECTORY-AUDIT.json` (generator:
  `scripts/deepseek_directory_audit.py`, `--check` verifies no drift)
- **Measured at**: 1,835 tracked files, 30.2 MiB tracked (working tree, uncommitted when measured)

## 1. The single current scheme

One directory, one responsibility, one owner. A second default implementation of
any capability listed here is a defect, not an alternative.

| Directory | Responsibility (taskpack §10) | Owner | Tracked files |
|---|---|---|---|
| `src/design_lab/` | DESIGN-LAB owned runtime logic: runtime, analysis, state, orchestration, domain logic | runtime core | 78 |
| `services/` | independently composable product services: jobs, review, quality, delivery | product services | 0 (empty) |
| `packages/` | reusable design-domain capability: capabilities, design-system, shared types | domain capability | 275 |
| `integrations/` | third-party boundary: hosts, generators, executors, mcp, canvases | adapter owner | 76 |
| `apps/` | runnable front ends (workbench) | front end | 3 |
| `fixtures/` | test and regression fixtures | test data owner | 226 |
| `evals/` | evaluation corpora (design-lab/evals is the current location) | evaluation owner | 63 (under `design-lab/`) |
| `research/` | research inputs and candidate intake | research owner | 2 |
| `vendor/` | third-party locks and minimal absorbed sources (`sources.lock.json`) | supply chain | 1 |
| `docs/` | documentation: current / architecture / decisions / taskpacks / history | doc owner | 248 |
| `reports/` | generated projections (`current/`) and history (`history/`) | report generator | 115 |
| `scripts/` | thin repository entry points (generators, verifiers, ledger tools) | tooling owner | 14 |
| `.project/` | governance truth: manifest, path declaration, governance rules | owner | 6 |
| `.project-local/` | **all** ignored runtime data: runs, state, cache, artifacts, exports, logs, temp | runtime | 0 tracked (65,482 ignored) |
| `.github/` | repository automation (CI workflows) | CI owner | 5 |
| `LICENSES/` | third-party licence texts | supply chain | 1 |
| `design-lab/` | **legacy dual scheme** — see §2 | legacy owner | 766 |

## 2. Deviation: `design-lab/` is a second scheme

`design-lab/` (766 tracked files) predates the root scheme and holds eight
second-level areas that the scheme assigns elsewhere:

| `design-lab/` area | Files | Scheme location | Verdict |
|---|---|---|---|
| `domain-packs/` | 183 | no root equivalent | **content root**: keep, this is the design-domain pack SSOT |
| `tests/` | 156 | no root equivalent (`testpaths = design-lab/tests`) | keep; `pyproject.toml` binds it |
| `schemas/` | 124 | `src/design_lab/resources` for packaged copies | keep as the authoring location; packaged copies are projections |
| `scripts/` | 76 | `scripts/` (thin entry points) | keep; these are the verifiers referenced by docs and CI |
| `evals/` | 63 | `evals/` | keep; the root `evals/` directory does not exist |
| `research/` | 42 | `research/` | keep; the root `research/` holds only candidate intake |
| `config/` | 33 | no root equivalent | keep; it is the machine-readable product/capability SSOT |
| `templates/`, `design-systems/`, `profiles/`, `usage-notes/`, `assets/`, `tool-assets/`, `external-assets/`, `prompts/`, `memory/` | 7–20 each | mixed | keep as content; see the per-area verdict in the audit artifact |
| `core/` | 8 | `packages/` (neutral objects, contracts, policy) | **legacy**: not imported by any active code; retained as contract reference |

**Why no relocation happened here.** The taskpack forbids moving things to look
tidy, and every one of these areas is bound by an active consumer
(`pyproject.toml` testpaths, `verify_product_manifest_v3.py` expected roles, CI
verifier paths, `AGENTS.md`, and the R5 pack's own instructions). A relocation is
a migration task with its own hashes, callers and rollback — the taskpack's
`DLDS-B020` classification and `DLDS-D040` documentation work, not something to
smuggle into a directory audit. What this document fixes is that **the dual
scheme is now declared, owned and bounded**, instead of being an undocumented
accident.

Rules that follow from this declaration:

1. `design-lab/` is a **content and configuration root**, not a second runtime.
   No new runtime module may be added there; runtime code goes to `src/design_lab/`.
2. `design-lab/core/` stays a reference/contract artefact. It must not gain new
   behaviour, and nothing may import it as a runtime dependency.
3. Any file that exists in both schemes must name one authoring source and one
   generated projection; `DLDS-B040` audits exactly that.
4. `services/` is empty. It is declared in the scheme but not populated; an empty
   directory is not a capability and must not be used to claim one.

## 3. Local-only directories (not part of the tree)

`.hermes/`, `.pytest_cache/`, `.venv/` are present on disk and git-ignored. They
are not repository content. `.hermes` is a legacy agent home whose DESIGN-LAB
owned content is handled by `DLDS-E030` (never a blanket delete).

## 4. What this document is not

It is not a migration authorisation, not a licence to delete anything, and not a
claim that the repository now has one physical tree. It binds the *semantics*:
which directory owns what, which direction dependencies may point, and which
duplication is a defect.
