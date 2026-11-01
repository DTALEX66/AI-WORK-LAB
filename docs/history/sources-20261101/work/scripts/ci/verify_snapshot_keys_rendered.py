"""Gate: every snapshot key the contract pins must be consumed by the Observer's own source.

The key list is read out of the frontend's pinned-refinement array, not retyped here, so growing the
contract cannot leave this gate describing an older world. A key that appears only in type/contract files
or inside a comment is not surfaced to anyone: it is an unrendered fact. That is exactly how
`artifactHandles` and `artifactHandlesSummary` (200 projected rows, cap 200 of 4,898 enumerated) sat
invisible while the v3 snapshot carried them.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CONTRACT_REL = "apps/observer/frontend/src/contractConformance.ts"
SRC_REL = "apps/observer/frontend/src"
# Type and contract declarations name keys without rendering anything, so they never count as coverage.
NON_RENDER_NAMES = {"types.ts", "contractConformance.ts"}
NON_RENDER_DIRS = {"test"}


def pinned_keys(contract_path: Path) -> list[str]:
    text = contract_path.read_text(encoding="utf-8")
    match = re.search(r"export const PINNED_REFINEMENT_PATHS = \[(.*?)\] as const", text, re.S)
    if not match:
        raise SystemExit(f"SNAPSHOT_KEYS_UNREADABLE: the pinned refinement array was not found in "
                         f"{contract_path}")
    keys = re.findall(r"'([^']+)'", match.group(1))
    if not keys:
        raise SystemExit("SNAPSHOT_KEYS_EMPTY: the pinned array parsed to zero keys")
    return keys


def code_lines(text: str) -> str:
    """Drop comment lines, because a comment that names a key renders nothing."""
    kept = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("//", "*", "/*", "///")):
            continue
        kept.append(line.split("//")[0])
    return "\n".join(kept)


def ui_files(src: Path) -> list[Path]:
    found = []
    for path in sorted(src.rglob("*.ts*")):
        if not path.is_file() or path.name in NON_RENDER_NAMES or ".test." in path.name:
            continue
        if path.relative_to(src).parts[0] in NON_RENDER_DIRS:
            continue
        found.append(path)
    return found


def consumers(key: str, files: list[Path]) -> list[str]:
    """Member access, bracket access, or a destructure pattern is the only form that reads a value.

    Measured on this repo: `views/IsolatedTrialView.tsx` uses `snap?.operationProgress`, a component may
    destructure `const { artifactHandles } = snap`, and prose inside a comment uses neither form.
    """
    hits = []
    escaped = re.escape(key)
    pattern = re.compile(r"(?:\?\.|\.)" + escaped + r"(?![\w])|"
                         r"[\[{,]\s*[\"']" + escaped + r"[\"']\s*[\]},:]|"
                         r"[\[{,]\s*" + escaped + r"\s*[,}\]]")
    for path in files:
        text = code_lines(path.read_text(encoding="utf-8", errors="replace"))
        match = pattern.search(text)
        if match:
            line = text[: match.start()].count("\n") + 1
            hits.append(f"{path.name}:{line}")
    return hits


def analyze(root: Path) -> dict:
    src = root / SRC_REL
    if not src.is_dir():
        raise SystemExit(f"SNAPSHOT_KEYS_NO_SRC: {src} is not a directory")
    keys = pinned_keys(root / CONTRACT_REL)
    files = ui_files(src)
    unrendered = [key for key in keys if not consumers(key, files)]
    return {"keys": keys, "files": len(files), "unrendered": unrendered}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", type=Path)
    args = parser.parse_args()
    result = analyze(args.root)
    unrendered = result["unrendered"]
    print(f"SNAPSHOT_KEYS_CONSUMED scanned_files={result['files']} keys={len(result['keys'])} "
          f"rendered={len(result['keys']) - len(unrendered)} unrendered={len(unrendered)} "
          + " ".join(unrendered))
    if unrendered:
        print("SNAPSHOT_KEYS_FAIL: the snapshot declares these keys but no Observer source consumes "
              "them, so the fact never reaches a reader")
        return 1
    print("SNAPSHOT_KEYS_PASS every pinned snapshot key is consumed by the interface source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
