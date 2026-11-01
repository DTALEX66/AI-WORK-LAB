from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]

NATIVE_OVERLAP = {
    "browser",
    "computer_use",
    "file",
    "filesystem",
    "memory",
    "search",
    "session_search",
    "web",
    "web_search",
}
PINNED_VERSION_RE = re.compile(r"(@|==|v)?\d+(\.\d+){1,}([-.+][A-Za-z0-9]+)?$")
SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization|bearer)\s*[:=]\s*['\"]?[^\s'\"]{8,}"
)

TEMPLATE: dict[str, Any] = {
    "schema_version": 1,
    "name": "example-mcp",
    "status": "candidate",
    "default_enable": False,
    "source": {
        "package": "@scope/example-mcp@1.2.3",
        "repository": "https://github.com/example/example-mcp",
        "license": "MIT",
        "version": "1.2.3",
    },
    "purpose": "What native Hermes cannot already do.",
    "distinct_advantage": "Why this is better than native Hermes tools for the target workflow.",
    "data_external": True,
    "permissions": {
        "filesystem": "none",
        "network": "public docs API",
        "browser": "none",
        "credentials": [],
    },
    "required_env": [],
    "overlaps_native_tools": [],
    "smoke": {
        "command": "hermes mcp test example-mcp",
        "status": "not_run",
        "evidence": "Run before enabling by default.",
    },
    "prompt_schema_budget": {
        "measured": False,
        "command": "hermes prompt-size --json",
        "delta_tokens": None,
    },
}


def redact(text: str) -> str:
    return SECRET_RE.sub("[REDACTED]", text)


def load_candidate(path: Path) -> dict[str, Any]:
    body = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(body)
    else:
        data = yaml.safe_load(body)
    if not isinstance(data, dict):
        raise SystemExit(f"candidate must be a mapping: {path}")
    return data


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def has_pinned_version(candidate: dict[str, Any]) -> bool:
    source = candidate.get("source") or {}
    package = str(source.get("package") or "")
    version = str(source.get("version") or "")
    if "latest" in package.lower() or version.lower() == "latest":
        return False
    return bool(PINNED_VERSION_RE.search(package) or PINNED_VERSION_RE.match(version))


def add(findings: list[dict[str, str]], severity: str, code: str, message: str) -> None:
    findings.append({"severity": severity, "code": code, "message": redact(message)})


def audit_candidate(candidate: dict[str, Any]) -> tuple[bool, list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    source = candidate.get("source") or {}
    permissions = candidate.get("permissions") or {}
    smoke = candidate.get("smoke") or {}
    budget = candidate.get("prompt_schema_budget") or {}
    default_enable = bool(candidate.get("default_enable"))

    for field in ("schema_version", "name", "status", "purpose", "distinct_advantage"):
        if candidate.get(field) in (None, "", []):
            add(findings, "blocker", f"missing_{field}", f"missing required field: {field}")

    for field in ("package", "repository", "license", "version"):
        if source.get(field) in (None, "", []):
            add(findings, "blocker", f"missing_source_{field}", f"missing source.{field}")

    if not has_pinned_version(candidate):
        add(findings, "blocker", "unpinned_version", "source package/version must be pinned; do not use latest")

    if candidate.get("data_external") is None:
        add(findings, "blocker", "missing_data_external", "data_external must be true or false")

    for field in ("filesystem", "network", "browser", "credentials"):
        if field not in permissions:
            add(findings, "blocker", f"missing_permission_{field}", f"missing permissions.{field}")

    overlaps = {str(item).lower() for item in as_list(candidate.get("overlaps_native_tools"))}
    duplicate_overlap = overlaps & NATIVE_OVERLAP
    if duplicate_overlap and not str(candidate.get("distinct_advantage") or "").strip():
        add(
            findings,
            "blocker",
            "native_overlap_without_advantage",
            "native tool overlap requires a distinct_advantage explanation: " + ",".join(sorted(duplicate_overlap)),
        )

    if default_enable:
        add(findings, "blocker", "default_enable_requested", "do not default-enable MCP candidates from audit files")
        if smoke.get("status") != "pass":
            add(findings, "blocker", "default_without_smoke_pass", "default enable requires smoke.status: pass")
        if not budget.get("measured"):
            add(findings, "blocker", "default_without_prompt_budget", "default enable requires prompt_schema_budget.measured: true")
    else:
        if smoke.get("status") not in {"pass", "not_run", "blocked", "fail"}:
            add(findings, "warning", "unknown_smoke_status", "smoke.status should be pass/not_run/blocked/fail")

    if smoke.get("status") == "pass" and not smoke.get("command"):
        add(findings, "blocker", "smoke_pass_without_command", "smoke pass requires command evidence")

    if as_list(candidate.get("required_env")) and permissions.get("credentials") in (None, [], "none"):
        add(findings, "warning", "env_without_credentials_permission", "required_env is set but permissions.credentials is empty")

    passed = not any(item["severity"] == "blocker" for item in findings)
    return passed, findings


def write_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(TEMPLATE, sort_keys=False, allow_unicode=True), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit a candidate MCP before enabling it in Workflow-assistance.")
    parser.add_argument("candidate", nargs="?", type=Path, help="YAML/JSON candidate audit file")
    parser.add_argument("--write-template", type=Path, help="Write a candidate YAML template and exit")
    parser.add_argument("--json", action="store_true", help="Emit JSON result")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.write_template:
        write_template(args.write_template)
        print(f"MCP_CANDIDATE_TEMPLATE_WRITTEN path={args.write_template}")
        return 0
    if not args.candidate:
        raise SystemExit("candidate path is required unless --write-template is used")

    candidate = load_candidate(args.candidate)
    passed, findings = audit_candidate(candidate)
    result = {
        "status": "pass" if passed else "fail",
        "candidate": candidate.get("name"),
        "findings": findings,
    }
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        marker = "MCP_CANDIDATE_AUDIT_PASS" if passed else "MCP_CANDIDATE_AUDIT_FAIL"
        print(f"{marker} candidate={candidate.get('name')}")
        for finding in findings:
            print(f"{finding['severity']}:{finding['code']}:{finding['message']}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
