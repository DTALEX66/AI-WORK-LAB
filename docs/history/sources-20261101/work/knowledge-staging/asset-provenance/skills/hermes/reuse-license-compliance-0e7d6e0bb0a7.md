---
name: reuse-license-compliance
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/reuse-license-compliance/SKILL.md
---

---
name: reuse-license-compliance
description: Use when backfilling SPDX/REUSE headers or license gates.
---

# REUSE / SPDX License Compliance Backfill

Class of work: adding SPDX-License-Identifier headers to a codebase, generating
binary `.license` sidecars, producing SPDX/CycloneDX SBOMs and third-party BOMs,
and wiring CI license-coverage gates so they actually fail on missing coverage.

## When to use
- Repo picks MIT (or any license) and must become REUSE-compliant.
- Backfilling SPDX headers on source files across mixed languages.
- Fixing a CI license gate that "passes" but only checks the root LICENSE file.
- Auditing whether binary/media assets carry `.license` sidecars or an exemption.

## Core rule: language-correct comment syntax (CRITICAL)
SPDX headers must use the comment syntax of each language. Injecting the wrong
one **breaks the file**:

| Language | Correct | Wrong (breaks) |
|---|---|---|
| Python | `# SPDX-License-Identifier: MIT` | — |
| JS / TS / MJS | `// SPDX-License-Identifier: MIT` | `# ...` → `SyntaxError: Invalid or unexpected token` |
| CSS / HTML block | `/* SPDX-License-Identifier: MIT */` | `# ...` breaks |
| SQL | `-- SPDX-License-Identifier: MIT` | — |

Symptom of a bad JS injection: the test suite count collapses (e.g. 321 → 54
with `pass 0 / fail 54`, each `SyntaxError: Invalid or unexpected token`) because
`#` at statement position is a JS private-field / unexpected-token error.

Fix pattern: write a two-pass script — (1) drop any bare `# SPDX...` line that is
not a `#!` shebang, (2) re-inject with `//`. See `scripts/backfill_spdx.py`.

## Preserve file structure
When injecting, keep in order (never reorder):
1. UTF-8 BOM (if present) — strip to decode, re-prepend on write.
2. Shebang (`#!...`) — must remain the FIRST line.
3. Python encoding declaration (`# -*- coding: ... -*-` / `# coding: ...`).
4. Docstring / block comment.
5. THEN the SPDX line, followed by a blank line, then the body.

Idempotent: skip any file whose first ~200 chars already contain
`SPDX-License-Identifier`.

### Windows / CRLF-safe idempotent injection (single-pass)
For pure-Python backfills you do NOT need the two-pass JS script. A single
pass is enough if it opens files correctly and skips existing headers:
- Open read with `encoding='utf-8-sig'` (auto-strips BOM) and `newline=''`
  (preserves the file's CRLF/LF line endings).
- Split on `\n` keeping endings; find the insertion index: line 0 if it is a
  `#!` shebang, else index 0; skip if any of the first ~4 lines already
  contain `SPDX-License-Identifier`.
- Insert `# SPDX-License-Identifier: MIT\n` at that index; write back with
  `encoding='utf-8', newline=''`.
This keeps BOM + line endings intact and is re-runnable (idempotent).

## .license sidecar audit: self-generated vs third-party ownership (CRITICAL)

When auditing a repo's `.license` sidecars (or backfilling them), the `SPDX-FileCopyrightText` line MUST distinguish who actually holds the rights:

| Asset class | Correct copyright line | Wrong (false re-licensing) |
|---|---|---|
| Self-generated assets (AI + own art, game sprites, screenshots of your own product, generated audio) | `SPDX-FileCopyrightText: 2026 <owner> and contributors` | — |
| Third-party screenshots / images vendored from upstream repos | real upstream author, e.g. `SPDX-FileCopyrightText: JimLiu (baoyu-design)`, `Avinava (document-design-system)` | `2026 <owner> and contributors` — claims copyright over someone else's image |
| Vendored upstream docs/images | upstream author + repo name | blanket `<owner> and contributors` |

A blanket `<owner> and contributors` + MIT on third-party images is a **false re-licensing defect**: it asserts DESIGN-LAB owns copyright of upstream screenshots and re-licenses them MIT, which it cannot do. This is exactly the class of P0 an audit flags ("新增 .license 侧车存在错误再授权风险").

Audit method (validated 2026-08-14, DESIGN-LAB 154 sidecars):
1. Enumerate via `git ls-files '*.license'` (NOT `rglob` — path-prefix matching on rel paths can silently miss `intelligence/`/`knowledge/` subtrees).
2. Bucket by directory ownership: `minigame-runtime/`, `exports/` = self-generated; `design-lab/intelligence/`, `design-lab/knowledge/` = third-party vendored.
3. For every third-party bucket entry, assert the copyright line names a REAL upstream author (grep the sidecar's `SPDX-FileCopyrightText`), never the repo owner.
4. When the same generator wrote sidecars, per-asset authorship must still be resolved from each asset's source repo — a uniform "authors" string is only valid when the whole tree is one upstream project.

## Coverage-verifier scope: exclude split-out / generated trees (CRITICAL)
A combined coverage verifier (source headers + binary sidecars) that scans the
whole repo will report **false "missing" gaps** for:
- Product trees already split out of this repo's ownership (e.g. a
  `minigame-runtime/` subtree kept only as an archive pointer),
- vendored / `node_modules` / generated bundles,
- non-source asset trees you intentionally leave out of header coverage
  (templates, domain packs, design systems, evals, exports).

Give the verifier an `EXCLUDE_PREFIX` tuple (and skip `node_modules/`), then
let it iterate `git ls-files` only, filtering by extension. A clean
`LICENSE_COVERAGE=OK (0 missing source, 0 missing sidecar)` is only trustworthy
if exclusions are intentional and documented, not accidental omissions.

## Supply-chain ledger enforcement: REVIEW-BLOCK components must never be default engines

A repo can carry a **supply-chain ledger** (`docs/truth/SUPPLY_CHAIN_LEDGER.json` — component id, name, capability, code/model licenses, disposition) that marks components `REVIEW-BLOCK` (e.g. code Apache-2.0 but weights under a modified OpenRAIL-M requiring separate review) or `REJECT-CORE`. The ledger is the licensing decision; the **default engine chain** (e.g. `app/ingestion/multi_format._ENGINES`) is the execution truth. A REVIEW-BLOCK component leaking into a default chain is a real compliance defect even when the code itself is Apache-2.0 — the weights/licensing decision gates *selection*, not just attribution.

Validated 2026-08-12 (Cognitive-Loop-OS #128): `marker-pdf` was registered as a default PDF engine while ledger B003 (Marker) was REVIEW-BLOCK; an enhanced MFX-001 test caught it.

Pattern:

1. **Drive the assertion from the ledger, not a hard-coded name list.** Build `blocked = {c["name"].lower() for c in ledger["components"] if c["disposition"] == "REVIEW-BLOCK"}` and assert `name not in chain_text` for EVERY blocked name. A hard-coded list rots (the 2026-08-12 sweep found the old list also asserted `zotero` as REVIEW-BLOCK when it never was). Keep a guard asserting the historical blockers are still in the ledger so the ledger itself can't silently drop a gate.
2. **Scan code AND docs, not just the engine map.** grep the blocked names across `app/` `shared/` and README/docs; a stub adapter file that imports nothing (delegates to the fallback chain) is not an integration — do not treat the filename as proof (frozen addenda explicitly warn "不得把已有 crawl4ai 依赖或文件名当作真实集成证明").
3. **Distinguish the component name from common English words.** `marker` matches `COMMAND_MARKERS` / `shift_markers` in unrelated code — verify each hit is the actual component before "fixing" anything.
4. **Removal pattern:** drop the entry from the default chain, keep the adapter function defined (re-enter only after the license review resolves), add an inline comment citing the ledger id + reason, and update the module header diagram. Run the MFX-001 regression + adapter contract tests after.
5. **Dependency declarations are not integration either.** `crawl4ai`/`langfuse`/`promptfoo` declared in a dependency group with zero imports can be legitimate *planned* reserves — check the frozen addenda/taskpack docs before calling them dead dependencies and removing them (removing a frozen-baseline-approved reserve violates the immutable baseline). `python-multipart` looks unused but is required by FastAPI `UploadFile=File(...)` — check indirect consumers before flagging.


Do NOT hardcode an absolute repo path in the verifier (it breaks on other
machines/CI). Use `REPO = Path(__file__).resolve().parents[1]` and run all
`git ls-files` / path lookups through `cwd=REPO`. This makes the same script
work locally and in CI (e.g. a `canonical-verify-v4.yml` step running it
directly).

## Drift-gate interplay (generated artifacts)
In repos with committed build bundles (e.g. `android-minigame/game.js`, webview
assets), adding a header to `src/*.js` changes what the bundle **should** be.
A drift gate that byte-compares against `git show HEAD:<file>` will FAIL until you:
1. Rebuild the bundles (`node build.js <platform>` + platform prep steps).
2. Commit source AND rebuilt bundles together.
3. Re-run the drift gate — it now compares against the new HEAD blob and passes.

Do NOT treat "drift gate still FAIL after rebuild" as a bug — if HEAD hasn't been
advanced to the rebuilt artifacts, it is expected. Commit first, then re-check.

## CI coverage gate (make it real)
A license gate that only does `test -f LICENSE` is fake. Add a coverage loop that
iterates tracked source files (exclude generated/vendored dirs), greps the first
few lines for `SPDX-License-Identifier`, and `exit 1` with a count on any miss.
Also make a general clean-tree gate fail on ANY `git status --porcelain` output
instead of just printing `wc -l` (a count with non-zero does not fail a step).

## Verification
- Coverage loop reports `missing=0` (mirror the CI check locally).
- `python -c "import ast; ast.parse(open(f).read())"` on every modified .py.
- Run the language test suite (e.g. `node scripts/run-tests.cjs`) — expect the
  full count restored and 0 fails.
- Run the drift gate — expect OK after commit.

## Beyond source headers: binary assets + SBOM
Source-header backfill is only half of REUSE. Tracked binary/media assets need
`.license` sidecars, an SPDX SBOM, a combined local coverage gate (source
headers + sidecars in one verifier), and registration of that gate as a
secondary verifier in the umbrella gate so CI actually runs it.
Full recipe (sidecar format, SPDX-2.3 SBOM JSON, combined gate, third-party
BOM): `references/binary-assets-and-sbom.md`.
A portable, copy-able combined verifier is at
`scripts/verify_license_coverage.py` (adjust SOURCE_EXT / BINARY_EXT /
EXCLUDE_PREFIX per repo; registers as a secondary verifier in the umbrella
gate and a CI step via `python scripts/verify_license_coverage.py`).

**Vendored third-party trees belong in the SBOM as packages** — a binary-only
SBOM omits the largest license surface in a repo that vendors whole skill/tool
trees. Derive vendored packages from the source registry (`vendor-adapt` +
`license_verified`), bind `documentNamespace` to the verified tree SHA, and add
a fail-closed `verify_sbom.py` (SPDX-2.x valid, SPDXID unique, tree-SHA suffix
present, every vendored registry entry covered) to the aggregate chain. See
`references/binary-assets-and-sbom.md` → "Vendored third-party trees as SBOM
packages".
