"""Read-only client value loop (integrated-taskpack-20260916 NF-05 / NF-06).

Aggregates a client adapter's probe evidence (installed / version / supported
capabilities) into a desensitized, write-free value receipt. This is a pure
function over in-memory records: it never shells out, never reads credentials
or private session stores, never writes live config, and never calls a paid
model API. A simulated adapter is flagged so it can never enter the real
applied-success tally.

The receipt answers NF-06 ("one real client's read-only value closed loop")
while staying strictly read-only: what is installed, what is confirmed
supported (with version + entry evidence), what is an honest capability gap
(NOT displayed as "adapted"), and the next step.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

# capabilities that are read-only observations; a value receipt may list them
# as "supported observations" but they never imply a write surface.
READ_ONLY_OBSERVATIONS = ("observe", "detect", "capabilities", "negotiate", "init")

# capabilities the value loop explicitly checks for gaps when a client is
# installed. Absence is an honest UNSUPPORTED gap, never silently filled.
_PROBE_CHECK_CAPS = ("run_status", "token_usage")


def classify_probe(probe_record: Mapping[str, Any]) -> Dict[str, Any]:
    """Split a probe record's declared capabilities into honest buckets.

    A capability is "supported" only if the adapter actually probed it; an
    absent capability is an explicit capability gap, never silently filled
    (NF-05: an unsupported feature must not be displayed as "adapted").
    """
    installed = bool(probe_record.get("installed", False))
    caps = set(probe_record.get("capabilities", []))
    version = probe_record.get("version")
    return {
        "installed": installed,
        "version": version if version else None,      # None => not evidenced, never faked
        "supported_actions": sorted(caps),
        "capability_gaps": [c for c in _PROBE_CHECK_CAPS if c not in caps],
        "evidence_level": probe_record.get("evidence_level", "B"),
    }


def build_readonly_value_report(
    client_id: str,
    probe_record: Mapping[str, Any],
    ownership: Mapping[str, Any],
    conformance: Mapping[str, Any],
    *,
    simulated: bool = False,
) -> Dict[str, Any]:
    """Produce a desensitized, write-free value receipt for one client."""
    owner = ownership.get("adapter_defaults", {}).get(client_id, {})
    mode = owner.get("mode", "OBSERVE")
    c = classify_probe(probe_record)
    # only an explicitly MANAGED ownership mode carries any write surface;
    # every observe/ignore/forbid mode has NO write surface at all.
    write_surface = mode == "MANAGE"
    next_step = _next_step(c, mode, write_surface)
    return {
        "client": client_id,
        "installed": c["installed"],
        "version": c["version"],
        "supported_actions": c["supported_actions"],
        "capability_gaps": c["capability_gaps"],        # honest gaps, not "adapted"
        "ownership_mode": mode,
        "write_surface": write_surface,                 # False for every observe-only client
        "conformance_unverified": unverified_protocols(conformance),
        "privacy": "metadata-only",
        "simulated": simulated,
        "next_step": next_step,
    }


def unverified_protocols(conformance: Mapping[str, Any]) -> List[str]:
    """Protocol views that are NOT statically verified must be surfaced, never
    counted as conformance-passed (NF-05: no 'adapted' claim without evidence)."""
    out: List[str] = []
    for section, val in conformance.items():
        if isinstance(val, dict) and val.get("status") != "STATIC_PASS":
            out.append(f"{section}={val.get('status', 'UNKNOWN')}")
    return out


def _next_step(c: Mapping[str, Any], mode: str, write_surface: bool) -> str:
    if not c["installed"]:
        return ("not-installed: no value claim is made; installing is a user "
                "action, not a WORK-LAB step")
    if c["version"] is None:
        return "version-not-evidenced: installed but no version probed; do not assert a version"
    if c["capability_gaps"]:
        return f"capability-gap: {c['capability_gaps']} remain UNSUPPORTED; not displayed as adapted"
    if not write_surface:
        return "observe-only: value is read-only (no write surface); management stays with the native client"
    return "manage-capable: a scoped, approved write loop (NF-07) may apply fields the user owns"


def apply_receipt(receipt: Mapping[str, Any]) -> Dict[str, Any]:
    """A value receipt is OBSERVED, not APPLIED. Any caller that tried to
    'apply' it gets an explicit NO-OP, never a fake success (NF-06 do_not:
    a read-only version must not be called a deployment)."""
    return {"status": "OBSERVED_ONLY", "applied": False,
            "client": receipt.get("client"),
            "reason": "a read-only value receipt has no write surface; apply is a no-op"}
