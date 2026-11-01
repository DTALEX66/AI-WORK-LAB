"""Measure whether the tracked tree carries secret-shaped values, without disclosing them.

The repository is PUBLIC on GitHub, and `reports/audit-archive/` holds copies of files that were
scanned out of the user's own home directories during a 2026-09-30 audit. A name-based rule cannot
answer "is this file exposed", because the question is about the bytes, so this tool answers it by
matching secret *shapes* and reporting only the pattern name, the number of matches and the key
path they hang off of.

It deliberately never prints, and never stores, a matched value or any surrounding text: a report
that carried values would turn a leak into a second, wider one.

    python scripts/audit/tracked_secret_shape_scan.py [--out PATH] [--scope PREFIX ...]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Each entry is (name, regex). The regexes match assignments/headers, not prose about them:
# `token =` alone would fire on every documentation file in the repo.
VALUE = r"[A-Za-z0-9_\-\.\/+]{12,}"
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("github-pat", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}")),
    ("github-fine-grained", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{12,}")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b")),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}")),
    ("azure-blob-sas", re.compile(r"[?&]sig=[A-Za-z0-9%]{20,}")),
    ("bearer-token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{20,}")),
    ("secret-assignment", re.compile(
        r"(?i)\b(password|passwd|secret|api_?key|access_?token|refresh_?token|client_?secret|"
        r"auth_?token|private_?key|token)\b\s*[:=]\s*[\"']?" + VALUE)),
)

# Keys whose *name* is a secret word but whose value is a placeholder are not exposure; report the
# shape hit anyway and let the operator read the file under an authorised session. This tool's job
# is to say where to look, not to adjudicate.
BINARY_SNIFF = b"\x00"

# A match inside these words is prose about credentials, not a credential.
PROSE_GUARDS = ("example", "placeholder", "your-", "your_", "<", "***", "redacted", "changeme")


def tracked_files(scope_prefixes: tuple[str, ...]) -> list[str]:
    raw = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True).stdout
    paths = [p.decode("utf-8", "replace") for p in raw.split(b"\x00") if p]
    if not scope_prefixes:
        return paths
    return [p for p in paths if p.startswith(scope_prefixes)]


def blob(rel: str) -> tuple[bool, bytes]:
    """Read from the committed tree: the exposure question is about what was published.

    Returns (present_in_head, bytes). An empty file is present with zero bytes, which is a
    different fact from "this path is not in HEAD at all" -- collapsing the two made a directory
    of `.gitkeep` placeholders look like unscanned coverage.
    """
    proc = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=REPO, capture_output=True)
    return proc.returncode == 0, proc.stdout


def scan_text(text: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for name, pattern in PATTERNS:
        for match in pattern.finditer(text):
            matched = match.group(0)
            if any(guard in matched.lower() for guard in PROSE_GUARDS):
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            findings.append({
                "pattern": name,
                "line": line_no,
                "matchedLength": len(matched),
                # the key name only: `openai.api_key` tells the operator where to look without
                # being a value
                "keyHint": match.group(1).lower() if match.groups() else "",
            })
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".project-local/artifacts/SECRET_SHAPE_SCAN_HEAD.json")
    ap.add_argument("--scope", nargs="*", default=[])
    args = ap.parse_args()

    scopes = tuple(args.scope)
    files = tracked_files(scopes)
    affected: list[dict[str, object]] = []
    scanned = 0
    skipped_binary = 0
    not_in_head: list[str] = []
    for rel in files:
        present, data = blob(rel)
        if not present:
            # A name in `git ls-files` with no HEAD blob is a staged-new or odd-symlink entry. A
            # scan that dropped these silently would report coverage it never had, so the gap is
            # counted and published rather than absorbed.
            not_in_head.append(rel)
            continue
        if not data:
            scanned += 1
            continue
        if BINARY_SNIFF in data[:4096]:
            skipped_binary += 1
            continue
        scanned += 1
        text = data.decode("utf-8", "replace")
        findings = scan_text(text)
        if findings:
            patterns = sorted({str(f["pattern"]) for f in findings})
            affected.append({
                "path": rel,
                "bytes": len(data),
                "matchCount": len(findings),
                "patterns": patterns,
                "lines": [f["line"] for f in findings][:40],
                "keyHints": sorted({str(f["keyHint"]) for f in findings if f["keyHint"]})[:20],
            })

    report = {
        "schema": "work-lab/tracked-secret-shape-scan/v1",
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                               capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip(),
        "repoVisibility": "public (GitHub API read at scan time by the operator)",
        "scope": list(scopes) or ["<whole tracked tree>"],
        "filesScanned": scanned,
        "filesSkippedBinary": skipped_binary,
        "filesNotInHead": len(not_in_head),
        "filesNotInHeadPaths": sorted(not_in_head)[:50],
        "filesWithSecretShapes": len(affected),
        "totalMatches": sum(int(a["matchCount"]) for a in affected),
        "disclosurePolicy": "no matched value, no surrounding text, no line content is recorded",
        "findings": affected,
    }
    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"SECRET_SHAPE_SCAN scanned={scanned} binary_skipped={skipped_binary} "
          f"not_in_head={len(not_in_head)} "
          f"affected_files={len(affected)} matches={report['totalMatches']}")
    for a in affected:
        print(f"  {a['path']} bytes={a['bytes']} matches={a['matchCount']} "
              f"patterns={','.join(a['patterns'])}")
    print(f"receipt -> {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
