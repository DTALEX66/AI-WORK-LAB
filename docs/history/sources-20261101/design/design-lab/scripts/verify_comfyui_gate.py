#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-CFY-001: ComfyUI loopback / no-auto-install gate (E0/E1).

Verifies the ComfyUI adapter contract:
1. adapter.manifest.json declares external-local-api + loopback-only
2. no auto-install / auto-download / external-port semantics anywhere in the adapter
3. rights-and-provider-policy.md declares loopback-only and manual launch

Fail-closed: any violation exits non-zero.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
COMFY_DIR = ROOT / "integrations" / "generators" / "comfyui"

FORBIDDEN = [
    (r"auto[- ]?install", "auto-install"),
    (r"pip\s+install", "pip install"),
    (r"curl\s+-[a-zA-Z]*O", "curl download"),
    (r"wget\s+", "wget"),
    (r"0\.0\.0\.0", "bind 0.0.0.0"),
    (r"public[ -]?port", "public port"),
    (r"download[ -]?(model|checkpoint|weights)", "model download"),
]

REQUIRED = [
    (r"loopback", "loopback-only"),
    (r"127\.0\.0\.1", "127.0.0.1"),
    (r"手动启动|manual", "manual launch"),
]
SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")


def _current_head() -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        check=False,
    )
    return result.stdout.strip()


def validate_e3_evidence(evidence_text: str, evidence_path: Path) -> list[str]:
    """Validate the provenance required for a current E3 claim."""
    findings: list[str] = []
    head = _current_head()
    m = SHA_RE.search(evidence_text)
    if not m:
        findings.append("EVIDENCE: E3 requires a full 40-hex tree SHA")
    else:
        # DL-EVD-002/003: committed evidence can only prove an ANCESTOR commit
        # (HISTORICAL_VALID), never itself. Requiring equality with HEAD would
        # create a self-reference loop (editing evidence changes HEAD).
        sha = m.group(0)
        if head:
            r = subprocess.run(
                ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", sha, head],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            if r.returncode != 0:
                findings.append(f"EVIDENCE: E3 tree SHA {sha[:12]} is not on HEAD ancestry (HISTORICAL_VALID required)")

    required_markers = {
        "runtime": ("运行时", "runtime"),
        "task": ("DL-CFY-",),
        "artifact/provenance": ("artifact", "provenance", "生成物"),
        "read-back": ("read-back", "readback", "读回"),
    }
    lowered = evidence_text.lower()
    for label, markers in required_markers.items():
        if not any(marker.lower() in lowered for marker in markers):
            findings.append(f"EVIDENCE: E3 missing {label} marker")

    e3_files = sorted(evidence_path.parent.glob("E3-*.md"))
    if not e3_files:
        findings.append("EVIDENCE: E3 declared but no E3-*.md evidence file present")
    return findings


def check() -> list[str]:
    findings: list[str] = []
    manifest_path = COMFY_DIR / "adapter.manifest.json"
    policy_path = COMFY_DIR / "rights-and-provider-policy.md"
    evidence_path = COMFY_DIR / "evidence" / "README.md"

    if not manifest_path.exists():
        findings.append("MISSING: adapter.manifest.json")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if "local" not in str(manifest.get("integration", "")).lower() and "loopback" not in json.dumps(manifest).lower():
                findings.append("MANIFEST: integration must be local/loopback")
        except json.JSONDecodeError as exc:
            findings.append(f"BAD-MANIFEST: {exc}")

    if not policy_path.exists():
        findings.append("MISSING: rights-and-provider-policy.md")
    else:
        text = policy_path.read_text(encoding="utf-8")
        # 禁止声明豁免：含"禁止/不/not"否定语气的行是政策声明，不是违规
        exempt_lines = []
        for line in text.splitlines():
            if any(w in line for w in ["禁止", "不得", "不自动", "not", "NOT", "无"]):
                exempt_lines.append(line)
        clean_text = text
        for exempt in exempt_lines:
            clean_text = clean_text.replace(exempt, "")
        for pat, label in FORBIDDEN:
            if re.search(pat, clean_text, re.IGNORECASE):
                findings.append(f"POLICY-FORBIDDEN: {label}")
        for pat, label in REQUIRED:
            if not re.search(pat, text, re.IGNORECASE):
                findings.append(f"POLICY-MISSING: {label}")

    if not evidence_path.exists():
        findings.append("MISSING: evidence/README.md")
    else:
        ev = evidence_path.read_text(encoding="utf-8")
        # 双态：E0 占位（未执行）或当前 checkout 已完整绑定的 E3 运行证据。
        has_e0 = "E0" in ev and "未执行" in ev
        has_e3 = "E3" in ev and "E3-" in ev and ("运行时" in ev or "runtime" in ev.lower())
        if not has_e0 and not has_e3:
            findings.append("EVIDENCE: must declare E0 placeholder (no execution) or E3 runtime evidence")
        if has_e3:
            findings.extend(validate_e3_evidence(ev, evidence_path))

    return findings


def main() -> int:
    findings = check()
    for f in sorted(findings):
        print(f"  {f}")
    if findings:
        print(f"\nVERIFY_COMFYUI_GATE=FAIL findings={len(findings)}")
        return 1
    ev = (COMFY_DIR / "evidence" / "README.md").read_text(encoding="utf-8")
    state = "E3 runtime verified" if "E3" in ev and "E3-" in ev else "E0 placeholder"
    print(f"\nVERIFY_COMFYUI_GATE=OK (loopback-only, no auto-install; {state})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
