#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-B040 — registry SSOT audit.

One fact, one authoring source. Everything else that carries the fact is a
generated projection, a frozen historical copy, or a defect.

This script walks an explicit, reviewable table of the registry families the
taskpack names (product manifest, adapter registry, capability registry/index,
rights registry, model registry, source lock, evidence index), resolves every
referencing file by grepping the tree, and reports for each family:

* the **authoring source** (edited by a human, never generated),
* the **projections/copies** and who generates them,
* **orphans** (tracked files nobody references) and **unreproducible
  projections** (generated files whose generator is not in the tree),
* the verdict.

Writes reports/current/DEEPSEEK-REGISTRY-SSOT.json.

Usage:
    python scripts/deepseek_registry_ssot.py [--check]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports/current/DEEPSEEK-REGISTRY-SSOT.json"
TASK_KEY = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-B040"

# family -> (fact it owns, authoring source, [members], [generators])
FAMILIES = [
    ("product-manifest", "product identity, positioning, directory roles, safety boundaries",
     "design-lab/config/product-manifest.json",
     ["design-lab/config/product-manifest.json"],
     ["design-lab/scripts/verify_product_manifest_v3.py"]),
    ("adapter-registry", "which host/generator/tool adapters exist and their declared evidence",
     "integrations/adapter-registry.json",
     ["integrations/adapter-registry.json", "integrations/hosts/adobe/adapter.manifest.json",
      "integrations/generators/comfyui/adapter.manifest.json",
      "integrations/generators/minimax-h3/adapter.manifest.json",
      "integrations/hosts/open-design/adapter.manifest.json",
      "integrations/mcp/adapter.manifest.json", "design-lab/readiness/adobe-host-matrix.json"],
     ["design-lab/scripts/verify_adapter_registry.py", "design-lab/scripts/verify_adapter_matrix.py"]),
    ("capability-index", "the product capability inventory and its declared state",
     "design-lab/config/capability-index.json",
     ["design-lab/config/capability-index.json", "design-lab/config/capability-status.json",
      "design-lab/config/CAPABILITY_INDEX.md"],
     ["design-lab/scripts/generate_capability_indexes.py"]),
    ("evidence-index", "evidence level records and their tree binding",
     "design-lab/config/capability-evidence-index.json",
     ["design-lab/config/capability-evidence-index.json",
      "design-lab/config/capability-evidence-current.json",
      "reports/current/EVIDENCE_INDEX.json"],
     ["design-lab/scripts/generate_capability_evidence_index.py",
      "design-lab/scripts/update_evidence_binding.py",
      "scripts/generate_ssot_projections.py"]),
    ("rights-registry", "licence, territory and use restrictions for models, plugins, donors and fonts",
     "design-lab/config/provider-capabilities.json",
     ["design-lab/config/provider-capabilities.json", "LICENSES/", "THIRD_PARTY_SOURCES_V2.md",
      "THIRD_PARTY_SOURCES_VISUAL_V21.md", "NOTICE", "design-lab/readiness/model-radar.json"],
     ["design-lab/scripts/verify_license_coverage.py"]),
    ("model-registry", "which models exist, their digests, hardware need and qualification stage",
     "design-lab/config/external-assets-index.json",
     ["design-lab/config/external-assets-index.json", "design-lab/config/reconstruction-models.json",
      "design-lab/config/model-manifest-trust.json", "design-lab/readiness/model-radar.json"],
     ["design-lab/scripts/verify_external_assets_index.py"]),
    ("source-lock", "third-party sources, their revisions and disposition",
     "vendor/sources.lock.json",
     ["vendor/sources.lock.json", "design-lab/research/global-absorption/SOURCE_REGISTRY.json",
      "design-lab/research/global-absorption/QUARANTINE_REGISTRY.json"],
     ["design-lab/scripts/verify_source_registry.py", "design-lab/scripts/verify_sbom.py"]),
    ("capability-projection", "the reports/current capability projection",
     "reports/current/CAPABILITY_INDEX.json",
     ["reports/current/CAPABILITY_INDEX.json", "design-lab/config/capability-index.json",
      "design-lab/config/capability-status.json"],
     ["scripts/generate_ssot_projections.py"]),
    ("machine-inventory-projection", "the recorded read-only host inventory",
     "reports/current/MACHINE_INVENTORY.json",
     ["reports/current/MACHINE_INVENTORY.json", ".project/paths.json", "docs/LOCAL_ENVIRONMENT.md"],
     ["scripts/generate_machine_inventory.py"]),
    ("authority-chain", "which taskpack is authoritative and how old packs are classified",
     "reports/current/DEEPSEEK-AUTHORITY-CHAIN.json",
     ["reports/current/DEEPSEEK-AUTHORITY-CHAIN.json",
      "reports/current/DEEPSEEK-AUTHORITY-LEDGER-2026-09-14.json", "AGENTS.md"],
     ["scripts/deepseek_authority_chain.py", "scripts/deepseek_authority_ledger.py"]),
]


def tracked() -> list:
    return [line for line in subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True,
                                            text=True, encoding="utf-8").stdout.splitlines()
            if line.strip()]


SELF = "scripts/deepseek_registry_ssot.py"


def references(name: str, files: list) -> list:
    """Files that reference a registry name. The audit's own table is not a consumer."""
    hits = []
    for rel in files:
        if rel == SELF:
            continue
        path = REPO / rel
        if not path.is_file() or path.name == name:
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if name in text:
            hits.append(rel)
    return sorted(hits)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    files = tracked()
    families = []
    for family, fact, authoring, members, generators in FAMILIES:
        authoring_refs = references(Path(authoring).name, files) if (REPO / authoring).is_file() else []
        present_members = []
        missing = []
        for member in members:
            target = REPO / member
            exists = target.is_file() or target.is_dir()
            present_members.append({"path": member, "present": exists,
                                    "refs": len(references(Path(member).name, files)) if exists else 0})
            if not exists:
                missing.append(member)
        present_generators = [g for g in generators if (REPO / g).is_file()]
        orphans = [m["path"] for m in present_members if m["present"] and m["refs"] == 0
                   and m["path"] != authoring]
        verdict = "SINGLE_AUTHORING_SOURCE"
        if missing:
            verdict = "MISSING_MEMBER"
        if orphans:
            verdict = "ORPHAN_MEMBER"
        families.append({
            "family": family,
            "fact_owned": fact,
            "authoring_source": authoring,
            "authoring_source_present": (REPO / authoring).is_file(),
            "referencing_files": len(authoring_refs),
            "members": present_members,
            "generators": present_generators,
            "generators_missing": [g for g in generators if not (REPO / g).is_file()],
            "orphan_members": orphans,
            "verdict": verdict,
        })
    unproven = [f["family"] for f in families if f["verdict"] != "SINGLE_AUTHORING_SOURCE"]
    document = {
        "schemaVersion": "design-lab/deepseek-registry-ssot/v1",
        "task_key": TASK_KEY,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_sha": subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                                      capture_output=True, text=True,
                                      encoding="utf-8").stdout.strip(),
        "tracked_files_scanned": len(files),
        "families": families,
        "families_not_single_source": unproven,
        "counts": {"families": len(families),
                   "single_authoring_source": sum(1 for f in families
                                                  if f["verdict"] == "SINGLE_AUTHORING_SOURCE"),
                   "with_findings": len(unproven)},
    }
    if args.check:
        if not OUT.is_file():
            print("REGISTRY_SSOT=FAIL missing artifact")
            return 1
        current = json.loads(OUT.read_text(encoding="utf-8"))
        same = [f["verdict"] for f in current["families"]] == [f["verdict"] for f in families]
        print("REGISTRY_SSOT=" + ("PASS" if same else "DRIFT"))
        return 0 if same else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"REGISTRY_SSOT=WRITTEN {OUT.relative_to(REPO)} families={len(families)} "
          f"single_source={document['counts']['single_authoring_source']} "
          f"with_findings={len(unproven)}")
    for family in families:
        if family["verdict"] != "SINGLE_AUTHORING_SOURCE":
            print(f"  {family['verdict']:16} {family['family']:28} "
                  f"orphans={family['orphan_members']} missing={family['missing_members'] if 'missing_members' in family else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
