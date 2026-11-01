#!/usr/bin/env python3
"""ACP compatibility-layer verifier (NX-200).

Runs static ACP conformance for all known clients + a Qwen Code pilot probe.
Unknown protocol version must degrade gracefully; unavailable Qwen must not
fail the project.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # WORK-LAB root
WF_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WF_SCRIPTS))
sys.path.insert(0, str(ROOT / "integrations/executors/codex"))

from acp_adapter import (  # noqa: E402
    CLIENT_CAPABILITIES, READ_ONLY_OPERATIONS, SUPPORTED_PROTOCOL_VERSIONS,
    build_adapter, make_qwen_code_pilot,
)


def verify() -> dict:
    errors: list[str] = []
    results: dict = {}

    # 1. Every known client builds an adapter.
    for client_id in CLIENT_CAPABILITIES:
        try:
            adapter = build_adapter(client_id)
        except ValueError as exc:
            errors.append(f"{client_id}: build failed: {exc}")
            continue
        # init on supported version -> OK, not degraded
        init = adapter.init()
        if init["status"] != "OK":
            errors.append(f"{client_id}: init failed")
        # capabilities readable
        cap = adapter.capabilities()
        if cap["status"] == "UNAVAILABLE":
            results[client_id] = "UNAVAILABLE"
            continue
        if not cap["operations"]:
            errors.append(f"{client_id}: no operations")
        # read-only must be a subset
        if not set(cap["read_only"]).issubset(set(cap["operations"])):
            errors.append(f"{client_id}: read_only not subset of operations")
        results[client_id] = "OK"

    # 2. Unknown protocol version degrades gracefully (fail closed, not crash).
    adapter = build_adapter("hermes")
    degraded = adapter.init(requested_version="99.0.0")
    if degraded["status"] != "OK" or not degraded.get("degraded"):
        errors.append("unknown protocol version must degrade gracefully")
    if degraded["protocol_version"] not in SUPPORTED_PROTOCOL_VERSIONS:
        errors.append("degraded protocol version must fall back to a supported one")

    # 3. Unsupported feature negotiates as unsupported (graceful), not a crash.
    neg = adapter.negotiate(["detect", "teleport", "observe"])
    if neg["status"] != "OK":
        errors.append("negotiate must not fail on unsupported features")
    if "teleport" not in neg["unsupported"]:
        errors.append("unsupported feature must be reported as unsupported")

    # 4. Qwen Code pilot: unavailable must not fail the project.
    qwen = make_qwen_code_pilot()
    qcap = qwen.capabilities()
    if qcap["status"] not in {"OK", "UNAVAILABLE"}:
        errors.append(f"qwen-code unexpected status: {qcap['status']}")

    if errors:
        raise ValueError("; ".join(errors))
    return {
        "clients": len(CLIENT_CAPABILITIES),
        "protocol_versions": list(SUPPORTED_PROTOCOL_VERSIONS),
        "read_only_ops": list(READ_ONLY_OPERATIONS),
        "client_results": results,
    }


def main() -> int:
    try:
        result = verify()
    except (ValueError, ImportError) as exc:
        print(f"ACP_CONFORMANCE_FAIL {exc}")
        return 1
    ok = sum(1 for v in result["client_results"].values() if v == "OK")
    unavail = sum(1 for v in result["client_results"].values() if v == "UNAVAILABLE")
    print(
        f"ACP_CONFORMANCE_PASS clients={result['clients']} ok={ok} unavailable={unavail} "
        f"protocol={result['protocol_versions']} degradation=fail-closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
