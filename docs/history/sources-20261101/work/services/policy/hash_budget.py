"""WLG-060: hash/idempotency budget contract.

Three-tier digest budget:

- REAL-TIME (Task ID, idempotency key, ledger event digest, desired-state
  digest, evidence envelope digest) — persisted in the ledger.
- STAGE (frozen tree SHA, gate plan digest, stage qualification evidence).
- RELEASE-ONLY (exact-SHA attestation, installer/package checksum,
  SBOM/signature/download readback).

NEVER hash or persist secrets, raw memory, sessions, or prompt/response
bodies.
"""

from __future__ import annotations

REAL_TIME_DIGESTS = (
    "task_id",
    "idempotency_key",
    "ledger_event_digest",
    "desired_state_digest",
    "evidence_envelope_digest",
)

STAGE_DIGESTS = (
    "frozen_tree_sha",
    "gate_plan_digest",
    "stage_qualification_evidence",
)

RELEASE_ONLY_DIGESTS = (
    "exact_sha_attestation",
    "installer_checksum",
    "package_checksum",
    "sbom",
    "signature",
    "download_readback",
)

FORBIDDEN_DIGEST_INPUTS = (
    "secrets",
    "raw_memory",
    "sessions",
    "prompt_bodies",
    "response_bodies",
)


def validate_budget() -> dict[str, int]:
    return {
        "real_time": len(REAL_TIME_DIGESTS),
        "stage": len(STAGE_DIGESTS),
        "release_only": len(RELEASE_ONLY_DIGESTS),
        "forbidden_inputs": len(FORBIDDEN_DIGEST_INPUTS),
    }
