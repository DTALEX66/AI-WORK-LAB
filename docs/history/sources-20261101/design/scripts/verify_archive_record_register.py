#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Re-derive the archive-wave register from git and fail if the written section disagrees.

`scripts/generate_archive_record_register.py` builds the register from the repository; this is the
other half — it parses the section back out of `docs/RECORD-ARCHIVE-INDEX.md` as a reader would see
it and re-derives every cited value from the committed blob. It catches the failure modes that a
generator cannot: two columns transposed, the bullet list disagreeing with the table, a section left
behind pointing at a hash that no longer exists, or a stale path written into a register whose whole
purpose is to stop stale paths being read.

Read-only. Never touches a record, so it is safe to run at any time.

Coverage note, because this is where a session learns the rule the hard way: the register is a
member of the CI `top-authority-gate` job but NOT of `verify_design_lab.py`'s aggregate (that chain
resolves its members under `design-lab/`, and these two record gates live in the repo-root `scripts/`
tree). So the one local command that otherwise covers the authority surface does not cover this one,
and `docs/audits/DESIGN-LAB-ARCHIVE-AND-REMOVAL-2026-10-19.md` is one of the five registered records
-- editing it invalidates the register and only this script says so. Run it, plus
`scripts/record_import_verify.py --head`, after touching any registered record or any file the Record
import manifest holds to a repository digest.

    python scripts/verify_archive_record_register.py
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "docs" / "RECORD-ARCHIVE-INDEX.md"
HEADING = "## 2026-10-19 新增：归档与移除波次的五份记录（owner 2026-10-19 指令）"
PATHISH = re.compile(r"^(?:docs|reports|scripts|src|design-lab|packages|fixtures|evals|apps)/")

checks: list[str] = []
problems: list[str] = []


def git(*args: str) -> bytes:
    done = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True)
    if done.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {done.stderr.decode('utf-8', 'replace').strip()}")
    return done.stdout


def section_or_none() -> str | None:
    if not INDEX.exists():
        problems.append("docs/RECORD-ARCHIVE-INDEX.md is missing")
        return None
    raw = INDEX.read_bytes()
    if b"\r" in raw:
        problems.append("register index changed newline shape (CR present on disk)")
    text = raw.decode("utf-8", "replace")
    if "\ufffd" in text:
        problems.append("register index contains a replacement character")
    parts = text.split(HEADING, 1)
    if len(parts) != 2:
        problems.append("register heading is absent — the wave's five records are not registered")
        return None
    if HEADING in parts[1]:
        problems.append("register heading appears twice; the generator is not idempotent")
        return None
    return parts[1]


def main() -> int:
    body = section_or_none()
    if body is None:
        print(f"RECORD_REGISTER_GATE=FAIL checks={len(checks)} problems={problems!r}")
        return 1

    # `-z`, not newline splitting: git porcelain octal-quotes non-ASCII paths, so `ls-files` text
    # would read a landed Chinese-named member as `"docs/...\345\261\202..."` and convict a register
    # row or a section path that is actually tracked. Observed 2026-10-23 on the Record package whose
    # 17 members are named in Chinese.
    tracked = set(git("ls-files", "-z").decode("utf-8").split("\0"))
    tracked.discard("")
    rows = re.findall(r"^\| (\d) \| `([^`]+)` \|[^|]*\|[^|]*\| `([0-9a-f]{12})` \| ([\d,]+) B \| "
                      r"`([0-9a-f]{16})…`", body, re.M)
    bullets = re.findall(r"^- (\d)\. `([^`]+)` → `([0-9a-f]{64})`", body, re.M)
    by_num = {n: (p, h) for n, p, h in bullets}

    if len(rows) != 5:
        problems.append(f"expected 5 register rows, parsed {len(rows)}")
    else:
        checks.append("row count")
    if len(by_num) != 5:
        problems.append(f"expected 5 full digests, parsed {len(by_num)}")
    else:
        checks.append("digest count")

    for idx, path, sha1_claim, bytes_claim, prefix_claim in rows:
        if path not in tracked:
            problems.append(f"row {idx}: {path} is not a tracked file")
            continue
        blob = git("cat-file", "blob", f"HEAD:{path}")
        sha1 = git("rev-parse", f"HEAD:{path}").decode().strip()
        digest = hashlib.sha256(blob).hexdigest()
        if sha1[:12] != sha1_claim:
            problems.append(f"row {idx}: blob SHA-1 claim {sha1_claim} vs {sha1[:12]}")
        if f"{len(blob):,}" != bytes_claim:
            problems.append(f"row {idx}: bytes claim {bytes_claim} vs {len(blob):,}")
        if digest[:16] != prefix_claim:
            problems.append(f"row {idx}: SHA-256 prefix claim {prefix_claim} vs {digest[:16]}")
        pair = by_num.get(idx)
        if pair is None:
            problems.append(f"row {idx}: no matching full-digest bullet")
        elif pair != (path, digest):
            problems.append(f"row {idx}: bullet disagrees with table (path or digest)")
    if rows:
        checks.append("per-row blob identity")

    for idx, path, digest in bullets:
        if path not in tracked:
            problems.append(f"bullet {idx}: {path} is not a tracked file")
        elif hashlib.sha256(git("cat-file", "blob", f"HEAD:{path}")).hexdigest() != digest:
            problems.append(f"bullet {idx}: digest no longer matches the committed blob")
    if bullets:
        checks.append("bullet digests re-derived")

    tokens = set(re.findall(r"`([^`\n]+)`", body))
    named = 0
    for token in tokens:
        if "<" in token or "：" in token:
            continue
        for cand in token.split(" · "):
            cand = cand.strip()
            if not PATHISH.match(cand):
                continue
            named += 1
            root = cand[:-3] if cand.endswith("/**") else cand
            if cand in tracked or root.rstrip("/") in tracked:
                continue
            if (REPO / root).is_dir():
                continue
            problems.append(f"register names an unresolvable path: {cand}")
    if named:
        checks.append(f"path-shaped tokens resolved ({named})")

    print(f"RECORD_REGISTER_GATE={'PASS' if not problems else 'FAIL'} "
          f"checks={len(checks)} pathish_named={named} problems={len(problems)}")
    for problem in problems:
        print("PROBLEM", problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
