#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-CLOUDAUDIT-B4 / G-4: adapter & integration machine-location locator audit.

Audit R10. Adapter / integration *runtime* source must not hard-code a machine
location (a drive-rooted executable such as ``D:\\Programs\\Open Design\\Open
Design.exe``, a specific drive, an install dir, a registry key) in a way that
assumes the owner's machine. The correct locator pattern is env-var / registry /
PATH-first with a fail-closed fallback.

This gate is *structural only*, per the task: it records the **locator refactor
inventory** (``design-lab/config/adapter-locator-inventory.json``) and enforces
it as a fail-closed drift guard. It does NOT refactor the code — that is the
owner-gated / TaskPack work this inventory hands off.

Model (mirrors the P1-3 library-index guard: stdlib, read-only, fail-closed,
``TAG=PASS/FAIL``):

  1. scan a fixed, versioned scope of adapter/integration files with a fixed set
     of high-signal machine-location patterns (drive-rooted paths/exe, env-var
     home reads, ``expanduser``, ProgID/CLSID/Program Files). The scope and the
     patterns live in code, so neither can silently drift;
  2. fingerprint every real-code hit (file + kind + normalised fragment);
  3. load the inventory and enforce:
       * every live ``violation``/``guard``/``locator`` hit is triaged in the
         inventory (a new untriaged hard-coded location fails the gate);
       * every inventory entry pinned ``true`` is still live (a refactored-away
         assumption must be re-triaged, not silently drop);
       * the inventory is schema-valid.

Informational hits (comment / error-message prose mentioning a path) are not
forced into the inventory: they carry no runtime assumption.

Run:
    python design-lab/scripts/verify_adapter_locator_audit.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

DESIGN_LAB = Path(__file__).resolve().parents[1]  # design-lab/
REPO_ROOT = DESIGN_LAB.parent                     # DESIGN-LAB/
INVENTORY = DESIGN_LAB / "config" / "adapter-locator-inventory.json"

# Fixed, versioned scan scope: the adapter / integration runtime source. A new
# adapter source tree must be added here deliberately (a scope change is a gate
# change, reviewed in PR). Tests and fixtures are out of scope on purpose: they
# may name concrete paths, and they are not the machine-integration surface.
SCAN_DIRS = [
    "src/design_lab/adapters",
    "src/design_lab/reconstruction",
    "src/design_lab/generators",
    "src/design_lab/creative",
    "src/design_lab/interop",
    "src/design_lab/readiness",
]
SCAN_FILES = [
    "src/design_lab/runtime/paths.py",
    "design-lab/scripts/configure_open_design_windows.py",
    "design-lab/scripts/doctor_open_design_windows.py",
    "design-lab/scripts/resolve_open_design_locator.py",
    "design-lab/scripts/scaffold_open_design_plugin.py",
    "design-lab/scripts/verify_illustrator_reconstruction_adapter.py",
    "design-lab/scripts/verify_photoshop_reconstruction_adapter.py",
]

# Kinds that carry a real machine-location assumption and must be triaged.
TRIAGE_KINDS = ("violation", "guard", "locator")
INFORMATIONAL_KINDS = ("message",)


def _tracked() -> list[str]:
    import subprocess
    out: list[str] = []
    for d in SCAN_DIRS:
        out += subprocess.run(["git", "ls-files", d], cwd=REPO_ROOT,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              check=False).stdout.splitlines()
    out += [f for f in SCAN_FILES]
    return sorted({f for f in out if f and (REPO_ROOT / f).exists()})


def _normalise(fragment: str) -> str:
    """Stable, line-independent fingerprint input: collapse whitespace, drop the
    raw drive letter casing differences are preserved (they matter), no line
    numbers, so the fingerprint survives an edit that only shifts lines."""
    return re.sub(r"\s+", " ", fragment).strip()


# ---- fixed, high-signal machine-location patterns ---------------------------
# Each: (kind, compiled regex, human label). The lookbehind before a drive letter
# blocks scheme pseudo-matches such as ``s://`` inside ``https://``.
PATTERNS: list[tuple[str, "re.Pattern[str]", str]] = [
    # A drive-rooted path or executable (the core R10 concern).
    ("drive", re.compile(r"""(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s"'`,;)\]}>]+"""), "drive-rooted path/exe"),
    # Explicit Windows home / app-data env reads (the *correct* locator inputs).
    ("env_home", re.compile(r"""(?:USERPROFILE|LOCALAPPDATA|APPDATA|HOMEDRIVE|HOMEPATH|ProgramData|CommonAppData|PROGRAMFILES|PROGRAMFILES\(X86\))"""), "Windows home/appdata env"),
    # Expanduser is the portable home locator.
    ("expanduser", re.compile(r"os\.path\.expanduser\(|Path\(\s*['\"]~"), "expanduser home"),
    # COM / Win32-registry surface (an adapter hard-coding a ProgID/CLSID or a
    # registry key is a machine assumption). Deliberately NOT the bare word
    # "registry": in this codebase it is a domain noun (the generative model
    # registry, Open Design's own UI registry, ``validate_registry``), never a
    # Win32 key.
    ("com_registry", re.compile(r"(?:HKLM|HKCU|HKEY_[A-Z]|winreg|CLSID|ProgID|Reg(?:istry)?OpenKey)"), "COM/Win32-registry surface"),
]

# Classify a live hit into a triage kind from the surrounding line. This is the
# heuristic that decides which *kinds* are enforced; the *inventory* is the
# authoritative triage (a hit's kind can be overridden by a matching entry).
_GUARD_HINTS = (
    "drive_roots",
    "wide_exact",
    "forbidden root",
    "security_block",
    'startswith("e:")',
)

# Prose that merely *mentions* a path: comments and user-facing strings. The
# audit records them (so the inventory is complete) but the gate does not
# enforce them, because they carry no runtime machine assumption.
_MESSAGE_HINTS = ("such as", "refus", "error", "warn", "print(", "systemexit")


def _classify(kind: str, line: str) -> str:
    """Classify a live hit from its line context.

    The classification decides *which* kinds the gate enforces; the inventory
    remains the authoritative triage. The gate's job is to keep the *scope* of
    what is enforced stable, not to out-wit the inventory.
    """
    low = line.lower()
    # a deny-set / security check that *uses* drive paths is a guard, not a
    # machine assumption.
    if kind == "drive" and any(h in low for h in _GUARD_HINTS):
        return "guard"
    # prose (a comment, or a user-facing error string) is informational.
    stripped = line.lstrip()
    if (
        stripped.startswith("#")
        or (kind == "drive" and (stripped.startswith('"') or stripped.startswith("'")))
        or (kind == "drive" and any(h in low for h in _MESSAGE_HINTS))
    ):
        return "message"
    # an executable default is the genuine overridable-default violation.
    if kind == "drive" and ".exe" in low:
        return "violation"
    # env-first home / appdata reads are the *correct* locator inputs; record
    # them so the audit shows they were considered, not missed.
    if kind in ("env_home", "expanduser"):
        return "locator"
    # a bare drive path, or a COM / registry surface: a violation until
    # triaged in the inventory.
    return "violation"


def scan() -> list[dict]:
    """Return the live, fingerprinted machine-location findings across the scope."""
    findings: list[dict] = []
    for rel in _tracked():
        p = REPO_ROOT / rel
        try:
            text = p.read_text(encoding="utf-8")
        except Exception as exc:  # fail closed on any undecodable source file
            findings.append({
                "id": f"UNREADABLE:{rel}", "file": rel, "line": 0,
                "kind": "violation", "reason": f"undecodable source: {exc}",
                "snippet": "", "fingerprint": None, "pinned": False, "readable": False,
            })
            continue
        lines = text.splitlines()
        seen = set()
        for i, line in enumerate(lines, 1):
            for pkind, cre, label in PATTERNS:
                for m in cre.finditer(line):
                    frag = m.group(0)
                    # de-dup by (line, kind, fragment-start) so a line carrying two
                    # drive paths is two findings, not one blob.
                    key = (i, pkind, frag, m.start())
                    if key in seen:
                        continue
                    seen.add(key)
                    triage_kind = _classify(pkind, line)
                    fp = hashlib.sha1(
                        f"{rel}|{triage_kind}|{_normalise(frag)}".encode("utf-8")
                    ).hexdigest()[:16]
                    findings.append({
                        "id": fp, "file": rel, "line": i, "pattern_kind": pkind,
                        "kind": triage_kind, "reason": label,
                        "snippet": frag, "fingerprint": fp,
                    })
    return findings


def _inventory_schema_ok(inv: dict) -> list[str]:
    errs: list[str] = []
    if set(inv.get("policy", {}).get("triage_kinds", [])) != set(TRIAGE_KINDS):
        errs.append("inventory policy.triage_kinds must equal the gate's TRIAGE_KINDS "
                    f"({sorted(TRIAGE_KINDS)}) — the scope of the audit drifted")
    entries = inv.get("findings", [])
    for e in entries:
        for field in ("id", "file", "kind", "reason"):
            if field not in e:
                errs.append(f"inventory entry missing field {field!r}: {e}")
        if e.get("kind") not in TRIAGE_KINDS and e.get("kind") not in INFORMATIONAL_KINDS:
            errs.append(f"inventory entry has unknown kind {e.get('kind')!r}")
    return errs


def check(findings: list[dict], inv: dict) -> tuple[list[str], dict]:
    """Enforce the triage invariants. Returns (errors, stats)."""
    errors: list[str] = []
    errors += _inventory_schema_ok(inv)

    # An undecodable source file in the scan scope is a hard failure: the audit
    # must never silently narrow its scope by failing open on a file it could
    # not read.
    unreadable = [f for f in findings if not f.get("readable", True)]
    for f in unreadable:
        errors.append(
            f"UNREADABLE source file in the locator scan scope cannot be "
            f"audited (fail-closed): {f['file']} — {f.get('reason','')}")

    live = [f for f in findings if f.get("readable", True) and f.get("kind") in TRIAGE_KINDS]
    inv_entries = inv.get("findings", [])
    inv_by_fp = {e["id"]: e for e in inv_entries}

    untriaged = [f for f in live if f["fingerprint"] not in inv_by_fp]
    for f in untriaged:
        errors.append(
            f"UNTRIAGED machine-location assumption not in the locator inventory: "
            f"{f['file']}:{f['line']} [{f['kind']}] {f['snippet']!r} — add it to "
            f"adapter-locator-inventory.json with a classification + recommended "
            f"locator (or refactor it), then re-run this gate")

    # pinned entries must still be live (a refactored-away assumption is re-triaged).
    stale = [e for e in inv_entries if e.get("pinned") and e["id"] not in {f["fingerprint"] for f in live}]
    for e in stale:
        errors.append(
            f"STALE inventory entry pinned true no longer live: {e['file']} "
            f"[{e['kind']}] {e.get('reason','')} — the code changed; update the "
            f"inventory (un-pin or re-classify)")

    stats = {
        "scanned_files": len({f["file"] for f in findings}),
        "live_triage_findings": len(live),
        "inventory_entries": len(inv_entries),
        "untriaged": len(untriaged),
        "stale": len(stale),
        "violations": sum(1 for f in live if f["kind"] == "violation"),
        "guards": sum(1 for f in live if f["kind"] == "guard"),
        "locators": sum(1 for f in live if f["kind"] == "locator"),
        "informational": sum(1 for f in findings if f.get("kind") in INFORMATIONAL_KINDS),
    }
    return errors, stats


def _bootstrap_inventory(findings: list[dict]) -> dict:
    """Build the pre-filled inventory document from the live scan.

    The fingerprints are computed by the scanner itself, so whoever triages the
    document only fills in the classification fields and never hand-copies a
    fingerprint (the one class of mistake that would silently break the gate).
    """
    live = [f for f in findings if f.get("readable", True) and f.get("kind") in TRIAGE_KINDS]
    live.sort(key=lambda f: (f["file"], f["line"], f["kind"], f["id"]))
    return {
        "schemaVersion": "design-lab/adapter-locator-inventory/v1",
        "audit": "DL-CLOUDAUDIT-B4 / G-4 (CROSSWALK R10 — adapter hard-coded machine-location audit)",
        "generatedBy": "design-lab/scripts/verify_adapter_locator_audit.py --emit-inventory",
        "policy": {
            "triage_kinds": list(TRIAGE_KINDS),
            "note": (
                "kind 'violation' = a hard-coded machine location that should "
                "eventually become a locator (env-var / registry / PATH-first, "
                "fail-closed fallback); 'guard' = a fail-closed deny-set that "
                "intentionally names machine roots; 'locator' = a correct "
                "env-first locator input, recorded to show it was considered. "
                "Every entry stays pinned=true while the code still carries the "
                "assumption: when a refactor removes one, the gate reports it "
                "STALE and the inventory must be re-triaged."
            ),
        },
        "findings": [
            {
                "id": f["id"],
                "file": f["file"],
                "line": f["line"],
                "kind": f["kind"],
                "reason": f["reason"],
                "classification": "TODO-triage",
                "recommended_locator": "TODO-triage",
                "pinned": True,
            }
            for f in live
        ],
    }


def main() -> int:
    emit = "--emit-inventory" in sys.argv[1:]
    findings = scan()

    if emit:
        inv = _bootstrap_inventory(findings)
        INVENTORY.parent.mkdir(parents=True, exist_ok=True)
        INVENTORY.write_text(json.dumps(inv, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"ADAPTER_LOCATOR_AUDIT=EMIT inventory={INVENTORY.relative_to(REPO_ROOT)} "
              f"findings={len(inv['findings'])}")
        print("triage each entry (classification / recommended_locator), keep pinned=true while "
              "live, then re-run the gate without the flag")
        return 0

    if not INVENTORY.exists():
        # Bootstrap: the gate is the source of truth for the live findings. When
        # the inventory is absent we still scan and report what would be recorded,
        # and fail closed (an audit gate must never pass with no inventory).
        live = [f for f in findings if f.get("readable", True) and f["kind"] in TRIAGE_KINDS]
        for f in live:
            print(f"  {f['kind']:9s} {f['file']}:{f['line']}  {f['snippet']!r}  ({f['reason']})")
        print(f"ADAPTER_LOCATOR_AUDIT=FAIL missing_inventory live_triage_findings={len(live)}")
        print("run with --emit-inventory to generate the document to triage, "
              "or write it by hand; then re-run without the flag")
        return 1

    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    errors, stats = check(findings, inv)
    for e in errors:
        print("ERROR", e)
    verdict = "PASS" if not errors else "FAIL"
    print(
        f"ADAPTER_LOCATOR_AUDIT={verdict} "
        f"scanned_files={stats['scanned_files']} live={stats['live_triage_findings']} "
        f"inventory={stats['inventory_entries']} untriaged={stats['untriaged']} "
        f"stale={stats['stale']} violations={stats['violations']} "
        f"guards={stats['guards']} locators={stats['locators']} "
        f"informational={stats['informational']}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
