# Repository licensing decision (RESOLVED)

**Decision (2026-08-07, by repository owner DTALEX66): MIT.**

- Root license: `LICENSE` (MIT), also mirrored as `LICENSES/MIT.txt` (REUSE convention).
- `NOTICE` records third-party / absorbed material and the quarantine of
  unknown or noncommercial-rights content.
- Original code and documentation: MIT.
- MiniGame runtime and design-system absorbed assets: keep their own
  provenance; unknown-rights content stays quarantined (see NOTICE).
- Commercial distribution: permitted under MIT for original work; third-party
  material remains governed by its own license (reference records are not
  vendored code).

## Remaining REUSE/SPDX work (tracked in ODA4-0102)

1. Per-file SPDX headers on source files (`SPDX-License-Identifier: MIT`).
2. `.license` sidecars for binary assets (audio/PNG/GIF) under `LICENSES/`.
3. A generated SPDX/CycloneDX SBOM and third-party BOM for release packages.
4. Keeping copyleft/external-tool adapters separated (none redistributed yet).

Historical note: prior to this decision the repository had only plugin-level
`MIT` declarations and no root license. The root MIT decision now supersedes
that. `NO_PUBLIC_COMMERCIAL_RELEASE` is lifted for original MIT-covered work;
release still requires the full V4 gate (E4/E5 evidence).
