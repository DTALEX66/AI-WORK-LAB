#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-ADP-OD-003: verify the Open Design Host Adapter layer.

Focused repository validator for the Open Design host adapter
(integrations/hosts/open-design/): plugin projections, template
references, design-system manifests, export fixtures, indexes, script
compileability (in-memory), asset counts and secondary verifiers.
Standard library only. The stale minigame visual-pack fixture check was
removed (minigame assets/generated deleted in 1382e2c; the boundary is
enforced by test_minigame_visual_fixture_boundary).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PLUGIN_SCHEMA = "https://open-design.ai/schemas/plugin.v1.json"
ASSISTANCE_DIR = "design-lab"
PRODUCT_MANIFEST_REL = f"{ASSISTANCE_DIR}/config/product-manifest.json"
EVIDENCE_LEVELS = {"E0", "E1", "E2", "E3", "E4", "E5"}
EVIDENCE_STATES = {"NOT_RUN", "PASS", "FAIL", "BLOCKED", "UNVERIFIED", "SKIPPED_OPTIONAL"}
LEGACY_PLUGIN_NAMES = {
    "anomaly-monitor-hud",
    "brand-visual-director",
    "design-qa-critic",
    "graphic-design-director",
    "minigame-ui-director",
    "spatial-exhibition-director",
    "uiux-layout-director",
}


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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> object:
    return json.loads(read_text(path))


def check(results: list[Result], label: str, ok: bool, detail: str = "") -> None:
    results.append(Result(label, ok, detail))


def contained_path(base: Path, relative: object, extra_bases: tuple[Path, ...] = ()) -> Path | None:
    """Resolve a manifest path only inside an explicit set of allowed trees."""
    if not isinstance(relative, str) or not relative:
        return None
    candidate = (base / relative).resolve()
    for allowed_base in (base, *extra_bases):
        try:
            candidate.relative_to(allowed_base.resolve())
            return candidate
        except ValueError:
            continue
    return None


def require_file(results: list[Result], root: Path, rel: str, min_bytes: int = 1) -> Path:
    path = root / rel
    check(results, f"exists: {rel}", path.is_file())
    size = path.stat().st_size if path.exists() else 0
    check(results, f"non-empty: {rel}", size >= min_bytes, str(size))
    return path


def iter_plugin_dirs(root: Path) -> Iterable[Path]:
    plugins_dir = root / ASSISTANCE_DIR / ".." / "packages" / "capabilities" / "plugins"
    return sorted(path for path in plugins_dir.iterdir() if path.is_dir())


def verify_plugin_manifests(root: Path, results: list[Result]) -> None:
    plugins = list(iter_plugin_dirs(root))
    check(results, "at least one Open Design plugin exists", bool(plugins), str(len(plugins)))
    product_families: set[str] = set()
    product_manifest_path = root / PRODUCT_MANIFEST_REL
    if product_manifest_path.is_file():
        try:
            product_manifest = load_json(product_manifest_path)
            if isinstance(product_manifest, dict):
                product_families = {
                    str(item.get("id"))
                    for item in product_manifest.get("capabilityFamilies", [])
                    if isinstance(item, dict) and item.get("id")
                }
        except Exception as exc:  # noqa: BLE001 - reported by JSON checks too.
            check(results, "product manifest loads for plugin family checks", False, str(exc))

    for plugin_dir in plugins:
        name = plugin_dir.name
        manifest_path = plugin_dir / "open-design.json"
        skill_path = plugin_dir / "SKILL.md"
        readme_path = plugin_dir / "README.md"

        check(results, f"plugin {name}: open-design.json exists", manifest_path.is_file())
        check(results, f"plugin {name}: SKILL.md exists", skill_path.is_file())
        check(results, f"plugin {name}: README.md exists", readme_path.is_file())
        if not manifest_path.is_file():
            continue

        try:
            manifest = load_json(manifest_path)
            check(results, f"plugin {name}: manifest JSON parses", isinstance(manifest, dict))
        except Exception as exc:  # noqa: BLE001 - verifier reports any parse issue.
            check(results, f"plugin {name}: manifest JSON parses", False, str(exc))
            continue

        od = manifest.get("od") if isinstance(manifest, dict) else None
        od = od if isinstance(od, dict) else {}
        capabilities = od.get("capabilities") or []
        categories = od.get("categories") or []
        suggested_inputs = od.get("suggestedInputs") or []
        compat = manifest.get("compat") if isinstance(manifest.get("compat"), dict) else {}
        agent_skills = compat.get("agentSkills") if isinstance(compat.get("agentSkills"), list) else []
        v3 = od.get("v3") if isinstance(od.get("v3"), dict) else {}
        evidence = v3.get("evidence") if isinstance(v3.get("evidence"), dict) else {}
        runtime = v3.get("runtime") if isinstance(v3.get("runtime"), dict) else {}
        v3_families = v3.get("productFamilies") if isinstance(v3.get("productFamilies"), list) else []

        check(results, f"plugin {name}: schema", manifest.get("$schema") == PLUGIN_SCHEMA, str(manifest.get("$schema")))
        check(results, f"plugin {name}: specVersion", manifest.get("specVersion") == "1.0.0", str(manifest.get("specVersion")))
        check(results, f"plugin {name}: name matches directory", manifest.get("name") == name, str(manifest.get("name")))
        check(results, f"plugin {name}: version present", bool(manifest.get("version")), str(manifest.get("version")))
        check(results, f"plugin {name}: entry is SKILL.md", manifest.get("entry") == "SKILL.md", str(manifest.get("entry")))
        check(results, f"plugin {name}: od.kind is skill", od.get("kind") == "skill", str(od.get("kind")))
        check(results, f"plugin {name}: prompt injection capability", "prompt:inject" in capabilities, str(capabilities))
        check(results, f"plugin {name}: categories present", bool(categories), str(categories))
        check(results, f"plugin {name}: suggested inputs present", bool(suggested_inputs), str(suggested_inputs))
        check(results, f"plugin {name}: compat agent skill present", bool(agent_skills), str(agent_skills))
        for item in agent_skills:
            rel = item.get("path") if isinstance(item, dict) else None
            check(results, f"plugin {name}: compat agent skill path shape", isinstance(rel, str) and rel.endswith(".md"), str(item))
            if isinstance(rel, str):
                resolved = contained_path(plugin_dir, rel)
                check(results, f"plugin {name}: compat agent skill path stays inside plugin", resolved is not None, rel)
                check(results, f"plugin {name}: compat agent skill path exists", resolved is not None and resolved.is_file(), rel)
        check(results, f"plugin {name}: v3 mode", od.get("mode") == "compat-plugin", str(od.get("mode")))
        check(results, f"plugin {name}: v3 product families present", bool(v3_families), str(v3_families))
        unknown_families = sorted(set(str(item) for item in v3_families) - product_families)
        check(results, f"plugin {name}: v3 product families known", not unknown_families, str(unknown_families))
        check(results, f"plugin {name}: v3 evidence level valid", evidence.get("level") in EVIDENCE_LEVELS, str(evidence))
        check(results, f"plugin {name}: v3 evidence state valid", evidence.get("state") in EVIDENCE_STATES, str(evidence))
        check(results, f"plugin {name}: v3 runtime pending E3", runtime.get("status") == "pending-e3", str(runtime))
        check(results, f"plugin {name}: v3 runtime requires provenance", "artifact and provenance read-back" in (runtime.get("requires") or []), str(runtime.get("requires")))
        if name in LEGACY_PLUGIN_NAMES:
            check(results, f"legacy plugin {name}: preserves v1", compat.get("preservesV1Plugin") is True, str(compat))
            check(results, f"legacy plugin {name}: upgraded evidence is E2", evidence.get("level") == "E2", str(evidence))
            check(results, f"legacy plugin {name}: upgraded evidence passed", evidence.get("state") == "PASS", str(evidence))
            verified_by = evidence.get("verifiedBy") if isinstance(evidence.get("verifiedBy"), list) else []
            check(results, f"legacy plugin {name}: verifier evidence recorded", "integrations/hosts/open-design/verifier/verify_open_design_host_adapter.py" in verified_by, str(verified_by))


def referenced_local_paths(text: str) -> set[str]:
    pattern = re.compile(r"design-lab/[A-Za-z0-9_./-]+\.(?:md|json|html|py)")
    return set(pattern.findall(text))


def verify_skill_references(root: Path, results: list[Result]) -> None:
    for plugin_dir in iter_plugin_dirs(root):
        skill_path = plugin_dir / "SKILL.md"
        if not skill_path.is_file():
            continue
        rel_skill = skill_path.relative_to(root).as_posix()
        for rel_ref in sorted(referenced_local_paths(read_text(skill_path))):
            resolved = contained_path(root, rel_ref)
            check(results, f"{rel_skill} reference stays inside repository: {rel_ref}", resolved is not None)
            check(results, f"{rel_skill} reference exists: {rel_ref}", resolved is not None and resolved.is_file())


def verify_templates(root: Path, results: list[Result]) -> None:
    templates_dir = root / ASSISTANCE_DIR / "templates"
    template_files = sorted(templates_dir.rglob("*.md"))
    check(results, "template library has markdown files", bool(template_files), str(len(template_files)))

    required_terms = {
        "templates/qa/anti-ai-slop-checklist.md": ["Hard fails", "Scorecard", "Reject below"],
        "templates/layouts/landing-page.md": ["Required structure", "hero", "CTA"],
        "templates/layouts/dashboard.md": ["Information architecture", "card soup"],
        "templates/layouts/mobile-menu.md": ["bottom tabs", "danger"],
        "templates/layouts/settings-panel.md": ["danger zone", "unsaved changes"],
        "templates/layouts/pricing-page.md": ["recommended plan", "feature comparison"],
        "templates/layouts/product-page.md": ["product surface", "feature proof"],
        "templates/graphic/poster-cover.md": ["composition", "xiaohongshu"],
        "templates/graphic/social-card.md": ["thumbnail-readable", "safe margins"],
        "templates/decks/pitch-deck.md": ["Six-slide bootstrap", "claim-based"],
        "templates/motion/motion-system.md": ["Motion tokens", "reduced-motion"],
        "templates/typography/cjk-ui-typography.md": ["PingFang SC", "Microsoft YaHei"],
        "templates/design-systems/style-reference-index.md": ["Stripe", "Linear", "Nothing"],
        "templates/brand/brand-identity-system.md": ["品牌", "Visual territory"],
        "templates/spatial/culture-wall.md": ["文化墙", "viewing distance"],
        "templates/spatial/exhibition-hall.md": ["展厅", "Visitor journey"],
        "templates/visual/art-direction.md": ["Visual design", "Three art directions"],
        "templates/visual/2d-design.md": ["2D design", "Export specs"],
        "templates/visual/3d-design.md": ["3D design", "scale references"],
    }

    for rel_suffix, terms in required_terms.items():
        rel = f"{ASSISTANCE_DIR}/{rel_suffix}"
        path = require_file(results, root, rel, min_bytes=500)
        text = read_text(path) if path.is_file() else ""
        text_lower = text.lower()
        for term in terms:
            check(results, f"{rel} includes {term}", term.lower() in text_lower)

    large = [str(path.relative_to(root)) for path in template_files if path.stat().st_size > 100_000]
    check(results, "template library has no large vendored files", not large, str(large))


def verify_design_systems(root: Path, results: list[Result]) -> None:
    base = root / ASSISTANCE_DIR / "design-systems" / "anomaly-monitor-dark"
    if not base.exists():
        check(results, "anomaly-monitor-dark design system exists", False)
        return

    manifest_path = base / "manifest.json"
    require_file(results, root, str(manifest_path.relative_to(root)))
    try:
        manifest = load_json(manifest_path)
        check(results, "anomaly-monitor-dark manifest parses", isinstance(manifest, dict))
    except Exception as exc:  # noqa: BLE001
        check(results, "anomaly-monitor-dark manifest parses", False, str(exc))
        return

    files = manifest.get("files", [])
    if isinstance(files, dict):
        file_refs = files.values()
    else:
        file_refs = files
    for rel in file_refs:
        resolved = contained_path(base, rel)
        check(results, f"design system file stays inside system: {rel}", resolved is not None)
        check(results, f"design system file exists: {rel}", resolved is not None and resolved.is_file())

    for rel in ["design-tokens.json", "components.manifest.json"]:
        try:
            load_json(base / rel)
            check(results, f"design system JSON parses: {rel}", True)
        except Exception as exc:  # noqa: BLE001
            check(results, f"design system JSON parses: {rel}", False, str(exc))


def png_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def verify_exports(root: Path, results: list[Result]) -> None:
    export = root / "fixtures" / "domains" / "game-visual" / "exports" / "minigame-mobile-controls"
    require_file(results, root, str((export / "README.md").relative_to(root)), min_bytes=500)
    html = require_file(results, root, str((export / "index.html").relative_to(root)), min_bytes=20_000)
    require_file(results, root, str((export / "implementation-handoff.md").relative_to(root)), min_bytes=300)
    require_file(results, root, str((export / "critique.json").relative_to(root)), min_bytes=300)
    require_file(results, root, str((export / "index.html.artifact.json").relative_to(root)), min_bytes=100)
    require_file(results, root, str((export / ".open-design" / "project.json").relative_to(root)), min_bytes=100)

    html_text = read_text(html) if html.is_file() else ""
    check(results, "minigame export uses local asset paths", "../../MINIGAME" not in html_text)
    expected_assets = [
        "cctv-elevator-corridor-clear.png",
        "cctv-elevator-corridor-warp.png",
        "cctv-elevator-corridor-figure.png",
    ]
    for name in expected_assets:
        rel = f"fixtures/domains/game-visual/exports/minigame-mobile-controls/assets/{name}"
        asset = require_file(results, root, rel, min_bytes=500_000)
        check(results, f"minigame export html references {name}", f"assets/{name}" in html_text)
        size = png_size(asset) if asset.is_file() else None
        check(results, f"minigame export PNG dimensions readable: {name}", bool(size), str(size))


def verify_json_files(root: Path, results: list[Result]) -> None:
    errors: list[str] = []
    for path in (root / ASSISTANCE_DIR).rglob("*.json"):
        try:
            load_json(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.relative_to(root)}: {exc}")
    check(results, "all design-lab JSON files parse", not errors, "\n".join(errors))


def verify_indexes(root: Path, results: list[Result]) -> None:
    plugins_index = root / ASSISTANCE_DIR / ".." / "packages" / "capabilities" / "plugins" / "INDEX.md"
    templates_index = root / ASSISTANCE_DIR / "templates" / "INDEX.md"
    require_file(results, root, str(plugins_index.relative_to(root)), min_bytes=500)
    require_file(results, root, str(templates_index.relative_to(root)), min_bytes=500)

    plugins_text = read_text(plugins_index) if plugins_index.is_file() else ""
    for plugin_dir in iter_plugin_dirs(root):
        if (plugin_dir / "open-design.json").is_file():
            check(results, f"plugins index mentions {plugin_dir.name}", plugin_dir.name in plugins_text)

    templates_text = read_text(templates_index) if templates_index.is_file() else ""
    required_sections = [
        "Brand / 品牌",
        "Graphic / 平面",
        "Layouts / UIUX",
        "Spatial / 文化墙展厅",
        "Visual / 2D/3D",
        "QA / 审查",
    ]
    for section in required_sections:
        check(results, f"templates index has section {section}", section in templates_text)


def verify_scripts(root: Path, results: list[Result]) -> None:
    scripts = [
        "integrations/hosts/open-design/verifier/verify_open_design_host_adapter.py",
        "design-lab/scripts/verify_product_manifest_v3.py",
        "design-lab/scripts/verify_runtime_contracts_v3.py",
        "design-lab/scripts/verify_visual_scoring_v3.py",
        "design-lab/scripts/verify_source_registry.py",
        "design-lab/scripts/verify_v2_protocols.py",
        "design-lab/scripts/verify_visual_quality_v21.py",
        "integrations/hosts/open-design/verifier/generate_open_design_adapter_indexes.py",
        "design-lab/scripts/scaffold_open_design_plugin.py",
        "design-lab/scripts/score_visual_quality.py",
        "design-lab/scripts/score_design_critique.py",
        "design-lab/scripts/compare_visual_iterations.py",
    ]
    for rel in scripts:
        path = require_file(results, root, rel, min_bytes=500)
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
            check(results, f"script compiles: {rel}", True)
        except Exception as exc:  # noqa: BLE001
            check(results, f"script compiles: {rel}", False, str(exc))


def verify_asset_counts(root: Path, results: list[Result]) -> None:
    """V42-0106: asset-counts.json must match real directory scans and registries.

    Hand-maintained counts in entrypoint-convergence.json must agree with the
    auto-generated single source of truth; otherwise the counts have drifted.
    """
    counts_path = root / ASSISTANCE_DIR / "config" / "asset-counts.json"
    if not counts_path.is_file():
        check(results, "asset-counts.json exists (run generate_open_design_adapter_indexes.py)", False)
        return
    try:
        counts = load_json(counts_path)
    except Exception as exc:  # noqa: BLE001
        check(results, "asset-counts.json parses", False, str(exc))
        return
    if not isinstance(counts, dict):
        check(results, "asset-counts.json is an object", False)
        return

    # After DL-DIR-MIG-R1 the capability catalogs (plugins/bundles/atoms/scenarios)
    # live under packages/capabilities/, while domain-packs and evals stay under
    # design-lab/ (ASSISTANCE_DIR).  Capability catalogs carry open-design.json
    # manifests; domain-packs carry manifest.json.
    CATALOG_KINDS = {"plugins", "bundles", "atoms", "scenarios"}

    def dir_count(rel_dir: str, manifest_name: str = "open-design.json") -> int:
        target = (
            root / "packages" / "capabilities" / rel_dir
            if rel_dir in CATALOG_KINDS
            else root / ASSISTANCE_DIR / rel_dir
        )
        if not target.is_dir():
            return 0
        return sum(1 for p in target.iterdir() if p.is_dir() and (p / manifest_name).is_file())

    def json_file_count(rel_dir: str) -> int:
        target = root / ASSISTANCE_DIR / rel_dir
        if not target.is_dir():
            return 0
        return len([p for p in target.iterdir() if p.is_file() and p.suffix == ".json"])

    expected = {
        "plugins": dir_count("plugins"),
        "bundles": dir_count("bundles"),
        "domain_packs": dir_count("domain-packs", manifest_name="manifest.json"),
        "atoms": dir_count("atoms"),
        "scenarios": dir_count("scenarios"),
        "rubrics": json_file_count("evals/rubrics"),
    }
    for key, real in expected.items():
        declared = counts.get(key)
        check(
            results,
            f"asset-count {key} matches directory scan",
            declared == real,
            f"declared={declared} real={real}",
        )

    # entrypoint-convergence counts must agree with the generated index.
    convergence_path = root / ASSISTANCE_DIR / "config" / "entrypoint-convergence.json"
    if convergence_path.is_file():
        try:
            convergence = load_json(convergence_path)
            conv_counts = convergence.get("counts") if isinstance(convergence, dict) else None
            if isinstance(conv_counts, dict):
                pairs = [
                    ("public_bundles", counts.get("bundles")),
                    ("internal_atoms", counts.get("atoms")),
                    ("compatibility_plugins", counts.get("plugins")),
                ]
                for field, expected_value in pairs:
                    declared_conv = conv_counts.get(field)
                    check(
                        results,
                        f"entrypoint-convergence {field} matches asset-counts",
                        declared_conv == expected_value,
                        f"declared={declared_conv} generated={expected_value}",
                    )
        except Exception as exc:  # noqa: BLE001
            check(results, "entrypoint-convergence parses for count check", False, str(exc))


def verify_secondary_verifiers(root: Path, results: list[Result]) -> None:
    verifiers = [
        "design-lab/scripts/verify_product_manifest_v3.py",
        "design-lab/scripts/verify_runtime_contracts_v3.py",
        "design-lab/scripts/verify_visual_scoring_v3.py",
        "design-lab/scripts/verify_source_registry.py",
        "design-lab/scripts/verify_v2_protocols.py",
        "design-lab/scripts/verify_visual_quality_v21.py",
        "design-lab/scripts/verify_capability_evidence_v4.py",
        "design-lab/scripts/verify_license_coverage.py",
    ]
    for rel in verifiers:
        path = root / rel
        if not path.is_file():
            check(results, f"secondary verifier exists: {rel}", False)
            continue
        completed = subprocess.run(
            [sys.executable, str(path)],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            check=False,
        )
        summary = "\n".join(completed.stdout.strip().splitlines()[-8:])
        check(results, f"secondary verifier passes: {rel}", completed.returncode == 0, summary)


def verify_docs(root: Path, results: list[Result]) -> None:
    required_refs = [
        "docs/PRODUCT_DEFINITION.md",
        "docs/ARCHITECTURE.md",
        "docs/BOUNDARY_CONTRACT.md",
        "docs/NEUTRALITY_POLICY.md",
        "docs/EVIDENCE_POLICY.md",
        "docs/ADAPTER_POLICY.md",
        "docs/OBJECT_MODEL.md",
        "docs/USER_MODES.md",
        "docs/ROADMAP.md",
        "design-lab/config/product-manifest.json",
        "design-lab/config/capability-status.json",
        "design-lab/scripts/verify_design_lab.py",
        "design-lab/scripts/verify_identity_gate.py",
        "design-lab/scripts/verify_product_manifest_v3.py",
        "design-lab/scripts/verify_runtime_contracts_v3.py",
        "design-lab/scripts/verify_visual_scoring_v3.py",
        "design-lab/scripts/verify_source_registry.py",
    ]
    root_readme = root / "README.md"
    assistance_readme = root / ASSISTANCE_DIR / "README.md"
    texts = {
        "README.md": read_text(root_readme) if root_readme.exists() else "",
        f"{ASSISTANCE_DIR}/README.md": read_text(assistance_readme) if assistance_readme.exists() else "",
    }
    for rel in required_refs:
        present = any(rel in text for text in texts.values())
        check(results, f"docs mention {rel}", present)


def print_results(results: list[Result]) -> int:
    failed = [result for result in results if not result.ok]
    for result in results:
        prefix = "PASS" if result.ok else "FAIL"
        print(f"{prefix} {result.label}")
        if result.detail:
            print(f"  {result.detail}")
    print(f"\nVERIFY_RESULT={'OK' if not failed else 'FAIL'} total={len(results)} failed={len(failed)}")
    return 0 if not failed else 1


def main() -> int:
    root = repo_root()
    results: list[Result] = []
    verify_plugin_manifests(root, results)
    verify_skill_references(root, results)
    verify_templates(root, results)
    verify_design_systems(root, results)
    verify_exports(root, results)
    verify_json_files(root, results)
    verify_indexes(root, results)
    verify_scripts(root, results)
    verify_asset_counts(root, results)
    verify_secondary_verifiers(root, results)
    verify_docs(root, results)
    return print_results(results)


if __name__ == "__main__":
    raise SystemExit(main())
