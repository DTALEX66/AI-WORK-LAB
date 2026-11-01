"""WORK-LAB Config Control Plane (WL-P0-005 / TP-20260819).

Six-layer configuration model:
  Official Baseline -> Compatibility Baseline -> User Profile -> Project
  Override -> Machine Overlay -> Session Override -> Effective Config
  -> Diff / Approval / Apply / Readback / Drift Detection / Rollback

Contracts: SoftwareRegistrationV1, OfficialBaselineV1, CompatibilityProfileV1,
UserConfigurationProfileV1, MachineOverlayV1, SessionOverrideV1,
SecretReferenceV1, EffectiveConfigurationV1, ConfigurationDiffV1,
ConfigurationApplyPlanV1, ConfigurationReadbackV1, ConfigurationDriftV1,
ConfigurationRollbackV1.

External software (Hermes/Codex/DSH/...) is managed here as registered
configuration, never as core product identity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LAYER_ORDER = ["session_override", "project_override", "user_profile", "machine_overlay", "compatibility", "official_baseline"]

# Safety policy cannot be overridden.
SAFETY_KEYS = {"safety_boundary", "approval_required", "credential_redaction"}

# U10: a key that is ABSENT from a config snapshot is not the same thing as a
# key explicitly set to null.  A bare sentinel distinguishes the two; .get()
# would conflate them (both -> None) and hide real config semantics.
_MISSING = object()


def _json_default(obj):
    """JSON encoder for diff payloads that may carry the _MISSING sentinel."""
    if obj is _MISSING:
        return "WORKLAB_MISSING"
    return str(obj)


@dataclass
class SoftwareRegistration:
    software_id: str
    display_name: str
    category: str
    official_repository: str | None
    current_baseline_version: str | None = None
    baseline_digest: str | None = None
    adapter_id: str | None = None
    secret_fields: list[str] = field(default_factory=list)
    compatibility_status: str = "registered"

    def to_dict(self) -> dict[str, Any]:
        return {
            "softwareId": self.software_id,
            "displayName": self.display_name,
            "category": self.category,
            "officialRepository": self.official_repository,
            "currentBaselineVersion": self.current_baseline_version,
            "baselineDigest": self.baseline_digest,
            "adapterId": self.adapter_id,
            "secretFields": self.secret_fields,
            "compatibilityStatus": self.compatibility_status,
        }


class ConfigControlPlane:
    def __init__(self) -> None:
        self._software: dict[str, SoftwareRegistration] = {}
        self._layers: dict[str, dict[str, Any]] = {k: {} for k in LAYER_ORDER}
        # U10: per-software monotonic revision floor.  A commit advances the
        # floor to revision+1; a later transaction claiming a revision below
        # the floor is rejected STALE_REVISION, so a concurrent writer can
        # never silently overwrite a newer commit.
        self._revision: dict[str, int] = {}

    def current_revision(self, software_id: str) -> int:
        """U10: the current monotonic revision floor for a software."""
        return self._revision.get(software_id, 0)

    def register(self, reg: SoftwareRegistration) -> None:
        self._software[reg.software_id] = reg

    def list_registered(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._software.values()]

    def set_layer(self, layer: str, config: dict[str, Any]) -> None:
        if layer not in self._layers:
            raise ValueError(f"unknown config layer: {layer}")
        self._layers[layer] = dict(config)

    def effective(self, software_id: str | None = None) -> dict[str, Any]:
        """Merge layers by priority; safety keys always win from the safest layer."""
        merged: dict[str, Any] = {}
        for layer in reversed(LAYER_ORDER):  # official first, session last (highest priority)
            merged.update(self._layers[layer])
        # safety policy cannot be overridden by lower-priority layers
        for key in SAFETY_KEYS:
            for layer in ("official_baseline", "compatibility", "user_profile"):
                if key in self._layers[layer]:
                    merged[key] = self._layers[layer][key]
        if software_id:
            merged["softwareId"] = software_id
        return merged

    def diff(self, before: dict[str, Any], after: dict[str, Any], *,
             strict_missing: bool = False) -> dict[str, Any]:
        """Produce a field diff.

        With ``strict_missing`` (U10: MISSING-vs-explicit-null), a key that is
        ABSENT from ``before`` is reported with before=_MISSING, while a key
        explicitly set to None is reported with before=None — the two are no
        longer conflated.  Default keeps the frozen .get() semantics.
        """
        changed = {}
        for k in set(before) | set(after):
            if strict_missing:
                bval = before.get(k, _MISSING)
                aval = after.get(k, _MISSING)
            else:
                bval = before.get(k)
                aval = after.get(k)
            if bval != aval:
                changed[k] = {"before": bval, "after": aval}
        return {"changedFields": changed, "changeCount": len(changed)}

    def readback_matches(self, applied: dict[str, Any], readback: dict[str, Any]) -> bool:
        return applied == readback

    def apply_plan(self, diff: dict[str, Any], *, approved: bool = False) -> dict[str, Any]:
        if not approved:
            return {"status": "WAITING_APPROVAL", "changeCount": diff["changeCount"]}
        return {"status": "UNSUPPORTED_APPLY", "changeCount": diff["changeCount"],
                "reason": "a plan is not a native write; use an adapter transaction"}

    def detect_drift(self, effective: dict[str, Any], readback: dict[str, Any]) -> dict[str, Any]:
        drifted = {k: {"effective": effective.get(k), "readback": readback.get(k)} for k in set(effective) | set(readback) if effective.get(k) != readback.get(k)}
        return {"drift": drifted, "driftCount": len(drifted), "status": "DRIFT" if drifted else "CLEAN"}

    def rollback(self, target: dict[str, Any], rollback_to: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ROLLBACK_REQUIRED", "restored": False,
                "reason": "no native rollback operation was performed"}

    # --- WLR-330: real config transaction (Discover -> Effective -> Diff -> Backup
    # -> Approval -> Apply -> Readback -> Commit or Rollback) ---
    def transaction(self, software_id: str, diff: dict[str, Any], *, approved: bool = False,
                    backup_dir: str | None = None, apply_fn=None, readback_fn=None,
                    idempotency_key: str | None = None, rollback_fn=None,
                    simulated: bool = False, revision: int | None = None,
                    expected_before: dict[str, Any] | None = None,
                    write_set: list[str] | None = None,
                    expected_after: dict[str, Any] | None = None) -> dict[str, Any]:
        """Adapter callback transaction; this is not durable transaction storage.
        The idempotency key is a receipt identifier, not replay prevention.
        Rollback requires a callback and a matching readback. Unapproved never writes live.

        - idempotency_key: caller-supplied stable operation identity
          (NF-04/A03: the key must NOT embed wall-clock time — replaying the
          same operation must yield the same key). When omitted, a stable
          digest of (software_id, diff) is derived; callers add their own
          nonce only when they intentionally need a fresh operation.
        - backup: effective config snapshot persisted (backup ref)
        - apply:  apply_fn(effective_after) if approved (else WAITING_APPROVAL)
        - readback: readback_fn() must equal the applied effective config
        - mismatch -> rollback to backup; match -> COMMITTED with receipt

        NF-04 honest-state additions (a plan is never a real write, so the
        transaction surfaces real outcomes rather than faking success):
        - NOOP: an approved empty diff (changeCount==0) never touches live
          config and needs no backup/apply/readback cycle.
        - APPLY_FAILED: apply_fn raised -> it is UNDETERMINED whether anything
          was written; we report that state and do NOT fake a rollback/success.
        - SIMULATED: when simulated=True the success outcomes are tagged
          *SIMULATED so a simulated adapter can never be counted into real
          applied-success statistics (NF-04 acceptance point 1).
        """
        import hashlib, json
        from pathlib import Path

        effective_before = self.effective(software_id)
        if idempotency_key is not None:
            idem = hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]
        else:
            idem = hashlib.sha256(
                (software_id + json.dumps(diff, sort_keys=True, default=_json_default)).encode()
            ).hexdigest()[:16]
        # --- U10 pre-flight truth gates (before anything writes live) ----
        # 1. monotonic revision floor: a writer claiming a stale revision must
        #    be rejected so a concurrent newer commit can't be clobbered.
        if revision is not None:
            floor = self._revision.get(software_id, 0)
            if revision < floor:
                return {"status": "STALE_REVISION", "idempotencyKey": idem,
                        "requestedRevision": revision, "currentRevision": floor,
                        "simulated": simulated}
        # 2. optimistic expected_before: the caller declares the state it read.
        #    If live before has drifted from it, refuse to write (CONFLICT).
        if expected_before is not None and any(
                effective_before.get(k, _MISSING) != v for k, v in expected_before.items()):
            return {"status": "CONFLICT", "idempotencyKey": idem,
                    "expectedBefore": expected_before, "liveBefore": effective_before,
                    "simulated": simulated}

        if not approved:
            return {"status": "WAITING_APPROVAL", "idempotencyKey": idem, "changeCount": diff.get("changeCount", 0)}

        # NF-04: an approved empty diff is a genuine no-op — it must not enter
        # the backup/apply/readback cycle and must not be reported as a write.
        if diff.get("changeCount", 0) == 0:
            return {"status": "NOOP", "idempotencyKey": idem, "changeCount": 0,
                    "simulated": simulated, "reason": "no fields changed; nothing applied"}

        # backup (recovery point)
        backup_ref = None
        if backup_dir:
            bdir = Path(backup_dir)
            bdir.mkdir(parents=True, exist_ok=True)
            backup_ref = bdir / f"{software_id}-{idem}.json"
            backup_ref.write_text(json.dumps(effective_before, ensure_ascii=False, indent=2), encoding="utf-8")

        # apply (only via provided apply_fn — never a bare in-memory return)
        if apply_fn is None:
            return {"status": "UNSUPPORTED_APPLY", "idempotencyKey": idem, "reason": "no adapter apply_fn"}
        try:
            apply_result = apply_fn(effective_before)
        except Exception as exc:
            # NF-04 honest-state: a raised write leaves it UNDETERMINED whether
            # anything landed. We report the failure type and never fabricate a
            # ROLLED_BACK / COMMITTED / success outcome from it.
            return {"status": "APPLY_FAILED", "idempotencyKey": idem, "written": "UNDETERMINED",
                    "restored": False, "errorType": type(exc).__name__,
                    "backupRef": str(backup_ref) if backup_ref else None,
                    "simulated": simulated}

        # --- U10 write-set enforcement (after a successful apply) --------
        # When the caller declared the keys it is allowed to touch, any key the
        # apply introduced outside that set is a violation — the operation must
        # not be counted as a commit even though apply_fn "succeeded".
        if write_set is not None and isinstance(apply_result, dict):
            allowed = set(write_set)
            smuggled = sorted(k for k in apply_result if k not in allowed)
            if smuggled:
                return {"status": "WRITE_SET_VIOLATION", "idempotencyKey": idem,
                        "writeSet": sorted(allowed), "smuggledKeys": smuggled,
                        "committed": False, "simulated": simulated,
                        "backupRef": str(backup_ref) if backup_ref else None}

        # readback (must match applied effective)
        if readback_fn is not None:
            readback = readback_fn()
            # --- U10 typed readback gate: a non-dict readback is a distinct,
            #     honest failure — never coerced into a commit / drift-clean.
            if not isinstance(readback, dict):
                return {"status": "READBACK_FAILED_TYPED", "idempotencyKey": idem,
                        "committed": False, "restored": False,
                        "readbackType": type(readback).__name__,
                        "simulated": simulated,
                        "backupRef": str(backup_ref) if backup_ref else None}
            # --- U10 intended-after verification: if the caller declared the
            #     state the live config must read back to, a mismatch is a
            #     distinct failure (apply "succeeded" yet landed elsewhere).
            if expected_after is not None and any(
                    readback.get(k, _MISSING) != v for k, v in expected_after.items()):
                return {"status": "READBACK_MISMATCH", "idempotencyKey": idem,
                        "committed": False, "restored": False,
                        "expectedAfter": expected_after, "observedAfter": readback,
                        "simulated": simulated,
                        "backupRef": str(backup_ref) if backup_ref else None}
            drift = self.detect_drift(apply_result if isinstance(apply_result, dict) else {}, readback)
            if drift["status"] == "DRIFT":
                # rollback to backup
                if rollback_fn is None:
                    return {"status": "ROLLBACK_REQUIRED", "idempotencyKey": idem,
                            "drift": drift, "restored": False, "simulated": simulated,
                            "backupRef": str(backup_ref) if backup_ref else None}
                try:
                    rollback_fn(dict(effective_before))
                    restored = readback_fn() == effective_before
                except Exception as exc:
                    # Do not include exception messages: an adapter may embed
                    # private config values in them.
                    return {"status": "ROLLBACK_FAILED", "idempotencyKey": idem,
                            "restored": False, "errorType": type(exc).__name__,
                            "simulated": simulated}
                suf = "_SIMULATED" if simulated else ""
                return {"status": ("ROLLED_BACK" + suf) if restored else "ROLLBACK_FAILED",
                        "idempotencyKey": idem, "drift": drift, "restored": restored,
                        "simulated": simulated,
                        "backupRef": str(backup_ref) if backup_ref else None}
            # U10: a true, verified commit advances the monotonic revision floor.
            if revision is not None:
                self._revision[software_id] = revision + 1
            else:
                self._revision[software_id] = self._revision.get(software_id, 0) + 1
            suf = "_SIMULATED" if simulated else ""
            return {"status": "COMMITTED" + suf, "idempotencyKey": idem,
                    "backupRef": str(backup_ref) if backup_ref else None, "receipt": idem,
                    "committed": True, "revision": self._revision[software_id],
                    "simulated": simulated}
        suf = "_SIMULATED" if simulated else ""
        return {"status": "APPLIED_NO_READBACK" + suf, "idempotencyKey": idem,
                "backupRef": str(backup_ref) if backup_ref else None, "committed": False,
                "simulated": simulated}
