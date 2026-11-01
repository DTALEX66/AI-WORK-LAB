#!/usr/bin/env python3
"""OTel/OpenInference mapping verifier (NX-300).

Verifies that a canonical WORK-LAB event maps losslessly to OTel semantic
fields and back, without ever exporting message bodies, secrets, full paths, or
session content.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WF_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WF_SCRIPTS))
sys.path.insert(0, str(ROOT / "services/receipts"))

from otel_mapper import (  # noqa: E402
    canonical_to_otel, otel_to_canonical, roundtrip_lossless,
    OTEL_VERSION, OPENINFERENCE_VERSION, PrivacyBlockedError,
)


def verify() -> dict:
    errors: list[str] = []

    # 1. A sample canonical event round-trips losslessly on mapped fields.
    sample = {
        "schemaVersion": "work-lab/observer-projection/v2",
        "mode": "LIVE",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "operation": "chat",
        "usage": {
            "inputTokens": 100, "outputTokens": 50,
            "cacheReadTokens": 20, "cacheWriteTokens": 5,
        },
        "latencyMs": 123,
        "outcome": "ok",
        "errorClass": None,
        "taskDigest": "abc",
        "sourceDigest": "def",
    }
    rt = roundtrip_lossless(sample)
    if not rt.get("lossless"):
        errors.append(f"roundtrip not lossless: {rt}")

    otel = canonical_to_otel(sample)
    if "gen_ai.request.model" not in otel:
        errors.append("otel mapping missing model")

    # 2. Privacy: blocked fields must raise.
    bad = dict(sample)
    bad["usage"]["gen_ai.input.messages"] = [{"role": "user", "content": "secret prompt"}]
    try:
        canonical_to_otel(bad)
        errors.append("blocked gen_ai.input.messages should raise PrivacyBlockedError")
    except PrivacyBlockedError:
        pass

    bad2 = dict(sample)
    bad2["prompt"] = "the actual prompt body"
    try:
        canonical_to_otel(bad2)
        errors.append("blocked prompt body should raise PrivacyBlockedError")
    except PrivacyBlockedError:
        pass

    # 3. Version snapshot recorded.
    if OTEL_VERSION not in otel.get("schemaVersion", ""):
        errors.append("otel version snapshot missing")
    if not OPENINFERENCE_VERSION:
        errors.append("openinference version missing")

    if errors:
        raise ValueError("; ".join(errors))
    return {"otel_version": OTEL_VERSION, "openinference_version": OPENINFERENCE_VERSION}


def main() -> int:
    try:
        result = verify()
    except (ValueError, ImportError) as exc:
        print(f"OTEL_MAPPING_FAIL {exc}")
        return 1
    print(
        f"OTEL_MAPPING_PASS lossless=true privacy_blocked=ok "
        f"otel={result['otel_version']} openinference={result['openinference_version']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
