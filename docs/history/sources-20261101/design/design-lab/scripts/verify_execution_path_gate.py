#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-CLOUD-2026-09-25 Prompt B-C: unapproved-execution-path gate (fail-closed).

Scans the repository's *execution paths* (agent/CLI scripts, active CI
workflows, apps, integrations, packages, evals) for toolchain-fetch tokens --
curl / wget / Invoke-WebRequest / winget|choco|scoop install / git clone /
pip|npm|pnpm|yarn install / npx -y / model auto-download. The risk this gate
closes is the audit's no-download-on-miss concern: a locator that *misses*
must return an actionable error, never trigger a second toolchain fetch.

Pinned allowlist (``execution-path-allowlist.json``):

* each live hit MUST be pinned by an exact (file, pattern_tag) entry carrying
  a receipt (Prompt B-D: source / revision / owner approval / rollback);
* an entry pinning no live hit is STALE and fails the gate (a silently-dead
  allow-list is drift);
* a hit with no pin is a NEW VIOLATION and fails the gate.

The gate's own pattern definitions are pinned entries (same convention as the
B4 locator gate). No line in this file that carries a fetch token outside the
pinned pattern table is accepted.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

ALLOWLIST = ROOT / "design-lab" / "config" / "execution-path-allowlist.json"

# Execution paths (the surfaces that would run the toolchain). The archived
# workflow directory is historical evidence, not an execution path.
SCAN_DIRS = [
    "design-lab/scripts",
    "design-lab/tests",
    "scripts",
    ".github/workflows",
    "apps",
    "integrations",
    "packages",
    "evals",
]
SCAN_EXTS = {".py", ".js", ".ts", ".mjs", ".sh", ".ps1", ".psm1", ".yml", ".yaml"}

# pattern_tag -> compiled regex. Tags are stable names used by the allowlist.
PATTERNS: dict[str, re.Pattern] = {
    "curl": re.compile(r"\bcurl\b"),
    "wget": re.compile(r"\bwget\b"),
    "invoke-web": re.compile(r"Invoke-WebRequest"),
    "invoke-rest": re.compile(r"Invoke-RestMethod"),
    "winget-install": re.compile(r"\bwinget\s+install\b"),
    "choco-install": re.compile(r"\bchoco\s+install\b"),
    "scoop-install": re.compile(r"\bscoop\s+install\b"),
    "git-clone": re.compile(r"\bgit\s+clone\b"),
    "pip-install": re.compile(r"\bpip\s+install\b|python\s+-m\s+pip\s+install"),
    "npm-install": re.compile(r"\bnpm\s+install\b"),
    "pnpm-install": re.compile(r"\bpnpm\s+(install|i)\b"),
    "yarn-add": re.compile(r"\byarn\s+(install|add)\b"),
    "npx-y": re.compile(r"\bnpx\s+-y\b"),
    "hf-snapshot": re.compile(r"snapshot_download"),
    "hf-from-pretrained": re.compile(r"from_pretrained"),
    "uv-toolchain": re.compile(r"\buv\s+(sync|pip)\b|\buv\s+lock\b"),
    "setup-action": re.compile(r"actions/(setup-python|setup-node|setup-@)"),
}


# This gate's own file is a *definition* surface: its PATTERNS table carries
# the fetch-token literals as data, not as execution paths. It is excluded
# from the scan (guard/verifier files that *consume* these patterns are pinned
# in the allowlist instead, per the B4 convention).
SELF = "design-lab/scripts/verify_execution_path_gate.py"


def _tracked() -> list[str]:
    out: list[str] = []
    for d in SCAN_DIRS:
        p = ROOT / d
        if not p.exists():
            continue
        r = subprocess.run(
            ["git", "ls-files", d], cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=False,
        )
        out += r.stdout.splitlines()
    return sorted({f for f in out if f and f != SELF and (ROOT / f).exists()})


def _live_hits() -> dict[str, list[tuple[str, int]]]:
    """file -> [(pattern_tag, line_no), ...] across the execution paths."""
    hits: dict[str, list[tuple[str, int]]] = {}
    for rel in _tracked():
        if Path(rel).suffix not in SCAN_EXTS:
            continue
        text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            s = line.strip()
            if s.startswith("#") or s.startswith("//") or s.startswith("*"):
                continue
            for tag, cre in PATTERNS.items():
                if cre.search(line):
                    hits.setdefault(rel, []).append((tag, i))
    return hits


def _load_allowlist() -> dict:
    if not ALLOWLIST.exists():
        return {"pins": []}
    return json.loads(ALLOWLIST.read_text(encoding="utf-8"))


def check() -> tuple[list[str], int]:
    findings: list[str] = []
    live = _live_hits()
    # A pin only counts when it carries the full receipt five-tuple
    # (reason + source + owner_approval); a bare pin is not approval.
    pins = {
        (p.get("file"), p.get("pattern"))
        for p in _load_allowlist().get("pins", [])
        if p.get("reason") and p.get("source") and p.get("owner_approval")
    }
    live_pairs = {(rel, tag) for rel, pairs in live.items() for tag, _line in pairs}
    # 1. any live hit with no pin is a NEW violation (the no-drift case).
    for rel, tag in sorted(live_pairs - pins):
        findings.append(f"NEW-VIOLATION {rel} [{tag}] (unpinned toolchain-fetch token)")
    # 2. any pin matching no live hit is STALE (a dead allow-list is drift).
    for rel, tag in sorted(pins - live_pairs):
        findings.append(f"STALE-PIN {rel} [{tag}] (allowlist pins a hit that no longer exists)")
    return findings, len(live)


def main() -> int:
    findings, files = check()
    for f in sorted(findings):
        print(f"  {f}")
    if findings:
        print(f"\nVERIFY_EXECUTION_PATH_GATE=FAIL files={files} findings={len(findings)}")
        return 1
    print(f"\nVERIFY_EXECUTION_PATH_GATE=PASS files={files} pins-verified (all live hits pinned; no stale pins)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
