#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify DESIGN-LAB V3 product manifest convergence.

The repository intentionally keeps this verifier dependency-free. It performs the
project-specific checks that a generic JSON Schema validator cannot prove:
referenced paths exist, capability families point at real local contracts, and
runtime/commercial claims remain bounded by evidence policy.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Run standalone from any cwd: the ladder is authored in src/, not copied here.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from design_lab.governance.evidence_levels import EVIDENCE_LEVELS  # noqa: E402

ASSISTANCE_DIR = "design-lab"
MANIFEST_REL = f"{ASSISTANCE_DIR}/config/product-manifest.json"
CAPABILITY_STATUS_REL = f"{ASSISTANCE_DIR}/config/capability-status.json"
PRODUCT_SCHEMA_REL = f"{ASSISTANCE_DIR}/schemas/product-manifest.schema.json"
CAPABILITY_STATUS_SCHEMA_REL = f"{ASSISTANCE_DIR}/schemas/capability-status.schema.json"
PROJECT_DEFINITION_REL = "docs/current/PROJECT_DEFINITION.md"
ARCHITECTURE_REL = "docs/architecture/ARCHITECTURE.md"

EXPECTED_EVIDENCE_LEVELS = list(EVIDENCE_LEVELS)
EXPECTED_STATES = ["NOT_RUN", "PASS", "FAIL", "BLOCKED", "UNVERIFIED", "SKIPPED_OPTIONAL"]
EXPECTED_CAPABILITY_STATES = [
    "missing",
    "declared-only",
    "structural-pass",
    "isolated-pass",
    "runtime-pass",
    "release-verified",
    "commercially-proven",
    "blocked",
    "superseded",
]
EXPECTED_FAMILIES = {
    "design-intelligence",
    "professional-visual-domains",
    "visual-quality",
    "creative-toolchain",
    "production-handoff",
    "research-evidence",
    "release-evidence",
}
EXPECTED_DIRS = {
    "design-lab/core/",
    "research/candidates/",
    "design-lab/config/",
    "design-lab/schemas/",
    "integrations/",
    "packages/capabilities/atoms/",
    "packages/capabilities/scenarios/",
    "packages/capabilities/bundles/",
    "research/candidates/",
    "design-lab/evals/",
    "design-lab/profiles/",
    "design-lab/research/",
    "packages/capabilities/quality/",
    "design-lab/production/",
    "design-lab/templates/",
    "design-lab/assets/",
    "packages/design-system/",
    "fixtures/domains/game-visual/",
    "docs/",
}
RUNTIME_READY_MARKERS = [
    "host runtime registration via AdapterRecord",
    "runtime ID/version read-back",
    "minimal task execution",
    "artifact and provenance read-back",
]
V3_DOC_MARKERS = [
    "Agent-platform-neutral",
    "evidence",
    "runtime",
    "commercial",
    "provenance",
]


@dataclass
class Result:
    label: str
    ok: bool
    detail: str = ""


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / ASSISTANCE_DIR).is_dir() and (parent / ".git").exists():
            return parent
    raise SystemExit("Could not locate repository root")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(results: list[Result], label: str, ok: bool, detail: str = "") -> None:
    results.append(Result(label, ok, detail))


def require_object(results: list[Result], label: str, value: Any) -> dict[str, Any]:
    check(results, f"{label} is object", isinstance(value, dict), type(value).__name__)
    return value if isinstance(value, dict) else {}


def require_path(results: list[Result], root: Path, rel: str, *, file: bool | None = None) -> Path:
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        check(results, f"path stays inside repository: {rel}", False, str(path))
        return path
    check(results, f"path stays inside repository: {rel}", True)
    exists = path.exists()
    check(results, f"path exists: {rel}", exists)
    if exists and file is True:
        check(results, f"path is file: {rel}", path.is_file())
    if exists and file is False:
        check(results, f"path is directory: {rel}", path.is_dir())
    return path


def verify_manifest_shape(root: Path, manifest: dict[str, Any], results: list[Result]) -> None:
    check(results, "manifest schemaVersion", manifest.get("schemaVersion") == "design-lab/product-manifest/v1", str(manifest.get("schemaVersion")))
    product = require_object(results, "manifest.product", manifest.get("product"))
    check(results, "product id", product.get("id") == "design-lab", str(product.get("id")))
    check(results, "product name", product.get("name") == "DESIGN-LAB", str(product.get("name")))
    positioning = str(product.get("positioning", ""))
    for marker in ["commercial", "visual quality", "editable delivery", "no default host"]:
        check(results, f"product positioning includes {marker}", marker.lower() in positioning.lower(), positioning)
    check(results, "no primaryRuntime in product contract", "primaryRuntime" not in product, "present" if "primaryRuntime" in product else "absent")
    check(results, "no fiveNeutralities in product contract", "fiveNeutralities" not in product, "present" if "fiveNeutralities" in product else "absent")
    neutrality = product.get("neutralityPolicy") if isinstance(product.get("neutralityPolicy"), dict) else {}
    for key in ["modelNeutral", "styleNeutral", "domainNeutral", "platformNeutral", "versionNeutral"]:
        check(results, f"neutrality policy includes {key}", bool(neutrality.get(key)), str(neutrality.get(key)))
    rights = product.get("rightsPolicy") if isinstance(product.get("rightsPolicy"), dict) else {}
    check(results, "rights policy mode rights-governed", rights.get("mode") == "rights-governed", str(rights.get("mode")))
    check(results, "rights policy default unknown reference-only", rights.get("defaultUnknown") == "reference-only", str(rights.get("defaultUnknown")))
    non_goals = "\n".join(str(item) for item in product.get("nonGoals", []))
    for phrase in ["replace Open Design", "claim runtime", "static files"]:
        check(results, f"non-goals guard: {phrase}", phrase.lower() in non_goals.lower(), non_goals)

    policy = require_object(results, "manifest.evidencePolicy", manifest.get("evidencePolicy"))
    levels = policy.get("levels")
    states = policy.get("states")
    runtime_requires = policy.get("runtimeReadyRequires") if isinstance(policy.get("runtimeReadyRequires"), list) else []
    check(results, "evidence levels exact", levels == EXPECTED_EVIDENCE_LEVELS, str(levels))
    check(results, "states exact", states == EXPECTED_STATES, str(states))
    for marker in RUNTIME_READY_MARKERS:
        check(results, f"runtime ready requires {marker}", marker in runtime_requires, str(runtime_requires))

    directory_roles = manifest.get("directoryRoles") if isinstance(manifest.get("directoryRoles"), list) else []
    role_paths = {item.get("path") for item in directory_roles if isinstance(item, dict)}
    check(results, "all expected directory roles present", EXPECTED_DIRS <= role_paths, str(sorted(EXPECTED_DIRS - role_paths)))
    for rel in sorted(role_paths):
        if not isinstance(rel, str):
            check(results, "directory role path is string", False, str(rel))
            continue
        require_path(results, root, rel, file=False)

    families = manifest.get("capabilityFamilies") if isinstance(manifest.get("capabilityFamilies"), list) else []
    family_ids = {item.get("id") for item in families if isinstance(item, dict)}
    check(results, "capability family IDs exact", family_ids == EXPECTED_FAMILIES, str(sorted(family_ids ^ EXPECTED_FAMILIES)))
    for item in families:
        if not isinstance(item, dict):
            check(results, "capability family shape", False, str(item))
            continue
        family_id = str(item.get("id"))
        check(results, f"family {family_id}: title present", bool(item.get("title")), str(item.get("title")))
        check(results, f"family {family_id}: minimumEvidence valid", item.get("minimumEvidence") in EXPECTED_EVIDENCE_LEVELS, str(item.get("minimumEvidence")))
        paths = item.get("paths") if isinstance(item.get("paths"), list) else []
        check(results, f"family {family_id}: paths present", bool(paths), str(paths))
        for rel in paths:
            rel_text = str(rel)
            root_relative_prefixes = (ASSISTANCE_DIR, ".github", ".hermes", ".project-local", "LICENSING", "THIRD_PARTY", "research/", "packages/", "integrations/", "vendor/", "docs/", "fixtures/")
            resolved_rel = rel_text if rel_text.startswith(root_relative_prefixes) else f"{ASSISTANCE_DIR}/{rel_text}"
            require_path(results, root, resolved_rel)

    entrypoints = require_object(results, "manifest.entrypoints", manifest.get("entrypoints"))
    for group in ["human", "machine", "verification"]:
        entries = entrypoints.get(group) if isinstance(entrypoints.get(group), list) else []
        check(results, f"entrypoints.{group} present", bool(entries), str(entries))
        for rel in entries:
            require_path(results, root, str(rel), file=True)

    safety = require_object(results, "manifest.safetyBoundaries", manifest.get("safetyBoundaries"))
    forbidden_roots = safety.get("forbiddenRoots") if isinstance(safety.get("forbiddenRoots"), list) else []
    authorization = safety.get("requiresExplicitAuthorization") if isinstance(safety.get("requiresExplicitAuthorization"), list) else []
    check(results, "safety forbids protected E drive", "E:/" in forbidden_roots, str(forbidden_roots))
    for action in ["commit", "push", "release"]:
        check(results, f"safety requires authorization for {action}", action in authorization, str(authorization))


def verify_capability_status(status: dict[str, Any], results: list[Result]) -> None:
    levels = status.get("evidenceLevels") if isinstance(status.get("evidenceLevels"), list) else []
    level_ids = [item.get("id") for item in levels if isinstance(item, dict)]
    check(results, "capability evidence levels exact", level_ids == EXPECTED_EVIDENCE_LEVELS, str(level_ids))
    check(results, "capability status states exact", status.get("states") == EXPECTED_STATES, str(status.get("states")))
    capability_states = status.get("capabilityStates")
    check(results, "capability state enum exact", capability_states == EXPECTED_CAPABILITY_STATES, str(capability_states))
    promotion_rules = status.get("promotionRules") if isinstance(status.get("promotionRules"), list) else []
    check(results, "promotion rules cover full ladder", len(promotion_rules) >= 5, str(len(promotion_rules)))
    rule_text = json.dumps(promotion_rules, ensure_ascii=False)
    for phrase in ["host/Agent runtime registration", "exact-SHA CI", "external acceptance"]:
        check(results, f"promotion rule mentions {phrase}", phrase.lower() in rule_text.lower(), rule_text[:500])
    hard_rules = "\n".join(str(item) for item in status.get("hardRules", []))
    for phrase in ["Static files", "runtime availability", "Commercially proven"]:
        check(results, f"hard rule guards {phrase}", phrase.lower() in hard_rules.lower(), hard_rules)


def _pyproject_project_version(root: Path) -> str | None:
    """The authoritative package version from the repo-root pyproject.toml.

    Version truth (taskpack 19 / FU-07): the manifest's product version is
    decided by the real package fact, i.e. the [project].version in
    pyproject.toml. The manifest must agree with it; a manifest that over-claims
    (e.g. 1.0.0 while the package is still 0.1.0-alpha.0) is exactly the drift
    this gate now catches, instead of hard-coding a 1.x assumption. Returns None
    when the authoritative source is missing, so the caller fails closed.
    """
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return None
    text = pyproject.read_text(encoding="utf-8")
    try:
        import tomllib
        data = tomllib.loads(text)
        version = data.get("project", {}).get("version")
        return str(version) if version else None
    except Exception:
        import re
        match = re.search(r'(?ms)^\[project\].*?^version\s*=\s*"([^"]+)"', text)
        return match.group(1) if match else None


def verify_v4_extensions(manifest: dict[str, Any], results: list[Result], root: Path) -> None:
    product = manifest.get("product") or {}
    neutrality = product.get("neutralityPolicy") or {}
    for key in ["modelNeutral", "styleNeutral", "domainNeutral", "platformNeutral", "versionNeutral"]:
        check(results, f"neutrality policy includes {key}", bool(neutrality.get(key)), str(neutrality.get(key)))
    rights = product.get("rightsPolicy") or {}
    check(results, "rights policy present", bool(rights.get("mode")), str(rights.get("mode")))
    # Version truth (taskpack 19 / FU-07): the manifest product version must
    # agree with the authoritative package version (pyproject.toml [project]).
    # A missing source or a mismatch is a FAIL — no hard-coded 1.x assumption.
    manifest_version = str(product.get("version", ""))
    authoritative = _pyproject_project_version(root)
    if authoritative is None:
        check(results, "authoritative package version resolvable", False,
              "pyproject.toml [project].version missing or unreadable")
    else:
        check(results, "manifest product.version equals pyproject [project].version",
              manifest_version == authoritative,
              f"manifest={manifest_version!r} pyproject={authoritative!r}")
    families = manifest.get("capabilityFamilies") if isinstance(manifest.get("capabilityFamilies"), list) else []
    for item in families:
        if not isinstance(item, dict):
            continue
        fid = str(item.get("id"))
        check(results, f"family {fid}: V4 domain present", bool(item.get("domain")), str(item.get("domain")))
        check(results, f"family {fid}: V4 owner present", bool(item.get("owner")), str(item.get("owner")))
        check(results, f"family {fid}: V4 license present", bool(item.get("license")), str(item.get("license")))
    entrypoints = manifest.get("entrypoints") or {}
    human = entrypoints.get("human") or []
    check(results, "V4 human entrypoint includes PRODUCT_DEFINITION", "docs/current/PRODUCT_DEFINITION.md" in human, str(human))


def verify_v3_docs(root: Path, results: list[Result]) -> None:
    project_definition = require_path(results, root, PROJECT_DEFINITION_REL, file=True)
    project_text = project_definition.read_text(encoding="utf-8") if project_definition.is_file() else ""
    check(results, "retired project definition points to PRODUCT_DEFINITION", "PRODUCT_DEFINITION.md" in project_text)
    for rel in [ARCHITECTURE_REL, "README.md", f"{ASSISTANCE_DIR}/README.md"]:
        path = require_path(results, root, rel, file=True)
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        for marker in V3_DOC_MARKERS:
            check(results, f"{rel} includes V3 marker {marker}", marker.lower() in text.lower())


def verify_json_contracts(root: Path, results: list[Result]) -> tuple[dict[str, Any], dict[str, Any]]:
    for rel in [MANIFEST_REL, CAPABILITY_STATUS_REL, PRODUCT_SCHEMA_REL, CAPABILITY_STATUS_SCHEMA_REL]:
        require_path(results, root, rel, file=True)
    parsed: dict[str, Any] = {}
    for rel in [MANIFEST_REL, CAPABILITY_STATUS_REL, PRODUCT_SCHEMA_REL, CAPABILITY_STATUS_SCHEMA_REL]:
        path = root / rel
        if not path.is_file():
            continue
        try:
            parsed[rel] = load_json(path)
            check(results, f"JSON parses: {rel}", True)
        except Exception as exc:  # noqa: BLE001
            check(results, f"JSON parses: {rel}", False, str(exc))
    manifest = require_object(results, "product manifest JSON", parsed.get(MANIFEST_REL))
    capability_status = require_object(results, "capability status JSON", parsed.get(CAPABILITY_STATUS_REL))
    product_schema = require_object(results, "product manifest schema JSON", parsed.get(PRODUCT_SCHEMA_REL))
    capability_schema = require_object(results, "capability status schema JSON", parsed.get(CAPABILITY_STATUS_SCHEMA_REL))
    check(results, "product manifest $schema points to schema file", manifest.get("$schema") == "../schemas/product-manifest.schema.json", str(manifest.get("$schema")))
    check(results, "capability status $schema points to schema file", capability_status.get("$schema") == "../schemas/capability-status.schema.json", str(capability_status.get("$schema")))
    check(results, "product schema title present", bool(product_schema.get("title")), str(product_schema.get("title")))
    check(results, "capability schema title present", bool(capability_schema.get("title")), str(capability_schema.get("title")))
    return manifest, capability_status


def print_results(results: list[Result]) -> int:
    failed = [result for result in results if not result.ok]
    for result in results:
        prefix = "PASS" if result.ok else "FAIL"
        print(f"{prefix} {result.label}")
        if result.detail:
            print(f"  {result.detail}")
    print(f"\nVERIFY_PRODUCT_MANIFEST_V3={'OK' if not failed else 'FAIL'} total={len(results)} failed={len(failed)}")
    return 0 if not failed else 1



ROOT_REL_PREFIXES = (
    ASSISTANCE_DIR,
    ".github",
    ".hermes",
    ".project-local",
    "LICENSING",
    "THIRD_PARTY",
    "research/",
    "packages/",
    "integrations/",
    "vendor/",
    "docs/",
    "fixtures/",
)
HISTORICAL_MARKERS = ("history", "historical", "reports/history", "docs/history")


def check_ref_safety(root: Path, results: list[Result], manifest: dict) -> None:
    """R0-002 / PR115-F07: manifest path references must be scanned against the
    REAL manifest structure (capabilityFamilies[].paths[]), must exist on disk,
    stay inside the repository, and never point at a historical-only tree.
    Uses the same Result/require_path machinery as the rest of the verifier so
    failures print and exit non-zero instead of crashing on str results."""
    scanned = 0
    families = manifest.get("capabilityFamilies") if isinstance(manifest.get("capabilityFamilies"), list) else []
    if not families:
        check(results, "R0-002: capabilityFamilies present", False, "no families to scan")
    for fam in families:
        if not isinstance(fam, dict):
            check(results, "R0-002: family is object", False, str(fam))
            continue
        family_id = str(fam.get("id", "?"))
        paths = fam.get("paths") if isinstance(fam.get("paths"), list) else []
        if not paths:
            check(results, f"R0-002 family {family_id}: paths present", False, "no referenced paths")
        for rel in paths:
            rel_text = str(rel)
            if not rel_text:
                check(results, f"R0-002 family {family_id}: non-empty ref", False, repr(rel))
                continue
            resolved_rel = rel_text if rel_text.startswith(ROOT_REL_PREFIXES) else f"{ASSISTANCE_DIR}/{rel_text}"
            # existence + containment + reparse hygiene via the shared gate
            require_path(results, root, resolved_rel)
            scanned += 1
            # traversal guard
            if any(part == ".." for part in Path(rel_text).parts):
                check(results, f"R0-002 family {family_id}: no traversal in {rel_text}", False, rel_text)
            else:
                check(results, f"R0-002 family {family_id}: no traversal in {rel_text}", True)
            # historical-only tree guard
            if any(marker in rel_text for marker in HISTORICAL_MARKERS):
                check(results, f"R0-002 family {family_id}: not historical {rel_text}", False, rel_text)
            else:
                check(results, f"R0-002 family {family_id}: not historical {rel_text}", True)
    entrypoints = manifest.get("entrypoints") if isinstance(manifest.get("entrypoints"), dict) else {}
    for group in ("human", "machine", "verification"):
        entries = entrypoints.get(group) if isinstance(entrypoints.get(group), list) else []
        for rel in entries:
            rel_text = str(rel)
            if not rel_text:
                continue
            require_path(results, root, rel_text, file=True)
            scanned += 1
    check(results, f"R0-002: refs scanned = {scanned}", scanned > 0, str(scanned))

def main() -> int:
    root = repo_root()
    results: list[Result] = []
    check_ref_safety(root, results, json.loads((root / MANIFEST_REL).read_text(encoding='utf-8')))
    manifest, capability_status = verify_json_contracts(root, results)
    verify_manifest_shape(root, manifest, results)
    verify_capability_status(capability_status, results)
    verify_v4_extensions(manifest, results, root)
    verify_v3_docs(root, results)
    return print_results(results)


if __name__ == "__main__":
    raise SystemExit(main())
