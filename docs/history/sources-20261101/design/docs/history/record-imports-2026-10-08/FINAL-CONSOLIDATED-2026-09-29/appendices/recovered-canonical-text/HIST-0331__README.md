# OPEN-DESIGN-Assistance V2 Global Absorption Pack

Snapshot: 2026-08-04

This is a safe, additive overlay for `DTALEX66/OPEN-DESIGN-Assistance`. It does not delete or silently overwrite existing project files.

## Included

- 112 curated sources with license, security and integration mode records.
- Current Open Design v1 manifest-compatible scenario, atom and bundle examples.
- Commercial Design Router and Brand Campaign 360 pipelines.
- 10 JSON Schemas for brief, reference DNA, directions, critique, preflight, handoff, state, cases, capability evidence and source registry.
- 8 discipline rubrics and 6 production preflight profiles.
- Standards notes for accessibility, design-token interop, print/PDF, CJK typography, spatial design, motion and 3D.
- Source registry and protocol validators plus GitHub Actions workflow.

## Apply

```bash
python apply_overlay.py "D:\All projects\OPEN-DESIGN-Assistance"
```

The default skips conflicts. To back up and replace conflicting files:

```bash
python apply_overlay.py "D:\All projects\OPEN-DESIGN-Assistance" --overwrite
```

Then run:

```bash
python opendesign-assistance/scripts/verify_source_registry_v2.py
python opendesign-assistance/scripts/verify_v2_protocols.py
```

## Important limitation

This pack was created against the public repository state and cannot push directly because the connected GitHub installation is read-only. It is merge-ready but still requires a local apply/commit or a connector with write permission.
