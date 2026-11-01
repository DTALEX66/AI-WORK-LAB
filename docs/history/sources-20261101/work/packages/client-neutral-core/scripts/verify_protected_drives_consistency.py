#!/usr/bin/env python3
"""Verify protected-drives truth consistency across E+F governance surfaces.

WS-3 (spec-1): the user standing rule protects BOTH data drives (E: and F:).
Three governed surfaces must agree on the protected-drive set:

  1. config/global-agent-policy.yaml            -> protected_storage.protected_drives
  2. .project/governance/projects.json          -> forbiddenRoots
  3. .project/governance/project-data-boundary.json
         -> forbiddenExternalRoots + spillGovernance.protectedDataVolume.roots

Fail-closed: a missing or unreadable file is a FAIL, not a pass.
stdlib-only, no network, repo-relative paths (ROOT derived from this file).
Style aligned with verify_external_libraries_index.py (PASS/FAIL + exit 0/1).
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
GAPS: list[str] = []


def _fail_closed(msg):
    GAPS.append(msg)


def parse_yaml(value: str, label: str):
    """Minimal stdlib-only YAML parse for `protected_storage.protected_drives: [E, F]`.

    No PyYAML dependency: the SSOT line is a flat flow-style list we own and verify.
    """
    for line in value.splitlines():
        m = re.match(r"^(\s*)protected_drives:\s*\[([^\]]*)\]", line)
        if m:
            drives = [item.strip().strip("\"'") for item in m.group(2).split(",") if item.strip()]
            return [item.upper() for item in drives]
    _fail_closed(f"{label}: protected_drives key not found")
    return None


def drive_set_from_roots(roots) -> set:
    """Extract uppercase drive letters from root strings like 'E:/', 'E:\\', 'F:'."""
    drives = set()
    for root in roots or []:
        if not isinstance(root, str):
            continue
        m = re.match(r"^([A-Za-z]):[\\/]", root)
        if m:
            drives.add(m.group(1).upper())
        else:
            m = re.match(r"^([A-Za-z]):$", root)
            if m:
                drives.add(m.group(1).upper())
    return drives


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    missing = []
    for relative in (
        "config/global-agent-policy.yaml",
        ".project/governance/projects.json",
        ".project/governance/project-data-boundary.json",
    ):
        if not (ROOT / relative).is_file():
            missing.append(relative)
    if missing:
        print("FAIL protected-drives-consistency: missing required file(s): " + ", ".join(missing))
        sys.exit(1)

    policy_text = (ROOT / "config/global-agent-policy.yaml").read_text(encoding="utf-8")
    policy_drives = parse_yaml(policy_text, "global-agent-policy.yaml")
    if policy_drives is None:
        print("FAIL protected-drives-consistency:\n  - " + "\n  - ".join(GAPS))
        sys.exit(1)
    policy_set = set(policy_drives)

    projects = json.loads((ROOT / ".project/governance/projects.json").read_text(encoding="utf-8"))
    forbidden_roots = projects.get("forbiddenRoots", [])
    forbidden_set = drive_set_from_roots(forbidden_roots)

    boundary = json.loads(
        (ROOT / ".project/governance/project-data-boundary.json").read_text(encoding="utf-8")
    )
    boundary_forbidden = boundary.get("forbiddenExternalRoots", [])
    boundary_forbidden_set = drive_set_from_roots(boundary_forbidden)
    volume_roots = boundary.get("spillGovernance", {}).get("protectedDataVolume", {}).get("roots", [])
    volume_set = drive_set_from_roots(volume_roots)

    all_sets = {
        "global-agent-policy.yaml protected_drives": policy_set,
        "projects.json forbiddenRoots": forbidden_set,
        "project-data-boundary.json forbiddenExternalRoots": boundary_forbidden_set,
        "project-data-boundary.json protectedDataVolume.roots": volume_set,
    }

    if policy_set != forbidden_set or policy_set != boundary_forbidden_set or policy_set != volume_set:
        GAPS.append("drive sets disagree: " + "; ".join(f"{k}={sorted(v)}" for k, v in all_sets.items()))
    expected = {"E", "F"}
    if not expected.issubset(policy_set):
        GAPS.append(f"standing rule requires E and F protected on every surface; got {sorted(expected - policy_set)} missing")

    if GAPS:
        print("FAIL protected-drives-consistency:")
        for gap in GAPS:
            print("  - " + gap)
        sys.exit(1)
    print(f"PASS protected-drives-consistency: {sorted(policy_set)} protected on all {len(all_sets)} surfaces; sets equal")


if __name__ == "__main__":
    raise SystemExit(main())
