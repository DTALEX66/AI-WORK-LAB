# Repository licensing decision required

The public repository currently uses license fields inside plugin manifests but does not establish one verified root license for all historical code, documentation, generated media and absorbed assets.

Before public commercial distribution:

1. Inventory copyright owners and origins.
2. Choose the root license(s) for original code and documentation.
3. Add `LICENSES/` and per-file SPDX metadata using REUSE conventions.
4. Keep copyleft/external-tool adapters separated.
5. Add `.license` sidecars for binary assets.
6. Generate SPDX or CycloneDX BOM and notices.
7. Remove or quarantine anything with unknown rights.

This file intentionally does not choose a license on the owner's behalf.
