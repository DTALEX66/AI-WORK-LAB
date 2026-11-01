#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate a non-destructive Git size report and budget status."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "design-lab" / "config" / "repository-size-report.json"
WARNING_MIB = 224.0
LIMIT_MIB = 256.0


def git(*args: str) -> str:
    result = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def main() -> int:
    pack = git("count-objects", "-vH")
    values = dict(line.split(":", 1) for line in pack.splitlines() if ":" in line)
    size_pack = float(values.get("size-pack", "0 MiB").strip().split()[0])
    blobs = []
    for line in git("ls-tree", "-rl", "HEAD").splitlines():
        meta, path = line.split("\t", 1)
        mode, kind, object_id, size = meta.split()
        if kind == "blob":
            blobs.append({"path": path, "bytes": int(size), "objectId": object_id})
    blobs.sort(key=lambda item: (-item["bytes"], item["path"]))
    status = "OVER_LIMIT" if size_pack > LIMIT_MIB else "WARNING" if size_pack >= WARNING_MIB else "OK"
    measured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = {"schemaVersion": "design-lab/repository-size-report/v1", "subjectSha": git("rev-parse", "HEAD"),
               "generatedAt": measured_at, "measuredAt": measured_at, "measuredPackMiB": size_pack,
               "packMiB": size_pack, "warningMiB": WARNING_MIB, "limitMiB": LIMIT_MIB, "status": status,
               "largestTrackedBlobs": blobs[:20], "historyRewriteAuthorized": False,
               "thresholdBasis": "thresholds re-validated against this measurement (DLDS-D050); the "
                                 "pack size is dominated by history, not by the current tree",
               "liveCheck": "python scripts/generate_repository_size_report.py --check",
               "note": "This report is observational. It does not delete blobs, rewrite history, or approve new binaries."}
    if "--check" in sys.argv:
        if not OUT.is_file():
            print("REPOSITORY_SIZE=FAIL missing report; run without --check")
            return 1
        recorded = json.loads(OUT.read_text(encoding="utf-8"))
        if recorded.get("measuredPackMiB") != size_pack:
            print(f"REPOSITORY_SIZE=DRIFT recorded={recorded.get('measuredPackMiB')} "
                  f"live={size_pack}; re-measure instead of reusing the old number")
            return 1
        print(f"REPOSITORY_SIZE=CHECK_PASS pack_mib={size_pack:.2f} status={status}")
        return 0
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"REPOSITORY_SIZE=PASS status={status} pack_mib={size_pack:.2f} blobs={len(blobs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
