#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Scaffold a local Open Design plugin directory."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ASSISTANCE_DIR = "design-lab"
PLUGIN_SCHEMA = "https://open-design.ai/schemas/plugin.v1.json"
DEFAULT_PRODUCT_FAMILIES = ["brief-routing", "visual-quality", "domain-scenarios"]
DEFAULT_PRODUCTION_PROFILES = ["digital-ui"]


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / ASSISTANCE_DIR).is_dir() and (parent / ".git").exists():
            return parent
    raise SystemExit("Could not locate repository root")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise SystemExit("Plugin name must contain at least one ASCII letter or digit")
    return slug


def titleize(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def skill_md(name: str, title: str, description: str, categories: list[str], inputs: list[str]) -> str:
    trigger_lines = "\n".join(f"  - \"{item}\"" for item in [title, *categories[:4]])
    input_lines = "\n".join(f"- `{item}`: describe the {item}." for item in inputs)
    return f"""---
name: {name}
zh_name: \"{title}\"
description: \"{description}\"
triggers:
{trigger_lines}
---

# {title}

Use this skill inside Open Design when the user needs: {description}

## Inputs to collect

{input_lines or "- `brief`: short design brief."}

## Design rules

1. Start with the user's actual deliverable and audience.
2. Choose the closest local template before generating.
3. Produce concrete layout, style, component, and implementation constraints.
4. Avoid generic mood words without decisions.

## Local template references

```text
design-lab/templates/design-systems/style-reference-index.md
design-lab/templates/qa/anti-ai-slop-checklist.md
```

## Output contract

```text
1. Objective
2. Information/design structure
3. Visual/style direction
4. Component or artifact list
5. Implementation/production constraints
6. Open Design generation prompt
7. QA gates
```
"""


def manifest(name: str, title: str, description: str, categories: list[str], capabilities: list[str], inputs: list[str]) -> str:
    data = {
        "$schema": PLUGIN_SCHEMA,
        "specVersion": "1.0.0",
        "name": name,
        "title": title,
        "version": "0.1.0",
        "description": description,
        "author": {
            "name": "DTALEX66 DESIGN-LAB",
        },
        "license": "MIT",
        "entry": "SKILL.md",
        "publishedAt": "2026-08-04T00:00:00Z",
        "compat": {
            "agentSkills": [{"path": "./SKILL.md"}],
            "preservesV1Plugin": True,
            "upgradeTrack": "v3-compatibility",
            "runtimeRegistration": "pending-open-design-e3",
        },
        "od": {
            "kind": "skill",
            "mode": "compat-plugin",
            "taskKind": "new-generation",
            "categories": categories,
            "capabilities": capabilities,
            "suggestedInputs": inputs,
            "useCase": {
                "query": {
                    "en": description,
                    "zh-CN": description,
                },
            },
            "context": {
                "skills": [{"ref": name}],
                "schemas": [
                    "design-lab/schemas/design-brief.schema.json",
                    "design-lab/schemas/design-direction.schema.json",
                    "design-lab/schemas/design-critique.schema.json",
                ],
                "productFamilies": DEFAULT_PRODUCT_FAMILIES,
                "productionProfiles": DEFAULT_PRODUCTION_PROFILES,
            },
            "v3": {
                "productFamilies": DEFAULT_PRODUCT_FAMILIES,
                "productionProfiles": DEFAULT_PRODUCTION_PROFILES,
                "outputContracts": [
                    "design brief",
                    "Open Design generation prompt",
                    "quality gate checklist",
                ],
                "evidence": {
                    "level": "E1",
                    "state": "NOT_RUN",
                    "claim": "Scaffolded V3 compatibility manifest; run repository verifiers before promoting beyond structural evidence.",
                    "verifiedBy": [],
                },
                "runtime": {
                    "status": "pending-e3",
                    "requires": [
                        "Open Design runtime registration",
                        "runtime ID/version read-back",
                        "minimal task execution",
                        "artifact and provenance read-back",
                    ],
                },
            },
        },
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def readme(name: str, title: str, description: str) -> str:
    return f"""# {title}

Open Design plugin/skill scaffolded as `{name}`.

## Purpose

{description}

## Files

```text
SKILL.md
open-design.json
README.md
```

Run after editing:

```bash
python integrations/hosts/open-design/verifier/verify_open_design_host_adapter.py
python integrations/hosts/open-design/verifier/generate_open_design_adapter_indexes.py
```
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scaffold a local Open Design plugin")
    parser.add_argument("name", help="Plugin name, e.g. brand-pack-director")
    parser.add_argument("--title", help="Human title; defaults to title-cased name")
    parser.add_argument("--description", default="Open Design local skill plugin.")
    parser.add_argument("--categories", default="design,open-design")
    parser.add_argument("--capabilities", default="prompt:inject,artifact:html,design-system:reference")
    parser.add_argument("--inputs", default="brief,audience,style")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing plugin directory")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = repo_root()
    name = slugify(args.name)
    title = args.title or titleize(name)
    categories = parse_csv(args.categories)
    capabilities = parse_csv(args.capabilities)
    inputs = parse_csv(args.inputs)
    if "prompt:inject" not in capabilities:
        capabilities.insert(0, "prompt:inject")

    plugin_dir = root / ASSISTANCE_DIR / "plugins" / name
    if plugin_dir.exists() and not args.force:
        raise SystemExit(f"Plugin already exists: {plugin_dir}. Use --force to overwrite.")
    plugin_dir.mkdir(parents=True, exist_ok=True)

    (plugin_dir / "SKILL.md").write_text(skill_md(name, title, args.description, categories, inputs), encoding="utf-8")
    (plugin_dir / "open-design.json").write_text(manifest(name, title, args.description, categories, capabilities, inputs), encoding="utf-8")
    (plugin_dir / "README.md").write_text(readme(name, title, args.description), encoding="utf-8")

    print(f"created {plugin_dir.relative_to(root).as_posix()}")
    print("next: edit SKILL.md, then run verify_open_design_host_adapter.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
