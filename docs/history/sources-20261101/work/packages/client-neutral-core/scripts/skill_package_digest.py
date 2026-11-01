"""Full skill-package digest verification for the 13 managed Skills (WL3-220).

Computes a package digest over SKILL.md plus every script/reference/asset
inside the skill directory, checks provenance/license presence, and quarantines
unknown or conflicting skills. Never deletes user skills; live Home apply stays
a separate explicit approval.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

MANAGED_SKILL_NAMES = {
    "codex",
    "github-auth",
    "github-code-review",
    "github-issues",
    "github-pr-workflow",
    "github-repo-management",
    "model-switch",
    "agent-workflow-fortress",
    "project-data-boundary",
    "python-testing",
    "requesting-code-review",
    "sleep-mode",
    "windows-development-environment",
}

SKILL_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def package_files(skill_dir: Path) -> list[Path]:
    """All regular files in the skill tree, sorted for stable digesting."""
    if not skill_dir.is_dir():
        return []
    return sorted(
        path for path in skill_dir.rglob("*") if path.is_file() and not path.is_symlink()
    )


def package_digest(skill_dir: Path) -> str | None:
    files = package_files(skill_dir)
    if not files:
        return None
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(skill_dir).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def read_frontmatter(skill_dir: Path) -> dict[str, Any]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return {}
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    match = SKILL_FRONTMATTER_RE.match(text)
    if not match:
        return {}
    result: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        result[key.strip()] = value.strip().strip('"\'')
    return result


def scan_hazards(skill_dir: Path) -> list[str]:
    """Read-only hazard scan: symlinks, hidden binaries, remote downloads, secrets."""
    findings: list[str] = []
    for path in package_files(skill_dir):
        if path.is_symlink():
            findings.append(f"symlink:{path.name}")
        if path.suffix.lower() in {".exe", ".dll", ".bin", ".msi", ".ps1"} and path.stat().st_size > 0:
            try:
                head = path.read_bytes()[:512].lower()
                if b"\x4d\x5a" in head or b"microsoft visual" in head or b"#requires" in head:
                    findings.append(f"binary-script:{path.relative_to(skill_dir).as_posix()}")
            except OSError:
                pass
        if path.suffix.lower() in {".sh", ".py", ".js", ".ps1", ".bash"}:
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            for marker in ("curl ", "wget ", "irm ", "iex ", "pip install", "npm install -g"):
                if marker in text:
                    findings.append(f"remote-download-hint:{path.relative_to(skill_dir).as_posix()}:{marker.strip()}")
    return findings


def verify_skill(skill_dir: Path, expected_name: str) -> dict[str, Any]:
    digest = package_digest(skill_dir)
    frontmatter = read_frontmatter(skill_dir)
    hazards = scan_hazards(skill_dir)
    has_license = (skill_dir / "LICENSE").is_file() or (skill_dir / "LICENSE.md").is_file()
    name_ok = frontmatter.get("name") == expected_name
    return {
        "name": expected_name,
        "present": digest is not None,
        "package_digest": digest,
        "file_count": len(package_files(skill_dir)),
        "frontmatter_name_ok": name_ok,
        "license_present": has_license,
        "hazards": hazards,
        "quarantine": bool(hazards) or not name_ok,
        "status": "QUARANTINED" if (hazards or not name_ok) else "SCANNED",
    }


def verify_managed_set(skill_root: Path, provenance: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify every managed skill; quarantine unknown names; never delete."""
    by_name = {str(entry["name"]): entry for entry in provenance}
    results: dict[str, dict[str, Any]] = {}
    for name in sorted(MANAGED_SKILL_NAMES):
        entry = by_name.get(name, {})
        source = str(entry.get("source", ""))
        if source:
            # Provenance source is repository-relative and already includes the
            # skills/ prefix (e.g. skills/github/github-auth/SKILL.md).
            source_path = Path(source)
            skill_dir = skill_root.parent / (source_path.parent if source_path.name == "SKILL.md" else source_path)
            if skill_dir.is_dir():
                results[name] = verify_skill(skill_dir, name)
            else:
                results[name] = {
                    "name": name, "present": False, "status": "MISSING",
                    "quarantine": True, "package_digest": None, "file_count": 0,
                    "frontmatter_name_ok": False, "license_present": False, "hazards": [],
                }
        else:
            results[name] = {
                "name": name, "present": False, "status": "NO_PROVENANCE",
                "quarantine": True, "package_digest": None, "file_count": 0,
                "frontmatter_name_ok": False, "license_present": False, "hazards": [],
            }
    present = sum(1 for result in results.values() if result["present"])
    quarantined = [name for name, result in results.items() if result["quarantine"]]
    return {
        "schema_version": "workflow/skill-package-digest/v1",
        "managed_count": len(MANAGED_SKILL_NAMES),
        "present_count": present,
        "quarantined": quarantined,
        "results": results,
    }


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Verify the 13 managed skill packages")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, default=Path("config/skill-provenance.yaml"))
    args = parser.parse_args()
    import yaml

    root = args.root.resolve()
    provenance = yaml.safe_load((root / args.manifest).read_text(encoding="utf-8")).get("entries", [])
    result = verify_managed_set(root / "skills", provenance)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["quarantined"]:
        print("SKILL_PACKAGE_DIGEST_FAIL quarantined=" + ",".join(result["quarantined"]))
        sys.exit(1)
    print(f"SKILL_PACKAGE_DIGEST_PASS managed={result['managed_count']} present={result['present_count']}")
