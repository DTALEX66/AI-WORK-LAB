# DESIGN-LAB — Codex Real-Host Handoff

- **Task**: `DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-J000`
- **Purpose**: give Codex everything it needs to start at real host E2 → real workflow E3 → independent/human E4, without redoing repository work
- **Prepared by**: DeepSeek. **Nothing in this document has been executed.** Every command below is an outline, not a transcript, and no live result is claimed.
- **Status of every domain**: `DEFERRED_TO_CODEX`

## 0. What is already done, and what is deliberately not

Done and re-verifiable from the repository (evidence paths in parentheses):

| Area | State | Evidence |
|---|---|---|
| Authority, directory, language, size, spill governance | closed | `reports/current/DEEPSEEK-*.json`, `docs/architecture/*.md` |
| Contract graph, migration rehearsal, foundation audit | closed | `reports/current/CONTRACT-GRAPH.json`, `CREATIVE-MIGRATION-REHEARSAL.json`, `FOUNDATION-AUDIT.json` |
| Standards baselines (DTCG 2025.10, OTIO, C2PA 2.4, Penpot v3, glTF 2.0) | closed structurally | `src/design_lab/interop/**`, `src/design_lab/creative/media/three_d.py` |
| QA planes, human jury, approval gates | closed structurally | `src/design_lab/assurance/**`, `src/design_lab/creative/approval.py` |
| Rights registry, supply chain gate, H3 blocked | closed | `design-lab/config/rights-registry.json`, `reports/current/SUPPLY-CHAIN-REPORT.json` |

Not done, on purpose: any real host run, any GPU inference, any model download, any human signature.
**Codex must not treat any DeepSeek artifact as host evidence.** The highest level any of them may claim is E2, and only for a host this agent actually ran.

## 1. Universal preconditions (all domains)

1. **Owner authorisation** for the window, recorded with scope and date.
2. **One writer**: no other agent or session touches the checkout while Codex has it.
3. **Freeze the base**: record `git rev-parse HEAD` before the first run and after the last.
4. **Boundary discipline**: write only inside `.project-local/**`, the explicit external roots declared
   in `.project/paths.json`, and the host's own project folder the owner opens. Never `E:\`.
5. **Evidence level ladder** (`AGENTS.md`): E0 declared, E1 structural, E2 controlled runtime on a
   fixture, E3 real brief → native editable artifact → reopen readback → rollback, E4 independent
   human acceptance, E5 released and repeatable.
6. **Every run produces a receipt**: exact host build, OS, subject SHA, ordered actions, artifact
   digest, readback digest, failure text, rollback performed, and the four axes recorded separately.
7. **No silent fallback**: if a host cannot do it, the record says `unsupported`; it never routes the
   work to another tool and files the result under this host's name.

Run the zero-spill probe around every session:

```powershell
$py = 'D:\All projects\DESIGN-LAB\.venv\Scripts\python.exe'
& $py scripts/verify_zero_spill.py --snapshot codex-before
#   ... do the host work ...
& $py scripts/verify_zero_spill.py --diff codex-before      # must print NO_SPILL_DETECTED
& $py scripts/verify_clean_tree.py --allow <your paths> --reason "Codex host run"
```

## 2. Adobe — Photoshop, Illustrator, Premiere

**Contract**
- Adapter declarations: `integrations/hosts/adobe/adapter.manifest.json`; registry entry
  `adapter-adobe-photoshop` / `adapter-adobe-illustrator` in `integrations/adapter-registry.json`.
- Photoshop: COM automation (`src/design_lab/adapters/photoshop_com.py`) is the historical primary
  transport; UXP is the forward path. Illustrator: `src/design_lab/adapters/illustrator_com.py` plus
  the JSX assembler `integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx`.
- Assembly contract for the target artifact: `integrations/hosts/adobe/illustrator/ASSEMBLY-CONTRACT.md`.
- The adapter must satisfy `src/design_lab/adapters/spi.py` (`probe/prepare/execute/observe/readback/rollback`).

**Fixture**
- One synthetic design small enough to inspect by eye: a two-layer composition with one text object,
  one raster placement and one vector shape; a second fixture identical except for one deliberate
  change, so the patch path has a known-before/known-after.
- Record the fixture digest before the run; the fixture is input evidence, not output evidence.

**Commands (outline — discover the real interface from the installed build, do not copy flags)**
1. Record the installed build string from the host itself (About dialog or the official `--version`
   surface); never reuse the version recorded in `reports/current/MACHINE_INVENTORY.json`.
2. `probe` through COM/UXP: confirm the automation entry point answers and the version matches.
3. `prepare`: open the fixture, produce the design IR → lowering plan
   (`src/design_lab/native_patch_plan.py`, `design_lab/native_plan.py`).
4. `execute`: apply the patch, save, export the editable artifact.
5. `readback`: reopen the exported file in the host and compare the changed element and the digest.
6. `rollback`: restore the pre-run file from the recorded backup and reopen it.
7. Deliberately fail one step (e.g. apply a patch to a missing layer) and record the exact error text
   plus the recovery.

**Evidence template** (`integrations/hosts/adobe/evidence/`)
```text
host_id / host_version: <from the host>
os / subject_sha: <windows build> / <DESIGN-LAB commit>
fixture: <path> sha256:<...>
actions: <ordered, replayable>
artifact: <path> sha256:<...> bytes=<n>
readback: <path> sha256:<...> compared=<what was compared>
failure: <step> <exact text> recovery=<what was done>
rollback: <what was restored and how it was verified>
axes: implementation=<...> unit=<...> host_live=<...> delivery=<...>
level: E2 | E3   (E4 only with a named human reviewer)
```

**Do not claim**: any DeepSeek-side E3; a screenshot as readback; a version read from the registry
instead of from the running host.

## 3. Open Design

**Contract**: `integrations/hosts/open-design/adapter.manifest.json`,
`design-lab/scripts/{configure,doctor}_open_design_windows.py`,
`integrations/hosts/open-design/verifier/verify_open_design_host_adapter.py`,
`design-lab/config/OPEN_DESIGN_COMPATIBILITY_MATRIX.md`.

**Precondition**: the desktop host was **not found in the recorded search scope** on this machine
(`reports/current/MACHINE_INVENTORY.json`). Installation is the owner's action; nothing is bundled.

**Fixture**: the adapter's own expert-suite projections and one minimal real design task.

**Commands (outline)**: install/probe → record the build → generate projections → confirm the
generated `open-design.json` matches the committed ones → install the expert suite under an approved
host profile → create → readback → modify → save → reopen → rollback. Discover CLI/MCP arguments
from the installed official runtime; this repository forbids inventing them.

**Evidence template**: as §2, plus the projection diff and the host profile id.

**Do not claim**: E3 from a projection file; any capability of a host that was never launched.

## 4. MiniMax Design

**Contract**: `integrations/hosts/minimax-design/adapter.manifest.json` (E0, `supported: false`),
`POC-PLAN.md` (the acceptance contract), `rights-and-provider-policy.md`.
Keep the **application** and the **H3 weights** on separate acceptance paths.

**Fixture**: one simple single-artboard design with one deterministic, describable edit.

**Commands (outline)**: the POC plan's five steps in order: create/open → one deterministic edit →
export → reopen → compare digests. Discover the export surface from the application.

**Evidence template**: as §2. A host that cannot reopen its own export is recorded as
`supported: false`, not as a failed run to hide.

**Do not claim**: anything about the H3 weights from the application's behaviour; H3 stays
`BLOCKED_BY_LICENSE` with an unadjudicated territory position
(`docs/handoffs/DEEPSEEK-RIGHTS-REFRESH-MINIMAX-H3-2026-09-13.md`).

## 5. ComfyUI

**Contract**: `src/design_lab/generative_workflow` provider
(`src/design_lab/creative/generative/workflow_provider.py`), the bounded transport
(`src/design_lab/generators/comfy_http.py`), the structural gate
(`design-lab/scripts/verify_comfyui_gate.py`), and the workflow pin/task protocol
(`src/design_lab/generators/comfy_task.py`).

**Fixture**: a graph that needs no model download (`EmptyImage → SaveImage`) for the transport smoke
test, then one real workflow with a rights-cleared checkpoint for generation.

**Commands (outline)**: start the portable bundle → record `comfyui_version.py` and the API surface →
submit → poll progress → cancel and confirm acknowledgement → force a disconnect and confirm recovery
→ read back the produced artifact and its digest → partial re-run of one node and confirm only its
downstream changed (`src/design_lab/creative/generative/partial_execution.py` plans this).
The ten-run golden requirement in `DL-R5-008` still stands: record ten complete runs including
failures, and never present a partial log as ten successes.

**Evidence template**: as §2 plus `prompt_id`, node fingerprint, model digests and the queue history.

**Do not claim**: design quality from a generated image; a cached hit as a new generation.

## 6. Penpot

**Contract**: `src/design_lab/interop/penpot.py` with `validate_penpot_archive` (structural validation
of a real `.penpot` ZIP: manifest present, declared references resolvable, no traversal, no duplicate
entries, declared sizes matching).

**Fixture**: one exported `.penpot` archive from the host, plus a synthetic archive for the negative
cases.

**Commands (outline)**: export from the host → run the validator on the real archive → import back →
edit one object → re-export → compare.

**Do not claim**: that structural validation implies the host can import it; only the host can show that.

## 7. Blender / 3D

**Contract**: `src/design_lab/creative/media/three_d.py` — a real byte-level GLB/glTF validator with
the full accessor matrix (`SCALAR/VEC2/VEC3/VEC4/MAT2/MAT3/MAT4`, per-column 4-byte matrix padding,
byteStride and alignment rules, sparse accessors) plus `parse_glb`/`validate_glb`/`summarize_glb`.

**Fixture**: a small scene with one mesh, one material and one camera; a GLB export of it for the
validator; a deliberately corrupted GLB for the negative path.

**Commands (outline)**: run headless (`--background --python`) → build the scene → export → reopen in
Blender and change one object → confirm the change survived → render a preview → roll back.
Blender is **not installed** on this machine; installation is the owner's action.

**Evidence template**: as §2 plus the scene graph digest and the GLB chunk table digest.
**Do not claim**: that a valid GLB implies an editable Blender scene.

## 8. Design quality and the Human Jury

**Contract**: `src/design_lab/assurance/qa_plane.py` (three planes, evidence ceilings, a model-assisted
plane that may never produce a final verdict), `human_jury.py` (verdict vocabulary `APPROVE`/`REJECT`,
artifact-digest binding, proposals structurally unrepresentable as verdicts),
`src/design_lab/creative/approval.py` (a gate approval is a decision by a human).

**Fixture**: the golden set and the accepted/rejected pairs the owner selects; the rubric the jury
will use.

**Commands (outline)**: run the deterministic checks → run the model-assisted plane and record its
`PASS`/`WARN`/`REVIEW_REQUIRED` → escalate to a **named human** → record the human verdict with its
evidence references → confirm the delivery gate blocks while any human gate is unsigned.

**Evidence template**: jury record v2 plus the reviewer identity and the RFC3339 decision time.
**Do not claim**: E4 from a model's opinion; a jury verdict nobody signed; an approval this agent
produced.

## 9. Audio and Video

**Contract**: `src/design_lab/creative/media/audio_provider.py` (ASR/TTS/SFX capability declarations,
transcript text structurally forbidden), `src/design_lab/interop/timeline.py` (OpenTimelineIO contract
with official transition semantics), `src/design_lab/creative/media/video_boundary.py` (which side owns
rendering, encoding and colour management, by versioned capability id).

**Fixture**: one short spoken line for ASR/TTS, one 20–30 second music segment, one three-shot
timeline.

**Commands (outline)**: run the local model → record text/model/version → export the track → build the
OTIO timeline → hand it to the editing host → read back the host's project → confirm the boundary rules
before claiming any rendered output.

**Do not claim**: a rendered or encoded deliverable from a timeline contract; audio ownership from a
transcript digest.

## 10. What Codex must leave behind

1. One evidence record per run, in the domain's `evidence/` directory, with the fields in §2.
2. The four axes updated **through the ledger**, never by editing a report
   (`design-lab/config/task-ledger-r3.json` is the only task-status authoring source).
3. `git status` clean, or every dirty path attributed (run `scripts/verify_clean_tree.py`).
4. The zero-spill diff for each session.
5. Any new dependency recorded with owner, reason, licence, exact version and rollback
   (`DLDS-G040`), and the lock regenerated — `uv sync --locked` is the CI gate.
6. `scripts/run_bound_test_suite.py` for any test claim, so the result is bound to a subject.

## 11. The one thing this document is not

It is not a substitute for running anything. Every level above E1 in this repository is currently
**unclaimed**, and it stays that way until a real host run produces the artifacts.
