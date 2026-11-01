#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate Open Design assistance index files."""

from __future__ import annotations

import json
from pathlib import Path

ASSISTANCE_DIR = "design-lab"

CATEGORY_LABELS = {
    "brand": "Brand / 品牌",
    "decks": "Decks / 演示",
    "design-systems": "Design Systems / 风格参考",
    "graphic": "Graphic / 平面",
    "layouts": "Layouts / UIUX",
    "motion": "Motion / 动效",
    "qa": "QA / 审查",
    "spatial": "Spatial / 文化墙展厅",
    "typography": "Typography / 排版",
    "visual": "Visual / 2D/3D",
    "config": "Config / 配置",
}


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / ASSISTANCE_DIR).is_dir() and (parent / ".git").exists():
            return parent
    raise SystemExit("Could not locate repository root")


def first_heading(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ").title()


def first_paragraph(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    heading_seen = False
    collected: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            heading_seen = True
            continue
        if not heading_seen:
            continue
        if not stripped:
            if collected:
                break
            continue
        if stripped.startswith("## "):
            break
        collected.append(stripped)
    return " ".join(collected)[:220]


def plugin_row(plugin_dir: Path, root: Path) -> str:
    manifest = json.loads((plugin_dir / "open-design.json").read_text(encoding="utf-8"))
    od = manifest.get("od") or {}
    name = manifest.get("name", plugin_dir.name)
    title = manifest.get("title", name)
    categories = ", ".join(od.get("categories") or [])
    capabilities = ", ".join(od.get("capabilities") or [])
    inputs = ", ".join(od.get("suggestedInputs") or [])
    rel = f"{plugin_dir.name}/README.md"
    return f"| [`{name}`]({rel}) | {title} | {categories} | {capabilities} | {inputs} |"


def generate_plugins_index(root: Path) -> None:
    plugins_dir = root / "packages" / "capabilities" / "plugins"
    rows = [plugin_row(path, root) for path in sorted(plugins_dir.iterdir()) if (path / "open-design.json").is_file()]
    content = "\n".join([
        "# Open Design plugin index",
        "",
        "Generated from `packages/capabilities/plugins/*/open-design.json`.",
        "",
        "Run:",
        "",
        "```bash",
        "python design-lab/scripts/generate_open_design_indexes.py",
        "```",
        "",
        "| Plugin | Title | Categories | Capabilities | Suggested inputs |",
        "|---|---|---|---|---|",
        *rows,
        "",
    ])
    (plugins_dir / "INDEX.md").write_text(content, encoding="utf-8")


def generate_templates_index(root: Path) -> None:
    templates_dir = root / ASSISTANCE_DIR / "templates"
    sections: dict[str, list[str]] = {}
    for path in sorted(templates_dir.rglob("*.md")):
        if path.name == "INDEX.md":
            continue
        parts = path.relative_to(templates_dir).parts
        category = parts[0] if len(parts) > 1 else "config"
        label = CATEGORY_LABELS.get(category, category.title())
        rel = path.relative_to(root).as_posix()
        title = first_heading(path)
        desc = first_paragraph(path)
        sections.setdefault(label, []).append(f"- [`{title}`]({rel}) — {desc}")

    lines = [
        "# Open Design template index",
        "",
        "Generated from `design-lab/templates/**/*.md`.",
        "",
        "Use this as the quick map for choosing local Open Design capability templates.",
        "",
    ]
    for label in sorted(sections):
        lines.extend([f"## {label}", "", *sections[label], ""])
    (templates_dir / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")


def generate_capability_index(root: Path) -> Path:
    """Generate capability index from product-manifest capabilityFamilies (SSOT)."""
    manifest = json.loads((root / ASSISTANCE_DIR / "config" / "product-manifest.json").read_text(encoding="utf-8"))
    families = manifest.get("capabilityFamilies") or []
    out = root / ASSISTANCE_DIR / "config" / "CAPABILITY_INDEX.md"
    rows = []
    for f in families:
        name = f.get("id", "")
        title = f.get("title", "")
        level = f.get("minimumEvidence", "")
        domain = f.get("domain", "")
        owner = f.get("owner", "")
        paths = ", ".join(f.get("paths") or [])
        rows.append(f"| `{name}` | {title} | {level} | {domain} | {owner} | `{paths}` |")
    content = "\n".join([
        "# Capability index",
        "",
        "Generated from `design-lab/config/product-manifest.json` (single source of truth).",
        "",
        "> Actual per-capability evidence level (E0-E5, bound to tree SHA) lives in",
        "> `design-lab/config/capability-evidence-index.json`, validated by",
        "> `design-lab/scripts/verify_capability_evidence_v4.py`.",
        "",
        "| Capability | Title | Min evidence | Domain | Owner | Paths |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
    ])
    out.write_text(content, encoding="utf-8")
    return out


def _dir_count(root: Path, rel_dir: str, manifest_name: str = "open-design.json") -> int:
    # After DL-DIR-MIG-R1 capability catalogs (plugins/bundles/atoms/scenarios)
    # live under packages/capabilities/; host/expert-suite trees under
    # integrations/hosts/; domain-packs/evals stay under design-lab.
    catalog_kinds = {"plugins", "bundles", "atoms", "scenarios"}
    if rel_dir.startswith("adapters/") or rel_dir.startswith("hosts/"):
        target = root / "integrations" / rel_dir
    else:
        target = (
            root / "packages" / "capabilities" / rel_dir
            if rel_dir in catalog_kinds
            else root / ASSISTANCE_DIR / rel_dir
        )
    if not target.is_dir():
        return 0
    return sum(1 for p in target.iterdir() if p.is_dir() and (p / manifest_name).is_file())


def _json_file_count(root: Path, rel_dir: str) -> int:
    target = root / ASSISTANCE_DIR / rel_dir
    if not target.is_dir():
        return 0
    return len([p for p in target.iterdir() if p.is_file() and p.suffix == ".json"])


def _managed_design_system_count(root: Path) -> int:
    """Count Open-Design-managed design systems (those whose manifest declares
    a DESIGN-LAB source lineage).  Local project-only systems (e.g. nebula-tech)
    are not part of the Open Design expert-suite surface."""
    base = root / ASSISTANCE_DIR / "design-systems"
    if not base.is_dir():
        return 0
    count = 0
    for p in base.iterdir():
        if not p.is_dir():
            continue
        manifest = p / "manifest.json"
        if not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("source", "").startswith("DESIGN-LAB/"):
            count += 1
    return count


def generate_asset_counts(root: Path) -> Path:
    """Generate the single authoritative asset-count index (V42-0106).

    Counts come from real directory scans and registry JSON files, never from
    prose. This is the replacement for hand-maintained plugin/bundle/domain-pack
    counts scattered across README/START_HERE/entrypoint-convergence.
    """
    out = root / ASSISTANCE_DIR / "config" / "asset-counts.json"

    def load_json(rel: str) -> dict:
        p = root / rel
        if not p.is_file():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    sources = load_json(f"{ASSISTANCE_DIR}/research/global-absorption/SOURCE_REGISTRY.json")
    quarantined = load_json(f"{ASSISTANCE_DIR}/research/global-absorption/QUARANTINE_REGISTRY.json")
    visual = load_json(f"{ASSISTANCE_DIR}/research/visual-quality/SOURCE_REGISTRY_VISUAL_V21.json")
    masters = load_json(f"{ASSISTANCE_DIR}/research/master-studies/MASTER_REGISTRY.json")
    methods = load_json(f"{ASSISTANCE_DIR}/research/master-studies/ANCHOR_METHOD_CARDS.json")
    evidence = load_json(f"{ASSISTANCE_DIR}/evals/evidence/evidence-cards.json")

    counts = {
        "schemaVersion": "design-lab/asset-counts/v1",
        "task": "V42-0106",
        "generated_at": None,  # filled below
        "source": "generated by integrations/hosts/open-design/verifier/generate_open_design_adapter_indexes.py from directory scans and registry JSONs",
        "plugins": _dir_count(root, "plugins"),
        "bundles": _dir_count(root, "bundles"),
        "personal_skills": _dir_count(
            root, "hosts/open-design/expert-suite/skills", manifest_name="SKILL.md"
        ),
        "design_systems": _managed_design_system_count(root),
        "domain_packs": _dir_count(root, "domain-packs", manifest_name="manifest.json"),
        "atoms": _dir_count(root, "atoms"),
        "scenarios": _dir_count(root, "scenarios"),
        "profiles": _dir_count(root, "profiles"),
        "rubrics": _json_file_count(root, "evals/rubrics"),
        "schemas": len(list((root / ASSISTANCE_DIR / "schemas").rglob("*.json"))),
        "templates": len(list((root / ASSISTANCE_DIR / "templates").rglob("*.md"))),
        "generic_sources": len(sources.get("entries") or []),
        "quarantined_sources": len(quarantined.get("entries") or []),
        "visual_sources": len(visual.get("entries") or []),
        "master_records": len(masters.get("masters") or masters.get("records") or []),
        "method_cards": len(methods.get("cards") or []),
        "evidence_cards": len(evidence.get("cards") or []),
    }
    counts["generated_at"] = __import__("datetime").datetime.now().strftime("%Y-%m-%d")  # date-only: deterministic
    out.write_text(json.dumps(counts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def main() -> int:
    root = repo_root()
    generate_plugins_index(root)
    generate_templates_index(root)
    cap = generate_capability_index(root)
    counts = generate_asset_counts(root)
    print("generated packages/capabilities/plugins/INDEX.md")
    print("generated design-lab/templates/INDEX.md")
    print(f"generated {cap.relative_to(root).as_posix()}")
    print(f"generated {counts.relative_to(root).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
