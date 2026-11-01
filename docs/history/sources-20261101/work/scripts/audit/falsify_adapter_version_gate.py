"""Falsify the adapter version-readback gate: write each lie it claims to catch, prove it turns red.

The gate guards a pairing (registry claim <-> receipt bytes), so the mutations are made on copies of both
files and restored by SHA-256 afterwards. A gate that survives all seven is not a gate.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "config/adapter-registry.json"
REC = ROOT / "docs/audits/TOOL_VERSION_METADATA_PROBE_2026-10-07.json"
TEST = "tests/workflow-assistance/test_adapter_version_readback.py"
ORIGINAL = {REG: REG.read_bytes(), REC: REC.read_bytes()}


def load(path: Path) -> dict:
    return json.loads(ORIGINAL[path].decode("utf-8"))


def write(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def entry(doc: dict, adapter: str) -> dict:
    return next(e for e in doc["entries"] if e["id"] == adapter)


def mut_version_disagrees_with_readback() -> None:
    doc = load(REG)
    entry(doc, "github")["provenance"]["version"] = "2.99.0"
    write(REG, doc)


def mut_placeholder_as_verified() -> None:
    doc = load(REG)
    entry(doc, "github")["provenance"]["version_readback"]["verified_version"] = "UNVERIFIED"
    write(REG, doc)


def mut_receipt_says_otherwise() -> None:
    doc = load(REC)
    doc["results"]["github"]["fileVersion"] = "9.9.9"
    write(REC, doc)


def mut_readback_buys_detection_state() -> None:
    doc = load(REG)
    entry(doc, "openhuman")["detection"]["evidence_state"] = "PASS"
    write(REG, doc)


def mut_declarative_client_observed() -> None:
    doc = load(REG)
    prov = entry(doc, "cursor")["provenance"]
    prov["version"] = "1.2.3"
    prov["version_readback"] = {"observed_at": "2026-10-07", "verified_version": "1.2.3",
                                "method": "windows-file-version-resource"}
    write(REG, doc)


def mut_undated_observation() -> None:
    doc = load(REG)
    entry(doc, "cc-switch")["provenance"]["version_readback"]["observed_at"] = ""
    write(REG, doc)


def mut_receipt_admits_launch() -> None:
    doc = load(REC)
    doc["launchedAnyProcessForVersion"] = True
    write(REC, doc)


MUTATIONS = [
    ("registry version disagrees with its own readback", mut_version_disagrees_with_readback),
    ("a placeholder becomes a verified version", mut_placeholder_as_verified),
    ("the receipt says a different number than the registry", mut_receipt_says_otherwise),
    ("a version readback buys a detection state", mut_readback_buys_detection_state),
    ("a declarative-only client grows an observation", mut_declarative_client_observed),
    ("an undated observation", mut_undated_observation),
    ("the receipt admits it launched the binaries", mut_receipt_admits_launch),
]


def run_gate() -> int:
    return subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", TEST, "-q"],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace").returncode


undetected = []
for name, mutate in MUTATIONS:
    try:
        mutate()
        code = run_gate()
        print(f"{name}: exit={code}")
        if code == 0:
            undetected.append(name)
    finally:
        for path, data in ORIGINAL.items():
            path.write_bytes(data)

digests = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:12] for p in ORIGINAL}
expected = {p.name: hashlib.sha256(d).hexdigest()[:12] for p, d in ORIGINAL.items()}
print("restored", digests, "ok" if digests == expected else "RESTORE_FAILED")
if digests != expected:
    sys.exit(4)
print("baseline after restore: exit=", run_gate())
if undetected:
    print("GATE CANNOT SEE: " + "; ".join(undetected))
    sys.exit(1)
print("all mutations detected")
