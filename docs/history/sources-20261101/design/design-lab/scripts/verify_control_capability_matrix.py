#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Host control capability matrix verifier (P1-CONTROL-SPIKE) — fail-closed, stdlib only.

The matrix (``design-lab/config/control-capability-matrix.json``) is a
*capability routing declaration*, not a runtime proof. It declares, per host,
how DESIGN-LAB reaches it (``reachability_model``) and where the truth comes
from (``truth_model``) plus the capability levels each control path actually
has evidence for. The task-book principle encoded here:

    Computer-Use 负责 reachability（能不能够到宿主 UI）
    Host-native readback / artifact rehash 负责 truth（宿主里究竟发生了什么）
    DESIGN-LAB State/Evidence 层负责 provenance

This verifier's job is deliberately asymmetric and fails closed:

* a matrix whose structure / values violate the schema must fail;
* a capability declared ``supported: true`` with ``evidence_level`` below E2
  (E0/E1) must fail — capability claims must not outrun the evidence;
* a capability declared ``supported: true`` with no ``qualified_sha`` must
  fail — a live claim is unlocatable;
* ``authorization.no_bypass_license`` must be true on every host (task-book
  red line: never bypass Adobe/MiniMax licensing);
* a host whose reachability is ``computer-use`` must have a non-"none"
  ``truth_model`` — a GUI that can reach but has no native/artifact truth
  layer is exactly the "能点 Photoshop 不等于解决集成" trap;
* the matrix must cover at least the ``browser`` and ``minimax-design``
  hosts (the two declared adapter-matrix entries that have a routing
  contract).

It never promotes a capability level. Promoting E0 -> E2+ stays a
human/owner decision bound to a real exact-SHA run.

Usage:
    python design-lab/scripts/verify_control_capability_matrix.py [--matrix PATH]

Output contract (one line, machine-parsed):
    CONTROL_CAPABILITY_MATRIX=<PASS|FAIL> hosts=N capabilities=M findings=[...]

Exit code: 0 for PASS, 1 for FAIL.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_MATRIX = REPO / "design-lab" / "config" / "control-capability-matrix.json"
SCHEMA_PATH = REPO / "design-lab" / "schemas" / "control-capability-matrix.schema.json"

MIN_HOSTS = {"browser", "minimax-design"}
MIN_EVIDENCE_FOR_SUPPORTED = "E2"
_LEVELS = ["E0", "E1", "E2", "E3", "E4", "E5"]
_TRANSPORTS = {"native", "script", "computer-use", "cloud-api"}
_REACHABILITY = {"computer-use", "native-launch", "none"}
_TRUTH = {"host-native-readback", "artifact-rehash", "none"}
_CAP_NAMES = {"launch", "inspect", "create", "patch",
              "save-editable", "export", "reopen-verify", "readback"}


def _level_rank(level: str) -> int:
    return _LEVELS.index(level) if level in _LEVELS else -1


def _hex_sha_ok(value) -> bool:
    if not isinstance(value, str):
        return False
    if not (7 <= len(value) <= 64):
        return False
    return all(c in "0123456789abcdefABCDEF" for c in value)


def validate_matrix(matrix) -> tuple[list[str], int]:
    """Validate structure + fail-closed rules. Returns (findings, cap_count)."""
    findings: list[str] = []

    if not isinstance(matrix, dict):
        return ["matrix is not a JSON object"], 0

    for field in ("version", "generated_at", "policy", "hosts"):
        if field not in matrix:
            findings.append(f"top-level field missing: {field}")
    if findings:
        return findings, 0

    hosts = matrix["hosts"]
    if not isinstance(hosts, list) or not hosts:
        return ["hosts must be a non-empty array"], 0

    seen_hosts: set[str] = set()
    total_caps = 0
    for index, host in enumerate(hosts):
        if not isinstance(host, dict):
            findings.append(f"hosts[{index}] is not an object")
            continue
        name = host.get("host")
        if not isinstance(name, str) or not name:
            findings.append(f"hosts[{index}].host missing or not a string")
            continue
        seen_hosts.add(name)

        transport = host.get("control_transport")
        if transport not in _TRANSPORTS:
            findings.append(f"hosts[{index}].control_transport={transport!r} not in {sorted(_TRANSPORTS)}")
        reach = host.get("reachability_model")
        if reach not in _REACHABILITY:
            findings.append(f"hosts[{index}].reachability_model={reach!r} not in {sorted(_REACHABILITY)}")
        truth = host.get("truth_model")
        if truth not in _TRUTH:
            findings.append(f"hosts[{index}].truth_model={truth!r} not in {sorted(_TRUTH)}")

        caps = host.get("capabilities")
        if not isinstance(caps, list) or not caps:
            findings.append(f"{name}.capabilities must be a non-empty array")
        else:
            total_caps += len(caps)
            for ci, cap in enumerate(caps):
                if not isinstance(cap, dict):
                    findings.append(f"{name}.capabilities[{ci}] is not an object")
                    continue
                cname = cap.get("name")
                if cname not in _CAP_NAMES:
                    findings.append(f"{name}.capabilities[{ci}].name={cname!r} not in {sorted(_CAP_NAMES)}")
                    continue
                if cap.get("supported") is not True:
                    continue  # only supported=true claims must carry evidence
                level = cap.get("evidence_level")
                if level not in _LEVELS:
                    findings.append(f"{name}.{cname}: evidence_level={level!r} not in {list(_LEVELS)}")
                    continue
                if _level_rank(level) < _level_rank(MIN_EVIDENCE_FOR_SUPPORTED):
                    findings.append(
                        f"{name}.{cname}: supported=true but evidence_level={level} "
                        f"< {MIN_EVIDENCE_FOR_SUPPORTED} — 能力声明不得超出证据等级")
                qsha = cap.get("qualified_sha")
                if not _hex_sha_ok(qsha):
                    findings.append(
                        f"{name}.{cname}: supported=true requires a qualified_sha "
                        f"(7-64 hex), got {qsha!r} — 没有 SHA 的 live claim 不可定位")

        auth = host.get("authorization")
        if not isinstance(auth, dict):
            findings.append(f"{name}.authorization missing or not an object")
        else:
            if auth.get("no_bypass_license") is not True:
                findings.append(f"{name}.authorization.no_bypass_license must be true — 不得绕过授权")
            if "user_authorized" not in auth or "bounded_command" not in auth:
                findings.append(f"{name}.authorization missing user_authorized/bounded_command")

        fr = host.get("failure_recovery")
        if not isinstance(fr, str) or not fr:
            findings.append(f"{name}.failure_recovery must be a non-empty string")

        if reach == "computer-use" and truth == "none":
            findings.append(
                f"{name}: reachability_model=computer-use with truth_model=none — "
                f"Computer-Use 负责 reachability 但必须配 host-native/artifact truth 层")

    missing = MIN_HOSTS - seen_hosts
    if missing:
        findings.append(f"matrix must cover hosts {sorted(MIN_HOSTS)}, missing: {sorted(missing)}")

    return findings, total_caps


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--matrix", default=None, metavar="PATH",
                        help="verify this matrix file instead of the tracked default")
    args = parser.parse_args(argv)

    matrix_path = Path(args.matrix) if args.matrix else DEFAULT_MATRIX
    if not matrix_path.is_file():
        print(f"CONTROL_CAPABILITY_MATRIX=FAIL hosts=0 capabilities=0 "
              f"findings={json.dumps([f'matrix file not found: {matrix_path}'], ensure_ascii=False)}")
        return 1
    try:
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"CONTROL_CAPABILITY_MATRIX=FAIL hosts=0 capabilities=0 "
              f"findings={json.dumps([f'matrix JSON invalid: {exc}'], ensure_ascii=False)}")
        return 1

    # schema cross-check (tracked schema file present + parses)
    if not SCHEMA_PATH.is_file():
        print(f"CONTROL_CAPABILITY_MATRIX=FAIL hosts=0 capabilities=0 "
              f"findings={json.dumps([f'schema file not found: {SCHEMA_PATH}'], ensure_ascii=False)}")
        return 1
    try:
        json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"CONTROL_CAPABILITY_MATRIX=FAIL hosts=0 capabilities=0 "
              f"findings={json.dumps([f'schema JSON invalid: {exc}'], ensure_ascii=False)}")
        return 1

    findings, total_caps = validate_matrix(matrix)
    host_count = len(matrix.get("hosts", [])) if isinstance(matrix, dict) else 0
    verdict = "PASS" if not findings else "FAIL"
    print(f"CONTROL_CAPABILITY_MATRIX={verdict} hosts={host_count} "
          f"capabilities={total_caps} findings={json.dumps(findings, ensure_ascii=False)}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
