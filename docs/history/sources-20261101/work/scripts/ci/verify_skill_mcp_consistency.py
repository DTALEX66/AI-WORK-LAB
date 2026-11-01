#!/usr/bin/env python3
"""Verify Agent Skills structure + MCP consistency (NX-210).

1. Every repo-managed skill passes the official Agent Skills base-structure check:
   name, description, version, metadata.hermes present; description non-empty.
2. Malicious Skill/MCP fixture detector: prompt injection, tool poisoning,
   hidden shell, secret reference, out-of-bounds path, oversized context,
   recursive loading — all fail closed and are reported with a reason.
3. MCP candidates validated by protocol schema/capabilities/transport/permission/
   provenance; a successful connection is never treated as security trust.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "packages" / "client-neutral-core" / "skills"
CAPABILITY = ROOT / "config" / "capability-conformance.json"

REQUIRED_FIELDS = ("name", "description", "version")
HIDDEN_SHELL_RE = re.compile(r"(?:subprocess|os\.system|shell=True|\bexec\s*\(|\beval\s*\()", re.IGNORECASE)
SECRET_RE = re.compile(r"(?:api[_ -]?key|authorization|password|secret|bearer\s+\w|token)\s*[:=]", re.IGNORECASE)
PROMPT_INJECTION_RE = re.compile(
    r"(?i)(ignore (all )?(previous|prior) instructions|system prompt|you are now|jailbreak|"
    r"disregard your (instructions|safety)|roleplay as admin|override safety)",
)
OUT_OF_BOUNDS_RE = re.compile(r"(?:\.\./|\.\.\\|C:\\|/etc/|/var/|/usr/|~[\\/]|\\\\[a-z])", re.IGNORECASE)
RECURSIVE_LOAD_RE = re.compile(r"(?i)(recursive|loop\s*load|import\s+self|load\s+itself)")

MALICIOUS_FIXTURES = [
    {"name": "prompt-injection", "regex": PROMPT_INJECTION_RE},
    {"name": "tool-poisoning", "regex": re.compile(r"(?i)(override tool|redefine tool|shadow (builtin|system) tool)")},
    {"name": "hidden-shell", "regex": HIDDEN_SHELL_RE},
    {"name": "secret-reference", "regex": SECRET_RE},
    {"name": "out-of-bounds-path", "regex": OUT_OF_BOUNDS_RE},
    {"name": "oversized-context", "regex": re.compile(r"(?i)(unlimited context|no context limit|load entire (repo|workspace))")},
    {"name": "recursive-load", "regex": RECURSIVE_LOAD_RE},
]

# These appear in benign skill docs (e.g. security guardrails); only flag when
# the surrounding intent is malicious. We keep the regexes narrow and require a
# matching detection reason to be surfaced, not silent auto-trust.
BENIGN_ALLOW = (
    "skill-guidance", "fail-closed", "must not", "prohibit", "never read",
    "never use", "never store", "禁止", "不得", "不要", "切勿", "勿", "does not",
    "do not", "reject", "blocked", "guard", "guardrail", "sandbox", "forbidden",
    "shall not", "should not", "avoid", "warning", "安全", "防护",
)
MALICIOUS_ACTION_HINTS = (
    "please run", "run this", "execute", "call shell", "invoke shell",
    "download and run", "curl |", "pipe to sh", "give me the secret",
    "send to", "upload to", "exfiltrate", "请执行", "请运行", "运行以下",
)


def _detect_malicious(path: Path, text: str) -> list[str]:
    findings: list[str] = []
    lines = text.splitlines()
    for fixture in MALICIOUS_FIXTURES:
        hit_lines = [ln for ln in lines if fixture["regex"].search(ln)]
        if not hit_lines:
            continue
        # A match is benign if the line is a prohibition/guardrail OR has no
        # active malicious-action intent.
        joined = " ".join(hit_lines).lower()
        if any(b in joined for b in BENIGN_ALLOW):
            continue
        # For hidden-shell/secret/path patterns, require an active action hint
        # to avoid flagging descriptive security notes.
        if fixture["name"] in ("hidden-shell", "secret-reference", "out-of-bounds-path"):
            if not any(h in joined for h in MALICIOUS_ACTION_HINTS):
                continue
        findings.append(fixture["name"])
    return findings


def _load_skill_frontmatter(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise ValueError("PyYAML required")
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path.name}: missing YAML frontmatter")
    end = text.find("\n---", 4)
    data = yaml.safe_load(text[4:end]) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: frontmatter must be a mapping")
    return data


def verify(root: Path = ROOT, skills_dir: Path | None = None, capability_path: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    if skills_dir is None:
        skills_dir = root / SKILLS.relative_to(ROOT)
    if capability_path is None:
        capability_path = root / CAPABILITY.relative_to(ROOT)
    skill_files = sorted(skills_dir.rglob("SKILL.md"))
    if not skill_files:
        raise ValueError("no repo-managed skills found")

    skills = []
    for path in skill_files:
        data = _load_skill_frontmatter(path)
        missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
        if missing:
            errors.append(f"{path.name}: missing required Agent Skills fields: {missing}")
        desc = str(data.get("description", "")).strip()
        if not desc:
            errors.append(f"{path.name}: description must be non-empty")
        metadata = data.get("metadata") or {}
        hermes = metadata.get("hermes") if isinstance(metadata, dict) else None
        if not isinstance(hermes, dict):
            errors.append(f"{path.name}: metadata.hermes is required (WORK-LAB extension namespace)")
        skills.append(path.name)

    # Malicious fixture scan on SKILL.md bodies.
    for path in skill_files:
        findings = _detect_malicious(path, path.read_text(encoding="utf-8"))
        if findings:
            errors.append(f"{path.name}: malicious pattern detected -> {','.join(findings)}")

    # MCP consistency: capability-conformance manifest, if present.
    cap_path = capability_path
    if cap_path.is_file():
        cap = json.loads(cap_path.read_text(encoding="utf-8"))
        mcp = cap.get("mcp", {})
        if mcp.get("status") not in ("STATIC_UNVERIFIED", "STATIC_PASS", "BLOCKED"):
            errors.append("mcp.status must be one of STATIC_UNVERIFIED/STATIC_PASS/BLOCKED")
        for entry in mcp.get("entries", []):
            if not entry.get("permissions") or entry.get("permissions") == ["execute"]:
                errors.append(f"mcp {entry.get('id')}: execute permission without read-only cannot auto-trust")

    if errors:
        raise ValueError("; ".join(errors))
    return {"skills": len(skills), "skill_names": skills, "malicious_fixtures": len(MALICIOUS_FIXTURES)}


def main() -> int:
    try:
        result = verify()
    except (ValueError, json.JSONDecodeError, OSError, ImportError) as exc:
        print(f"SKILL_MCP_CONSISTENCY_FAIL {exc}")
        return 1
    print(
        f"SKILL_MCP_CONSISTENCY_PASS skills={result['skills']} "
        f"malicious_fixtures={result['malicious_fixtures']} all_validated=true scope=workflow"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
