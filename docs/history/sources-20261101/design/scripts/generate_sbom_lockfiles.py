#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""G-2 / B2 — regenerate the SBOM lockfile-level bindings.

Writes `lockfileBindings` (pnpm-lock + uv.lock + requirements.txt: sha256 +
parsed manifest) into design-lab/config/sbom-v42.spdx.json. The binding is
the single source of truth shared with verify_sbom.py's integrity check: if a
lockfile changes after generation, the SBOM gate fails closed until this is
re-run.

Pure-stdlib (the CI python venv has no PyYAML): pnpm-lock is regex-parsed,
uv.lock is TOML-parsed. Idempotent: re-running on unchanged lockfiles only
rewrites the binding block.

Usage:
    python scripts/generate_sbom_lockfiles.py

Exit codes: 0 OK (binding written + SBOM re-verified clean), 1 FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
DL_ROOT = SCRIPTS_DIR.parent / "design-lab"
sys.path.insert(0, str(DL_ROOT / "scripts"))

import verify_sbom  # noqa: E402  (same module the gate runs)

SBOM = DL_ROOT / "config" / "sbom-v42.spdx.json"
REPO_ROOT = SCRIPTS_DIR.parent


def main() -> int:
    if not SBOM.is_file():
        print(f"SBOM not found: {SBOM}")
        return 1
    sbom = json.loads(SBOM.read_text(encoding="utf-8"))
    sbom["lockfileBindings"] = verify_sbom.build_lockfile_bindings(REPO_ROOT)
    # NB: the document namespace (tree-SHA suffix) is NOT touched here — it is
    # bound separately by update_evidence_binding / the drift gate. This tool
    # only rewrites the lockfile binding block; re-running on unchanged
    # lockfiles is idempotent.
    SBOM.write_text(json.dumps(sbom, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")
    bound = {name: (b.get("entryCount") or b.get("packageCount") or len(b.get("pins", [])))
             for name, b in sbom["lockfileBindings"].items()}
    print(f"SBOM_LOCKFILES=OK bound={bound}")
    findings = verify_sbom.check()
    for f in findings:
        print(f"  {f}")
    if findings:
        print(f"SBOM_LOCKFILES=FAIL findings={len(findings)}")
        return 1
    print("SBOM_LOCKFILES=OK (binding written + full SBOM re-verified clean)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
