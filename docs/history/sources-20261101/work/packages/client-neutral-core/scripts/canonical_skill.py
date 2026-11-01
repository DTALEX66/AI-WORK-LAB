"""WLOSS-500: CanonicalSkill neutralization.

A single source of truth for a WORK-LAB skill, from which agent-specific
artifacts are EXPORTED (Hermes SKILL.md, Codex skill, Agent Skills open
format). The canonical model — not any agent-specific SKILL.md — is the
source of truth. No agent runtime is required.

Integration modes: the canonical model is DERIVE (from repo skills); the
exporters are ADAPTERS.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CANONICAL_SKILL_SCHEMA = "work-lab/canonical-skill/v1"

FORBIDDEN_TOOLS = {"terminal", "execute_code", "browser", "file"}  # allowlist baseline


@dataclass
class CanonicalSkill:
    identity: str  # stable id, e.g. "project-data-boundary"
    purpose: str
    trigger_hints: list[str] = field(default_factory=list)
    required_inputs: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    evidence_contract: str = ""
    tests: list[str] = field(default_factory=list)
    adapters: dict[str, str] = field(default_factory=dict)  # adapter_id -> path/note
    version: str = "1.0.0"
    license: str = "MIT"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": CANONICAL_SKILL_SCHEMA,
            "identity": self.identity,
            "purpose": self.purpose,
            "triggerHints": list(self.trigger_hints),
            "requiredInputs": list(self.required_inputs),
            "forbiddenActions": list(self.forbidden_actions),
            "allowedTools": list(self.allowed_tools),
            "evidenceContract": self.evidence_contract,
            "tests": list(self.tests),
            "adapters": dict(self.adapters),
            "version": self.version,
            "license": self.license,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CanonicalSkill":
        return cls(
            identity=str(data["identity"]),
            purpose=str(data["purpose"]),
            trigger_hints=list(data.get("triggerHints", [])),
            required_inputs=list(data.get("requiredInputs", [])),
            forbidden_actions=list(data.get("forbiddenActions", [])),
            allowed_tools=list(data.get("allowedTools", [])),
            evidence_contract=str(data.get("evidenceContract", "")),
            tests=list(data.get("tests", [])),
            adapters=dict(data.get("adapters", {})),
            version=str(data.get("version", "1.0.0")),
            license=str(data.get("license", "MIT")),
        )

    def digest(self) -> str:
        raw = f"{self.identity}|{self.version}|{self.purpose}|{self.evidence_contract}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.identity or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", self.identity):
            errors.append("identity must be lowercase alphanumeric with hyphens")
        if not self.purpose:
            errors.append("purpose is required")
        if not self.evidence_contract:
            errors.append("evidence_contract is required (evidence must be verifiable, never fabricated)")
        return errors


# ------------------------- Exporters (ADAPTERS) -------------------------

def export_hermes(skill: CanonicalSkill) -> str:
    """Hermes SKILL.md (frontmatter + markdown body)."""
    fm = {
        "name": skill.identity,
        "description": skill.purpose,
        "version": skill.version,
        "author": "WORK-LAB",
        "license": skill.license,
        "metadata": {"hermes": {"tags": skill.trigger_hints[:8]}},
    }
    import json

    lines = ["---"]
    lines.append(f"name: {skill.identity}")
    lines.append(f"description: \"{skill.purpose}\"")
    lines.append(f"version: {skill.version}")
    lines.append(f"author: WORK-LAB")
    lines.append(f"license: {skill.license}")
    lines.append("metadata:")
    lines.append("  hermes:")
    lines.append("    tags: " + json.dumps(skill.trigger_hints[:8], ensure_ascii=False))
    lines.append("---")
    lines.append(f"# {skill.identity}")
    lines.append("")
    lines.append(skill.purpose)
    lines.append("")
    lines.append("## Evidence contract")
    lines.append(skill.evidence_contract)
    lines.append("")
    lines.append("## Forbidden")
    for action in skill.forbidden_actions:
        lines.append(f"- {action}")
    lines.append("")
    lines.append("## Tests")
    for test in skill.tests:
        lines.append(f"- {test}")
    return "\n".join(lines) + "\n"


def export_codex(skill: CanonicalSkill) -> str:
    """Codex user-skill SKILL.md (frontmatter + markdown)."""
    return (
        "---\n"
        f"name: {skill.identity}\n"
        f"description: \"{skill.purpose}\"\n"
        f"version: {skill.version}\n"
        "license: MIT\n"
        "platforms: [windows, linux, macos]\n"
        "---\n\n"
        f"# {skill.identity}\n\n{skill.purpose}\n\n"
        "## Evidence contract\n\n" + skill.evidence_contract + "\n\n"
        "## Forbidden actions\n\n" + "\n".join(f"- {a}" for a in skill.forbidden_actions) + "\n"
    )


def export_agent_skills(skill: CanonicalSkill) -> str:
    """Agent Skills open format (frontmatter + body)."""
    return (
        "---\n"
        f"name: {skill.identity}\n"
        f"description: \"{skill.purpose}\"\n"
        f"version: {skill.version}\n"
        "license: MIT\n"
        "agent-skills: v1\n"
        "---\n\n"
        f"# {skill.identity}\n\n{skill.purpose}\n\n"
        "## Evidence contract\n\n" + skill.evidence_contract + "\n\n"
        "## Trigger hints\n\n" + "\n".join(f"- {t}" for t in skill.trigger_hints) + "\n"
    )


def parse_hermes_skill_md(path: Path) -> CanonicalSkill:
    """Parse an existing Hermes SKILL.md into a canonical model (DERIVE)."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError(f"not a frontmatter skill: {path}")
    frontmatter, body = match.group(1), match.group(2)
    fields: dict[str, Any] = {}
    for line in frontmatter.splitlines():
        if ":" in line and not line.startswith((" ", "  ")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip('"')
    first_paragraph = body.strip().split("\n\n")[0].strip()
    purpose = fields.get("description") or first_paragraph
    return CanonicalSkill(
        identity=str(fields.get("name", path.stem)),
        purpose=purpose,
        version=str(fields.get("version", "1.0.0")),
        license=str(fields.get("license", "MIT")),
        evidence_contract="Evidence is recorded as verifiable artifacts; no fabricated results.",
        tests=[f"tests for {fields.get('name', path.stem)}"],
    )
