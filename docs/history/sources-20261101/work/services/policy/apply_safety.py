"""WLG-100: global config apply safety contract.

Every apply must follow:
  plan -> diff -> approval -> backup -> atomic apply -> readback -> rollback

Rules:
- official config schema wins;
- unknown fields preserved (OBSERVE/quarantine, never silently deleted);
- provider/model/auth default OBSERVE (never auto-apply);
- no cross-client sync of prompt/skill/memory/session bodies;
- apply failure must never leave the client unstartable.
"""

from __future__ import annotations

APPLY_SEQUENCE = (
    "plan",
    "diff",
    "approval",
    "backup",
    "atomic_apply",
    "readback",
    "rollback",
)

SAFETY_INVARIANTS = (
    "official_schema_wins",
    "unknown_preserved",
    "provider_model_auth_observe",
    "no_cross_client_body_sync",
    "failure_never_breaks_client",
)


def validate_apply_sequence(order: tuple[str, ...]) -> bool:
    return order == APPLY_SEQUENCE
