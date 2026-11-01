#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-EVD-001: verify SBOM (sbom-v42.spdx.json) integrity + vendored coverage.

Checks:
1. JSON parses and declares SPDX 2.3
2. SPDXID unique across packages
3. documentNamespace binds a known 12-char tree SHA
4. every vendor-adapt entry in SOURCE_REGISTRY appears as a package
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = Path(__file__).resolve().parents[2]
SBOM = ROOT / "config" / "sbom-v42.spdx.json"
REGISTRY = ROOT / "research" / "global-absorption" / "SOURCE_REGISTRY.json"
QUARANTINE = ROOT / "research" / "global-absorption" / "QUARANTINE_REGISTRY.json"
# G-2 / B2: lockfile-level SBOM coverage. Bound to the on-disk lockfiles at the
# repo root (pnpm + uv + requirements). Pure-stdlib: pnpm-lock is parsed with
# regex (the CI python venv has no PyYAML), uv.lock with tomllib.
LOCKFILE_NAMES = ("pnpm-lock.yaml", "uv.lock", "requirements.txt")

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_pnpm_lock(text: str) -> dict:
    """Parse the pnpm v9 lockfile `packages:` map with regex (no PyYAML dep).

    Returns {lockfileVersion, entries: {entryKey: {name, version, integrity,
    optional}}}. entryKey is the raw `name@version[(peers)]` string; a peer-
    suffix is stripped for the name/version split. Integrity is the per-entry
    `resolution.integrity` digest when present (absent on the pure-meta
    entries and the optional platform variants).
    """
    m = re.search(r"^lockfileVersion:\s*['\"]?([^'\n]+)['\"]?", text, re.M)
    version = m.group(1).strip() if m else None
    # Scope strictly to the `packages:` section: it ends at the next col-0
    # top-level marker (`snapshots:` / EOF). The snapshots section re-lists
    # every key WITHOUT resolution.integrity; parsing it would silently
    # overwrite every digest with null (a false lockfile-level guarantee).
    sec = re.search(r"^packages:\n(.*?)(?=^\S|\Z)", text, re.M | re.S)
    body = sec.group(1) if sec else ""
    entries: dict[str, dict] = {}
    for key, block in re.findall(r"^(  .+?):\n((?:^    .*\n)+)", body, re.M):
        k = key.strip()
        if k.endswith(":"):
            k = k[:-1]
        if k.startswith("'") and k.endswith("'") and len(k) > 1:
            k = k[1:-1]
        plain = re.sub(r"\(.*\)$", "", k)
        at = plain.rfind("@")
        name, ver = (plain[:at], plain[at + 1:]) if at > 0 else (plain, None)
        im = re.search(r"integrity:\s*([A-Za-z0-9+/=.\-]+)", block)
        entries[k] = {
            "name": name,
            "version": ver,
            "integrity": im.group(1) if im else None,
            "optional": "optional: true" in block,
        }
    return {"lockfileVersion": version, "entries": entries}


def _parse_uv_lock(text: str) -> dict:
    """Parse uv.lock (TOML) via tomllib: package -> resolved version + hashes."""
    doc = tomllib.loads(text)
    packages = {}
    for p in doc.get("package", []):
        ident = f"{p['name']}@{p['version']}"
        packages[ident] = {
            "sdist": (p.get("sdist") or {}).get("hash"),
            "wheels": [w.get("hash") for w in p.get("wheels", [])],
        }
    return {"lockVersion": doc.get("version"), "packages": packages,
            "packageCount": len(doc.get("package", []))}


def _requirement_pins(root: Path, text: str) -> list[str]:
    """Requirement spec strings, resolving top-level `-r` includes (no recursion)."""
    pins: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("-r "):
            inc = (root / s.split(" ", 1)[1]).resolve()
            if inc.is_file():
                pins.extend(_requirement_pins(root, inc.read_text(encoding="utf-8")))
            continue
        pins.append(s)
    return pins


def build_lockfile_bindings(repo_root: Path) -> dict:
    """Compute the `lockfileBindings` section for the SBOM (single source of
    truth, shared by the generator CLI and the integrity verifier)."""
    out: dict = {}
    for name in LOCKFILE_NAMES:
        p = repo_root / name
        if not p.is_file():
            continue
        if name == "pnpm-lock.yaml":
            parsed = _parse_pnpm_lock(p.read_text(encoding="utf-8"))
            out[name] = {
                "sha256": _sha256_file(p),
                "lockfileVersion": parsed["lockfileVersion"],
                "entryCount": len(parsed["entries"]),
                "integrityCount": sum(1 for e in parsed["entries"].values()
                                      if e["integrity"]),
                "manifest": parsed["entries"],
            }
        elif name == "uv.lock":
            parsed = _parse_uv_lock(p.read_text(encoding="utf-8"))
            out[name] = {
                "sha256": _sha256_file(p),
                "lockVersion": parsed["lockVersion"],
                "packageCount": parsed["packageCount"],
                "manifest": parsed["packages"],
            }
        elif name == "requirements.txt":
            out[name] = {"sha256": _sha256_file(p),
                         "pins": _requirement_pins(repo_root, p.read_text(encoding="utf-8"))}
    return out


def _verify_lockfile_bindings(sbom: dict, repo_root: Path) -> list[str]:
    findings: list[str] = []
    lb = sbom.get("lockfileBindings")
    if not lb:
        return ["SBOM missing lockfileBindings (run scripts/generate_sbom_lockfiles.py)"]
    for name in LOCKFILE_NAMES:
        p = repo_root / name
        if not p.is_file():
            continue
        b = lb.get(name)
        if b is None:
            findings.append(f"lockfileBindings missing entry for {name}")
            continue
        if b.get("sha256") != _sha256_file(p):
            findings.append(f"{name} changed since SBOM was generated "
                            "(sha256 mismatch) — regenerate lockfileBindings")
            continue
        if name == "pnpm-lock.yaml":
            reparsed = _parse_pnpm_lock(p.read_text(encoding="utf-8"))
            cur = {k: (v["name"], v["version"], v["integrity"]) for k, v in reparsed["entries"].items()}
            rec = {k: (v["name"], v["version"], v["integrity"]) for k, v in b["manifest"].items()}
            if cur != rec:
                findings.append(f"pnpm manifest drift: {len(cur)} on-disk vs "
                                f"{len(rec)} bound entries")
        elif name == "uv.lock":
            reparsed = _parse_uv_lock(p.read_text(encoding="utf-8"))
            if reparsed["packages"] != b["manifest"]:
                findings.append("uv.lock manifest drift from SBOM binding")
        elif name == "requirements.txt":
            cur = _requirement_pins(repo_root, p.read_text(encoding="utf-8"))
            if cur != b["pins"]:
                findings.append("requirements pins drift from SBOM binding")
    return findings


def check() -> list[str]:
    findings: list[str] = []

    try:
        sbom = json.loads(SBOM.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"SBOM unreadable: {exc}"]

    if not sbom.get("spdxVersion", "").startswith("SPDX-2."):
        findings.append(f"bad spdxVersion: {sbom.get('spdxVersion')}")

    ids = [p.get("SPDXID") for p in sbom.get("packages", [])]
    if len(ids) != len(set(ids)):
        findings.append("duplicate SPDXID in packages")
    if not ids:
        findings.append("SBOM has no packages")

    ns = sbom.get("documentNamespace", "")
    m = re.search(r"/([0-9a-f]{12})$", ns)
    if not m:
        findings.append("documentNamespace missing tree-SHA suffix")

    # vendored coverage (v3 active entries + quarantined legacy records)
    try:
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        vendored = [
            e["source"].get("sourceId", "?")
            for e in reg.get("entries", [])
            if e.get("integration", {}).get("mode") == "vendor-adapt"
        ]
        qreg = json.loads(QUARANTINE.read_text(encoding="utf-8"))
        vendored += [
            e.get("name")
            for e in qreg.get("entries", [])
            if e.get("originalRecord", {}).get("integration_mode") == "vendor-adapt"
            and e.get("originalRecord", {}).get("license_verified")
        ]
    except (OSError, json.JSONDecodeError) as exc:
        return findings + [f"REGISTRY unreadable: {exc}"]

    sbom_names = {p.get("name") for p in sbom.get("packages", [])}
    missing = [n for n in vendored if n not in sbom_names]
    if missing:
        findings.append(f"vendored packages missing from SBOM: {len(missing)} ({missing[:3]}...)")

    # G-2 / B2: lockfile-level integrity (pnpm + uv + requirements bindings)
    findings.extend(_verify_lockfile_bindings(sbom, REPO_ROOT))

    return findings


def main() -> int:
    findings = check()
    for f in sorted(findings):
        print(f"  {f}")
    if findings:
        print(f"\nVERIFY_SBOM=FAIL findings={len(findings)}")
        return 1
    print("\nVERIFY_SBOM=OK (SPDX 2.3 valid, SPDXID unique, vendored covered)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
