#!/usr/bin/env python3
"""NX-600 offline source health monitor verifier."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

from source_health_monitor import (  # noqa: E402
    RollbackEvidence,
    SourceSnapshot,
    compare_upstream,
    discover_candidate,
    offline_osv_scan,
    scorecard_signal,
)


def verify() -> dict[str, int]:
    approved = SourceSnapshot(
        "fixture-source", "abc123", "MIT", False,
        ("parse", "render", "export"), False, "owner-a", "fixture-pkg", "1.0.0",
    )
    rollback = RollbackEvidence("fixture-source", "abc123", "1.0.0", "git:abc123")
    scenarios = [
        ("license", approved.__class__(**{**approved.__dict__, "license_id": "GPL-3.0"}), "LICENSE_CHANGED"),
        ("postinstall", approved.__class__(**{**approved.__dict__, "has_postinstall": True}), "POSTINSTALL_ADDED"),
        ("api", approved.__class__(**{**approved.__dict__, "api_surface": ("parse", "render")}), "API_REMOVED"),
        ("archive", approved.__class__(**{**approved.__dict__, "archived": True}), "REPOSITORY_ARCHIVED"),
        ("takeover", approved.__class__(**{**approved.__dict__, "package_owner": "owner-b"}), "PACKAGE_OWNERSHIP_CHANGED"),
    ]
    for _, candidate, reason in scenarios:
        result = compare_upstream(approved, candidate, rollback)
        assert result.status == "UPSTREAM_CHANGED"
        assert result.update_decision == "BLOCK_UPDATE"
        assert reason in result.reasons
        assert result.rollback == rollback

    candidate = discover_candidate("new-source", "new-pkg")
    assert candidate["status"] == "DISCOVERED"
    assert candidate["decision"] == "QUARANTINED"
    assert candidate["installation"] == "FORBIDDEN"

    osv = offline_osv_scan(
        [{"name": "fixture-pkg", "version": "1.0.0"}],
        {"fixture-pkg": ["OSV-2026-0001"]},
    )
    assert osv["mode"] == "OFFLINE_READ_ONLY"
    assert osv["auto_fix"] is False
    assert osv["findings"][0]["advisories"] == ["OSV-2026-0001"]
    assert osv["findings"][0]["fix"] == "MANUAL_REVIEW_ONLY"

    signal = scorecard_signal("fixture-source", 8.4)
    assert signal["decision_role"] == "SIGNAL_ONLY"
    assert signal["requires_review"] is False

    return {"upstream_change_controls": len(scenarios), "quarantined_candidates": 1}


def main() -> int:
    try:
        result = verify()
    except (AssertionError, ValueError, TypeError) as exc:
        print(f"SOURCE_HEALTH_FAIL {exc}")
        return 1
    print(
        "SOURCE_HEALTH_PASS "
        f"upstream_change_controls={result['upstream_change_controls']} "
        f"quarantined_candidates={result['quarantined_candidates']} "
        "osv=offline_read_only scorecard=signal_only rollback=preserved"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
