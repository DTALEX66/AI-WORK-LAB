"""Fetch each external row's LICENSE bytes, hash them, and show the first line.

Usage: python scripts/audit/licence_file_bytes.py [--out PATH]

This is the step that turns "GitHub's scanner says MIT" into "I read the document": the sha256 of the
file bytes goes into `licenseFileHash`, and the first non-empty line is quoted so the value in the
ledger is tied to specific bytes rather than to a detector's guess. Only rows whose licence came from
detection are processed; rows already confirmed from a file, the row mid-relicensing, and this repo's
own rows are left alone.
"""
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = (Path(__file__).resolve().parents[2] / ".project-local" / "runs" / "ci" /
       "licence_file_bytes.json")

DETECTION_ONLY = {
    "opa": "open-policy-agent/opa",
    "trivy": "aquasecurity/trivy",
    "actionlint": "rhysd/actionlint",
    "zizmor": "zizmorcore/zizmor",
    "cosign": "sigstore/cosign",
    "openinference-reference": "Arize-ai/openinference",
    "superpowers": "obra/superpowers",
    "promptfoo": "promptfoo/promptfoo",
    "otel-semconv": "open-telemetry/semantic-conventions-genai",
    "opentelemetry-genai-reference": "open-telemetry/semantic-conventions-genai",
    "agent-skills": "agentskills/agentskills",
    # the three rows whose value already came from an opened file, hashed here so every named
    # licence in the ledger carries bytes rather than a detector's opinion
    "conftest": "open-policy-agent/conftest",
    "in-toto": "in-toto/attestation",
    "ccusage-external-optional": "ccusage/ccusage",
}


def api(path: str) -> dict:
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path} exit={r.returncode}: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    out = Path(args.out)
    out = out if out.is_absolute() else REPO / out
    rows = []
    for rid, slug in DETECTION_ONLY.items():
        try:
            meta = api(f"repos/{slug}/license")
        except Exception as exc:  # noqa: BLE001 — reported, never turned into a silent pass
            print(f"FETCH_FAIL {rid} {slug}: {exc}")
            rows.append({"id": rid, "state": "FETCH_FAILED", "error": str(exc)[:200]})
            continue
        raw = base64.b64decode(meta["content"])
        digest = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8", "replace")
        first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        named = [ln.strip() for ln in text.splitlines()
                 if "License" in ln or "license" in ln][:2]
        rows.append({"id": rid, "state": "OK", "repo": slug, "licenseFileName": meta.get("name"),
                     "path": meta.get("path"), "bytes": len(raw), "sha256": digest,
                     "githubDetectionSpdx": (meta.get("license") or {}).get("spdx_id"),
                     "firstLine": first[:160], "licenseLines": named,
                     "matchesLedgerValueCheckNeeded": True})
        print(f"{rid:32s} {meta.get('name'):10s} {len(raw):>8,} B  sha256={digest[:16]}…  "
              f"detection={(meta.get('license') or {}).get('spdx_id')}")
        print(f"{'':32s} first line: {first[:120]}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"schemaVersion": "work-lab/licence-file-bytes/v1",
                               "fetchedVia": "gh api repos/{slug}/license (base64 content decoded)",
                               "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in rows if r["state"] == "OK")
    print(f"RESULT ok={ok} failed={len(rows) - ok} of {len(rows)} -> {out.name}")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
