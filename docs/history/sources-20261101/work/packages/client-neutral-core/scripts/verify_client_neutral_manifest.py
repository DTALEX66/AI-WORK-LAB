#!/usr/bin/env python
"""Validate and list the client-neutral Workflow-assistance manifest.

This verifier is deliberately independent of Hermes, Codex, provider SDKs, and
user runtime state. It reads one project-local YAML manifest and emits a safe
adapter inventory. It never detects executables, reads auth stores, or writes
files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


EXPECTED_INTERFACE = [
    "detect",
    "capabilities",
    "plan",
    "apply",
    "invoke",
    "observe",
    "rollback",
]
EXPECTED_ADAPTERS = {
    "hermes": "deep",
    "codex": "deep",
    "cc-switch": "deep",
    "github": "deep",
    "openhuman": "experimental",
    "open-design": "experimental",

    "cursor": "manifest-only",
    "claude-code": "manifest-only",
    "workbuddy": "manifest-only",
}
FIRST_CLASS_ADAPTERS = [
    "hermes",
    "codex",
    "cc-switch",
    "github",
    "openhuman",
    "open-design",
]
HERMES_ADAPTER_REQUIREMENT = "capability-discovery"


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def load_and_validate(path: Path) -> dict[str, Any]:
    """Load one manifest and enforce the client-neutral contract."""
    if not path.is_file():
        raise ValueError(f"manifest does not exist: {path}")
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    root = _mapping(document, "manifest")
    if root.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")

    product = _mapping(root.get("product"), "product")
    if product.get("architecture") != "client-neutral":
        raise ValueError("product.architecture must be client-neutral")
    non_goals = product.get("non_goals")
    if not isinstance(non_goals, list) or not {"agent", "chat", "model_gateway"}.issubset(non_goals):
        raise ValueError("product.non_goals must exclude agent, chat, and model_gateway")
    first_class = product.get("first_class_adapters")
    if first_class != FIRST_CLASS_ADAPTERS:
        raise ValueError("product.first_class_adapters must list the declared first-class adapters")

    requirements = _mapping(root.get("requirements"), "requirements")
    if "hermes" in requirements:
        raise ValueError("Hermes must remain an optional adapter, not a core requirement")
    if requirements.get("core_runtime") != "no Hermes installation required":
        raise ValueError("requirements.core_runtime must be client-neutral")
    optional = _mapping(requirements.get("optional_adapters"), "requirements.optional_adapters")
    if optional.get("hermes") != HERMES_ADAPTER_REQUIREMENT:
        raise ValueError("Hermes adapter must use capability discovery instead of a pinned package range")

    adapters_section = _mapping(root.get("adapters"), "adapters")
    interface = adapters_section.get("interface")
    if interface != EXPECTED_INTERFACE:
        raise ValueError("adapters.interface must expose the complete adapter interface")
    if adapters_section.get("apply_policy") != "approval_required_action_plan":
        raise ValueError("adapters.apply_policy must require an approved ActionPlan")
    entries = adapters_section.get("entries")
    if not isinstance(entries, list):
        raise ValueError("adapters.entries must be a list")
    if len(entries) != len(EXPECTED_ADAPTERS):
        raise ValueError(f"adapters.entries must contain {len(EXPECTED_ADAPTERS)} adapters")

    normalized: dict[str, dict[str, str]] = {}
    for entry in entries:
        item = _mapping(entry, "adapter entry")
        adapter_id = item.get("id")
        if not isinstance(adapter_id, str) or adapter_id in normalized:
            raise ValueError("adapter ids must be unique strings")
        if adapter_id not in EXPECTED_ADAPTERS:
            raise ValueError(f"unsupported adapter id: {adapter_id}")
        if item.get("support") != EXPECTED_ADAPTERS[adapter_id]:
            raise ValueError(f"adapter {adapter_id} has an invalid support level")
        for field in ("detection", "writes"):
            if not isinstance(item.get(field), str) or not item[field]:
                raise ValueError(f"adapter {adapter_id} requires {field}")
        normalized[adapter_id] = {
            "support": item["support"],
            "detection": item["detection"],
            "writes": item["writes"],
        }
    if set(normalized) != set(EXPECTED_ADAPTERS):
        raise ValueError("adapter inventory does not match the required manifest")
    return {"manifest": root, "adapters": normalized}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a client-neutral workflow manifest")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "workflow-manifest.yaml",
    )
    parser.add_argument("--json", action="store_true", help="emit the redacted adapter inventory as JSON")
    args = parser.parse_args(argv)
    result = load_and_validate(args.manifest.resolve())
    if args.json:
        print(json.dumps(result["adapters"], ensure_ascii=False, sort_keys=True))
    else:
        for adapter_id, details in result["adapters"].items():
            print(
                f"ADAPTER id={adapter_id} support={details['support']} "
                f"detection={details['detection']} writes={details['writes']}"
            )
        deep = sum(item["support"] == "deep" for item in result["adapters"].values())
        print(f"CLIENT_NEUTRAL_MANIFEST_PASS adapters={len(result['adapters'])} first_class={deep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
