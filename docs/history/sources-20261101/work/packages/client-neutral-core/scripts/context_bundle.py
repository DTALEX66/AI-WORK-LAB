# -*- coding: utf-8 -*-
"""Stable Prefix and ContextBundle (WL3-330 / MR-10, upgraded per Context Control Plane design).

Deterministic context bundles: stable vs volatile separation, selector-driven
incremental file reads, versioned digests, required-field validation, and the
full taskpack §12.2 manifest. Assembly follows §12.1 order (system boundary ->
tool schema -> global rules -> project rules summary -> evidence -> tree/SHA ->
transient state). Head pinning keeps critical rules/boundary across compaction.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "workflow/context-bundle/v1"
BOUNDARY_MARKER = "BOUNDARY"
ACCEPTANCE_MARKER = "ACCEPTANCE"

# §12.1 assembly order: stable blocks keep this rank.
ASSEMBLY_ORDER = (
    "system_boundary",       # 1 system boundary
    "tool_schema",           # 2 tool schema (deterministic order)
    "global_rules",          # 3 global rules reference
    "project_rules",         # 4 project rules versioned summary
    "evidence",              # 5 task-relevant stable evidence
    "tree_sha",              # 6 current tree/SHA/diff
    "transient",             # 7 current turn + temporary state
)

# §12.6: compaction must preserve these; missing any => fail closed.
DRIFT_PRESERVE = (
    "user_goal",
    "non_goals",
    "allowed_paths",
    "forbidden_paths",
    "data_boundary",
    "base_sha_tree",
    "known_failures",
    "acceptance_commands",
    "rollback_method",
)

# Volatile patterns that must never enter the stable digest (§12.1 forbidden).
_VOLATILE_RE = re.compile(
    r"(?:20\d{2}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"
    r"|(?:[0-9a-f]{32})"
    r"|(?:tmp[\\/][A-Za-z0-9_.-]+)"
    r"|(?:__pycache__)"
)


class ContextBundle:
    def __init__(self, project_id: str, rules_revision: str,
                 global_rules_revision: str = "global-1") -> None:
        self.project_id = project_id
        self.rules_revision = rules_revision
        self.global_rules_revision = global_rules_revision

    # -- stable digest -------------------------------------------------------
    def stable_digest(self, source_text: str, revision: str | None = None) -> str:
        normalized = self._normalize(source_text)
        effective_revision = revision or self.rules_revision
        payload = f"{self.project_id}\0{effective_revision}\0{normalized}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _normalize(text: str) -> str:
        cleaned = _VOLATILE_RE.sub("", text)
        return cleaned.rstrip("\n")

    # -- bundle assembly (§12.1 + §12.2 manifest) -----------------------------
    def build(self, blocks: dict[str, str], boundary: str, acceptance: str,
              base_tree: str | None = None,
              evidence_selectors: list[str] | None = None,
              data_classification: str = "public",
              redaction_result: str = "none-required",
              expires_at: str | None = None,
              volatile: dict[str, Any] | None = None,
              preserve: dict[str, str] | None = None) -> dict[str, Any]:
        """Build a canonical context bundle.

        blocks: {assembly_block_id: content} keyed by ASSEMBLY_ORDER entries.
        preserve: {drift_field: value} for §12.6 critical facts.
        Missing boundary/acceptance or drift facts => fail closed.
        """
        if not boundary.strip():
            raise ValueError("context_bundle_missing_boundary")
        if not acceptance.strip():
            raise ValueError("context_bundle_missing_acceptance")

        # §12.6: compaction/assembly must preserve critical facts.
        preserve = preserve or {}
        missing_drift = [k for k in DRIFT_PRESERVE if k not in preserve or not str(preserve.get(k) or "").strip()]
        if missing_drift:
            raise ValueError(f"context_drift_missing: {missing_drift}")

        # Stable prefix: assemble in §12.1 order, dropping absent blocks.
        ordered = [(bid, blocks[bid]) for bid in ASSEMBLY_ORDER if bid in blocks]
        stable_lines: list[str] = []
        for bid, content in ordered:
            stable_lines.append(f"[{bid}]")
            stable_lines.append(self._normalize(content))
        stable_block = "\n".join(stable_lines)
        stable_digest = self.stable_digest(stable_block, self.rules_revision)

        return {
            "schema_version": SCHEMA_VERSION,
            "project_id": self.project_id,
            "global_rules_revision": self.global_rules_revision,
            "project_rules_revision": self.rules_revision,
            "base_tree": base_tree,
            "evidence_selectors": sorted(evidence_selectors or []),
            "ordered_stable_block_ids": [bid for bid, _ in ordered],
            "volatile_block_ids": sorted(set(blocks) - {bid for bid, _ in ordered}),
            "token_estimate_source": "unavailable",
            "data_classification": data_classification,
            "redaction_result": redaction_result,
            "expires_at": expires_at,
            "boundary": boundary,
            "acceptance": acceptance,
            "drift_preserve": dict(preserve),
            "stable_prefix": stable_block,
            "stable_digest": stable_digest,
            "volatile": volatile or {},
            "volatile_absent": volatile is None,
        }

    # -- validation ----------------------------------------------------------
    @staticmethod
    def validate(bundle: dict[str, Any]) -> tuple[bool, str]:
        required = ("schema_version", "project_id", "global_rules_revision",
                    "project_rules_revision", "base_tree", "evidence_selectors",
                    "ordered_stable_block_ids", "data_classification",
                    "redaction_result", "boundary", "acceptance",
                    "drift_preserve", "stable_prefix", "stable_digest")
        for key in required:
            if key not in bundle:
                return False, f"missing required field: {key}"
        if not bundle.get("boundary"):
            return False, "boundary empty (fail closed)"
        if not bundle.get("acceptance"):
            return False, "acceptance empty (fail closed)"
        # §12.6 drift facts must all be present and non-empty.
        for key in DRIFT_PRESERVE:
            val = (bundle.get("drift_preserve") or {}).get(key)
            if not val or not str(val).strip():
                return False, f"drift fact missing: {key}"
        return True, "bundle valid"

    # -- project isolation ---------------------------------------------------
    @staticmethod
    def project_mismatch(bundle: dict[str, Any], project_id: str) -> bool:
        return bundle.get("project_id") != project_id

    # -- revision invalidation ------------------------------------------------
    @staticmethod
    def revision_changed(bundle: dict[str, Any], current_revision: str) -> bool:
        return bundle.get("project_rules_revision") != current_revision


def build_from_directory(bundle: ContextBundle, root: Path,
                         selectors: list[str], boundary: str, acceptance: str,
                         preserve: dict[str, str] | None = None,
                         base_tree: str | None = None) -> dict[str, Any]:
    """Read selected files into the evidence block. Read-only, containment-checked."""
    files: dict[str, str] = {}
    for selector in selectors:
        path = (root / selector).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            raise ValueError(f"path escape rejected: {selector}")
        if path.is_file():
            files[selector] = path.read_text(encoding="utf-8", errors="replace")
    evidence = "\n".join(f"{rel}: {content}" for rel, content in sorted(files.items()))
    blocks = {"system_boundary": boundary, "evidence": evidence}
    return bundle.build(blocks, boundary, acceptance, base_tree=base_tree,
                        evidence_selectors=list(files), preserve=preserve)


if __name__ == "__main__":
    b = ContextBundle("work-lab", "rev-1")
    preserve = {
        "user_goal": "reduce token waste",
        "non_goals": "do not drop evidence",
        "allowed_paths": ".hermes",
        "forbidden_paths": "E:/",
        "data_boundary": "project only",
        "base_sha_tree": "abc123",
        "known_failures": "none",
        "acceptance_commands": "python run_quality_gate.py verify",
        "rollback_method": "restore from backup",
    }
    bundle = b.build(
        {"system_boundary": "project root only", "evidence": "rules.md: No E drive."},
        boundary="project root only",
        acceptance="tests pass",
        base_tree="abc123",
        preserve=preserve,
    )
    print(json.dumps({k: v for k, v in bundle.items() if k != "stable_prefix"}, ensure_ascii=False, indent=2))
    print("valid:", ContextBundle.validate(bundle))
