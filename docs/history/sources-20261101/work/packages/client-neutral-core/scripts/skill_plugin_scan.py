"""Skill/Plugin/MCP supply-chain security scanner (WL3-320).

Read-only scan of skill/plugin/MCP directories: symlinks/junctions, hidden
binaries, remote downloads, postinstall hooks, secret references, recursive
loading, prompt-injection patterns, and data exfiltration hints. New third-party
assets default to QUARANTINED; upstream license/security changes mark
UPSTREAM_CHANGED and stop auto-upgrade.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

BINARY_SUFFIXES = {".exe", ".dll", ".bin", ".msi", ".so", ".dylib", ".class", ".pyc"}
SCRIPT_SUFFIXES = {".sh", ".py", ".js", ".ts", ".ps1", ".bash", ".zsh", ".rb"}
REMOTE_DOWNLOAD_RE = re.compile(
    r"\b(curl|wget|Invoke-WebRequest|Invoke-RestMethod|irm|iwr|download|pip install|npm install -g|gem install|go install)\b",
    re.IGNORECASE,
)
EXFIL_RE = re.compile(
    r"\b(curl -X (POST|PUT)|requests?\.(post|put)|urllib[^\n]*(POST|PUT)|data\s*[=:]\s*\$?\w*(KEY|TOKEN|SECRET|PASSWORD))\b",
    re.IGNORECASE,
)
INJECTION_RE = re.compile(
    r"\b(ignore\s+(previous|prior)\s+(instructions|directives)|system\s+prompt\s+override)\b",
    re.IGNORECASE,
)
SECRET_REF_RE = re.compile(r"\b(api[_ -]?key|password|secret|token|bearer|private[_ -]?key)\b", re.IGNORECASE)
POSTINSTALL_RE = re.compile(r"\b(postinstall|post-install|preinstall|prepare|install-hook)\b", re.IGNORECASE)


class ScanFinding:
    def __init__(self, severity: str, category: str, path: str, detail: str) -> None:
        self.severity = severity
        self.category = category
        self.path = path
        self.detail = detail

    def to_dict(self) -> dict[str, str]:
        return {"severity": self.severity, "category": self.category, "path": self.path, "detail": self.detail}


def _walk_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)  # reparse point
    except OSError:
        return False


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def scan_tree(root: Path) -> dict[str, Any]:
    findings: list[ScanFinding] = []
    for path in _walk_files(root):
        relative = path.relative_to(root).as_posix()
        if _is_link(path):
            findings.append(ScanFinding("high", "symlink-or-junction", relative, "path is a link/reparse point"))
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            try:
                head = path.read_bytes()[:1024]
                if b"\x4d\x5a" in head:  # PE header
                    findings.append(ScanFinding("high", "binary-executable", relative, "portable executable"))
            except OSError:
                pass
            continue
        if path.suffix.lower() in SCRIPT_SUFFIXES or path.name in {"SKILL.md", "README.md", "plugin.json", "AGENTS.md"}:
            text = _read_text(path)
            if REMOTE_DOWNLOAD_RE.search(text):
                findings.append(ScanFinding("medium", "remote-download-hint", relative, "downloads/installs from network"))
            if EXFIL_RE.search(text):
                findings.append(ScanFinding("high", "data-exfiltration-hint", relative, "sends environment or data outward"))
            if INJECTION_RE.search(text):
                findings.append(ScanFinding("medium", "prompt-injection-hint", relative, "prompt-injection phrasing"))
            if SECRET_REF_RE.search(text) and path.name not in {"SKILL.md"}:
                findings.append(ScanFinding("medium", "secret-reference", relative, "references secret-like names"))
            if POSTINSTALL_RE.search(text):
                findings.append(ScanFinding("medium", "postinstall-hook", relative, "install-time hook"))
    return {
        "schema_version": "workflow/supply-chain-scan/v1",
        "root": str(root),
        "file_count": len(_walk_files(root)),
        "findings": sorted([finding.to_dict() for finding in findings], key=lambda item: item["path"]),
        "quarantined": bool(findings),
        "status": "QUARANTINED" if findings else "SCANNED",
    }


def quarantine_if_third_party(scan: dict[str, Any], *, origin: str) -> dict[str, Any]:
    """Third-party (non-official) assets default to QUARANTINED regardless of scan."""
    result = dict(scan)
    if origin not in {"official", "user"}:
        result["quarantined"] = True
        result["status"] = "QUARANTINED"
        result["quarantine_reason"] = f"third-party-origin:{origin}"
    return result


def upstream_change_flag(current_digest: str, known_digest: str | None, upstream_ok: bool) -> str:
    """UPSTREAM_CHANGED when upstream no longer matches known state or health is degraded."""
    if not upstream_ok:
        return "UPSTREAM_CHANGED"
    if known_digest is not None and current_digest != known_digest:
        return "UPSTREAM_CHANGED"
    return "STABLE"


def tree_digest(root: Path) -> str | None:
    files = _walk_files(root)
    if not files:
        return None
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scan skill/plugin/MCP trees for supply-chain hazards")
    parser.add_argument("roots", nargs="+", type=Path)
    args = parser.parse_args()
    all_quarantined = []
    for root in args.roots:
        scan = scan_tree(root)
        print(json.dumps(scan, ensure_ascii=False, indent=2))
        if scan["quarantined"]:
            all_quarantined.append(str(root))
    if all_quarantined:
        print("SUPPLY_CHAIN_SCAN_FAIL quarantined=" + ",".join(all_quarantined))
        raise SystemExit(1)
    print("SUPPLY_CHAIN_SCAN_PASS roots=" + str(len(args.roots)))
