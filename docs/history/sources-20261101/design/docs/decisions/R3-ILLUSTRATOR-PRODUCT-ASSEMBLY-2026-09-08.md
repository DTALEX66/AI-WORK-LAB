# Illustrator product assembly: first native round trip

Status: IMPLEMENTED_LOCAL / scoped TESTED_LOCAL. Full R3-11 remains PARTIAL.
Base commit: `5bac7f6c3ce4b4568c9b2fb2f9a03ca392445829`; tests ran with the
assembly and regression changes in the working tree. This is not an exact-SHA
release, independent quality acceptance, or complete reconstruction workflow.

## Implemented

The actual `integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx`
now rejects invalid jobs before document creation, builds editable text and
Bezier paths, embeds raster assets in AI, saves/closes/reopens, reads structure,
exports PNG/SVG, then reopens the native AI editing session again.

The trusted caller must supply a separate approved root. Payload fields are
closed; malformed geometry, unknown operations, missing fonts/assets, duplicate
IDs, existing output and outside paths reject. The detailed input and remaining
limitations are in [ASSEMBLY-CONTRACT](../../integrations/hosts/adobe/illustrator/ASSEMBLY-CONTRACT.md).

## Actual tests and errors retained

1. RED: `test_illustrator_job_validation.py` executed actual JSX in Node VM.
   Twenty of 22 invalid-job cases incorrectly reached document creation before
   the change. File/Folder/fonts are explicit doubles, not Adobe proof.
2. GREEN: all 22 reject before creation; valid input passes preflight. Existing
   ten path decisions also pass. Two existing static adapter tests pass.
3. Native RED, Illustrator 29.5.1: `run-1788797553158/result.tsv` reported
   ExtendScript syntax error at line 50; no document created. An unescaped slash
   inside a regex character class parsed in Node but not the host. Replaced
   it with normalized slash input and an explicitly escaped regex slash.
4. Native RED: `run-1788797659973/result.tsv` reported missing editable text,
   textCount=0, documents 0→0. This is the actual empty product-bridge behavior,
   not a simulation. Object construction/save/reopen was then implemented.
5. Native partial failure: `run-1788797873143/result.tsv` reported final native
   identity mismatch. AI, PNG and SVG existed; text/Bezier/raster assertions
   passed. Identity checked before export passed but the returned document after
   SVG export no longer matched AI. The bridge now closes that task-owned export
   session and explicitly opens AI again before returning it.
6. Native GREEN: `run-1788798022227/result.tsv` PASS, host 29.5.1, textCount=1,
   documentsBefore=0, documentsAfter=0. Wrapper directly checks text contents,
   Bezier point/control, embedded raster counts, all three files and native
   document identity. Product readback additionally checks all Bezier geometry,
   layer count, artboard, font and font size.
7. Independent readback: PNG loaded with Pillow, size `(800,600)`, mode RGBA;
   output files are nonempty. This is not pixel-fidelity or rights approval.

Runtime root (ignored):
`D:/All projects/DESIGN-LAB/.project-local/task-artifacts/illustrator-product-20260908/`.
The wrapper is `run.jsx`; successful outputs are under `run-1788798022227/`.
Its source is preserved at
`design-lab/tests/host_fixtures/illustrator_assembly_native.jsx` (machine-specific
qualification fixture, not auto-run by unit tests). It uses fixed project-owned
roots and the prior synthetic PNG; missing inputs must fail, never be invented.
Each attempt uses a new directory. Failure evidence was not overwritten/deleted.
Only project-owned new documents were used. UI input used Computer Use to select
the reviewed script in Illustrator; all drawing/save/readback used native JSX.

## SHA-256 bindings

| Artifact | SHA-256 |
|---|---|
| Actual product JSX | `7e5b795a69609b5b7886205a91f94c32a280ff65288347f822e7ce0c4187e525` |
| Runtime wrapper run.jsx | `63711699cd0a81e12dba4d08dd3690d3eb8480f2ffad742fa8c5d6636c6b1fe4` |
| baseline.ai | `31e44321c525cec4c0e2a1ec4865a08625e02c38e2271bcca1669dc61d74efb1` |
| baseline.png | `36ac69e940a544bff13866fe6b49c650d82a8b50421ef62bb126d30b742711de` |
| baseline.svg | `2226bca8ac7b14eab4499caf1af854da768cfed685331cc10937573d3afd77e9` |
| result.tsv | `bdc12dc651999f78ddf5c4eb82af22533db5cf98843ec3582d5fcf9e42ec50af` |

Generated Adobe outputs remain local/ignored. SVG may embed font material; no
font redistribution clearance is implied and it must not be uploaded casually.

Final local gates: `.venv/Scripts/python.exe -B design-lab/scripts/verify_design_lab.py`
reported `total=49 failed=0`; targeted Illustrator tests passed. Generated report
drift after source changes was rebuilt by `scripts/generate_current_reports.py`;
`--check` passed for bound-input integrity. That check is not live cloud readback.

## Required continuation, not completion claims

- Closed group/mask contract and real native masked output.
- Two object-local modifications, separately saved/reopened, plus rollback.
- Coordinator-owned attempts/leases/receipts and unknown-effect recovery; the
  synchronous JSX is not yet dispatched from the product API.
- Machine-readable schema parity, detailed geometry/color/raster/z-order
  readback and repeatable multi-object qualification.
- 5–10 complex reference types, PS native editable deliverables, UI workflow,
  independent Jury/rights/production acceptance, Comfy video remain outstanding.
- Knowledge migration remains deferred. R4.1 is reviewed, not silently made
  the task authority; R3 ledger remains authoritative. No historic receipt was
  relabeled as fresh success.

Rollback: restore this implementation through a reviewed forward/revert commit;
do not reset unrelated work or remove user assets. The outputs/old failures are
independent session directories and remain available for inspection.
