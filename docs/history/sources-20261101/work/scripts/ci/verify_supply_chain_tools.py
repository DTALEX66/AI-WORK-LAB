"""WLOSS-200: verify supply-chain tool wiring in CI.

Checks .github/workflows/work-lab-gate.yml:
- the supply-chain-security job exists and runs the three baseline tools:
  actionlint (GHA syntax), zizmor (GHA security), Trivy (vuln/SBOM/secret/
  license/misconfig);
- every tool is version-pinned (never @latest);
- no overlapping scanner stack (Syft/Grype/Gitleaks/OSV-Scanner/Semgrep) is
  added by default — one primary scanner + focused supplements.

Never downloads or executes the scanners locally; it only validates wiring.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED_TOOLS = {
    "rhysd/actionlint": "actionlint",
    "aquasecurity/trivy-action": "trivy",
}
# zizmor runs as a pinned pipx tool (pipx run zizmor==<ver>); the upstream
# Docker action's version input mapping was unreliable in CI and the runner
# lacks uv.
ZIZMOR_PIN_RE = re.compile(r"pipx run zizmor==([^\s#]+)")
FORBIDDEN_OVERLAP = ("syft", "grype", "gitleaks", "osv-scanner", "semgrep")
WORKFLOW_REL = Path(".github/workflows/work-lab-gate.yml")


def verify() -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    current = Path.cwd()
    root = current
    for _ in range(6):
        if (root / WORKFLOW_REL).is_file():
            break
        if root.parent == root:
            root = current
            break
        root = root.parent
    path = root / WORKFLOW_REL
    if not path.is_file():
        return {"valid": False, "errors": [f"workflow missing: {WORKFLOW_REL}"], "warnings": [], "tools": {}}

    text = path.read_text(encoding="utf-8")

    if "supply-chain-security:" not in text:
        errors.append("supply-chain-security job missing")

    found: dict[str, str] = {}
    for action, tool in REQUIRED_TOOLS.items():
        # e.g. "uses: rhysd/actionlint@v1.7.12"
        pattern = re.compile(rf"uses:\s*{re.escape(action)}@([^\s#]+)")
        match = pattern.search(text)
        if not match:
            errors.append(f"{tool}: action {action} not wired")
        else:
            ref = match.group(1)
            found[tool] = ref
            if ref == "latest" or re.fullmatch(r"@?latest", ref):
                errors.append(f"{tool}: version must be pinned, got @latest")

    # zizmor: pinned uv tool invocation.
    zizmor_match = ZIZMOR_PIN_RE.search(text)
    if not zizmor_match:
        errors.append("zizmor: pinned uv tool run (uv tool run zizmor@<ver>) not wired")
    else:
        zizmor_ref = zizmor_match.group(1)
        found["zizmor"] = zizmor_ref
        if zizmor_ref == "latest" or not zizmor_ref:
            errors.append("zizmor: version must be pinned, got @latest")

    for tool in FORBIDDEN_OVERLAP:
        if re.search(rf"(?i)\b{re.escape(tool)}\b", text):
            warnings.append(f"overlapping scanner {tool!r} appears in workflow (default baseline should avoid stacking)")

    # zizmor findings exemptions must be justified in .zizmor.yml (never blind).
    zizmor_config = root / ".zizmor.yml"
    if zizmor_config.is_file():
        zizmor_text = zizmor_config.read_text(encoding="utf-8")
        if "artipacked" in zizmor_text and not any(kw in zizmor_text for kw in ("justification", "never", "false positive", "does not")):
            warnings.append("zizmor artipacked exemption lacks a justification comment")
    else:
        errors.append("zizmor exemptions config (.zizmor.yml) missing")

    return {"valid": not errors, "errors": errors, "warnings": warnings, "tools": found}


if __name__ == "__main__":
    report = verify()
    print(json.dumps({k: v for k, v in report.items()}, ensure_ascii=False, indent=2))
    print(f"SUPPLY_CHAIN_TOOLS {'PASS' if report['valid'] else 'FAIL'} tools={report['tools']}")
    raise SystemExit(0 if report["valid"] else 1)
